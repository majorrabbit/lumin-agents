# Lumin MAS — Integration Report (Phase 2.2)

**Date:** April 2026  
**Phase:** 2.2 — Runner smoke-tests, all 13 agents  
**Author:** Eric (CTO)

---

## Executive Summary

All 13 agents were smoke-tested by importing their `agent.py` modules under a
full mock harness and calling `lambda_handler()` with a safe representative
task.  **12 agents passed cleanly.  1 agent (Agent 09) is marked `xfail` due
to a SyntaxError in the vendored source ZIP.**  No agent file was modified —
all vendored bytes remain identical to the Phase 2.1 ingestion baseline.

---

## Test Results

| # | Agent | Folder | Task Tested | Result | Notes |
|---|-------|--------|-------------|--------|-------|
| 01 | Resonance Intelligence | `agent-01-resonance` | `hourly_data_collection` | **PASS** | |
| 02 | Sync Brief Hunter | `agent-02-sync-brief` | `brief_scan` | **PASS** | |
| 03 | Sync Pitch Campaign | `agent-03-sync-pitch` | `weekly_pitch_cycle` | **PASS** | module-level boto3 — see §4 |
| 04 | Anime & Gaming Scout | `agent-04-anime-gaming` | `daily_scout` | **PASS** | module-level boto3 — see §4 |
| 05 | Royalty Reconciliation | `agent-05-royalty` | `monthly_reconciliation` | **PASS** | module-level boto3 — see §4 |
| 06 | Cultural Moment Detection | `agent-06-cultural` | `30min_scan` | **PASS** | module-level boto3 — see §4 |
| 07 | Fan Behavior Intelligence | `agent-07-fan-behavior` | `daily_metrics_update` | **PASS** | |
| 08 | A&R Catalog Growth | `agent-08-ar-catalog` | `monthly_ar_review` | **PASS** | module-level boto3 — see §4 |
| 09 | Customer Success | `agent-09-customer-success` | `daily_onboarding_sweep` | **XFAIL** | SyntaxError — see §5 |
| 10 | CyberSecurity | `agent-10-cybersecurity` | `daily_guardduty_digest` | **PASS** | |
| 11 | Fan Discovery | `agent-11-fan-discovery` | `morning_discovery` | **PASS** | direct `anthropic` import — see §4 |
| 12 | Social Media | `agent-12-social-media` | `mention_monitor` | **PASS** | direct `anthropic` import — see §4 |
| SBIA | SkyBlew Booking Intelligence | `agent-sbia-booking` | `DISCOVERY_RUN` (dry_run=True) | **PASS** | `httpx` import — see §4 |

**Summary: 12 passed, 1 xfailed (expected), 0 errors, 0 unexpected failures.**

---

## Run Command

```bash
pytest tests/integration/ -v
```

Output (all 13 tests):

```
tests/integration/test_runner_per_agent.py::test_agent_01_resonance          PASSED
tests/integration/test_runner_per_agent.py::test_agent_02_sync_brief         PASSED
tests/integration/test_runner_per_agent.py::test_agent_03_sync_pitch         PASSED
tests/integration/test_runner_per_agent.py::test_agent_04_anime_gaming       PASSED
tests/integration/test_runner_per_agent.py::test_agent_05_royalty            PASSED
tests/integration/test_runner_per_agent.py::test_agent_06_cultural           PASSED
tests/integration/test_runner_per_agent.py::test_agent_07_fan_behavior       PASSED
tests/integration/test_runner_per_agent.py::test_agent_08_ar_catalog         PASSED
tests/integration/test_runner_per_agent.py::test_agent_09_customer_success   XFAIL
tests/integration/test_runner_per_agent.py::test_agent_10_cybersecurity      PASSED
tests/integration/test_runner_per_agent.py::test_agent_11_fan_discovery      PASSED
tests/integration/test_runner_per_agent.py::test_agent_12_social_media       PASSED
tests/integration/test_runner_per_agent.py::test_agent_sbia_booking          PASSED

12 passed, 1 xfailed in 0.34s
```

---

## Mock Harness Architecture

The test infrastructure lives in `tests/integration/conftest.py`.  It solves
two non-obvious problems that arise when importing agent modules in a test
environment.

### Problem 1 — module-level external calls

Every agent makes AWS calls at **module level** (not just inside functions).
Style B agents (03, 04, 05, 06, 08) call `boto3.resource("dynamodb", ...)` and
`boto3.client("ses", ...)` directly in `agent.py`.  Style A agents call them in
each `tools/*.py` file.  These calls execute when Python runs
`spec.loader.exec_module(mod)` during import.

**Solution:** All patches (`boto3.resource`, `boto3.client`, `requests.post`,
`requests.get`) are applied via a `pytest.fixture(autouse=True)` that is active
before each test function runs.  Each test imports its agent module *inside*
the test function body — after the fixture is live — so module-level calls see
the mocks.

### Problem 2 — strands not on sys.path

The `strands-agents` framework may not be installed in the test environment.
Agents import it at the top of every file (`from strands import Agent, tool`).
If strands is not installed, every agent import fails before any mock is applied.

**Solution:** At conftest **load time** (before any test collection), fake
`strands`, `strands.models`, and `strands.models.anthropic` modules are
injected into `sys.modules`.  The `@tool` decorator is replaced with an
identity function (`lambda fn: fn`) so decorated tool functions remain plain
callables.  `strands.Agent` and `strands.models.anthropic.AnthropicModel` are
`MagicMock` classes that return callable mock instances.

### Additional module mocks

Two further third-party libraries were discovered to be imported at module level
in specific tool files:

| Library | Tool file | Reason |
|---------|-----------|--------|
| `anthropic` | `agent-11-fan-discovery/tools/outreach_tools.py` | Direct haiku calls for outreach classification |
| `anthropic` | `agent-12-social-media/tools/voice_tools.py` | Direct haiku calls for voice-style matching |
| `httpx` | `agent-sbia-booking/tools/discovery_tools.py` | Async HTTP client for convention scraping |

These are mocked via `sys.modules.setdefault(...)` in the same conftest load
block.

---

## Known Defect — Agent 09 SyntaxError

**File:** `agents/agent-09-customer-success/tools/support_tools.py`  
**Line:** 557  
**Defect:** The `dynamodb.Table.query()` call passes `ExpressionAttributeValues`
as a keyword argument twice in the same call:

```python
resp = cs_metrics_t.query(
    KeyConditionExpression="pk BEGINS_WITH :pfx",
    ExpressionAttributeValues={":pfx": f"INT#"},      # first occurrence
    FilterExpression="#d = :today",
    ExpressionAttributeNames={"#d": "date"},
    ExpressionAttributeValues={":pfx": "INT#", ":today": today},  # duplicate
)
```

This is a **Python syntax error** (`SyntaxError: keyword argument repeated`).
Python 3.12+ raises it at compile time; the file cannot be imported at all.

**Impact:** Agent 09 (`agent-09-customer-success`) cannot be imported on Python
3.9+ without fixing this line.  The agent is non-functional in its current state.

**Resolution required:** Fix in the upstream source, rebuild the delivery ZIP,
and re-ingest per the Phase 2.1 ingestion procedure (hash update in
`audit/baseline-hashes.json`).

**Test status:** `test_agent_09_customer_success` is marked
`@pytest.mark.xfail(strict=True, raises=SyntaxError)`.  The suite reports
this as an **expected failure** — CI will alert if the agent unexpectedly
starts passing (meaning the fix was applied without a corresponding test update).

---

## Conventions Confirmed

These patterns were confirmed across the full fleet during Phase 2.2:

### 1. Dispatch key convention

- **12 agents** dispatch on `event["task"]` (Pattern A)
- **SBIA** dispatches on `event["trigger_type"]` (Pattern B)
- The runner script (`scripts/run_agent.py`) sets **both keys** to the same
  value, making it compatible with every agent fleet-wide

### 2. Error return convention

All agents return a dict with an `"error"` key on dispatch failure:
```python
return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
```
This is the contract the runner checks (`exit code 1` on `"error"` key present).

### 3. Module-level resource initialization

Every agent initializes AWS resources (DynamoDB tables, SES client, SNS client)
at **module level**, not inside `lambda_handler`.  This is intentional — it
amortizes connection setup across a Lambda container's lifetime.  The mock
harness must be active before `exec_module()` for tests to work correctly.

### 4. Tool decoration styles

- **Style A agents** (01, 02, 07, 09, 10, 11, 12, SBIA): `@tool` functions
  live in `tools/*.py` files; `agent.py` imports them
- **Style B agents** (03, 04, 05, 06, 08): `@tool` functions are defined
  inline in `agent.py`; `tools/__init__.py` is an empty package placeholder
- Both styles work identically under the mock harness

### 5. Agent factory pattern

All 13 agents follow the same factory pattern:
```python
def create_<name>_agent() -> Agent:
    return Agent(model=get_model(), system_prompt=SYSTEM_PROMPT, tools=[...])

def lambda_handler(event: dict, context) -> dict:
    agent = create_<name>_agent()
    task = event.get("task", "<default>")
    ...
```
The agent is created fresh on every invocation — no shared global state between
calls.

---

## Phase 3 Deployment Ordering Recommendation

Based on the smoke test results and the agent dependency graph (see
`agents/README.md` § Inter-Agent Signal Flows), the recommended Phase 3
integration order is:

**Priority 1 — No dependencies, low complexity:**
1. **Agent 01 Resonance** — standalone; feeds Agent 07. Deploy first to start
   building the Boltzmann/entropy signal history.
2. **Agent 10 CyberSecurity** — standalone; monitors all three entities.
   Deploy early so security coverage is live from day one.

**Priority 2 — Downstream of Priority 1:**
3. **Agent 07 Fan Behavior** — consumes Agent 01 entropy signals.  Deploy
   after Agent 01 has produced at least one daily update.
4. **Agent 06 Cultural Moment** — triggers Agents 02, 03, 11, 12.  Deploy
   before those agents to ensure the trigger chain is ready.

**Priority 3 — Revenue operations (independent of fan layer):**
5. **Agent 02 Sync Brief Hunter**
6. **Agent 04 Anime & Gaming Scout**
7. **Agent 05 Royalty Reconciliation** (monthly — deploy anytime)
8. **Agent 08 A&R Catalog Growth** (monthly — deploy anytime)
9. **SBIA Booking Intelligence** — independent of all other agents

**Priority 4 — Fan experience layer (after Agent 06 is live):**
10. **Agent 03 Sync Pitch Campaign** — triggered by Agent 06 cultural moments
11. **Agent 11 Fan Discovery** — triggered by Agent 06; consumes Agent 07 UTM data
12. **Agent 12 Social Media** — triggered by Agent 06; consumes Agent 07 affinity data

**Priority 5 — Requires upstream fix first:**
13. **Agent 09 Customer Success** — blocked by the `support_tools.py`
    SyntaxError.  Fix the duplicate keyword argument on line 557, re-ingest
    the corrected ZIP, then deploy.

---

## Integrity Check

Agent files were not modified during Phase 2.2.  Confirm with:

```bash
git diff --stat agents/
# Expected: empty (no output)
```

Baseline hashes remain valid: `audit/baseline-hashes.json`

---

*Phase 2.2 complete — April 2026*  
*12/13 agents smoke-test clean.  1 blocked on upstream SyntaxError (Agent 09).*
