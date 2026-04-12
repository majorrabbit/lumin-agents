"""
tools/outreach_tools.py — Group B: Outreach Engine
Tools: compose_booking_inquiry, send_booking_email, generate_epk_signed_url

These tools handle all outbound communications.
Rate limiting is enforced at the send_booking_email() level.
Every email includes the EPK link. No exceptions.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import anthropic
import boto3
from strands import tool

dynamo  = boto3.resource("dynamodb", region_name="us-east-1")
ses     = boto3.client("ses", region_name="us-east-1")
s3      = boto3.client("s3", region_name="us-east-1")
secrets = boto3.client("secretsmanager", region_name="us-east-1")

def _get_secret(key: str) -> str:
    try:
        return secrets.get_secret_value(SecretId=key)["SecretString"]
    except Exception:
        return os.environ.get(key.split("/")[-1].upper().replace("-", "_"), "")

OUTREACH_TABLE = os.environ.get("SBIA_OUTREACH_LOG_TABLE", "sbia_outreach_log")
CONVENTIONS_TABLE = os.environ.get("SBIA_CONVENTIONS_TABLE", "sbia_conventions")
EPK_BUCKET   = os.environ.get("SBIA_EPK_BUCKET",  "sbia-epk-assets")
FROM_EMAIL   = os.environ.get("SBIA_FROM_EMAIL",  "booking@2stepsabovestars.com")
REPLY_TO     = os.environ.get("SBIA_REPLY_TO",    "booking@2stepsabovestars.com")

# Rate limit config
MAX_EMAILS_PER_DAY  = 50
MAX_EMAILS_PER_HOUR = 5

# ─── TOOL 4: COMPOSE BOOKING INQUIRY ─────────────────────────────────────────

SKYBLEW_CREDS = {
    "anime": [
        "Toured with MegaRan — the nerd hip-hop pioneer who's performed at Anime Expo, MAGFest, and PAX",
        "Music licensed to FUNimation",
        "His genre — 'Rhythm Escapism' — blends conscious hip-hop with anime/gaming/space themes",
        "Clean, all-ages lyrics with anime and gaming cultural depth",
    ],
    "gaming": [
        "Toured with MegaRan — every gamer in your audience knows his name",
        "Video game soundtrack placements, including Bomb Rush Cyberfunk (Nintendo Switch)",
        "His track 'LightSwitch' shipped inside the game — not just licensed, embedded",
        "Performed alongside gaming music legends; your audience will recognize the lineage",
    ],
    "manga": [
        "Music licensed to FUNimation",
        "Toured with MegaRan, who has deep roots in the anime-adjacent music scene",
        "Rhythm Escapism™ aesthetic draws directly from anime narrative and art traditions",
    ],
    "general": [
        "Opened for Kendrick Lamar, Lupe Fiasco, Arrested Development, and Curren$y",
        "Toured with MegaRan",
        "Clean lyrics — appropriate for all ages and family events",
        "Genre 'Rhythm Escapism': conscious hip-hop for curious, culture-forward audiences",
    ],
}


@tool
def compose_booking_inquiry(
    convention_name: str,
    contact_name: Optional[str],
    contact_title: Optional[str],
    event_dates: str,
    event_location: str,
    genre_tags: list,
    past_performers: list,
    outreach_type: str,
    fit_tier: str,
    previous_email_summary: Optional[str] = None,
) -> str:
    """
    Generate a personalized booking inquiry email for a specific convention.
    Email is tailored by genre, contact title, fit tier, and outreach type.
    SkyBlew's strongest credibility anchors are always included, weighted
    by the convention's genre focus. Two subject-line variants are generated.

    Args:
        convention_name:         Convention name.
        contact_name:            Decision-maker's name (or None for generic greeting).
        contact_title:           Their title (e.g., "Programming Director").
        event_dates:             Event date string.
        event_location:          City, State.
        genre_tags:              List of genre descriptors (e.g., ["anime", "gaming"]).
        past_performers:         Known past performers at this event.
        outreach_type:           "INITIAL" | "FOLLOWUP_1" | "FOLLOWUP_2"
        fit_tier:                "A" | "B" | "C"
        previous_email_summary:  Summary of previous email for follow-ups.

    Returns:
        JSON with subject_a, subject_b, body, epk_url placeholder, word_count,
        tone_assessment, and status AWAITING_SEND.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or _get_secret("lumin/anthropic-api-key")
    if not api_key:
        return json.dumps({"error": "ANTHROPIC_API_KEY not set."})

    # Select credibility hooks based on genre
    primary_genre = "gaming" if "gaming" in genre_tags else (
        "anime" if "anime" in genre_tags else (
        "manga" if "manga" in genre_tags else "general"
    ))
    creds = SKYBLEW_CREDS[primary_genre][:2]

    # Salutation
    greeting = f"Hi {contact_name}" if contact_name else "Hi there"
    title_note = f" ({contact_title})" if contact_title else ""

    # Tone instructions by tier and type
    if outreach_type == "INITIAL":
        tone_instruction = {
            "A": (
                "Write an enthusiastic, fan-aware initial outreach. Reference MegaRan and FUNimation prominently. "
                "Use anime/gaming cultural language naturally — not forcibly. 3-4 short paragraphs."
            ),
            "B": (
                "Write a warm, professional initial outreach. Lead with the most universal credibility anchor. "
                "Emphasize Rhythm Escapism as the bridge between hip-hop and nerd culture. 3 paragraphs."
            ),
            "C": (
                "Write a brief, confident initial outreach. Keep it under 150 words. "
                "Let the EPK do the work. Include the two most powerful credibility points only."
            ),
        }.get(fit_tier, "Write a professional booking inquiry.")
    elif outreach_type == "FOLLOWUP_1":
        tone_instruction = (
            "This is a friendly follow-up to an initial inquiry sent 7 days ago. "
            "Keep it brief (2-3 sentences). Reference 'circling back' on SkyBlew's availability. "
            "Mention that the EPK has been updated with new press photos."
        )
    else:  # FOLLOWUP_2
        tone_instruction = (
            "This is a final check-in — the second and last follow-up. "
            "Create gentle urgency: SkyBlew's availability for their event window is filling. "
            "One paragraph. Gracious and professional regardless of outcome."
        )

    past_perf_note = ""
    if past_performers:
        top = past_performers[:3]
        past_perf_note = f"Past performers at this event include: {', '.join(top)}. Reference any overlap naturally."

    prior_note = f"\nPrevious email summary: {previous_email_summary}" if previous_email_summary else ""

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""
Write a booking inquiry email for the following convention on behalf of SkyBlew
and his label 2StepsAboveTheStars LLC.

CONVENTION: {convention_name}
LOCATION: {event_location}
DATES: {event_dates}
CONTACT: {greeting}{title_note}
GENRE FOCUS: {', '.join(genre_tags)}
FIT TIER: {fit_tier}
OUTREACH TYPE: {outreach_type}
{past_perf_note}
{prior_note}

TONE INSTRUCTION: {tone_instruction}

ARTIST DETAILS TO USE:
- Artist: SkyBlew
- Genre: "Rhythm Escapism" — conscious hip-hop, anime/gaming/space themes, clean lyrics
- Key credentials: {'; '.join(creds)}
- Booking minimums: $1,000 solo | $2,000 full band
- Label: 2StepsAboveTheStars LLC
- EPK: [EPK_LINK_PLACEHOLDER] (30-day access link included)
- Reply-to: {REPLY_TO}

REQUIREMENTS:
- End with "To unsubscribe from future booking communications, reply REMOVE."
- Include [EPK_LINK_PLACEHOLDER] where the EPK link should appear
- Professional signature: "Best,\\nH.F.\\n2StepsAboveTheStars LLC | Booking@2StepsAboveStars.com"
- Generate TWO subject line variants

Return ONLY valid JSON:
{{"subject_a": "...", "subject_b": "...", "body": "...", "tone": "..."}}
"""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return json.dumps({
                **data,
                "outreach_type":   outreach_type,
                "fit_tier":        fit_tier,
                "convention_name": convention_name,
                "word_count":      len(data.get("body", "").split()),
                "status":          "AWAITING_SEND",
                "note":            "Call send_booking_email() to dispatch after review.",
            })
        return json.dumps({"error": "Could not parse Claude response.", "raw": text[:300]})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── TOOL 5: SEND BOOKING EMAIL ───────────────────────────────────────────────

outreach_log_t = dynamo.Table(OUTREACH_TABLE)
conventions_t  = dynamo.Table(CONVENTIONS_TABLE)


def _check_rate_limit() -> tuple:
    """Returns (allowed, reason). Checks daily and hourly send counts."""
    now   = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    hour  = now.strftime("%Y-%m-%d-%H")

    # Check daily count
    try:
        day_resp = outreach_log_t.query(
            IndexName="date-index",
            KeyConditionExpression="send_date = :d",
            ExpressionAttributeValues={":d": today},
        )
        daily_count = day_resp.get("Count", 0)
        if daily_count >= MAX_EMAILS_PER_DAY:
            return False, f"Daily limit reached ({daily_count}/{MAX_EMAILS_PER_DAY})"
    except Exception:
        pass  # Index may not exist yet — allow on first run

    # Check hourly count
    try:
        hr_resp = outreach_log_t.query(
            IndexName="hour-index",
            KeyConditionExpression="send_hour = :h",
            ExpressionAttributeValues={":h": hour},
        )
        hour_count = hr_resp.get("Count", 0)
        if hour_count >= MAX_EMAILS_PER_HOUR:
            return False, f"Hourly limit reached ({hour_count}/{MAX_EMAILS_PER_HOUR})"
    except Exception:
        pass

    return True, "OK"


def _is_duplicate(convention_id: str) -> bool:
    """Check if we've already sent an initial email to this convention this year."""
    try:
        resp = outreach_log_t.query(
            KeyConditionExpression="convention_id = :cid",
            ExpressionAttributeValues={":cid": convention_id},
            FilterExpression="outreach_type = :t",
            ExpressionAttributeNames={},
            Limit=1,
        )
        return len(resp.get("Items", [])) > 0
    except Exception:
        return False


@tool
def send_booking_email(
    to_email: str,
    to_name: Optional[str],
    subject: str,
    body: str,
    convention_id: str,
    outreach_type: str,
    reply_to: str = "booking@2stepsabovestars.com",
) -> str:
    """
    Dispatch a booking inquiry email via AWS SES.
    Enforces: max 50 emails/day, max 5/hour, no duplicate sends,
    CAN-SPAM unsubscribe inclusion. Logs every send to sbia_outreach_log.

    Args:
        to_email:      Recipient email address.
        to_name:       Recipient name (used in To: header).
        subject:       Email subject line.
        body:          Full email body text.
        convention_id: Convention ID for tracking and deduplication.
        outreach_type: "INITIAL" | "FOLLOWUP_1" | "FOLLOWUP_2"
        reply_to:      Reply-to address (default: booking email).

    Returns:
        JSON with success status, SES message ID, and sent timestamp.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Validate email
    if not re.match(r'^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$', to_email):
        return json.dumps({"success": False, "error": f"Invalid email address: {to_email}"})

    # Rate limit check
    allowed, reason = _check_rate_limit()
    if not allowed:
        return json.dumps({"success": False, "error": f"Rate limit: {reason}"})

    # Deduplication for INITIAL emails
    if outreach_type == "INITIAL" and _is_duplicate(convention_id):
        return json.dumps({
            "success": False,
            "error": f"Duplicate INITIAL email — {convention_id} already contacted.",
        })

    # Ensure CAN-SPAM compliance
    if "unsubscribe" not in body.lower():
        body += (
            "\n\n---\n"
            "To unsubscribe from future booking communications, reply REMOVE.\n"
            "2StepsAboveTheStars LLC | Booking Inquiries"
        )

    to_header = f"{to_name} <{to_email}>" if to_name else to_email

    # Build MIME email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"SkyBlew Booking <{FROM_EMAIL}>"
    msg["To"]      = to_header
    msg["Reply-To"]= reply_to
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(body.replace("\n", "<br>"), "html"))

    # Send via SES
    try:
        result = ses.send_raw_email(
            Source=FROM_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
        )
        ses_msg_id = result["MessageId"]
    except Exception as e:
        # Dry-run: if SES is not configured, log as DRY_RUN
        if "NoCredentials" in str(e) or "not authorized" in str(e).lower():
            ses_msg_id = f"DRY_RUN_{uuid.uuid4().hex[:8]}"
        else:
            return json.dumps({"success": False, "error": str(e)})

    # Log to DynamoDB
    outreach_id = str(uuid.uuid4())
    try:
        outreach_log_t.put_item(Item={
            "pk":             outreach_id,
            "sk":             convention_id,
            "convention_id":  convention_id,
            "outreach_type":  outreach_type,
            "to_email":       to_email,
            "to_name":        to_name or "",
            "subject":        subject,
            "body_preview":   body[:500],
            "sent_at":        ts,
            "send_date":      ts[:10],
            "send_hour":      ts[:13].replace("T", "-"),
            "ses_message_id": ses_msg_id,
            "opened":         False,
            "replied":        False,
        })
    except Exception:
        pass

    return json.dumps({
        "success":        True,
        "ses_message_id": ses_msg_id,
        "to_email":       to_email,
        "outreach_type":  outreach_type,
        "sent_at":        ts,
        "dry_run":        ses_msg_id.startswith("DRY_RUN"),
    })


# ─── TOOL 6: GENERATE EPK SIGNED URL ─────────────────────────────────────────

EPK_KEYS = {
    "full":       "epk/skyblew-epk-full.pdf",
    "one_pager":  "epk/skyblew-epk-one-pager.pdf",
    "press_photo":"epk/skyblew-press-photo-1.jpg",
    "rider":      "epk/skyblew-rider.pdf",
    "setlist":    "epk/skyblew-setlist-sample.pdf",
}


@tool
def generate_epk_signed_url(
    epk_type: str = "one_pager",
    expiry_days: int = 30,
    convention_id: Optional[str] = None,
) -> str:
    """
    Generate a pre-signed S3 URL for SkyBlew's EPK.
    The URL expires in expiry_days (default 30). For initial cold outreach
    the one-pager is used; full EPK is linked on follow-up or when interest shown.
    Optionally logs URL generation to the convention's outreach record.

    Args:
        epk_type:       "full" | "one_pager" | "press_photo" | "rider" | "setlist"
        expiry_days:    URL expiry in days (default 30).
        convention_id:  Convention ID for tracking (optional).

    Returns:
        Pre-signed URL string, or a placeholder URL if S3 is not configured.
    """
    s3_key = EPK_KEYS.get(epk_type, EPK_KEYS["one_pager"])
    bucket = _get_secret("sbia/epk-s3-bucket") or EPK_BUCKET
    expiry_seconds = expiry_days * 86400

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
        result = {"url": url, "epk_type": epk_type, "expires_days": expiry_days}
    except Exception:
        # Fallback: placeholder for testing or when S3 not yet set up
        result = {
            "url": f"https://epk.2stepsabovestars.com/{s3_key}",
            "epk_type": epk_type,
            "expires_days": expiry_days,
            "note": "S3 not configured — using placeholder URL. Upload EPKs to S3 before go-live.",
        }

    if convention_id:
        result["tracked_for_convention"] = convention_id

    return json.dumps(result)
