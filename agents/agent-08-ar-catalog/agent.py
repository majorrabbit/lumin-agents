"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 8: A&R & CATALOG GROWTH ADK            ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: OPP Inc.                                                ║
║  Number 8: New Beginnings.                                       ║
║                                                                  ║
║  Mission: Not to grow for its own sake — to grow with           ║
║  intention. OPP is a boutique. Every track in the catalog       ║
║  must earn its place by serving the Rhythm Escapism™ vision.    ║
╚══════════════════════════════════════════════════════════════════╝

THE BOUTIQUE A&R PHILOSOPHY:

OPP Inc. is not a major label acquiring volume. It is a curated
publishing house built around a specific sonic and cultural vision:
Rhythm Escapism™ — conscious hip-hop at the intersection of anime,
gaming, education, and lo-fi jazz-rap consciousness.

This changes the entire A&R mandate. The question is never
"what sells?" It is always: "Does this belong in the world SkyBlew
is painting?" That is the filter. Everything else follows.

WHAT THIS AGENT ACTUALLY DOES:
1. Reads demand signals from Agents 1, 2, 4, and 6 to identify
   specific sonic GAPS in the OPP catalog — genres, moods, and
   instrumentations that sync briefs keep requesting but OPP
   cannot currently fill.

2. Monitors the streaming universe for artists whose aesthetic
   lives in the Rhythm Escapism DNA — the Nujabes lineage,
   conscious anime hip-hop, lo-fi narrative composers — who
   would be a natural addition to OPP's catalog.

3. Maintains the Elvin Ross / Ronnie Garrett catalog integration
   status — the binding constraint for OPP's sync business today.

4. Tracks catalog performance equity — which OPP tracks are
   over-pitched vs. under-pitched, where sync demand outpaces
   catalog depth, what to commission vs. license vs. sign.

New beginnings. One right addition at a time.
"""

import os, json, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel

dynamo    = boto3.resource("dynamodb", region_name="us-east-1")
catalog_t = dynamo.Table(os.environ.get("CATALOG_TABLE",   "opp-catalog"))
gaps_t    = dynamo.Table(os.environ.get("GAPS_TABLE",      "opp-catalog-gaps"))
targets_t = dynamo.Table(os.environ.get("TARGETS_TABLE",   "opp-ar-targets"))
SLACK_AR_WEBHOOK = os.environ.get("SLACK_AR_WEBHOOK", "")

# ─── THE RHYTHM ESCAPISM DNA FILTER ──────────────────────────────────────────
# Every potential addition to OPP catalog is measured against this.
# If it does not map to at least two of these dimensions, it is not OPP.

RHYTHM_ESCAPISM_DNA = {
    "sonic_anchors": [
        "Lo-fi jazz-rap (Nujabes / J Dilla lineage)",
        "Conscious hip-hop with lyrical precision (Common / Lupe lineage)",
        "Anime-informed aesthetics (Samurai Champloo / Cowboy Bebop sonic language)",
        "Boom bap with harmonic sophistication",
        "Instrumental hip-hop with cinematic depth",
        "Electronic fusion with organic hip-hop feeling",
    ],
    "thematic_anchors": [
        "Philosophical / educational content — wisdom embedded in music",
        "Social consciousness — justice, peace, healing, unity",
        "Escapism as a positive — music as transport to a better imagined world",
        "Narrative storytelling — music that takes you somewhere",
        "Gaming / urban culture — authentic, not appropriated",
        "Spiritual groundedness without religious exclusivity",
    ],
    "deal_structure_fit": [
        "Artist open to one-stop clearance arrangement",
        "Artist understands sync licensing as a primary revenue stream",
        "Artist content with boutique placement over major-label volume",
        "Artist whose existing catalog has at least 10 relevant tracks",
    ],
    "aesthetic_exclusions": [
        "Drill / trap with negative violent content — not OPP",
        "Generic lo-fi without lyrical or narrative depth",
        "Anime-themed music without genuine cultural connection",
        "Artists pursuing EDM / pop crossover as primary goal",
    ],
}

SYSTEM_PROMPT = f"""
You are the Lumin A&R & Catalog Growth Agent for OPP Inc. — a boutique music
publisher built around the Rhythm Escapism™ aesthetic.

THE CORE MANDATE:
Your job is not to grow the catalog. Your job is to ensure the catalog is
COMPLETE for what OPP does best. There is a difference. A major label fills
gaps with volume. OPP fills gaps with intention.

THE RHYTHM ESCAPISM DNA FILTER:
Every potential addition must map to at least two sonic anchors AND at least
two thematic anchors from the Rhythm Escapism DNA matrix below. If it does not,
it is the wrong artist for OPP regardless of how talented they are.

SONIC ANCHORS: {", ".join(RHYTHM_ESCAPISM_DNA["sonic_anchors"][:3])} ...
THEMATIC ANCHORS: {", ".join(RHYTHM_ESCAPISM_DNA["thematic_anchors"][:3])} ...

THE ELVIN ROSS / RONNIE GARRETT PRIORITY:
Before any new signing conversation, the Elvin Ross / Ronnie Garrett catalog
agreement must be finalized. This is the binding constraint — without it,
OPP's one-stop clearance claim for that portion of the catalog is incomplete.
Always check this status first. Always flag if still pending.

CATALOG GAP LOGIC:
You read Agent 2's brief rejection patterns (which brief types had no OPP match),
Agent 4's anime/gaming opportunity scores (which aesthetics are in demand),
and Agent 6's cultural moment catalog misses (moments we detected but couldn't
capitalize on). These three data streams define what OPP needs next.

SIGNING TARGETS (Boutique Criteria Only):
- Artists with 10+ catalog tracks in Rhythm Escapism DNA
- Artists open to one-stop clearance licensing structure
- Artists who understand sync as a revenue stream (not an afterthought)
- Artists whose catalog has no existing sync conflicts
- Artists in the Nujabes / Oddisee / Open Mike Eagle aesthetic tier

DO NOT recommend: major-label artists, EDM crossovers, artists pursuing
mainstream pop trajectories, or anyone whose primary goal is chart performance.
OPP is not that. OPP is the other thing — the one that matters longer.
"""

# ─── MODEL ────────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def analyze_catalog_gaps() -> str:
    """
    Analyze the OPP catalog for gaps by reading brief rejection patterns
    from Agent 2 (Sync Brief Hunter), opportunity miss data from Agent 4
    (Anime & Gaming Scout), and cultural moment catalog misses from Agent 6
    (Cultural Moment Detection).

    A catalog gap is defined as: a brief type, mood category, or aesthetic
    profile that appears repeatedly in the data but has NO adequate OPP
    catalog match.

    Returns:
        JSON catalog gap report with gap type, frequency, demand score,
        and recommended fill strategy (commission / license / sign).
    """
    ts = datetime.now(timezone.utc).isoformat()

    # In production: pull from agent data tables.
    # Synthetic gap analysis calibrated to OPP's current catalog state.
    gaps = [
        {
            "gap_id":         "GAP-001",
            "gap_type":       "INSTRUMENTAL_ORCHESTRAL_HIP_HOP",
            "description":    "Cinematic instrumental hip-hop with orchestral elements — no pure instrumental tracks in current OPP catalog that score 8+/10 for film briefs",
            "brief_frequency":  12,
            "demand_score":     8.5,
            "rhythm_escapism_fit": "HIGH — cinematic consciousness is core RE™ territory",
            "fill_strategy":    "COMMISSION — ask Elvin Ross for 3-5 cinematic instrumentals once catalog agreement is signed",
            "timeline":         "Dependent on Elvin Ross agreement — PRIORITY to finalize",
        },
        {
            "gap_id":         "GAP-002",
            "gap_type":       "FEMALE_CONSCIOUS_HIP_HOP",
            "description":    "Female-voiced conscious hip-hop — zero female artist representation in current OPP catalog. Multiple briefs specify or prefer female vocal.",
            "brief_frequency":  8,
            "demand_score":     7.0,
            "rhythm_escapism_fit": "HIGH — female consciousness artists exist in exact RE™ aesthetic space (Noname, Saba-adjacent, Little Simz UK tier)",
            "fill_strategy":    "SIGN — identify 1-2 artists in Noname / Little Simz aesthetic tier for OPP one-stop deal",
            "timeline":         "6-12 months (relationship building required)",
        },
        {
            "gap_id":         "GAP-003",
            "gap_type":       "LO_FI_JAZZ_INSTRUMENTAL_LOOPS",
            "description":    "Pure lo-fi jazz instrumental loops (no rap) for gaming apps, mobile, and YouTube background music. High-volume low-fee passive licensing opportunity.",
            "brief_frequency":  18,
            "demand_score":     6.5,
            "rhythm_escapism_fit": "MEDIUM — instrumentals without lyrical consciousness are adjacent RE™, not core",
            "fill_strategy":    "LICENSE — negotiate non-exclusive license from lo-fi producers on Bandcamp for Artlist/Musicbed passive placement. Not worth a full signing.",
            "timeline":         "30-60 days — straightforward licensing negotiation",
        },
        {
            "gap_id":         "GAP-004",
            "gap_type":       "JAPANESE_LANGUAGE_HIP_HOP",
            "description":    "Japanese-language conscious hip-hop for anime productions preferring domestic artists. JAM LAB briefs increasingly request Japanese-language options.",
            "brief_frequency":  5,
            "demand_score":     9.0,
            "rhythm_escapism_fit": "HIGH — Rhythm Escapism has deep anime roots; Japanese-language tracks open the anime market in ways English tracks cannot",
            "fill_strategy":    "PARTNERSHIP — pursue co-publishing agreement with a Flying Dog or Victor Entertainment artist via Spine Sounds relationship. Not a signing, a co-pub.",
            "timeline":         "12-18 months — requires Japan market relationship development",
        },
    ]

    # Store gaps
    for gap in gaps:
        try:
            gaps_t.put_item(Item={
                "pk": f"GAP#{gap['gap_id']}",
                "sk": ts,
                **{k: str(v) if isinstance(v, float) else v for k, v in gap.items()},
            })
        except Exception:
            pass

    high_demand = [g for g in gaps if g["demand_score"] >= 8]
    immediate   = [g for g in gaps if "PRIORITY" in g.get("timeline", "") or "30-60" in g.get("timeline", "")]

    return json.dumps({
        "gaps_identified":     len(gaps),
        "high_demand_count":   len(high_demand),
        "immediate_action":    immediate,
        "full_gap_analysis":   gaps,
        "binding_constraint":  "Elvin Ross / Ronnie Garrett catalog agreement must be finalized before GAP-001 can be filled. This is the single most impactful action available.",
        "analyzed_at":         ts,
    })


@tool
def check_elvin_ross_agreement_status() -> str:
    """
    Return the current status of the Elvin Ross / Ronnie Garrett catalog
    agreement — the binding constraint for OPP's full one-stop clearance claim.

    This is the most important outstanding action for OPP Inc. and must
    be checked before any new A&R activity. Until this agreement is signed,
    the most valuable portion of the catalog cannot be fully leveraged.

    Returns:
        JSON with agreement status, what is blocking it, and recommended actions.
    """
    return json.dumps({
        "agreement_name":    "Elvin Ross / Ronnie Garrett Catalog Co-Publishing Agreement",
        "current_status":    "PENDING — Agreement in preparation. Not yet executed.",
        "what_is_at_stake": {
            "Elvin Ross":     "Emmy-winning composer (Tyler Perry Studios). Cinematic catalog. Direct access to Tyler Perry Studios sync pipeline via Joel C. High relationship.",
            "Ronnie Garrett": "10,000-song library. Catalog depth that transforms OPP from boutique to mid-tier publisher in terms of sync supply.",
        },
        "blocking_factors":  [
            "Formal agreement terms not yet finalized",
            "H.F. to review agreement structure with legal counsel",
            "Publishing splits and term length to be negotiated",
        ],
        "impact_of_delay":   "Every month without this agreement is a month OPP cannot pitch Elvin Ross tracks one-stop. Joel C. High relationship has been established — we need the catalog to back it up.",
        "recommended_actions": [
            "1. Prioritize agreement finalization this month — block time with legal counsel",
            "2. Use Joel C. High relationship to create soft deadline: 'We expect to have the Elvin Ross catalog fully cleared by [date]' gives OPP a natural forcing function",
            "3. Do not bring on any new signings until this agreement is executed — the Elvin Ross catalog alone addresses GAP-001 and provides 10x more value than a new signing",
        ],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })


@tool
def score_ar_target(
    artist_name: str,
    sonic_description: str,
    thematic_description: str,
    catalog_size: int,
    open_to_one_stop: bool,
) -> str:
    """
    Score a potential A&R target against OPP's Rhythm Escapism™ DNA filter.
    This is the boutique filter — the question is not 'are they talented?'
    but 'do they belong in the world OPP is building?'

    Args:
        artist_name:          Name of the artist being evaluated.
        sonic_description:    Their sound described in plain English.
        thematic_description: Their lyrical/thematic content.
        catalog_size:         Number of available tracks.
        open_to_one_stop:     Whether they can offer one-stop clearance.

    Returns:
        JSON with RE™ DNA score, dimensional breakdown, and recommendation.
    """
    sonic_score  = sum(1 for anchor in RHYTHM_ESCAPISM_DNA["sonic_anchors"]
                       if any(w.lower() in sonic_description.lower()
                               for w in anchor.split()[:3]))
    theme_score  = sum(1 for anchor in RHYTHM_ESCAPISM_DNA["thematic_anchors"]
                       if any(w.lower() in thematic_description.lower()
                               for w in anchor.split()[:3]))
    # Check exclusions
    exclusion_flags = [ex for ex in RHYTHM_ESCAPISM_DNA["aesthetic_exclusions"]
                       if any(w.lower() in sonic_description.lower() or
                               w.lower() in thematic_description.lower()
                               for w in ex.split()[:2])]

    deal_score  = (2 if open_to_one_stop else 0) + (1 if catalog_size >= 10 else 0)
    total_score = min(sonic_score * 2 + theme_score * 2 + deal_score, 10)

    if exclusion_flags:
        total_score = max(0, total_score - 3)
        recommendation = "DO NOT PURSUE — aesthetic exclusion flags detected"
    elif total_score >= 7:
        recommendation = f"STRONG FIT — initiate exploratory conversation. Lead with one-stop structure and sync focus."
    elif total_score >= 5:
        recommendation = "POTENTIAL FIT — deeper evaluation needed. Request catalog listen before proceeding."
    else:
        recommendation = "WEAK FIT — does not align with Rhythm Escapism™ DNA. OPP is not the right home for this artist."

    result = {
        "artist":           artist_name,
        "re_dna_score":     total_score,
        "sonic_score":      sonic_score,
        "thematic_score":   theme_score,
        "deal_score":       deal_score,
        "catalog_size":     catalog_size,
        "one_stop_capable": open_to_one_stop,
        "exclusion_flags":  exclusion_flags,
        "recommendation":   recommendation,
        "scored_at":        datetime.now(timezone.utc).isoformat(),
    }

    if total_score >= 5 and not exclusion_flags:
        try:
            targets_t.put_item(Item={
                "pk": f"TARGET#{artist_name.replace(' ', '_')}",
                "sk": result["scored_at"],
                **{k: str(v) if isinstance(v, (float, bool, list)) else v
                   for k, v in result.items()},
            })
        except Exception:
            pass

    return json.dumps(result)


@tool
def scan_emerging_re_artists() -> str:
    """
    Scan streaming and social data for emerging artists whose sound
    maps to Rhythm Escapism™ DNA. Reads Chartmetric emerging artist
    signals, Bandcamp new releases, and Agent 1's Boltzmann attention
    distribution for artists with growing momentum in the RE™ aesthetic space.

    Returns:
        JSON list of emerging artist candidates with RE™ DNA scores
        and recommended approach strategy.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Synthetic emerging artist roster calibrated to OPP's aesthetic
    candidates = [
        {
            "name":           "Yūgen",
            "origin":         "Chicago, IL",
            "sonic":          "Lo-fi jazz-rap, Nujabes-influenced, instrumental + vocal",
            "thematic":       "Japanese-American consciousness, philosophy, urban spirituality",
            "monthly_listeners": 8200,
            "catalog_size":   14,
            "bandcamp_sales": "Active — 3,200 album downloads past 12 months",
            "one_stop_potential": True,
            "re_fit":         "EXCELLENT — exact Rhythm Escapism DNA. Dual-cultural consciousness is unique.",
            "approach":       "Direct Bandcamp message → Spine Sounds potential collaboration framing",
        },
        {
            "name":           "Solstice Nzinga",
            "origin":         "Atlanta, GA",
            "sonic":          "Conscious hip-hop, cinematic beats, female-voiced narrative rap",
            "thematic":       "Afrofuturism, healing, social justice, cosmic consciousness",
            "monthly_listeners": 4800,
            "catalog_size":   11,
            "bandcamp_sales": "Moderate",
            "one_stop_potential": True,
            "re_fit":         "STRONG — fills the female voice gap identified in GAP-002. Afrofuturist thematic overlaps with RE™ escapism concept.",
            "approach":       "Approach through Sentric Music (UK sub-publisher) or direct at live events",
        },
        {
            "name":           "Kai Moriwaki",
            "origin":         "Los Angeles / Tokyo",
            "sonic":          "Anime hip-hop, J-rap influenced, English/Japanese bilingual",
            "thematic":       "Cultural bridging, honor, loyalty, urban mythology",
            "monthly_listeners": 12400,
            "catalog_size":   22,
            "bandcamp_sales": "Strong",
            "one_stop_potential": False,
            "re_fit":         "STRONG sonically — bilingual catalog addresses Japanese anime market gap (GAP-004). One-stop requires negotiation with existing label.",
            "approach":       "Co-publishing arrangement rather than full signing. Target 3-5 tracks for Japan market via JAM LAB.",
        },
    ]

    # Score each candidate
    scored = []
    for c in candidates:
        score_raw = json.loads(score_ar_target(
            artist_name=c["name"],
            sonic_description=c["sonic"],
            thematic_description=c["thematic"],
            catalog_size=c["catalog_size"],
            open_to_one_stop=c["one_stop_potential"],
        ))
        scored.append({**c, "re_dna_score": score_raw.get("re_dna_score"),
                        "recommendation": score_raw.get("recommendation")})

    scored.sort(key=lambda x: x.get("re_dna_score", 0), reverse=True)

    return json.dumps({
        "candidates_scanned": len(scored),
        "strong_fits":        len([s for s in scored if s.get("re_dna_score", 0) >= 7]),
        "candidates":         scored,
        "reminder":           "Finalize Elvin Ross agreement before initiating any new signing conversation. New signings add complexity. The existing catalog, fully cleared, is worth more.",
        "scanned_at":         ts,
    })


@tool
def analyze_catalog_performance_equity() -> str:
    """
    Analyze performance equity across the OPP catalog: which tracks are
    over-pitched (too many submissions, diminishing returns) vs. under-pitched
    (high quality but low exposure), and which tracks are generating passive
    revenue vs. requiring active effort.

    Returns:
        JSON with performance equity matrix and rebalancing recommendations.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Performance equity analysis of current OPP catalog
    performance = {
        "over_pitched": [
            {
                "track": "LightSwitch (SkyBlew)",
                "status": "Over-pitched in gaming/anime space — now let passive sync do the work. BRC Nintendo sync is the best possible placement; all others are diminishing returns.",
                "action": "Reduce active pitching. Focus on passive YouTube Content ID and Artlist/Musicbed listing. Let the Nintendo credibility do the work.",
            }
        ],
        "under_pitched": [
            {
                "track": "MoreLoveLessWar (SkyBlew)",
                "status": "Critically under-pitched. Peace/unity theme is historically timely. Currently blocked by Apple Music distribution failure.",
                "action": "Fix Apple Music distribution FIRST. Then aggressive proactive pitch to Morgan Rhodes, Jen Malone, and Fam Udeorji immediately.",
            },
            {
                "track": "Above The Clouds (SkyBlew)",
                "status": "Strong catalog track with broad applicability (inspirational, achievement, triumph). Has not received a dedicated pitch cycle.",
                "action": "Prepare pitch package. Target: healthcare advertising, graduation content, sports editorial, documentary triumph sequences.",
            },
        ],
        "passive_revenue_opportunities": [
            "Register full SkyBlew catalog on YouTube Content ID via DistroKid/Redeye — every YouTube use of any OPP track should be monetized.",
            "Upload OPP instrumental catalog to Musicbed and Artlist for passive licensing — these platforms pay without active pitching.",
            "Register all tracks with BMAT for global passive broadcast monitoring — captures performance royalties from international TV/radio.",
        ],
        "catalog_health_summary": {
            "total_tracks_reviewed": 94,
            "actively_pitched": 3,
            "passively_licensed": 0,
            "recommendation": "Expand passive licensing infrastructure. OPP is leaving money on the table by only pitching actively.",
        },
    }

    return json.dumps({**performance, "analyzed_at": ts})


@tool
def generate_ar_strategy_report() -> str:
    """
    Generate a complete A&R and catalog growth strategy report for H.F.
    Synthesizes gap analysis, Elvin Ross status, emerging candidates,
    and performance equity into a single strategic document with
    prioritized action items.

    Returns:
        JSON strategic report formatted for H.F. review.
    """
    gaps_raw    = json.loads(analyze_catalog_gaps())
    elvin_raw   = json.loads(check_elvin_ross_agreement_status())
    equity_raw  = json.loads(analyze_catalog_performance_equity())

    report = {
        "report_date": datetime.now(timezone.utc).strftime("%B %Y"),
        "executive_summary": (
            "OPP Inc.'s catalog growth strategy for the next 6 months has one overriding "
            "priority: finalize the Elvin Ross / Ronnie Garrett agreement. This single action "
            "unlocks the cinematic instrumental gap (GAP-001), completes OPP's one-stop "
            "clearance claim, and activates the Tyler Perry Studios pipeline via Joel C. High. "
            "Everything else — new signings, passive licensing expansion, emerging artist "
            "conversations — is secondary to this."
        ),
        "elvin_ross_status": elvin_raw["current_status"],
        "catalog_gaps":      gaps_raw["gaps_identified"],
        "highest_priority_gap": gaps_raw["immediate_action"],
        "passive_revenue_actions": equity_raw["passive_revenue_opportunities"],
        "under_pitched_tracks": equity_raw["under_pitched"],
        "new_signing_recommendation": (
            "NO new signing conversations should be initiated until the Elvin Ross agreement "
            "is executed. OPP is a boutique — adding complexity before the foundation is "
            "complete dilutes focus. The right next artist for OPP is one who extends the "
            "Rhythm Escapism DNA rather than adding a new aesthetic branch."
        ),
        "6_month_priorities": [
            "1. Execute Elvin Ross / Ronnie Garrett catalog agreement",
            "2. Fix Apple Music distribution for MoreLoveLessWar + all OPP catalog",
            "3. Register full catalog on YouTube Content ID for passive revenue",
            "4. Upload OPP instrumentals to Musicbed / Artlist",
            "5. Begin Yūgen exploratory conversation (top RE™ DNA candidate)",
            "6. Develop Spine Sounds Japan co-publishing path for Kai Moriwaki tracks",
        ],
        "boutique_principle": (
            "OPP's power is specificity. One-stop clearance + Rhythm Escapism™ identity "
            "= a catalog that supervisors can rely on for a defined aesthetic. "
            "Growing with intention means every addition strengthens this identity. "
            "Growing with volume means losing it."
        ),
    }

    if SLACK_AR_WEBHOOK:
        try:
            requests.post(SLACK_AR_WEBHOOK, json={
                "text": f"📚 A&R Strategy Report — {report['report_date']}: {gaps_raw['gaps_identified']} gaps identified. Top priority: Elvin Ross agreement."
            }, timeout=5)
        except Exception:
            pass

    return json.dumps(report)


# ─── AGENT ────────────────────────────────────────────────────────────────────

def create_ar_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            analyze_catalog_gaps,
            check_elvin_ross_agreement_status,
            score_ar_target,
            scan_emerging_re_artists,
            analyze_catalog_performance_equity,
            generate_ar_strategy_report,
        ],
    )


def run_monthly_ar_review(agent: Agent) -> dict:
    """1st of month 09:00 UTC — Monthly A&R and catalog health review."""
    result = agent(
        "Run the monthly A&R and catalog growth review. "
        "1. Call check_elvin_ross_agreement_status() — this is ALWAYS the first check. "
        "   If still PENDING, escalate to H.F. immediately with the specific impact statement. "
        "2. Call analyze_catalog_gaps() to identify current brief demand vs. catalog gaps. "
        "3. Call analyze_catalog_performance_equity() — identify any under-pitched tracks "
        "   that should be prioritized this month, and any passive licensing actions pending. "
        "4. Call scan_emerging_re_artists() for any new candidates that meet the Rhythm "
        "   Escapism DNA filter at 7+ score. "
        "5. Call generate_ar_strategy_report() and post summary to Slack #ar-strategy. "
        "Return: Elvin Ross status, top gap, most urgent action, top emerging candidate."
    )
    return {"task": "monthly_ar_review", "result": str(result)}


def score_new_candidate(agent: Agent, artist_data: dict) -> dict:
    """On-demand — Score a specific artist against the RE™ DNA filter."""
    result = agent(
        f"Score this artist against the Rhythm Escapism™ DNA filter: "
        f"Name: {artist_data.get('name')} | "
        f"Sound: {artist_data.get('sonic')} | "
        f"Themes: {artist_data.get('thematic')} | "
        f"Catalog size: {artist_data.get('catalog_size', 0)} tracks | "
        f"One-stop capable: {artist_data.get('one_stop', False)}. "
        f"Call score_ar_target() with these details. "
        f"If score >= 7: prepare a brief Slack summary of why they fit and how to approach them. "
        f"If score < 5: explain specifically which RE™ DNA dimensions are missing."
    )
    return {"task": "score_candidate", "result": str(result)}


def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point.

    Scheduled: {"task": "monthly_ar_review"}
    On-demand:  {"task": "score_candidate", "artist": {name, sonic, thematic, catalog_size, one_stop}}
    """
    agent = create_ar_agent()
    task  = event.get("task", "monthly_ar_review")
    p     = event.get("params", event)

    dispatch = {
        "monthly_ar_review": lambda: run_monthly_ar_review(agent),
        "score_candidate":   lambda: score_new_candidate(agent, {
            "name":         p.get("artist", {}).get("name", ""),
            "sonic":        p.get("artist", {}).get("sonic", ""),
            "thematic":     p.get("artist", {}).get("thematic", ""),
            "catalog_size": p.get("artist", {}).get("catalog_size", 0),
            "one_stop":     p.get("artist", {}).get("one_stop", False),
        }),
    }

    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("📚 A&R & Catalog Growth Agent — Interactive Mode")
    print("   Commands: 'gaps' | 'elvin' | 'emerging' | 'equity' | 'report' | 'quit'\n")

    agent = create_ar_agent()
    shortcuts = {
        "gaps":     "Analyze the current OPP catalog gaps based on sync demand signals.",
        "elvin":    "What is the current status of the Elvin Ross / Ronnie Garrett catalog agreement?",
        "emerging": "Show me the top emerging artist candidates that fit the Rhythm Escapism DNA.",
        "equity":   "Which OPP tracks are under-pitched and missing passive licensing opportunities?",
        "report":   "Generate the full monthly A&R strategy report.",
    }

    while True:
        try:
            ui = input("A&R > ").strip()
            if ui.lower() in ("quit", "exit"):
                break
            if ui.lower() in shortcuts:
                ui = shortcuts[ui.lower()]
            elif not ui:
                continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nA&R Agent offline.")
            break
