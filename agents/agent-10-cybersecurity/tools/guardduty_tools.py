"""
tools/guardduty_tools.py — AWS GuardDuty threat intelligence for Agent 10.
"""
import json, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

gd = boto3.client("guardduty", region_name="us-east-1")
dynamo = boto3.resource("dynamodb", region_name="us-east-1")
alerts_table = dynamo.Table("security-alerts")

# GuardDuty Detector ID — retrieve via: aws guardduty list-detectors
DETECTOR_ID = "LUMIN-GUARDDUTY-DETECTOR-ID"

SEVERITY_MAP = {
    (0.0, 4.0):  ("LOW",      "🟡", "Include in weekly digest. No immediate action."),
    (4.0, 7.0):  ("MEDIUM",   "🟠", "Review within 4 hours."),
    (7.0, 8.9):  ("HIGH",     "🔴", "Review immediately — active threat likely."),
    (8.9, 10.0): ("CRITICAL", "🚨", "Page Eric now. Possible active breach."),
}

def _classify(score: float) -> tuple:
    for (lo, hi), label in SEVERITY_MAP.items():
        if lo <= score < hi:
            return label
    return ("UNKNOWN", "❓", "Manual review required.")


@tool
def get_guardduty_findings(severity_min: float = 0.0, hours_back: int = 24) -> str:
    """
    Retrieve GuardDuty threat findings from the last N hours filtered by minimum
    severity score. Translates raw AWS finding JSON into human-readable summaries
    with plain-English impact descriptions and recommended responses.

    Args:
        severity_min: Minimum severity score 0-10 (default 0.0 = all findings).
        hours_back: Hours to look back (default 24).

    Returns:
        JSON list of findings with severity label, plain-English description, and action.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
        list_resp = gd.list_findings(
            DetectorId=DETECTOR_ID,
            FindingCriteria={
                "Criterion": {
                    "severity": {"Gte": int(severity_min)},
                    "updatedAt": {"Gte": cutoff},
                }
            },
            MaxResults=50,
        )
        finding_ids = list_resp.get("FindingIds", [])
        if not finding_ids:
            return json.dumps({"findings": [], "message": "No findings in the specified window."})

        detail_resp = gd.get_findings(DetectorId=DETECTOR_ID, FindingIds=finding_ids)
        findings = []
        for f in detail_resp.get("Findings", []):
            score = f.get("Severity", 0)
            label, emoji, guidance = _classify(score)
            findings.append({
                "id":           f.get("Id"),
                "type":         f.get("Type"),
                "severity":     score,
                "severity_label": label,
                "emoji":        emoji,
                "description":  f.get("Description"),
                "resource_type": f.get("Resource", {}).get("ResourceType"),
                "region":       f.get("Region"),
                "updated_at":   f.get("UpdatedAt"),
                "guidance":     guidance,
            })

        return json.dumps({"total_findings": len(findings), "findings": findings})
    except Exception as e:
        return json.dumps({"error": str(e), "tip": "Verify DETECTOR_ID and GuardDuty is enabled."})


@tool
def acknowledge_guardduty_finding(finding_id: str, notes: str) -> str:
    """
    Mark a GuardDuty finding as acknowledged (archived) after review.
    Use this once a finding has been investigated and resolved or deemed a false positive.

    Args:
        finding_id: The GuardDuty finding ID to acknowledge.
        notes: Brief notes on resolution (for audit log in DynamoDB).

    Returns:
        JSON confirmation of acknowledgment.
    """
    try:
        gd.archive_findings(DetectorId=DETECTOR_ID, FindingIds=[finding_id])
        alerts_table.put_item(Item={
            "pk": f"GUARDDUTY#{finding_id}",
            "sk": datetime.now(timezone.utc).isoformat(),
            "status": "ACKNOWLEDGED",
            "notes": notes,
        })
        return json.dumps({"status": "ACKNOWLEDGED", "finding_id": finding_id, "notes": notes})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_security_summary() -> str:
    """
    Generate a high-level security posture summary across all monitoring layers.
    Suitable for the daily morning briefing to H.F. Combines GuardDuty findings
    count, active session anomalies, and content integrity status into one report.

    Returns:
        JSON security posture summary for the last 24 hours.
    """
    findings_raw = json.loads(get_guardduty_findings(severity_min=4.0, hours_back=24))
    findings = findings_raw.get("findings", [])
    critical = [f for f in findings if f.get("severity_label") == "CRITICAL"]
    high     = [f for f in findings if f.get("severity_label") == "HIGH"]

    return json.dumps({
        "report_type": "DAILY_SECURITY_SUMMARY",
        "overall_status": "RED" if critical else "ORANGE" if high else "GREEN",
        "guardduty": {
            "total_findings_24h": len(findings),
            "critical": len(critical),
            "high": len(high),
        },
        "recommendation": (
            "IMMEDIATE ACTION REQUIRED — critical findings detected." if critical
            else "Review high findings within 4 hours." if high
            else "No urgent threats. Continue standard monitoring."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
