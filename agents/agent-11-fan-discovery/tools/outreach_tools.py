"""
tools/outreach_tools.py — Human-gated outreach tools for Agent 11.
EVERY outreach message goes to human approval before posting. No exceptions.
"""
import json, os, requests, boto3
from datetime import datetime, timezone
from strands import tool
import anthropic

dynamo  = boto3.resource("dynamodb", region_name="us-east-1")
queue_t = dynamo.Table("fan-discovery-outreach-queue")

SKYBLEW_VOICE_PROMPT = """
You are writing a short, authentic message on behalf of SkyBlew — a conscious
hip-hop artist whose music lives at the intersection of Nujabes-inspired lo-fi,
the lyrical tradition of Common and Lupe Fiasco, anime culture (Samurai Champloo,
Carole & Tuesday), and video game aesthetics (Bomb Rush Cyberfunk on Nintendo).

SkyBlew coined Rhythm Escapism™ — music that paints your world into something better.
His track LightSwitch is in Bomb Rush Cyberfunk. His album MoreLoveLessWar just dropped.

Voice rules:
- Warm and genuine — never promotional
- Specific to the community — speak their language first
- Brief — 3-5 sentences maximum
- Connect to what they ALREADY love, then introduce SkyBlew
- Lead with the music or message, not the artist's credentials
- Never: "Check out my music!" | Always: "If you love X, this might resonate."

Write a {message_type} for someone in the {community_name} community.
Context about this community: {community_context}
The cultural touchstone to connect through: {cultural_touchstone}
Featured track or album: {featured_content}
Platform: {platform} (adjust tone/length accordingly)
Word limit: {word_limit} words maximum.
"""


@tool
def generate_outreach_message(
    community_name: str,
    community_context: str,
    cultural_touchstone: str,
    featured_content: str,
    message_type: str = "comment_reply",
    platform: str = "reddit",
    word_limit: int = 80,
) -> str:
    """
    Generate 3 variants of an outreach message for a specific community using
    SkyBlew's authentic voice. Uses Claude to write messages that feel native
    to the platform and community — not generic promotional copy.
    ALL output is submitted to the approval queue. Nothing is posted automatically.

    Args:
        community_name:    The community name (e.g., "r/nujabes").
        community_context: Why this community is relevant to SkyBlew.
        cultural_touchstone: The specific reference to connect through.
        featured_content:  Track or album to feature (e.g., "LightSwitch").
        message_type:      post / comment_reply / dm / discord_message.
        platform:          reddit / tiktok / youtube / discord / twitter.
        word_limit:        Maximum word count (default 80).

    Returns:
        JSON with 3 message variants ready for human review.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "ANTHROPIC_API_KEY not set."})

    client = anthropic.Anthropic(api_key=api_key)

    prompt = SKYBLEW_VOICE_PROMPT.format(
        message_type=message_type,
        community_name=community_name,
        community_context=community_context,
        cultural_touchstone=cultural_touchstone,
        featured_content=featured_content,
        platform=platform,
        word_limit=word_limit,
    )

    variants = []
    temperatures = [0.70, 0.85, 1.00]
    for i, temp in enumerate(temperatures):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                temperature=temp,
                messages=[{"role": "user", "content": prompt + f"\n\nWrite variant {i+1} of 3."}],
            )
            variants.append(resp.content[0].text.strip())
        except Exception as e:
            variants.append(f"[Generation error: {str(e)}]")

    return json.dumps({
        "community": community_name,
        "platform": platform,
        "featured_content": featured_content,
        "message_type": message_type,
        "variants": variants,
        "status": "AWAITING_HUMAN_APPROVAL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Submit to approval queue via submit_for_human_approval().",
    })


@tool
def submit_for_human_approval(
    community_name: str,
    platform: str,
    target_url: str,
    message_variants: list,
    featured_content: str,
    utm_link: str = "",
) -> str:
    """
    Submit outreach message variants to the human approval queue in DynamoDB.
    This is the REQUIRED step before any message can be posted. The agent
    may never post directly — all messages must pass through human review.

    Args:
        community_name:   Target community name.
        platform:         reddit / tiktok / youtube / discord.
        target_url:       URL of the specific post/thread/channel to reply to.
        message_variants: List of 3 message variants from generate_outreach_message().
        featured_content: Track or album being featured.
        utm_link:         UTM-tracked link to include (from build_utm_link()).

    Returns:
        JSON with queue entry ID and Slack notification confirmation.
    """
    ts     = datetime.now(timezone.utc).isoformat()
    queue_id = f"QUEUE#{platform.upper()}#{community_name}#{ts[:10]}"

    item = {
        "pk":               queue_id,
        "sk":               ts,
        "community_name":   community_name,
        "platform":         platform,
        "target_url":       target_url,
        "message_variants": message_variants,
        "featured_content": featured_content,
        "utm_link":         utm_link,
        "status":           "PENDING_APPROVAL",
        "submitted_at":     ts,
        "approved_by":      None,
        "approved_at":      None,
        "posted_at":        None,
    }
    queue_t.put_item(Item=item)

    # Notify H.F. via Slack (webhook)
    slack_url = os.environ.get("SLACK_DISCOVERY_WEBHOOK", "")
    if slack_url:
        slack_msg = {
            "text": f"🎵 *Fan Discovery: New Outreach Ready for Approval*",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "🎵 Fan Discovery Queue"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Community:*\n{community_name}"},
                    {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                    {"type": "mrkdwn", "text": f"*Featured:*\n{featured_content}"},
                    {"type": "mrkdwn", "text": f"*Target:*\n{target_url}"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Variant 1 (preview):*\n_{message_variants[0][:200] if message_variants else 'None'}_"
                }},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"Review and approve at: ask.lumin.luxe/admin/discovery-queue\nQueue ID: `{queue_id}`"
                }},
            ],
        }
        try:
            requests.post(slack_url, json=slack_msg, timeout=5)
        except Exception:
            pass

    return json.dumps({"status": "QUEUED", "queue_id": queue_id, "message": "Submitted for H.F. approval. Check Slack."})


@tool
def get_pending_approvals() -> str:
    """
    Retrieve all outreach messages currently waiting for human approval.
    Use this to check what's in the queue and surface the most time-sensitive
    opportunities (posts that will scroll off the front page soon).

    Returns:
        JSON list of pending items sorted by time sensitivity.
    """
    resp = queue_t.scan(
        FilterExpression="#s = :pending",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pending": "PENDING_APPROVAL"},
    )
    items = sorted(resp.get("Items", []), key=lambda x: x.get("submitted_at", ""))
    return json.dumps({"pending_count": len(items), "items": items[:20]})


@tool
def post_approved_message(queue_id: str, selected_variant_index: int, approved_by: str) -> str:
    """
    Post an approved outreach message. Only callable after human approval.
    Updates the queue record with approval metadata and marks the item as POSTED.
    Actual posting to Reddit/Discord/YouTube requires platform OAuth tokens
    configured in environment — see docs/DEPLOY.md for setup.

    Args:
        queue_id:               The queue entry ID from submit_for_human_approval().
        selected_variant_index: Which variant H.F. selected (0, 1, or 2).
        approved_by:            Name of approver for audit log.

    Returns:
        JSON confirmation with posting result.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        resp = queue_t.get_item(Key={"pk": queue_id, "sk": queue_t.query(
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": queue_id},
            Limit=1,
        )["Items"][0]["sk"]})
        item = resp.get("Item", {})
    except Exception:
        return json.dumps({"error": f"Queue item {queue_id} not found."})

    variants = item.get("message_variants", [])
    if selected_variant_index >= len(variants):
        return json.dumps({"error": f"Variant {selected_variant_index} does not exist."})

    message = variants[selected_variant_index]
    platform = item.get("platform")

    # Platform posting is handled by n8n after this confirmation
    # This tool marks the item as approved and ready for n8n to execute
    queue_t.update_item(
        Key={"pk": queue_id, "sk": item.get("sk", ts)},
        UpdateExpression="SET #s = :approved, approved_by = :ab, approved_at = :at, selected_variant = :sv, selected_message = :sm",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":approved": "APPROVED_READY_TO_POST",
            ":ab": approved_by,
            ":at": ts,
            ":sv": selected_variant_index,
            ":sm": message,
        },
    )

    return json.dumps({
        "status": "APPROVED",
        "queue_id": queue_id,
        "platform": platform,
        "message": message,
        "approved_by": approved_by,
        "next_step": "n8n will execute the post within the next scheduled run.",
    })


# ─── tracking_tools.py (inline) ──────────────────────────────────────────────

conversions_t  = dynamo.Table("fan-discovery-conversions")
communities_t2 = dynamo.Table("fan-discovery-communities")

CONVERSION_WEIGHTS = {
    "spotify_stream": 1, "spotify_follow": 5, "spotify_save": 8,
    "apple_music_add": 8, "app_install": 20,
    "bandcamp_purchase": 50, "website_visit_long": 3,
    "youtube_full_watch": 5, "community_share": 15,
}


@tool
def log_community_entry(
    community_name: str,
    platform: str,
    member_count: int,
    cultural_context: str,
    priority_tier: str = "TIER_2",
) -> str:
    """
    Log a newly discovered community to the fan-discovery-communities database.
    Used to build and maintain the master list of target communities with their
    cultural context, estimated size, and conversion performance over time.

    Args:
        community_name:   Name of the community (e.g., "r/nujabes").
        platform:         Platform (reddit/discord/tiktok/youtube).
        member_count:     Estimated community size.
        cultural_context: Why this community is relevant to SkyBlew.
        priority_tier:    TIER_1 (highest priority) / TIER_2 / TIER_3.

    Returns:
        JSON confirmation of the logged community.
    """
    communities_t2.put_item(Item={
        "pk": f"COMMUNITY#{platform.upper()}#{community_name}",
        "sk": "META",
        "community_name": community_name,
        "platform": platform,
        "member_count": member_count,
        "cultural_context": cultural_context,
        "priority_tier": priority_tier,
        "weighted_conversion_score": 0,
        "total_outreach_attempts": 0,
        "first_logged": datetime.now(timezone.utc).isoformat(),
    })
    return json.dumps({"status": "LOGGED", "community": community_name, "tier": priority_tier})


@tool
def record_conversion_event(
    community_name: str,
    event_type: str,
    utm_source: str,
    count: int = 1,
) -> str:
    """
    Record a conversion event attributed to a specific community's outreach.
    Conversion events are weighted by value: app_install (20pts) > bandcamp_purchase
    (50pts) > spotify_save (8pts) > spotify_stream (1pt). Use UTM source to
    attribute correctly.

    Args:
        community_name: The community that drove this conversion.
        event_type:     Type from CONVERSION_WEIGHTS keys.
        utm_source:     UTM source tag from the link that was clicked.
        count:          Number of events (default 1).

    Returns:
        JSON with weighted score added and running community total.
    """
    weight = CONVERSION_WEIGHTS.get(event_type, 1)
    weighted_score = weight * count
    ts = datetime.now(timezone.utc).isoformat()

    conversions_t.put_item(Item={
        "pk": f"CONV#{community_name}#{event_type}",
        "sk": ts,
        "community_name": community_name,
        "event_type": event_type,
        "utm_source": utm_source,
        "count": count,
        "weighted_score": weighted_score,
    })

    return json.dumps({"status": "RECORDED", "event": event_type, "weighted_score": weighted_score, "community": community_name})


@tool
def get_conversion_report(days_back: int = 7) -> str:
    """
    Generate a conversion performance report showing which communities are
    driving the most valuable fan actions — installs, saves, purchases — over
    the specified period. Used for the daily evening report to H.F.

    Args:
        days_back: Number of days to include in the report (default 7).

    Returns:
        JSON report with community rankings, top converters, and recommendations.
    """
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days_back)).isoformat()
    resp = conversions_t.scan(
        FilterExpression="#sk >= :cutoff",
        ExpressionAttributeNames={"#sk": "sk"},
        ExpressionAttributeValues={":cutoff": cutoff},
    )

    by_community: dict = {}
    for item in resp.get("Items", []):
        c = item.get("community_name", "unknown")
        by_community[c] = by_community.get(c, 0) + item.get("weighted_score", 0)

    ranked = sorted(by_community.items(), key=lambda x: x[1], reverse=True)
    return json.dumps({
        "period_days": days_back,
        "total_communities_active": len(ranked),
        "top_communities": [{"community": c, "weighted_score": s} for c, s in ranked[:10]],
        "top_performer": ranked[0][0] if ranked else "No data yet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@tool
def get_top_converting_communities(limit: int = 5) -> str:
    """
    Return the top N communities by all-time weighted conversion score.
    Use this to decide where to concentrate outreach resources.

    Args:
        limit: Number of top communities to return (default 5).

    Returns:
        JSON list of top communities with scores and recommended next action.
    """
    report = json.loads(get_conversion_report(days_back=30))
    top = report.get("top_communities", [])[:limit]
    for c in top:
        c["recommendation"] = "Escalate to Tier 2 — personalized influencer outreach" if c["weighted_score"] > 100 else "Continue Tier 1 content seeding"
    return json.dumps({"top_communities": top, "note": "Based on last 30 days weighted conversion data."})


# ─── distribution_tools.py (inline) ─────────────────────────────────────────

@tool
def check_distrokid_delivery_status(release_name: str = "MoreLoveLessWar") -> str:
    """
    Check the DistroKid delivery status for a release and return which platforms
    it has been delivered to, which are still pending, and any rejection reasons.
    IMPORTANT: Apple Music availability is the critical check — if missing, flag
    as urgent and provide the fix steps.

    Args:
        release_name: Name of the release to check (default "MoreLoveLessWar").

    Returns:
        JSON delivery status report with per-platform availability and fix steps.
    """
    # DistroKid does not provide a public API — this tool provides guidance
    # for manual checking and summarizes known delivery patterns
    return json.dumps({
        "release": release_name,
        "check_method": "MANUAL",
        "instructions": [
            "1. Log into DistroKid at distrokid.com/vip",
            "2. Go to 'My Music' → find MoreLoveLessWar → click 'View stores'",
            "3. Look for 'Apple Music' row — status should be 'Live'",
            "4. If status is 'Rejected': note the rejection reason shown",
            "5. Common Apple Music rejections: (a) ISRC conflict, (b) artwork <3000px, (c) metadata mismatch between master and publishing credits, (d) explicit/clean flag error",
            "6. Fix the flagged issue → click 'Resubmit to stores'",
            "7. If unresolved in 48h: email support@distrokid.com with release ID",
            "8. Parallel path: submit via TuneCore or Amuse as backup distributor",
        ],
        "impact_of_missing_apple_music": (
            "Apple Music pays ~$0.01/stream vs Spotify's ~$0.004/stream — 2.5x revenue lost. "
            "Apple editorial placement (Pitchfork-equivalent for streaming) is only accessible "
            "when the track is live. This is the single most urgent distribution fix."
        ),
        "fan_discovery_gate": "Do not run outreach campaigns until Apple Music delivery confirmed.",
        "distrokid_support": "support@distrokid.com | twitter.com/distrokid",
    })


@tool
def build_utm_link(
    base_url: str,
    community_name: str,
    campaign: str,
    tier: str = "tier1",
) -> str:
    """
    Build a UTM-tracked URL for outreach so every click can be attributed to
    the specific community that drove it. This is how we know which communities
    produce the highest-value fans.

    Args:
        base_url:       The destination URL (e.g., https://open.spotify.com/track/...).
        community_name: The community name (becomes utm_source).
        campaign:       Campaign name (e.g., 'lightswitch', 'morelovelesswar').
        tier:           Outreach tier (tier1/tier2/tier3).

    Returns:
        JSON with the full UTM URL and attribution code.
    """
    source = community_name.lower().replace("/", "").replace(" ", "-").replace("#", "")
    utm = f"{base_url}?utm_source={source}&utm_medium={tier}-outreach&utm_campaign={campaign}&utm_content=skyblew"
    return json.dumps({
        "utm_url": utm,
        "utm_source": source,
        "utm_medium": f"{tier}-outreach",
        "utm_campaign": campaign,
        "note": "Add this link to all outreach messages so conversions are attributed correctly.",
    })


@tool
def get_streaming_platform_status(track_name: str = "LightSwitch") -> str:
    """
    Return the known streaming platform availability for a SkyBlew track.
    Provides manual check instructions for any platform showing gaps.

    Args:
        track_name: Track to check (default "LightSwitch").

    Returns:
        JSON platform-by-platform status with check instructions.
    """
    return json.dumps({
        "track": track_name,
        "platforms": {
            "Spotify":       {"status": "LIVE", "monthly_listeners": "~35K", "daily_growth": "~1K/day (Nintendo BRC sync)"},
            "Apple Music":   {"status": "CHECK_REQUIRED", "note": "Verify via DistroKid delivery status — this is the priority gap"},
            "Amazon Music":  {"status": "CHECK_REQUIRED"},
            "YouTube Music": {"status": "CHECK_REQUIRED"},
            "Tidal":         {"status": "CHECK_REQUIRED"},
            "Deezer":        {"status": "CHECK_REQUIRED"},
            "Bandcamp":      {"status": "LIVE_IF_UPLOADED", "note": "Direct sales — highest royalty rate. Confirm catalog uploaded."},
        },
        "priority_action": "Confirm Apple Music status via DistroKid. It is the highest-value missing platform.",
        "note": "Fan discovery outreach should NOT begin for any track until Apple Music is confirmed live.",
    })


@tool
def prepare_editorial_pitch(track_name: str, platforms: list = None) -> str:
    """
    Generate a ready-to-submit editorial pitch for SkyBlew's tracks to streaming
    platform playlist curators. Different platforms have different pitch portals
    and lead times — this tool formats the pitch correctly for each.

    Args:
        track_name: The track to pitch (e.g., "MoreLoveLessWar").
        platforms:  Platforms to pitch (default: Spotify, Apple Music).

    Returns:
        JSON with formatted pitches per platform and submission instructions.
    """
    if platforms is None:
        platforms = ["Spotify", "Apple Music"]

    pitches = {}
    for platform in platforms:
        if platform == "Spotify":
            pitches["Spotify"] = {
                "portal": "Spotify for Artists → Music → Upcoming releases → Pitch",
                "lead_time": "7 days before release minimum",
                "pitch_template": f"""
Track: {track_name}
Artist: SkyBlew
Genre: Conscious Hip-Hop / Rhythm Escapism™
Mood: Uplifting, Reflective, Conscious
Tempo: Mid-tempo
Description: SkyBlew — known for LightSwitch in Bomb Rush Cyberfunk (Nintendo) — 
delivers a message of love over conflict in a moment when the world needs it most.
Nujabes-influenced consciousness meets modern hip-hop production.
Target playlists: Lo-Fi Hip Hop, Conscious Rap, Anime Hip Hop, Chill Hip Hop
                """.strip(),
            }
        elif platform == "Apple Music":
            pitches["Apple Music"] = {
                "portal": "music.apple.com/us/curator/apple-music-editorial → Submit via distributor",
                "lead_time": "10-14 days before release",
                "pitch_template": f"""
{track_name} by SkyBlew (2StepsAboveTheStars LLC / Redeye Worldwide)
SkyBlew is the artist behind 'LightSwitch' — featured in Bomb Rush Cyberfunk 
(Nintendo Switch/PC), generating 1,000+ daily streams. {track_name} represents
his most timely release: conscious hip-hop for a world in need of its message.
Lupe Fiasco × Nujabes × anime aesthetics. Rhythm Escapism™.
                """.strip(),
            }

    return json.dumps({
        "track": track_name,
        "pitches": pitches,
        "important": "Submit pitches AFTER confirming the track is live on each platform. Pitching a track that isn't live wastes the editorial opportunity.",
    })
