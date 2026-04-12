"""tests/test_agent.py — Agent 5 Royalty Reconciliation. Run: pytest tests/ -v"""
import json, os, pytest, math
from unittest.mock import patch, MagicMock


class TestRoyaltyTools:
    def test_fetch_pro_statements_returns_four_sources(self):
        with patch("agent.royal_t") as mt:
            mt.put_item.return_value = {}
            from agent import fetch_pro_statements
            r = json.loads(fetch_pro_statements())
            assert "ASCAP" in r["statements"]
            assert "BMI" in r["statements"]
            assert "SoundExchange" in r["statements"]
            assert "MLC" in r["statements"]

    def test_mlc_unmatched_works_flagged(self):
        with patch("agent.royal_t") as mt:
            mt.put_item.return_value = {}
            from agent import fetch_pro_statements
            r = json.loads(fetch_pro_statements())
            flags = r.get("critical_flags", [])
            assert any("MLC" in f for f in flags)

    def test_apple_music_zero_streams_is_critical(self):
        from agent import fetch_dsp_statements
        r = json.loads(fetch_dsp_statements())
        apple = r["dsp_statements"]["Apple Music"]
        assert apple["streams_q4"] == 0
        assert "CRITICAL" in apple.get("flag", "")

    def test_reconcile_detects_apple_music_issue(self):
        with patch("agent.royal_t") as mt:
            mt.put_item.return_value = {}
            from agent import reconcile_statements
            r = json.loads(reconcile_statements())
            dist_issues = [i for i in r["issues"]
                           if i["type"] == "DISTRIBUTION_FAILURE"]
            assert len(dist_issues) >= 1

    def test_check_mlc_returns_registration_steps(self):
        from agent import check_mlc_registration_status
        r = json.loads(check_mlc_registration_status())
        assert "portal.themlc.com" in r["registration_portal"]
        assert len(r["immediate_actions"]) >= 3

class TestAgentCreation:
    def test_fails_without_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_mentions_mlc(self):
        from agent import SYSTEM_PROMPT
        assert "MLC" in SYSTEM_PROMPT

    def test_lambda_routes(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_royalty_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            assert "error" not in lambda_handler({"task": "monthly_reconciliation"}, None)
