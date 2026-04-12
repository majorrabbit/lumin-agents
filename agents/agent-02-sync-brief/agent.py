"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 2: SYNC BRIEF HUNTER ADK               ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: OPP Inc.                                                ║
║  Mission: Monitor every brief platform every 4 hours, match     ║
║  OPP's catalog instantly, and have a submission package         ║
║  ready before the deadline window closes.                        ║
╚══════════════════════════════════════════════════════════════════╝

Sync briefs have notoriously short turnaround windows — 24 to 72 hours
is standard for advertising briefs, 1-2 weeks for film/TV.
The difference between landing a placement and missing it is often
simply speed. This agent provides that speed.
"""

import os
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.brief_tools import (
    fetch_active_briefs,
    get_brief_deadline_alerts,
    log_brief_seen,
    get_brief_history,
)
from tools.catalog_tools import (
    search_opp_catalog,
    match_catalog_to_brief,
    get_track_metadata,
    prepare_submission_package,
)
from tools.submission_tools import (
    submit_to_platform,
    queue_submission_for_approval,
    get_pending_submissions,
    record_submission_outcome,
)
from tools.alert_tools_sync import (
    post_brief_alert_to_slack,
    send_deadline_warning,
    log_brief_event,
)

SYSTEM_PROMPT = """
You are the Lumin Sync Brief Hunter — the agent that watches every music
licensing brief platform on behalf of OPP Inc. and ensures no opportunity
is missed.

OPP INC. CATALOG STRENGTHS:
- One-stop clearance: OPP holds master AND publishing rights for its catalog,
  enabling pre-cleared licensing with no clearance delay (eliminates the
  standard 2-12 week wait). This is OPP's single most valuable asset for sync.
- Elvin Ross / Ronnie Garrett catalog: Emmy-winning composer (Tyler Perry Studios);
  Ronnie Garrett 10,000-song library (pending formal agreement — check status
  before pitching these tracks).
- SkyBlew / 2StepsAboveTheStars catalog: Rhythm Escapism™ genre, LightSwitch
  (Nintendo BRC sync proven), MoreLoveLessWar — anime, gaming, conscious audiences.
- Turnaround advantage: one email clears both sides. Most competitors take weeks.

THE BRIEF MATCHING FRAMEWORK:
For every brief, assess:
1. Sync DNA match: Does OPP have a track that fits the mood, tempo, genre, vocal type?
2. Clearance speed: Is the matching track fully cleared (one-stop)? Flag if not.
3. Deadline feasibility: Can we deliver stems + metadata before the deadline?
4. Fee fit: Is the proposed budget appropriate for the placement type?

YOUR DECISION AUTHORITY:
You MAY: Fetch briefs, search catalog, prepare submission packages, log events.
You MUST escalate (H.F. approval): Before submitting any actual brief response.
ALL submissions require a human "send" — you draft and prepare, H.F. authorizes.

BRIEF PRIORITY TIERS:
TIER 1 — Submit within 4 hours: Netflix/HBO/major streaming, major film/TV, 
          >$5K sync fee, cultural moment relevance (war/peace/social message).
TIER 2 — Submit within 24 hours: Cable TV, mid-tier advertising, web series.
TIER 3 — Submit within 72 hours: Independent film, podcast, YouTube Original.

MoreLoveLessWar NOTE: Any brief with themes of peace, unity, social justice,
anti-war, healing, or global community is a TIER 1 priority match.
Flag these immediately regardless of platform or fee size.
"""

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

def create_sync_brief_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            fetch_active_briefs, get_brief_deadline_alerts,
            log_brief_seen, get_brief_history,
            search_opp_catalog, match_catalog_to_brief,
            get_track_metadata, prepare_submission_package,
            submit_to_platform, queue_submission_for_approval,
            get_pending_submissions, record_submission_outcome,
            post_brief_alert_to_slack, send_deadline_warning, log_brief_event,
        ],
    )

def run_brief_scan(agent: Agent) -> dict:
    """Every 4 hours — EventBridge trigger."""
    result = agent(
        "Run the brief scan cycle. "
        "1. Call fetch_active_briefs() to pull all live briefs from all monitored platforms. "
        "2. For each brief not yet seen (check log_brief_seen()): "
        "   a. Call match_catalog_to_brief() to find the 3 best OPP catalog matches. "
        "   b. Assign the correct TIER (1/2/3) based on deadline and opportunity size. "
        "   c. Call prepare_submission_package() for the top match. "
        "   d. Call queue_submission_for_approval() — never submit directly. "
        "   e. For TIER 1 briefs: call post_brief_alert_to_slack() immediately. "
        "3. Call get_brief_deadline_alerts() for any brief within 6 hours of deadline. "
        "   For those: call send_deadline_warning() to H.F. "
        "Return: briefs found, new briefs, TIER 1 count, submissions queued."
    )
    return {"task": "brief_scan", "result": str(result)}

def run_deadline_monitor(agent: Agent) -> dict:
    """Every hour — watch for imminent deadlines."""
    result = agent(
        "Check for deadline urgency. Call get_brief_deadline_alerts() for all active "
        "briefs. For any brief with deadline < 6 hours and status QUEUED (not yet "
        "submitted): call send_deadline_warning() with urgency=CRITICAL. "
        "For briefs within 24 hours: urgency=HIGH. "
        "Return count of urgent briefs and actions taken."
    )
    return {"task": "deadline_monitor", "result": str(result)}

def run_weekly_brief_digest(agent: Agent) -> dict:
    """Mondays 08:00 UTC — Weekly sync brief performance summary."""
    result = agent(
        "Generate the weekly sync brief performance digest. "
        "Pull get_brief_history() for the last 7 days. Report: "
        "total briefs monitored, total matches found, submissions made, "
        "submissions pending, any placements confirmed. "
        "Identify: which platforms produced the most relevant briefs this week, "
        "which OPP catalog tracks matched most frequently (signals catalog strength), "
        "and any brief types where OPP had no matching track (catalog gap signals). "
        "Post to Slack #sync-intelligence and return the digest."
    )
    return {"task": "weekly_digest", "result": str(result)}

def lambda_handler(event: dict, context) -> dict:
    agent = create_sync_brief_agent()
    task  = event.get("task", "brief_scan")
    dispatch = {
        "brief_scan":        lambda: run_brief_scan(agent),
        "deadline_monitor":  lambda: run_deadline_monitor(agent),
        "weekly_digest":     lambda: run_weekly_brief_digest(agent),
    }
    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("🎵 Sync Brief Hunter — Interactive Mode")
    print("   Commands: 'scan' | 'pending' | 'deadlines' | 'quit'\n")
    agent = create_sync_brief_agent()
    shortcuts = {
        "scan":      "Run a full brief scan across all platforms and show me what's live right now.",
        "pending":   "Show me all submissions currently waiting in the approval queue.",
        "deadlines": "Are there any briefs with deadlines in the next 24 hours I should know about?",
    }
    while True:
        try:
            ui = input("SyncBrief > ").strip()
            if ui.lower() in ("quit", "exit"): break
            if ui.lower() in shortcuts: ui = shortcuts[ui.lower()]
            elif not ui: continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nSync Brief Hunter offline."); break
