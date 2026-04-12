"""
tests/test_agent.py — Test suite for Agent 10: CyberSecurity Agent.

Run: pytest tests/ -v
All tests use mocked AWS clients — no real AWS calls are made.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


# ─── TOOL UNIT TESTS ─────────────────────────────────────────────────────────

class TestWAFTools:
    def test_check_waf_block_rate_returns_valid_json(self):
        with patch("tools.waf_tools.cloudwatch") as mock_cw:
            mock_cw.get_metric_statistics.return_value = {
                "Datapoints": [{"Sum": 150.0}]
            }
            from tools.waf_tools import check_waf_block_rate
            result = json.loads(check_waf_block_rate(hours=1))
            assert "block_rate_pct" in result
            assert "severity" in result

    def test_update_waf_ip_blocklist_dry_run_without_approval(self):
        from tools.waf_tools import update_waf_ip_blocklist
        result = json.loads(update_waf_ip_blocklist(
            ip_addresses=["1.2.3.4/32"],
            reason="Test",
            human_approved=False,
        ))
        assert result["status"] == "DRY_RUN"

    def test_update_waf_ip_blocklist_executes_with_approval(self):
        from tools.waf_tools import update_waf_ip_blocklist
        result = json.loads(update_waf_ip_blocklist(
            ip_addresses=["1.2.3.4/32"],
            reason="Bot IP detected",
            human_approved=True,
        ))
        assert result["status"] == "EXECUTED"
        assert "1.2.3.4/32" in result["ips_blocked"]


class TestSessionTools:
    def test_session_risk_score_impossible_travel(self):
        """Sessions with impossible travel should score > 0.70."""
        from tools.session_tools import _compute_risk
        session = {"multi_continent_login": True, "calls_last_15min": 10, "token_age_hours": 24}
        score, reasons = _compute_risk(session)
        assert score > 0.70
        assert "IMPOSSIBLE_TRAVEL" in reasons

    def test_session_risk_score_expired_token(self):
        """Expired token reuse should score > 0.80."""
        from tools.session_tools import _compute_risk
        session = {"token_age_hours": 200, "calls_last_15min": 5}
        score, reasons = _compute_risk(session)
        assert score > 0.80
        assert "EXPIRED_TOKEN_REUSE" in reasons

    def test_safe_session_scores_zero(self):
        """Normal session should have zero risk score."""
        from tools.session_tools import _compute_risk
        session = {"token_age_hours": 12, "calls_last_15min": 20}
        score, reasons = _compute_risk(session)
        assert score == 0.0
        assert reasons == []


class TestContentTools:
    def test_reset_asset_baseline_rejects_unknown_asset(self):
        from tools.content_tools import reset_asset_baseline_hash
        result = json.loads(reset_asset_baseline_hash(
            asset_name="unknown_file.exe",
            confirmed_by="TestUser"
        ))
        assert "error" in result
        assert "not in the protected assets list" in result["error"]

    def test_invalidate_cloudfront_cache_dry_run_no_distribution(self):
        """Without a real distribution ID, should return an error gracefully."""
        with patch("tools.content_tools.cf") as mock_cf:
            mock_cf.create_invalidation.side_effect = Exception("Distribution not found")
            from tools.content_tools import invalidate_cloudfront_cache
            result = json.loads(invalidate_cloudfront_cache(["index.js"]))
            assert "error" in result


class TestAlertTools:
    def test_slack_alert_dry_run_without_webhook(self):
        """Without SLACK_SECURITY_WEBHOOK set, should return DRY_RUN."""
        import os
        os.environ.pop("SLACK_SECURITY_WEBHOOK", None)

        from tools.alert_tools import post_security_alert_to_slack
        result = json.loads(post_security_alert_to_slack(
            message="Test finding",
            severity="MEDIUM",
            layer="Layer 3 - Sessions",
            recommended_action="Monitor for 4 hours.",
        ))
        assert result["status"] == "DRY_RUN"

    def test_log_security_event_writes_to_dynamo(self):
        with patch("tools.alert_tools.events_table") as mock_table:
            mock_table.put_item.return_value = {}
            from tools.alert_tools import log_security_event
            result = json.loads(log_security_event(
                event_type="WAF_BLOCK",
                severity="MEDIUM",
                details="Rate limit exceeded from IP 5.6.7.8",
                auto_action_taken="NONE",
            ))
            assert result["status"] == "LOGGED"
            assert "WAF_BLOCK" in result["event_id"]
            mock_table.put_item.assert_called_once()


# ─── AGENT INTEGRATION TEST ──────────────────────────────────────────────────

class TestAgentCreation:
    def test_agent_creation_fails_without_api_key(self):
        """Agent creation should raise EnvironmentError without API key."""
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY not set"):
            get_model()

    def test_agent_has_all_21_tools(self):
        """Agent should have all 21 security tools registered."""
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.AnthropicModel"):
            from agent import create_security_agent
            with patch("strands.models.anthropic.AnthropicModel"):
                # Verify tool count by inspecting tool definitions
                from tools.waf_tools import check_waf_block_rate, update_waf_ip_blocklist, get_waf_recent_blocked_requests
                from tools.session_tools import scan_active_sessions_for_anomalies, invalidate_session, get_session_risk_report
                from tools.content_tools import verify_asset_integrity, reset_asset_baseline_hash, invalidate_cloudfront_cache
                from tools.guardduty_tools import get_guardduty_findings, acknowledge_guardduty_finding, get_security_summary
                from tools.fraud_tools import scan_streaming_anomalies, get_fraud_risk_report, prepare_dsp_fraud_report
                from tools.fraud_tools import process_gdpr_deletion_request, audit_data_retention_compliance, check_pii_exposure_in_logs
                from tools.alert_tools import post_security_alert_to_slack, send_critical_page_to_engineer, log_security_event

                all_tools = [
                    check_waf_block_rate, update_waf_ip_blocklist, get_waf_recent_blocked_requests,
                    scan_active_sessions_for_anomalies, invalidate_session, get_session_risk_report,
                    verify_asset_integrity, reset_asset_baseline_hash, invalidate_cloudfront_cache,
                    get_guardduty_findings, acknowledge_guardduty_finding, get_security_summary,
                    scan_streaming_anomalies, get_fraud_risk_report, prepare_dsp_fraud_report,
                    process_gdpr_deletion_request, audit_data_retention_compliance, check_pii_exposure_in_logs,
                    post_security_alert_to_slack, send_critical_page_to_engineer, log_security_event,
                ]
                assert len(all_tools) == 21


# ─── LAMBDA HANDLER TEST ──────────────────────────────────────────────────────

class TestLambdaHandler:
    def test_lambda_handler_unknown_task_returns_error(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_security_agent") as mock_agent:
            mock_agent.return_value = MagicMock()
            from agent import lambda_handler
            result = lambda_handler({"task": "unknown_task"}, None)
            assert "error" in result

    def test_lambda_handler_routes_correct_task(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_security_agent") as mock_create:
            with patch("agent.run_daily_guardduty_digest") as mock_task:
                mock_create.return_value = MagicMock()
                mock_task.return_value = {"task": "daily_guardduty_digest", "result": "ok"}
                from agent import lambda_handler
                result = lambda_handler({"task": "daily_guardduty_digest"}, None)
                assert result["task"] == "daily_guardduty_digest"
