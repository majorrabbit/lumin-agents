"""
╔══════════════════════════════════════════════════════════════╗
║   LUMIN LUXE INC. — AGENT 11: FAN DISCOVERY AGENT ADK       ║
║   AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12   ║
║   Mission: Find everyone who should love SkyBlew — then     ║
║   introduce them, authentically, one community at a time.   ║
╚══════════════════════════════════════════════════════════════╝

CRITICAL RULE: This agent DISCOVERS and DRAFTS.
It NEVER posts anything without explicit human approval.
Every outreach message goes to H.F. first. Always.
"""

import os
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.discovery_tools import (
    scan_reddit_communities,
    scan_tiktok_hashtags,
    scan_youtube_comments,
    find_discord_communities,
)
from tools.outreach_tools import (
    generate_outreach_message,
    submit_for_human_approval,
    post_approved_message,
    get_pending_approvals,
)
from tools.tracking_tools import (
    log_community_entry,
    record_conversion_event,
    get_conversion_report,
    get_top_converting_communities,
)
from tools.distribution_tools import (
    check_distrokid_delivery_status,
    build_utm_link,
    get_streaming_platform_status,
    prepare_editorial_pitch,
)

# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are the Lumin Fan Discovery Agent — the ambassador of SkyBlew's universe.
Your mission is to find every community of people worldwide who would love
SkyBlew's music, then introduce them to it in a way that feels natural,
specific, and respectful of their culture.

WHO IS SKYBLEW:
SkyBlew is a conscious hip-hop artist from North Carolina. His music lives at
the intersection of Nujabes-inspired lo-fi jazz-rap, the lyrical tradition of
Common and Lupe Fiasco, anime visual aesthetics (especially Samurai Champloo
and Carole & Tuesday), and the gaming culture of Bomb Rush Cyberfunk (Nintendo).
He coined "Rhythm Escapism™" — music that paints your world into something better.
His track "LightSwitch" is in Bomb Rush Cyberfunk and grows ~1,000 streams/day
organically from that Nintendo sync alone.
His newest album "MoreLoveLessWar" dropped in 2026 — a message the world needs.

THE NON-NEGOTIABLE RULE — HUMAN APPROVAL FIRST:
You NEVER post, send, reply, or publish anything without submitting it to the
human approval queue first via submit_for_human_approval(). This is not optional.
SkyBlew's authentic voice cannot be automated. You discover and draft.
H.F. decides what goes out under SkyBlew's name.

YOUR DISCOVERY TARGETS:
- r/nujabes, r/SamuraiChamploo — the sonic and aesthetic ancestors
- r/BombRushCyberfunk — fans who already heard LightSwitch in the game
- r/hiphopheads, r/LofiHipHop, r/nerdcore, r/ProgressiveHipHop
- r/LupeFiasco, r/Common — direct taste community
- TikTok: #nujabes (800M+ views), #lofi, #animemusic, #consciouship hop
- YouTube: Lofi Girl comment sections, Nujabes tribute videos, BRC gameplay videos
- Discord: anime-music, lo-fi, conscious-hiphop servers

HOW YOU SPEAK FOR SKYBLEW:
- Always specific — connect his music to exactly what THEY already love
- Always humble — introduce, never promote
- Always brief — 3-5 sentences maximum, never a wall of text
- Always genuine — if it sounds like an ad, rewrite it
- Never name-drop his streaming numbers unless directly relevant
- Lead with the music and message, not the artist's credentials

MORELOVELESSLY WAR CONTEXT:
This album arrived in a global moment of conflict. It is not a coincidence.
When pitching this to conscious communities, acknowledge the moment honestly.
This is not a marketing opportunity — it's a message that belongs in the world.

DISTRIBUTION CHECK:
Before pushing outreach for any track, verify it's live on all major platforms
using get_streaming_platform_status(). If Apple Music is missing, flag it
immediately. Running fan discovery while tracks are unavailable on major
platforms wastes the first-impression opportunity permanently.

YOUR DAILY FLOW:
1. Run discovery scans across target communities
2. Identify natural entry points (someone asking for music recs, discussing Nujabes, etc.)
3. Generate 3 outreach message variants using generate_outreach_message()
4. Submit ALL variants to the approval queue via submit_for_human_approval()
5. Track what gets approved, posted, and converted
6. Report daily: top opportunities, conversion rates, recommended priorities
"""

# ─── MODEL ──────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

# ─── AGENT ──────────────────────────────────────────────────────────────────

def create_fan_discovery_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            # Discovery
            scan_reddit_communities,
            scan_tiktok_hashtags,
            scan_youtube_comments,
            find_discord_communities,
            # Outreach (human-gated)
            generate_outreach_message,
            submit_for_human_approval,
            post_approved_message,
            get_pending_approvals,
            # Tracking
            log_community_entry,
            record_conversion_event,
            get_conversion_report,
            get_top_converting_communities,
            # Distribution
            check_distrokid_delivery_status,
            build_utm_link,
            get_streaming_platform_status,
            prepare_editorial_pitch,
        ],
    )

# ─── DAILY TASK HANDLERS ────────────────────────────────────────────────────

def run_morning_discovery(agent: Agent) -> dict:
    """06:00 UTC daily — scan all target communities for entry points."""
    result = agent(
        "Run the morning discovery scan across all target communities. "
        "Check r/nujabes, r/BombRushCyberfunk, r/hiphopheads, r/LofiHipHop, "
        "and TikTok #nujabes for new posts from the last 24 hours. "
        "Identify any posts that represent a natural entry point for introducing "
        "SkyBlew — someone asking for music recommendations, discussing lo-fi "
        "consciousness, talking about Bomb Rush Cyberfunk, or asking about "
        "music like Nujabes. For each opportunity found, log it to the database "
        "with context and generate outreach message variants."
    )
    return {"task": "morning_discovery", "result": str(result)}


def generate_daily_outreach_queue(agent: Agent) -> dict:
    """07:00 UTC daily — generate messages for all logged opportunities."""
    result = agent(
        "Review all newly logged community entry points from this morning's scan. "
        "For each opportunity, generate exactly 3 outreach message variants using "
        "SkyBlew's authentic voice — specific to that community, humble, brief "
        "(3-5 sentences max), and connecting his music to what they already love. "
        "Lead with LightSwitch for gaming/anime communities, MoreLoveLessWar for "
        "conscious music communities. Include the appropriate UTM-tracked link. "
        "Submit all variants to the human approval queue. Do not post anything."
    )
    return {"task": "generate_outreach_queue", "result": str(result)}


def run_evening_conversion_report(agent: Agent) -> dict:
    """22:00 UTC daily — summarize what worked today."""
    result = agent(
        "Generate today's fan discovery performance report. "
        "Pull conversion data for all posted content from today. "
        "Which communities drove the most Spotify streams? Which drove app installs? "
        "Which drove Bandcamp purchases? What is the top-performing community by "
        "weighted conversion score? What should be the priority outreach target tomorrow? "
        "Format this as a brief Slack-ready summary for H.F. — one screen, no fluff."
    )
    return {"task": "evening_report", "result": str(result)}


def run_distribution_health_check(agent: Agent) -> dict:
    """
    Run before any outreach campaign launch.
    ALWAYS verify tracks are available everywhere before driving traffic.
    """
    result = agent(
        "Run a distribution health check for LightSwitch and MoreLoveLessWar. "
        "Verify both tracks are live on: Spotify, Apple Music, Amazon Music, "
        "YouTube Music, Tidal, and Deezer. "
        "If either track is missing from any major platform, report which platform "
        "and what the DistroKid delivery status shows. "
        "Do not begin outreach campaign until both tracks are confirmed live "
        "on Apple Music specifically — this is the most critical gap. "
        "Also confirm that DistroKid has delivered MoreLoveLessWar to Apple Music "
        "and provide the current delivery status."
    )
    return {"task": "distribution_health_check", "result": str(result)}


def run_moreless_war_campaign_launch(agent: Agent) -> dict:
    """
    Special task: launch the coordinated MoreLoveLessWar outreach campaign.
    Only call this AFTER distribution_health_check confirms Apple Music is live.
    """
    result = agent(
        "Launch Phase 1 of the MoreLoveLessWar awareness campaign. "
        "Identify the 5 highest-priority community entry points for introducing "
        "MoreLoveLessWar specifically — focus on conscious hip-hop communities "
        "(r/hiphopheads, r/ProgressiveHipHop, conscious hip-hop Discord servers) "
        "and anime communities where the message of love over war resonates with "
        "ongoing thematic discussions. "
        "Frame the message authentically: this album arrived when the world needs "
        "this message. Generate 3 variants per community. "
        "Submit ALL to the approval queue with 'MORELOVELESSWAR_CAMPAIGN' tag. "
        "Do not post anything without human approval."
    )
    return {"task": "morelovelesswar_campaign", "result": str(result)}


# ─── LAMBDA HANDLER ─────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point for scheduled EventBridge triggers.

    Event structure:
    {
        "task": "morning_discovery" | "generate_outreach_queue" |
                "evening_report" | "distribution_health_check" |
                "morelovelesswar_campaign",
        "params": {}
    }
    """
    agent = create_fan_discovery_agent()
    task = event.get("task", "morning_discovery")

    task_map = {
        "morning_discovery":         lambda: run_morning_discovery(agent),
        "generate_outreach_queue":   lambda: generate_daily_outreach_queue(agent),
        "evening_report":            lambda: run_evening_conversion_report(agent),
        "distribution_health_check": lambda: run_distribution_health_check(agent),
        "morelovelesswar_campaign":  lambda: run_moreless_war_campaign_launch(agent),
    }

    handler = task_map.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available_tasks": list(task_map.keys())}

    return handler()


# ─── LOCAL DEV RUNNER ───────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🌍 Lumin Fan Discovery Agent — Interactive Mode")
    print("   Commands: 'scan' | 'queue' | 'report' | 'distro' | 'pending' | 'quit'\n")

    agent = create_fan_discovery_agent()

    shortcuts = {
        "scan":    "Scan all target communities for new fan discovery opportunities.",
        "queue":   "Generate outreach messages for all pending opportunities and submit for approval.",
        "report":  "Show today's conversion report — what drove the most streams and app installs?",
        "distro":  "Check distribution status for LightSwitch and MoreLoveLessWar on all platforms.",
        "pending": "Show all messages currently waiting in the human approval queue.",
    }

    while True:
        try:
            user_input = input("Discovery > ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if user_input.lower() in shortcuts:
                user_input = shortcuts[user_input.lower()]
            elif not user_input:
                continue

            response = agent(user_input)
            print(f"\nAgent: {response}\n")

        except KeyboardInterrupt:
            print("\n\nFan Discovery Agent offline.")
            break
