"""tests/test_agent.py — Agent 3 Sync Pitch Campaign. Run: pytest tests/ -v"""
import json, os, pytest
from unittest.mock import patch, MagicMock


class TestSupervisorTools:
    def test_database_has_all_key_supervisors(self):
        from agent import SUPERVISOR_DATABASE
        names = [s["name"] for s in SUPERVISOR_DATABASE]
        for name in ["Jen Malone", "Joel C. High", "Kier Lehman"]:
            assert name in names, f"Missing supervisor: {name}"

    def test_get_supervisor_database_returns_tier1(self):
        from agent import get_supervisor_database
        r = json.loads(get_supervisor_database(tier_filter=1))
        assert r["count"] >= 5

    def test_placement_history_new_supervisor(self):
        with patch("agent.pitches_t") as mt:
            mt.query.return_value = {"Items": []}
            from agent import get_supervisor_placement_history
            r = json.loads(get_supervisor_placement_history("SUP-999"))
            assert r["relationship_status"] == "NEW"
            assert r["total_pitches"] == 0

class TestPitchQueue:
    def test_queue_pitch_writes_dynamo_and_slacks(self):
        with patch("agent.pitches_t") as mt, patch("agent.requests") as mr:
            mt.put_item.return_value = {}
            from agent import queue_pitch_for_approval
            r = json.loads(queue_pitch_for_approval(
                "SUP-001", "OPP-001", "MoreLoveLessWar fits Euphoria perfectly.", "Sync Pitch: MoreLoveLessWar"
            ))
            assert r["status"] == "QUEUED"

    def test_system_prompt_mentions_onestopp(self):
        from agent import SYSTEM_PROMPT
        assert "one-stop" in SYSTEM_PROMPT.lower()

class TestAgentCreation:
    def test_fails_without_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_lambda_routes(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_sync_pitch_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            for t in ["weekly_pitch_cycle", "follow_up_scan"]:
                assert "error" not in lambda_handler({"task": t}, None)
