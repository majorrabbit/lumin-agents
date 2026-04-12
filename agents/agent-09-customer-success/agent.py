"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 9: ASKLUM IN CUSTOMER SUCCESS ADK      ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: Lumin Luxe Inc.  |  Platform: ask.lumin.luxe            ║
║  Mission: Every AskLumin subscriber succeeds — or we know why.  ║
╚══════════════════════════════════════════════════════════════════╝

The Customer Success Agent is the first human voice a new AskLumin subscriber
encounters — except it is not human. It is Claude, configured with the full
context of that subscriber's account, usage history, and engagement trend,
operating under a strict constitutional prompt that defines exactly what it
can handle and what it must escalate.

This agent defers the need for a CS hire by 6-9 months while generating the
training corpus that makes AskLumin progressively better.
"""

import os
import json
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.context_tools import (
    enrich_user_context,
    get_subscription_details,
    get_feature_usage_summary,
)
from tools.onboarding_tools import (
    get_onboarding_status,
    send_onboarding_touchpoint,
    mark_touchpoint_completed,
    get_users_needing_touchpoint,
)
from tools.support_tools import (
    create_support_ticket,
    update_ticket_status,
    get_open_tickets,
    escalate_to_human,
    log_cs_interaction,
)
from tools.retention_tools import (
    compute_churn_risk,
    trigger_reengagement,
    get_at_risk_subscribers,
    record_nps_response,
)
from tools.metrics_tools import (
    compute_daily_cs_metrics,
    get_deflection_rate,
    get_feature_activation_rates,
    get_nps_summary,
)

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are Lumin — the Customer Success intelligence of AskLumin (ask.lumin.luxe),
the AI-powered music intelligence platform built by Lumin Luxe Inc. for music
industry professionals: artists, labels, publishers, sync agents, and A&R teams.

YOUR ROLE:
Help every AskLumin subscriber get maximum value from their subscription. You
onboard new users, answer product questions, proactively reach out to users who
are not engaging, identify upsell opportunities, and connect users with human
support when the situation requires it.

WHAT YOU KNOW ABOUT THIS USER:
{user_context}

ASKLUM IN SUBSCRIPTION TIERS:
- Spark (free): Core research queries, basic Resonance Engine access, 50 queries/month
- Resonance Pro ($49/mo): Full Resonance Engine, Sync Brief Scanner, Artist Trajectory
  Reports, Sync Pitch Generator, Export to PDF, 500 queries/month
- Luminary Enterprise (custom): Full platform + API access, team collaboration,
  custom data upload, dedicated onboarding, SLA support

YOUR DECISION AUTHORITY:
YOU MAY autonomously:
- Answer any product question about AskLumin features and capabilities
- Guide users through any feature with step-by-step instructions
- Proactively surface unused features relevant to the user's role
- Send onboarding touchpoint emails via SES
- Create and update support ticket records
- Collect NPS scores
- Generate usage reports for H.F.'s review

YOU MUST escalate (human required) for:
- Any billing dispute or refund request
- Any request to change subscription tier
- Any report of data accuracy issues in the Resonance Engine
- Any Enterprise prospect asking about custom data integrations or API access
- Any user expressing serious frustration (3+ negative signals in one conversation)
- Legal or compliance questions

ESCALATION SCRIPT:
When escalating always say: "I'm connecting you with our team — they'll follow up
within [24 hours for Pro / 4 hours for Enterprise]. I've already shared your full
context so you won't need to repeat anything." Then call escalate_to_human().

ESCALATION TRIGGERS — detect these patterns:
- Words: "refund", "cancel", "terrible", "useless", "wrong data", "broken"
- Sentiment: repeated frustration in the same session
- Request type: anything outside your decision authority above

THE ASKLUM IN VOICE:
Warm, direct, knowledgeable. Never sycophantic. You are Lumin — the same
intelligence that powers the research platform. Speak with confidence and care.
Avoid "I understand your frustration" clichés. Instead, act on the problem.
If a user is stuck, show them the path forward immediately.

Never say "as an AI" or disclaim your nature unless directly asked. If asked
whether you are human or AI, be honest: you are Lumin, the AI customer success
intelligence built by Lumin Luxe Inc.
"""

# ─── MODEL ─────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. "
            "Add it to .env or AWS Secrets Manager (key: lumin/anthropic-api-key)."
        )
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=2048,
    )

# ─── CONTEXT-ENRICHED AGENT FACTORY ────────────────────────────────────────

def create_cs_agent(user_id: str = None) -> Agent:
    """
    Create a Customer Success Agent pre-enriched with a specific user's context.
    When user_id is provided, the system prompt is hydrated with that user's
    subscription tier, usage history, features activated, and engagement trend.
    When user_id is None, creates a generic agent for batch operations.
    """
    if user_id:
        ctx_raw = enrich_user_context(user_id=user_id)
        ctx = json.loads(ctx_raw)
        user_context_block = (
            f"Tier: {ctx.get('tier', 'Unknown')}\n"
            f"Account age: {ctx.get('account_age_days', '?')} days\n"
            f"Last active: {ctx.get('last_active', 'Unknown')}\n"
            f"Features activated: {', '.join(ctx.get('features_used', ['None yet']))}\n"
            f"Features NOT yet activated: {', '.join(ctx.get('features_not_used', []))}\n"
            f"Usage trend: {ctx.get('usage_trend', 'NEW')}\n"
            f"Open tickets: {ctx.get('open_tickets', 0)}\n"
            f"Churn risk: {ctx.get('churn_risk', 'LOW')}"
        )
    else:
        user_context_block = "No specific user context — operating in batch mode."

    enriched_prompt = SYSTEM_PROMPT.replace("{user_context}", user_context_block)

    return Agent(
        model=get_model(),
        system_prompt=enriched_prompt,
        tools=[
            # Context
            enrich_user_context,
            get_subscription_details,
            get_feature_usage_summary,
            # Onboarding
            get_onboarding_status,
            send_onboarding_touchpoint,
            mark_touchpoint_completed,
            get_users_needing_touchpoint,
            # Support
            create_support_ticket,
            update_ticket_status,
            get_open_tickets,
            escalate_to_human,
            log_cs_interaction,
            # Retention
            compute_churn_risk,
            trigger_reengagement,
            get_at_risk_subscribers,
            record_nps_response,
            # Metrics
            compute_daily_cs_metrics,
            get_deflection_rate,
            get_feature_activation_rates,
            get_nps_summary,
        ],
    )

# ─── SCHEDULED TASK HANDLERS ───────────────────────────────────────────────

def run_daily_onboarding_sweep(agent: Agent) -> dict:
    """
    08:00 UTC daily — EventBridge trigger.
    Finds all users who need a Day 0, 1, 3, 5, 7, or 30 onboarding touchpoint
    and dispatches the appropriate message via SES.
    """
    result = agent(
        "Run the daily onboarding sweep. Call get_users_needing_touchpoint() to find "
        "all subscribers who are due for a Day 0, 1, 3, 5, 7, or 30 touchpoint today. "
        "For each user: check their usage_trend and features_not_used, then send the "
        "most relevant touchpoint message via send_onboarding_touchpoint(). "
        "Day 0 = welcome and first 3 moves. Day 1 = activation check. "
        "Day 3 = surface one unused high-value feature. Day 5 = NPS check-in. "
        "Day 7 = Spark users get upgrade prompt with specific value prop. "
        "Day 30 = monthly summary + month 2 suggestions. "
        "Log every touchpoint sent. Return a count by day and tier."
    )
    return {"task": "daily_onboarding_sweep", "result": str(result)}


def run_daily_churn_scan(agent: Agent) -> dict:
    """
    09:00 UTC daily — Detect and act on at-risk subscribers before they cancel.
    """
    result = agent(
        "Run the daily churn risk scan. Call get_at_risk_subscribers() to find all "
        "subscribers with usage_trend = DECLINING and days_since_last_session > 5. "
        "For each: compute their churn risk score via compute_churn_risk(). "
        "For HIGH risk (score > 0.70): trigger a proactive re-engagement via "
        "trigger_reengagement() — do NOT mention their declining usage in the message, "
        "instead surface one specific unused feature that matches their role. "
        "For MEDIUM risk (0.40-0.70): add to the weekly watch list. "
        "Post a summary to Slack #cs-alerts with: count by tier, highest-risk users, "
        "and actions taken. Return a risk report."
    )
    return {"task": "daily_churn_scan", "result": str(result)}


def run_weekly_cs_digest(agent: Agent) -> dict:
    """
    Mondays 09:00 UTC — Weekly CS metrics report to H.F.
    """
    result = agent(
        "Generate the weekly Customer Success digest for H.F. Pull: "
        "get_deflection_rate() for the past 7 days, "
        "get_feature_activation_rates() to see which features users aren't discovering, "
        "get_nps_summary() for any scores collected this week, "
        "get_at_risk_subscribers() for the current churn watch list. "
        "Format as a concise executive summary: headline metrics, one insight, "
        "one recommended action. Post to Slack #cs-leadership. "
        "This should be readable in 90 seconds — no fluff."
    )
    return {"task": "weekly_cs_digest", "result": str(result)}


def handle_inbound_support(user_id: str, message: str, session_id: str) -> dict:
    """
    Real-time handler for inbound support conversations.
    Called from the AskLumin /cs-chat API endpoint.
    Creates a context-enriched agent for this specific user.
    """
    agent = create_cs_agent(user_id=user_id)
    result = agent(
        f"A subscriber has sent you this message: '{message}'\n\n"
        f"Session ID: {session_id}\n"
        "Respond in character as Lumin — their AskLumin customer success partner. "
        "Check their context above. If their question relates to a feature they haven't "
        "activated yet, guide them to it directly with specific steps. "
        "If this triggers any escalation criteria, call escalate_to_human() immediately. "
        "Log this interaction via log_cs_interaction() after responding."
    )
    return {"task": "inbound_support", "user_id": user_id, "result": str(result)}


def run_monthly_metrics_report(agent: Agent) -> dict:
    """
    1st of each month 07:00 UTC — Full CS performance report.
    """
    result = agent(
        "Generate the monthly Customer Success performance report. Include: "
        "total support interactions handled, ticket deflection rate (target >75%), "
        "feature activation rates by tier (which features are being discovered vs. ignored), "
        "NPS score trend, churn interventions attempted vs. churned, "
        "top 3 reasons for escalation to human team. "
        "Compare to prior month where data exists. "
        "Output as a structured report suitable for the investor update narrative."
    )
    return {"task": "monthly_metrics_report", "result": str(result)}


# ─── LAMBDA HANDLER ────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point. Routes EventBridge and API Gateway events.

    Scheduled tasks (EventBridge):
        {"task": "daily_onboarding_sweep"}
        {"task": "daily_churn_scan"}
        {"task": "weekly_cs_digest"}
        {"task": "monthly_metrics_report"}

    Real-time support (API Gateway → /cs-chat):
        {"task": "inbound_support", "user_id": "...", "message": "...", "session_id": "..."}
    """
    agent = create_cs_agent()  # generic agent for batch tasks
    task  = event.get("task", "daily_onboarding_sweep")
    p     = event.get("params", event)  # support both formats

    dispatch = {
        "daily_onboarding_sweep":  lambda: run_daily_onboarding_sweep(agent),
        "daily_churn_scan":        lambda: run_daily_churn_scan(agent),
        "weekly_cs_digest":        lambda: run_weekly_cs_digest(agent),
        "monthly_metrics_report":  lambda: run_monthly_metrics_report(agent),
        "inbound_support":         lambda: handle_inbound_support(
                                       p.get("user_id", ""),
                                       p.get("message", ""),
                                       p.get("session_id", ""),
                                   ),
    }

    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()


# ─── LOCAL DEV RUNNER ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("💬 AskLumin Customer Success Agent — Interactive Mode")
    print("   Commands: 'onboard' | 'churn' | 'metrics' | 'nps' | 'quit'\n")

    agent = create_cs_agent()

    shortcuts = {
        "onboard": "Find all users needing an onboarding touchpoint today and show me who they are.",
        "churn":   "Show me the current at-risk subscriber list with churn risk scores.",
        "metrics": "Give me today's CS metrics: deflection rate, feature activation, and NPS.",
        "nps":     "Summarize all NPS scores collected this week and the most common feedback themes.",
    }

    while True:
        try:
            user_input = input("CS > ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if user_input.lower() in shortcuts:
                user_input = shortcuts[user_input.lower()]
            elif not user_input:
                continue
            print(f"\nLumin: {agent(user_input)}\n")
        except KeyboardInterrupt:
            print("\n\nCustomer Success Agent offline.")
            break
