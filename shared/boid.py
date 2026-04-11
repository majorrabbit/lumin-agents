"""
BOID action audit log for the Lumin MAS fleet.

WHY THIS EXISTS:
The BDI-O (Belief-Obligation-Intention-Desire) framework is the cognitive
architecture of the Lumin MAS. Every agent action has a reason rooted in the
agent's current beliefs, constrained by its obligations, directed by its
intentions, and motivated by its desires.

Logging actions in BOID terms creates an auditable trail that answers the
question "why did the agent do that?" — not just "what did it do?" This is
essential for debugging unexpected agent behavior and for the investor
narrative around AI governance.

The audit table is a fleet-wide resource (all agents write to the same table
by default). Individual agents can override the table name to write to their
own isolated audit table if needed.

CRITICAL DESIGN DECISION — NEVER RAISES:
Audit logging breaking an agent is worse than missing a few audit entries.
If the DynamoDB write fails, we log a WARNING and continue. The agent's
primary task is never blocked by an audit failure.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from shared.dynamo import now_iso, put_record

logger = logging.getLogger(__name__)

_BOID_TABLE_DEFAULT = "lumin-boid-actions"


def log_action(
    *,
    table_name: Optional[str] = None,
    agent: str,
    action: str,
    belief: str,
    obligation: str,
    intention: str,
    desire: str,
    result: Optional[dict] = None,
) -> None:
    """
    Write a BOID-structured audit record for an agent action.

    This function NEVER raises. Any failure to write to DynamoDB is logged
    as a WARNING and silently swallowed. The caller's primary task continues
    regardless of audit log availability.

    Args:
        table_name:  DynamoDB table to write to. Defaults to the value of
                     LUMIN_BOID_TABLE env var, or "lumin-boid-actions".
        agent:       Agent identifier. e.g. "agent01-resonance"
        action:      Short action label. e.g. "run_weekly_backtest"
        belief:      What the agent believed to be true at decision time.
                     e.g. "Entropy variance 2.4x above baseline"
        obligation:  The rule or constraint that governed this action.
                     e.g. "Never skip Sunday backtest"
        intention:   The immediate goal this action serves.
                     e.g. "Compute walk-forward Brier score"
        desire:      The long-term goal this action contributes to.
                     e.g. "Brier score < 0.18 by Month 6"
        result:      Optional dict of action outcome data. Written as-is.

    Examples:
        log_action(
            agent="agent01-resonance",
            action="run_weekly_backtest",
            belief="7 days of predictions exist with known outcomes",
            obligation="Brier score computed every Sunday without exception",
            intention="Compute walk-forward accuracy proof",
            desire="Investor-grade track record, Brier < 0.18",
            result={"brier_score": 0.14, "predictions_count": 47},
        )
    """
    tbl = table_name or os.environ.get("LUMIN_BOID_TABLE", _BOID_TABLE_DEFAULT)

    try:
        ts = now_iso()
        put_record(
            tbl,
            pk=f"BOID#{agent}",
            sk=f"{ts}#{action}",
            agent=agent,
            action=action,
            belief=belief,
            obligation=obligation,
            intention=intention,
            desire=desire,
            result=result or {},
            recorded_at=ts,
        )
        logger.debug("BOID logged: agent=%s action=%s", agent, action)
    except Exception as exc:
        logger.warning(
            "BOID audit log write failed (non-fatal): agent=%s action=%s error=%s",
            agent, action, exc,
        )
