# Lumin MAS — Makefile
#
# Wraps the most common operations so you don't need to remember script paths.
#
# Usage:
#   make help                                    Print this message
#   make install AGENT=09-customer-success       Set up an agent's venv + deps
#   make run AGENT=09-customer-success TASK=daily_onboarding_sweep
#   make test                                    Run shared library tests
#   make test-agent AGENT=09-customer-success    Run one agent's tests
#   make new-agent AGENT=14-my-new-agent         Scaffold a new agent folder
#   make bootstrap-aws                           One-time shared AWS setup
#   make deploy AGENT=09-customer-success        Deploy one agent
#   make install-systemd AGENT=09-customer-success  Copy + enable systemd units
#   make logs AGENT=09-customer-success          Tail journalctl for an agent
#   make status                                  systemctl status all lumin timers
#   make clean                                   Remove all venvs and __pycache__
#
# AGENT is the agent suffix WITHOUT the 'agent-' prefix.
#   Correct:   AGENT=09-customer-success   (folder: agents/agent-09-customer-success)
#   Incorrect: AGENT=agent-09-customer-success

SHELL := /bin/bash
.DEFAULT_GOAL := help

REPO_ROOT := $(shell pwd)

# Computed from AGENT variable (if provided)
AGENT_FOLDER  = agent-$(AGENT)
AGENT_DIR     = $(REPO_ROOT)/agents/$(AGENT_FOLDER)

# Python to use for direct invocations (not inside a venv)
PYTHON ?= python

# ============================================================================
.PHONY: help
help: ## Print this usage message
	@echo ""
	@echo "  Lumin MAS — Makefile"
	@echo ""
	@echo "  make install AGENT=09-customer-success"
	@echo "      Set up an agent's Python 3.12 venv and install dependencies."
	@echo ""
	@echo "  make run AGENT=09-customer-success TASK=daily_onboarding_sweep"
	@echo "      Run a single agent task. Prints JSON result to stdout."
	@echo "      Pass extra event params with PARAMS='key=val key2=val2'."
	@echo ""
	@echo "  make test"
	@echo "      Run all shared library tests (pytest tests/shared/)."
	@echo ""
	@echo "  make test-agent AGENT=09-customer-success"
	@echo "      Run one agent's test suite (pytest agents/<name>/tests/)."
	@echo ""
	@echo "  make new-agent AGENT=14-my-new-agent"
	@echo "      Scaffold a new agent folder from the standard template."
	@echo ""
	@echo "  make bootstrap-aws"
	@echo "      Create shared AWS infrastructure (DynamoDB tables, SM placeholders)."
	@echo "      Idempotent — safe to run multiple times."
	@echo ""
	@echo "  make deploy AGENT=09-customer-success"
	@echo "      Full deploy: git pull, venv, pip install, tests, systemd reload."
	@echo ""
	@echo "  make install-systemd AGENT=09-customer-success"
	@echo "      Copy example timer + service files for this agent to"
	@echo "      /etc/systemd/system/ and enable them. Requires sudo."
	@echo ""
	@echo "  make logs AGENT=09-customer-success"
	@echo "      Tail the journalctl log for all tasks of this agent."
	@echo ""
	@echo "  make status"
	@echo "      Show systemctl status of all lumin-agent-*.timer units."
	@echo ""
	@echo "  make clean"
	@echo "      Remove all agent venvs, __pycache__ directories, and .pyc files."
	@echo ""
	@echo "  Variables:"
	@echo "    AGENT   Agent suffix, e.g. 09-customer-success (no 'agent-' prefix)"
	@echo "    TASK    Task name for 'make run', e.g. daily_onboarding_sweep"
	@echo "    PARAMS  Extra --params flags, e.g. 'user_id=abc session_id=xyz'"
	@echo "    PYTHON  Python executable (default: python)"
	@echo ""

# ============================================================================
.PHONY: install
install: ## Set up agent venv and install dependencies  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make install AGENT=09-customer-success" && exit 1)
	@echo "==> Installing: $(AGENT_FOLDER)"
	DEPLOY_SKIP_GIT=1 DEPLOY_SKIP_TESTS=1 bash scripts/deploy_agent.sh $(AGENT_FOLDER)

# ============================================================================
.PHONY: run
run: ## Run one agent task  [AGENT= TASK= PARAMS=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make run AGENT=09-customer-success TASK=daily_onboarding_sweep" && exit 1)
	@test -n "$(TASK)" || \
	    (echo "ERROR: TASK is required.   Example: make run AGENT=09-customer-success TASK=daily_onboarding_sweep" && exit 1)
	@echo "==> Running: $(AGENT_FOLDER) / $(TASK)"
	$(PYTHON) scripts/run_agent.py $(AGENT_FOLDER) $(TASK) \
	    $(if $(PARAMS),$(addprefix --params ,$(PARAMS)),)

# ============================================================================
.PHONY: test
test: ## Run all shared library tests
	@echo "==> Running shared library tests"
	$(PYTHON) -m pytest tests/shared/ -v

# ============================================================================
.PHONY: test-agent
test-agent: ## Run one agent's test suite  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make test-agent AGENT=09-customer-success" && exit 1)
	@test -d "$(AGENT_DIR)/tests" || \
	    (echo "ERROR: No tests/ directory found at $(AGENT_DIR)/tests" && exit 1)
	@echo "==> Testing: $(AGENT_FOLDER)"
	PYTHONPATH=$(REPO_ROOT):$(AGENT_DIR) \
	    $(PYTHON) -m pytest $(AGENT_DIR)/tests/ -v

# ============================================================================
.PHONY: new-agent
new-agent: ## Scaffold a new agent from the standard template  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make new-agent AGENT=14-my-new-agent" && exit 1)
	@echo "==> Scaffolding: $(AGENT_FOLDER)"
	bash scripts/new_agent.sh $(AGENT_FOLDER)

# ============================================================================
.PHONY: bootstrap-aws
bootstrap-aws: ## Create shared AWS infra (DynamoDB tables + SM placeholders)
	@echo "==> Bootstrapping shared AWS infrastructure"
	bash scripts/bootstrap_aws.sh

# ============================================================================
.PHONY: deploy
deploy: ## Full agent deploy: git pull, venv, pip, tests, systemd reload  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make deploy AGENT=09-customer-success" && exit 1)
	@echo "==> Deploying: $(AGENT_FOLDER)"
	bash scripts/deploy_agent.sh $(AGENT_FOLDER)

# ============================================================================
.PHONY: install-systemd
install-systemd: ## Copy + enable systemd timers for one agent  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make install-systemd AGENT=09-customer-success" && exit 1)
	@echo "==> Installing systemd units for $(AGENT_FOLDER)"
	@# Install the fleet-wide template if not already present
	@if [ ! -f /etc/systemd/system/lumin-agent@.service ]; then \
	    sudo cp infra/systemd/lumin-agent@.service /etc/systemd/system/; \
	    echo "  Installed lumin-agent@.service template"; \
	fi
	@# Copy all timer + service files matching this agent
	@TIMER_COUNT=$$(ls infra/systemd/example-timers/lumin-agent-$(AGENT)-*.timer 2>/dev/null | wc -l); \
	if [ "$$TIMER_COUNT" -eq 0 ]; then \
	    echo "WARNING: No timer files found matching lumin-agent-$(AGENT)-*.timer"; \
	    echo "         Add them to infra/systemd/example-timers/ first."; \
	    exit 0; \
	fi; \
	sudo cp infra/systemd/example-timers/lumin-agent-$(AGENT)-*.timer   /etc/systemd/system/; \
	sudo cp infra/systemd/example-timers/lumin-agent-$(AGENT)-*.service /etc/systemd/system/; \
	echo "  Copied $$TIMER_COUNT timer + service pair(s)"
	@sudo systemctl daemon-reload
	@for timer in infra/systemd/example-timers/lumin-agent-$(AGENT)-*.timer; do \
	    unit=$$(basename $$timer); \
	    sudo systemctl enable --now $$unit; \
	    echo "  Enabled: $$unit"; \
	done
	@echo ""
	@echo "  Verify: sudo systemctl list-timers 'lumin-agent-$(AGENT)-*'"
	@echo "  Logs:   make logs AGENT=$(AGENT)"

# ============================================================================
.PHONY: logs
logs: ## Tail journalctl for an agent  [AGENT=]
	@test -n "$(AGENT)" || \
	    (echo "ERROR: AGENT is required.  Example: make logs AGENT=09-customer-success" && exit 1)
	@echo "==> Tailing logs for $(AGENT_FOLDER) (Ctrl-C to stop)"
	sudo journalctl -u 'lumin-agent-$(AGENT)*' -f --no-pager

# ============================================================================
.PHONY: status
status: ## Show systemctl status of all lumin-agent timers
	@echo "==> Lumin agent timer status"
	sudo systemctl list-timers 'lumin-agent-*' --no-pager

# ============================================================================
.PHONY: clean
clean: ## Remove all agent venvs, __pycache__ dirs, and .pyc files
	@echo "==> Cleaning venvs and Python cache"
	@find agents/ -name venv -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -delete 2>/dev/null || true
	@find . -name '.pytest_cache' -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "  Done."
