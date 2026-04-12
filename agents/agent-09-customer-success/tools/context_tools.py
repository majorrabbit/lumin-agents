"""
tools/context_tools.py — User context enrichment for Agent 9.
Pulls Stripe subscription data + AskLumin session history + churn signals
and compiles a complete user profile before every CS interaction.
"""
import json, os, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
sessions_t = dynamo.Table(os.environ.get("SESSIONS_TABLE", "ask-lumin-sessions"))
cs_t       = dynamo.Table(os.environ.get("CS_TABLE", "ask-lumin-cs-tickets"))

ALL_FEATURES = [
    "Deep Research Mode", "Sync Brief Scanner", "Resonance Dashboard",
    "Artist Trajectory Reports", "Sync Pitch Generator", "Export to PDF",
    "API Access", "Team Collaboration", "Custom Data Upload",
]


@tool
def enrich_user_context(user_id: str) -> str:
    """
    Build a complete context profile for a specific AskLumin subscriber.
    Pulls subscription tier from Stripe metadata in DynamoDB, usage history
    from session records, computes engagement trend and churn risk signals,
    and identifies which features the user has and has not activated.
    Use this before every subscriber-specific interaction.

    Args:
        user_id: The AskLumin user identifier.

    Returns:
        JSON profile with tier, account_age_days, last_active, features_used,
        features_not_used, usage_trend, open_tickets, and churn_risk.
    """
    try:
        # Pull session history (last 90 days)
        resp = sessions_t.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
            Limit=90,
        )
        sessions = resp.get("Items", [])

        if not sessions:
            return json.dumps({
                "user_id": user_id, "tier": "Unknown", "account_age_days": 0,
                "last_active": "Never", "features_used": [], "features_not_used": ALL_FEATURES,
                "usage_trend": "NEW", "open_tickets": 0, "churn_risk": "UNKNOWN",
                "note": "No session history found for this user_id.",
            })

        # Compute engagement metrics
        last_active = sessions[0].get("created_at", "Unknown")
        tier = sessions[0].get("tier", "Spark")

        first_session_ts = sessions[-1].get("created_at", datetime.now(timezone.utc).isoformat())
        try:
            account_age_days = (datetime.now(timezone.utc) -
                                datetime.fromisoformat(first_session_ts.replace("Z", "+00:00"))
                                ).days
        except Exception:
            account_age_days = 0

        # Features activated: any feature_used field in session records
        features_used = list({
            f for s in sessions
            for f in s.get("features_used", [])
        })
        features_not_used = [f for f in ALL_FEATURES if f not in features_used]

        # Usage trend: compare last 7 days vs prior 7 days
        now_ts = datetime.now(timezone.utc)
        recent_count = sum(
            1 for s in sessions
            if _days_ago(s.get("created_at", ""), now_ts) <= 7
        )
        prior_count = sum(
            1 for s in sessions
            if 7 < _days_ago(s.get("created_at", ""), now_ts) <= 14
        )
        if recent_count == 0 and account_age_days > 7:
            trend = "DECLINING"
        elif recent_count > prior_count * 1.2:
            trend = "GROWING"
        elif recent_count < prior_count * 0.8:
            trend = "DECLINING"
        elif account_age_days <= 7:
            trend = "NEW"
        else:
            trend = "STABLE"

        # Open tickets
        ticket_resp = cs_t.query(
            KeyConditionExpression="user_id = :uid",
            FilterExpression="#s = :open",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":uid": user_id, ":open": "OPEN"},
        )
        open_tickets = len(ticket_resp.get("Items", []))

        # Simple churn risk heuristic
        days_since_last = _days_ago(last_active, now_ts)
        churn_risk = (
            "HIGH"   if trend == "DECLINING" and days_since_last > 10 else
            "MEDIUM" if trend == "DECLINING" or days_since_last > 7 else
            "LOW"
        )

        return json.dumps({
            "user_id":            user_id,
            "tier":               tier,
            "account_age_days":   account_age_days,
            "last_active":        last_active,
            "features_used":      features_used,
            "features_not_used":  features_not_used,
            "usage_trend":        trend,
            "open_tickets":       open_tickets,
            "churn_risk":         churn_risk,
            "session_count_7d":   recent_count,
            "session_count_14d":  prior_count,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "user_id": user_id})


def _days_ago(ts_str: str, now: datetime) -> int:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (now - ts).days
    except Exception:
        return 999


@tool
def get_subscription_details(user_id: str) -> str:
    """
    Retrieve full subscription details for a user including tier, billing cycle,
    monthly query usage vs. limit, and any usage overage flags.

    Args:
        user_id: AskLumin user identifier.

    Returns:
        JSON with tier, billing_cycle, queries_used, query_limit, overage_flag.
    """
    TIER_LIMITS = {"Spark": 50, "Resonance Pro": 500, "Luminary Enterprise": 999999}
    try:
        resp = sessions_t.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False, Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return json.dumps({"error": "User not found"})

        tier = items[0].get("tier", "Spark")
        limit = TIER_LIMITS.get(tier, 50)

        # Count queries this billing month
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0).isoformat()
        month_resp = sessions_t.query(
            KeyConditionExpression="user_id = :uid",
            FilterExpression="created_at >= :ms",
            ExpressionAttributeValues={":uid": user_id, ":ms": month_start},
        )
        queries_used = len(month_resp.get("Items", []))

        return json.dumps({
            "user_id": user_id, "tier": tier,
            "query_limit_monthly": limit,
            "queries_used_this_month": queries_used,
            "queries_remaining": max(0, limit - queries_used),
            "overage_flag": queries_used > limit * 0.90,
            "upgrade_nudge": tier == "Spark" and queries_used > 40,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_feature_usage_summary(user_id: str) -> str:
    """
    Return a structured summary of which AskLumin features a specific user has
    and has not discovered, with a recommended 'next feature to surface' based
    on their role and past usage patterns.

    Args:
        user_id: AskLumin user identifier.

    Returns:
        JSON with used_features list, unused_features list, and top_recommendation.
    """
    ctx = json.loads(enrich_user_context(user_id=user_id))
    used = ctx.get("features_used", [])
    unused = ctx.get("features_not_used", ALL_FEATURES)
    tier = ctx.get("tier", "Spark")

    # Recommend the most impactful unused feature for their tier
    tier_priority = {
        "Spark":            ["Deep Research Mode", "Sync Brief Scanner"],
        "Resonance Pro":    ["Sync Brief Scanner", "Artist Trajectory Reports", "Sync Pitch Generator"],
        "Luminary Enterprise": ["API Access", "Custom Data Upload", "Team Collaboration"],
    }
    priority_list = tier_priority.get(tier, [])
    recommendation = next((f for f in priority_list if f in unused), unused[0] if unused else None)

    return json.dumps({
        "user_id": user_id, "tier": tier,
        "features_activated": used,
        "features_not_activated": unused,
        "activation_rate_pct": round(len(used) / len(ALL_FEATURES) * 100, 1),
        "top_recommendation": recommendation,
        "recommendation_rationale": f"'{recommendation}' is the highest-value unactivated feature for {tier} users based on usage patterns." if recommendation else "All features activated — focus on depth of use.",
    })
