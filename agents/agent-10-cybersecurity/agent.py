"""
╔══════════════════════════════════════════════════════════════╗
║   LUMIN LUXE INC. — AGENT 10: CYBERSECURITY AGENT ADK       ║
║   AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12   ║
║   Protects: SkyBlew Universe App + all three Lumin entities  ║
╚══════════════════════════════════════════════════════════════╝

Entry point for the Lumin CyberSecurity Agent.
Run locally:   python agent.py
Deploy Lambda: see docs/DEPLOY.md
"""

import os
import json
from strands import Agent
from strands.models.anthropic import AnthropicModel

# Import all security tools
from tools.waf_tools import (
    check_waf_block_rate,
    update_waf_ip_blocklist,
    get_waf_recent_blocked_requests,
)
from tools.session_tools import (
    scan_active_sessions_for_anomalies,
    invalidate_session,
    get_session_risk_report,
)
from tools.content_tools import (
    verify_asset_integrity,
    reset_asset_baseline_hash,
    invalidate_cloudfront_cache,
)
from tools.guardduty_tools import (
    get_guardduty_findings,
    acknowledge_guardduty_finding,
    get_security_summary,
)
from tools.fraud_tools import (
    scan_streaming_anomalies,
    get_fraud_risk_report,
    prepare_dsp_fraud_report,
)
from tools.privacy_tools import (
    process_gdpr_deletion_request,
    audit_data_retention_compliance,
    check_pii_exposure_in_logs,
)
from tools.alert_tools import (
    post_security_alert_to_slack,
    send_critical_page_to_engineer,
    log_security_event,
)

# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are the Lumin CyberSecurity Agent — the silent guardian of the SkyBlew Universe
App and the entire Lumin three-entity infrastructure (Lumin Luxe Inc., OPP Inc.,
2StepsAboveTheStars LLC).

YOUR CORE MANDATE:
Protect every layer of the infrastructure while ensuring the fan experience remains
bright, joyful, and uninterrupted. Security must be INVISIBLE to fans. A fan loading
Kid Sky's face should never see a raw error code — they see a friendly sky-blue screen.
Behind that screen, you are watching everything.

YOUR SEVEN PROTECTION LAYERS:
1. Edge Defense (AWS WAF + CloudFront) — block threats before they reach the app
2. Post-Quantum Cryptography (AWS KMS) — protect fan data against future quantum attacks
3. Session Integrity — detect impossible travel, token reuse, anomalous API volumes
4. Content Integrity — verify Kid Sky, the SkyBlew logo, and all app assets are untampered
5. Fan Data Privacy — enforce GDPR/CCPA compliance, process deletion requests within 72h
6. Threat Intelligence (AWS GuardDuty) — interpret findings and route to the right human
7. Streaming Fraud Detection — protect SkyBlew's royalty income from bot inflation

YOUR DECISION AUTHORITY:
YOU MAY autonomously:
- Read monitoring data and generate reports
- Log security events to DynamoDB
- Post alerts to Slack (non-critical findings)
- Invalidate CloudFront cache when content tampering is detected
- Auto-invalidate sessions with risk score > 0.90 (immediate threat)

YOU MUST escalate (human decision required) before:
- Updating WAF rules (could block legitimate fans)
- Sending fraud reports to DSPs
- Processing GDPR deletion requests (irreversible)
- Any action affecting billing or account access

SEVERITY LEVELS:
- LOW (0-4): Log and include in weekly digest. No immediate alert.
- MEDIUM (4-7): Slack alert to #security-alerts. Review within 4 hours.
- HIGH (7-8.9): Immediate Slack alert. Eric and H.F. notified. Review now.
- CRITICAL (9-10): Page Eric directly. Potential active breach. Stop everything.

THE UI-FIRST RULE:
Before recommending any security response that touches the user-facing layer,
ask yourself: will this interrupt a fan's experience? If yes, find a way to
enforce security behind the scenes instead. Rate limiting should be invisible.
Session invalidation should redirect to a warm re-login screen with the SkyBlew
logo — never a blank page.

TONE: Report findings clearly and concisely. Use plain English, not security jargon,
when communicating with H.F. Use technical detail when communicating with Eric.
Always lead with the impact on the fan experience, then the technical detail.
"""

# ─── MODEL ──────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    """Initialize Claude claude-sonnet-4-6 via Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. "
            "Add it to .env or AWS Secrets Manager (key: lumin/anthropic-api-key)."
        )
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

# ─── AGENT DEFINITION ───────────────────────────────────────────────────────

def create_security_agent() -> Agent:
    """
    Create and return the fully configured CyberSecurity Agent.

    All seven security tool groups are registered. The agent uses Claude claude-sonnet-4-6
    with the security-specific system prompt and operates with the Minimal Footprint
    principle — reads freely, writes cautiously, escalates irreversible actions.
    """
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            # Layer 1 — Edge defense
            check_waf_block_rate,
            update_waf_ip_blocklist,
            get_waf_recent_blocked_requests,
            # Layer 3 — Session integrity
            scan_active_sessions_for_anomalies,
            invalidate_session,
            get_session_risk_report,
            # Layer 4 — Content integrity
            verify_asset_integrity,
            reset_asset_baseline_hash,
            invalidate_cloudfront_cache,
            # Layer 6 — GuardDuty
            get_guardduty_findings,
            acknowledge_guardduty_finding,
            get_security_summary,
            # Layer 7 — Streaming fraud
            scan_streaming_anomalies,
            get_fraud_risk_report,
            prepare_dsp_fraud_report,
            # Privacy
            process_gdpr_deletion_request,
            audit_data_retention_compliance,
            check_pii_exposure_in_logs,
            # Alerting
            post_security_alert_to_slack,
            send_critical_page_to_engineer,
            log_security_event,
        ],
    )

# ─── SCHEDULED TASK HANDLERS ─────────────────────────────────────────────────

def run_hourly_session_scan(agent: Agent) -> dict:
    """Triggered every hour by EventBridge → Lambda."""
    result = agent(
        "Run the hourly session integrity scan. Check all active sessions from the "
        "last 24 hours for anomalies. For any session with risk score > 0.90, "
        "auto-invalidate it. For sessions with risk score 0.70-0.89, post a Slack "
        "alert and log the event. Return a summary of sessions scanned and actions taken."
    )
    return {"task": "hourly_session_scan", "result": str(result)}


def run_daily_content_integrity(agent: Agent) -> dict:
    """Triggered every day at 02:00 UTC by EventBridge → Lambda."""
    result = agent(
        "Run the daily content integrity check. Verify the SHA-256 hash of every "
        "protected asset (Kid_Sky.png, SkyBlew_Logo_-_No_BG.PNG, SkyBlewUniverseApp.html, "
        "index.js, styles.css). If any hash differs from the stored baseline, immediately "
        "invalidate the CloudFront cache for that asset and post a CRITICAL alert to "
        "#security-alerts with the asset name, stored hash, and current hash. "
        "Do not update the baseline automatically — human confirmation required."
    )
    return {"task": "daily_content_integrity", "result": str(result)}


def run_daily_guardduty_digest(agent: Agent) -> dict:
    """Triggered every day at 08:00 UTC — morning security briefing."""
    result = agent(
        "Pull all new GuardDuty findings from the last 24 hours. For each finding: "
        "translate the technical finding type into plain-English impact language, "
        "assign the correct severity level (LOW/MEDIUM/HIGH/CRITICAL), and recommend "
        "the specific response action. Route HIGH and CRITICAL findings to Slack "
        "immediately. Compile LOW and MEDIUM findings into a daily digest message "
        "for the weekly report. Return the full digest."
    )
    return {"task": "daily_guardduty_digest", "result": str(result)}


def run_weekly_streaming_fraud_scan(agent: Agent) -> dict:
    """Triggered every Sunday at 03:00 UTC by EventBridge → Lambda."""
    result = agent(
        "Run the weekly streaming fraud analysis for the entire SkyBlew and OPP catalog. "
        "Focus especially on LightSwitch — it's growing ~1,000 streams/day organically "
        "from the Nintendo sync; any spike beyond that pattern with low save rates is "
        "a red flag. Check all tracks for: stream spikes without attribution source, "
        "geographic anomalies, low save rate relative to stream volume, and short "
        "listen duration clusters. Produce a fraud risk report. If any track shows "
        "high-confidence fraud (score > 0.80), prepare a draft DSP report for H.F. "
        "approval — do not send it automatically."
    )
    return {"task": "weekly_fraud_scan", "result": str(result)}


def handle_gdpr_request(agent: Agent, user_email: str, request_id: str) -> dict:
    """Triggered by n8n when a privacy@ email is received."""
    result = agent(
        f"Process GDPR/CCPA deletion request. Request ID: {request_id}. "
        f"User email: {user_email}. "
        "Step 1: Identify all DynamoDB records associated with this email across "
        "skyblew-sessions, fan-behavior-metrics, ask-lumin-cs-tickets, and "
        "ask-lumin-onboarding tables. "
        "Step 2: Log the full list of records to be deleted and present for human "
        "confirmation — DO NOT delete yet. "
        "Step 3: After human confirms, process the deletion and send a confirmation "
        "email via SES. Complete within 72 hours of the original request timestamp."
    )
    return {"task": "gdpr_deletion", "request_id": request_id, "result": str(result)}


# ─── LAMBDA HANDLER ──────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point. Routes EventBridge scheduled events to the correct
    security task handler.

    Event structure (from EventBridge):
    {
        "task": "hourly_session_scan" | "daily_content_integrity" |
                "daily_guardduty_digest" | "weekly_fraud_scan" | "gdpr_request",
        "params": {}  # task-specific parameters
    }
    """
    agent = create_security_agent()
    task = event.get("task", "daily_guardduty_digest")
    params = event.get("params", {})

    task_map = {
        "hourly_session_scan":      lambda: run_hourly_session_scan(agent),
        "daily_content_integrity":  lambda: run_daily_content_integrity(agent),
        "daily_guardduty_digest":   lambda: run_daily_guardduty_digest(agent),
        "weekly_fraud_scan":        lambda: run_weekly_streaming_fraud_scan(agent),
        "gdpr_request":             lambda: handle_gdpr_request(
                                        agent,
                                        params.get("user_email", ""),
                                        params.get("request_id", ""),
                                    ),
    }

    handler = task_map.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available_tasks": list(task_map.keys())}

    return handler()


# ─── LOCAL DEV RUNNER ────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Interactive mode for local testing.
    Set ANTHROPIC_API_KEY in your .env file before running.
    """
    from dotenv import load_dotenv
    load_dotenv()

    print("🔐 Lumin CyberSecurity Agent — Interactive Mode")
    print("   Type 'quit' to exit | 'scan' for quick session scan | 'status' for security summary\n")

    agent = create_security_agent()

    while True:
        try:
            user_input = input("Security > ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            elif user_input.lower() == "scan":
                user_input = "Run a quick security status check across all seven layers and give me a one-paragraph summary."
            elif user_input.lower() == "status":
                user_input = "Give me the current security posture of the Lumin infrastructure. What is the most pressing concern right now?"
            elif not user_input:
                continue

            response = agent(user_input)
            print(f"\nAgent: {response}\n")

        except KeyboardInterrupt:
            print("\n\nShutting down security agent.")
            break
