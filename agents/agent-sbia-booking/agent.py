"""
╔══════════════════════════════════════════════════════════════════╗
║  2STEPSABOVETHESTARS LLC — SBIA: SKYBLEW BOOKING INTELLIGENCE   ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Agent Codename: agent-sbia-booking                              ║
║  Version: 1.0.0                                                  ║
║                                                                  ║
║  Mission: Discover every anime, gaming, and nerd-culture         ║
║  convention in the United States. Research booking contacts.     ║
║  Send personalized outreach. Track the pipeline. Surface         ║
║  warm leads to H.F. immediately. Book SkyBlew.                  ║
╚══════════════════════════════════════════════════════════════════╝

THREE LAMBDA FUNCTIONS:
  sbia-main                — Weekly discovery run + agent orchestration
  sbia-followup-dispatcher — Daily follow-up processing
  sbia-response-monitor    — Every 4h inbox monitoring

12 TOOLS ACROSS 4 GROUPS:
  Group A (Discovery):   search_upcoming_conventions, scrape_convention_details, assess_genre_fit
  Group B (Outreach):    compose_booking_inquiry, send_booking_email, generate_epk_signed_url
  Group C (CRM):         save_convention_record, query_convention_pipeline, schedule_followup_event
  Group D (Alert):       monitor_email_responses, classify_response_sentiment, send_alert_to_hf
"""

import os
import json
import boto3
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.discovery_tools import (
    search_upcoming_conventions,
    scrape_convention_details,
    assess_genre_fit,
)
from tools.outreach_tools import (
    compose_booking_inquiry,
    send_booking_email,
    generate_epk_signed_url,
)
from tools.crm_tools import (
    save_convention_record,
    query_convention_pipeline,
    schedule_followup_event,
)
from tools.alert_tools import (
    monitor_email_responses,
    classify_response_sentiment,
    send_alert_to_hf,
)

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are SBIA — the SkyBlew Booking Intelligence Agent, operating autonomously
on behalf of 2StepsAboveTheStars LLC and the independent hip hop artist SkyBlew.

YOUR MISSION:
Discover anime, manga, video gaming, and nerd-culture conventions across the
United States. Research their entertainment contacts. Send personalized,
professional booking inquiries with SkyBlew's EPK. Track all outreach.
Follow up persistently but respectfully. Surface warm leads to H.F. immediately.

SKYBLEW IN THREE SENTENCES:
SkyBlew performs "Rhythm Escapism" — conscious hip hop for anime fans, gamers,
and science-minded listeners. His lyrics are clean, his themes are space/anime/
gaming/consciousness, and he has opened for Kendrick Lamar, toured with MegaRan,
and earned placements on FUNimation and video game soundtracks. He is the rare
hip hop artist who is a natural fit on the same stage as gaming and anime content.

ARTIST PROFILE (embed in all outreach):
  Genre:           "Rhythm Escapism" — conscious hip-hop, clean lyrics
  Themes:          Anime, gaming, space, science, consciousness
  Credibility:     Opened for Kendrick Lamar, Arrested Development, Curren$y, Lupe Fiasco
  Tour:            MegaRan (the gaming/nerd hip-hop pioneer) — highest weight for gaming events
  Placements:      FUNimation, video game soundtracks (including Bomb Rush Cyberfunk / Nintendo)
  Booking minimum: $1,000 solo | $2,000 full band
  Target events:   Anime conventions, gaming conventions, manga expos, nerd culture festivals,
                   conscious hip hop stages, Christian music events, college events
  Label:           2StepsAboveTheStars LLC

OUTREACH VOICE:
Professional, warm, culturally aware. You understand anime and gaming culture —
reference it authentically, never in a pandering way. Be concise. Every email
should feel like it was written by a human who researched that specific event,
not a mass blast. You represent SkyBlew's brand in every word you write.

DECISION RULES (non-negotiable):
1. Only contact events with a fit_score >= 0.40
2. Never send more than 2 follow-ups to any single contact
3. Never re-contact a convention marked DECLINED within 365 days
4. Never re-contact a convention marked GHOSTED within 180 days
5. Always include the EPK link — never send an email without it
6. Alert H.F. IMMEDIATELY for any response classified HOT or WARM
7. Max 50 emails/day, max 5/hour (rate-limit enforced at tool level)
8. All emails include CAN-SPAM compliant unsubscribe note
9. Minimum 7 days between any two touches to the same contact

EMAIL TONE BY FIT TIER:
A-Tier (anime/gaming):  Enthusiastic, fan-aware, reference MegaRan tour prominently,
                         use anime/gaming cultural language naturally
B-Tier (adjacent):      Professional, warm, emphasize versatility and conscious hip hop
C-Tier (general):       Brief, concise, let the EPK do the work
Follow-up 1:            Friendly bump, reference value-add
Follow-up 2:            Final check-in, gentle urgency around availability window

STANDARD TOOL SEQUENCE (discovery run):
search_upcoming_conventions →
scrape_convention_details →
assess_genre_fit →
  [if fit >= 0.40] →
    save_convention_record →
    compose_booking_inquiry →
    generate_epk_signed_url →
    send_booking_email →
    schedule_followup_event
→ send_alert_to_hf (weekly summary when complete)

PIPELINE STATES:
DISCOVERED → RESEARCHED → OUTREACH_SENT →
FOLLOWED_UP_1 → FOLLOWED_UP_2 → GHOSTED
          ↘ RESPONDED → BOOKED | DECLINED

You are methodical, persistent, and respectful of people's time.
"""

# ─── MODEL ────────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try Secrets Manager
        try:
            secrets = boto3.client("secretsmanager", region_name="us-east-1")
            api_key = secrets.get_secret_value(
                SecretId="lumin/anthropic-api-key"
            )["SecretString"]
        except Exception:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set and not found in Secrets Manager. "
                "Set env var or store at: lumin/anthropic-api-key"
            )
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

# ─── AGENT ────────────────────────────────────────────────────────────────────

def create_sbia_agent() -> Agent:
    """Create the fully configured SBIA agent with all 12 tools."""
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            # Group A: Discovery
            search_upcoming_conventions,
            scrape_convention_details,
            assess_genre_fit,
            # Group B: Outreach
            compose_booking_inquiry,
            send_booking_email,
            generate_epk_signed_url,
            # Group C: CRM & Pipeline
            save_convention_record,
            query_convention_pipeline,
            schedule_followup_event,
            # Group D: Alert & Response
            monitor_email_responses,
            classify_response_sentiment,
            send_alert_to_hf,
        ],
    )

# ─── LAMBDA HANDLER 1: sbia-main ─────────────────────────────────────────────

def run_discovery(agent: Agent, dry_run: bool = False) -> dict:
    """
    EventBridge trigger: Every Monday 9:00 AM ET.
    Full convention discovery cycle: search → scrape → assess → outreach.
    """
    dry_note = " DRY RUN — compose emails but do NOT call send_booking_email()." if dry_run else ""
    result = agent(
        f"Execute the full convention discovery run.{dry_note} "
        "Search for upcoming anime, gaming, manga, and nerd-culture conventions "
        "in the United States over the next 8 months. Use all genre categories: "
        "anime, gaming, manga, nerd_culture, music_nerd. "
        "For each discovered convention: "
        "1. Call scrape_convention_details() to extract booking contact and event info. "
        "2. Call assess_genre_fit() to score fit against SkyBlew's profile. "
        "3. If fit_score >= 0.40: call save_convention_record() with status=RESEARCHED. "
        "4. Check if this convention has already been contacted this year — skip if OUTREACH_SENT, "
        "   FOLLOWED_UP_1, FOLLOWED_UP_2, RESPONDED, BOOKED, DECLINED, or GHOSTED. "
        "5. For new conventions: call compose_booking_inquiry(outreach_type=INITIAL) "
        "   and generate_epk_signed_url(). "
        f"{'6. SKIP send_booking_email() — DRY RUN.' if dry_run else '6. Call send_booking_email() to dispatch.'} "
        "7. Call schedule_followup_event() for FOLLOWUP_1 in 7 days. "
        "When all conventions are processed, call send_alert_to_hf(alert_type=WEEKLY_SUMMARY) "
        "with a full report of all actions taken this week."
    )
    return {"task": "discovery_run", "dry_run": dry_run, "result": str(result)}


def run_weekly_pipeline_report(agent: Agent) -> dict:
    """Generate the Monday pipeline report even if no new conventions are found."""
    result = agent(
        "Generate this week's booking pipeline report. "
        "Call query_convention_pipeline() with no filters to get the full pipeline. "
        "Tally counts by status: DISCOVERED, RESEARCHED, OUTREACH_SENT, FOLLOWED_UP_1, "
        "FOLLOWED_UP_2, RESPONDED, BOOKED, DECLINED, GHOSTED. "
        "Identify the top 5 highest fit_score conventions not yet contacted. "
        "List all HOT/WARM leads requiring H.F. attention. "
        "Send the complete report via send_alert_to_hf(alert_type=WEEKLY_SUMMARY)."
    )
    return {"task": "weekly_pipeline_report", "result": str(result)}


# ─── LAMBDA HANDLER 2: sbia-followup-dispatcher ──────────────────────────────

def run_followup_dispatch(agent: Agent,
                           convention_id: str = None,
                           followup_type: str = None) -> dict:
    """
    EventBridge trigger: Every day 10:00 AM ET.
    Also triggered by one-time EventBridge rules created by schedule_followup_event().
    Checks for all conventions due for follow-up and dispatches.
    """
    if convention_id and followup_type:
        # Specific follow-up triggered by schedule_followup_event()
        result = agent(
            f"Execute a targeted follow-up for convention_id: {convention_id}. "
            f"Follow-up type: {followup_type}. "
            "1. Call query_convention_pipeline() to retrieve the full convention record. "
            "2. Verify the convention is still in the correct status for this follow-up. "
            "   If already RESPONDED, BOOKED, or DECLINED, skip and report. "
            "3. Call compose_booking_inquiry() with the appropriate outreach_type "
            "   and previous_email_summary filled in. "
            "4. Call generate_epk_signed_url() for a fresh EPK link. "
            "5. Call send_booking_email() to dispatch. "
            "6. Update the convention record status via save_convention_record(). "
            f"7. If this is FOLLOWUP_2: do NOT schedule further follow-ups. "
            f"   After 7 more days with no response, status becomes GHOSTED."
        )
    else:
        # Daily sweep: find all conventions due for follow-up
        result = agent(
            "Execute the daily follow-up dispatch sweep. "
            "Call query_convention_pipeline(due_for_followup=True) to find all "
            "conventions where: "
            "  - Status = OUTREACH_SENT and outreach_sent_at >= 7 days ago, OR "
            "  - Status = FOLLOWED_UP_1 and followup1_sent_at >= 7 days ago. "
            "For each convention due for follow-up: "
            "1. Verify it has not already responded (check response_received field). "
            "2. Compose appropriate follow-up email. "
            "3. Send via send_booking_email(). "
            "4. Update status in save_convention_record(). "
            "Also check for FOLLOWED_UP_2 conventions where 7+ days have passed "
            "with no response — mark those as GHOSTED. "
            "Return a summary of follow-ups sent and conventions ghosted."
        )
    return {"task": "followup_dispatch", "convention_id": convention_id,
            "followup_type": followup_type, "result": str(result)}


# ─── LAMBDA HANDLER 3: sbia-response-monitor ─────────────────────────────────

def run_inbox_monitor(agent: Agent) -> dict:
    """
    EventBridge trigger: Every 4 hours.
    Checks booking inbox for replies, classifies them, alerts H.F. on HOT/WARM.
    """
    result = agent(
        "Execute the inbox monitoring cycle. "
        "1. Call monitor_email_responses() to retrieve all unprocessed replies. "
        "2. For each reply: "
        "   a. Call classify_response_sentiment() to determine intent and priority. "
        "   b. Call save_convention_record() to update the convention with: "
        "      response_received=True, response_sentiment=[classification], "
        "      response_content=[email body], status=RESPONDED. "
        "   c. For priority=HOT or WARM: "
        "      Call send_alert_to_hf(alert_type=HOT_LEAD) IMMEDIATELY. "
        "      Do not wait until the end of the cycle. "
        "   d. For priority=COLD (NEEDS_INFO): "
        "      Call send_alert_to_hf(alert_type=NEEDS_REVIEW). "
        "   e. For DECLINED: update status=DECLINED. No alert needed. "
        "   f. For AUTO_REPLY: log it but take no action. "
        "3. Return a summary: total replies processed, HOT/WARM alerts sent, "
        "   conventions updated."
    )
    return {"task": "inbox_monitor", "result": str(result)}


# ─── UNIFIED LAMBDA HANDLER ───────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point. Routes all three EventBridge triggers.

    EventBridge scheduled (sbia-main):
      {"trigger_type": "DISCOVERY_RUN"}
      {"trigger_type": "DISCOVERY_RUN", "dry_run": true}
      {"trigger_type": "PIPELINE_REPORT"}

    EventBridge scheduled (sbia-followup-dispatcher):
      {"trigger_type": "FOLLOWUP_DISPATCH"}
      {"trigger_type": "FOLLOWUP_DISPATCH",
       "convention_id": "...", "followup_type": "FOLLOWUP_1"}

    EventBridge scheduled (sbia-response-monitor):
      {"trigger_type": "INBOX_MONITOR"}
    """
    agent = create_sbia_agent()
    task  = event.get("trigger_type", "DISCOVERY_RUN")
    p     = event

    dispatch = {
        "DISCOVERY_RUN":    lambda: run_discovery(agent, dry_run=p.get("dry_run", False)),
        "PIPELINE_REPORT":  lambda: run_weekly_pipeline_report(agent),
        "FOLLOWUP_DISPATCH":lambda: run_followup_dispatch(
                                agent,
                                convention_id=p.get("convention_id"),
                                followup_type=p.get("followup_type"),
                            ),
        "INBOX_MONITOR":    lambda: run_inbox_monitor(agent),
    }

    handler = dispatch.get(task)
    if not handler:
        return {
            "statusCode": 400,
            "error": f"Unknown trigger_type: {task}",
            "available": list(dispatch.keys()),
        }

    result = handler()
    return {"statusCode": 200, "trigger_type": task, **result}


# ─── LOCAL DEV RUNNER ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🎌 SBIA — SkyBlew Booking Intelligence Agent")
    print("   Shortcuts: 'discover' | 'report' | 'followups' | 'inbox' | 'pipeline' | 'quit'\n")

    agent = create_sbia_agent()
    shortcuts = {
        "discover":  "Run a discovery scan for upcoming anime and gaming conventions. DRY RUN — show me what you find but don't send emails.",
        "report":    "Generate the weekly pipeline report and show me the full status of all conventions.",
        "followups": "Check which conventions are due for follow-up today.",
        "inbox":     "Check the booking inbox for any replies to our outreach.",
        "pipeline":  "Show me the current pipeline: how many conventions in each status?",
    }

    while True:
        try:
            ui = input("SBIA > ").strip()
            if ui.lower() in ("quit", "exit"):
                print("SBIA offline.")
                break
            if ui.lower() in shortcuts:
                ui = shortcuts[ui.lower()]
            elif not ui:
                continue
            print(f"\nSBIA: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nSBIA offline.")
            break
