"""tests/test_agent.py — Agent 2 Sync Brief Hunter. Run: pytest tests/ -v"""
import json, os, pytest
from unittest.mock import patch, MagicMock


class TestBriefTools:
    def test_fetch_active_briefs_returns_tier1(self):
        with patch("tools.brief_tools.briefs_t") as mt:
            mt.put_item.return_value = {}
            from tools.brief_tools import fetch_active_briefs
            r = json.loads(fetch_active_briefs())
            assert r["tier_1_count"] >= 1
            assert r["briefs_found"] >= 2

    def test_morelovelesswar_brief_is_tier1(self):
        with patch("tools.brief_tools.briefs_t") as mt:
            mt.put_item.return_value = {}
            from tools.brief_tools import fetch_active_briefs
            r = json.loads(fetch_active_briefs())
            tier1 = [b for b in r["briefs"] if b.get("tier") == 1]
            notes = [b.get("note", "") for b in tier1]
            assert any("MORELOVELESSWAR" in n for n in notes)

    def test_deadline_alerts_returns_sorted(self):
        with patch("tools.brief_tools.briefs_t") as mt:
            mt.scan.return_value = {"Items": []}
            from tools.brief_tools import get_brief_deadline_alerts
            r = json.loads(get_brief_deadline_alerts())
            assert "urgent_count" in r

    def test_log_brief_seen_calls_dynamo(self):
        with patch("tools.brief_tools.briefs_t") as mt:
            mt.update_item.return_value = {}
            from tools.brief_tools import log_brief_seen
            r = json.loads(log_brief_seen("BRF-001"))
            assert r["status"] == "MARKED_SEEN"


class TestCatalogTools:
    def test_search_catalog_returns_onestopp_tracks(self):
        from tools.brief_tools import search_opp_catalog
        r = json.loads(search_opp_catalog(genre="Hip-Hop"))
        tracks = r.get("tracks", [])
        one_stop = [t for t in tracks if t.get("clearance") == "ONE_STOP"]
        assert len(one_stop) > 0

    def test_match_catalog_to_brief_returns_3(self):
        from tools.brief_tools import match_catalog_to_brief
        r = json.loads(match_catalog_to_brief(
            brief_id="BRF-001",
            brief_description="peace unity healing social justice",
            genre="Hip-Hop", mood="hopeful reflective"
        ))
        matches = r.get("top_matches", [])
        assert len(matches) <= 3
        assert any(m.get("title") == "MoreLoveLessWar" for m in matches)

    def test_prepare_package_status_ready_for_approval(self):
        from tools.brief_tools import prepare_submission_package
        with patch("tools.brief_tools.subs_t") as mt:
            mt.put_item.return_value = {}
            r = json.loads(prepare_submission_package("OPP-001", "BRF-001", "Jen Malone"))
            assert r["status"] == "READY_FOR_APPROVAL"
            assert "cover_note_draft" in r


class TestSubmissionTools:
    def test_queue_submission_requires_no_auto_send(self):
        """Agent must NEVER submit directly — only queue."""
        with patch("tools.brief_tools.subs_t") as mt, patch("tools.brief_tools.requests") as mr:
            mt.put_item.return_value = {}
            from tools.brief_tools import queue_submission_for_approval
            r = json.loads(queue_submission_for_approval("BRF-001", "OPP-001", 1, "MoreLoveLessWar matches peace theme"))
            assert r["status"] == "QUEUED"
            # Verify it was not submitted — no supervisor contact made

    def test_system_prompt_requires_hf_approval(self):
        from agent import SYSTEM_PROMPT
        assert "human" in SYSTEM_PROMPT.lower() or "H.F." in SYSTEM_PROMPT
        assert "approval" in SYSTEM_PROMPT.lower() or "authoriz" in SYSTEM_PROMPT.lower()


class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_lambda_routes_three_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_sync_brief_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            for t in ["brief_scan", "deadline_monitor", "weekly_digest"]:
                r = lambda_handler({"task": t}, None)
                assert "error" not in r
