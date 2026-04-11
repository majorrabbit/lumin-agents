"""
Tests for shared/approval.py

Scenarios:
- submit_for_approval: writes DynamoDB record + posts Slack alert + returns UUID
- submit_for_approval: DynamoDB failure re-raises (must be surfaced to caller)
- submit_for_approval: record has correct pk/sk structure, status=PENDING, TTL set
- list_pending with agent: queries by agent pk
- list_pending without agent: scans full table
- mark_status: updates record status; edited_payload changes status to EDITED
- mark_status: item not found logs warning without raising
- mark_status: invalid status raises ValueError
"""

import os
from unittest.mock import MagicMock, call, patch

import pytest

import shared.approval as approval_mod
from shared.approval import list_pending, mark_status, submit_for_approval


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_dynamo_table():
    """Patch shared.dynamo.table to return a MagicMock table."""
    tbl = MagicMock()
    tbl.put_item.return_value = {}
    tbl.query.return_value = {"Items": []}
    tbl.scan.return_value = {"Items": []}
    tbl.update_item.return_value = {}
    return tbl


@pytest.fixture
def patched_table(mock_dynamo_table):
    with patch("shared.approval.dynamo_table", return_value=mock_dynamo_table):
        yield mock_dynamo_table


@pytest.fixture
def silent_slack():
    """Suppress all Slack calls in approval tests."""
    with patch("shared.approval.post_alert", return_value={"status": "dry_run"}):
        yield


# ─── submit_for_approval ─────────────────────────────────────────────────────

class TestSubmitForApproval:
    def test_returns_uuid_string(self, patched_table, silent_slack):
        result = submit_for_approval(
            table_name="test-queue",
            webhook_env="SLACK_TEST",
            agent="agent12",
            action_type="post_tiktok",
            summary="Post clip during trending peak",
            payload={"content": "..."},
            rationale="Cultural moment confidence 0.91",
        )
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format: 8-4-4-4-12

    def test_writes_record_to_dynamo(self, patched_table, silent_slack):
        submit_for_approval(
            table_name="my-queue",
            webhook_env="HOOK",
            agent="agent11",
            action_type="send_outreach",
            summary="Post in r/nujabes",
            payload={"platform": "reddit"},
            rationale="High CLV community",
        )
        patched_table.put_item.assert_called_once()

    def test_record_has_pending_status(self, patched_table, silent_slack):
        submit_for_approval(
            table_name="q",
            webhook_env="H",
            agent="agent12",
            action_type="post",
            summary="s",
            payload={},
            rationale="r",
        )
        item = patched_table.put_item.call_args[1]["Item"]
        assert item["status"] == "PENDING"

    def test_record_pk_contains_agent(self, patched_table, silent_slack):
        submit_for_approval(
            table_name="q", webhook_env="H",
            agent="agent12", action_type="t",
            summary="s", payload={}, rationale="r",
        )
        item = patched_table.put_item.call_args[1]["Item"]
        assert item["pk"] == "APPROVAL#agent12"

    def test_record_sk_contains_approval_id(self, patched_table, silent_slack):
        approval_id = submit_for_approval(
            table_name="q", webhook_env="H",
            agent="agent12", action_type="t",
            summary="s", payload={}, rationale="r",
        )
        item = patched_table.put_item.call_args[1]["Item"]
        assert approval_id in item["sk"]

    def test_record_has_ttl(self, patched_table, silent_slack):
        submit_for_approval(
            table_name="q", webhook_env="H",
            agent="a", action_type="t",
            summary="s", payload={}, rationale="r",
        )
        item = patched_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        assert isinstance(item["ttl"], int)

    def test_slack_alert_posted(self, patched_table):
        with patch("shared.approval.post_alert", return_value={"status": "ok"}) as mock_slack:
            submit_for_approval(
                table_name="q", webhook_env="MY_HOOK",
                agent="agent11", action_type="send_dm",
                summary="Outreach message ready",
                payload={}, rationale="High CLV community",
                urgency="high",
            )
        mock_slack.assert_called_once()
        call_kwargs = mock_slack.call_args[1]
        assert call_kwargs["webhook_env"] == "MY_HOOK"

    def test_dynamo_failure_reraises(self, silent_slack):
        with patch("shared.approval.dynamo_table") as mock_tbl_factory:
            mock_tbl = MagicMock()
            mock_tbl.put_item.side_effect = RuntimeError("DDB down")
            mock_tbl_factory.return_value = mock_tbl
            with pytest.raises(RuntimeError, match="DDB down"):
                submit_for_approval(
                    table_name="q", webhook_env="H",
                    agent="a", action_type="t",
                    summary="s", payload={}, rationale="r",
                )

    def test_deadline_stored_when_provided(self, patched_table, silent_slack):
        submit_for_approval(
            table_name="q", webhook_env="H",
            agent="a", action_type="t",
            summary="s", payload={}, rationale="r",
            deadline_iso="2026-04-12T18:00:00Z",
        )
        item = patched_table.put_item.call_args[1]["Item"]
        assert item["deadline_at"] == "2026-04-12T18:00:00Z"


# ─── list_pending ─────────────────────────────────────────────────────────────

class TestListPending:
    def test_queries_by_agent_when_provided(self):
        mock_tbl = MagicMock()
        mock_tbl.query.return_value = {"Items": [{"pk": "APPROVAL#agent12", "status": "PENDING"}]}
        with patch("shared.approval.dynamo_table", return_value=mock_tbl):
            result = list_pending("my-queue", agent="agent12")
        mock_tbl.query.assert_called_once()
        assert len(result) == 1

    def test_scans_when_no_agent(self):
        mock_tbl = MagicMock()
        mock_tbl.scan.return_value = {"Items": [{"pk": "APPROVAL#agent11"}, {"pk": "APPROVAL#agent12"}]}
        with patch("shared.approval.dynamo_table", return_value=mock_tbl):
            result = list_pending("my-queue")
        mock_tbl.scan.assert_called_once()
        assert len(result) == 2

    def test_returns_empty_list_on_no_results(self):
        mock_tbl = MagicMock()
        mock_tbl.scan.return_value = {}
        with patch("shared.approval.dynamo_table", return_value=mock_tbl):
            result = list_pending("my-queue")
        assert result == []


# ─── mark_status ─────────────────────────────────────────────────────────────

class TestMarkStatus:
    @pytest.fixture
    def table_with_item(self):
        mock_tbl = MagicMock()
        mock_tbl.query.return_value = {
            "Items": [{
                "pk": "APPROVAL#agent12",
                "sk": "2026-04-11T12:00:00+00:00#abc-123",
                "approval_id": "abc-123",
                "status": "PENDING",
            }]
        }
        mock_tbl.update_item.return_value = {}
        return mock_tbl

    def test_updates_status_to_approved(self, table_with_item):
        with patch("shared.approval.dynamo_table", return_value=table_with_item):
            mark_status("q", "agent12", "abc-123", "APPROVED")
        table_with_item.update_item.assert_called_once()

    def test_edited_payload_sets_status_to_edited(self, table_with_item):
        with patch("shared.approval.dynamo_table", return_value=table_with_item):
            mark_status("q", "agent12", "abc-123", "APPROVED",
                       edited_payload={"new": "payload"})
        call_kwargs = table_with_item.update_item.call_args[1]
        # Status should be overridden to EDITED when edited_payload provided
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert any("EDITED" in str(v) for v in expr_values.values())

    def test_item_not_found_logs_warning_no_raise(self, caplog):
        mock_tbl = MagicMock()
        mock_tbl.query.return_value = {"Items": []}
        with patch("shared.approval.dynamo_table", return_value=mock_tbl):
            with caplog.at_level("WARNING", logger="shared.approval"):
                mark_status("q", "agent12", "not-found-id", "APPROVED")
        assert "not found" in caplog.text.lower()
        mock_tbl.update_item.assert_not_called()

    def test_invalid_status_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid status"):
            mark_status("q", "agent12", "abc-123", "WHATEVER")

    @pytest.mark.parametrize("valid_status", [
        "PENDING", "APPROVED", "EDITED", "DECLINED", "EXECUTED", "EXPIRED"
    ])
    def test_all_valid_statuses_accepted(self, valid_status, table_with_item):
        with patch("shared.approval.dynamo_table", return_value=table_with_item):
            mark_status("q", "agent12", "abc-123", valid_status)  # should not raise
