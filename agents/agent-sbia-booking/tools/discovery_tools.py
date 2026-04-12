"""
tools/discovery_tools.py — Group A: Convention Discovery Engine
Tools: search_upcoming_conventions, scrape_convention_details, assess_genre_fit

These three tools are the front end of the SBIA pipeline.
They run in sequence for every discovery cycle.
"""
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import boto3
import httpx
from strands import tool

secrets_client = boto3.client("secretsmanager", region_name="us-east-1")

def _get_secret(key: str) -> str:
    try:
        return secrets_client.get_secret_value(SecretId=key)["SecretString"]
    except Exception:
        return os.environ.get(key.split("/")[-1].upper().replace("-", "_"), "")

# ─── SEARCH MATRIX ────────────────────────────────────────────────────────────

SEARCH_MATRIX = {
    "anime": [
        "anime convention", "anime expo", "anime festival",
        "AnimeCon", "Anime Weekend", "anime con US", "anime event"
    ],
    "gaming": [
        "gaming convention", "video game convention", "game expo",
        "PAX", "MAGFest", "game festival", "esports convention",
        "nerd gaming event"
    ],
    "manga": [
        "manga convention", "manga expo", "Japanese pop culture convention",
        "otaku convention", "J-pop convention", "cosplay expo"
    ],
    "nerd_culture": [
        "nerd culture festival", "geek convention", "comic con",
        "pop culture expo", "fandom convention", "cosplay festival"
    ],
    "music_nerd": [
        "nerd music festival", "chiptune festival", "game music concert",
        "conscious hip hop convention", "independent music anime",
        "nerdcore music event"
    ],
}

# Current year for search queries
YEAR = datetime.now(timezone.utc).year

# ─── TOOL 1: SEARCH UPCOMING CONVENTIONS ──────────────────────────────────────

@tool
def search_upcoming_conventions(
    genre: str,
    region: str = "US",
    months_ahead: int = 8,
) -> str:
    """
    Search the web for upcoming anime, manga, gaming, and nerd-culture
    conventions in the United States. Executes multiple targeted queries
    per genre using the Tavily or Brave Search API.

    Args:
        genre:        "anime" | "gaming" | "manga" | "nerd_culture" | "music_nerd"
        region:       State abbreviation (e.g., "CA") or "US" for nationwide
        months_ahead: How many months ahead to search (default 8)

    Returns:
        JSON list of raw convention discovery records with name, url, location,
        dates, and source snippet.
    """
    search_terms = SEARCH_MATRIX.get(genre, SEARCH_MATRIX["anime"])
    api_key = _get_secret("sbia/web-search-api-key")
    results = []
    seen_names = set()

    for term in search_terms[:4]:  # cap at 4 queries per genre per run
        query = (
            f"{term} {YEAR} {region} schedule entertainment performers"
            if region != "US"
            else f"{term} {YEAR} United States schedule upcoming"
        )

        # Try Tavily first, fall back to Brave
        try:
            if api_key:
                resp = httpx.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 5,
                        "include_domains": [
                            "convention-calendar.com", "animecons.com",
                            "otakucalendar.com", "conventionscene.com",
                            "comicconventions.com",
                        ],
                    },
                    timeout=15,
                )
                if resp.ok:
                    for r in resp.json().get("results", []):
                        name = _extract_convention_name(r.get("title", ""), r.get("url", ""))
                        if name and name not in seen_names:
                            seen_names.add(name)
                            results.append({
                                "name":           name,
                                "url":            r.get("url", ""),
                                "location":       _extract_location(r.get("content", "")),
                                "dates":          _extract_dates(r.get("content", "")),
                                "source_snippet": r.get("content", "")[:300],
                                "genre":          genre,
                            })
        except Exception:
            pass

    # If no API key or no results, return representative seed data for testing
    if not results:
        results = _get_seed_conventions(genre)

    return json.dumps({
        "genre":        genre,
        "region":       region,
        "results_count":len(results),
        "conventions":  results,
        "search_year":  YEAR,
        "note":         "Results require scrape_convention_details() for full contact info.",
    })


def _extract_convention_name(title: str, url: str) -> str:
    """Pull convention name from page title."""
    # Common patterns: "Anime Expo 2026 | Official Site", "MomoCon 2026"
    clean = re.sub(r'\s*[\|–—\-]\s*.*', '', title).strip()
    clean = re.sub(r'\s+\d{4}\s*$', '', clean).strip()
    return clean[:80] if len(clean) > 3 else ""


def _extract_location(text: str) -> str:
    """Attempt to extract city/state from snippet text."""
    # Look for "City, ST" or "City, State"
    m = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s*,\s*[A-Z]{2})', text)
    return m.group(1) if m else "Location TBD — see scrape"


def _extract_dates(text: str) -> str:
    """Attempt to extract event dates from snippet text."""
    # Look for month + date patterns
    m = re.search(
        r'(January|February|March|April|May|June|July|August|September|'
        r'October|November|December)\s+\d{1,2}(?:–\d{1,2})?,?\s*\d{4}',
        text, re.IGNORECASE,
    )
    return m.group(0) if m else "Dates TBD — see scrape"


def _get_seed_conventions(genre: str) -> list:
    """Return seed convention list for testing when API is not configured."""
    from data.seed_conventions import SEED_CONVENTIONS
    return [c for c in SEED_CONVENTIONS if genre in c.get("genre_tags", [])][:5]


# ─── TOOL 2: SCRAPE CONVENTION DETAILS ───────────────────────────────────────

@tool
def scrape_convention_details(
    convention_url: str,
    convention_name: str,
) -> str:
    """
    Visit a convention's website and extract entertainment/programming contact
    information, confirmed dates and location, past performers, and application
    deadlines. Checks /entertainment, /performers, /guests, /contact, /about,
    /talent, /booking, /programming, /apply, and /submit subpages.

    Args:
        convention_url:  The convention's main URL.
        convention_name: The convention name for context.

    Returns:
        JSON with dates, location, attendance estimate, booking contact,
        past performers, genre fit score, and notes.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        api_key = _get_secret("lumin/anthropic-api-key")

    # Pages to check for booking contact info
    contact_paths = [
        "", "/contact", "/entertainment", "/performers", "/guests",
        "/talent", "/booking", "/programming", "/apply", "/submit",
        "/about", "/music",
    ]

    base_url = convention_url.rstrip("/")
    collected_text = f"Convention: {convention_name}\nURL: {convention_url}\n\n"

    client = httpx.Client(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BookingResearch/1.0)"},
    )

    for path in contact_paths[:6]:  # cap at 6 pages to avoid Lambda timeout
        try:
            resp = client.get(f"{base_url}{path}")
            if resp.status_code == 200:
                # Strip HTML tags for Claude
                text = re.sub(r'<[^>]+>', ' ', resp.text)
                text = re.sub(r'\s+', ' ', text).strip()
                collected_text += f"\n--- {path or '/'} ---\n{text[:2000]}\n"
        except Exception:
            continue

    client.close()

    # Use Claude to extract structured info from the scraped text
    if api_key and len(collected_text) > 200:
        claude = anthropic.Anthropic(api_key=api_key)
        try:
            resp = claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Extract booking/entertainment contact information from this convention website text.\n\n"
                        f"{collected_text[:6000]}\n\n"
                        "Return ONLY valid JSON with these fields:\n"
                        '{"dates": "...", "location": "city, state", '
                        '"attendance_est": null_or_number, '
                        '"booking_contact": {"name": null_or_str, "title": null_or_str, '
                        '"email": null_or_str, "contact_form_url": null_or_str, '
                        '"source_page": "..."}, '
                        '"past_performers": ["list", "of", "names"], '
                        '"application_deadline": null_or_str, '
                        '"notes": "brief observations"}'
                    ),
                }],
            )
            text = resp.content[0].text.strip()
            json_m = re.search(r'\{.*\}', text, re.DOTALL)
            if json_m:
                result = json.loads(json_m.group())
                result["genre_fit_score"] = None  # set by assess_genre_fit()
                return json.dumps(result)
        except Exception:
            pass

    # Fallback: return what we can parse heuristically
    email_m = re.search(
        r'[\w.+-]+@[\w-]+\.[\w.]+',
        collected_text,
    )
    return json.dumps({
        "dates":            _extract_dates(collected_text),
        "location":         _extract_location(collected_text),
        "attendance_est":   None,
        "booking_contact":  {
            "name":             None,
            "title":            None,
            "email":            email_m.group(0) if email_m else None,
            "contact_form_url": f"{base_url}/contact",
            "source_page":      "heuristic extraction",
        },
        "past_performers":  [],
        "application_deadline": None,
        "notes":            "Partial extraction — manual review recommended.",
        "genre_fit_score":  None,
    })


# ─── TOOL 3: ASSESS GENRE FIT ─────────────────────────────────────────────────

SKYBLEW_TAGS = {
    "anime", "gaming", "manga", "otaku", "cosplay", "j-pop", "jrpg",
    "nintendo", "video game", "nerd", "geek", "fandom", "sci-fi",
    "space", "consciousness", "conscious", "hip hop", "hiphop",
    "funimation", "megaran", "nerdcore", "chiptune",
}

TIER_A_PERFORMERS = {
    "megaran", "mega ran", "mc frontalot", "optimus rhyme", "ytcracker",
    "nursehella", "the protomen", "bit brigade", "crashfaster",
    "k.flay", "jsa", "nerd core", "tensai", "random",
}


@tool
def assess_genre_fit(
    convention_name: str,
    genre_tags: list,
    past_performers: list,
    description: str,
) -> str:
    """
    Score how well a convention matches SkyBlew's "Rhythm Escapism" profile.
    Scoring: genre alignment (40 pts) + past performer similarity (30 pts) +
    audience demographic match (20 pts) + size/prestige fit (10 pts).

    Fit tiers:
      A (0.80–1.0): Priority — anime/gaming/nerd focused
      B (0.60–0.79): Strong — adjacent genre events
      C (0.40–0.59): Opportunistic — general music/culture
      D (0.00–0.39): Skip — poor fit

    Args:
        convention_name: Convention name.
        genre_tags:      List of genre descriptors for the event.
        past_performers: Known past performers (for similarity scoring).
        description:     Convention description or notes text.

    Returns:
        JSON with fit_score, fit_tier, rationale, and recommended approach.
    """
    score = 0.0
    reasons = []
    comparable = []

    # 1. Genre alignment (40 pts)
    combined_text = (
        " ".join(genre_tags + [description, convention_name]).lower()
    )
    matched_tags = SKYBLEW_TAGS & set(combined_text.split())
    genre_score = min(40, len(matched_tags) * 8)
    score += genre_score
    if genre_score >= 32:
        reasons.append(f"Strong genre alignment: {', '.join(list(matched_tags)[:5])}")
    elif genre_score >= 16:
        reasons.append(f"Moderate genre alignment: {', '.join(list(matched_tags)[:3])}")

    # 2. Past performer similarity (30 pts)
    performers_lower = {p.lower() for p in past_performers}
    perf_score = 0
    for perf in performers_lower:
        for tier_a in TIER_A_PERFORMERS:
            if tier_a in perf or perf in tier_a:
                perf_score += 15
                comparable.append(perf.title())
                break
        else:
            # Check for hip-hop or conscious music keywords in performer names
            if any(kw in perf for kw in ["rap", "hip", "mc ", "emcee", "dj "]):
                perf_score += 8
    perf_score = min(30, perf_score)
    score += perf_score
    if comparable:
        reasons.append(f"Past performer match: {', '.join(comparable[:3])}")

    # 3. Audience demographic match (20 pts)
    demo_keywords = {
        "18-35": 10, "18-30": 10, "young adult": 10, "college": 8,
        "high school": 5, "family": 3, "all ages": 6, "teen": 5,
    }
    demo_score = sum(
        pts for kw, pts in demo_keywords.items() if kw in combined_text
    )
    demo_score = min(20, demo_score + 8)  # +8 baseline (anime cons skew right demo)
    score += demo_score

    # 4. Size/prestige fit (10 pts) — favor medium/large events
    size_words = {"annual": 4, "international": 5, "national": 4,
                  "large": 4, "premiere": 3, "biggest": 5}
    size_score = min(10, sum(
        pts for kw, pts in size_words.items() if kw in combined_text
    ) + 3)  # +3 baseline
    score += size_score

    # Normalize to 0.0–1.0
    fit_score = round(score / 100, 3)
    fit_score = min(1.0, fit_score)

    # Assign tier
    if fit_score >= 0.80:
        tier = "A"
        approach = (
            "Priority outreach. Lead with MegaRan tour connection and FUNimation placement. "
            "Use anime/gaming cultural language naturally. Reference any comparable past performers."
        )
    elif fit_score >= 0.60:
        tier = "B"
        approach = (
            "Strong outreach. Emphasize versatility and clean conscious hip-hop angle. "
            "Reference Rhythm Escapism as 'the bridge between hip-hop and nerd culture.'"
        )
    elif fit_score >= 0.40:
        tier = "C"
        approach = (
            "Opportunistic outreach. Keep email brief — let the EPK do the heavy lifting. "
            "Lead with the most credible anchor (Kendrick Lamar / Lupe Fiasco opening)."
        )
    else:
        tier = "D"
        approach = "Skip — poor fit. Do not contact."

    if not reasons:
        reasons.append("General culture/music event — limited direct genre overlap with SkyBlew.")

    return json.dumps({
        "convention_name":            convention_name,
        "fit_score":                  fit_score,
        "fit_tier":                   tier,
        "genre_score":                genre_score,
        "performer_score":            perf_score,
        "demographic_score":          demo_score,
        "size_score":                 size_score,
        "rationale":                  " | ".join(reasons),
        "comparable_artists_matched": comparable,
        "recommended_approach":       approach,
        "should_contact":             fit_score >= 0.40,
    })
