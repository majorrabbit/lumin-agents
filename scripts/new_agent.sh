#!/usr/bin/env bash
# new_agent.sh — Scaffold a new Lumin MAS agent from the standard template.
#
# Usage:
#   ./scripts/new_agent.sh <agent-folder-name>
#
# Example:
#   ./scripts/new_agent.sh agent-14-my-new-feature
#
# Creates agents/<name>/ with:
#   agent.py           — stub entry point (obviously a template — full of TODOs)
#   tools/__init__.py  — empty tools package
#   requirements.txt   — standard 5-package baseline every agent uses
#   .env.example       — credential template
#   tests/__init__.py  — empty, makes tests/ a pytest-discoverable package
#   tests/test_agent.py — passing smoke test (no AWS calls)
#   docs/README.md     — documentation stub
#   docs/DEPLOY.md     — deployment instructions stub
#
# This script does NOT commit the result. Review and edit before committing.

set -euo pipefail

# ---- Color output -----------------------------------------------------------

if command -v tput &>/dev/null && tput setaf 1 &>/dev/null 2>&1; then
    C_GREEN="$(tput setaf 2)"
    C_BOLD="$(tput bold)"
    C_RESET="$(tput sgr0)"
else
    C_GREEN="" C_BOLD="" C_RESET=""
fi

info()    { echo "[new_agent] $*"; }
ok()      { echo "${C_GREEN}[  OK  ]${C_RESET} $*"; }

# ---- Validate argument ------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <agent-folder-name>" >&2
    echo "Example: $0 agent-14-my-new-feature" >&2
    exit 1
fi

AGENT_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
AGENT_DIR="${REPO_ROOT}/agents/${AGENT_NAME}"

# ---- Guard against overwriting existing work --------------------------------

if [[ -d "${AGENT_DIR}" ]]; then
    echo "ERROR: Agent folder already exists: ${AGENT_DIR}" >&2
    echo "       Delete it first if you want to re-scaffold." >&2
    exit 1
fi

info "Scaffolding: ${AGENT_NAME}"
info "Target:      ${AGENT_DIR}"
echo ""

mkdir -p "${AGENT_DIR}/tools"
mkdir -p "${AGENT_DIR}/tests"
mkdir -p "${AGENT_DIR}/docs"

# =============================================================================
# agent.py — stub entry point
# =============================================================================
# Uses 'AGENT_PY_EOF' (unquoted) so ${AGENT_NAME} expands,
# but all Python $ chars are escaped with backslash.

cat > "${AGENT_DIR}/agent.py" << AGENT_PY_EOF
"""
${AGENT_NAME} — Lumin MAS agent stub.

TODO: Replace this stub with the real agent implementation.

Cognitive architecture: BDI-O (Belief-Obligation-Intention-Desire)
Core principle — Win³: every action must win for artist, fan, AND world.
"""

from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# Model selection — env-var-first, Secrets Manager fallback (SBIA pattern)
# ---------------------------------------------------------------------------

def get_model() -> str:
    """
    Return the Claude model ID to use for this agent.

    TODO: update secret_id to the correct per-agent path, or keep using the
    shared lumin/anthropic-model secret if all agents share the same model.
    """
    # Fast path: env var already set (local .env or systemd EnvironmentFile)
    model = os.environ.get("ANTHROPIC_MODEL")
    if model:
        return model
    # Fallback: Secrets Manager
    from shared.secrets import get_credential  # noqa: PLC0415
    return get_credential(
        env_var="ANTHROPIC_MODEL",
        secret_id="lumin/anthropic-api-key",
        secret_key="model",
    )


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_agent():
    """
    Build and return a Strands Agent configured for this agent's role.

    TODO: Replace the system prompt and tool list with the real ones.
    """
    from strands import Agent  # noqa: PLC0415
    from shared.secrets import get_credential  # noqa: PLC0415

    api_key = get_credential(
        env_var="ANTHROPIC_API_KEY",
        secret_id="lumin/anthropic-api-key",
        secret_key="api_key",
    )

    # TODO: replace with real system prompt
    SYSTEM_PROMPT = """
You are a Lumin MAS agent. Replace this stub with your real system prompt.

Core principle — Win\xb3:
Every action must create genuine value for the artist, the fan, AND the world.
Never optimise for one at the expense of the others.
""".strip()

    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        api_key=api_key,
        # TODO: add tools=[] with your real tool list
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def run_status_check() -> dict:
    """
    Infrastructure-free heartbeat. No AWS calls, no agent creation.

    TODO: replace with a real status check that verifies key dependencies
    (DynamoDB table accessible, secrets readable, etc.).
    """
    return {
        "status": "ok",
        "agent": "${AGENT_NAME}",
        "message": "Status check passed. Replace this stub with a real task.",
    }


# ---------------------------------------------------------------------------
# Lambda handler — canonical Lumin MAS entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:
    """
    Dispatches on event["task"] (Pattern A) and event["trigger_type"] (Pattern B).
    The fleet runner sets both keys, so this handler is compatible with both.

    TODO: add real tasks to the dispatch table.
    """
    task = event.get("task") or event.get("trigger_type", "status_check")

    # Fast path: status_check never touches AWS
    if task == "status_check":
        return run_status_check()

    # Build dispatch table — lambdas create the agent lazily so unknown
    # tasks return an error without wasting a model-creation call.
    dispatch = {
        # TODO: add real tasks here, e.g.:
        # "daily_sweep": lambda: run_daily_sweep(create_agent(), event),
    }

    if task not in dispatch:
        return {
            "error": f"Unknown task: {task!r}",
            "available": ["status_check"] + list(dispatch.keys()),
        }

    try:
        return dispatch[task]()
    except Exception as exc:  # pylint: disable=broad-except
        return {"error": str(exc), "task": task}
AGENT_PY_EOF
ok "Created agent.py"

# =============================================================================
# tools/__init__.py
# =============================================================================

cat > "${AGENT_DIR}/tools/__init__.py" << 'TOOLS_INIT_EOF'
# Agent tools package.
# Add tool modules here as the agent grows, e.g.:
#   from tools.my_tool import my_tool
TOOLS_INIT_EOF
ok "Created tools/__init__.py"

# =============================================================================
# requirements.txt — standard 5-package baseline
# =============================================================================

cat > "${AGENT_DIR}/requirements.txt" << 'REQS_EOF'
strands-agents>=1.34.1
anthropic>=0.89.0
boto3>=1.42.0
requests>=2.32.0
python-dotenv>=1.0.0
REQS_EOF
ok "Created requirements.txt"

# =============================================================================
# .env.example
# =============================================================================

cat > "${AGENT_DIR}/.env.example" << 'ENV_EXAMPLE_EOF'
# Copy this file to .env and fill in your values.
# NEVER commit .env to version control.

ANTHROPIC_API_KEY=sk-ant-...
AWS_DEFAULT_REGION=us-east-1

# TODO: add agent-specific environment variables below.
# Variables listed here should also be documented in docs/README.md.
#
# Example:
# MY_WEBHOOK_URL=https://hooks.slack.com/...
# MY_API_KEY=...
ENV_EXAMPLE_EOF
ok "Created .env.example"

# =============================================================================
# tests/__init__.py
# =============================================================================

touch "${AGENT_DIR}/tests/__init__.py"
ok "Created tests/__init__.py"

# =============================================================================
# tests/test_agent.py — smoke tests (no AWS calls)
# =============================================================================

cat > "${AGENT_DIR}/tests/test_agent.py" << 'TEST_PY_EOF'
"""
Smoke tests for this agent stub.

These tests verify the module structure without making any AWS calls.
Extend this file as the agent gains real tasks and tools.
"""

import importlib.util
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# Loader helper — imports agent.py without going through the package system
# ---------------------------------------------------------------------------

def _load_agent():
    """Import agent.py from this agent's directory."""
    agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(os.path.dirname(agent_dir))
    for path in (repo_root, agent_dir):
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(
        "agent", os.path.join(agent_dir, "agent.py")
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_lambda_handler_exists():
    """agent.py must expose a callable lambda_handler."""
    agent = _load_agent()
    assert callable(getattr(agent, "lambda_handler", None)), (
        "agent.py must define a callable lambda_handler(event, context)"
    )


def test_status_check_returns_ok():
    """status_check task must return without AWS calls."""
    agent = _load_agent()
    result = agent.lambda_handler({"task": "status_check"}, None)
    assert isinstance(result, dict), "lambda_handler must return a dict"
    assert result.get("status") == "ok", f"Expected status=ok, got: {result}"


def test_unknown_task_returns_error_key():
    """Unknown tasks must return a dict with 'error' key, not raise."""
    agent = _load_agent()
    result = agent.lambda_handler({"task": "__nonexistent__"}, None)
    assert isinstance(result, dict), "lambda_handler must return a dict"
    assert "error" in result, (
        f"Unknown task should return dict with 'error' key, got: {result}"
    )


def test_trigger_type_key_also_dispatches():
    """SBIA-style event (trigger_type key) must also reach status_check."""
    agent = _load_agent()
    result = agent.lambda_handler({"trigger_type": "status_check"}, None)
    assert result.get("status") == "ok", (
        f"trigger_type dispatch failed. Got: {result}"
    )
TEST_PY_EOF
ok "Created tests/test_agent.py"

# =============================================================================
# docs/README.md
# =============================================================================

{
echo "# ${AGENT_NAME}"
cat << 'README_BODY_EOF'

<!-- TODO: describe what this agent does, which entity it serves, and its schedule. -->

## Purpose

TODO: one paragraph describing this agent's role in the Lumin MAS fleet,
which of the three entities it serves (Lumin Luxe Inc. / OPP Inc. /
2StepsAboveTheStars LLC), and how it embodies the Win³ principle.

## Tasks

| Task | Trigger | Description |
|------|---------|-------------|
| `status_check` | manual | Heartbeat — no AWS calls, confirms agent is importable |
| TODO | TODO | Replace with real task table |

## Dispatch key

This agent dispatches on `event["task"]` (Pattern A — same as most fleet agents).
Update this section if you switch to `event["trigger_type"]` (SBIA Pattern B).

## Environment Variables

| Variable | Required | Source | Description |
|----------|----------|--------|-------------|
| `ANTHROPIC_API_KEY` | Yes | `.env` / Secrets Manager | Claude API key |
| `AWS_DEFAULT_REGION` | No | `.env` | AWS region (default: `us-east-1`) |

TODO: add agent-specific variables to the table above.

## Win³ Alignment

TODO: explain how this agent's actions create value for:
- **Artist**: ...
- **Fan**: ...
- **World**: ...

## BDI-O Frame

TODO: describe the agent's typical belief, obligation, intention, and desire
at runtime so future maintainers can audit its `log_action` calls.
README_BODY_EOF
} > "${AGENT_DIR}/docs/README.md"
ok "Created docs/README.md"

# =============================================================================
# docs/DEPLOY.md
# =============================================================================

{
echo "# Deploy: ${AGENT_NAME}"
printf '\n'
cat << 'DEPLOY_BODY_EOF'
## Quick deploy

```bash
./scripts/deploy_agent.sh AGENT_NAME_PLACEHOLDER
```

## One-shot manual run

```bash
python scripts/run_agent.py AGENT_NAME_PLACEHOLDER status_check
```

## First-time setup

1. Copy `.env.example` to `.env` and fill in credentials.
2. Run `bash scripts/bootstrap_aws.sh` once per AWS account (shared infra).
3. Create any agent-specific DynamoDB tables (document them here).
4. Run `./scripts/deploy_agent.sh AGENT_NAME_PLACEHOLDER` to install the venv.

## Agent-specific AWS resources

TODO: list the DynamoDB tables, Secrets Manager paths, and any other AWS
resources this agent requires. For each resource, note whether it is
created by bootstrap_aws.sh (shared) or by this agent's deploy (per-agent).

| Resource | Type | Created by | Purpose |
|----------|------|-----------|---------|
| TODO | DynamoDB | deploy_agent.sh | ... |

## Systemd unit files

TODO: add unit file paths and timer schedules here once the agent is
ready for production scheduling on EC2.
DEPLOY_BODY_EOF
} | sed "s/AGENT_NAME_PLACEHOLDER/${AGENT_NAME}/g" > "${AGENT_DIR}/docs/DEPLOY.md"
ok "Created docs/DEPLOY.md"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "${C_GREEN}${C_BOLD}=== Scaffold complete: ${AGENT_NAME} ===${C_RESET}"
echo ""
echo "  ${AGENT_DIR}/"
echo "  ├── agent.py           (stub — fill in system prompt and tasks)"
echo "  ├── requirements.txt   (5-package baseline)"
echo "  ├── .env.example       (copy to .env, fill in credentials)"
echo "  ├── tools/"
echo "  │   └── __init__.py"
echo "  ├── tests/"
echo "  │   ├── __init__.py"
echo "  │   └── test_agent.py  (4 smoke tests — all pass without AWS)"
echo "  └── docs/"
echo "      ├── README.md"
echo "      └── DEPLOY.md"
echo ""
echo "  Next steps:"
echo "    1. Edit ${AGENT_DIR}/agent.py"
echo "       Replace # TODO stubs with real system prompt and tasks."
echo ""
echo "    2. Verify smoke tests pass:"
echo "       pytest agents/${AGENT_NAME}/tests/ -v"
echo ""
echo "    3. Run the status check:"
echo "       python scripts/run_agent.py ${AGENT_NAME} status_check"
echo ""
echo "    4. When ready to deploy:"
echo "       ./scripts/deploy_agent.sh ${AGENT_NAME}"
echo ""
