#!/usr/bin/env bash
# deploy_agent.sh — Deploy a single Lumin MAS agent on this machine.
#
# Usage:
#   ./scripts/deploy_agent.sh <agent-folder-name>
#
# Examples:
#   ./scripts/deploy_agent.sh agent-01-resonance
#   ./scripts/deploy_agent.sh agent-09-customer-success
#   DEPLOY_SKIP_TESTS=1 ./scripts/deploy_agent.sh agent-sbia-booking
#
# Environment overrides:
#   DEPLOY_SKIP_GIT=1     Skip 'git pull' (useful when testing local changes)
#   DEPLOY_SKIP_TESTS=1   Skip pytest (useful for faster re-deploys)
#   AWS_REGION            AWS region (default: us-east-1)

set -euo pipefail

# ---- Color output (degrades gracefully in non-interactive shells) -----------

if command -v tput &>/dev/null && tput setaf 1 &>/dev/null 2>&1; then
    C_GREEN="$(tput setaf 2)"
    C_RED="$(tput setaf 1)"
    C_YELLOW="$(tput setaf 3)"
    C_BOLD="$(tput bold)"
    C_RESET="$(tput sgr0)"
else
    C_GREEN="" C_RED="" C_YELLOW="" C_BOLD="" C_RESET=""
fi

info()    { echo "${C_BOLD}[deploy]${C_RESET}  $*"; }
ok()      { echo "${C_GREEN}[  OK  ]${C_RESET}  $*"; }
warn()    { echo "${C_YELLOW}[ WARN ]${C_RESET}  $*"; }
fail()    { echo "${C_RED}[ FAIL ]${C_RESET}  $*" >&2; }

# Track overall success so we can print a clean summary even after set -e
DEPLOY_OK=1
_on_error() {
    DEPLOY_OK=0
    fail "Unexpected error on line ${LINENO} — deploy aborted."
}
trap '_on_error' ERR

# ---- Validate argument ------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <agent-folder-name>" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 agent-01-resonance" >&2
    echo "  $0 agent-09-customer-success" >&2
    exit 1
fi

AGENT_NAME="$1"

# ---- Resolve paths ----------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
AGENT_DIR="${REPO_ROOT}/agents/${AGENT_NAME}"
VENV_DIR="${AGENT_DIR}/venv"

echo ""
echo "${C_BOLD}=== Lumin MAS Deploy: ${AGENT_NAME} ===${C_RESET}"
echo "    Repo:  ${REPO_ROOT}"
echo "    Agent: ${AGENT_DIR}"
echo ""

# ---- Step 1: Verify agent folder exists ------------------------------------

info "Step 1 — Verifying agent folder"
if [[ ! -d "${AGENT_DIR}" ]]; then
    fail "Agent folder not found: ${AGENT_DIR}"
    fail "Run './scripts/new_agent.sh ${AGENT_NAME}' to scaffold it first."
    exit 1
fi
ok "Agent folder exists."

# ---- Step 2: Pull latest code from git -------------------------------------

info "Step 2 — Updating code from git"
if [[ "${DEPLOY_SKIP_GIT:-0}" == "1" ]]; then
    warn "DEPLOY_SKIP_GIT=1 — skipping git pull."
else
    cd "${REPO_ROOT}"
    git pull --ff-only
    ok "Git pull complete."
fi

# ---- Step 3: Create or update per-agent venv --------------------------------

info "Step 3 — Setting up Python 3.12 venv: ${VENV_DIR}"
if [[ ! -d "${VENV_DIR}" ]]; then
    python3.12 -m venv "${VENV_DIR}"
    ok "Venv created."
else
    ok "Venv already exists — will update packages."
fi

PIP="${VENV_DIR}/bin/pip"
PYTHON="${VENV_DIR}/bin/python"

# ---- Step 4: Install dependencies ------------------------------------------

info "Step 4 — Installing dependencies"

"${PIP}" install --upgrade pip --quiet
ok "pip upgraded."

ROOT_REQS="${REPO_ROOT}/requirements.txt"
if [[ -f "${ROOT_REQS}" ]]; then
    "${PIP}" install -r "${ROOT_REQS}" --quiet
    ok "Installed root requirements.txt"
else
    warn "No root requirements.txt found — skipping."
fi

AGENT_REQS="${AGENT_DIR}/requirements.txt"
if [[ -f "${AGENT_REQS}" ]]; then
    "${PIP}" install -r "${AGENT_REQS}" --quiet
    ok "Installed agent requirements.txt"
else
    info "No agent-specific requirements.txt — skipping."
fi

# ---- Step 5: Run tests -------------------------------------------------------

info "Step 5 — Running tests"
AGENT_TESTS="${AGENT_DIR}/tests"

if [[ "${DEPLOY_SKIP_TESTS:-0}" == "1" ]]; then
    warn "DEPLOY_SKIP_TESTS=1 — skipping pytest."
elif [[ ! -d "${AGENT_TESTS}" ]]; then
    warn "No tests/ directory found at ${AGENT_TESTS} — skipping."
else
    PYTHONPATH="${REPO_ROOT}:${AGENT_DIR}" \
        "${VENV_DIR}/bin/pytest" "${AGENT_TESTS}" -v --tb=short
    ok "All tests passed."
fi

# ---- Step 6: Reload systemd timers ------------------------------------------

info "Step 6 — Reloading systemd timers"

TIMER_GLOB="lumin-agent-${AGENT_NAME}-*.timer"
MATCHING_TIMERS=()

# Scan standard systemd unit directories
for search_dir in /etc/systemd/system /lib/systemd/system; do
    if [[ -d "${search_dir}" ]]; then
        while IFS= read -r timer_file; do
            MATCHING_TIMERS+=("$(basename "${timer_file}")")
        done < <(find "${search_dir}" -maxdepth 1 -name "${TIMER_GLOB}" -type f 2>/dev/null)
    fi
done

if [[ ${#MATCHING_TIMERS[@]} -eq 0 ]]; then
    warn "No systemd timers matching '${TIMER_GLOB}' found."
    info "  Install unit files to /etc/systemd/system/ when ready to schedule."
else
    sudo systemctl daemon-reload
    ok "systemctl daemon-reload complete."
    for timer in "${MATCHING_TIMERS[@]}"; do
        sudo systemctl restart "${timer}"
        ok "Restarted timer: ${timer}"
    done
fi

# ---- Step 7: Tail service logs (if we have access) --------------------------

info "Step 7 — Checking recent service logs"

if [[ "${EUID}" -eq 0 ]] || sudo -n true 2>/dev/null; then
    SERVICE_GLOB="lumin-agent-${AGENT_NAME}-*.service"
    MATCHING_SERVICES=()

    for search_dir in /etc/systemd/system /lib/systemd/system; do
        if [[ -d "${search_dir}" ]]; then
            while IFS= read -r svc_file; do
                MATCHING_SERVICES+=("$(basename "${svc_file}")")
            done < <(find "${search_dir}" -maxdepth 1 -name "${SERVICE_GLOB}" -type f 2>/dev/null)
        fi
    done

    if [[ ${#MATCHING_SERVICES[@]} -gt 0 ]]; then
        UNIT="${MATCHING_SERVICES[0]}"
        info "  Tailing ${UNIT} for 10 seconds ..."
        timeout 10 sudo journalctl -u "${UNIT}" -f --no-pager 2>/dev/null || true
    else
        warn "No matching service unit found — skipping log tail."
    fi
else
    warn "Not running as root / sudo not available — skipping log tail."
fi

# ---- Summary ----------------------------------------------------------------

echo ""
if [[ "${DEPLOY_OK}" -eq 1 ]]; then
    echo "${C_GREEN}${C_BOLD}=== Deploy complete: ${AGENT_NAME} ===${C_RESET}"
    echo ""
    echo "  Agent:  ${AGENT_DIR}"
    echo "  Venv:   ${VENV_DIR}"
    echo ""
    echo "  To run manually:"
    echo "    python scripts/run_agent.py ${AGENT_NAME} <task>"
    echo ""
    exit 0
else
    echo "${C_RED}${C_BOLD}=== Deploy FAILED: ${AGENT_NAME} ===${C_RESET}"
    echo ""
    exit 1
fi
