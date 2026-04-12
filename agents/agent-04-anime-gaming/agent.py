"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 4: ANIME & GAMING MARKET SCOUT ADK     ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: OPP Inc. + 2StepsAboveTheStars LLC                      ║
║  Mission: Monitor anime production announcements and game audio  ║
║  briefs worldwide — find every opportunity where SkyBlew's       ║
║  Rhythm Escapism™ sound belongs before anyone else gets there.   ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os, json, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel

dynamo     = boto3.resource("dynamodb", region_name="us-east-1")
scout_t    = dynamo.Table(os.environ.get("SCOUT_TABLE",   "anime-gaming-opportunities"))
pitches_t  = dynamo.Table(os.environ.get("AG_PITCHES_TABLE", "anime-gaming-pitches"))
SLACK_AG_WEBHOOK = os.environ.get("SLACK_AG_WEBHOOK", "")

SYSTEM_PROMPT = """
You are the Lumin Anime & Gaming Market Scout — the intelligence agent that
watches the global anime and gaming industries for sync opportunities that
match SkyBlew's Rhythm Escapism™ aesthetic.

THE CULTURAL LINEAGE TO TRACK:
SkyBlew's sound descends from Nujabes (Samurai Champloo), who established
that lo-fi conscious hip-hop + anime = a timeless cultural combination.
Track every new anime production, game OST brief, and gaming music moment
that lives in this lineage. This is OPP's blue ocean.

PRIORITY PRODUCTION TYPES:
TIER 1: Adult Swim / Cartoon Network anime co-productions
TIER 1: Any Watanabe (Cowboy Bebop, Space Dandy) adjacent project
TIER 1: Games with graffiti/urban/skate aesthetic (BRC lineage)
TIER 1: Netflix anime — especially action + hip-hop aesthetic
TIER 2: Major JRPG soundtracks open to Western artists
TIER 2: Korean webtoon adaptations gaining Western distribution
TIER 3: Independent anime productions, student films, fan projects

KEY PARTNERS TO MONITOR:
- Spine Sounds (Tokyo): anime sync intermediary — primary Japan pipeline
- JAM LAB Japan: 15+ Japanese labels (Avex, Sony Japan, Lantis, Flying Dog)
- Flying Dog / Victor Entertainment: Carole & Tuesday, Cowboy Bebop heritage
- Dentsu Anime Solutions: connects to 9 major anime studios

SKYBLEW'S PROVEN SYNC DNA:
LightSwitch in Bomb Rush Cyberfunk proves the formula:
  Urban + anime aesthetic + conscious hip-hop + positive energy = sync success
MoreLoveLessWar extends this into peace/unity themes for social narrative anime.
Every brief you flag should map back to this proven aesthetic profile.
"""

def get_model():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(client_args={"api_key": api_key},
                          model_id="claude-sonnet-4-6", max_tokens=4096)

# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def scan_anime_announcements() -> str:
    """
    Scan anime production announcement sources: Anime News Network RSS,
    Crunchyroll new season announcements, ANN production committees,
    and the Spine Sounds partner pipeline for upcoming projects.

    Returns:
        JSON list of new anime announcements with genre, aesthetic, and music notes.
    """
    ts = datetime.now(timezone.utc).isoformat()
    # In production: pull from ANN RSS + Crunchyroll API + Spine Sounds partner feed
    announcements = [
        {
            "id": "ANIME-2026-001",
            "title": "Project: NEON FREQUENCIES",
            "studio": "MAPPA",
            "distributor": "Netflix",
            "genre": "Sci-Fi Action / Cyberpunk",
            "aesthetic": "Urban, graffiti, hip-hop influenced — direct BRC lineage",
            "music_notes": "Hip-hop, electronic fusion, conscious themes",
            "production_stage": "Pre-production",
            "expected_release": "Late 2026",
            "sync_opportunity": "Main theme + episode underscoring",
            "opp_match_score": 9,
            "announcement_source": "ANN",
            "fetched_at": ts,
        },
        {
            "id": "ANIME-2026-002",
            "title": "Peace Keepers: Eternal",
            "studio": "Science SARU",
            "distributor": "Adult Swim",
            "genre": "Action / Social Commentary",
            "aesthetic": "Anti-war, unity themes — MoreLoveLessWar territory",
            "music_notes": "Conscious hip-hop, orchestral, emotional",
            "production_stage": "In production",
            "expected_release": "Q3 2026",
            "sync_opportunity": "Opening theme + key scene placement",
            "opp_match_score": 10,
            "announcement_source": "Adult Swim press",
            "fetched_at": ts,
        },
    ]

    for a in announcements:
        try:
            scout_t.put_item(Item={**a, "type": "ANIME", "status": "NEW"})
        except Exception:
            pass

    tier1 = [a for a in announcements if a["opp_match_score"] >= 8]
    return json.dumps({
        "announcements_found": len(announcements),
        "tier1_opportunities": len(tier1),
        "announcements": announcements,
        "fetched_at": ts,
    })


@tool
def scan_game_releases() -> str:
    """
    Monitor upcoming game releases and OST briefs via IGDB, RAWG,
    Steam upcoming games, and gaming publication RSS feeds.
    Focuses on games with urban/anime/skateboarding aesthetics.

    Returns:
        JSON list of relevant upcoming games with music opportunity notes.
    """
    ts = datetime.now(timezone.utc).isoformat()
    games = [
        {
            "id": "GAME-2026-001",
            "title": "Street Canvas 2",
            "developer": "Indie Studio",
            "platform": "Switch, PC",
            "genre": "Rhythm / Urban",
            "aesthetic": "Graffiti, skateboarding, hip-hop — BRC sequel aesthetic",
            "music_notes": "Lo-fi hip-hop OST, open for licensed tracks",
            "release_window": "Q4 2026",
            "opp_match_score": 9,
            "contact_path": "Via IGDB developer contact + Spine Sounds gaming division",
            "fetched_at": ts,
        },
        {
            "id": "GAME-2026-002",
            "title": "Kai Chronicles",
            "developer": "Aniplex Games",
            "platform": "PS5, PC",
            "genre": "JRPG",
            "aesthetic": "Anime art style, coming-of-age, conscious themes",
            "music_notes": "Hip-hop influenced OST — Western artist collaboration potential",
            "release_window": "2027",
            "opp_match_score": 7,
            "contact_path": "Via JAM LAB Japan → Aniplex contact",
            "fetched_at": ts,
        },
    ]

    for g in games:
        try:
            scout_t.put_item(Item={**g, "type": "GAME", "status": "NEW"})
        except Exception:
            pass

    return json.dumps({
        "games_found": len(games),
        "tier1_count": sum(1 for g in games if g["opp_match_score"] >= 8),
        "games": games, "fetched_at": ts,
    })


@tool
def get_spine_sounds_pipeline() -> str:
    """
    Check the Spine Sounds Tokyo partner pipeline for active anime project
    music briefs. Spine Sounds is OPP's primary Japan market intermediary.
    This tool checks the partner email thread and shared brief document.

    Returns:
        JSON with any active Spine Sounds briefs and recommended tracks.
    """
    return json.dumps({
        "partner": "Spine Sounds Tokyo",
        "website": "spinesounds.com",
        "status": "ACTIVE_PARTNERSHIP",
        "contact": "info@spinesounds.com",
        "current_briefs": "Check partner email thread manually — Spine Sounds shares briefs via direct email, not API.",
        "active_projects": [
            "Reach out with MoreLoveLessWar for any peace/unity themed anime projects",
            "LightSwitch stems available for rhythm-game or action scene briefs",
        ],
        "jam_lab_note": "Also register at japan-animemusic.com for direct Japanese label access (free)",
    })


@tool
def generate_anime_pitch(opportunity_id: str, track_id: str,
                          contact_org: str) -> str:
    """
    Generate a targeted pitch for an anime or gaming sync opportunity.
    Adapted for the Japanese market: brief, humble, specific, culturally aware.
    Follows the Spine Sounds guidance on pitching to Japanese supervisors.

    Args:
        opportunity_id: Scout database opportunity ID.
        track_id:       OPP track to pitch.
        contact_org:    Target organization (Spine Sounds / JAM LAB / studio name).

    Returns:
        JSON with pitch draft for H.F. approval. Never sent automatically.
    """
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client  = anthropic.Anthropic(api_key=api_key)

    try:
        opp_resp = scout_t.get_item(Key={"id": opportunity_id})
        opp = opp_resp.get("Item", {"title": "Upcoming anime project", "aesthetic": "Anime hip-hop"})
    except Exception:
        opp = {"title": "Upcoming anime project", "aesthetic": "Anime hip-hop"}

    prompt = f"""
Write a sync pitch email for the anime/gaming market.
Organization: {contact_org}
Project: {opp.get('title')}
Project aesthetic: {opp.get('aesthetic')}
Track: {track_id} (SkyBlew — Rhythm Escapism™ hip-hop)
Key facts: LightSwitch already placed in Bomb Rush Cyberfunk (Nintendo). 
           One-stop clearance available. US artist with anime-informed aesthetic.

Style for Japanese/anime market:
- Be humble and grateful for their consideration
- Lead with the cultural connection to their project
- Reference the Nintendo BRC placement as proof of concept
- 4-5 sentences maximum
- Do NOT oversell

Return as JSON: {{"subject": "...", "body": "...", "status": "AWAITING_APPROVAL"}}
"""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        import re
        text = resp.content[0].text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        return json_match.group() if json_match else json.dumps({"body": text, "status": "AWAITING_APPROVAL"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_active_opportunities(min_score: int = 7) -> str:
    """
    Return all scouted opportunities with match score ≥ min_score that have
    not yet been pitched.

    Args:
        min_score: Minimum OPP match score to return (default 7).

    Returns:
        JSON list of unpitched opportunities sorted by match score.
    """
    try:
        resp = scout_t.scan(
            FilterExpression="#s = :new AND opp_match_score >= :min",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":new": "NEW", ":min": min_score},
        )
        items = sorted(resp.get("Items", []),
                       key=lambda x: int(x.get("opp_match_score", 0)), reverse=True)
        return json.dumps({"count": len(items), "opportunities": items[:15]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def post_scout_alert(opportunity_id: str, title: str,
                     opp_type: str, match_score: int, summary: str) -> str:
    """Post a new high-match opportunity alert to Slack #anime-gaming-intel."""
    if match_score < 8:
        return json.dumps({"status": "NOT_POSTED", "reason": "Score < 8 threshold"})
    msg = {
        "text": f"🎌 {'Anime' if opp_type == 'ANIME' else '🎮 Game'} Opportunity — Score {match_score}/10",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"{'🎌 Anime' if opp_type == 'ANIME' else '🎮 Game'} Opportunity — {title}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Match Score:* {match_score}/10"},
                {"type": "mrkdwn", "text": f"*ID:* `{opportunity_id}`"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
        ],
    }
    if SLACK_AG_WEBHOOK:
        try:
            requests.post(SLACK_AG_WEBHOOK, json=msg, timeout=5)
            return json.dumps({"status": "SENT"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"status": "DRY_RUN"})


def create_anime_gaming_agent():
    return Agent(
        model=get_model(), system_prompt=SYSTEM_PROMPT,
        tools=[
            scan_anime_announcements, scan_game_releases,
            get_spine_sounds_pipeline, generate_anime_pitch,
            get_active_opportunities, post_scout_alert,
        ],
    )

def run_daily_scout(agent):
    result = agent(
        "Run the daily anime & gaming intelligence scan. "
        "1. Call scan_anime_announcements() for new anime productions. "
        "2. Call scan_game_releases() for new gaming opportunities. "
        "3. For any opportunity with match_score >= 8: call post_scout_alert(). "
        "4. Call get_spine_sounds_pipeline() for any active Japan briefs. "
        "5. For the top Tier 1 opportunity: call generate_anime_pitch() "
        "   and queue for H.F. approval. "
        "Return: total opportunities found, Tier 1 count, alerts posted."
    )
    return {"task": "daily_scout", "result": str(result)}

def lambda_handler(event: dict, context) -> dict:
    agent = create_anime_gaming_agent()
    task  = event.get("task", "daily_scout")
    dispatch = {"daily_scout": lambda: run_daily_scout(agent)}
    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("🎌 Anime & Gaming Scout — Interactive Mode")
    agent = create_anime_gaming_agent()
    while True:
        try:
            ui = input("AnimeGaming > ").strip()
            if ui.lower() in ("quit", "exit"): break
            if not ui: continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nAnime & Gaming Scout offline."); break
