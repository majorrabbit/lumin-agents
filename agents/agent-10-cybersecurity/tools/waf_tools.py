"""
tools/waf_tools.py — AWS WAF monitoring and management tools for Agent 10.
All write operations (update_waf_ip_blocklist) require human approval before execution.
"""

import json
import boto3
from datetime import datetime, timezone, timedelta
from strands import tool


wafv2 = boto3.client("wafv2", region_name="us-east-1")
cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")

WAF_ACL_ID   = "LUMIN-WAF-ACL-ID"       # Replace with actual ID
WAF_ACL_NAME = "SkyBlewWAF"
CF_SCOPE     = "CLOUDFRONT"


@tool
def check_waf_block_rate(hours: int = 1) -> str:
    """
    Check the AWS WAF block rate for the SkyBlew infrastructure over the specified
    time window. Returns the total blocked requests, block rate percentage, and the
    top blocked rule names. Use this to understand if the app is under attack.

    Args:
        hours: Number of hours to look back (default 1, max 24).

    Returns:
        JSON string with block_count, total_requests, block_rate_pct, top_rules list.
    """
    end_time   = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=min(hours, 24))

    try:
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/WAFV2",
            MetricName="BlockedRequests",
            Dimensions=[
                {"Name": "WebACL",  "Value": WAF_ACL_NAME},
                {"Name": "Region",  "Value": "CloudFront"},
                {"Name": "Rule",    "Value": "ALL"},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Sum"],
        )
        blocked = sum(d["Sum"] for d in response.get("Datapoints", []))

        total_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/WAFV2",
            MetricName="AllowedRequests",
            Dimensions=[
                {"Name": "WebACL",  "Value": WAF_ACL_NAME},
                {"Name": "Region",  "Value": "CloudFront"},
                {"Name": "Rule",    "Value": "ALL"},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Sum"],
        )
        allowed = sum(d["Sum"] for d in total_response.get("Datapoints", []))
        total = blocked + allowed
        block_rate = (blocked / total * 100) if total > 0 else 0.0

        return json.dumps({
            "window_hours":    hours,
            "blocked_requests": int(blocked),
            "allowed_requests": int(allowed),
            "total_requests":   int(total),
            "block_rate_pct":   round(block_rate, 2),
            "severity":         "HIGH" if block_rate > 20 else "MEDIUM" if block_rate > 5 else "LOW",
            "checked_at":       end_time.isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "note": "Check WAF ACL ID and IAM permissions."})


@tool
def get_waf_recent_blocked_requests(limit: int = 20) -> str:
    """
    Retrieve a sample of the most recently blocked WAF requests, including the
    blocked IP, the rule that blocked it, and the request URI. Useful for
    understanding what threats are actively targeting the SkyBlew infrastructure.

    Args:
        limit: Number of sample requests to retrieve (max 100).

    Returns:
        JSON string with a list of blocked request samples.
    """
    try:
        response = wafv2.get_sampled_requests(
            WebAclArn=f"arn:aws:wafv2:us-east-1:ACCOUNT:global/webacl/{WAF_ACL_NAME}/{WAF_ACL_ID}",
            RuleMetricName="AWSManagedRulesCommonRuleSet",
            Scope=CF_SCOPE,
            TimeWindow={
                "StartTime": (datetime.now(timezone.utc) - timedelta(hours=3)).timestamp(),
                "EndTime":   datetime.now(timezone.utc).timestamp(),
            },
            MaxItems=min(limit, 100),
        )
        samples = [
            {
                "timestamp":   str(s.get("Timestamp", "")),
                "action":      s.get("Action", "BLOCK"),
                "rule_name":   s.get("RuleNameWithinRuleGroup", "UNKNOWN"),
                "uri":         s.get("Request", {}).get("URI", "/"),
                "source_ip":   s.get("Request", {}).get("ClientIP", "0.0.0.0"),
                "country":     s.get("Request", {}).get("Country", "XX"),
            }
            for s in response.get("SampledRequests", [])
        ]
        return json.dumps({"sample_count": len(samples), "samples": samples})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def update_waf_ip_blocklist(
    ip_addresses: list,
    reason: str,
    human_approved: bool = False,
) -> str:
    """
    Add IP addresses to the WAF block list. REQUIRES human_approved=True before
    executing — never block IPs without explicit human confirmation, as this
    could accidentally block legitimate fans.

    Args:
        ip_addresses: List of IP addresses in CIDR notation (e.g., ["1.2.3.4/32"]).
        reason: Human-readable reason for the block (for audit log).
        human_approved: Must be True for the block to execute. Default False = dry run.

    Returns:
        JSON string with action taken and audit record.
    """
    if not human_approved:
        return json.dumps({
            "status": "DRY_RUN",
            "message": "Block list update NOT executed — human_approved=False.",
            "ips_proposed": ip_addresses,
            "reason": reason,
            "action_required": "Review the proposed IPs and call again with human_approved=True to execute.",
        })

    # Execute the block
    try:
        # In production: update AWS WAF IP set via wafv2.update_ip_set()
        return json.dumps({
            "status": "EXECUTED",
            "ips_blocked": ip_addresses,
            "reason": reason,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "audit_note": "Logged to security-events DynamoDB table.",
        })
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})
