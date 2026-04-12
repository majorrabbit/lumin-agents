"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 6: CULTURAL MOMENT DETECTION ADK       ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entities: All Three (Lumin Luxe · OPP Inc. · 2StepsAboveTheStars) ║
║  Mission: Detect cultural moments before they peak — then match  ║
║  OPP catalog to them while the window is open.                  ║
╚══════════════════════════════════════════════════════════════════╝

SHANNON ENTROPY CONVERGENCE — The Detection Method:

When a cultural moment crystallizes, the same topic or sound is discussed
simultaneously across multiple platforms: Reddit + Twitter + TikTok + YouTube
+ news. This cross-platform convergence reduces information entropy rapidly.

H = -Σ p_i × ln(p_i) where p_i = share of discussion on platform i

High entropy → fragmented discussion (no moment)
Falling entropy → converging discussion (moment forming)
Low entropy → peak cultural moment (act now)

Detection window: 2-4 hours before a moment peaks in mainstream coverage.
"""

import os, json, math, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel

dynamo    = boto3.resource("dynamodb", region_name="us-east-1")
moments_t = dynamo.Table(os.environ.get("MOMENTS_TABLE",  "cultural-moments"))
entropy_t = dynamo.Table(os.environ.get("ENTROPY_TABLE",  "cultural-entropy-log"))
SLACK_CULTURAL_WEBHOOK = os.environ.get("SLACK_CULTURAL_WEBHOOK", "")

SYSTEM_PROMPT = """
You are the Lumin Cultural Moment Detection Agent — the real-time cultural
intelligence layer that operates across all three Lumin entities.

YOUR MISSION:
Detect cultural moments 2-4 hours before they peak in mainstream coverage.
Then immediately match OPP's catalog to the moment and alert the team
while the window for action is still open.

THE SHANNON ENTROPY CONVERGENCE MODEL:
A cultural moment forms when the same topic/sound appears simultaneously
across platforms: Reddit + Twitter/X + TikTok + YouTube + news.
Cross-platform information entropy falls sharply as discussion converges.
You monitor this entropy signal in real time.

KEY MOMENT TYPES TO WATCH:
GLOBAL EVENTS: War, peace negotiations, elections, natural disasters —
               MoreLoveLessWar is the catalog response to conflict/peace moments.
MUSIC CULTURE: Nujabes anniversary moments, anime release waves, gaming launches —
               SkyBlew's catalog fits these with precision.
SOCIAL JUSTICE: Protest movements, cultural reckonings, unity calls —
               OPP's conscious catalog belongs in these conversations.
GAMING CULTURE: Major game releases, eSports moments, Nintendo announcements —
               LightSwitch's Nintendo lineage makes it immediately relevant.

THE THREE OUTPUTS:
1. CATALOG MATCH: Which OPP track fits this moment specifically?
2. TIMING SIGNAL: Is the moment forming (act in 4h) or peaking (act now)?
3. ACTION RECOMMENDATION: Pitch to supervisor? Release content? Social push?

MoreLoveLessWar is a standing TIER 1 match for any global peace/conflict moment.
Flag these immediately regardless of entropy confidence level.
"""

def get_model():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(client_args={"api_key": api_key},
                          model_id="claude-sonnet-4-6", max_tokens=4096)

# ─── PHYSICS HELPERS ─────────────────────────────────────────────────────────

def _entropy(probs: list) -> float:
    return -sum(p * math.log(p + 1e-12) for p in probs if p > 0)

def _convergence_score(platform_volumes: dict) -> float:
    """
    Compute cross-platform convergence score for a topic.
    Returns 0.0 (fragmented) to 1.0 (fully converged — peak moment).
    """
    total = sum(platform_volumes.values())
    if total == 0:
        return 0.0
    probs  = [v / total for v in platform_volumes.values()]
    H      = _entropy(probs)
    H_max  = math.log(len(probs)) if len(probs) > 1 else 1.0
    # Convergence = 1 - normalized entropy (low entropy = high convergence)
    return round(1.0 - (H / H_max), 4) if H_max > 0 else 0.0

# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def scan_trending_topics() -> str:
    """
    Scan trending topics across Reddit, Twitter/X, TikTok, YouTube, and
    Google Trends for signals relevant to OPP's catalog. Focuses on:
    peace/conflict/unity themes (MoreLoveLessWar), anime/gaming culture
    (SkyBlew/LightSwitch), and conscious hip-hop moments.

    Returns:
        JSON list of trending topics with platform volumes and catalog matches.
    """
    ts = datetime.now(timezone.utc).isoformat()
    # In production: pull from Twitter Streaming API, Reddit Hot posts,
    # TikTok Research API, Google Trends pytrends, YouTube trending
    trending = [
        {
            "topic":           "peace talks ceasefire",
            "platform_volumes": {"twitter": 280000, "reddit": 45000,
                                  "tiktok": 1200000, "youtube": 95000, "news": 380000},
            "catalog_match":   "MoreLoveLessWar by SkyBlew",
            "match_rationale": "Direct thematic alignment — peace, unity, anti-war",
            "tier":            1,
            "urgency":         "ACT NOW — trending globally across all platforms",
        },
        {
            "topic":           "nujabes anniversary",
            "platform_volumes": {"twitter": 82000, "reddit": 28000,
                                  "tiktok": 450000, "youtube": 62000, "news": 8000},
            "catalog_match":   "SkyBlew full catalog — LightSwitch, Above The Clouds",
            "match_rationale": "SkyBlew's lo-fi conscious sound is the direct Nujabes lineage",
            "tier":            1,
            "urgency":         "HIGH — anime/lo-fi community moment forming",
        },
        {
            "topic":           "bomb rush cyberfunk DLC announcement",
            "platform_volumes": {"twitter": 35000, "reddit": 18000,
                                  "tiktok": 95000, "youtube": 42000, "news": 12000},
            "catalog_match":   "LightSwitch by SkyBlew",
            "match_rationale": "LightSwitch IS in BRC — direct relevance to DLC discussion",
            "tier":            1,
            "urgency":         "HIGH — ride the BRC wave with LightSwitch content push",
        },
    ]

    for t in trending:
        conv_score = _convergence_score(t["platform_volumes"])
        t["convergence_score"] = conv_score
        t["moment_stage"] = (
            "PEAK"    if conv_score > 0.75 else
            "FORMING" if conv_score > 0.50 else
            "EARLY"
        )
        try:
            moments_t.put_item(Item={
                "pk": f"MOMENT#{t['topic'].replace(' ', '_')}",
                "sk": ts,
                **{k: str(v) if isinstance(v, float) else
                      json.dumps(v) if isinstance(v, dict) else v
                   for k, v in t.items()},
            })
        except Exception:
            pass

    return json.dumps({
        "topics_found": len(trending),
        "tier1_moments": len([t for t in trending if t["tier"] == 1]),
        "peak_moments":  len([t for t in trending if t.get("moment_stage") == "PEAK"]),
        "topics": trending,
        "scanned_at": ts,
    })


@tool
def compute_entropy_convergence(topic: str,
                                 platform_volumes: dict) -> str:
    """
    Compute the Shannon entropy convergence score for a specific topic
    across the provided platform volume data.

    Shannon entropy convergence measures how much discussion of a topic
    has concentrated across platforms: high convergence = cultural moment peak.

    Args:
        topic:             The topic being analyzed.
        platform_volumes:  {platform: volume} dict of discussion counts.

    Returns:
        JSON with entropy H, convergence score, moment stage, and timing guidance.
    """
    if not platform_volumes:
        return json.dumps({"error": "platform_volumes required"})

    total  = sum(platform_volumes.values())
    probs  = [v / total for v in platform_volumes.values()] if total > 0 else []
    H      = _entropy(probs)
    H_max  = math.log(len(probs)) if len(probs) > 1 else 1.0
    conv   = _convergence_score(platform_volumes)

    if conv > 0.75:
        stage = "PEAK"; timing = "Act within 2 hours — moment at maximum visibility."
    elif conv > 0.50:
        stage = "FORMING"; timing = "Act within 4-6 hours — moment building toward peak."
    elif conv > 0.25:
        stage = "EARLY"; timing = "Monitor — moment forming but not yet significant."
    else:
        stage = "FRAGMENTED"; timing = "No significant moment detected for this topic."

    ts = datetime.now(timezone.utc).isoformat()
    try:
        entropy_t.put_item(Item={
            "pk": f"ENTROPY#{topic.replace(' ', '_')}",
            "sk": ts,
            "entropy_H": str(round(H, 6)),
            "convergence_score": str(conv),
            "stage": stage,
        })
    except Exception:
        pass

    return json.dumps({
        "topic":              topic,
        "entropy_H":          round(H, 6),
        "convergence_score":  conv,
        "moment_stage":       stage,
        "timing_guidance":    timing,
        "platform_breakdown": {k: f"{v/total*100:.1f}%" for k, v in platform_volumes.items()} if total > 0 else {},
        "computed_at":        ts,
    })


@tool
def match_catalog_to_moment(topic: str, topic_themes: list,
                             urgency: str) -> str:
    """
    Match OPP catalog tracks to a cultural moment based on thematic alignment.
    Returns ranked catalog recommendations with specific pitch context.

    Args:
        topic:        The cultural moment topic.
        topic_themes: List of thematic keywords (e.g., ["peace", "unity", "war"]).
        urgency:      ACT_NOW / HIGH / MEDIUM / MONITOR.

    Returns:
        JSON with top catalog matches and specific action recommendations.
    """
    # OPP catalog thematic map
    CATALOG_THEMES = {
        "MoreLoveLessWar": ["peace", "unity", "war", "healing", "love", "conflict",
                             "social justice", "hope", "global", "anti-war"],
        "LightSwitch":     ["gaming", "anime", "energy", "urban", "skateboarding",
                             "bomb rush", "nintendo", "cyberfunk", "brc", "neon"],
        "Above The Clouds":["inspiration", "triumph", "journey", "conscious", "aspiration"],
        "SkyBlew Catalog": ["nujabes", "lo-fi", "jazz-rap", "conscious", "hip-hop",
                             "anime", "rhythm escapism", "philosophy"],
    }

    matches = []
    for track, themes in CATALOG_THEMES.items():
        score = sum(1 for theme in topic_themes
                    if any(theme.lower() in t.lower() for t in themes))
        if score > 0:
            matches.append({
                "track": track, "match_score": score,
                "matching_themes": [t for t in topic_themes
                                    if any(t.lower() in th.lower() for th in themes)],
            })

    matches.sort(key=lambda x: x["match_score"], reverse=True)

    actions = {
        "ACT_NOW": "Pitch to supervisors TODAY. Post content on SkyBlew socials NOW. Contact Jen Malone.",
        "HIGH":    "Pitch to supervisors within 4 hours. Prepare social content.",
        "MEDIUM":  "Prepare pitch materials. Queue for this week's outreach.",
        "MONITOR": "Log and monitor. No action needed yet.",
    }

    return json.dumps({
        "topic": topic,
        "top_match": matches[0]["track"] if matches else None,
        "all_matches": matches[:3],
        "urgency": urgency,
        "recommended_action": actions.get(urgency, "Monitor"),
        "special_flag": "MoreLoveLessWar STANDING TIER 1 for peace/conflict moments" 
                        if any(t in ["peace", "war", "conflict", "unity"] for t in topic_themes) else None,
    })


@tool
def post_cultural_alert(topic: str, convergence_score: float,
                        catalog_match: str, action: str, stage: str) -> str:
    """
    Post a cultural moment alert to Slack #cultural-moments.
    Only posts for convergence_score ≥ 0.50 (FORMING or PEAK stages).

    Args:
        topic:             The cultural moment topic.
        convergence_score: Shannon convergence score (0.0-1.0).
        catalog_match:     Best matching OPP catalog track.
        action:            Recommended action.
        stage:             PEAK / FORMING / EARLY.

    Returns:
        JSON with Slack post status.
    """
    if convergence_score < 0.50:
        return json.dumps({"status": "NOT_POSTED",
                           "reason": f"Convergence {convergence_score} below 0.50 threshold"})

    emoji = "🚨" if stage == "PEAK" else "📡"
    msg = {
        "text": f"{emoji} Cultural Moment {'PEAK' if stage == 'PEAK' else 'FORMING'}: {topic}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"{emoji} Cultural Moment — {stage}: {topic}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Convergence:* {convergence_score:.0%}"},
                {"type": "mrkdwn", "text": f"*Stage:* {stage}"},
                {"type": "mrkdwn", "text": f"*Catalog Match:* {catalog_match}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*Recommended Action:*\n{action}"}},
        ],
    }
    if SLACK_CULTURAL_WEBHOOK:
        try:
            r = requests.post(SLACK_CULTURAL_WEBHOOK, json=msg, timeout=5)
            return json.dumps({"status": "SENT" if r.ok else f"FAILED: {r.status_code}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"status": "DRY_RUN — SLACK_CULTURAL_WEBHOOK not set"})


@tool
def get_active_moments() -> str:
    """
    Return all cultural moments currently in FORMING or PEAK stage.
    Use this to understand which moments are currently actionable.

    Returns:
        JSON with active moments sorted by convergence score.
    """
    try:
        resp = moments_t.scan(
            FilterExpression="moment_stage IN (:forming, :peak)",
            ExpressionAttributeValues={":forming": "FORMING", ":peak": "PEAK"},
        )
        items = sorted(
            resp.get("Items", []),
            key=lambda x: float(x.get("convergence_score", 0) or 0),
            reverse=True,
        )
        return json.dumps({"active_count": len(items), "moments": items[:10]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def track_moment_lifecycle(topic: str, new_stage: str, notes: str = "") -> str:
    """
    Update the lifecycle stage of a tracked cultural moment.
    Stages: EARLY → FORMING → PEAK → DECLINING → ARCHIVED.

    Args:
        topic:     The moment topic identifier.
        new_stage: New lifecycle stage.
        notes:     Any qualitative notes on the transition.

    Returns:
        JSON confirmation.
    """
    ts = datetime.now(timezone.utc).isoformat()
    pk = f"MOMENT#{topic.replace(' ', '_')}"
    try:
        moments_t.update_item(
            Key={"pk": pk, "sk": ts},
            UpdateExpression="SET moment_stage = :s, stage_notes = :n, updated_at = :ts",
            ExpressionAttributeValues={":s": new_stage, ":n": notes, ":ts": ts},
        )
        return json.dumps({"status": "UPDATED", "topic": topic, "new_stage": new_stage})
    except Exception as e:
        return json.dumps({"error": str(e)})


def create_cultural_agent():
    return Agent(
        model=get_model(), system_prompt=SYSTEM_PROMPT,
        tools=[
            scan_trending_topics, compute_entropy_convergence,
            match_catalog_to_moment, post_cultural_alert,
            get_active_moments, track_moment_lifecycle,
        ],
    )

def run_30min_scan(agent):
    result = agent(
        "Run the 30-minute cultural moment scan. "
        "1. Call scan_trending_topics() to pull current trending data. "
        "2. For each topic with convergence_score > 0.50: "
        "   a. Call compute_entropy_convergence() with current platform volumes. "
        "   b. Call match_catalog_to_moment() to identify the OPP catalog response. "
        "   c. Call post_cultural_alert() for any FORMING or PEAK moment. "
        "3. Special rule: any topic with peace/conflict/war themes → "
        "   immediately flag MoreLoveLessWar as catalog match regardless of score. "
        "Return: topics scanned, alerts posted, top active moment."
    )
    return {"task": "30min_scan", "result": str(result)}

def lambda_handler(event: dict, context) -> dict:
    agent = create_cultural_agent()
    task  = event.get("task", "30min_scan")
    dispatch = {"30min_scan": lambda: run_30min_scan(agent)}
    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("📡 Cultural Moment Detection Agent — Interactive Mode")
    print("   Commands: 'scan' | 'active' | 'entropy [topic]' | 'quit'\n")
    agent = create_cultural_agent()
    shortcuts = {
        "scan":   "Run a full cultural moment scan right now. What is converging?",
        "active": "Show me all active cultural moments currently in FORMING or PEAK stage.",
    }
    while True:
        try:
            ui = input("Cultural > ").strip()
            if ui.lower() in ("quit", "exit"): break
            if ui.lower() in shortcuts: ui = shortcuts[ui.lower()]
            elif not ui: continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nCultural Moment Agent offline."); break
