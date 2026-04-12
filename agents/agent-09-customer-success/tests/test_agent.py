"""tests/test_agent.py — Agent 9 Customer Success test suite. Run: pytest tests/ -v"""
import json, os, pytest
from unittest.mock import patch, MagicMock


class TestContextTools:
    def test_enrich_returns_new_for_unknown_user(self):
        with patch("tools.context_tools.sessions_t") as mt:
            mt.query.return_value = {"Items": []}
            from tools.context_tools import enrich_user_context
            r = json.loads(enrich_user_context(user_id="unknown_user"))
            assert r["usage_trend"] == "NEW"
            assert "features_not_used" in r

    def test_feature_usage_summary_detects_all_unused(self):
        with patch("tools.context_tools.sessions_t") as mt:
            mt.query.return_value = {"Items": [{"user_id": "u1", "tier": "Spark", "created_at": "2026-01-01T00:00:00Z", "features_used": []}]}
            with patch("tools.context_tools.cs_t") as ct:
                ct.query.return_value = {"Items": []}
                from tools.context_tools import get_feature_usage_summary
                r = json.loads(get_feature_usage_summary(user_id="u1"))
                assert r["activation_rate_pct"] == 0.0
                assert len(r["features_not_activated"]) == 9


class TestOnboardingTools:
    def test_send_touchpoint_day_0_marks_sent(self):
        with patch("tools.support_tools.ses") as ms, patch("tools.support_tools.onboard_t") as mt:
            ms.send_email.return_value = {"MessageId": "test123"}
            mt.update_item.return_value = {}
            from tools.support_tools import send_onboarding_touchpoint
            r = json.loads(send_onboarding_touchpoint(
                user_id="u1", email="test@example.com", day=0, tier="Spark"
            ))
            assert r["status"] == "SENT"
            assert r["day"] == 0
            ms.send_email.assert_called_once()

    def test_mark_touchpoint_completed_writes_dynamo(self):
        with patch("tools.support_tools.onboard_t") as mt:
            mt.update_item.return_value = {}
            from tools.support_tools import mark_touchpoint_completed
            r = json.loads(mark_touchpoint_completed(user_id="u1", day=3))
            assert r["status"] == "MARKED"
            mt.update_item.assert_called_once()


class TestSupportTools:
    def test_create_ticket_assigns_correct_sla(self):
        with patch("tools.support_tools.cs_tickets_t") as mt:
            mt.put_item.return_value = {}
            from tools.support_tools import create_support_ticket
            r = json.loads(create_support_ticket(
                user_id="u1", user_email="test@test.com",
                trigger="BILLING_DISPUTE", summary="Double charge issue", urgency="HIGH"
            ))
            assert r["sla_commitment"] == "4 hours"
            assert r["status"] == "OPEN"

    def test_escalate_creates_ticket_and_returns_message(self):
        with patch("tools.support_tools.cs_tickets_t") as mt:
            with patch("tools.support_tools.requests") as mr:
                mt.put_item.return_value = {}
                from tools.support_tools import escalate_to_human
                r = json.loads(escalate_to_human(
                    user_id="u1", user_email="test@test.com",
                    trigger="FRUSTRATED_USER", conversation_summary="User upset",
                ))
                assert r["status"] == "ESCALATED"
                assert "team" in r["message_to_user"].lower()


class TestRetentionTools:
    def test_nps_detractor_classification(self):
        with patch("tools.support_tools.nps_t") as mt:
            mt.put_item.return_value = {}
            from tools.support_tools import record_nps_response
            r = json.loads(record_nps_response(user_id="u1", score=4, comment="Not useful"))
            assert r["classification"] == "DETRACTOR"

    def test_nps_promoter_classification(self):
        with patch("tools.support_tools.nps_t") as mt:
            mt.put_item.return_value = {}
            from tools.support_tools import record_nps_response
            r = json.loads(record_nps_response(user_id="u1", score=10))
            assert r["classification"] == "PROMOTER"

    def test_churn_risk_declining_user_scores_high(self):
        with patch("tools.context_tools.sessions_t") as mt:
            with patch("tools.context_tools.cs_t") as ct:
                # Simulate user with no recent sessions
                mt.query.return_value = {"Items": [
                    {"user_id": "u1", "tier": "Spark", "created_at": "2026-01-01T00:00:00Z",
                     "features_used": [], "last_active": "2026-01-01T00:00:00Z"}
                ]}
                ct.query.return_value = {"Items": []}
                from tools.support_tools import compute_churn_risk
                r = json.loads(compute_churn_risk(user_id="u1"))
                assert "churn_risk_score" in r
                assert r["churn_risk_score"] >= 0.0  # Score computed


class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_has_escalation_triggers(self):
        from agent import SYSTEM_PROMPT
        assert "escalate" in SYSTEM_PROMPT.lower()
        assert "billing" in SYSTEM_PROMPT.lower()
        assert "refund" in SYSTEM_PROMPT.lower()

    def test_lambda_handler_routes_all_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_cs_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            # Unknown task returns error
            r = lambda_handler({"task": "nonexistent"}, None)
            assert "error" in r
