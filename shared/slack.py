"""
Slack alert helper for the Lumin MAS fleet.

WHY THIS EXISTS:
Every agent posts alerts to Slack. The pattern is always the same: read a
webhook URL from a per-agent environment variable, build a blocks payload,
and POST it. Without this helper, every agent has its own version of the
webhook posting code with slightly different payloads.

KEY DESIGN DECISIONS:
- The webhook URL is read from os.environ at CALL TIME, not at import time.
  This matters for tests where the env var may be set after module load.
- A missing or empty webhook never raises — it logs a warning and returns
  {"status": "no_webhook"}. An agent whose Slack webhook isn't configured
  yet should still function.
- dry_run=True logs the full payload at INFO level without any HTTP call.
  This is the standard local-dev testing mode across the fleet.
- Severity emojis and colors follow a consistent palette so H.F. can triage
  the #alerts channel at a glance by color/emoji.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Severity → (emoji prefix, Slack color for attachment fallback)
_SEVERITY: dict[str, tuple[str, str]] = {
    "info":     ("ℹ️",  "#36a64f"),
    "low":      ("📝",  "#2eb886"),
    "medium":   ("⚠️",  "#daa038"),
    "high":     ("🚨",  "#e01e5a"),
    "critical": ("🔴",  "#8B0000"),
}


def post_alert(
    *,
    webhook_env: str,
    title: str,
    body: str,
    severity: str = "info",
    agent: Optional[str] = None,
    fields: Optional[dict[str, str]] = None,
    link: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Post a structured alert to a Slack channel via incoming webhook.

    The Slack message uses Block Kit with: a header block (emoji + title),
    a body section, an optional two-column fields grid, an optional link
    button, and a context footer with the agent name and timestamp.

    Args:
        webhook_env: Name of the environment variable that holds the Slack
                     webhook URL. e.g. "SLACK_RESONANCE_WEBHOOK".
                     The URL is resolved at call time.
        title:       Bold header text. Keep under 150 chars.
        body:        Main message body. Supports Slack mrkdwn formatting.
        severity:    One of: info | low | medium | high | critical.
                     Controls the leading emoji. Defaults to "info".
        agent:       Agent identifier for the footer. e.g. "agent01-resonance".
        fields:      Optional dict of label→value pairs rendered as a two-column
                     grid below the body. e.g. {"Brier Score": "0.14"}.
        link:        Optional URL for an "Open" button in the message.
        dry_run:     If True, log the payload at INFO and return without POSTing.

    Returns:
        dict with "status" key:
          - "ok"         on HTTP 200
          - "dry_run"    when dry_run=True (includes "payload" key)
          - "no_webhook" when the env var is unset or empty
          - "error"      on non-200 HTTP response (includes "code" key)
    """
    emoji, _ = _SEVERITY.get(severity, _SEVERITY["info"])
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    footer = f"{agent or 'Lumin MAS'}  ·  {ts}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji}  {title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        },
    ]

    if fields:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{k}*\n{v}"}
                for k, v in fields.items()
            ],
        })

    if link:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open", "emoji": True},
                    "url": link,
                }
            ],
        })

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": footer}],
    })

    payload = {"blocks": blocks}

    if dry_run:
        logger.info("[DRY RUN] Slack alert would post: %s", json.dumps(payload, indent=2))
        return {"status": "dry_run", "payload": payload}

    webhook_url = os.environ.get(webhook_env, "")
    if not webhook_url:
        logger.warning(
            "Slack webhook env var '%s' is unset — alert not posted: %s",
            webhook_env, title,
        )
        return {"status": "no_webhook"}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        if resp.status_code == 200:
            return {"status": "ok"}
        logger.warning("Slack POST returned %d for alert: %s", resp.status_code, title)
        return {"status": "error", "code": resp.status_code}
    except requests.RequestException as exc:
        logger.warning("Slack POST failed for alert '%s': %s", title, exc)
        return {"status": "error", "code": None}
