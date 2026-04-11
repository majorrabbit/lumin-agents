"""
Tests for shared/slack.py

Scenarios:
- dry_run=True: no HTTP call, returns {"status": "dry_run", "payload": ...}
- webhook env var unset/empty: returns {"status": "no_webhook"}, no raise
- successful POST (200): returns {"status": "ok"}
- non-200 POST: returns {"status": "error", "code": <status>}
- payload structure: header contains severity emoji, title, agent footer
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from shared.slack import post_alert


# ── dry_run mode ─────────────────────────────────────────────────────────────

def test_dry_run_returns_dry_run_status():
    result = post_alert(
        webhook_env="SLACK_TEST_WEBHOOK",
        title="Test Alert",
        body="Test body",
        dry_run=True,
    )
    assert result["status"] == "dry_run"
    assert "payload" in result


def test_dry_run_does_not_call_requests(monkeypatch):
    posted = []
    monkeypatch.setattr("requests.post", lambda *a, **kw: posted.append(1))
    post_alert(
        webhook_env="SLACK_TEST_WEBHOOK",
        title="Silent Test",
        body="no HTTP please",
        dry_run=True,
    )
    assert posted == [], "requests.post should not be called in dry_run mode"


def test_dry_run_payload_has_blocks():
    result = post_alert(
        webhook_env="SLACK_TEST_WEBHOOK",
        title="Block Check",
        body="Body text",
        severity="high",
        dry_run=True,
    )
    blocks = result["payload"]["blocks"]
    assert isinstance(blocks, list)
    assert len(blocks) >= 2  # at minimum: header + body


# ── Missing webhook ───────────────────────────────────────────────────────────

def test_missing_webhook_env_returns_no_webhook():
    with patch.dict(os.environ, {}, clear=True):
        result = post_alert(
            webhook_env="NONEXISTENT_WEBHOOK",
            title="Orphaned Alert",
            body="no webhook configured",
        )
    assert result == {"status": "no_webhook"}


def test_empty_webhook_env_returns_no_webhook():
    with patch.dict(os.environ, {"MY_WEBHOOK": ""}):
        result = post_alert(
            webhook_env="MY_WEBHOOK",
            title="Empty URL",
            body="webhook is empty string",
        )
    assert result == {"status": "no_webhook"}


def test_missing_webhook_does_not_raise():
    with patch.dict(os.environ, {}, clear=True):
        # Must not raise — missing webhook is a non-fatal condition
        post_alert(webhook_env="NOPE", title="x", body="y")


# ── Successful POST ───────────────────────────────────────────────────────────

def test_successful_post_returns_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.dict(os.environ, {"MY_WEBHOOK": "https://hooks.slack.com/test"}):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = post_alert(
                webhook_env="MY_WEBHOOK",
                title="Success",
                body="everything is fine",
            )
    assert result == {"status": "ok"}
    mock_post.assert_called_once()


def test_post_uses_correct_url():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.dict(os.environ, {"MY_HOOK": "https://hooks.slack.com/real-url"}):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            post_alert(webhook_env="MY_HOOK", title="t", body="b")
    url_used = mock_post.call_args[0][0]
    assert url_used == "https://hooks.slack.com/real-url"


def test_post_timeout_is_five_seconds():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.dict(os.environ, {"HOOK": "https://hooks.slack.com/x"}):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            post_alert(webhook_env="HOOK", title="t", body="b")
    kwargs = mock_post.call_args[1]
    assert kwargs.get("timeout") == 5


# ── Non-200 response ──────────────────────────────────────────────────────────

def test_non_200_returns_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch.dict(os.environ, {"HOOK": "https://hooks.slack.com/x"}):
        with patch("requests.post", return_value=mock_resp):
            result = post_alert(webhook_env="HOOK", title="t", body="b")
    assert result["status"] == "error"
    assert result["code"] == 429


# ── Payload structure ─────────────────────────────────────────────────────────

def test_payload_header_contains_severity_emoji_and_title():
    result = post_alert(
        webhook_env="X",
        title="Phase Transition Detected",
        body="Variance surge 2.4x above baseline",
        severity="high",
        dry_run=True,
    )
    header_text = result["payload"]["blocks"][0]["text"]["text"]
    assert "🚨" in header_text
    assert "Phase Transition Detected" in header_text


def test_payload_body_block_present():
    result = post_alert(
        webhook_env="X",
        title="t",
        body="The body text here",
        dry_run=True,
    )
    body_block = result["payload"]["blocks"][1]
    assert body_block["type"] == "section"
    assert "The body text here" in body_block["text"]["text"]


def test_payload_fields_block_added_when_provided():
    result = post_alert(
        webhook_env="X",
        title="t",
        body="b",
        fields={"Score": "0.14", "Agent": "resonance"},
        dry_run=True,
    )
    blocks = result["payload"]["blocks"]
    field_block = next((b for b in blocks if b.get("type") == "section" and "fields" in b), None)
    assert field_block is not None
    field_texts = [f["text"] for f in field_block["fields"]]
    assert any("Score" in t for t in field_texts)


def test_payload_link_button_added_when_provided():
    result = post_alert(
        webhook_env="X",
        title="t",
        body="b",
        link="https://example.com/dashboard",
        dry_run=True,
    )
    blocks = result["payload"]["blocks"]
    actions = next((b for b in blocks if b.get("type") == "actions"), None)
    assert actions is not None
    assert actions["elements"][0]["url"] == "https://example.com/dashboard"


def test_payload_footer_contains_agent_name():
    result = post_alert(
        webhook_env="X",
        title="t",
        body="b",
        agent="agent01-resonance",
        dry_run=True,
    )
    blocks = result["payload"]["blocks"]
    context_block = next((b for b in blocks if b.get("type") == "context"), None)
    assert context_block is not None
    footer_text = context_block["elements"][0]["text"]
    assert "agent01-resonance" in footer_text


def test_all_severity_levels_produce_valid_payload():
    for sev in ("info", "low", "medium", "high", "critical"):
        result = post_alert(
            webhook_env="X",
            title=f"Test {sev}",
            body="body",
            severity=sev,
            dry_run=True,
        )
        assert result["status"] == "dry_run"
