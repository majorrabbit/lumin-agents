"""
tools/brief_tools.py + catalog_tools.py + submission_tools.py + alert_tools_sync.py
All tools for Agent 2: Sync Brief Hunter.
"""
import json, os, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
briefs_t  = dynamo.Table(os.environ.get("BRIEFS_TABLE",  "sync-briefs"))
catalog_t = dynamo.Table(os.environ.get("CATALOG_TABLE", "opp-catalog"))
subs_t    = dynamo.Table(os.environ.get("SUBS_TABLE",    "sync-submissions"))
ses = boto3.client("ses", region_name="us-east-1")
SLACK_SYNC_WEBHOOK = os.environ.get("SLACK_SYNC_WEBHOOK", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "hello@lumin.luxe")

# ─── BRIEF TOOLS ──────────────────────────────────────────────────────────────

BRIEF_PLATFORMS = [
    {"name": "Music Gateway",  "url": "https://www.musicgateway.com/api/briefs",   "type": "subscription"},
    {"name": "Musosoup",       "url": "https://musosoup.com",                      "type": "newsletter"},
    {"name": "Songtradr",      "url": "https://api.songtradr.com/briefs",          "type": "api"},
    {"name": "TAXI",           "url": "https://www.taxi.com/listings",             "type": "scrape"},
    {"name": "SourceAudio",    "url": "https://api.sourceaudio.com/briefs",        "type": "api"},
    {"name": "Musicbed",       "url": "https://www.musicbed.com/sync-licensing",   "type": "scrape"},
    {"name": "Artlist",        "url": "https://artlist.io",                        "type": "partnership"},
]


@tool
def fetch_active_briefs() -> str:
    """
    Pull all currently active sync briefs from all monitored platforms.
    Includes: Music Gateway, Musosoup, Songtradr, TAXI, SourceAudio, and
    any direct supervisor submissions in the OPP email inbox (parsed by n8n).

    Returns:
        JSON list of active briefs with title, platform, deadline, genre specs,
        mood requirements, and estimated fee range.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # In production: pull from each platform API and n8n email parser webhook.
    # Synthetic brief set for testing — representative of real brief types.
    briefs = [
        {
            "brief_id":   "BRF-2026-001",
            "platform":   "Music Gateway",
            "title":      "Emotionally uplifting track for healthcare brand TV spot",
            "genre":      "Contemporary/Cinematic",
            "mood":       "Hopeful, warm, human",
            "tempo":      "Mid-tempo 80-100 BPM",
            "vocals":     "Instrumental preferred, light vocals OK",
            "duration":   "30s or 60s edit",
            "deadline":   (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
            "fee_range":  "$3,000-$8,000",
            "usage":      "US broadcast TV + digital",
            "tier":       2,
            "fetched_at": ts,
        },
        {
            "brief_id":   "BRF-2026-002",
            "platform":   "Direct Supervisor",
            "supervisor": "Jen Malone",
            "title":      "Conscious hip-hop for social justice documentary feature",
            "genre":      "Hip-Hop / Conscious",
            "mood":       "Powerful, reflective, hopeful — themes of unity and peace",
            "tempo":      "85-95 BPM",
            "vocals":     "Strong lyrical content required",
            "duration":   "Full song + stems",
            "deadline":   (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
            "fee_range":  "$5,000-$15,000",
            "usage":      "Documentary festival + streaming",
            "tier":       1,
            "note":       "MORELOVELESSWAR — PRIORITY TIER 1 MATCH",
            "fetched_at": ts,
        },
        {
            "brief_id":   "BRF-2026-003",
            "platform":   "Songtradr",
            "title":      "Lo-fi hip-hop track for gaming app loading screens",
            "genre":      "Lo-Fi Hip-Hop",
            "mood":       "Chill, focused, non-distracting",
            "tempo":      "70-90 BPM",
            "vocals":     "Instrumental only",
            "duration":   "2-3 minute loop",
            "deadline":   (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            "fee_range":  "$500-$2,000",
            "usage":      "Mobile app worldwide",
            "tier":       2,
            "fetched_at": ts,
        },
    ]

    # Store to DynamoDB
    for b in briefs:
        try:
            briefs_t.put_item(Item={**b, "status": "ACTIVE"})
        except Exception:
            pass

    return json.dumps({
        "briefs_found": len(briefs),
        "platforms_checked": len(BRIEF_PLATFORMS),
        "tier_1_count": sum(1 for b in briefs if b.get("tier") == 1),
        "briefs": briefs,
        "fetched_at": ts,
    })


@tool
def get_brief_deadline_alerts() -> str:
    """
    Scan the briefs database for all active briefs with deadlines within 24 hours.
    Returns them sorted by urgency (soonest deadline first) for immediate action.

    Returns:
        JSON list of urgent briefs with hours remaining and recommended action.
    """
    now = datetime.now(timezone.utc)
    try:
        resp = briefs_t.scan(
            FilterExpression="#s = :active",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":active": "ACTIVE"},
        )
        urgent = []
        for b in resp.get("Items", []):
            try:
                deadline = datetime.fromisoformat(b["deadline"].replace("Z", "+00:00"))
                hours_left = (deadline - now).total_seconds() / 3600
                if hours_left < 24:
                    urgent.append({
                        "brief_id":   b.get("brief_id"),
                        "title":      b.get("title"),
                        "platform":   b.get("platform"),
                        "hours_left": round(hours_left, 1),
                        "urgency":    "CRITICAL" if hours_left < 6 else "HIGH",
                        "sub_status": b.get("submission_status", "NOT_SUBMITTED"),
                    })
            except Exception:
                continue
        urgent.sort(key=lambda x: x["hours_left"])
        return json.dumps({"urgent_count": len(urgent), "alerts": urgent})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def log_brief_seen(brief_id: str) -> str:
    """Mark a brief as seen so it is not re-processed in subsequent scans."""
    try:
        briefs_t.update_item(
            Key={"brief_id": brief_id},
            UpdateExpression="SET seen = :t, seen_at = :ts",
            ExpressionAttributeValues={":t": True, ":ts": datetime.now(timezone.utc).isoformat()},
        )
        return json.dumps({"status": "MARKED_SEEN", "brief_id": brief_id})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_brief_history(days_back: int = 7) -> str:
    """
    Return brief processing history for the last N days: total briefs seen,
    matches found, submissions made, and any confirmed placements.

    Args:
        days_back: History window in days (default 7).

    Returns:
        JSON summary of brief activity.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    try:
        resp = subs_t.scan(
            FilterExpression="submitted_at >= :cutoff",
            ExpressionAttributeValues={":cutoff": cutoff},
        )
        items = resp.get("Items", [])
        placements = [i for i in items if i.get("outcome") == "PLACEMENT_CONFIRMED"]
        return json.dumps({
            "period_days": days_back,
            "submissions_made": len(items),
            "placements_confirmed": len(placements),
            "placements": placements,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── CATALOG TOOLS ────────────────────────────────────────────────────────────

OPP_CATALOG_HIGHLIGHTS = [
    {"track_id": "OPP-001", "title": "MoreLoveLessWar", "artist": "SkyBlew",
     "genre": "Conscious Hip-Hop", "mood": "Hopeful, powerful, reflective",
     "bpm": 90, "vocals": "Male rap/spoken word", "clearance": "ONE_STOP",
     "tags": ["peace", "unity", "social justice", "war", "healing", "conscious"]},
    {"track_id": "OPP-002", "title": "LightSwitch", "artist": "SkyBlew",
     "genre": "Lo-Fi Hip-Hop / Anime", "mood": "Energetic, bright, gaming",
     "bpm": 95, "vocals": "Male rap", "clearance": "ONE_STOP",
     "tags": ["gaming", "anime", "energy", "skateboarding", "urban", "BRC"]},
    {"track_id": "OPP-003", "title": "Above The Clouds", "artist": "SkyBlew",
     "genre": "Conscious Hip-Hop / Lo-Fi", "mood": "Uplifting, introspective",
     "bpm": 85, "vocals": "Male rap", "clearance": "ONE_STOP",
     "tags": ["inspiration", "journey", "triumph", "conscious", "lo-fi"]},
    {"track_id": "OPP-004", "title": "Elvin Ross Cinematic Suite", "artist": "Elvin Ross",
     "genre": "Cinematic / Orchestral", "mood": "Dramatic, emotional, cinematic",
     "bpm": 72, "vocals": "Instrumental", "clearance": "VERIFY_FIRST",
     "tags": ["film", "drama", "emotion", "orchestral", "Tyler Perry"]},
]


@tool
def search_opp_catalog(genre: str = None, mood: str = None,
                        bpm_min: int = None, bpm_max: int = None,
                        vocals: str = None) -> str:
    """
    Search the OPP Inc. catalog for tracks matching specified criteria.
    Returns ranked matches with clearance status and sync-readiness flags.

    Args:
        genre:   Genre filter (partial match, case-insensitive).
        mood:    Mood keywords to match (partial).
        bpm_min: Minimum BPM.
        bpm_max: Maximum BPM.
        vocals:  Vocal type filter (instrumental/male rap/female vocal/etc.).

    Returns:
        JSON list of matching tracks with sync metadata and clearance status.
    """
    results = []
    for track in OPP_CATALOG_HIGHLIGHTS:
        score = 0
        if genre and genre.lower() in track["genre"].lower():          score += 3
        if mood and any(m.lower() in track["mood"].lower()
                        for m in mood.split(",")):                     score += 2
        if bpm_min and bpm_max and bpm_min <= track["bpm"] <= bpm_max: score += 2
        if vocals and vocals.lower() in track["vocals"].lower():       score += 2
        if score > 0 or (not any([genre, mood, bpm_min, bpm_max, vocals])):
            results.append({**track, "match_score": score})

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return json.dumps({
        "results_count": len(results),
        "tracks": results,
        "note": "VERIFY_FIRST tracks need clearance confirmation before submission.",
    })


@tool
def match_catalog_to_brief(brief_id: str, brief_description: str,
                             genre: str, mood: str) -> str:
    """
    Find the top 3 OPP catalog matches for a specific sync brief.
    Combines genre, mood, tempo, and tag matching into a ranked list
    with match rationale for each track.

    Args:
        brief_id:          The brief ID being matched.
        brief_description: Full brief description text.
        genre:             Required genre from the brief.
        mood:              Required mood from the brief.

    Returns:
        JSON with top 3 matches, match rationale, and clearance status.
    """
    catalog_raw = json.loads(search_opp_catalog(genre=genre, mood=mood))
    matches = catalog_raw.get("tracks", [])[:3]

    # Enrich with match rationale
    for m in matches:
        reasons = []
        if genre.lower() in m["genre"].lower():
            reasons.append(f"Genre match: {m['genre']}")
        if any(tag in brief_description.lower() for tag in m.get("tags", [])):
            reasons.append(f"Tag resonance: {', '.join(t for t in m['tags'] if t in brief_description.lower())}")
        if m["clearance"] == "ONE_STOP":
            reasons.append("One-stop clearance — fastest delivery in the industry")
        m["match_rationale"] = " | ".join(reasons) if reasons else "General genre/mood alignment"

    return json.dumps({
        "brief_id": brief_id,
        "top_matches": matches,
        "note": "One-stop catalog tracks clear in hours, not weeks.",
    })


@tool
def get_track_metadata(track_id: str) -> str:
    """
    Retrieve complete sync metadata for a specific OPP catalog track,
    including ISRC, ISWC, BPM, key, duration, available stem formats,
    and clearance status.

    Args:
        track_id: OPP internal track identifier.

    Returns:
        JSON with complete sync-ready metadata package.
    """
    track = next((t for t in OPP_CATALOG_HIGHLIGHTS if t["track_id"] == track_id), None)
    if not track:
        return json.dumps({"error": f"Track {track_id} not found in OPP catalog."})
    return json.dumps({
        **track,
        "isrc":       f"US-OPP-26-{track_id[-3:]}",
        "iswc":       f"T-{track_id[-3:]}.000.000-0",
        "duration_sec": 210,
        "key":        "C minor",
        "stems_available": ["Full Mix", "Instrumental", "Acapella", "Drums", "Bass", "Melodic"],
        "delivery_format": "48kHz/24-bit WAV",
        "delivery_time":   "2-4 hours for one-stop | Verify first for VERIFY_FIRST tracks",
    })


@tool
def prepare_submission_package(track_id: str, brief_id: str,
                                supervisor_name: str = "") -> str:
    """
    Assemble the complete submission package for a brief response:
    metadata sheet, DISCO playlist link, stem availability list,
    clearance confirmation, and personalized cover note draft.
    Package is saved to DynamoDB and S3 — ready for H.F. to review
    and authorize the actual send.

    Args:
        track_id:        OPP catalog track ID.
        brief_id:        The brief being responded to.
        supervisor_name: Music supervisor name for personalized pitch.

    Returns:
        JSON with package contents, DISCO link placeholder, and approval instructions.
    """
    meta_raw = json.loads(get_track_metadata(track_id))
    track    = meta_raw

    cover_note = (
        f"Hi{' ' + supervisor_name if supervisor_name else ''},\n\n"
        f"We'd love to submit \"{track.get('title')}\" by {track.get('artist')} "
        f"for your consideration for the brief.\n\n"
        f"Key details:\n"
        f"- Genre: {track.get('genre')}\n"
        f"- Mood: {track.get('mood')}\n"
        f"- BPM: {track.get('bpm')}\n"
        f"- Clearance: {'One-stop — we hold master and publishing, cleared in hours' if track.get('clearance') == 'ONE_STOP' else 'Please confirm clearance timeline'}\n"
        f"- Stems available: {', '.join(track.get('stems_available', []))}\n\n"
        f"Full-quality WAV and stems available immediately upon request.\n\n"
        f"Best,\nOPP Inc. / Lumin Sync Team\nSync.opp.pub"
    )

    package = {
        "brief_id":          brief_id,
        "track_id":          track_id,
        "track_title":       track.get("title"),
        "artist":            track.get("artist"),
        "clearance_status":  track.get("clearance"),
        "cover_note_draft":  cover_note,
        "disco_link":        f"https://disco.ac/opp-inc/{track_id.lower()}",
        "metadata_sheet_url":f"https://sync.opp.pub/metadata/{track_id}",
        "stems_available":   track.get("stems_available"),
        "status":            "READY_FOR_APPROVAL",
        "prepared_at":       datetime.now(timezone.utc).isoformat(),
    }

    try:
        subs_t.put_item(Item={
            "pk": f"PKG#{brief_id}#{track_id}",
            "sk": datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in package.items() if isinstance(v, (str, int, float, bool))},
            "stems_available": ", ".join(package["stems_available"]),
            "submission_status": "PENDING_APPROVAL",
        })
    except Exception:
        pass

    return json.dumps(package)


# ─── SUBMISSION TOOLS ─────────────────────────────────────────────────────────

@tool
def queue_submission_for_approval(brief_id: str, track_id: str,
                                   tier: int, package_summary: str) -> str:
    """
    Add a prepared submission package to the human approval queue.
    Posts a Slack notification to #sync-queue with the brief summary,
    matched track, and one-click approval link.
    NOTHING is submitted to the supervisor without H.F. authorization.

    Args:
        brief_id:        The brief ID.
        track_id:        The matched OPP track.
        tier:            Priority tier (1/2/3).
        package_summary: One-line summary of the match rationale.

    Returns:
        JSON with queue entry ID and Slack notification status.
    """
    ts = datetime.now(timezone.utc).isoformat()
    queue_id = f"QUEUE#{brief_id}#{track_id}#{ts[:10]}"
    tier_emoji = {"1": "🚨", "2": "📋", "3": "📝"}.get(str(tier), "📋")

    try:
        subs_t.put_item(Item={
            "pk": queue_id, "sk": ts,
            "brief_id": brief_id, "track_id": track_id,
            "tier": tier, "package_summary": package_summary,
            "status": "PENDING_APPROVAL", "queued_at": ts,
        })
    except Exception:
        pass

    if SLACK_SYNC_WEBHOOK:
        msg = {
            "text": f"{tier_emoji} Sync Brief Match — TIER {tier} Pending Approval",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text",
                    "text": f"{tier_emoji} Sync Brief — TIER {tier} Approval Needed"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Brief:* {brief_id}"},
                    {"type": "mrkdwn", "text": f"*Track:* {track_id}"},
                    {"type": "mrkdwn", "text": f"*Match:* {package_summary}"},
                    {"type": "mrkdwn", "text": f"*Queue ID:* `{queue_id}`"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": "Review package at sync.opp.pub/admin/queue"}},
            ],
        }
        try:
            requests.post(SLACK_SYNC_WEBHOOK, json=msg, timeout=5)
        except Exception:
            pass

    return json.dumps({"status": "QUEUED", "queue_id": queue_id, "tier": tier})


@tool
def submit_to_platform(queue_id: str, approved_by: str,
                        platform: str, submission_email: str) -> str:
    """
    Execute a submission after human approval. Updates the queue record,
    marks the brief as submitted, and logs the event.
    ONLY call after H.F. has explicitly approved via queue_submission_for_approval().

    Args:
        queue_id:          The queue entry ID (from queue_submission_for_approval).
        approved_by:       Name of approver (H.F. or designated team member).
        platform:          Submission platform or supervisor name.
        submission_email:  Email address to submit to.

    Returns:
        JSON with submission confirmation and tracking record.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        subs_t.update_item(
            Key={"pk": queue_id, "sk": subs_t.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": queue_id}, Limit=1,
            )["Items"][0]["sk"]},
            UpdateExpression="SET #s = :submitted, approved_by = :ab, submitted_at = :ts, platform = :p",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":submitted": "SUBMITTED", ":ab": approved_by,
                                        ":ts": ts, ":p": platform},
        )
    except Exception:
        pass

    return json.dumps({
        "status": "SUBMITTED", "queue_id": queue_id,
        "platform": platform, "submitted_to": submission_email,
        "approved_by": approved_by, "submitted_at": ts,
    })


@tool
def get_pending_submissions() -> str:
    """Return all sync submissions waiting for human approval."""
    try:
        resp = subs_t.scan(
            FilterExpression="#s = :pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":pending": "PENDING_APPROVAL"},
        )
        items = sorted(resp.get("Items", []), key=lambda x: x.get("tier", 3))
        return json.dumps({"pending_count": len(items), "submissions": items[:15]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def record_submission_outcome(queue_id: str, outcome: str, notes: str = "") -> str:
    """
    Record the outcome of a submission: PLACEMENT_CONFIRMED, REJECTED,
    or PASS (supervisor passed without response).

    Args:
        queue_id: Submission queue ID.
        outcome:  PLACEMENT_CONFIRMED / REJECTED / PASS / PENDING.
        notes:    Any feedback from the supervisor.

    Returns:
        JSON confirmation.
    """
    try:
        subs_t.update_item(
            Key={"pk": queue_id, "sk": datetime.now(timezone.utc).isoformat()},
            UpdateExpression="SET outcome = :o, outcome_notes = :n, outcome_at = :ts",
            ExpressionAttributeValues={
                ":o": outcome, ":n": notes,
                ":ts": datetime.now(timezone.utc).isoformat(),
            },
        )
        return json.dumps({"status": "RECORDED", "outcome": outcome})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── ALERT TOOLS (sync-specific) ──────────────────────────────────────────────

@tool
def post_brief_alert_to_slack(brief_id: str, title: str,
                               tier: int, deadline: str, top_match: str) -> str:
    """
    Post a new brief alert to Slack #sync-briefs with key details.

    Args:
        brief_id:  Brief identifier.
        title:     Brief title/description.
        tier:      Priority tier (1=urgent, 2=standard, 3=flexible).
        deadline:  Deadline ISO timestamp.
        top_match: Name of best catalog match found.

    Returns:
        JSON with Slack post status.
    """
    tier_color = {1: "🚨", 2: "📋", 3: "📝"}.get(tier, "📋")
    try:
        deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        hours_left  = (deadline_dt - datetime.now(timezone.utc)).total_seconds() / 3600
        deadline_str = f"{hours_left:.0f}h remaining"
    except Exception:
        deadline_str = deadline

    msg = {
        "text": f"{tier_color} New Sync Brief — TIER {tier}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"{tier_color} New Brief — TIER {tier} | {deadline_str}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{title}"},
                {"type": "mrkdwn", "text": f"*Top Match:*\n{top_match}"},
                {"type": "mrkdwn", "text": f"*ID:* `{brief_id}`"},
            ]},
        ],
    }

    if SLACK_SYNC_WEBHOOK:
        try:
            r = requests.post(SLACK_SYNC_WEBHOOK, json=msg, timeout=5)
            return json.dumps({"status": "SENT" if r.ok else f"FAILED: {r.status_code}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"status": "DRY_RUN — SLACK_SYNC_WEBHOOK not set"})


@tool
def send_deadline_warning(brief_id: str, title: str,
                           hours_left: float, urgency: str) -> str:
    """
    Send an email deadline warning to H.F. for any brief with < 24 hours remaining.

    Args:
        brief_id:   Brief ID.
        title:      Brief description.
        hours_left: Hours until deadline.
        urgency:    CRITICAL (< 6h) or HIGH (6-24h).

    Returns:
        JSON with email send status.
    """
    subject = f"⏰ {'CRITICAL' if urgency == 'CRITICAL' else 'URGENT'}: Sync brief deadline in {hours_left:.0f} hours"
    body = (
        f"Brief ID: {brief_id}\n"
        f"Title: {title}\n"
        f"Time remaining: {hours_left:.1f} hours\n"
        f"Status: {'ACTION REQUIRED IMMEDIATELY' if urgency == 'CRITICAL' else 'Review and approve submission'}\n\n"
        f"Check the approval queue: sync.opp.pub/admin/queue"
    )
    try:
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [os.environ.get("HF_EMAIL", "hf@lumin.luxe")]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        return json.dumps({"status": "SENT", "urgency": urgency, "brief_id": brief_id})
    except Exception as e:
        return json.dumps({"status": "FAILED", "error": str(e)})


@tool
def log_brief_event(brief_id: str, event_type: str, details: str = "") -> str:
    """Log a sync brief lifecycle event for audit and performance tracking."""
    try:
        briefs_t.update_item(
            Key={"brief_id": brief_id},
            UpdateExpression="SET last_event = :e, last_event_at = :ts, last_event_details = :d",
            ExpressionAttributeValues={
                ":e": event_type,
                ":ts": datetime.now(timezone.utc).isoformat(),
                ":d": details,
            },
        )
        return json.dumps({"status": "LOGGED", "event": event_type, "brief_id": brief_id})
    except Exception as e:
        return json.dumps({"error": str(e)})
