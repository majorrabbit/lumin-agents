"""
Tests for shared/logging_config.py

Scenarios:
- JSON format: root logger emits valid JSON lines with expected fields
- Text format: root logger emits readable strings (not JSON)
- LUMIN_LOG_LEVEL env var is honored
- Default level is INFO (DEBUG messages suppressed)
- botocore and urllib3 are quieted to WARNING
- Repeated calls to configure_logging don't stack duplicate handlers
- extra= fields appear in JSON output
"""

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest

from shared.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    """Restore root logger state after each test."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    # Re-quiet noisy loggers to avoid test bleed
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# ─── JSON format ─────────────────────────────────────────────────────────────

class TestJsonFormat:
    def test_emits_valid_json(self):
        configure_logging("test-agent")
        buf = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = buf

        logging.getLogger("test").info("hello world")

        line = buf.getvalue().strip()
        data = json.loads(line)
        assert data["message"] == "hello world"

    def test_required_fields_present(self):
        configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("mymodule").info("test message")

        data = json.loads(buf.getvalue().strip())
        for field in ("timestamp", "level", "agent", "logger", "message"):
            assert field in data, f"Missing field: {field}"

    def test_agent_name_in_output(self):
        configure_logging("agent01-resonance")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").info("ping")

        data = json.loads(buf.getvalue().strip())
        assert data["agent"] == "agent01-resonance"

    def test_level_field_correct(self):
        configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").warning("warn msg")

        data = json.loads(buf.getvalue().strip())
        assert data["level"] == "WARNING"

    def test_extra_fields_included(self):
        configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").info("with extra", extra={"user_id": "abc123"})

        data = json.loads(buf.getvalue().strip())
        assert data.get("user_id") == "abc123"

    def test_timestamp_is_iso_format(self):
        configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").info("ts check")

        data = json.loads(buf.getvalue().strip())
        ts = data["timestamp"]
        # ISO format contains 'T' separator and timezone info
        assert "T" in ts
        assert "+" in ts or ts.endswith("Z")


# ─── Text format ─────────────────────────────────────────────────────────────

class TestTextFormat:
    def test_text_format_not_json(self):
        with patch.dict(os.environ, {"LUMIN_LOG_FORMAT": "text"}):
            configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").info("plain text message")

        line = buf.getvalue().strip()
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(line)  # should NOT be valid JSON

    def test_text_format_contains_message(self):
        with patch.dict(os.environ, {"LUMIN_LOG_FORMAT": "text"}):
            configure_logging("test-agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").info("readable output")

        assert "readable output" in buf.getvalue()


# ─── Log level ────────────────────────────────────────────────────────────────

class TestLogLevel:
    def test_default_level_is_info(self):
        with patch.dict(os.environ, {}, clear=True):
            configure_logging("agent")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_debug_level_honored(self):
        with patch.dict(os.environ, {"LUMIN_LOG_LEVEL": "DEBUG"}):
            configure_logging("agent")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_warning_level_honored(self):
        with patch.dict(os.environ, {"LUMIN_LOG_LEVEL": "WARNING"}):
            configure_logging("agent")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_debug_suppressed_at_info_level(self):
        with patch.dict(os.environ, {"LUMIN_LOG_LEVEL": "INFO"}):
            configure_logging("agent")
        buf = StringIO()
        logging.getLogger().handlers[0].stream = buf

        logging.getLogger("t").debug("should not appear")

        assert buf.getvalue() == ""


# ─── Noisy loggers quieted ────────────────────────────────────────────────────

class TestNoisyLoggers:
    def test_botocore_at_warning(self):
        configure_logging("agent")
        assert logging.getLogger("botocore").level == logging.WARNING

    def test_urllib3_at_warning(self):
        configure_logging("agent")
        assert logging.getLogger("urllib3").level == logging.WARNING

    def test_boto3_at_warning(self):
        configure_logging("agent")
        assert logging.getLogger("boto3").level == logging.WARNING


# ─── No duplicate handlers ────────────────────────────────────────────────────

class TestNoDuplicateHandlers:
    def test_repeated_calls_single_handler(self):
        configure_logging("agent-a")
        configure_logging("agent-b")
        configure_logging("agent-c")
        root = logging.getLogger()
        assert len(root.handlers) == 1
