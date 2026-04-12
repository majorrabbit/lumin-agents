"""
tools/crm_tools.py — Group C: Pipeline CRM Engine
Tools: save_convention_record, query_convention_pipeline, schedule_followup_event

tools/alert_tools.py — Group D: Alert & Response Engine
Tools: monitor_email_responses, classify_response_sentiment, send_alert_to_hf

Both groups in one file for compactness. Shim files provide clean imports.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import anthropic
import boto3
import requests
from strands import tool

dynamo      = boto3.resource("dynamodb", region_name="us-east-1")
eb_client   = boto3.client("events",          region_name="us-east-1")
lambda_c    = boto3.client("lambda",          region_name="us-east-1")
sns_client  = boto3.client("sns",             region_name="us-east-1")
secrets_c   = boto3.client("secretsmanager",  region_name="us-east-1")

CONVENTIONS_TABLE  = os.environ.get("SBIA_CONVENTIONS_TABLE",  "sbia_conventions")
OUTREACH_TABLE     = os.environ.get("SBIA_OUTREACH_LOG_TABLE", "sbia_outreach_log")
conventions_t      = dynamo.Table(CONVENTIONS_TABLE)
outreach_t         = dynamo.Table(OUTREACH_TABLE)


def _get_secret(key: str) -> str:
    try:
        return secrets_c.get_secret_value(SecretId=key)["SecretString"]
    except Exception:
        return os.environ.get(key.split("/")[-1].upper().replace("-", "_"), "")

# ════════════════════════════════════════════════════════════════════════════
# GROUP C — CRM & PIPELINE TOOLS
# ════════════════════════════════════════════════════════════════════════════

# Valid pipeline states
VALID_STATUSES = {
    "DISCOVERED", "RESEARCHED", "OUTREACH_SENT",
    "FOLLOWED_UP_1", "FOLLOWED_UP_2",
    "RESPONDED", "BOOKED", "DECLINED", "GHOSTED",
}


@tool
def save_convention_record(
    convention_data: dict,
    update_only: bool = False,
) -> str:
    """
    Write or update a convention record in sbia_conventions DynamoDB table.
    Deduplicates by convention name + year to prevent double-processing.
    Performs a full upsert: creates new record or updates existing fields.

    Args:
        convention_data: Dict containing convention fields (see DynamoDB schema).
                         Required: name. Optional: all other fields.
        update_only:     If True, only update existing records (skip creates).

    Returns:
        JSON with convention_id and action ("created" or "updated").
    """
    ts = datetime.now(timezone.utc).isoformat()
    name = convention_data.get("name", "").strip()
    if not name:
        return json.dumps({"error": "convention_data.name is required."})

    year = datetime.now(timezone.utc).year

    # Check for existing record
    try:
        existing = conventions_t.query(
            IndexName="name-year-index",
            KeyConditionExpression="#n = :name AND #y = :year",
            ExpressionAttributeNames={"#n": "name", "#y": "year"},
            ExpressionAttributeValues={":name": name, ":year": str(year)},
            Limit=1,
        )
        items = existing.get("Items", [])
    except Exception:
        items = []  # Index may not exist yet

    if items:
        # Update existing
        convention_id = items[0]["pk"]
        updates = {
            k: v for k, v in convention_data.items()
            if k not in ("pk", "sk", "convention_id") and v is not None
        }
        updates["updated_at"] = ts

        try:
            expr  = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
            names = {f"#{k}": k for k in updates}
            vals  = {f":{k}": v for k, v in updates.items()}
            conventions_t.update_item(
                Key={"pk": convention_id, "sk": str(year)},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=vals,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "convention_id": convention_id})

        return json.dumps({"convention_id": convention_id, "action": "updated", "name": name})

    elif update_only:
        return json.dumps({"action": "skipped", "reason": "Record not found and update_only=True."})

    else:
        # Create new
        convention_id = str(uuid.uuid4())
        item = {
            "pk":                  convention_id,
            "sk":                  str(year),
            "convention_id":       convention_id,
            "name":                name,
            "year":                str(year),
            "url":                 convention_data.get("url", ""),
            "location":            convention_data.get("location", "TBD"),
            "state":               convention_data.get("state", ""),
            "event_dates":         convention_data.get("event_dates", "TBD"),
            "event_month":         convention_data.get("event_month", 0),
            "attendance_est":      convention_data.get("attendance_est", 0),
            "genre_tags":          convention_data.get("genre_tags", []),
            "booking_contact":     convention_data.get("booking_contact", {}),
            "fit_score":           str(convention_data.get("fit_score", 0)),
            "fit_tier":            convention_data.get("fit_tier", "C"),
            "status":              convention_data.get("status", "DISCOVERED"),
            "outreach_sent_at":    "",
            "followup1_sent_at":   "",
            "followup2_sent_at":   "",
            "response_received":   False,
            "response_content":    "",
            "response_sentiment":  "",
            "notes":               convention_data.get("notes", ""),
            "created_at":          ts,
            "updated_at":          ts,
        }

        try:
            conventions_t.put_item(Item={
                k: v for k, v in item.items()
                if v is not None and v != []
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

        return json.dumps({
            "convention_id": convention_id,
            "action":        "created",
            "name":          name,
            "status":        item["status"],
        })


@tool
def query_convention_pipeline(
    status_filter: Optional[list] = None,
    state_filter: Optional[str] = None,
    fit_tier_filter: Optional[str] = None,
    due_for_followup: bool = False,
    limit: int = 50,
) -> str:
    """
    Query the booking pipeline with optional filters. Returns convention
    records sorted by fit_score (highest first). When due_for_followup=True,
    returns conventions overdue for their next follow-up touch.

    Args:
        status_filter:     List of statuses to include (e.g., ["OUTREACH_SENT"]).
        state_filter:      Filter by state abbreviation (e.g., "CA").
        fit_tier_filter:   Filter by fit tier ("A", "B", "C", "D").
        due_for_followup:  Return only conventions needing follow-up today.
        limit:             Maximum records to return (default 50).

    Returns:
        JSON with count and list of matching convention records.
    """
    now = datetime.now(timezone.utc)

    try:
        resp  = conventions_t.scan(Limit=500)  # scan is fine at our scale
        items = resp.get("Items", [])
    except Exception as e:
        return json.dumps({"error": str(e), "count": 0, "conventions": []})

    # Apply filters
    if status_filter:
        items = [i for i in items if i.get("status") in status_filter]

    if state_filter:
        items = [i for i in items
                 if state_filter.upper() in i.get("state", "").upper()
                 or state_filter.upper() in i.get("location", "").upper()]

    if fit_tier_filter:
        items = [i for i in items if i.get("fit_tier") == fit_tier_filter.upper()]

    if due_for_followup:
        due = []
        for item in items:
            status = item.get("status", "")

            if status == "OUTREACH_SENT":
                sent_at_str = item.get("outreach_sent_at", "")
                if sent_at_str:
                    try:
                        sent_at = datetime.fromisoformat(sent_at_str.replace("Z", "+00:00"))
                        if (now - sent_at).days >= 7:
                            item["_followup_due"] = "FOLLOWUP_1"
                            due.append(item)
                    except Exception:
                        pass

            elif status == "FOLLOWED_UP_1":
                fu1_str = item.get("followup1_sent_at", "")
                if fu1_str:
                    try:
                        fu1_at = datetime.fromisoformat(fu1_str.replace("Z", "+00:00"))
                        if (now - fu1_at).days >= 7:
                            item["_followup_due"] = "FOLLOWUP_2"
                            due.append(item)
                    except Exception:
                        pass

            elif status == "FOLLOWED_UP_2":
                fu2_str = item.get("followup2_sent_at", "")
                if fu2_str:
                    try:
                        fu2_at = datetime.fromisoformat(fu2_str.replace("Z", "+00:00"))
                        if (now - fu2_at).days >= 7:
                            item["_followup_due"] = "GHOSTED"
                            due.append(item)
                    except Exception:
                        pass

        items = due

    # Sort by fit_score descending
    items.sort(key=lambda x: float(x.get("fit_score", 0) or 0), reverse=True)
    items = items[:limit]

    # Build status summary for pipeline reports
    all_items = conventions_t.scan().get("Items", [])
    summary = {}
    for status in VALID_STATUSES:
        summary[status] = sum(1 for i in all_items if i.get("status") == status)

    return json.dumps({
        "count":            len(items),
        "conventions":      items,
        "pipeline_summary": summary,
        "total_in_db":      len(all_items),
    })


@tool
def schedule_followup_event(
    convention_id: str,
    followup_type: str,
    scheduled_date: str,
    contact_email: str,
) -> str:
    """
    Create a one-time EventBridge scheduled rule to trigger the follow-up
    dispatcher Lambda on the specified date for a specific convention.
    Rule is automatically deleted after firing.

    Args:
        convention_id:  Convention UUID.
        followup_type:  "FOLLOWUP_1" | "FOLLOWUP_2"
        scheduled_date: ISO date string (e.g., "2026-05-15").
        contact_email:  Contact email (stored in the event payload for convenience).

    Returns:
        JSON with rule ARN, scheduled date, and status.
    """
    lambda_arn = os.environ.get("SBIA_FOLLOWUP_LAMBDA_ARN", "")
    rule_name  = f"sbia-followup-{convention_id[:8]}-{followup_type.lower()}"

    # Parse and validate scheduled date
    try:
        sched = datetime.strptime(scheduled_date, "%Y-%m-%d")
        sched = sched.replace(hour=15, minute=0, second=0, tzinfo=timezone.utc)  # 10am ET = 15:00 UTC
        cron_expr = f"cron({sched.minute} {sched.hour} {sched.day} {sched.month} ? {sched.year})"
    except ValueError:
        return json.dumps({"error": f"Invalid date format: {scheduled_date}. Use YYYY-MM-DD."})

    if not lambda_arn:
        # No Lambda ARN configured — log intent only
        return json.dumps({
            "status":        "LOGGED_ONLY",
            "rule_name":     rule_name,
            "scheduled_for": scheduled_date,
            "followup_type": followup_type,
            "note":          "Set SBIA_FOLLOWUP_LAMBDA_ARN env var to enable EventBridge scheduling.",
        })

    try:
        # Create EventBridge rule
        rule_resp = eb_client.put_rule(
            Name=rule_name,
            ScheduleExpression=cron_expr,
            State="ENABLED",
            Description=f"SBIA follow-up for {convention_id} — {followup_type}",
        )
        rule_arn = rule_resp["RuleArn"]

        # Add Lambda as target
        payload = json.dumps({
            "trigger_type":  "FOLLOWUP_DISPATCH",
            "convention_id": convention_id,
            "followup_type": followup_type,
            "contact_email": contact_email,
        })
        eb_client.put_targets(
            Rule=rule_name,
            Targets=[{
                "Id":    "sbia-followup-target",
                "Arn":   lambda_arn,
                "Input": payload,
            }],
        )

        return json.dumps({
            "status":        "SCHEDULED",
            "rule_name":     rule_name,
            "rule_arn":      rule_arn,
            "scheduled_for": scheduled_date,
            "followup_type": followup_type,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "rule_name": rule_name})


# ════════════════════════════════════════════════════════════════════════════
# GROUP D — ALERT & RESPONSE TOOLS
# ════════════════════════════════════════════════════════════════════════════

# Response sentiment categories
SENTIMENT_CATEGORIES = {
    "INTERESTED":       ("HOT",  "Positive, wants to proceed or learn more"),
    "NEEDS_INFO":       ("WARM", "Asking questions, wants more details"),
    "RATE_NEGOTIATION": ("HOT",  "Interested but discussing fees"),
    "DECLINED":         ("COLD", "Politely or firmly declined"),
    "ALREADY_BOOKED":   ("COLD", "Entertainment already confirmed for this year"),
    "WRONG_CONTACT":    ("WARM", "Forwarded to correct person"),
    "AUTO_REPLY":       ("IGNORE","Automated out-of-office response"),
    "SPAM_UNRELATED":   ("IGNORE","Not relevant to our inquiry"),
}


@tool
def monitor_email_responses() -> str:
    """
    Poll the booking inbox for replies to sent outreach emails.
    Matches replies to convention records via email threading.
    In production: uses SES receipt rules → S3 → Lambda parse pattern,
    or Gmail API if using Gmail as the booking inbox.

    Returns:
        JSON list of unprocessed replies with convention_id, sender info,
        subject, body, and received timestamp.
    """
    # Production: Parse emails from S3 bucket where SES receipt rules deposit them
    # Or poll Gmail via Gmail API if booking@ is a Gmail account
    email_s3_bucket = os.environ.get("SBIA_EMAIL_INBOX_BUCKET", "")
    s3_c = boto3.client("s3", region_name="us-east-1")

    unprocessed = []
    ts = datetime.now(timezone.utc).isoformat()

    if email_s3_bucket:
        try:
            # List new email objects in S3
            objects = s3_c.list_objects_v2(
                Bucket=email_s3_bucket,
                Prefix="inbox/unprocessed/",
            ).get("Contents", [])

            for obj in objects[:20]:  # cap at 20 per cycle
                try:
                    body_raw = s3_c.get_object(
                        Bucket=email_s3_bucket,
                        Key=obj["Key"],
                    )["Body"].read().decode("utf-8", errors="replace")

                    # Parse headers for convention matching
                    from_m    = re.search(r'From:\s*(.+)', body_raw, re.IGNORECASE)
                    subject_m = re.search(r'Subject:\s*(.+)', body_raw, re.IGNORECASE)
                    in_reply_m= re.search(r'In-Reply-To:\s*<([^>]+)>', body_raw, re.IGNORECASE)

                    # Match to convention via SES message ID
                    convention_id = None
                    if in_reply_m:
                        ses_ref = in_reply_m.group(1)
                        try:
                            conv_resp = outreach_t.scan(
                                FilterExpression="ses_message_id = :sid",
                                ExpressionAttributeValues={":sid": ses_ref},
                                Limit=1,
                            )
                            if conv_resp.get("Items"):
                                convention_id = conv_resp["Items"][0].get("convention_id")
                        except Exception:
                            pass

                    unprocessed.append({
                        "s3_key":         obj["Key"],
                        "convention_id":  convention_id,
                        "from_email":     from_m.group(1).strip() if from_m else "unknown",
                        "subject":        subject_m.group(1).strip() if subject_m else "(no subject)",
                        "body":           body_raw[:3000],
                        "received_at":    obj["LastModified"].isoformat(),
                    })

                    # Move to processed/ folder
                    processed_key = obj["Key"].replace("inbox/unprocessed/", "inbox/processed/")
                    s3_c.copy_object(
                        Bucket=email_s3_bucket,
                        CopySource={"Bucket": email_s3_bucket, "Key": obj["Key"]},
                        Key=processed_key,
                    )
                    s3_c.delete_object(Bucket=email_s3_bucket, Key=obj["Key"])

                except Exception:
                    continue
        except Exception as e:
            return json.dumps({"error": str(e), "replies": [], "checked_at": ts})

    return json.dumps({
        "replies_found": len(unprocessed),
        "replies":       unprocessed,
        "checked_at":    ts,
        "inbox_bucket":  email_s3_bucket or "NOT_CONFIGURED",
        "note":          "Set SBIA_EMAIL_INBOX_BUCKET to enable inbox monitoring." if not email_s3_bucket else "",
    })


@tool
def classify_response_sentiment(
    email_body: str,
    convention_name: str,
) -> str:
    """
    Use Claude to classify the intent and priority of an inbound email reply.
    Returns category, confidence, priority (HOT/WARM/COLD/IGNORE),
    suggested next action, and key quotes from the email.

    Categories:
      INTERESTED, NEEDS_INFO, DECLINED, RATE_NEGOTIATION,
      ALREADY_BOOKED, WRONG_CONTACT, AUTO_REPLY, SPAM_UNRELATED

    Args:
        email_body:       The full email body text.
        convention_name:  Convention name for context.

    Returns:
        JSON with sentiment, confidence, priority, action, and key_quotes.
    """
    # Fast rule-based classification for obvious cases
    body_lower = email_body.lower()

    if any(kw in body_lower for kw in ["out of office", "automatic reply", "auto-reply", "vacation"]):
        return json.dumps({
            "sentiment": "AUTO_REPLY", "confidence": 0.98,
            "priority": "IGNORE", "key_quotes": [],
            "suggested_response_action": "Log and ignore. Re-check in 7 days.",
        })

    if any(kw in body_lower for kw in ["unsubscribe", "remove me", "stop contacting", "do not contact"]):
        return json.dumps({
            "sentiment": "DECLINED", "confidence": 0.99,
            "priority": "COLD",
            "key_quotes": ["Unsubscribe request"],
            "suggested_response_action": "Mark DECLINED. Add to suppression list. Do not contact again.",
        })

    # Use Claude for nuanced cases
    api_key = os.environ.get("ANTHROPIC_API_KEY") or _get_secret("lumin/anthropic-api-key")
    if not api_key:
        return json.dumps({"error": "ANTHROPIC_API_KEY not set.", "sentiment": "NEEDS_INFO", "priority": "WARM"})

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    f"Classify this email reply to a booking inquiry for artist SkyBlew.\n"
                    f"Convention: {convention_name}\n\n"
                    f"Email body:\n{email_body[:2000]}\n\n"
                    "Classify the intent into ONE of:\n"
                    "INTERESTED, NEEDS_INFO, DECLINED, RATE_NEGOTIATION, "
                    "ALREADY_BOOKED, WRONG_CONTACT, AUTO_REPLY, SPAM_UNRELATED\n\n"
                    "Return ONLY valid JSON:\n"
                    '{"sentiment": "...", "confidence": 0.0-1.0, '
                    '"priority": "HOT"|"WARM"|"COLD"|"IGNORE", '
                    '"suggested_response_action": "...", '
                    '"key_quotes": ["..."]}'
                ),
            }],
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            # Validate priority against known categories
            sentiment    = result.get("sentiment", "NEEDS_INFO")
            known_prio, _= SENTIMENT_CATEGORIES.get(sentiment, ("WARM", ""))
            result["priority"] = result.get("priority", known_prio)
            return json.dumps(result)
    except Exception as e:
        pass

    # Fallback heuristic
    if any(kw in body_lower for kw in ["interested", "love to", "yes", "sounds great", "tell me more"]):
        sentiment, priority = "INTERESTED", "HOT"
    elif any(kw in body_lower for kw in ["declined", "not at this time", "already booked", "full roster"]):
        sentiment, priority = "DECLINED", "COLD"
    else:
        sentiment, priority = "NEEDS_INFO", "WARM"

    return json.dumps({
        "sentiment": sentiment,
        "confidence": 0.65,
        "priority": priority,
        "suggested_response_action": "H.F. to review and respond personally.",
        "key_quotes": [],
    })


@tool
def send_alert_to_hf(
    alert_type: str,
    convention_name: str,
    details: str,
    action_required: str,
    response_email: Optional[str] = None,
) -> str:
    """
    Send an immediate alert to H.F. via SNS → email, and for HOT_LEAD
    and BOOKING_CONFIRMED alerts, also post to the Slack webhook.

    Alert types:
      HOT_LEAD          — Interested response received, action needed ASAP
      BOOKING_CONFIRMED — Show has been booked
      NEEDS_REVIEW      — Needs_info response that requires H.F. attention
      WEEKLY_SUMMARY    — Monday pipeline report

    Args:
        alert_type:       One of the four alert types above.
        convention_name:  Convention name.
        details:          Full details of the situation.
        action_required:  Clear, specific action H.F. needs to take.
        response_email:   Full inbound email body (for HOT_LEAD / NEEDS_REVIEW).

    Returns:
        JSON with SNS and Slack notification statuses.
    """
    ts = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    emoji = {
        "HOT_LEAD":          "🔥",
        "BOOKING_CONFIRMED": "🎉",
        "NEEDS_REVIEW":      "📋",
        "WEEKLY_SUMMARY":    "📊",
    }.get(alert_type, "📋")

    subject = f"{emoji} SBIA Alert: {alert_type} — {convention_name}"

    body_lines = [
        f"SBIA BOOKING ALERT — {ts}",
        f"Alert Type: {alert_type}",
        f"Convention: {convention_name}",
        "",
        "DETAILS:",
        details,
        "",
        "ACTION REQUIRED:",
        action_required,
    ]
    if response_email:
        body_lines += ["", "FULL RESPONSE EMAIL:", "─" * 40, response_email[:3000]]

    body = "\n".join(body_lines)

    sns_arn    = _get_secret("sbia/sns-alert-topic-arn")
    slack_url  = _get_secret("sbia/slack-webhook-url")
    sns_status = "SKIPPED"
    slack_status = "SKIPPED"

    # SNS notification
    if sns_arn:
        try:
            sns_client.publish(
                TopicArn=sns_arn,
                Subject=subject[:100],
                Message=body,
            )
            sns_status = "SENT"
        except Exception as e:
            sns_status = f"FAILED: {str(e)[:50]}"
    else:
        sns_status = "DRY_RUN — SBIA_SNS_ALERT_TOPIC_ARN not configured"

    # Slack webhook (HOT_LEAD and BOOKING_CONFIRMED only)
    if slack_url and alert_type in ("HOT_LEAD", "BOOKING_CONFIRMED"):
        slack_body = {
            "text": f"{emoji} *{alert_type}*: {convention_name}",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text",
                    "text": f"{emoji} {alert_type}: {convention_name}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Details:*\n{details[:300]}"},
                    {"type": "mrkdwn", "text": f"*Action Required:*\n{action_required}"},
                ]},
            ],
        }
        try:
            r = requests.post(slack_url, json=slack_body, timeout=5)
            slack_status = "SENT" if r.ok else f"FAILED: {r.status_code}"
        except Exception as e:
            slack_status = f"ERROR: {str(e)[:50]}"

    return json.dumps({
        "alert_type":    alert_type,
        "convention":    convention_name,
        "sns_status":    sns_status,
        "slack_status":  slack_status,
        "sent_at":       datetime.now(timezone.utc).isoformat(),
    })
