"""
tools/alert_tools.py — Notification and alerting tools for Agent 10.
Routes security findings to the right humans through the right channels.
"""
import json, os, boto3, requests
from datetime import datetime, timezone
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
events_table = dynamo.Table("security-events")
sns = boto3.client("sns", region_name="us-east-1")

SLACK_WEBHOOK_URL     = os.environ.get("SLACK_SECURITY_WEBHOOK", "")
CRITICAL_PAGE_TOPIC   = os.environ.get("SNS_CRITICAL_TOPIC", "")   # Eric's phone via SNS→SMS
SECURITY_TOPIC_ARN    = os.environ.get("SNS_SECURITY_TOPIC", "")   # #security-alerts email/slack


@tool
def post_security_alert_to_slack(
    message: str,
    severity: str,
    layer: str,
    recommended_action: str,
) -> str:
    """
    Post a formatted security alert to the Lumin #security-alerts Slack channel.
    Use for MEDIUM, HIGH, and CRITICAL findings. LOW findings go in the weekly digest only.

    Args:
        message: Plain-English description of the security finding.
        severity: One of LOW, MEDIUM, HIGH, CRITICAL.
        layer: Which security layer detected the issue (e.g., 'Layer 3 - Sessions').
        recommended_action: What the human team should do next.

    Returns:
        JSON confirmation or error from Slack webhook.
    """
    emoji_map = {"LOW": "🟡", "MEDIUM": "🟠", "HIGH": "🔴", "CRITICAL": "🚨"}
    emoji = emoji_map.get(severity.upper(), "❓")

    payload = {
        "text": f"{emoji} *Security Alert — {severity}*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} Lumin Security — {severity} Alert"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Layer:*\n{layer}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*Finding:*\n{message}"},
                    {"type": "mrkdwn", "text": f"*Recommended Action:*\n{recommended_action}"},
                    {"type": "mrkdwn", "text": f"*Detected At:*\n{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"},
                ],
            },
        ],
    }

    if not SLACK_WEBHOOK_URL:
        return json.dumps({"status": "DRY_RUN", "note": "SLACK_SECURITY_WEBHOOK not set.", "payload": payload})

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        return json.dumps({"status": "SENT" if resp.ok else "FAILED", "http_status": resp.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def send_critical_page_to_engineer(
    finding_summary: str,
    finding_id: str,
) -> str:
    """
    Send an immediate page to Eric via SNS → SMS for CRITICAL security findings only.
    This bypasses Slack and phones him directly. Use sparingly — only for severity 9+
    GuardDuty findings or confirmed content tampering.

    Args:
        finding_summary: One-sentence summary of the critical issue.
        finding_id: Unique ID for tracking (GuardDuty ID or internal event ID).

    Returns:
        JSON confirmation of page sent.
    """
    message = (
        f"🚨 LUMIN CRITICAL SECURITY ALERT\n"
        f"ID: {finding_id}\n"
        f"{finding_summary}\n"
        f"Check #security-alerts in Slack immediately.\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    if not CRITICAL_PAGE_TOPIC:
        return json.dumps({"status": "DRY_RUN", "note": "SNS_CRITICAL_TOPIC not set.", "message": message})

    try:
        sns.publish(TopicArn=CRITICAL_PAGE_TOPIC, Message=message, Subject="LUMIN CRITICAL SECURITY")
        return json.dumps({"status": "PAGED", "finding_id": finding_id, "message_sent": message})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def log_security_event(
    event_type: str,
    severity: str,
    details: str,
    auto_action_taken: str = "NONE",
) -> str:
    """
    Write a security event to the security-events DynamoDB audit log.
    Every security action taken by the agent — scan, alert, invalidation —
    must be logged here for auditability and compliance review.

    Args:
        event_type: Category (e.g., WAF_BLOCK, SESSION_ANOMALY, CONTENT_TAMPER).
        severity: LOW / MEDIUM / HIGH / CRITICAL.
        details: Full details of what was detected.
        auto_action_taken: What the agent did automatically (default NONE).

    Returns:
        JSON confirmation with the event ID written to DynamoDB.
    """
    ts = datetime.now(timezone.utc).isoformat()
    event_id = f"EVT#{event_type}#{ts}"

    try:
        events_table.put_item(Item={
            "pk": event_id,
            "sk": ts,
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "auto_action_taken": auto_action_taken,
            "reviewed_by_human": False,
            "logged_by": "agent-10-cybersecurity",
        })
        return json.dumps({"status": "LOGGED", "event_id": event_id, "severity": severity})
    except Exception as e:
        return json.dumps({"error": str(e)})
