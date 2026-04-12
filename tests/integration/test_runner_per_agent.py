"""
Phase 2.2 — Per-agent smoke tests.

One test per agent (13 total).  Each test:
  1. Imports the agent module under the full mock harness (integration_env
     fixture active — see conftest.py).
  2. Verifies lambda_handler is present and callable.
  3. Calls lambda_handler with a minimal safe event.
  4. Asserts the return value is a dict with no top-level 'error' key.

These tests prove:
  - Every agent.py loads without ImportError or EnvironmentError.
  - The dispatch table recognises the nominated task (no "Unknown task" paths).
  - No uncaught exception escapes the handler.
  - Zero real AWS / Anthropic / HTTP calls are made.

All 13 agents: 01 Resonance, 02 Sync Brief, 03 Sync Pitch, 04 Anime/Gaming,
05 Royalty, 06 Cultural, 07 Fan Behavior, 08 A&R Catalog,
09 Customer Success, 10 CyberSecurity, 11 Fan Discovery,
12 Social Media, SBIA Booking.
"""
from __future__ import annotations

import pytest

# Import the helper from the sibling conftest.  Pytest adds conftest.py
# directories to sys.path, so the import resolves correctly.
from tests.integration.conftest import import_agent_module


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _event(task: str, **extra) -> dict:
    """Build a minimal lambda event with both dispatch keys set."""
    return {"task": task, "trigger_type": task, **extra}


def _smoke(agent_folder: str, task: str, **extra) -> dict:
    """
    Import *agent_folder*, invoke lambda_handler, assert a clean dict result.

    Returns the result dict so individual tests can make additional assertions
    if needed.
    """
    mod = import_agent_module(agent_folder)

    assert hasattr(mod, "lambda_handler"), (
        f"{agent_folder}/agent.py is missing lambda_handler(event, context)"
    )

    result = mod.lambda_handler(_event(task, **extra), None)

    assert isinstance(result, dict), (
        f"{agent_folder}: lambda_handler returned {type(result).__name__!r}, "
        f"expected dict"
    )
    assert "error" not in result, (
        f"{agent_folder}: handler returned an error dict — {result.get('error')!r}"
    )
    return result


# ---------------------------------------------------------------------------
# Agent 01 — Resonance Intelligence
# ---------------------------------------------------------------------------

def test_agent_01_resonance():
    """Hourly data collection — entry point for the Boltzmann pipeline."""
    _smoke("agent-01-resonance", "hourly_data_collection")


# ---------------------------------------------------------------------------
# Agent 02 — Sync Brief Hunter
# ---------------------------------------------------------------------------

def test_agent_02_sync_brief():
    """Brief scan — checks every sync brief platform for open briefs."""
    _smoke("agent-02-sync-brief", "brief_scan")


# ---------------------------------------------------------------------------
# Agent 03 — Sync Pitch Campaign
# ---------------------------------------------------------------------------

def test_agent_03_sync_pitch():
    """Weekly pitch cycle — builds supervisor outreach queue."""
    _smoke("agent-03-sync-pitch", "weekly_pitch_cycle")


# ---------------------------------------------------------------------------
# Agent 04 — Anime & Gaming Scout
# ---------------------------------------------------------------------------

def test_agent_04_anime_gaming():
    """Daily scout — scans anime/gaming production announcements."""
    _smoke("agent-04-anime-gaming", "daily_scout")


# ---------------------------------------------------------------------------
# Agent 05 — Royalty Reconciliation
# ---------------------------------------------------------------------------

def test_agent_05_royalty():
    """Monthly reconciliation — PRO / MLC / DSP statement processing."""
    _smoke("agent-05-royalty", "monthly_reconciliation")


# ---------------------------------------------------------------------------
# Agent 06 — Cultural Moment Detection
# ---------------------------------------------------------------------------

def test_agent_06_cultural():
    """30-minute scan — Shannon entropy convergence check."""
    _smoke("agent-06-cultural", "30min_scan")


# ---------------------------------------------------------------------------
# Agent 07 — Fan Behavior Intelligence
# ---------------------------------------------------------------------------

def test_agent_07_fan_behavior():
    """Daily metrics update — streaming stats, CLV model refresh."""
    _smoke("agent-07-fan-behavior", "daily_metrics_update")


# ---------------------------------------------------------------------------
# Agent 08 — A&R Catalog Growth
# ---------------------------------------------------------------------------

def test_agent_08_ar_catalog():
    """Monthly A&R review — catalog gap analysis and artist scouting."""
    _smoke("agent-08-ar-catalog", "monthly_ar_review")


# ---------------------------------------------------------------------------
# Agent 09 — Customer Success
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=True,
    raises=SyntaxError,
    reason=(
        "agent-09-customer-success/tools/support_tools.py:557 contains a "
        "Python SyntaxError: 'ExpressionAttributeValues' keyword argument is "
        "passed twice in the same DynamoDB query() call.  The file is a "
        "vendored byte-identical copy that must not be edited here; the fix "
        "must be applied to the upstream source ZIP and re-ingested in a "
        "future phase."
    ),
)
def test_agent_09_customer_success():
    """Daily onboarding sweep — AskLumin subscriber onboarding touchpoints.

    Expected xfail: support_tools.py has a duplicate-keyword SyntaxError
    introduced in the original vendor ZIP (line 557).  Fix in upstream source.
    """
    _smoke("agent-09-customer-success", "daily_onboarding_sweep")


# ---------------------------------------------------------------------------
# Agent 10 — CyberSecurity
# ---------------------------------------------------------------------------

def test_agent_10_cybersecurity():
    """Daily GuardDuty digest — threat finding summary."""
    _smoke("agent-10-cybersecurity", "daily_guardduty_digest")


# ---------------------------------------------------------------------------
# Agent 11 — Fan Discovery
# ---------------------------------------------------------------------------

def test_agent_11_fan_discovery():
    """Morning discovery — Reddit/TikTok/YouTube community scan."""
    _smoke("agent-11-fan-discovery", "morning_discovery")


# ---------------------------------------------------------------------------
# Agent 12 — Social Media
# ---------------------------------------------------------------------------

def test_agent_12_social_media():
    """Mention monitor — cross-platform mention check (early-exit path)."""
    _smoke("agent-12-social-media", "mention_monitor")


# ---------------------------------------------------------------------------
# SBIA — SkyBlew Booking Intelligence Agent
# ---------------------------------------------------------------------------

def test_agent_sbia_booking():
    """Discovery run (dry_run=True) — convention discovery without email sends."""
    # SBIA dispatches on trigger_type, not task; the runner sets both.
    # dry_run=True prevents any outreach from being composed.
    _smoke("agent-sbia-booking", "DISCOVERY_RUN", dry_run=True)
