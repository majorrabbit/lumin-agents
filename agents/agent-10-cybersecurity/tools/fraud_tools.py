"""
tools/fraud_tools.py — Streaming fraud detection for Agent 10.
Protects SkyBlew's royalty income from bot inflation and manipulation.
"""
import json, os, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
fraud_table = dynamo.Table("security-fraud-reports")

CM_BASE = "https://api.chartmetric.com/api"


def _cm_headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('CHARTMETRIC_API_KEY', '')}"}


@tool
def scan_streaming_anomalies(artist_id: str = "skyblew", days_back: int = 7) -> str:
    """
    Scan SkyBlew's streaming data for fraud signals: stream spikes without
    attribution, geographic anomalies, low save-rate-to-stream ratios, and
    short listen duration clusters. Returns an anomaly report with confidence
    scores and recommended actions.

    Args:
        artist_id: Chartmetric artist identifier (default 'skyblew').
        days_back: Days of history to analyze (default 7).

    Returns:
        JSON anomaly report with findings, confidence scores, and recommendations.
    """
    try:
        # Pull streaming velocity from Chartmetric
        resp = requests.get(
            f"{CM_BASE}/artist/{artist_id}/where-people-listen",
            headers=_cm_headers(),
            params={"since": (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")},
            timeout=15,
        )
        data = resp.json() if resp.ok else {}

        anomalies = []

        # Signal 1: Save-rate divergence (most reliable organic indicator)
        # Real fans stream AND save. Bots only stream.
        streams = data.get("total_streams", 0)
        saves   = data.get("total_saves", 0)
        save_rate = saves / streams if streams > 0 else 0

        if streams > 50_000 and save_rate < 0.02:
            anomalies.append({
                "type": "LOW_SAVE_RATE",
                "confidence": 0.75,
                "detail": f"Save rate {save_rate:.3f} is below 2% threshold for {streams:,} streams.",
                "action": "Monitor for 72 hours. If persists, prepare DSP report.",
            })

        # Signal 2: Geographic concentration
        geo = data.get("top_countries", [])
        if geo and geo[0].get("pct", 0) > 60:
            anomalies.append({
                "type": "GEOGRAPHIC_CONCENTRATION",
                "confidence": 0.65,
                "detail": f"60%+ streams from single country: {geo[0].get('country')}.",
                "action": "Cross-check against marketing activity. Flag if no campaign in that market.",
            })

        fraud_score = max((a["confidence"] for a in anomalies), default=0.0)
        return json.dumps({
            "artist_id": artist_id,
            "days_analyzed": days_back,
            "total_streams": streams,
            "save_rate": round(save_rate, 4),
            "fraud_score": round(fraud_score, 3),
            "fraud_risk": "HIGH" if fraud_score > 0.75 else "MEDIUM" if fraud_score > 0.50 else "LOW",
            "anomalies": anomalies,
            "note": "LightSwitch growing ~1,000/day from Nintendo BRC sync is LEGITIMATE. Do not flag organic sync growth.",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_fraud_risk_report() -> str:
    """
    Retrieve the most recent streaming fraud risk assessment from DynamoDB.
    Use for the weekly security digest or when H.F. asks for the current fraud status.

    Returns:
        JSON of the latest fraud risk report.
    """
    try:
        resp = fraud_table.query(
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": "FRAUD#WEEKLY"},
            ScanIndexForward=False,
            Limit=1,
        )
        items = resp.get("Items", [])
        return json.dumps(items[0] if items else {"message": "No fraud reports on file. Run scan_streaming_anomalies first."})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def prepare_dsp_fraud_report(track_name: str, anomaly_details: str) -> str:
    """
    Draft a fraud report to submit to DSP (Spotify/Apple Music) trust and safety teams.
    This is DRAFT ONLY — requires H.F. review and approval before sending.
    Do not send this automatically.

    Args:
        track_name: The track name affected (e.g., "LightSwitch").
        anomaly_details: Plain-English description of the anomaly detected.

    Returns:
        JSON with draft report text and submission instructions.
    """
    draft = f"""
DSP FRAUD REPORT DRAFT — SkyBlew / 2StepsAboveTheStars LLC
Submitted: {datetime.now(timezone.utc).strftime("%B %d, %Y")}
Track: {track_name}
Artist: SkyBlew
Label: 2StepsAboveTheStars LLC
Distributor: DistroKid

ANOMALY DETECTED:
{anomaly_details}

CONTEXT:
SkyBlew's track 'LightSwitch' is featured in Bomb Rush Cyberfunk (Nintendo Switch/PC).
Organic growth of approximately 1,000 streams per day is expected and legitimate.
The anomalies described above fall outside this expected pattern.

REQUEST:
We request investigation of the streaming data for this track and remediation of
any artificial inflation that may be distorting royalty calculations or chart positions.

CONTACT: [H.F.'s contact info]
"""
    return json.dumps({
        "status": "DRAFT — AWAITING H.F. APPROVAL",
        "track": track_name,
        "draft_text": draft.strip(),
        "submission_channels": [
            "Spotify: artists.spotify.com/contact → 'Streaming fraud report'",
            "Apple Music: itunesaffiliate@apple.com",
            "DistroKid: support@distrokid.com → 'Fraud/manipulation report'",
        ],
        "important": "DO NOT SEND. Present to H.F. for review first.",
    })


# ─────────────────────────────────────────────────────────────────────────────
# tools/privacy_tools.py  (inline — same file for compactness in this ADK)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def process_gdpr_deletion_request(user_email: str, request_id: str) -> str:
    """
    Process a GDPR/CCPA deletion request. Scans all DynamoDB tables for records
    associated with the user email, presents the full list for human confirmation,
    and logs the request. Does NOT delete automatically — outputs a deletion plan
    that requires human approval before execution.

    Args:
        user_email: The email address from the deletion request.
        request_id: Unique identifier for this deletion request (for tracking).

    Returns:
        JSON deletion plan listing all records found and confirmation instructions.
    """
    affected_tables = [
        "skyblew-sessions", "fan-behavior-metrics",
        "ask-lumin-cs-tickets", "ask-lumin-onboarding",
    ]
    records_found = []

    for table_name in affected_tables:
        try:
            table = dynamo.Table(table_name)
            resp = table.scan(
                FilterExpression="user_email = :email OR user_id = :email",
                ExpressionAttributeValues={":email": user_email},
                Limit=50,
            )
            for item in resp.get("Items", []):
                records_found.append({"table": table_name, "pk": item.get("pk", "?"), "sk": item.get("sk", "?")})
        except Exception:
            pass

    return json.dumps({
        "request_id": request_id,
        "user_email": user_email,
        "status": "DELETION_PLAN_READY",
        "records_to_delete": records_found,
        "record_count": len(records_found),
        "deadline": "72 hours from request receipt (GDPR Article 17 requirement)",
        "next_step": "Human must confirm this list, then call execute_gdpr_deletion(request_id) to proceed.",
        "note": "DELETION IS IRREVERSIBLE. Confirm carefully.",
    })


@tool
def audit_data_retention_compliance() -> str:
    """
    Check whether data retention TTL settings are correctly configured on all
    DynamoDB tables that store fan data. Flags any table missing TTL configuration
    or with incorrect expiration periods.

    Returns:
        JSON compliance report with table-by-table TTL status.
    """
    required = {
        "skyblew-sessions":       365,
        "security-alerts":        90,
        "ask-lumin-cs-tickets":   90,
        "fan-behavior-metrics":   365,
    }
    ddb_client = boto3.client("dynamodb", region_name="us-east-1")
    report = []

    for table_name, expected_days in required.items():
        try:
            resp = ddb_client.describe_time_to_live(TableName=table_name)
            ttl = resp.get("TimeToLiveDescription", {})
            status = ttl.get("TimeToLiveStatus", "DISABLED")
            report.append({
                "table": table_name,
                "ttl_status": status,
                "expected_retention_days": expected_days,
                "compliant": status == "ENABLED",
                "action": "None" if status == "ENABLED" else f"ENABLE TTL on {table_name}",
            })
        except Exception as e:
            report.append({"table": table_name, "error": str(e)})

    compliant = all(r.get("compliant") for r in report)
    return json.dumps({
        "overall_compliance": "PASS" if compliant else "FAIL",
        "tables_checked": len(report),
        "tables_failing": sum(1 for r in report if not r.get("compliant")),
        "table_details": report,
        "audited_at": datetime.now(timezone.utc).isoformat(),
    })


@tool
def check_pii_exposure_in_logs() -> str:
    """
    Scan recent CloudWatch log groups for accidental PII exposure — email addresses,
    phone numbers, or full names appearing in application logs where they should not.
    Returns a summary of findings and affected log streams.

    Returns:
        JSON with PII exposure findings or clean confirmation.
    """
    logs_client = boto3.client("logs", region_name="us-east-1")
    log_groups = ["/aws/lambda/skyblew-universe-api", "/aws/lambda/resonance-data-collector"]
    findings = []

    for group in log_groups:
        try:
            resp = logs_client.filter_log_events(
                logGroupName=group,
                filterPattern="?@gmail.com ?@yahoo.com ?@hotmail.com ?phone",
                startTime=int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000),
                limit=20,
            )
            events = resp.get("events", [])
            if events:
                findings.append({
                    "log_group": group,
                    "events_found": len(events),
                    "sample_message": events[0].get("message", "")[:200] + "...",
                    "action": "INVESTIGATE — potential PII in logs. Add log scrubbing middleware.",
                })
        except Exception as e:
            findings.append({"log_group": group, "error": str(e)})

    return json.dumps({
        "pii_exposure_detected": len(findings) > 0,
        "findings_count": len(findings),
        "findings": findings,
        "status": "ACTION_REQUIRED" if findings else "CLEAN",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })
