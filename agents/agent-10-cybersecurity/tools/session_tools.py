"""
tools/session_tools.py  — Session anomaly detection for Agent 10.
"""
import json, math, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
sessions_table = dynamo.Table("skyblew-sessions")

@tool
def scan_active_sessions_for_anomalies(hours_back: int = 24) -> str:
    """
    Scan all active fan sessions from the last N hours and compute a risk score
    for each. Returns sessions flagged as HIGH (>0.70) or CRITICAL (>0.90) risk,
    with the reasons detected (impossible travel, token reuse, API volume spike).

    Args:
        hours_back: Hours of session history to scan (default 24, max 72).

    Returns:
        JSON with flagged sessions list, total scanned, and risk breakdown.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=min(hours_back, 72))).isoformat()
    try:
        resp = sessions_table.scan(
            FilterExpression="last_active > :cutoff",
            ExpressionAttributeValues={":cutoff": cutoff},
            Limit=500,
        )
        flagged = []
        for session in resp.get("Items", []):
            score, reasons = _compute_risk(session)
            if score > 0.70:
                flagged.append({
                    "session_id":  session.get("pk", ""),
                    "user_id":     session.get("user_id", ""),
                    "risk_score":  round(score, 3),
                    "risk_tier":   "CRITICAL" if score > 0.90 else "HIGH",
                    "reasons":     reasons,
                    "last_active": session.get("last_active", ""),
                })
        return json.dumps({
            "total_scanned": len(resp.get("Items", [])),
            "flagged_count": len(flagged),
            "flagged_sessions": flagged,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def _compute_risk(session: dict) -> tuple:
    score, reasons = 0.0, []
    if int(session.get("calls_last_15min", 0)) > 500:
        score += 0.40; reasons.append("HIGH_API_VOLUME")
    if session.get("multi_continent_login"):
        score += 0.60; reasons.append("IMPOSSIBLE_TRAVEL")
    if session.get("token_age_hours", 0) > 168:
        score += 0.80; reasons.append("EXPIRED_TOKEN_REUSE")
    return min(score, 1.0), reasons

@tool
def invalidate_session(session_id: str, reason: str) -> str:
    """
    Invalidate a specific fan session by marking its status as INVALIDATED_SECURITY.
    Use only for sessions with risk score > 0.90. Fan will be redirected to the
    warm SkyBlew re-login screen — not a blank page.

    Args:
        session_id: The DynamoDB session primary key (pk field).
        reason: Reason code (e.g., IMPOSSIBLE_TRAVEL, EXPIRED_TOKEN_REUSE).

    Returns:
        JSON confirmation with session_id and timestamp.
    """
    try:
        sessions_table.update_item(
            Key={"pk": session_id},
            UpdateExpression="SET #s = :invalid, invalidated_at = :ts, invalidation_reason = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":invalid": "INVALIDATED_SECURITY",
                ":ts": datetime.now(timezone.utc).isoformat(),
                ":r": reason,
            },
        )
        return json.dumps({"status": "INVALIDATED", "session_id": session_id, "reason": reason})
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_session_risk_report() -> str:
    """
    Generate a high-level session risk summary: total active sessions, count by
    risk tier (LOW/MEDIUM/HIGH/CRITICAL), and top 3 flagged sessions.
    Suitable for the daily security digest.

    Returns:
        JSON risk report.
    """
    raw = json.loads(scan_active_sessions_for_anomalies(hours_back=24))
    return json.dumps({
        "report_type": "SESSION_RISK_SUMMARY",
        "total_active": raw.get("total_scanned", 0),
        "flagged_high_or_critical": raw.get("flagged_count", 0),
        "top_flagged": raw.get("flagged_sessions", [])[:3],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
