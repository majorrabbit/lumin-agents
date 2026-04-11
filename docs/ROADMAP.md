# Lumin MAS — Roadmap & Vision

---

## Vision

The Lumin Multi-Agent System is the operational infrastructure of three
interdependent companies — Lumin Luxe Inc. (the technology and IP platform),
OPP Inc. (music publishing with one-stop sync clearance), and
2StepsAboveTheStars LLC (the independent hip-hop artist SkyBlew and his
catalog). Rather than deploying AI as a productivity tool, these companies
run AI as infrastructure: 13 specialized agents operating continuously, each
with a defined domain, clear escalation thresholds, and measurable success
criteria. H.F. (CEO) and Eric (CTO) oversee the fleet — the agents handle
the operational layer so H.F. and Eric can focus on the decisions that require
human judgment.

The system is governed by the **Win³ principle**: every agent action must win
for the artist, win for the fan, and win for the world simultaneously. No
optimization is acceptable if it compromises any of the three. This is not a
tagline — it is the decision framework agents use when there is no explicit
rule. The fleet is built on the BDI-O (Belief-Obligation-Intention-Desire)
cognitive architecture, extended from classical BDI to add Obligations as a
first-class reasoning primitive. Obligations are hard stops — rules that
cannot be overridden by any Desire or Intention, no matter how compelling the
goal.

---

## Build Plan — 7 Phases

### Phase 0 — Scaffold & Discovery *(current)*

**Goal:** Read all source material, understand every agent's conventions, and
establish the empty repository structure that subsequent phases will populate.

**Output:**
- Empty repo skeleton (`shared/`, `scripts/`, `infra/`, `agents/`, `audit/`, `docs/`, `tests/`)
- `docs/PATTERNS.md` — complete fleet conventions reference
- `docs/ROADMAP.md` — this document
- `.gitignore`, `README.md`
- Initial git commit: `Phase 0: empty scaffold`

**Effort:** 1 session (discovery + documentation)

---

### Phase 1 — Shared Library & EC2 Runner

**Goal:** Build the shared Python library and the runner script that can
invoke any agent's `lambda_handler` from EC2. No agent code is modified.

**Output:**
- `shared/secrets.py` — `get_api_key(env_var, sm_key=None)`
- `shared/slack.py` — `post_slack(webhook_url, message, timeout=5)`
- `shared/dynamo.py` — `get_table(env_var, default_name)`
- `shared/approval.py` — approval queue helpers
- `shared/context.py` — context window management
- `shared/boid.py` — BDI-O identity validation helpers
- `shared/logging_config.py` — structured JSON logging for Lambda/EC2
- `scripts/run_agent.py` — CLI runner: `python run_agent.py agent09 inbound_support --user_id=abc123 --message="help"`
- `infra/systemd/` — systemd service units for EC2 deployment
- `tests/shared/` — pytest suite for the shared library

**Effort:** 2-3 sessions

---

### Phase 2 — Agent Integration (13 Agents)

**Goal:** Port all 13 agents from ZIPs into the `agents/` directory.
Each agent gets its own subdirectory, venv, and `.env` (excluded from git).

**Output:**
- `agents/01-resonance/` through `agents/12-social-media/` + `agents/sbia-booking/`
- Each agent directory contains: `agent.py`, `tools/`, `requirements.txt`,
  `.env.example`, `tests/`, `docs/` (where provided in original ZIP)
- Each agent's tests passing (`pytest agents/0N-name/tests/ -v`)
- `agents/README.md` — index of all agents with status

**Effort:** 1-2 sessions per agent tier (agents sharing common infra batched together)

---

### Phase 3 — Audit Layer & Integration Tests

**Goal:** Add an audit trail across the fleet and build integration tests
that validate agent behavior against real AWS infrastructure (dev environment).

**Output:**
- `audit/` — structured audit logging for all agent actions
- Integration test suite (requires dev AWS credentials)
- Per-agent deployment checklists validated
- `docs/DEPLOY.md` — fleet-wide deployment guide

**Effort:** 2-3 sessions

---

### Phase 4 — Fleet Hardening

**Goal:** Address known gaps identified during Phase 0 discovery.

**Output:**
- Agent 10 real-time SLA validation (sub-60s critical alert path)
- Apple Music delivery gate automation (Agent 11 + 12)
- Context-enriched factory pattern extended to Agents 3, 11, 12 (optional)
- Rate limiting and retry logic standardized across all Slack/SES calls
- Cost monitoring dashboard

**Effort:** 2-3 sessions

---

### Phase 5 — CyberSecurity Sub-MAS

**Goal:** Implement Agent 10 as a full fleet of six specialized sub-agents
plus a coordinator, as specified in the architecture guide.

**Output:**
- Agent 10A through 10F (WAF, Session, Content, GuardDuty, Fraud, Compliance)
- Agent 10 Coordinator orchestrating the sub-fleet
- Sub-MAS communication protocol (internal blackboard via DynamoDB)

**Effort:** 3-4 sessions

---

### Phase 6 — Intelligence Network Activation

**Goal:** Activate the inter-agent data flows described in the architecture.
Agents begin sharing signals through the shared blackboard (DynamoDB + SNS).

**Output:**
- Agent 6 → Agents 2, 3, 11, 12 notification flow (cultural moment triggers)
- Agent 1 → Agent 7 entropy/temperature signal sharing
- Agent 7 → Agent 11 UTM conversion feed
- Agent 7 → Agent 12 genre affinity and geo cohort data
- Agent 9 → Lumin meta subscription data reporting
- Fleet health dashboard for H.F. and Eric

**Effort:** 2-3 sessions

---

## Deployment Posture

### EC2-first, Lambda-compatible

All 13 agents are deployed on EC2 as long-running processes driven by
EventBridge-triggered Lambda invocations. The `lambda_handler` function in
each agent serves dual duty:

1. **EC2 mode**: The runner script (`scripts/run_agent.py`) constructs an
   event dict and calls `lambda_handler(event, None)` directly in a Python
   subprocess. EventBridge triggers the runner script.

2. **Lambda mode**: The function is directly deployable to AWS Lambda.
   EventBridge invokes it as a standard Lambda function. This path requires
   no code changes.

This approach costs ~$3.50/month for Lambda compute (event-driven, no
idle cost) vs. $29.95/month for an always-on EC2 t3.medium. The fleet uses
both: EC2 for agents that need warm-start performance (Agent 10's <60s SLA)
and Lambda for agents that run infrequently (Agent 5 runs once/month).

### Per-agent virtual environments

Each agent in `agents/` has its own `venv/` (excluded from git). This
prevents dependency conflicts between agents that may pin different versions
of `strands-agents` or `boto3`. The runner script activates the correct venv
before invoking any agent.

---

## The 13-Agent Fleet

| # | Agent | Entity | Layer | Schedule | ADK Status |
|---|---|---|---|---|---|
| 01 | Resonance Intelligence | Lumin Luxe | Strategic Intelligence | Hourly / Daily / Weekly | Complete — ZIP delivered |
| 02 | Sync Brief Hunter | OPP Inc. | Revenue Operations | Every 4h / Daily | Complete — ZIP delivered |
| 03 | Sync Pitch Campaign | OPP Inc. | Revenue Operations | Weekly / Event-driven | Complete — ZIP delivered |
| 04 | Anime & Gaming Scout | OPP Inc. | Revenue Operations | Weekly / Monthly | Complete — ZIP delivered |
| 05 | Royalty Reconciliation | OPP Inc. | Revenue Operations | Monthly | Complete — ZIP delivered |
| 06 | Cultural Moment Detection | OPP Inc. / 2SATS | Fan Experience | Every 30 min | Complete — ZIP delivered |
| 07 | Fan Behavior Intelligence | 2SATS | Strategic Intelligence | Daily / Weekly / Monthly | Complete — ZIP delivered |
| 08 | A&R & Catalog Growth | OPP Inc. | Revenue Operations | Monthly | Complete — ZIP delivered |
| 09 | Customer Success (AskLumin) | Lumin Luxe | Fan Experience | Daily / Real-time | Complete — ZIP delivered |
| 10 | CyberSecurity | Lumin Luxe | Meta | Every 15m / Daily / Weekly | Complete — ZIP delivered |
| 11 | Fan Discovery & Outreach | 2SATS | Fan Experience | Weekly / Event-driven | Complete — ZIP delivered |
| 12 | Social Media Director | 2SATS | Fan Experience | Every 15m / Daily / Event-driven | Complete — ZIP delivered |
| SBIA | SkyBlew Booking Intelligence | 2SATS | Revenue Operations | Mon 09:00 ET / Daily / Every 4h | Complete — ZIP delivered |

**Layer key:**
- **Strategic Intelligence**: Generates market signals and predictive models
- **Revenue Operations**: Converts intelligence into placements, royalties, bookings
- **Fan Experience**: Faces the public — fans, communities, subscribers
- **Meta**: Fleet-wide infrastructure (security, orchestration)

**Entity key:**
- **Lumin Luxe Inc.**: Technology platform and IP holding company
- **OPP Inc.**: Music publishing, one-stop sync clearance
- **2SATS (2StepsAboveTheStars LLC)**: SkyBlew's artist company

---

*Lumin MAS Roadmap — April 2026*
*H.F. (CEO) · Eric (CTO) · ask.lumin.luxe*
*Win for the Artist · Win for the Fan · Win for the World*
