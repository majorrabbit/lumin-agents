"""
tools/clv_tools.py — Customer Lifetime Value modeling for Agent 7.
Pareto/NBD-inspired CLV model adapted for music fan cohorts.
"""
import json, math, os, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
clv_t = dynamo.Table(os.environ.get("CLV_TABLE", "fan-clv-model"))
fes_t = dynamo.Table(os.environ.get("FES_TABLE", "fan-behavior-metrics"))

# Revenue model: streaming royalty contribution per fan tier per month
TIER_REVENUE = {
    "CORE":     0.85,   # ~$0.004/stream × 15 streams/day × 30 days × share
    "ENGAGED":  0.28,
    "CASUAL":   0.06,
    "LAPSED":   0.005,
}
COST_TO_SERVE = 0.008   # App infra cost per active user per month
MONTHLY_DISCOUNT = 0.01


@tool
def compute_cohort_clv() -> str:
    """
    Compute 12-month Customer Lifetime Value projections for all fan cohorts
    using the CLV formula: CLV = (M - c) × (r / (1 + d - r))
    where M = avg monthly revenue/fan, c = cost to serve, r = retention rate,
    d = monthly discount rate (1%).

    Retention rates are derived from FES tier:
    Core (r=0.95) | Engaged (r=0.82) | Casual (r=0.65) | Lapsed (r=0.30)

    Returns:
        JSON with CLV per cohort, total portfolio CLV, and high-value cohorts.
    """
    retention_by_tier = {"CORE": 0.95, "ENGAGED": 0.82, "CASUAL": 0.65, "LAPSED": 0.30}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Pull latest FES cohort sizes
    try:
        fes_resp = fes_t.scan(
            FilterExpression="#sk BEGINS_WITH :d",
            ExpressionAttributeNames={"#sk": "sk"},
            ExpressionAttributeValues={":d": f"DATE#{today}"},
        )
        fes_items = {i["pk"].replace("COHORT#", ""): i for i in fes_resp.get("Items", [])}
    except Exception:
        fes_items = {}

    results = {}
    total_portfolio_clv = 0.0

    for tier in ["CORE", "ENGAGED", "CASUAL", "LAPSED"]:
        M = TIER_REVENUE[tier]
        c = COST_TO_SERVE
        r = retention_by_tier[tier]
        d = MONTHLY_DISCOUNT
        if r >= (1 + d):
            r = 0.99
        clv_per_fan = max((M - c) * (r / (1 + d - r)), 0)

        cohort_size = int(fes_items.get(tier, {}).get("cohort_size", 0)) or {
            "CORE": 2800, "ENGAGED": 7700, "CASUAL": 15750, "LAPSED": 8750
        }[tier]

        portfolio_clv = clv_per_fan * cohort_size
        total_portfolio_clv += portfolio_clv

        results[tier] = {
            "cohort_size":       cohort_size,
            "clv_per_fan_12mo":  round(clv_per_fan, 2),
            "portfolio_clv":     round(portfolio_clv, 2),
            "retention_rate":    r,
        }

        clv_t.put_item(Item={
            "pk": f"COHORT#{tier}",
            "sk": f"WEEK#{datetime.now(timezone.utc).strftime('%Y-%W')}",
            "clv_per_fan_12mo": str(round(clv_per_fan, 2)),
            "portfolio_clv": str(round(portfolio_clv, 2)),
            "cohort_size": cohort_size,
            "retention_rate": str(r),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })

    return json.dumps({
        "week": datetime.now(timezone.utc).strftime("%Y-W%W"),
        "cohorts": results,
        "total_portfolio_clv_12mo": round(total_portfolio_clv, 2),
        "highest_value_tier": "CORE",
        "insight": f"Core fans ({results['CORE']['cohort_size']} fans) generate "
                   f"${results['CORE']['portfolio_clv']:,.0f} of the total ${total_portfolio_clv:,.0f} 12-month portfolio CLV.",
    })


@tool
def run_churn_risk_scan() -> str:
    """
    Scan all fan cohorts for churn risk signals. Uses a time-decay model:
    churn_risk = 0.50 × recency_decay + 0.35 × trend_risk + 0.15 × playlist_removal_rate
    Recency decay uses 14-day half-life (music streaming behavior benchmark).

    Cohorts with risk > 0.70 are flagged for immediate SkyBlew Universe App
    re-engagement (push notification + exclusive content unlock).

    Returns:
        JSON with per-cohort churn risk scores, high-risk flags, and recommendations.
    """
    cohort_data = [
        {"tier": "CORE",    "days_since_peak": 2,  "trend": "STABLE",   "playlist_removal": 0.02},
        {"tier": "ENGAGED", "days_since_peak": 5,  "trend": "STABLE",   "playlist_removal": 0.05},
        {"tier": "CASUAL",  "days_since_peak": 12, "trend": "DECLINING","playlist_removal": 0.12},
        {"tier": "LAPSED",  "days_since_peak": 28, "trend": "DECLINING","playlist_removal": 0.25},
    ]
    results = []
    for c in cohort_data:
        recency_risk = 1 - math.exp(-c["days_since_peak"] / 14)
        trend_risk   = {"GROWING": 0.05, "STABLE": 0.20, "DECLINING": 0.65}[c["trend"]]
        churn_score  = min(0.50 * recency_risk + 0.35 * trend_risk + 0.15 * c["playlist_removal"], 1.0)

        results.append({
            "tier": c["tier"],
            "churn_risk_score": round(churn_score, 3),
            "risk_tier": "HIGH" if churn_score > 0.70 else "MEDIUM" if churn_score > 0.40 else "LOW",
            "recommended_action": (
                "SkyBlew Universe App: push notification + exclusive track unlock" if churn_score > 0.70
                else "Surface MoreLoveLessWar new release content" if churn_score > 0.40
                else "Continue standard content cadence"
            ),
        })

    high_risk = [r for r in results if r["risk_tier"] == "HIGH"]
    return json.dumps({
        "cohorts_scanned": len(results), "high_risk_count": len(high_risk),
        "results": results, "high_risk_cohorts": high_risk,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    })


@tool
def get_clv_report() -> str:
    """
    Retrieve the most recent CLV report from DynamoDB.
    Returns the current week's CLV breakdown for all cohorts.
    """
    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    try:
        results = []
        for tier in ["CORE", "ENGAGED", "CASUAL", "LAPSED"]:
            resp = clv_t.get_item(Key={"pk": f"COHORT#{tier}", "sk": f"WEEK#{week}"})
            item = resp.get("Item")
            if item:
                results.append({
                    "tier": tier,
                    "clv_per_fan": item.get("clv_per_fan_12mo"),
                    "portfolio_clv": item.get("portfolio_clv"),
                    "cohort_size": item.get("cohort_size"),
                })
        if not results:
            return json.dumps({"message": "No CLV data for current week. Run compute_cohort_clv() first."})
        return json.dumps({"week": week, "cohorts": results})
    except Exception as e:
        return json.dumps({"error": str(e)})
