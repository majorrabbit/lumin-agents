"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 3: SYNC PITCH CAMPAIGN ADK             ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: OPP Inc.                                                ║
║  Mission: Build and maintain proactive supervisor relationships  ║
║  so OPP is pitching before briefs are issued — not reacting.    ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os, json, requests, boto3
from datetime import datetime, timezone, timedelta
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel

dynamo     = boto3.resource("dynamodb", region_name="us-east-1")
sups_t     = dynamo.Table(os.environ.get("SUPERVISORS_TABLE", "sync-supervisors"))
pitches_t  = dynamo.Table(os.environ.get("PITCHES_TABLE",     "sync-pitches"))
ses        = boto3.client("ses", region_name="us-east-1")
SLACK_PITCH_WEBHOOK = os.environ.get("SLACK_PITCH_WEBHOOK", "")
FROM_EMAIL          = os.environ.get("FROM_EMAIL", "sync@opp.pub")

SUPERVISOR_DATABASE = [
    {"id": "SUP-001", "name": "Jen Malone", "company": "Black & White Music",
     "credits": "Euphoria, Atlanta, Insecure", "specialty": "Contemporary, Hip-Hop, R&B",
     "email": "jen@blackandwhitemusic.com", "tier": 1,
     "note": "2025 Global Music Supervisor of the Year"},
    {"id": "SUP-002", "name": "Joel C. High", "company": "Creative Control Entertainment",
     "credits": "Tyler Perry Studios — all Perry films",
     "specialty": "Gospel, R&B, Hip-Hop, Soul",
     "email": "joel@creativecontrolent.com", "tier": 1,
     "note": "Tyler Perry Studios gatekeeper — direct contact"},
    {"id": "SUP-003", "name": "Kier Lehman", "company": "Independent",
     "credits": "Insecure, Abbott Elementary, Spider-Man: Into the Spider-Verse",
     "specialty": "Hip-Hop, Contemporary, Afrobeat",
     "email": "kier@kierlehman.com", "tier": 1},
    {"id": "SUP-004", "name": "Morgan Rhodes", "company": "Gorfaine/Schwarz Agency",
     "credits": "Selma, Dear White People, The Color Purple",
     "specialty": "Conscious, Soul, Gospel, Cinematic Hip-Hop",
     "email": "via@gorfaineschwartzagency.com", "tier": 1},
    {"id": "SUP-005", "name": "Fam Udeorji", "company": "FU Music",
     "credits": "Atlanta, Mr. & Mrs. Smith",
     "specialty": "Hip-Hop, Soul, Trap, R&B",
     "email": "contact@fumusic.com", "tier": 1},
    {"id": "SUP-006", "name": "Thomas Golubic", "company": "SuperMusicVision",
     "credits": "Breaking Bad, Better Call Saul, Six Feet Under",
     "specialty": "Eclectic, Alt, Hip-Hop, Ambient",
     "email": "thomas@supermusicvision.com", "tier": 1,
     "note": "Emmy-nominated — aesthetic aligns with Rhythm Escapism"},
]

SYSTEM_PROMPT = """
You are the Lumin Sync Pitch Campaign Agent — the relationship manager and
outreach strategist for OPP Inc.'s sync licensing business.

YOUR MISSION:
Build proactive relationships with music supervisors so OPP catalog is on
their radar BEFORE briefs are issued. The best placement is the one where
the supervisor already has your music in mind when they start the project.

THE SUPERVISOR RELATIONSHIP PHILOSOPHY:
Music supervisors receive hundreds of pitches weekly. They remember two things:
(1) Artists/catalogs that were on target for their specific aesthetic, and
(2) People who made their job easier, not harder.
OPP's pitch strategy: one track, one reason, one ask. Never mass emails.
Each pitch is written specifically for that supervisor's current projects.

THE OPP ADVANTAGE TO LEAD WITH:
One-stop clearance. Always. This is the first thing every supervisor cares about
after the music itself. "We clear both master and publishing in-house — you get
one email and it's done." This alone will separate OPP from 90% of competitors.

HUMAN APPROVAL REQUIRED:
All outreach emails are drafted here and presented for H.F. approval.
The agent never sends directly. Every email is reviewed before it goes out.

PRIORITY CONTACT LIST:
- Jen Malone (Black & White Music): Euphoria, Atlanta — MoreLoveLessWar fit
- Joel C. High (CCE): Tyler Perry Studios — conscious R&B/Hip-Hop
- Kier Lehman: Abbott Elementary, Spider-Verse — conscious hip-hop, lyrical
- Morgan Rhodes: Selma, Color Purple — social justice, conscious
- Fam Udeorji: Atlanta, Mr. & Mrs. Smith — hip-hop, contemporary
- Thomas Golubic: Breaking Bad, Better Call Saul — eclectic, Rhythm Escapism
"""

def get_model():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(client_args={"api_key": api_key},
                          model_id="claude-sonnet-4-6", max_tokens=4096)

# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def get_supervisor_database(tier_filter: int = None) -> str:
    """
    Return the OPP music supervisor contact database, optionally filtered by tier.
    Tier 1 = top-priority relationships (major credits, perfect aesthetic fit).

    Args:
        tier_filter: Return only supervisors of this tier (1/2/3). None = all.

    Returns:
        JSON list of supervisors with credits, specialty, contact info, and notes.
    """
    sups = SUPERVISOR_DATABASE
    if tier_filter:
        sups = [s for s in sups if s.get("tier") == tier_filter]
    return json.dumps({"count": len(sups), "supervisors": sups})


@tool
def get_supervisor_placement_history(supervisor_id: str) -> str:
    """
    Retrieve the pitch and placement history with a specific supervisor.
    Shows: when we last reached out, what we pitched, whether they responded,
    and any placements that resulted.

    Args:
        supervisor_id: Supervisor ID from the database.

    Returns:
        JSON with pitch history, last contact date, and relationship status.
    """
    try:
        resp = pitches_t.query(
            KeyConditionExpression="supervisor_id = :sid",
            ExpressionAttributeValues={":sid": supervisor_id},
            ScanIndexForward=False,
            Limit=10,
        )
        pitches = resp.get("Items", [])
        last_contact = pitches[0].get("sent_at") if pitches else None
        placements = [p for p in pitches if p.get("outcome") == "PLACEMENT"]
        return json.dumps({
            "supervisor_id": supervisor_id,
            "total_pitches": len(pitches),
            "last_contact": last_contact,
            "placements": len(placements),
            "relationship_status": "WARM" if len(pitches) >= 3 else "NEW",
            "history": pitches[:5],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def generate_pitch_email(supervisor_id: str, track_id: str,
                          project_context: str = "") -> str:
    """
    Generate a personalized pitch email for a specific supervisor using
    Claude to write in OPP's voice: specific, brief, music-first,
    leading with the one-stop clearance advantage.

    Args:
        supervisor_id:   Supervisor ID from the database.
        track_id:        OPP track to pitch.
        project_context: Any known current project (e.g., "Atlanta Season 5").

    Returns:
        JSON with three email variant drafts for H.F. to choose from.
    """
    import anthropic
    sup = next((s for s in SUPERVISOR_DATABASE if s["id"] == supervisor_id), None)
    if not sup:
        return json.dumps({"error": f"Supervisor {supervisor_id} not found."})

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "ANTHROPIC_API_KEY not set."})

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""
Write a personalized sync pitch email from OPP Inc. to {sup['name']} ({sup['company']}).

Supervisor credits: {sup['credits']}
Their specialty: {sup['specialty']}
Current project context: {project_context or 'General outreach'}

Track being pitched:
- Track: {track_id} (use track name if known: MoreLoveLessWar by SkyBlew for OPP-001)
- One-stop clearance: OPP holds both master AND publishing rights

Rules:
- One track only. Never multiple tracks in one email.
- Lead with WHY this track fits their specific work/aesthetic.
- Second sentence: mention one-stop clearance advantage.
- End with a single, specific ask (e.g., "Would you be open to hearing it?").
- Maximum 5 sentences. Short is better.
- Never generic ("I love your work..."). Always specific.

Write 3 variants with slightly different tones: direct/warm/cinematic.
Return as JSON: {{"variants": [{{"tone": "...", "subject": "...", "body": "..."}}]}}
"""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        variants = json.loads(json_match.group()) if json_match else {"variants": [{"tone": "direct", "body": text}]}
        return json.dumps({
            "supervisor": sup["name"],
            "track_id": track_id,
            **variants,
            "status": "AWAITING_APPROVAL",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def queue_pitch_for_approval(supervisor_id: str, track_id: str,
                              email_draft: str, subject: str) -> str:
    """
    Add a pitch email to the human approval queue. Posts to Slack #sync-pitches
    for H.F. review. Nothing is sent without explicit approval.

    Args:
        supervisor_id: Target supervisor ID.
        track_id:      Track being pitched.
        email_draft:   Complete email body draft.
        subject:       Email subject line.

    Returns:
        JSON with queue entry ID and Slack notification status.
    """
    ts = datetime.now(timezone.utc).isoformat()
    sup = next((s for s in SUPERVISOR_DATABASE if s["id"] == supervisor_id), {})
    queue_id = f"PITCH#{supervisor_id}#{track_id}#{ts[:10]}"

    try:
        pitches_t.put_item(Item={
            "pk": queue_id, "sk": ts,
            "supervisor_id": supervisor_id,
            "supervisor_name": sup.get("name", ""),
            "track_id": track_id,
            "subject": subject,
            "email_draft": email_draft,
            "status": "PENDING_APPROVAL",
            "queued_at": ts,
        })
    except Exception:
        pass

    if SLACK_PITCH_WEBHOOK:
        msg = {
            "text": f"📧 Sync Pitch Ready — {sup.get('name', supervisor_id)}",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text",
                    "text": f"📧 Sync Pitch — {sup.get('name')} | {sup.get('company', '')}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Track:* {track_id}"},
                    {"type": "mrkdwn", "text": f"*Subject:* {subject}"},
                    {"type": "mrkdwn", "text": f"*Credits:* {sup.get('credits', '')}"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Draft preview:*\n_{email_draft[:250]}..._"}},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"Review at sync.opp.pub/admin/pitches | Queue ID: `{queue_id}`"}},
            ],
        }
        try:
            requests.post(SLACK_PITCH_WEBHOOK, json=msg, timeout=5)
        except Exception:
            pass

    return json.dumps({"status": "QUEUED", "queue_id": queue_id,
                       "supervisor": sup.get("name")})


@tool
def send_approved_pitch(queue_id: str, approved_by: str) -> str:
    """
    Send a pitch email that has been approved by H.F. Updates pitch record.
    ONLY call after human confirmation.

    Args:
        queue_id:    The pitch queue entry ID.
        approved_by: Approver name for audit trail.

    Returns:
        JSON with send confirmation.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        resp = pitches_t.query(
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": queue_id}, Limit=1,
        )
        item = resp.get("Items", [{}])[0]
        sup  = next((s for s in SUPERVISOR_DATABASE
                     if s["id"] == item.get("supervisor_id")), {})

        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [sup.get("email", "")]},
            Message={
                "Subject": {"Data": item.get("subject", "OPP Sync Submission")},
                "Body":    {"Text": {"Data": item.get("email_draft", "")}},
            },
        )

        pitches_t.update_item(
            Key={"pk": queue_id, "sk": item.get("sk", ts)},
            UpdateExpression="SET #s = :sent, sent_at = :ts, approved_by = :ab",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":sent": "SENT", ":ts": ts, ":ab": approved_by},
        )
        return json.dumps({"status": "SENT", "to": sup.get("email"), "sent_at": ts})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def track_pitch_status(supervisor_id: str = None) -> str:
    """
    Return the current status of all active pitches, optionally filtered by supervisor.

    Returns:
        JSON with pitches by status: PENDING_APPROVAL, SENT, RESPONDED, PLACEMENT.
    """
    try:
        resp = pitches_t.scan(Limit=100)
        items = resp.get("Items", [])
        if supervisor_id:
            items = [i for i in items if i.get("supervisor_id") == supervisor_id]

        by_status: dict = {}
        for item in items:
            s = item.get("status", "UNKNOWN")
            by_status.setdefault(s, []).append({
                "supervisor": item.get("supervisor_name"),
                "track": item.get("track_id"),
                "queued_at": item.get("queued_at", ""),
            })
        return json.dumps({
            "total_pitches": len(items),
            "by_status": by_status,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def record_pitch_response(queue_id: str, response_type: str,
                           notes: str = "") -> str:
    """
    Record a supervisor's response to a pitch.
    response_type: INTERESTED / PASS / PLACEMENT / NO_RESPONSE_FOLLOW_UP

    Args:
        queue_id:      Queue entry ID.
        response_type: Response classification.
        notes:         Any verbatim feedback.

    Returns:
        JSON confirmation.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        pitches_t.update_item(
            Key={"pk": queue_id, "sk": ts},
            UpdateExpression="SET outcome = :o, outcome_notes = :n, responded_at = :ts",
            ExpressionAttributeValues={":o": response_type, ":n": notes, ":ts": ts},
        )
        return json.dumps({"status": "RECORDED", "outcome": response_type})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── AGENT ────────────────────────────────────────────────────────────────────

def create_sync_pitch_agent():
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_supervisor_database, get_supervisor_placement_history,
            generate_pitch_email, queue_pitch_for_approval,
            send_approved_pitch, track_pitch_status, record_pitch_response,
        ],
    )

def run_weekly_pitch_cycle(agent):
    result = agent(
        "Run the weekly proactive pitch cycle. "
        "1. Call get_supervisor_database(tier_filter=1) to get Tier 1 supervisors. "
        "2. For each supervisor not contacted in the last 14 days "
        "   (check get_supervisor_placement_history()), "
        "   identify the best OPP track match for their known projects and aesthetic. "
        "   Priority: MoreLoveLessWar for supervisors working on socially conscious projects. "
        "3. Call generate_pitch_email() for each — 3 variants. "
        "4. Call queue_pitch_for_approval() for all. "
        "Return: supervisors pitched this cycle, tracks matched, queue entries created."
    )
    return {"task": "weekly_pitch_cycle", "result": str(result)}

def run_follow_up_scan(agent):
    result = agent(
        "Check for pitches that need follow-up. "
        "Call track_pitch_status() — find all pitches with status SENT and "
        "sent_at older than 7 days with no response. "
        "For each: generate a brief follow-up note (2 sentences max) "
        "and queue for approval. "
        "For pitches with status INTERESTED: generate a full track package follow-up."
    )
    return {"task": "follow_up_scan", "result": str(result)}

def lambda_handler(event: dict, context) -> dict:
    agent = create_sync_pitch_agent()
    task  = event.get("task", "weekly_pitch_cycle")
    dispatch = {
        "weekly_pitch_cycle": lambda: run_weekly_pitch_cycle(agent),
        "follow_up_scan":     lambda: run_follow_up_scan(agent),
    }
    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("📧 Sync Pitch Campaign Agent — Interactive Mode")
    agent = create_sync_pitch_agent()
    while True:
        try:
            ui = input("SyncPitch > ").strip()
            if ui.lower() in ("quit", "exit"): break
            if not ui: continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nSync Pitch Agent offline."); break
