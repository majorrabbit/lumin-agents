"""
Tests for shared/boid.py

Scenarios:
- Successful write: calls put_record with correct BOID fields
- Custom table_name used when provided
- Default table falls back to LUMIN_BOID_TABLE env var
- Default table falls back to "lumin-boid-actions" when env var unset
- DynamoDB failure is swallowed (never raises to caller)
- Warning logged on failure
- result dict included when provided
"""

import logging
import os
from unittest.mock import call, patch

import pytest

from shared.boid import log_action


# ─── Successful write ─────────────────────────────────────────────────────────

class TestLogActionSuccess:
    def test_calls_put_record(self):
        with patch("shared.boid.put_record") as mock_put:
            mock_put.return_value = {}
            log_action(
                agent="agent01-resonance",
                action="run_weekly_backtest",
                belief="7 days of predictions with known outcomes",
                obligation="Never skip Sunday backtest",
                intention="Compute walk-forward Brier score",
                desire="Brier < 0.18 by Month 6",
            )
        mock_put.assert_called_once()

    def test_pk_contains_agent(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                agent="agent01-resonance",
                action="test",
                belief="b", obligation="o", intention="i", desire="d",
            )
        # put_record called as put_record(table, pk=..., sk=..., ...)
        pk = mock_put.call_args[1]["pk"]
        assert "agent01-resonance" in pk

    def test_sk_contains_action(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                agent="agent09",
                action="handle_inbound_support",
                belief="b", obligation="o", intention="i", desire="d",
            )
        sk = mock_put.call_args[1]["sk"]
        assert "handle_inbound_support" in sk

    def test_boid_fields_in_kwargs(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                agent="a",
                action="act",
                belief="entropy rising",
                obligation="no skipping",
                intention="detect phase",
                desire="brier < 0.18",
            )
        kwargs = mock_put.call_args[1]
        assert kwargs["belief"] == "entropy rising"
        assert kwargs["obligation"] == "no skipping"
        assert kwargs["intention"] == "detect phase"
        assert kwargs["desire"] == "brier < 0.18"

    def test_result_dict_included_when_provided(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                agent="a", action="act",
                belief="b", obligation="o", intention="i", desire="d",
                result={"brier_score": 0.14, "count": 47},
            )
        kwargs = mock_put.call_args[1]
        assert kwargs["result"] == {"brier_score": 0.14, "count": 47}

    def test_result_defaults_to_empty_dict(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                agent="a", action="act",
                belief="b", obligation="o", intention="i", desire="d",
            )
        kwargs = mock_put.call_args[1]
        assert kwargs["result"] == {}


# ─── Table name resolution ────────────────────────────────────────────────────

class TestTableName:
    def test_custom_table_name_used(self):
        with patch("shared.boid.put_record") as mock_put:
            log_action(
                table_name="custom-boid-table",
                agent="a", action="act",
                belief="b", obligation="o", intention="i", desire="d",
            )
        table_arg = mock_put.call_args[0][0]
        assert table_arg == "custom-boid-table"

    def test_env_var_overrides_default(self):
        with patch.dict(os.environ, {"LUMIN_BOID_TABLE": "env-boid-table"}):
            with patch("shared.boid.put_record") as mock_put:
                log_action(
                    agent="a", action="act",
                    belief="b", obligation="o", intention="i", desire="d",
                )
        table_arg = mock_put.call_args[0][0]
        assert table_arg == "env-boid-table"

    def test_falls_back_to_hardcoded_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("shared.boid.put_record") as mock_put:
                log_action(
                    agent="a", action="act",
                    belief="b", obligation="o", intention="i", desire="d",
                )
        table_arg = mock_put.call_args[0][0]
        assert table_arg == "lumin-boid-actions"


# ─── Never raises ────────────────────────────────────────────────────────────

class TestNeverRaises:
    def test_dynamo_failure_swallowed(self):
        with patch("shared.boid.put_record", side_effect=RuntimeError("DDB down")):
            # Must not raise — audit failure is non-fatal
            log_action(
                agent="a", action="act",
                belief="b", obligation="o", intention="i", desire="d",
            )

    def test_warning_logged_on_failure(self, caplog):
        with patch("shared.boid.put_record", side_effect=Exception("boom")):
            with caplog.at_level(logging.WARNING, logger="shared.boid"):
                log_action(
                    agent="a", action="act",
                    belief="b", obligation="o", intention="i", desire="d",
                )
        assert "boom" in caplog.text or "non-fatal" in caplog.text

    def test_import_error_swallowed(self):
        """Even if shared.dynamo can't be imported, log_action must not crash."""
        import builtins
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "shared.dynamo":
                raise ImportError("dynamo not available")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocking_import):
            # The ImportError must be swallowed inside log_action
            try:
                log_action(
                    agent="a", action="act",
                    belief="b", obligation="o", intention="i", desire="d",
                )
            except ImportError:
                pytest.fail("log_action raised ImportError — must never raise")
