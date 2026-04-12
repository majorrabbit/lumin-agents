"""
tools/onboarding_tools.py — 7-day onboarding sequence for Agent 9.
Proactive, context-aware touchpoints at Days 0,1,3,5,7,30.
"""
import json, os, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
onboard_t = dynamo.Table(os.environ.get("ONBOARDING_TABLE", "ask-lumin-onboarding"))
sessions_t = dynamo.Table(os.environ.get("SESSIONS_TABLE", "ask-lumin-sessions"))
ses = boto3.client("ses", region_name="us-east-1")

TOUCHPOINT_SUBJECTS = {
    0:  "Welcome to AskLumin — your first 3 moves",
    1:  "Have you tried AskLumin yet? Here's your fastest path to value",
    3:  "One feature you haven't discovered yet (it changes everything)",
    5:  "Quick check-in from AskLumin — how's it going?",
    7:  "You've been with AskLumin for a week — here's what's next",
    30: "Your first month with AskLumin — a look back and forward",
}

FROM_EMAIL = os.environ.get("FROM_EMAIL", "hello@lumin.luxe")


@tool
def get_users_needing_touchpoint() -> str:
    """
    Scan the onboarding table and return all users who are due for a
    Day 0, 1, 3, 5, 7, or 30 touchpoint today. Considers account age
    and which touchpoints have already been sent.

    Returns:
        JSON list of users needing touchpoints, grouped by day number.
    """
    now = datetime.now(timezone.utc)
    try:
        resp = onboard_t.scan(Limit=500)
        due = {}
        for item in resp.get("Items", []):
            signup_ts = item.get("signup_at", "")
            if not signup_ts:
                continue
            try:
                signup_dt = datetime.fromisoformat(signup_ts.replace("Z", "+00:00"))
                age_days = (now - signup_dt).days
            except Exception:
                continue

            for day in [0, 1, 3, 5, 7, 30]:
                if age_days == day and not item.get(f"day_{day}_sent", False):
                    due.setdefault(day, []).append({
                        "user_id":    item.get("user_id"),
                        "email":      item.get("email"),
                        "tier":       item.get("tier", "Spark"),
                        "day":        day,
                        "features_not_used": item.get("features_not_used", []),
                    })

        total = sum(len(v) for v in due.values())
        return json.dumps({"total_due": total, "by_day": due})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def send_onboarding_touchpoint(
    user_id: str, email: str, day: int, tier: str,
    featured_feature: str = None
) -> str:
    """
    Send the appropriate onboarding email for a specific day milestone.
    Email content adapts to the user's tier and any featured feature to surface.
    All emails are sent via AWS SES from hello@lumin.luxe.

    Args:
        user_id:          AskLumin user ID.
        email:            User's email address.
        day:              Touchpoint day (0, 1, 3, 5, 7, or 30).
        tier:             Subscription tier for personalized content.
        featured_feature: Specific feature to highlight (optional, Day 3 focus).

    Returns:
        JSON with send status and touchpoint details.
    """
    subject = TOUCHPOINT_SUBJECTS.get(day, f"Day {day} check-in from AskLumin")

    body_templates = {
        0: f"Welcome to AskLumin! Here are your first 3 moves:\n\n1. Run your first research query — ask about any artist, label, or market trend\n2. Try the Resonance Dashboard to see streaming analytics in action\n3. Explore the Sync Brief Scanner (available in Resonance Pro)\n\nYour {tier} plan is active. Start exploring at ask.lumin.luxe\n\n— The AskLumin Team",
        1: f"You signed up yesterday — have you run your first query? Ask AskLumin anything about the music industry. Start with: 'What is the current streaming momentum for [artist you care about]?' — The AskLumin Team",
        3: f"There's a feature on your {tier} plan you haven't tried yet: {featured_feature or 'Deep Research Mode'}. It lets you go deeper than standard queries — pulling cross-platform intelligence in a single ask. Try it at ask.lumin.luxe — The AskLumin Team",
        5: "Quick check-in: are you getting what you expected from AskLumin? Reply to this email and I'll make sure you're on the right track. — The AskLumin Team",
        7: f"One week with AskLumin! Based on your {tier} plan, here's what we recommend focusing on next: deeper use of the Resonance Engine for artist trajectory analysis. Ask: 'Show me the 90-day attention curve for [artist].' — The AskLumin Team",
        30: f"Your first month with AskLumin. Here's a quick recap of what you've been exploring, and what's waiting for you in month 2. The Resonance Engine tracks 16M+ artists — you've only scratched the surface. — The AskLumin Team",
    }

    body = body_templates.get(day, f"Day {day} check-in from AskLumin — ask.lumin.luxe")

    try:
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        mark_touchpoint_completed(user_id=user_id, day=day)
        return json.dumps({"status": "SENT", "user_id": user_id, "day": day, "email": email})
    except Exception as e:
        return json.dumps({"status": "FAILED", "error": str(e), "user_id": user_id, "day": day})


@tool
def mark_touchpoint_completed(user_id: str, day: int) -> str:
    """
    Mark a specific onboarding touchpoint as sent in DynamoDB so it
    is not re-sent on subsequent runs.

    Args:
        user_id: AskLumin user ID.
        day:     Touchpoint day number.

    Returns:
        JSON confirmation.
    """
    try:
        onboard_t.update_item(
            Key={"user_id": user_id},
            UpdateExpression=f"SET day_{day}_sent = :t, day_{day}_sent_at = :ts",
            ExpressionAttributeValues={
                ":t": True,
                ":ts": datetime.now(timezone.utc).isoformat(),
            },
        )
        return json.dumps({"status": "MARKED", "user_id": user_id, "day": day})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_onboarding_status(user_id: str) -> str:
    """
    Return the full onboarding progress for a specific user: which touchpoints
    have been sent, which are pending, and what percentage of the onboarding
    sequence is complete.

    Args:
        user_id: AskLumin user ID.

    Returns:
        JSON onboarding status with sent/pending touchpoints and completion pct.
    """
    try:
        resp = onboard_t.get_item(Key={"user_id": user_id})
        item = resp.get("Item", {})
        sent = [d for d in [0,1,3,5,7,30] if item.get(f"day_{d}_sent", False)]
        pending = [d for d in [0,1,3,5,7,30] if not item.get(f"day_{d}_sent", False)]
        return json.dumps({
            "user_id": user_id,
            "touchpoints_sent": sent,
            "touchpoints_pending": pending,
            "completion_pct": round(len(sent) / 6 * 100, 1),
            "signup_at": item.get("signup_at"),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── support_tools.py ─────────────────────────────────────────────────────────

cs_tickets_t = dynamo.Table(os.environ.get("CS_TICKETS_TABLE", "ask-lumin-cs-tickets"))
cs_metrics_t = dynamo.Table(os.environ.get("CS_METRICS_TABLE", "ask-lumin-cs-metrics"))
sns = boto3.client("sns", region_name="us-east-1")
ESCALATION_TOPIC = os.environ.get("SNS_ESCALATION_TOPIC", "")
SLACK_CS_WEBHOOK = os.environ.get("SLACK_CS_WEBHOOK", "")


@tool
def create_support_ticket(
    user_id: str, user_email: str, trigger: str,
    summary: str, urgency: str = "NORMAL"
) -> str:
    """
    Create a support ticket in DynamoDB for tracking a subscriber issue.
    Used for escalations, billing disputes, and any issue requiring follow-up.

    Args:
        user_id:    AskLumin user ID.
        user_email: User's email address.
        trigger:    What triggered this ticket (e.g., BILLING_DISPUTE, BUG_REPORT).
        summary:    Plain-English summary of the issue.
        urgency:    NORMAL / HIGH / CRITICAL (affects SLA: 24h / 4h / 1h).

    Returns:
        JSON with ticket_id, status, and SLA commitment.
    """
    ts = datetime.now(timezone.utc).isoformat()
    ticket_id = f"TICKET#{user_id}#{ts[:10]}#{trigger[:8]}"
    sla = {"NORMAL": "24 hours", "HIGH": "4 hours", "CRITICAL": "1 hour"}.get(urgency, "24 hours")

    try:
        cs_tickets_t.put_item(Item={
            "pk": ticket_id, "sk": ts,
            "user_id": user_id, "user_email": user_email,
            "trigger": trigger, "summary": summary,
            "urgency": urgency, "status": "OPEN",
            "sla_commitment": sla, "created_at": ts,
            "resolved_at": None, "resolution_notes": None,
        })
        return json.dumps({
            "ticket_id": ticket_id, "status": "OPEN",
            "sla_commitment": sla, "urgency": urgency,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def escalate_to_human(
    user_id: str, user_email: str, trigger: str,
    conversation_summary: str, urgency: str = "NORMAL"
) -> str:
    """
    Escalate a subscriber issue to the human CS team. Creates a ticket,
    posts a rich Slack alert to #cs-escalations with full context, and
    sends the user a confirmation email. Always call this when a situation
    exceeds the agent's decision authority.

    Args:
        user_id:               User ID.
        user_email:            User email.
        trigger:               Trigger type (BILLING_DISPUTE / BUG_REPORT / FRUSTRATED_USER / etc.).
        conversation_summary:  Concise summary of the issue for the human reviewer.
        urgency:               NORMAL / HIGH / CRITICAL.

    Returns:
        JSON with ticket_id and escalation confirmation.
    """
    ticket = json.loads(create_support_ticket(
        user_id=user_id, user_email=user_email,
        trigger=trigger, summary=conversation_summary, urgency=urgency,
    ))
    ticket_id = ticket.get("ticket_id", "UNKNOWN")

    # Slack alert to #cs-escalations
    import requests
    if SLACK_CS_WEBHOOK:
        msg = {
            "text": f"🆘 CS Escalation — {urgency}",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"🆘 CS Escalation — {urgency}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*User:*\n{user_email}"},
                    {"type": "mrkdwn", "text": f"*Trigger:*\n{trigger}"},
                    {"type": "mrkdwn", "text": f"*SLA:*\n{ticket.get('sla_commitment')}"},
                    {"type": "mrkdwn", "text": f"*Ticket:*\n`{ticket_id}`"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Issue Summary:*\n{conversation_summary}"}},
            ],
        }
        try:
            requests.post(SLACK_CS_WEBHOOK, json=msg, timeout=5)
        except Exception:
            pass

    return json.dumps({
        "status": "ESCALATED", "ticket_id": ticket_id,
        "message_to_user": f"I'm connecting you with our team. They'll follow up within {ticket.get('sla_commitment')}. I've shared your full context so you won't need to repeat anything.",
    })


@tool
def update_ticket_status(
    ticket_id: str, new_status: str, resolution_notes: str = ""
) -> str:
    """
    Update a support ticket's status and add resolution notes.
    Valid statuses: OPEN / IN_PROGRESS / RESOLVED / CLOSED.

    Args:
        ticket_id:        The ticket primary key.
        new_status:       New status string.
        resolution_notes: What was done to resolve the issue.

    Returns:
        JSON with updated status.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        cs_tickets_t.update_item(
            Key={"pk": ticket_id, "sk": ts},
            UpdateExpression="SET #s = :s, resolution_notes = :r, resolved_at = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": new_status, ":r": resolution_notes, ":ts": ts},
        )
        return json.dumps({"ticket_id": ticket_id, "new_status": new_status})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_open_tickets(tier_filter: str = None) -> str:
    """
    Retrieve all currently open support tickets, optionally filtered by tier.

    Args:
        tier_filter: Optional tier to filter by (Spark / Resonance Pro / Luminary Enterprise).

    Returns:
        JSON list of open tickets sorted by urgency and creation date.
    """
    try:
        resp = cs_tickets_t.scan(
            FilterExpression="#s = :open",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":open": "OPEN"},
        )
        tickets = resp.get("Items", [])
        if tier_filter:
            tickets = [t for t in tickets if t.get("tier") == tier_filter]
        # Sort: CRITICAL first, then HIGH, then NORMAL
        priority = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2}
        tickets.sort(key=lambda t: priority.get(t.get("urgency", "NORMAL"), 2))
        return json.dumps({"open_count": len(tickets), "tickets": tickets[:20]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def log_cs_interaction(
    user_id: str, session_id: str,
    resolved_by_agent: bool, sentiment_score: float,
    topic: str, notes: str = ""
) -> str:
    """
    Log a completed CS interaction to the metrics table for deflection rate
    tracking and training corpus generation. Every conversation should end
    with this call.

    Args:
        user_id:             User ID.
        session_id:          Session identifier.
        resolved_by_agent:   True if the agent handled it without escalation.
        sentiment_score:     Estimated sentiment 0.0 (negative) to 1.0 (positive).
        topic:               Category (onboarding / feature_help / billing / bug / churn).
        notes:               Any notes for training corpus review.

    Returns:
        JSON confirmation with interaction ID.
    """
    ts = datetime.now(timezone.utc).isoformat()
    interaction_id = f"INT#{session_id}#{ts[:13]}"
    try:
        cs_metrics_t.put_item(Item={
            "pk": interaction_id, "sk": ts,
            "user_id": user_id, "session_id": session_id,
            "resolved_by_agent": resolved_by_agent,
            "sentiment_score": str(sentiment_score),
            "topic": topic, "notes": notes,
            "date": ts[:10],
        })
        return json.dumps({"status": "LOGGED", "interaction_id": interaction_id,
                           "deflection_credit": resolved_by_agent})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── retention_tools.py ───────────────────────────────────────────────────────

nps_t = dynamo.Table(os.environ.get("NPS_TABLE", "ask-lumin-nps"))
SES = boto3.client("ses", region_name="us-east-1")


@tool
def compute_churn_risk(user_id: str) -> str:
    """
    Compute a churn risk score (0.0-1.0) for a specific subscriber based on
    recency decay, usage trend, and session frequency. Returns the risk tier
    and the recommended intervention action.

    Args:
        user_id: AskLumin user ID.

    Returns:
        JSON with churn_risk_score, risk_tier, recommended_action.
    """
    import math
    ctx = json.loads(enrich_user_context(user_id=user_id))
    trend = ctx.get("usage_trend", "STABLE")
    sessions_7d  = ctx.get("session_count_7d", 0)
    sessions_14d = ctx.get("session_count_14d", 0)

    # Recency decay: exponential half-life of 14 days
    days_since = (datetime.now(timezone.utc) -
                  datetime.fromisoformat(
                      ctx.get("last_active", datetime.now(timezone.utc).isoformat())
                      .replace("Z", "+00:00")
                  )).days if ctx.get("last_active", "Unknown") != "Unknown" else 30
    recency_risk = 1 - math.exp(-days_since / 14)

    # Trend risk
    trend_risk = {"DECLINING": 0.60, "STABLE": 0.20, "GROWING": 0.05, "NEW": 0.10}.get(trend, 0.20)

    # Volume drop risk
    vol_drop = 0.0
    if sessions_14d > 0:
        vol_drop = max(0, (sessions_14d - sessions_7d) / sessions_14d * 0.30)

    score = min(0.40 * recency_risk + 0.40 * trend_risk + 0.20 * vol_drop, 1.0)

    if score > 0.70:
        tier_label = "HIGH"
        action = "IMMEDIATE: Trigger proactive re-engagement within 24 hours."
    elif score > 0.40:
        tier_label = "MEDIUM"
        action = "NEAR-TERM: Surface unused high-value feature this week."
    else:
        tier_label = "LOW"
        action = "MONITOR: Continue standard onboarding cadence."

    return json.dumps({
        "user_id": user_id, "churn_risk_score": round(score, 3),
        "risk_tier": tier_label, "recommended_action": action,
        "days_since_last_session": days_since, "usage_trend": trend,
    })


@tool
def trigger_reengagement(user_id: str, user_email: str, featured_feature: str) -> str:
    """
    Send a proactive re-engagement email to a declining or at-risk subscriber.
    The email surfaces one specific unused feature without mentioning their
    declining usage — it reads as a helpful tip, not an alarm bell.

    Args:
        user_id:          User ID.
        user_email:       User email address.
        featured_feature: The specific unused feature to highlight.

    Returns:
        JSON with send status.
    """
    subject = f"A quick note from AskLumin — have you tried {featured_feature}?"
    body = (
        f"Hi there,\n\n"
        f"Just wanted to share something that might be useful for you: "
        f"{featured_feature} is one of the most powerful tools on your AskLumin plan, "
        f"and a lot of users discover it's exactly what they needed after they try it.\n\n"
        f"If you have 5 minutes, here's how to use it: log into ask.lumin.luxe and try asking: "
        f"'Help me use {featured_feature} for [your specific music industry goal].'\n\n"
        f"If there's anything I can help you with, just reply to this email.\n\n"
        f"— The AskLumin Team"
    )
    try:
        SES.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [user_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        return json.dumps({"status": "SENT", "user_id": user_id, "feature_featured": featured_feature})
    except Exception as e:
        return json.dumps({"status": "FAILED", "error": str(e)})


@tool
def get_at_risk_subscribers() -> str:
    """
    Return all subscribers currently showing churn risk signals: usage_trend
    DECLINING and/or days_since_last_session > 5. Sorted by risk severity.
    Use this for the daily churn scan and weekly CS digest.

    Returns:
        JSON list of at-risk subscribers with their risk scores.
    """
    try:
        resp = onboard_t.scan(
            FilterExpression="usage_trend = :d OR days_inactive > :t",
            ExpressionAttributeValues={":d": "DECLINING", ":t": 5},
            Limit=200,
        )
        at_risk = []
        for item in resp.get("Items", []):
            uid = item.get("user_id", "")
            if uid:
                risk_raw = json.loads(compute_churn_risk(user_id=uid))
                at_risk.append({
                    "user_id": uid, "email": item.get("email", ""),
                    "tier": item.get("tier", "Spark"),
                    **risk_raw,
                })
        at_risk.sort(key=lambda x: x.get("churn_risk_score", 0), reverse=True)
        return json.dumps({"at_risk_count": len(at_risk), "subscribers": at_risk[:20]})
    except Exception as e:
        return json.dumps({"error": str(e), "note": "Scan may need GSI on usage_trend — see DEPLOY.md"})


@tool
def record_nps_response(user_id: str, score: int, comment: str = "") -> str:
    """
    Record an NPS survey response from a subscriber. NPS score 0-10.
    Scores 0-6 = detractor (triggers immediate CS review), 7-8 = passive,
    9-10 = promoter (candidate for testimonial request).

    Args:
        user_id: AskLumin user ID.
        score:   NPS score 0-10.
        comment: Optional verbatim comment.

    Returns:
        JSON with NPS classification and follow-up action.
    """
    classification = "DETRACTOR" if score <= 6 else "PASSIVE" if score <= 8 else "PROMOTER"
    ts = datetime.now(timezone.utc).isoformat()
    try:
        nps_t.put_item(Item={
            "pk": f"NPS#{user_id}", "sk": ts,
            "user_id": user_id, "score": score,
            "comment": comment, "classification": classification,
            "recorded_at": ts,
        })
        return json.dumps({
            "status": "RECORDED", "score": score,
            "classification": classification,
            "follow_up": (
                "URGENT: Review immediately — below average." if classification == "DETRACTOR"
                else "Consider testimonial request." if classification == "PROMOTER"
                else "Monitor — no immediate action."
            ),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── metrics_tools.py ─────────────────────────────────────────────────────────

@tool
def compute_daily_cs_metrics() -> str:
    """
    Compute today's Customer Success performance metrics: ticket deflection rate,
    average sentiment score, new tickets opened, and tickets resolved.
    Writes the daily record to ask-lumin-cs-metrics table.

    Returns:
        JSON with today's CS metrics snapshot.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = cs_metrics_t.query(
            KeyConditionExpression="pk BEGINS_WITH :pfx",
            ExpressionAttributeValues={":pfx": f"INT#"},
            FilterExpression="#d = :today",
            ExpressionAttributeNames={"#d": "date"},
            ExpressionAttributeValues={":pfx": "INT#", ":today": today},
        )
        interactions = resp.get("Items", [])
        total = len(interactions)
        deflected = sum(1 for i in interactions if i.get("resolved_by_agent", False))
        sentiments = [float(i.get("sentiment_score", 0.5)) for i in interactions]
        avg_sentiment = round(sum(sentiments)/len(sentiments), 3) if sentiments else 0.5

        metrics = {
            "date": today, "total_interactions": total,
            "deflected_by_agent": deflected,
            "deflection_rate_pct": round(deflected/total*100, 1) if total else 0,
            "average_sentiment": avg_sentiment,
            "target_deflection_pct": 75.0,
            "on_track": (deflected/total*100 >= 75.0) if total else None,
        }
        cs_metrics_t.put_item(Item={"pk": f"DAILY#{today}", "sk": today, **metrics})
        return json.dumps(metrics)
    except Exception as e:
        return json.dumps({"error": str(e), "note": "Needs GSI on date field — see DEPLOY.md"})


@tool
def get_deflection_rate(days_back: int = 7) -> str:
    """
    Return the agent deflection rate over the past N days.
    Deflection rate = % of interactions resolved by the agent without human escalation.
    Target: >75% by Month 3.

    Args:
        days_back: Number of days to analyze (default 7).

    Returns:
        JSON with period deflection rate, trend, and daily breakdown.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    try:
        resp = cs_metrics_t.scan(
            FilterExpression="#s >= :cutoff",
            ExpressionAttributeNames={"#s": "sk"},
            ExpressionAttributeValues={":cutoff": cutoff},
        )
        items = [i for i in resp.get("Items", []) if i.get("pk", "").startswith("DAILY#")]
        total = sum(int(i.get("total_interactions", 0)) for i in items)
        deflected = sum(int(i.get("deflected_by_agent", 0)) for i in items)
        rate = round(deflected/total*100, 1) if total else 0
        return json.dumps({
            "period_days": days_back, "total_interactions": total,
            "deflected": deflected, "deflection_rate_pct": rate,
            "target_pct": 75.0, "status": "ON_TRACK" if rate >= 75 else "BELOW_TARGET",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_feature_activation_rates() -> str:
    """
    Return the activation rate for each AskLumin feature across all subscribers.
    Shows which features users discover organically vs. need the CS agent to surface.

    Returns:
        JSON with per-feature activation rates and the most under-discovered features.
    """
    try:
        resp = onboard_t.scan(Limit=500)
        all_users = resp.get("Items", [])
        total = len(all_users)
        if total == 0:
            return json.dumps({"error": "No onboarding records found."})

        feature_counts = {f: 0 for f in ALL_FEATURES}
        for user in all_users:
            for f in user.get("features_used", []):
                if f in feature_counts:
                    feature_counts[f] += 1

        rates = {
            f: {"count": c, "activation_rate_pct": round(c/total*100, 1)}
            for f, c in feature_counts.items()
        }
        most_under = sorted(rates.items(), key=lambda x: x[1]["activation_rate_pct"])[:3]
        return json.dumps({
            "total_users_analyzed": total,
            "feature_rates": rates,
            "most_under_discovered": [{"feature": f, **v} for f, v in most_under],
            "recommendation": f"Surface '{most_under[0][0]}' in next CS touchpoint — only {most_under[0][1]['activation_rate_pct']}% of users have activated it.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_nps_summary(days_back: int = 30) -> str:
    """
    Return NPS summary statistics for the past N days: average score, promoter /
    passive / detractor breakdown, and top feedback themes from comments.

    Args:
        days_back: Days of NPS data to include.

    Returns:
        JSON NPS summary with score, breakdown, and themes.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    try:
        resp = nps_t.scan(
            FilterExpression="sk >= :c",
            ExpressionAttributeValues={":c": cutoff},
        )
        items = resp.get("Items", [])
        if not items:
            return json.dumps({"message": f"No NPS responses in the last {days_back} days.", "nps_score": None})

        scores = [int(i.get("score", 5)) for i in items]
        promoters  = sum(1 for s in scores if s >= 9)
        passives   = sum(1 for s in scores if 7 <= s <= 8)
        detractors = sum(1 for s in scores if s <= 6)
        n = len(scores)
        nps = round((promoters - detractors) / n * 100)

        return json.dumps({
            "period_days": days_back, "responses": n, "nps_score": nps,
            "promoters": promoters, "passives": passives, "detractors": detractors,
            "avg_score": round(sum(scores)/n, 2),
            "status": "EXCELLENT" if nps >= 70 else "GOOD" if nps >= 50 else "NEEDS_ATTENTION",
            "target_nps": 50,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# Make ALL_FEATURES importable from context_tools
from tools.context_tools import ALL_FEATURES  # noqa: E402
