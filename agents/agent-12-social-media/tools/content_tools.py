"""
tools/content_tools.py — Content calendar and approval pipeline for Agent 12.
The human approval gate lives here. Nothing posts without going through this.
"""
import json
import os
import requests
import boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo   = boto3.resource("dynamodb", region_name="us-east-1")
cal_t    = dynamo.Table(os.environ.get("CALENDAR_TABLE",  "skyblew-content-calendar"))
queue_t  = dynamo.Table(os.environ.get("QUEUE_TABLE",     "skyblew-approval-queue"))
perf_t   = dynamo.Table(os.environ.get("PERF_TABLE",      "skyblew-post-performance"))
ses      = boto3.client("ses", region_name="us-east-1")
SLACK_APPROVAL_WEBHOOK = os.environ.get("SLACK_APPROVAL_WEBHOOK", "")
SLACK_SOCIAL_WEBHOOK   = os.environ.get("SLACK_SOCIAL_WEBHOOK", "")


@tool
def update_content_calendar(entries: list) -> str:
    """
    Add or update entries in the 30-day content calendar.
    Each entry includes platform, content draft, scheduled time, and campaign phase.

    Args:
        entries: List of {"platform", "content", "scheduled_at", "campaign_phase",
                           "content_type", "market"} dicts.

    Returns:
        JSON with count of entries added and calendar window.
    """
    ts = datetime.now(timezone.utc).isoformat()
    added = 0
    for entry in entries:
        pk = f"CALENDAR#{entry.get('platform','ALL').upper()}#{entry.get('scheduled_at','')[:10]}"
        try:
            cal_t.put_item(Item={
                "pk": pk, "sk": entry.get("scheduled_at", ts),
                "status": "PENDING_APPROVAL",
                "created_at": ts,
                **{k: str(v) if isinstance(v, (float, bool)) else v
                   for k, v in entry.items()},
            })
            added += 1
        except Exception as e:
            pass
    return json.dumps({"entries_added": added, "calendar_updated_at": ts})


@tool
def get_todays_content_queue() -> str:
    """
    Return all calendar entries scheduled for today, sorted by posting time.
    Separates APPROVED (ready to post) from PENDING_APPROVAL (needs H.F. review).

    Returns:
        JSON with approved and pending content lists.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = cal_t.scan(
            FilterExpression="begins_with(sk, :today)",
            ExpressionAttributeValues={":today": today},
        )
        items = sorted(resp.get("Items", []), key=lambda x: x.get("sk", ""))
        approved = [i for i in items if i.get("status") == "APPROVED"]
        pending  = [i for i in items if i.get("status") == "PENDING_APPROVAL"]
        return json.dumps({
            "date": today,
            "approved_count": len(approved),
            "pending_count": len(pending),
            "approved": approved,
            "pending": pending,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_pending_approvals(priority_filter: str = None) -> str:
    """
    Return all content currently waiting in the human approval queue,
    sorted by urgency (URGENT first, then time submitted).

    Args:
        priority_filter: Optional filter: URGENT / HIGH / NORMAL.

    Returns:
        JSON list of pending approval items.
    """
    try:
        resp = queue_t.scan(
            FilterExpression="#s = :pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":pending": "PENDING"},
        )
        items = resp.get("Items", [])
        if priority_filter:
            items = [i for i in items if i.get("priority") == priority_filter]
        # Sort: URGENT first, then by submitted_at
        priority_order = {"URGENT": 0, "HIGH": 1, "NORMAL": 2}
        items.sort(key=lambda x: (priority_order.get(x.get("priority", "NORMAL"), 2),
                                   x.get("submitted_at", "")))
        return json.dumps({"pending_count": len(items), "items": items[:20]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def send_approval_request(
    platform: str,
    content_type: str,
    caption_variants: list,
    cultural_context: str = "",
    priority: str = "NORMAL",
    campaign_phase: str = "",
) -> str:
    """
    Submit content to the human approval queue and post a rich Slack
    notification to #social-approvals with all variants and context.
    THE REQUIRED STEP before any content can be posted.

    Args:
        platform:          Target platform.
        content_type:      Type of content (album/culture/fan_engagement/etc.).
        caption_variants:  List of variant dicts from generate_caption().
        cultural_context:  Cultural moment context if applicable.
        priority:          URGENT / HIGH / NORMAL.
        campaign_phase:    FM & AM campaign phase if applicable.

    Returns:
        JSON with queue ID, Slack notification status.
    """
    ts = datetime.now(timezone.utc).isoformat()
    queue_id = f"APPROVE#{platform.upper()}#{ts[:10]}T{ts[11:16].replace(':', '')}"

    try:
        queue_t.put_item(Item={
            "pk": queue_id, "sk": ts,
            "platform": platform, "content_type": content_type,
            "variants": json.dumps(caption_variants),
            "cultural_context": cultural_context,
            "priority": priority, "campaign_phase": campaign_phase,
            "status": "PENDING", "submitted_at": ts,
        })
    except Exception:
        pass

    # Build Slack message
    priority_emoji = {"URGENT": "🚨", "HIGH": "⚡", "NORMAL": "📝"}.get(priority, "📝")
    preview = caption_variants[0].get("caption", str(caption_variants[0]))[:200] if caption_variants else ""

    msg = {
        "text": f"{priority_emoji} Social Content Approval — {platform.title()} [{priority}]",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"{priority_emoji} SkyBlew Content Approval — {platform.title()}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform.title()}"},
                {"type": "mrkdwn", "text": f"*Type:*\n{content_type}"},
                {"type": "mrkdwn", "text": f"*Priority:*\n{priority}"},
                {"type": "mrkdwn", "text": f"*Variants:*\n{len(caption_variants)} options"},
            ]},
        ],
    }

    if cultural_context:
        msg["blocks"].append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Cultural Context:*\n{cultural_context}"}})

    if campaign_phase:
        msg["blocks"].append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*FM & AM Phase:*\n{campaign_phase}"}})

    msg["blocks"].append({"type": "section", "text": {"type": "mrkdwn",
        "text": f"*Variant 1 Preview:*\n_{preview}_"}})
    msg["blocks"].append({"type": "section", "text": {"type": "mrkdwn",
        "text": f"Review at: ask.lumin.luxe/admin/social-queue\nQueue ID: `{queue_id}`"}})

    slack_status = "DRY_RUN"
    if SLACK_APPROVAL_WEBHOOK:
        try:
            r = requests.post(SLACK_APPROVAL_WEBHOOK, json=msg, timeout=5)
            slack_status = "SENT" if r.ok else f"FAILED:{r.status_code}"
        except Exception as e:
            slack_status = f"ERROR:{str(e)[:30]}"

    return json.dumps({
        "status": "QUEUED",
        "queue_id": queue_id,
        "priority": priority,
        "slack_notification": slack_status,
        "message": f"Submitted to H.F. approval queue. Check #social-approvals in Slack.",
    })


@tool
def mark_content_approved(queue_id: str, approved_by: str,
                            selected_variant: int = 0) -> str:
    """
    Mark a content approval request as approved. Records who approved,
    which variant was selected, and updates the calendar entry to APPROVED.
    Only call after receiving explicit human confirmation.

    Args:
        queue_id:         The approval queue ID.
        approved_by:      Name of approver (H.F. or SkyBlew).
        selected_variant: Index of approved variant (0, 1, or 2).

    Returns:
        JSON with approval confirmation and content ready-to-post status.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        queue_t.update_item(
            Key={"pk": queue_id, "sk": queue_t.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": queue_id},
                Limit=1,
            )["Items"][0]["sk"]},
            UpdateExpression="SET #s = :approved, approved_by = :ab, "
                             "approved_at = :ts, selected_variant = :sv",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":approved": "APPROVED", ":ab": approved_by,
                ":ts": ts, ":sv": selected_variant,
            },
        )
        return json.dumps({
            "status": "APPROVED",
            "queue_id": queue_id,
            "approved_by": approved_by,
            "selected_variant": selected_variant,
            "next_step": "Content is ready to post via post_to_[platform]() tool.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def mark_content_posted(queue_id: str, platform: str,
                          post_url: str = "") -> str:
    """
    Mark a content item as successfully posted. Updates both the approval
    queue record and the calendar entry.

    Args:
        queue_id:  Approval queue ID.
        platform:  Platform where it was posted.
        post_url:  URL of the live post (if available from platform API response).

    Returns:
        JSON confirmation.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        queue_t.update_item(
            Key={"pk": queue_id, "sk": ts},
            UpdateExpression="SET #s = :posted, posted_at = :ts, post_url = :url, platform = :p",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":posted": "POSTED", ":ts": ts,
                ":url": post_url, ":p": platform,
            },
        )
        return json.dumps({"status": "POSTED", "platform": platform,
                           "post_url": post_url, "posted_at": ts})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def log_post_performance(platform: str, post_id: str, post_url: str,
                          content_type: str, initial_metrics: dict = None) -> str:
    """
    Log a posted piece of content to the performance tracking table.
    This seeds the record that pull_platform_analytics() will enrich
    with engagement data over time.

    Args:
        platform:        Platform name.
        post_id:         Platform-native post identifier.
        post_url:        Live URL of the post.
        content_type:    Category of content.
        initial_metrics: Any metrics available at posting time.

    Returns:
        JSON confirmation with performance record ID.
    """
    ts = datetime.now(timezone.utc).isoformat()
    record_id = f"PERF#{platform.upper()}#{post_id}"
    try:
        perf_t.put_item(Item={
            "pk": record_id, "sk": ts,
            "platform": platform, "post_id": post_id,
            "post_url": post_url, "content_type": content_type,
            "posted_at": ts,
            "likes": 0, "comments": 0, "shares": 0, "views": 0,
            "engagement_rate": "0.0",
            **(initial_metrics or {}),
        })
        return json.dumps({"status": "LOGGED", "record_id": record_id})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# tools/platform_tools.py  (inline — all platform posting tools)
# ─────────────────────────────────────────────────────────────────────────────

IG_TOKEN     = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
TT_TOKEN     = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
TW_BEARER    = os.environ.get("TWITTER_BEARER_TOKEN", "")
YT_TOKEN     = os.environ.get("YOUTUBE_OAUTH_TOKEN", "")
DC_TOKEN     = os.environ.get("DISCORD_BOT_TOKEN", "")
TH_TOKEN     = os.environ.get("THREADS_ACCESS_TOKEN", "")
IG_USER_ID   = os.environ.get("INSTAGRAM_USER_ID", "")
DC_GUILD_ID  = os.environ.get("DISCORD_GUILD_ID", "")
DC_CHANNEL_ID= os.environ.get("DISCORD_CHANNEL_ID", "")

def _check_approval(queue_id: str) -> bool:
    """Verify content is in APPROVED status before posting."""
    try:
        resp = queue_t.query(
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": queue_id},
            Limit=1,
            ScanIndexForward=False,
        )
        items = resp.get("Items", [])
        return items[0].get("status") == "APPROVED" if items else False
    except Exception:
        return False


@tool
def post_to_instagram(queue_id: str, caption: str,
                       image_url: str = "", reel_url: str = "",
                       story: bool = False) -> str:
    """
    Post approved content to Instagram (Feed, Reels, or Stories)
    via the Instagram Graph API.
    REQUIRES queue_id to be in APPROVED status — will refuse otherwise.

    Args:
        queue_id:  Approval queue ID confirming human approval.
        caption:   The approved caption text.
        image_url: URL of image in S3 (for Feed posts).
        reel_url:  URL of video in S3 (for Reels).
        story:     True for Stories post.

    Returns:
        JSON with post status, post ID if successful.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED",
            "message": "Content must be in APPROVED status. Call mark_content_approved() first."})

    if not IG_TOKEN:
        return json.dumps({"status": "DRY_RUN",
            "message": "INSTAGRAM_ACCESS_TOKEN not configured.",
            "caption_preview": caption[:100],
            "note": "Set up Instagram Graph API token in .env to enable live posting."})

    post_type = "story" if story else ("reel" if reel_url else "feed")
    try:
        # Step 1: Create container
        container_data = {"access_token": IG_TOKEN}
        if reel_url:
            container_data.update({"media_type": "REELS", "video_url": reel_url, "caption": caption})
        elif story:
            container_data.update({"media_type": "IMAGE", "image_url": image_url, "is_carousel_item": False})
        else:
            container_data.update({"image_url": image_url or "https://placeholder.skyblew.com", "caption": caption})

        container_resp = requests.post(
            f"https://graph.instagram.com/{IG_USER_ID}/media",
            data=container_data, timeout=15,
        )

        if not container_resp.ok:
            return json.dumps({"status": "FAILED", "error": container_resp.text[:200]})

        container_id = container_resp.json().get("id")

        # Step 2: Publish
        publish_resp = requests.post(
            f"https://graph.instagram.com/{IG_USER_ID}/media_publish",
            data={"creation_id": container_id, "access_token": IG_TOKEN},
            timeout=15,
        )

        if publish_resp.ok:
            post_id = publish_resp.json().get("id", "unknown")
            mark_content_posted(queue_id=queue_id, platform="instagram",
                                 post_url=f"https://instagram.com/p/{post_id}")
            return json.dumps({"status": "POSTED", "platform": "instagram",
                                "post_id": post_id, "post_type": post_type})
        else:
            return json.dumps({"status": "FAILED", "error": publish_resp.text[:200]})

    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


@tool
def post_to_tiktok(queue_id: str, caption: str, video_url: str = "") -> str:
    """
    Post approved video content to TikTok via TikTok Content Posting API.
    REQUIRES queue_id to be in APPROVED status.

    Args:
        queue_id:  Approval queue ID.
        caption:   Approved caption with hashtags.
        video_url: URL of video asset in S3.

    Returns:
        JSON with post status.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED"})

    if not TT_TOKEN:
        return json.dumps({"status": "DRY_RUN",
            "message": "TIKTOK_ACCESS_TOKEN not configured. Apply at developers.tiktok.com/products/content-posting-api/",
            "caption_preview": caption[:100]})

    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {TT_TOKEN}",
                     "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {"title": caption[:150], "privacy_level": "PUBLIC_TO_EVERYONE",
                              "disable_duet": False, "disable_comment": False,
                              "disable_stitch": False},
                "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
            },
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            publish_id = data.get("data", {}).get("publish_id", "unknown")
            mark_content_posted(queue_id=queue_id, platform="tiktok")
            return json.dumps({"status": "POSTED", "platform": "tiktok", "publish_id": publish_id})
        else:
            return json.dumps({"status": "FAILED", "error": resp.text[:200]})
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


@tool
def post_to_twitter(queue_id: str, tweet_text: str) -> str:
    """
    Post approved content to X/Twitter via Twitter API v2.
    REQUIRES queue_id to be in APPROVED status.

    Args:
        queue_id:   Approval queue ID.
        tweet_text: The approved tweet (max 280 characters).

    Returns:
        JSON with tweet ID and URL if successful.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED"})

    if len(tweet_text) > 280:
        return json.dumps({"error": f"Tweet exceeds 280 characters ({len(tweet_text)}). Shorten it."})

    TW_ACCESS_TOKEN  = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    TW_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

    if not TW_ACCESS_TOKEN:
        return json.dumps({"status": "DRY_RUN",
            "message": "TWITTER_ACCESS_TOKEN not configured.",
            "tweet_preview": tweet_text})

    try:
        # requests-oauthlib handles OAuth 1.0a for Twitter API v2 writes
        from requests_oauthlib import OAuth1Session
        oauth = OAuth1Session(
            client_key=os.environ.get("TWITTER_API_KEY", ""),
            client_secret=os.environ.get("TWITTER_API_SECRET", ""),
            resource_owner_key=TW_ACCESS_TOKEN,
            resource_owner_secret=TW_ACCESS_SECRET,
        )
        resp = oauth.post(
            "https://api.twitter.com/2/tweets",
            json={"text": tweet_text},
            timeout=15,
        )
        if resp.ok:
            tweet_id = resp.json().get("data", {}).get("id", "unknown")
            post_url = f"https://twitter.com/SkyBlewOfficial/status/{tweet_id}"
            mark_content_posted(queue_id=queue_id, platform="twitter", post_url=post_url)
            return json.dumps({"status": "POSTED", "platform": "twitter",
                                "tweet_id": tweet_id, "post_url": post_url})
        else:
            return json.dumps({"status": "FAILED", "error": resp.text[:200]})
    except ImportError:
        return json.dumps({"status": "DEPENDENCY_MISSING",
            "message": "pip install requests-oauthlib required for Twitter OAuth 1.0a"})
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


@tool
def post_to_youtube_community(queue_id: str, post_text: str,
                               image_url: str = "") -> str:
    """
    Post approved content to YouTube Community tab via YouTube Data API v3.
    REQUIRES queue_id to be in APPROVED status.

    Args:
        queue_id:   Approval queue ID.
        post_text:  Community post text.
        image_url:  Optional image URL.

    Returns:
        JSON with post status.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED"})

    if not YT_TOKEN:
        return json.dumps({"status": "DRY_RUN",
            "message": "YOUTUBE_OAUTH_TOKEN not configured.",
            "post_preview": post_text[:150]})

    try:
        resp = requests.post(
            "https://www.googleapis.com/youtube/v3/communityPosts?part=snippet",
            headers={"Authorization": f"Bearer {YT_TOKEN}",
                     "Content-Type": "application/json"},
            json={"snippet": {"type": "textPost", "textOriginal": post_text}},
            timeout=15,
        )
        if resp.ok:
            post_id = resp.json().get("id", "unknown")
            mark_content_posted(queue_id=queue_id, platform="youtube")
            return json.dumps({"status": "POSTED", "platform": "youtube", "post_id": post_id})
        else:
            return json.dumps({"status": "FAILED", "error": resp.text[:200]})
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


@tool
def post_to_discord(queue_id: str, message: str, channel_id: str = "") -> str:
    """
    Post approved content to a Discord channel via the Discord Bot API.
    REQUIRES queue_id to be in APPROVED status.

    Args:
        queue_id:   Approval queue ID.
        message:    Message content.
        channel_id: Target channel ID (defaults to env DISCORD_CHANNEL_ID).

    Returns:
        JSON with post status.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED"})

    target_channel = channel_id or DC_CHANNEL_ID
    if not DC_TOKEN or not target_channel:
        return json.dumps({"status": "DRY_RUN",
            "message": "DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID not configured.",
            "message_preview": message[:100]})

    try:
        resp = requests.post(
            f"https://discord.com/api/v10/channels/{target_channel}/messages",
            headers={"Authorization": f"Bot {DC_TOKEN}", "Content-Type": "application/json"},
            json={"content": message},
            timeout=10,
        )
        if resp.ok:
            msg_id = resp.json().get("id", "unknown")
            mark_content_posted(queue_id=queue_id, platform="discord")
            return json.dumps({"status": "POSTED", "platform": "discord", "message_id": msg_id})
        else:
            return json.dumps({"status": "FAILED", "error": resp.text[:200]})
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})


@tool
def post_to_threads(queue_id: str, post_text: str, image_url: str = "") -> str:
    """
    Post approved content to Threads via the Threads API.
    REQUIRES queue_id to be in APPROVED status.

    Args:
        queue_id:   Approval queue ID.
        post_text:  Post content (max 500 characters).
        image_url:  Optional image URL.

    Returns:
        JSON with post status.
    """
    if not _check_approval(queue_id):
        return json.dumps({"error": "APPROVAL_REQUIRED"})

    if not TH_TOKEN:
        return json.dumps({"status": "DRY_RUN",
            "message": "THREADS_ACCESS_TOKEN not configured.",
            "post_preview": post_text[:100]})

    THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")
    try:
        # Step 1: Create container
        data = {"media_type": "TEXT", "text": post_text[:500]}
        if image_url:
            data.update({"media_type": "IMAGE", "image_url": image_url})
        container = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
            params={"access_token": TH_TOKEN},
            json=data, timeout=15,
        )
        if not container.ok:
            return json.dumps({"status": "FAILED", "error": container.text[:200]})
        container_id = container.json().get("id")

        # Step 2: Publish
        publish = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
            params={"access_token": TH_TOKEN, "creation_id": container_id},
            timeout=15,
        )
        if publish.ok:
            post_id = publish.json().get("id", "unknown")
            mark_content_posted(queue_id=queue_id, platform="threads")
            return json.dumps({"status": "POSTED", "platform": "threads", "post_id": post_id})
        else:
            return json.dumps({"status": "FAILED", "error": publish.text[:200]})
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": str(e)})
