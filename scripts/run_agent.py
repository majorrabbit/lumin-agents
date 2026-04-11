#!/usr/bin/env python3
"""
Universal one-shot runner for the Lumin MAS agent fleet.

Usage:
    python scripts/run_agent.py <agent-folder-name> <task-or-trigger> [--params KEY=VALUE ...]
    python -m scripts.run_agent <agent-folder-name> <task-or-trigger> [--params KEY=VALUE ...]

Examples:
    python scripts/run_agent.py agent-09-customer-success daily_onboarding_sweep
    python scripts/run_agent.py agent-09-customer-success inbound_support \\
        --params user_id=cus_abc123 --params message="how do I export?" \\
        --params session_id=sess_xyz
    python scripts/run_agent.py agent-01-resonance daily_physics_update
    python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN
    python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN --params dry_run=true

Exit codes:
    0  — agent returned a result dict with no 'error' key
    1  — agent raised an exception OR result contains an 'error' key

Design notes:
    - Sets BOTH event["task"] and event["trigger_type"] to the same value.
      12 agents dispatch on "task"; SBIA dispatches on "trigger_type".
      Setting both makes this runner compatible with every agent in the fleet
      without knowing (or caring) which key each agent uses internally.
    - Never imports any agent module at import time. All agent imports happen
      inside main() via importlib, one agent per invocation.
    - No retry logic. No scheduling. 1-shot dispatcher only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
import traceback


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    """Absolute path to the repo root (parent of the scripts/ directory)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def _load_dotenv(repo_root: str) -> None:
    """
    Load .env from the repo root via python-dotenv if available.

    Silent no-op when python-dotenv is not installed (e.g., production EC2
    where env is injected by systemd). Existing env vars are never overwritten
    (override=False) so systemd-provided values always win.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
        env_path = os.path.join(repo_root, ".env")
        load_dotenv(env_path, override=False)
    except ImportError:
        pass  # Not installed — fine. EC2 systemd unit provides the env.


# ---------------------------------------------------------------------------
# Parameter coercion
# ---------------------------------------------------------------------------

def _coerce_value(raw: str):
    """
    Coerce a --params string value to the most specific Python type.

    Precedence: bool → int → float → str
    """
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_params(param_list: list[str]) -> dict:
    """
    Parse a list of 'KEY=VALUE' strings into a dict with coerced values.

    Malformed entries (no '=') are warned about and skipped.
    """
    result: dict = {}
    for item in param_list:
        if "=" not in item:
            print(
                f"WARNING: --params value {item!r} has no '=' separator — skipped.",
                file=sys.stderr,
            )
            continue
        key, _, raw_value = item.partition("=")
        result[key.strip()] = _coerce_value(raw_value)
    return result


# ---------------------------------------------------------------------------
# Agent module loader
# ---------------------------------------------------------------------------

def _import_agent_module(agent_dir: str):
    """
    Dynamically import agents/<name>/agent.py as a fresh module named 'agent'.

    Uses importlib.util so we never need the agent folder on sys.path at
    import time — it's only added right before this call.
    """
    agent_py = os.path.join(agent_dir, "agent.py")
    if not os.path.isfile(agent_py):
        raise FileNotFoundError(
            f"agent.py not found: {agent_py}\n"
            f"Expected at agents/<name>/agent.py"
        )
    spec = importlib.util.spec_from_file_location("agent", agent_py)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_agent",
        description="Universal one-shot dispatcher for Lumin MAS agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python scripts/run_agent.py agent-09-customer-success daily_onboarding_sweep
  python scripts/run_agent.py agent-09-customer-success inbound_support \\
      --params user_id=cus_abc123 --params message="how do I export?"
  python scripts/run_agent.py agent-01-resonance daily_physics_update
  python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN
  python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN --params dry_run=true

exit codes:
  0   result dict has no 'error' key
  1   result dict has 'error' key, or agent raised an exception
""",
    )
    parser.add_argument(
        "agent_name",
        help=(
            "Agent folder name under agents/. "
            "e.g. agent-01-resonance, agent-09-customer-success, agent-sbia-booking"
        ),
    )
    parser.add_argument(
        "task",
        help=(
            "Task or trigger name passed to lambda_handler. "
            "e.g. daily_physics_update, inbound_support, DISCOVERY_RUN"
        ),
    )
    parser.add_argument(
        "--params",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        help=(
            "Event parameters to include in the handler payload. "
            "Repeat the flag for multiple params. "
            "Values are auto-coerced: 'true'/'false' -> bool, integers -> int, "
            "decimals -> float, everything else stays a str. "
            "Example: --params dry_run=true --params user_id=cus_abc123"
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    # ── Step 1: Load .env (silent if python-dotenv absent or file missing) ──
    _load_dotenv(repo_root)

    # ── Step 2: Wire sys.path so shared.* and agent.* imports work ──────────
    #    Repo root must come first so 'import shared.X' resolves correctly.
    #    Agent dir is added so the agent's own 'from tools.X import Y' works.
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    agent_dir = os.path.join(repo_root, "agents", args.agent_name)
    if not os.path.isdir(agent_dir):
        print(
            f"ERROR: Agent folder not found: {agent_dir}\n"
            f"       Check that '{args.agent_name}' exists under agents/",
            file=sys.stderr,
        )
        return 1

    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    # ── Step 3: Configure logging ────────────────────────────────────────────
    from shared.logging_config import configure_logging  # noqa: PLC0415
    configure_logging(args.agent_name)
    log = logging.getLogger("run_agent")

    # ── Step 4: Build event dict ─────────────────────────────────────────────
    #    Set BOTH 'task' and 'trigger_type' — 12 agents use 'task'; SBIA uses
    #    'trigger_type'. Setting both makes this runner compatible with the
    #    entire fleet without per-agent knowledge.
    params = _parse_params(args.params)
    event: dict = {
        "task": args.task,
        "trigger_type": args.task,
        **params,
    }
    log.debug("Dispatching: agent=%s event=%s", args.agent_name, event)

    # ── Step 5: Dynamically import the agent module ──────────────────────────
    try:
        agent_module = _import_agent_module(agent_dir)
    except FileNotFoundError as exc:
        log.error("Could not load agent module: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not hasattr(agent_module, "lambda_handler"):
        log.error("agent.py has no lambda_handler function")
        print(
            f"ERROR: {agent_dir}/agent.py does not define lambda_handler(event, context)",
            file=sys.stderr,
        )
        return 1

    # ── Step 6: Invoke lambda_handler(event, None) ───────────────────────────
    try:
        result = agent_module.lambda_handler(event, None)
    except Exception:
        log.exception("Agent raised an unhandled exception")
        traceback.print_exc()
        return 1

    # ── Step 7: Emit result as a single JSON line, determine exit code ───────
    try:
        output = json.dumps(result, default=str)
    except (TypeError, ValueError):
        output = json.dumps({"raw_result": str(result)})

    print(output)

    if isinstance(result, dict) and "error" in result:
        log.warning("Agent returned an error: %s", result.get("error"))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
