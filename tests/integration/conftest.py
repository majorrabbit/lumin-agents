"""
Lumin MAS — integration test conftest.

Injects fake 'strands' modules into sys.modules at load time (before any
agent module is imported) and provides an autouse fixture that patches
boto3 and requests for every test in this directory.

Why sys.modules injection at load time?
  Agents call `from strands import Agent, tool` at module level.  These
  imports execute when agent.py is first loaded inside a test, AFTER the
  fixture is already active.  Injecting into sys.modules here (when
  conftest.py is first loaded) guarantees the fakes are present no matter
  when an agent is imported.

Why module-level boto3 matters?
  Every agent (both inline Style B and tool-file Style A) calls
  `boto3.resource(...)` or `boto3.client(...)` at module level.  The
  `patch("boto3.resource", ...)` fixture ensures the mock is the active
  target when `spec.loader.exec_module(mod)` runs inside each test.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Repo root — two levels up from tests/integration/
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# ---------------------------------------------------------------------------
# Strands mock factory
# ---------------------------------------------------------------------------

def _build_strands_mocks() -> tuple[MagicMock, MagicMock, MagicMock]:
    """
    Return (strands_mod, strands_models_mod, strands_anthropic_mod).

    strands.tool  — identity decorator: @tool functions remain plain callables.
    strands.Agent — class mock; instances are MagicMocks (callable, return str-like).
    strands.models.anthropic.AnthropicModel — class mock; instances are MagicMocks.
    """
    # @tool → identity pass-through
    def _identity(fn):
        return fn

    agent_class = MagicMock(return_value=MagicMock())

    strands_mod = MagicMock()
    strands_mod.tool = _identity
    strands_mod.Agent = agent_class

    anthropic_model_class = MagicMock(return_value=MagicMock())
    strands_anthropic_mod = MagicMock()
    strands_anthropic_mod.AnthropicModel = anthropic_model_class

    strands_models_mod = MagicMock()
    strands_models_mod.anthropic = strands_anthropic_mod

    return strands_mod, strands_models_mod, strands_anthropic_mod


# ---------------------------------------------------------------------------
# Inject strands mocks at conftest load time (before any test runs)
# ---------------------------------------------------------------------------
_SM, _SMM, _SMA = _build_strands_mocks()
sys.modules["strands"] = _SM
sys.modules["strands.models"] = _SMM
sys.modules["strands.models.anthropic"] = _SMA
# Pre-inject other sub-modules agents may reference
for _sub in ("strands.tools", "strands.telemetry", "strands.types"):
    sys.modules.setdefault(_sub, MagicMock())

# ---------------------------------------------------------------------------
# Fake 'anthropic' — agents 11 and 12 tool files import it directly for
# lightweight haiku calls (classify_response_sentiment, voice synthesis).
# ---------------------------------------------------------------------------
_anthropic_client_mock = MagicMock()
_anthropic_mock = MagicMock()
_anthropic_mock.Anthropic = MagicMock(return_value=_anthropic_client_mock)

# Expose exception types that tool code may reference
class _AnthropicAPIError(Exception):
    pass

_anthropic_mock.APIError = _AnthropicAPIError
_anthropic_mock.BadRequestError = _AnthropicAPIError
_anthropic_mock.RateLimitError = _AnthropicAPIError
_anthropic_mock.AuthenticationError = _AnthropicAPIError
sys.modules.setdefault("anthropic", _anthropic_mock)
sys.modules.setdefault("anthropic.types", MagicMock())

# ---------------------------------------------------------------------------
# Fake 'httpx' — SBIA discovery_tools imports httpx for async HTTP calls.
# ---------------------------------------------------------------------------
_httpx_response_mock = MagicMock()
_httpx_response_mock.status_code = 200
_httpx_response_mock.ok = True
_httpx_response_mock.json.return_value = {}
_httpx_response_mock.text = ""
_httpx_response_mock.raise_for_status = MagicMock()

_httpx_mock = MagicMock()
_httpx_mock.post = MagicMock(return_value=_httpx_response_mock)
_httpx_mock.get  = MagicMock(return_value=_httpx_response_mock)

_httpx_client_instance = MagicMock()
_httpx_client_instance.__enter__ = MagicMock(return_value=_httpx_client_instance)
_httpx_client_instance.__exit__  = MagicMock(return_value=False)
_httpx_client_instance.get       = MagicMock(return_value=_httpx_response_mock)
_httpx_client_instance.post      = MagicMock(return_value=_httpx_response_mock)
_httpx_mock.Client = MagicMock(return_value=_httpx_client_instance)
sys.modules.setdefault("httpx", _httpx_mock)


# ---------------------------------------------------------------------------
# DynamoDB / HTTP response helpers
# ---------------------------------------------------------------------------

def _make_dynamo_table() -> MagicMock:
    """MagicMock with the fluent DynamoDB Table API."""
    t = MagicMock()
    t.put_item.return_value = {}
    t.get_item.return_value = {"Item": {}}
    t.query.return_value = {"Items": [], "Count": 0}
    t.scan.return_value = {"Items": [], "Count": 0}
    t.update_item.return_value = {"Attributes": {}}
    t.delete_item.return_value = {}
    # batch_writer context manager
    bw = MagicMock()
    bw.__enter__ = MagicMock(return_value=bw)
    bw.__exit__ = MagicMock(return_value=False)
    t.batch_writer.return_value = bw
    return t


def _make_http_response() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.ok = True
    r.json.return_value = {}
    r.text = ""
    r.raise_for_status = MagicMock()
    return r


# ---------------------------------------------------------------------------
# Autouse fixture — runs before/after every test in tests/integration/
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def integration_env(monkeypatch):
    """
    Set required env vars and patch all external I/O so agent modules can be
    imported and invoked without real AWS credentials or a live Claude API.
    """
    # ── Environment variables ────────────────────────────────────────────────
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")

    for _var in (
        # Slack webhooks
        "SLACK_RESONANCE_WEBHOOK", "SLACK_SYNC_WEBHOOK", "SLACK_PITCH_WEBHOOK",
        "SLACK_AG_WEBHOOK", "SLACK_ROYALTY_WEBHOOK", "SLACK_CULTURAL_WEBHOOK",
        "SLACK_FAN_WEBHOOK", "SLACK_AR_WEBHOOK", "SLACK_CS_WEBHOOK",
        "SLACK_SECURITY_WEBHOOK", "SLACK_DISCOVERY_WEBHOOK",
        "SLACK_APPROVAL_WEBHOOK", "SLACK_SOCIAL_WEBHOOK", "SLACK_BOOKING_WEBHOOK",
        # Email / SES
        "FROM_EMAIL", "HF_EMAIL", "SBIA_FROM_EMAIL", "SBIA_REPLY_TO",
        # DynamoDB tables — agent 01
        "MODEL_TABLE", "SIGNALS_TABLE", "BACKTEST_TABLE", "PREDICT_TABLE",
        # DynamoDB tables — agent 02
        "BRIEFS_TABLE", "CATALOG_TABLE", "SUBS_TABLE",
        # DynamoDB tables — agent 03
        "SUPERVISORS_TABLE", "PITCHES_TABLE",
        # DynamoDB tables — agent 04
        "SCOUT_TABLE", "AG_PITCHES_TABLE",
        # DynamoDB tables — agent 05
        "ROYALTY_TABLE", "ISSUES_TABLE",
        # DynamoDB tables — agent 06
        "MOMENTS_TABLE", "ENTROPY_TABLE",
        # DynamoDB tables — agent 07
        "FES_TABLE", "CLV_TABLE", "GEO_TABLE", "AFFI_TABLE", "APP_CONFIG_TABLE",
        # DynamoDB tables — agent 08
        "GAPS_TABLE", "TARGETS_TABLE",
        # DynamoDB tables — agent 09
        "SESSIONS_TABLE", "CS_TICKETS_TABLE", "CS_METRICS_TABLE",
        "ONBOARDING_TABLE", "NPS_TABLE",
        # DynamoDB tables — agent 10
        "ASSET_HASHES_TABLE", "SECURITY_EVENTS_TABLE",
        "SECURITY_ALERTS_TABLE", "FRAUD_REPORTS_TABLE",
        # DynamoDB tables — agent 11
        "OUTREACH_QUEUE_TABLE", "COMMUNITIES_TABLE",
        "ENTRY_POINTS_TABLE", "CONVERSIONS_TABLE",
        # DynamoDB tables — agent 12
        "CALENDAR_TABLE", "QUEUE_TABLE", "PERF_TABLE",
        "MENTIONS_TABLE", "ANALYTICS_TABLE", "CAMPAIGN_TABLE", "VOICE_TABLE",
        # DynamoDB tables — SBIA
        "SBIA_CONVENTIONS_TABLE", "SBIA_OUTREACH_LOG_TABLE",
        # AWS services / ARNs
        "KINESIS_STREAM", "CF_DISTRIBUTION_ID",
        "SNS_RESONANCE_TOPIC", "SNS_SECURITY_TOPIC",
        "SNS_CRITICAL_TOPIC", "SNS_ESCALATION_TOPIC",
        "SBIA_FOLLOWUP_LAMBDA_ARN", "SBIA_EPK_BUCKET", "SBIA_EMAIL_INBOX_BUCKET",
        "S3_BACKTEST_BUCKET", "S3_REPORTS_BUCKET",
        # External API keys
        "CHARTMETRIC_API_KEY", "SOUNDCHARTS_API_KEY",
        "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
        "YOUTUBE_API_KEY", "TIKTOK_RESEARCH_API_KEY",
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT",
        "MAILGUN_API_KEY", "MAILGUN_DOMAIN",
        "AIRTABLE_API_KEY", "AIRTABLE_BASE_ID",
        "SKYBLEW_VOICE_BOOK_SECRET_KEY", "SKYBLEW_CM_ID",
        # Social platform tokens
        "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID",
        "TIKTOK_ACCESS_TOKEN", "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET",
        "YOUTUBE_OAUTH_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID",
        "DISCORD_CHANNEL_ID", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID",
        "APPLE_MUSIC_CONFIRMED",
    ):
        monkeypatch.setenv(_var, f"test-{_var.lower().replace('_', '-')}")

    # ── boto3 mocks ──────────────────────────────────────────────────────────
    mock_table = _make_dynamo_table()
    mock_dynamo_resource = MagicMock()
    mock_dynamo_resource.Table.return_value = mock_table

    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "msg-test-ses"}
    mock_sns = MagicMock()
    mock_sns.publish.return_value = {"MessageId": "msg-test-sns"}
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.test/presigned"
    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.return_value = {"StatusCode": 200, "Payload": MagicMock()}
    mock_guardduty = MagicMock()
    mock_guardduty.list_detectors.return_value = {"DetectorIds": ["det-test"]}
    mock_guardduty.list_findings.return_value = {"FindingIds": []}
    mock_guardduty.get_findings.return_value = {"Findings": []}

    _client_registry = {
        "ses":         mock_ses,
        "sns":         mock_sns,
        "s3":          mock_s3,
        "lambda":      mock_lambda_client,
        "guardduty":   mock_guardduty,
    }

    def _boto3_client(service_name, **kwargs):
        return _client_registry.get(service_name, MagicMock())

    # ── HTTP mocks ───────────────────────────────────────────────────────────
    mock_http = _make_http_response()
    mock_session = MagicMock()
    mock_session.get.return_value = mock_http
    mock_session.post.return_value = mock_http

    # ── Re-inject fresh strands mocks so each test is independent ───────────
    sm, smm, sma = _build_strands_mocks()
    sys.modules["strands"] = sm
    sys.modules["strands.models"] = smm
    sys.modules["strands.models.anthropic"] = sma

    # ── Activate patches ─────────────────────────────────────────────────────
    with (
        patch("boto3.resource", return_value=mock_dynamo_resource),
        patch("boto3.client", side_effect=_boto3_client),
        patch("requests.post", return_value=mock_http),
        patch("requests.get",  return_value=mock_http),
        patch("requests.Session", return_value=mock_session),
    ):
        yield {
            "mock_table":          mock_table,
            "mock_dynamo_resource": mock_dynamo_resource,
        }

    # ── Post-test cleanup: evict agent/tools modules from sys.modules ────────
    # Prevents a previous agent's 'tools' package from shadowing the next
    # agent's when sys.path resolution hits the cache.
    _stale = [
        k for k in list(sys.modules)
        if k in ("agent",)
        or k.startswith("tools")
        or k in ("data",)
        or k.startswith("data.")
    ]
    for _k in _stale:
        del sys.modules[_k]


# ---------------------------------------------------------------------------
# Dynamic agent importer (called inside each test function)
# ---------------------------------------------------------------------------

def import_agent_module(agent_folder: str):
    """
    Dynamically import agents/<agent_folder>/agent.py.

    Must be called INSIDE a test function so that the integration_env
    fixture's patches are already active when module-level boto3 calls
    execute during exec_module().

    Purges stale 'agent' / 'tools' / 'data' cache entries before importing
    so consecutive tests targeting different agents never share a module.
    """
    agent_dir = os.path.join(REPO_ROOT, "agents", agent_folder)
    agent_py  = os.path.join(agent_dir, "agent.py")

    if not os.path.isfile(agent_py):
        raise FileNotFoundError(
            f"agent.py not found at {agent_py}. "
            f"Expected agents/{agent_folder}/agent.py"
        )

    # Ensure repo root and agent dir are on sys.path
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    # Purge stale module-cache entries before this import
    for _k in list(sys.modules):
        if (
            _k in ("agent",)
            or _k.startswith("tools")
            or _k in ("data",)
            or _k.startswith("data.")
        ):
            del sys.modules[_k]

    spec = importlib.util.spec_from_file_location("agent", agent_py)
    mod  = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(mod)                   # type: ignore[union-attr]
    return mod
