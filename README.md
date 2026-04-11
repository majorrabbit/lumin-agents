# Lumin MAS — Multi-Agent System

The Lumin Multi-Agent System is a fleet of 13 specialized AI agents operating
across three interdependent companies: **Lumin Luxe Inc.** (technology and IP
platform), **OPP Inc.** (music publishing with one-stop sync clearance), and
**2StepsAboveTheStars LLC** (the independent hip-hop artist SkyBlew and his
catalog). The agents run on AWS Strands Agents backed by Claude Sonnet 4.6,
deployed EC2-first with full Lambda compatibility. They handle the operational
layer — market intelligence, fan engagement, revenue operations, security
monitoring — so H.F. (CEO) and Eric (CTO) can focus on decisions that require
human judgment. Every agent action is governed by the **Win³ principle**: it
must win for the artist, win for the fan, and win for the world simultaneously.

---

## Quick Start on a Fresh Machine

```bash
# 1. Clone the repo
git clone <repo-url> lumin-agents
cd lumin-agents

# 2. Install shared library dependencies
pip install boto3 requests python-dotenv pytest

# 3. Verify the shared library tests pass (119 tests, no AWS required)
pytest tests/shared/ -v

# 4. Verify the runner help
python scripts/run_agent.py --help

# 5. Scaffold a test agent and run its status check
./scripts/new_agent.sh agent-test
python scripts/run_agent.py agent-test status_check
# Expected output: {"status": "ok", "agent": "agent-test", ...}

# 6. Clean up the scaffold
rm -rf agents/agent-test

# 7. (One-time, requires AWS credentials) Bootstrap shared AWS infrastructure
bash scripts/bootstrap_aws.sh

# 8. Deploy your first real agent
./scripts/deploy_agent.sh agent-09-customer-success
python scripts/run_agent.py agent-09-customer-success status_check
```

Or use the Makefile:

```bash
make test
make install AGENT=09-customer-success
make run AGENT=09-customer-success TASK=daily_onboarding_sweep
```

---

## Repo Layout

```
lumin-agents/
├── shared/                    <- Shared Python library (all agents can import)
│   ├── secrets.py             <- Credential resolution (env var -> Secrets Manager)
│   ├── slack.py               <- Slack Block Kit alert helper
│   ├── dynamo.py              <- DynamoDB table helpers + float coercion
│   ├── approval.py            <- Human-in-the-loop approval queue
│   ├── context.py             <- Agent context enrichment utilities
│   ├── boid.py                <- BDI-O action audit log
│   └── logging_config.py      <- Structured JSON logging (CloudWatch / journalctl)
│
├── scripts/                   <- Runner and deployment tooling
│   ├── run_agent.py           <- Universal one-shot agent runner (the key script)
│   ├── bootstrap_aws.sh       <- One-time shared AWS infrastructure setup
│   ├── deploy_agent.sh        <- Per-agent deploy (venv, pip, tests, systemd)
│   └── new_agent.sh           <- Scaffold a new agent from the standard template
│
├── infra/systemd/             <- EC2 scheduling unit files
│   ├── lumin-agent@.service   <- Template service (all agents)
│   ├── lumin-agent@.timer     <- Template timer
│   ├── README.md              <- Installation guide for Ubuntu 24.04
│   └── example-timers/        <- Production-ready timer + service pairs
│
├── agents/                    <- One subdirectory per agent (Phase 2+)
│   ├── agent-01-resonance/
│   ├── agent-09-customer-success/
│   ├── agent-sbia-booking/
│   └── ...                    <- 13 agents total
│
├── tests/
│   └── shared/                <- pytest suite for the shared library (119 tests)
│
├── docs/
│   ├── PATTERNS.md            <- Fleet conventions reference (read this first)
│   ├── ROADMAP.md             <- Vision, 7-phase build plan, agent registry
│   └── EC2_VS_LAMBDA.md       <- Deployment posture decision document
│
├── audit/                     <- Audit logging helpers (Phase 3)
├── Makefile                   <- Common operation shortcuts
├── requirements.txt           <- Shared library runtime dependencies
├── .env.example               <- Fleet-wide credential template
└── conftest.py                <- pytest sys.path setup
```

---

## Adding a New Agent

The `new_agent.sh` script scaffolds a complete agent folder from the standard
template in under 5 seconds. The scaffold includes a stub `agent.py` with the
canonical BDI-O lambda handler pattern, a Python 3.12 venv target, 4 smoke
tests that pass without any AWS calls, and documentation stubs.

```bash
./scripts/new_agent.sh agent-14-my-new-feature
# OR
make new-agent AGENT=14-my-new-feature
```

After scaffolding: edit `agents/agent-14-my-new-feature/agent.py`, replace
the `# TODO:` stubs with the real system prompt and task functions, then:

```bash
make test-agent AGENT=14-my-new-feature
make run AGENT=14-my-new-feature TASK=status_check
make deploy AGENT=14-my-new-feature
```

See `infra/systemd/README.md` for how to schedule the new agent on EC2.

---

## Deploying to EC2

The agents run on EC2 as systemd-managed oneshot services, driven by
systemd timers. Each agent gets its own Python 3.12 virtual environment
under `agents/<name>/venv/`. The fleet-wide runner (`scripts/run_agent.py`)
handles all agents without modification -- it sets both `task` and
`trigger_type` event keys so it works with every dispatch pattern in the fleet.

For the full EC2 deployment guide -- including user setup, SSH config, venv
management, secrets rotation, and EC2 vs. Lambda tradeoffs -- see:

**[docs/EC2_VS_LAMBDA.md](docs/EC2_VS_LAMBDA.md)**

*(A detailed `docs/EC2_DEPLOYMENT.md` step-by-step guide will be added in Phase 4.)*

Quick deploy commands:

```bash
make bootstrap-aws                          # once per AWS account
make deploy AGENT=09-customer-success       # per agent
make install-systemd AGENT=09-customer-success
make status                                 # verify timers are scheduled
```

---

## Where the Patterns Live

**[docs/PATTERNS.md](docs/PATTERNS.md)** is the canonical reference for all
conventions in this codebase. Read it before touching any agent code. It covers:

- The exact agent file structure (imports, system prompt, factory, tasks, handler)
- Both lambda handler dispatch patterns (Pattern A: `task` key; Pattern B: `trigger_type` key for SBIA)
- All Slack webhook env var names, DynamoDB table names, and Secrets Manager paths
- Tool organization styles (separate files vs. inline)
- Agent 9's unique context-enriched factory pattern
- Cost optimization patterns (prompt caching, model tiering, Batch API)
- The Win3 principle and BDI-O cognitive architecture

---

## Where the Build Plan Lives

**[docs/ROADMAP.md](docs/ROADMAP.md)** contains the vision, the 7-phase build
plan, the deployment posture, and the full 13-agent registry with entity,
layer, schedule, and status columns.

Current status: **Phase 1 complete** -- shared library (119 tests passing),
universal runner, deploy scripts, systemd unit files, and this documentation.
Phase 2 begins the agent integration work: porting all 13 agent ZIPs into the
`agents/` directory.

---

*Lumin MAS -- April 2026*
*H.F. (CEO) · Eric (CTO) · ask.lumin.luxe*
*Win for the Artist · Win for the Fan · Win for the World*
