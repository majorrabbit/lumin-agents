"""
Per-agent approval queue helper for the Lumin MAS fleet.

WHY THIS EXISTS:
Three agents (9 CS, 11 Fan Discovery, 12 Social Media) require human approval
before taking public-facing actions. A fourth (Agent 3 Sync Pitch) drafts
emails for H.F. review. Each has its own DynamoDB queue table and its own
Slack webhook. Without a shared helper, each agent implements the same
"write to queue → post Slack alert → return ID → agent exits" dance slightly
differently.

KEY DESIGN DECISIONS:
- Per-agent isolation: every call takes table_name and webhook_env explicitly.
  There is no global approval table. See PATTERNS.md §6.
- Non-blocking: submit_for_approval writes the record and posts the alert,
  then returns immediately with an approval_id. The agent does not poll.
- TTL: every pending record has a 7-day DynamoDB TTL. Stale items clean up
  automatically without requiring a maintenance job.
- Urgency → severity mapping keeps Slack alerts visually consistent with the
  post_alert() severity levels in shared.slack.

STATUS LIFECYCLE:
  PENDING → APPROVED → EXECUTED
         → EDITED   → EXECUTED   (H.F. approved with changes)
         → DECLINED              (H.F. said no)
  PENDING → EXPIRED              (7-day TTL hit, DynamoDB auto-deletes)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from boto3.dynamodb.conditions import Attr, Key

from shared.dynamo import coerce_floats, now_iso, table as dynamo_table
from shared.slack import post_alert

logger = logging.getLogger(__name__)

# Map submission urgency to slack severity
_URGENCY_SEVERITY: dict[str, str] = {
    "low":    "info",
    "normal": "low",
    "high":   "medium",
    "urgent": "high",
}

VALID_STATUSES = frozenset({
    "PENDING", "APPROVED", "EDITED", "DECLINED", "EXECUTED", "EXPIRED",
})


def submit_for_approval(
    *,
    table_name: str,
    webhook_env: str,
    agent: str,
    action_type: str,
    summary: str,
    payload: dict[str, Any],
    rationale: str,
    urgency: str = "normal",
    deadline_iso: Optional[str] = None,
) -> str:
    """
    Queue an action for human approval and notify H.F. via Slack.

    The function writes one DynamoDB record, posts one Slack alert, and
    returns. It does NOT block or poll. The agent records the returned
    approval_id and exits — H.F.'s Slack interaction updates the record
    via mark_status().

    Args:
        table_name:   DynamoDB queue table for this agent.
                      e.g. "skyblew-approval-queue" (Agent 12)
        webhook_env:  Env var name holding this agent's Slack webhook URL.
                      e.g. "SLACK_APPROVAL_WEBHOOK"
        agent:        Agent identifier. e.g. "agent12-social-media"
        action_type:  Short action label. e.g. "post_instagram", "send_pitch"
        summary:      One-sentence human description of the proposed action.
        payload:      Full action data to execute if approved. Stored as-is.
        rationale:    Why this action should happen. Shown in the Slack alert.
        urgency:      low | normal | high | urgent. Controls Slack severity.
        deadline_iso: Optional ISO timestamp by which approval is needed.
                      Shown in the Slack alert for time-sensitive items.

    Returns:
        approval_id (UUID string). Store this to correlate approval events.

    Example:
        approval_id = submit_for_approval(
            table_name="skyblew-approval-queue",
            webhook_env="SLACK_APPROVAL_WEBHOOK",
            agent="agent12-social-media",
            action_type="post_tiktok",
            summary="Post MoreLoveLessWar clip during #ceasefire trending peak",
            payload={"platform": "tiktok", "content": "..."},
            rationale="Cultural moment PEAK — Agent 6 confidence 0.91",
            urgency="urgent",
            deadline_iso="2026-04-12T18:00:00Z",
        )
    """
    approval_id = str(uuid.uuid4())
    ts = now_iso()
    tbl = ttl_epoch = None

    # TTL: 7 days from now (epoch integer, as DynamoDB requires)
    ttl_epoch = int(
        (datetime.now(timezone.utc) + timedelta(days=7)).timestamp()
    )

    record = {
        "pk": f"APPROVAL#{agent}",
        "sk": f"{ts}#{approval_id}",
        "approval_id": approval_id,
        "agent": agent,
        "action_type": action_type,
        "summary": summary,
        "payload": payload,
        "rationale": rationale,
        "urgency": urgency,
        "status": "PENDING",
        "created_at": ts,
        "deadline_at": deadline_iso,
        "ttl": ttl_epoch,
    }

    try:
        dynamo_table(table_name).put_item(Item=coerce_floats(record))
        logger.info(
            "Approval queued: id=%s agent=%s action=%s",
            approval_id, agent, action_type,
        )
    except Exception as exc:
        logger.error("Failed to write approval record: %s", exc)
        # Re-raise — if we can't write the queue record, the caller
        # must know, because they can't track this action.
        raise

    # Build Slack alert body
    slack_fields: dict[str, str] = {
        "Action": action_type,
        "Urgency": urgency.upper(),
    }
    if deadline_iso:
        slack_fields["Deadline"] = deadline_iso
    slack_fields["Approval ID"] = approval_id[:8] + "..."  # truncate for readability

    post_alert(
        webhook_env=webhook_env,
        title=f"Approval Required — {action_type}",
        body=f"*{summary}*\n\n_{rationale}_",
        severity=_URGENCY_SEVERITY.get(urgency, "low"),
        agent=agent,
        fields=slack_fields,
    )

    return approval_id


def list_pending(
    table_name: str,
    agent: Optional[str] = None,
) -> list[dict]:
    """
    Return all PENDING approval records from a queue table.

    Args:
        table_name: DynamoDB queue table to scan/query.
        agent:      If provided, restrict to this agent's partition only.
                    If None, scans the full table (acceptable for low-volume
                    approval queues — these tables never grow large).

    Returns:
        List of PENDING item dicts, unordered.
    """
    tbl = dynamo_table(table_name)
    pending_filter = Attr("status").eq("PENDING")

    if agent:
        resp = tbl.query(
            KeyConditionExpression=Key("pk").eq(f"APPROVAL#{agent}"),
            FilterExpression=pending_filter,
        )
    else:
        resp = tbl.scan(FilterExpression=pending_filter)

    return resp.get("Items", [])


def mark_status(
    table_name: str,
    agent: str,
    approval_id: str,
    status: str,
    edited_payload: Optional[dict] = None,
) -> None:
    """
    Update the status of an approval record.

    Finds the record by querying the agent's partition and filtering for
    the approval_id. This avoids needing to store the full sk externally.

    Args:
        table_name:     DynamoDB queue table.
        agent:          Agent identifier (used to construct pk).
        approval_id:    UUID returned by submit_for_approval().
        status:         New status: APPROVED | EDITED | DECLINED | EXECUTED | EXPIRED.
        edited_payload: If H.F. modified the action before approving, pass the
                        edited payload here. status is automatically set to
                        "EDITED" when this is provided.

    Raises:
        ValueError: If status is not a valid status string.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Valid values: {sorted(VALID_STATUSES)}"
        )

    tbl = dynamo_table(table_name)

    # Find the record — query by pk, filter by stored approval_id attribute
    resp = tbl.query(
        KeyConditionExpression=Key("pk").eq(f"APPROVAL#{agent}"),
        FilterExpression=Attr("approval_id").eq(approval_id),
    )
    items = resp.get("Items", [])
    if not items:
        logger.warning(
            "Approval record not found: agent=%s id=%s", agent, approval_id
        )
        return

    item = items[0]
    ts = now_iso()

    # Build update expression dynamically to avoid reserved-word conflicts
    updates: dict[str, Any] = {"status": status, "updated_at": ts}
    if edited_payload is not None:
        updates["payload"] = coerce_floats(edited_payload)
        updates["status"] = "EDITED"

    set_clauses = ", ".join(f"#{k} = :{k}" for k in updates)
    expr_names = {f"#{k}": k for k in updates}
    expr_values = {f":{k}": coerce_floats(v) for k, v in updates.items()}

    tbl.update_item(
        Key={"pk": item["pk"], "sk": item["sk"]},
        UpdateExpression=f"SET {set_clauses}",
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )
    logger.info(
        "Approval status updated: id=%s agent=%s status=%s",
        approval_id, agent, updates["status"],
    )
