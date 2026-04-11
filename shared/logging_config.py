"""
Structured logging configuration for the Lumin MAS fleet.

WHY THIS EXISTS:
Lambda and EC2 logs land in CloudWatch. Without structured JSON logging,
filtering CloudWatch logs for "all errors from agent09 this hour" requires
text grep. With structured JSON, a single CloudWatch Insights query can
filter by agent, level, and any extra= field in milliseconds.

The format is controlled by two environment variables so it can be switched
without code changes:
  LUMIN_LOG_LEVEL   DEBUG|INFO|WARNING|ERROR|CRITICAL  (default: INFO)
  LUMIN_LOG_FORMAT  json|text                           (default: json)

Use text format for local development (human-readable), json for all
deployed environments (CloudWatch-queryable).

QUIET LOGGERS:
botocore and urllib3 are silenced to WARNING. They produce chatty INFO
output that pollutes the agent logs with AWS request internals.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Fields that are standard LogRecord attributes — not treated as extras.
_STANDARD_LOG_FIELDS = frozenset({
    "name", "msg", "args", "created", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs",
    "pathname", "process", "processName", "relativeCreated",
    "thread", "threadName", "exc_info", "exc_text", "stack_info",
    "message", "taskName",
})


class _JsonFormatter(logging.Formatter):
    """
    Emit one JSON object per log line.

    Base fields: timestamp, level, agent, logger, message.
    Any extra= dict passed to the logger call is merged into the output.
    Exceptions are formatted and included as an "exception" key.
    """

    def __init__(self, agent_name: str) -> None:
        super().__init__()
        self._agent = agent_name

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "agent": self._agent,
            "logger": record.name,
            "message": record.message,
        }
        # Capture any extra= fields the caller provided
        for key, val in record.__dict__.items():
            if key not in _STANDARD_LOG_FIELDS and not key.startswith("_"):
                try:
                    json.dumps(val)  # only include JSON-serialisable extras
                    data[key] = val
                except (TypeError, ValueError):
                    data[key] = str(val)

        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)

        return json.dumps(data, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable single-line format for local development."""

    def __init__(self, agent_name: str) -> None:
        super().__init__(
            fmt=f"%(asctime)s  [{agent_name}]  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def configure_logging(agent_name: str) -> None:
    """
    Configure the root logger with a single structured stdout handler.

    Replaces any existing root logger handlers so this function is safe to
    call multiple times (e.g. in tests). Honors LUMIN_LOG_LEVEL and
    LUMIN_LOG_FORMAT environment variables.

    Args:
        agent_name: Short agent identifier included in every log record.
                    e.g. "agent01-resonance", "agent09-cs", "sbia-booking"

    Environment variables:
        LUMIN_LOG_LEVEL:  Logging threshold. Default "INFO".
        LUMIN_LOG_FORMAT: "json" (default) or "text" for local dev.

    Example:
        from shared.logging_config import configure_logging
        configure_logging("agent09-cs")
        log = logging.getLogger(__name__)
        log.info("CS agent started", extra={"tier": "Resonance Pro"})
        # JSON output: {"timestamp":..., "level":"INFO", "agent":"agent09-cs",
        #               "logger":"...", "message":"CS agent started",
        #               "tier":"Resonance Pro"}
    """
    level_name = os.environ.get("LUMIN_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt_name = os.environ.get("LUMIN_LOG_FORMAT", "json").lower()
    formatter: logging.Formatter = (
        _TextFormatter(agent_name)
        if fmt_name == "text"
        else _JsonFormatter(agent_name)
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace all existing handlers so repeated calls don't stack duplicates
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
