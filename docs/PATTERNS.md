# Lumin MAS — Fleet Patterns & Conventions

**Canonical reference for all Claude Code sessions working on `lumin-agents`.**

This document was assembled by reading all 13 agent ZIPs and all architectural
source material in `../source-material/`. Future sessions should read this first.
When the code disagrees with this document, trust the code.

---

## 1. Repo Philosophy

### One repo, shared library, 13 agents

```
lumin-agents/
├── shared/          ← shared Python library (Phase 1)
├── scripts/         ← runner scripts (Phase 1)
├── infra/systemd/   ← EC2 service units (Phase 1)
├── agents/          ← one subdirectory per agent (Phase 2+)
├── audit/           ← audit logging helpers (Phase 3)
├── docs/            ← PATTERNS.md, ROADMAP.md
└── tests/shared/    ← tests for the shared library
```

### Existing agent code is immutable

The 13 agent ZIPs are the authoritative source. We do not modify them.
The `shared/` library we build in Phase 1 is entirely **opt-in** — agents that
already exist keep working without touching a single line of their code.
New agents and future iterations may use the shared library; existing ones never
have to.

### EC2-first, Lambda-compatible

Every agent runs on EC2 via a runner script that invokes its `lambda_handler`.
Every `lambda_handler` is also directly invocable as an AWS Lambda function.
No agent requires always-on infrastructure — EventBridge triggers drive
the cadence. This keeps costs at ~$50/month for the whole fleet.

### Runtime framework: AWS Strands Agents

```
pip install strands-agents
```

Model: always `claude-sonnet-4-6`. Every agent imports:
```python
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel
```

No agent in the current fleet uses any other model for the primary agent.
Some agents invoke `claude-haiku-4-5-20251001` for classification subtasks
via separate tool calls, but the Strands Agent itself always runs Sonnet 4.6.

---

## 2. The Agent Shape

Every agent file follows this exact structure, in this order:

```
1. Module docstring with banner block
2. Imports (stdlib → strands → tools → boto3 → requests)
3. Module-level AWS resource initialization (DynamoDB tables, SES client, etc.)
4. SYSTEM_PROMPT constant
5. get_model() function
6. create_<name>_agent() factory function
7. Scheduled task handler functions  run_*(agent) ...
8. lambda_handler(event, context) function
9. if __name__ == "__main__": dev runner
```

### 2.1 Module docstring banner

Every agent opens with a Unicode box-drawing banner:

```python
"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT N: AGENT NAME ADK                      ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12 ║
║  Entity: <entity>                                                ║
║  Mission: <one-sentence mission>                                 ║
╚══════════════════════════════════════════════════════════════════╝
"""
```

### 2.2 Module-level AWS resource initialization

Agents that use DynamoDB declare their table handles at module load, not inside
functions. This is intentional — boto3 resources are reusable and the table name
is resolved once at startup.

```python
# Agent 3 pattern (typical)
import boto3, os

dynamo    = boto3.resource("dynamodb", region_name="us-east-1")
sups_t    = dynamo.Table(os.environ.get("SUPERVISORS_TABLE", "sync-supervisors"))
pitches_t = dynamo.Table(os.environ.get("PITCHES_TABLE",     "sync-pitches"))
ses       = boto3.client("ses", region_name="us-east-1")
SLACK_PITCH_WEBHOOK = os.environ.get("SLACK_PITCH_WEBHOOK", "")
```

Agents that organize tools in separate files (1, 2, 7, 9, 10, 11, 12, SBIA)
declare their boto3 resources inside the tool files, not in agent.py.

### 2.3 SYSTEM_PROMPT

A module-level string constant. Always named `SYSTEM_PROMPT`. The longest and
most important part of every agent — encodes the agent's BDI-O identity,
decision authority, escalation rules, tool usage guidance, and output standards.

Agent 9 is unique: its `SYSTEM_PROMPT` contains a `{user_context}` placeholder
that is filled in at agent-creation time by the factory function.

### 2.4 Canonical get_model()

**Most agents** (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):

```python
def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )
```

**SBIA** (canonical pattern — env var first, Secrets Manager fallback):

```python
def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            secrets = boto3.client("secretsmanager", region_name="us-east-1")
            api_key = secrets.get_secret_value(
                SecretId="lumin/anthropic-api-key"
            )["SecretString"]
        except Exception:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set and not found in Secrets Manager. "
                "Set env var or store at: lumin/anthropic-api-key"
            )
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )
```

The SBIA pattern is the **recommended pattern** for any new agent. The shared
library will provide a helper that implements this logic once and re-exports it.

**Note on max_tokens:** Agent 9 uses `max_tokens=2048` (conversational replies
are shorter). All others use `max_tokens=4096`.

### 2.5 Agent factory: create_<name>_agent()

The factory creates the Strands `Agent` with model + system prompt + tool list.
No other logic belongs here — except Agent 9's context enrichment (see §6).

```python
# Standard factory (Agents 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, SBIA)
def create_resonance_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            tool_function_one,
            tool_function_two,
            # ...
        ],
    )
```

### 2.6 Scheduled task handlers: run_*(agent)

Each agent has 2-5 handler functions that accept an `Agent` and return a `dict`.
They always have this shape:

```python
def run_hourly_data_collection(agent: Agent) -> dict:
    """Every hour — pull fresh data from all streaming APIs."""
    result = agent(
        "Run the hourly data collection cycle. ..."
    )
    return {"task": "hourly_data_collection", "result": str(result)}
```

The dict always includes `"task"` as a string key and `"result"` as a string.
Some handlers include additional keys (e.g., `"dry_run"`, `"convention_id"`).

**Exception — Agent 9's `handle_inbound_support`**: This function takes
`user_id`, `message`, and `session_id` directly (not an `agent` parameter).
It creates its own agent internally using `create_cs_agent(user_id=user_id)`.

### 2.7 lambda_handler(event, context)

The Lambda entry point. Follows one of two dispatch patterns (see §7).

### 2.8 Local dev runner

Every agent ends with:

```python
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Interactive REPL with shortcut commands
    agent = create_<name>_agent()
    while True:
        ui = input("<AgentName> > ").strip()
        ...
        print(f"\nAgent: {agent(ui)}\n")
```

Shortcut commands map single words (`"entropy"`, `"backtest"`, `"signals"`)
to full natural-language prompts.

---

## 3. Credential Conventions

### Rule: env var first, Secrets Manager as optional fallback

All agents read `ANTHROPIC_API_KEY` from the environment. Local dev uses
`.env` + `python-dotenv`. Production Lambda uses environment variables set
in the Lambda console (or injected by EC2 IAM role + the runner script).

Secrets Manager is used for third-party API credentials that rotate
(Chartmetric, Spotify OAuth, etc.) but is **optional** for the Anthropic key
itself. The SBIA pattern is the canonical example of graceful fallback.

### Secrets Manager key namespace

```
lumin/anthropic-api-key       ← shared across fleet
lumin/chartmetric-api-key
lumin/spotify-oauth-token
lumin/apple-music-token
lumin/youtube-api-key
lumin/soundcharts-api-key
lumin/slack-webhook-resonance  ← per-agent Slack secrets
sbia/web-search-api-key        ← Tavily or Brave Search API key (operator's choice)
sbia/ses-sending-identity      ← Verified SES sender address (spec §3.5; not in code env vars)
sbia/sns-alert-topic-arn       ← SNS topic ARN for H.F. hot-lead alerts
sbia/slack-webhook-url         ← Optional Slack notifications (no dedicated env var)
sbia/epk-s3-bucket             ← S3 bucket name for EPK assets (code also reads SBIA_EPK_BUCKET env var)
sbia/dynamodb-conventions      ← Conventions table name (spec §3.5; code uses SBIA_CONVENTIONS_TABLE env var)
sbia/dynamodb-outreach-log     ← Outreach log table name (spec §3.5; code uses SBIA_OUTREACH_LOG_TABLE env var)
skyblew/voice-book             ← Agent 12: Voice Book stored in SM
```

**Note:** For `sbia/ses-sending-identity`, `sbia/dynamodb-conventions`, and
`sbia/dynamodb-outreach-log`, the engineering spec lists them as SM keys but
the code does NOT call `_get_secret()` for them — it reads the env vars
(`SBIA_FROM_EMAIL`, `SBIA_CONVENTIONS_TABLE`, `SBIA_OUTREACH_LOG_TABLE`) directly.
The env var approach is correct per fleet conventions. The SM keys in the spec
are aspirational "you could rotate these" items, not runtime requirements.

### What the shared library will provide

```python
# shared/secrets.py (Phase 1)
def get_api_key(env_var: str, sm_key: str | None = None) -> str:
    """Env var first, Secrets Manager fallback, clear error if both missing."""
```

---

## 4. Slack Webhook Conventions

### Rule: per-agent env var, direct requests.post(), timeout=5

Every agent has its own `SLACK_*_WEBHOOK` environment variable. There is no
shared Slack client. Pattern:

```python
SLACK_WEBHOOK = os.environ.get("SLACK_<AGENT>_WEBHOOK", "")

def post_to_slack(msg: dict) -> bool:
    if not SLACK_WEBHOOK:
        return False
    resp = requests.post(SLACK_WEBHOOK, json=msg, timeout=5)
    return resp.status_code == 200
```

### Complete webhook env var registry (all 13 agents)

| Agent | Env Var |
|-------|---------|
| 01 Resonance | `SLACK_RESONANCE_WEBHOOK` |
| 02 Sync Brief | `SLACK_SYNC_WEBHOOK` |
| 03 Sync Pitch | `SLACK_PITCH_WEBHOOK` |
| 04 Anime & Gaming | `SLACK_AG_WEBHOOK` |
| 05 Royalty | `SLACK_ROYALTY_WEBHOOK` |
| 06 Cultural Moment | `SLACK_CULTURAL_WEBHOOK` |
| 07 Fan Behavior | `SLACK_FAN_WEBHOOK` |
| 08 A&R Catalog | `SLACK_AR_WEBHOOK` |
| 09 Customer Success | `SLACK_CS_WEBHOOK` |
| 10 CyberSecurity | `SLACK_SECURITY_WEBHOOK` |
| 11 Fan Discovery | `SLACK_DISCOVERY_WEBHOOK` |
| 12 Social Media | `SLACK_APPROVAL_WEBHOOK`, `SLACK_SOCIAL_WEBHOOK` |
| SBIA Booking | *(stored in SM: `sbia/slack-webhook-url`, no dedicated env var)* |

Agent 12 has **two** webhook env vars: approval queue notifications go to
`SLACK_APPROVAL_WEBHOOK`; social intelligence alerts go to `SLACK_SOCIAL_WEBHOOK`.

Agent 1 also uses SNS for high-confidence alerts (`SNS_RESONANCE_TOPIC`) in
addition to Slack. Agent 9 uses `SNS_ESCALATION_TOPIC` for CS escalations.
Agent 10 has `SNS_SECURITY_TOPIC` (standard) and `SNS_CRITICAL_TOPIC`
(pages Eric within 60 seconds).

### What the shared library will provide

```python
# shared/slack.py (Phase 1)
def post_slack(webhook_url: str, message: dict, timeout: int = 5) -> bool:
    """Send a Slack message. Returns True on 200, False if URL empty."""
```

---

## 5. DynamoDB Table Conventions

### Rule: module-level Table handle, env var override, reasonable default name

```python
# Pattern used in agents with inline tools (3, 4, 5, 6, 8)
dynamo    = boto3.resource("dynamodb", region_name="us-east-1")
my_table  = dynamo.Table(os.environ.get("MY_TABLE", "my-default-name"))
```

Agents with tool files (1, 2, 7, 9, 10, 11, 12, SBIA) declare their Table
handles inside the relevant tool file, not in agent.py.

### Complete DynamoDB env var registry

**Agent 01 — Resonance Intelligence**
| Env Var | Default Table Name |
|---|---|
| `MODEL_TABLE` | `resonance-model-params` |
| `SIGNALS_TABLE` | `resonance-trend-signals` |
| `BACKTEST_TABLE` | `resonance-backtest-log` |
| `PREDICT_TABLE` | `resonance-predictions` |

**Agent 02 — Sync Brief Hunter**
| Env Var | Default Table Name |
|---|---|
| `BRIEFS_TABLE` | `sync-briefs` |
| `CATALOG_TABLE` | `opp-catalog` |
| `SUBS_TABLE` | `sync-submissions` |

**Agent 03 — Sync Pitch Campaign**
| Env Var | Default Table Name |
|---|---|
| `SUPERVISORS_TABLE` | `sync-supervisors` |
| `PITCHES_TABLE` | `sync-pitches` |

**Agent 04 — Anime & Gaming Scout**
| Env Var | Default Table Name |
|---|---|
| `SCOUT_TABLE` | `anime-gaming-opportunities` |
| `AG_PITCHES_TABLE` | `anime-gaming-pitches` |

**Agent 05 — Royalty Reconciliation**
| Env Var | Default Table Name |
|---|---|
| `ROYALTY_TABLE` | `opp-royalty-statements` |
| `ISSUES_TABLE` | `opp-royalty-issues` |

**Agent 06 — Cultural Moment Detection**
| Env Var | Default Table Name |
|---|---|
| `MOMENTS_TABLE` | `cultural-moments` |
| `ENTROPY_TABLE` | `cultural-entropy-log` |

**Agent 07 — Fan Behavior Intelligence**
| Env Var | Default Table Name |
|---|---|
| `FES_TABLE` | `fan-behavior-metrics` |
| `CLV_TABLE` | `fan-clv-model` |
| `GEO_TABLE` | `fan-geographic-index` |
| `AFFI_TABLE` | `fan-genre-affinity` |
| `APP_CONFIG_TABLE` | `skyblew-app-config` |

**Agent 08 — A&R & Catalog Growth**
| Env Var | Default Table Name |
|---|---|
| `CATALOG_TABLE` | `opp-catalog` |
| `GAPS_TABLE` | `opp-catalog-gaps` |
| `TARGETS_TABLE` | `opp-ar-targets` |

**Agent 09 — Customer Success**
| Env Var | Default Table Name |
|---|---|
| `SESSIONS_TABLE` | `ask-lumin-sessions` |
| `CS_TICKETS_TABLE` | `ask-lumin-cs-tickets` |
| `CS_METRICS_TABLE` | `ask-lumin-cs-metrics` |
| `ONBOARDING_TABLE` | `ask-lumin-onboarding` |
| `NPS_TABLE` | `ask-lumin-nps` |

**Agent 10 — CyberSecurity**
| Env Var | Default Table Name |
|---|---|
| `SESSIONS_TABLE` | `skyblew-sessions` |
| `ASSET_HASHES_TABLE` | `security-asset-hashes` |
| `SECURITY_EVENTS_TABLE` | `security-events` |
| `SECURITY_ALERTS_TABLE` | `security-alerts` |
| `FRAUD_REPORTS_TABLE` | `security-fraud-reports` |

**Agent 11 — Fan Discovery & Outreach**
| Env Var | Default Table Name |
|---|---|
| `OUTREACH_QUEUE_TABLE` | `fan-discovery-outreach-queue` |
| `COMMUNITIES_TABLE` | `fan-discovery-communities` |
| `ENTRY_POINTS_TABLE` | `fan-discovery-entry-points` |
| `CONVERSIONS_TABLE` | `fan-discovery-conversions` |

**Agent 12 — Social Media Director**
| Env Var | Default Table Name |
|---|---|
| `CALENDAR_TABLE` | `skyblew-content-calendar` |
| `QUEUE_TABLE` | `skyblew-approval-queue` |
| `PERF_TABLE` | `skyblew-post-performance` |
| `MENTIONS_TABLE` | `skyblew-fan-interactions` |
| `ANALYTICS_TABLE` | `skyblew-analytics` |
| `CAMPAIGN_TABLE` | `skyblew-fm-am-campaign` |
| `VOICE_TABLE` | `skyblew-voice-log` |

**SBIA — SkyBlew Booking Intelligence**
| Env Var | Default Table Name |
|---|---|
| `SBIA_CONVENTIONS_TABLE` | `sbia_conventions` |
| `SBIA_OUTREACH_LOG_TABLE` | `sbia_outreach_log` |

**SBIA DynamoDB schema note — variant convention:**
Most fleet agents use generic `pk`/`sk` key names. SBIA uses a domain-specific
schema with `convention_id` (UUID) as PK and `discovery_date` as SK on
`sbia_conventions`, and `outreach_id` (UUID) as PK with `convention_id` as SK
on `sbia_outreach_log`. This is intentional — the spec treats `sbia_conventions`
as a pipeline CRM, not a generic audit log, and the domain-specific naming makes
console queries more readable. Both are valid DynamoDB patterns.

Note: Agents 2 and 8 share the `opp-catalog` table name (`CATALOG_TABLE`).
This is intentional — they operate on the same OPP catalog.

---

## 6. Approval Queue Conventions

### Rule: per-agent table, never shared

Each agent that requires human approval has its own isolated queue/approval
table. There is no fleet-wide approval queue. Approvals are surfaced to H.F.
via Slack notifications from each agent independently.

| Agent | Queue Table | Mechanism |
|---|---|---|
| 09 Customer Success | `ask-lumin-cs-tickets` | Agent creates ticket record; escalation sent to `SNS_ESCALATION_TOPIC` → Slack |
| 11 Fan Discovery | `fan-discovery-outreach-queue` | All outreach drafts go into queue; H.F. approves via Slack reaction |
| 12 Social Media | `skyblew-approval-queue` | All significant posts queued; H.F. reviews via `SLACK_APPROVAL_WEBHOOK` before any post goes live |

Agent 3 (Sync Pitch) also has a de-facto approval queue — it drafts emails
and presents them for H.F. review before sending — but uses `sync-pitches`
as the record store rather than a dedicated "approval queue" table name.

SBIA's approval workflow: outreach emails are sent directly (within rate limits)
but H.F. is alerted immediately for any HOT or WARM response via `send_alert_to_hf`.

---

## 7. Lambda Handler Dispatch

### Two dispatch patterns in the fleet

**Pattern A — `task` key (12 of 13 agents):**

```python
def lambda_handler(event: dict, context) -> dict:
    agent  = create_resonance_agent()
    task   = event.get("task", "hourly_data_collection")

    dispatch = {
        "hourly_data_collection": lambda: run_hourly_data_collection(agent),
        "daily_physics_update":   lambda: run_daily_physics_update(agent),
        "weekly_backtest":        lambda: run_weekly_backtest(agent),
        "trend_alert_check":      lambda: run_trend_alert_check(agent),
    }

    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()
```

EventBridge payload: `{"task": "daily_physics_update"}`

**Pattern B — `trigger_type` key (SBIA only):**

```python
def lambda_handler(event: dict, context) -> dict:
    agent = create_sbia_agent()
    task  = event.get("trigger_type", "DISCOVERY_RUN")
    p     = event

    dispatch = {
        "DISCOVERY_RUN":     lambda: run_discovery(agent, dry_run=p.get("dry_run", False)),
        "PIPELINE_REPORT":   lambda: run_weekly_pipeline_report(agent),
        "FOLLOWUP_DISPATCH": lambda: run_followup_dispatch(
                                 agent,
                                 convention_id=p.get("convention_id"),
                                 followup_type=p.get("followup_type"),
                             ),
        "INBOX_MONITOR":     lambda: run_inbox_monitor(agent),
    }
    handler = dispatch.get(task)
    if not handler:
        return {"statusCode": 400, "error": f"Unknown trigger_type: {task}",
                "available": list(dispatch.keys())}
    return {"statusCode": 200, "trigger_type": task, **handler()}
```

EventBridge payload: `{"trigger_type": "FOLLOWUP_DISPATCH", "convention_id": "...", "followup_type": "FOLLOWUP_1"}`

### What the runner (Phase 1) must handle

The EC2 runner script must support **both** dispatch keys. When invoking an
agent, the runner constructs the event dict as the agent expects it.

The runner should also support passing arbitrary kwargs to a task — because
Agent 9's `handle_inbound_support` takes `user_id`, `message`, `session_id`
and SBIA's `run_followup_dispatch` optionally takes `convention_id` and
`followup_type`. The runner cannot assume every task takes only a name.

---

## 8. Tool Organization Styles

Three valid styles exist in the fleet. The shared library must not impose a
fourth. All three work identically at runtime — Strands doesn't care where
the `@tool` function lives, only that it is registered in the `Agent(tools=[])` list.

### Style A — Multiple tool files (Agents 1, 2, 7, 10, 11, 12, SBIA)

Tools are organized into thematic files under `tools/`. Each file contains
multiple `@tool`-decorated functions. `tools/__init__.py` is present but
may be empty — imports happen directly in `agent.py`.

```
agent-01-resonance/tools/
    __init__.py           ← empty
    data_tools.py         ← pull_chartmetric_streaming_data, etc.
    physics_tools.py      ← compute_boltzmann_distribution, etc.
    trend_tools.py        ← detect_phase_transitions, etc.
    backtest_tools.py     ← run_walk_forward_backtest, etc.
    report_tools_resonance.py  ← generate_weekly_resonance_digest, etc.
```

Import pattern in agent.py:
```python
from tools.data_tools import pull_chartmetric_streaming_data, pull_spotify_audio_features
from tools.physics_tools import compute_boltzmann_distribution, compute_shannon_entropy
```

### Style B — All tools inline in agent.py (Agents 3, 4, 5, 6, 8)

`@tool` decorated functions live directly in `agent.py`. The `tools/` directory
exists with only an empty `__init__.py` (git placeholder).

```python
# Inside agent.py
from strands import Agent, tool

@tool
def get_supervisor_database(tier_filter: int = None) -> str:
    """Return the supervisor contact database..."""
    ...

@tool
def get_supervisor_placement_history(supervisor_id: str) -> str:
    """Retrieve pitch history with a specific supervisor..."""
    ...
```

### Style C — Thin shim files re-exporting from consolidated file (Agent 9)

`tools/support_tools.py` is the main implementation file with all tool logic.
`tools/onboarding_tools.py`, `tools/retention_tools.py`, and
`tools/metrics_tools.py` are thin shims that import and re-export from
`support_tools.py` for organizational clarity.

```
agent-09-customer-success/tools/
    __init__.py
    context_tools.py       ← standalone context enrichment tools
    support_tools.py       ← main implementation file (all core tools)
    onboarding_tools.py    ← re-exports onboarding functions from support_tools
    retention_tools.py     ← re-exports retention functions from support_tools
    metrics_tools.py       ← re-exports metrics functions from support_tools
```

This style is appropriate when a single agent has a large number of tools
that fall into natural thematic groups but share underlying DynamoDB resources.

---

## 9. Tasks Taking Arguments (Runtime Kwargs)

### The standard case

Most task handlers take only one argument: the pre-created `agent` object.
The runner can call them with no additional parameters:

```python
dispatch = {
    "daily_physics_update": lambda: run_daily_physics_update(agent),
}
```

### Exceptions — tasks that take additional runtime arguments

**Agent 9 — `handle_inbound_support`**

```python
def handle_inbound_support(user_id: str, message: str, session_id: str) -> dict:
    """Real-time handler for inbound support conversations."""
    agent = create_cs_agent(user_id=user_id)  # creates its own agent!
    result = agent(f"A subscriber has sent you: '{message}'...")
    return {"task": "inbound_support", "user_id": user_id, "result": str(result)}
```

This handler does NOT accept an agent parameter. It creates its own
context-enriched agent. Lambda event format:
```json
{
  "task": "inbound_support",
  "user_id": "user_abc123",
  "message": "How do I use the Sync Brief Scanner?",
  "session_id": "sess_xyz789"
}
```

**SBIA — `run_followup_dispatch`**

```python
def run_followup_dispatch(agent: Agent, convention_id: str = None,
                           followup_type: str = None) -> dict:
```

Both kwargs are optional. When provided, the function targets a specific
convention instead of doing a fleet-wide sweep. Lambda event format:
```json
{
  "trigger_type": "FOLLOWUP_DISPATCH",
  "convention_id": "conv-12345",
  "followup_type": "FOLLOWUP_1"
}
```

**SBIA — `run_discovery`**

```python
def run_discovery(agent: Agent, dry_run: bool = False) -> dict:
```

Lambda event format: `{"trigger_type": "DISCOVERY_RUN", "dry_run": true}`

### Runner requirement

The EC2 runner script (Phase 1) must support passing arbitrary kwargs from
the event payload to the task handler. It cannot assume all tasks take only
a name. Implementation approach: parse the event, extract the task key,
pass remaining event keys as kwargs to the dispatch lambda.

---

## 10. Agent 9's Context-Enriched Factory (Unique Pattern)

Agent 9's `create_cs_agent()` is the only factory in the fleet that accepts
a parameter:

```python
def create_cs_agent(user_id: str = None) -> Agent:
    """Create a CS Agent pre-enriched with a specific user's context."""
    if user_id:
        ctx_raw = enrich_user_context(user_id=user_id)
        ctx = json.loads(ctx_raw)
        user_context_block = (
            f"Tier: {ctx.get('tier', 'Unknown')}\n"
            f"Account age: {ctx.get('account_age_days', '?')} days\n"
            f"Last active: {ctx.get('last_active', 'Unknown')}\n"
            f"Features activated: {', '.join(ctx.get('features_used', ['None yet']))}\n"
            f"Features NOT yet activated: {', '.join(ctx.get('features_not_used', []))}\n"
            f"Usage trend: {ctx.get('usage_trend', 'NEW')}\n"
            f"Open tickets: {ctx.get('open_tickets', 0)}\n"
            f"Churn risk: {ctx.get('churn_risk', 'LOW')}"
        )
    else:
        user_context_block = "No specific user context — operating in batch mode."

    enriched_prompt = SYSTEM_PROMPT.replace("{user_context}", user_context_block)

    return Agent(
        model=get_model(),
        system_prompt=enriched_prompt,
        tools=[...],
    )
```

The `{user_context}` placeholder in `SYSTEM_PROMPT` is the only case in the
fleet where a system prompt is dynamic. This pattern could benefit Agents 3,
11, and 12 if standardized — Agent 3 could inject the target supervisor's
profile; Agent 11 could inject the target community's characteristics;
Agent 12 could inject the current cultural moment context. This is noted as
a Phase 3 enhancement, not a Phase 1 requirement.

For batch operations (scheduled tasks), `create_cs_agent()` is called with
no arguments: `agent = create_cs_agent()`. For real-time support, it is
called with a user_id: `agent = create_cs_agent(user_id=user_id)`.

---

## 11. SBIA-Specific Patterns (Variant Conventions)

SBIA has the most complete engineering specification in the fleet.  Several
of its design choices differ from the other 12 agents and must be treated as
**intentional variants**, not deviations.

### 11.1 Three-Lambda architecture (unified handler in EC2 mode)

The spec describes three separate Lambda functions:

| Lambda | EventBridge Trigger | Payload |
|--------|---------------------|---------|
| `sbia-main` | Every Monday 9:00 AM ET | `{"trigger_type": "DISCOVERY_RUN"}` |
| `sbia-followup-dispatcher` | Every day 10:00 AM ET | `{"trigger_type": "FOLLOWUP_DISPATCH"}` |
| `sbia-response-monitor` | Every 4 hours | `{"trigger_type": "INBOX_MONITOR"}` |

In the code, all three are unified into a single `lambda_handler` that routes
on `trigger_type`.  On EC2, the runner calls the unified handler with the
appropriate payload.  On Lambda, the same handler can be deployed as either
one function receiving three different EventBridge payloads OR three separate
functions each pointing to `agent.lambda_handler` — both work identically.

### 11.2 Rate limiting — tool-enforced, not agent-enforced

SBIA enforces strict email rate limits at the `send_booking_email` tool level:

| Limit | Value | Mechanism |
|-------|-------|-----------|
| Max emails/day | 50 | DynamoDB counter + TTL reset at midnight |
| Max emails/hour | 5 | DynamoDB counter + 1h TTL |
| Min days between touches | 7 | Checked before every send |
| Max follow-ups per contact | 2 | Enforced by pipeline state machine |
| DECLINED re-contact cooldown | 365 days | Status check before any outreach |
| GHOSTED re-contact cooldown | 180 days | Status check before any outreach |

These constants are defined in `tools/outreach_tools.py`:
```python
MAX_EMAILS_PER_DAY  = 50
MAX_EMAILS_PER_HOUR = 5
```

### 11.3 dry_run safety protocol

`DISCOVERY_RUN` accepts `{"trigger_type": "DISCOVERY_RUN", "dry_run": true}`.
When `dry_run=True`, the agent discovers and scores conventions but **skips
`send_booking_email()`**.  The pipeline prompt explicitly says:

```
"6. SKIP send_booking_email() — DRY RUN."
```

**Operational rule**: `dry_run=True` should be the default for at least the
first two weeks of production operation.  SBIA sends emails to real booking
contacts on behalf of SkyBlew.  A poorly timed or poorly composed email
damages a real booking relationship.  Validate output in dry_run mode before
enabling live sends.

### 11.4 S3 EPK bucket layout

SBIA requires EPK assets pre-loaded in S3 before going live.  The bucket name
defaults to `sbia-epk-assets` (overridable via `SBIA_EPK_BUCKET` env var or
`sbia/epk-s3-bucket` in Secrets Manager).  Required layout:

```
sbia-epk-assets/
├── epk/
│   ├── skyblew-epk-full.pdf          ← 4–6 page full EPK
│   ├── skyblew-epk-one-pager.pdf     ← 1-page summary for cold outreach
│   ├── skyblew-press-photo-1.jpg     ← 300 DPI, min 3000×3000 px (performance shot)
│   ├── skyblew-press-photo-2.jpg     ← 300 DPI, min 3000×3000 px (promo/portrait)
│   ├── skyblew-rider.pdf             ← Technical/hospitality rider
│   └── skyblew-setlist-sample.pdf    ← 45-min and 60-min set options
└── templates/
    ├── email-initial-anime.txt
    ├── email-initial-gaming.txt
    ├── email-initial-general.txt
    ├── email-followup-1.txt
    └── email-followup-2.txt
```

**If the EPK bucket is empty or missing assets, every outbound email will
contain a broken EPK link.**  Populate S3 before enabling live sends.

### 11.5 Seed convention database

The spec includes a pre-loaded Tier A / B / C convention target list (§8 of
the engineering spec).  This list is NOT embedded in the code — it must be
loaded into `sbia_conventions` as seed records at deploy time.

| Tier | Count | Examples |
|------|-------|---------|
| A — Anime/Gaming (highest fit) | 12 | Anime Expo, MomoCon, Super MAGFest, PAX East/West |
| B — Adjacent (strong opportunities) | 7 | Dragon Con, Comic-Con International, C2E2 |
| C — Exploratory | 3+ | Christian music festivals, NACA/APCA college booking |

Without the seed list, SBIA starts from zero on first run.  The agent
will discover conventions through web search, but pre-seeding the Tier A list
accelerates the pipeline significantly.

### 11.6 CAN-SPAM compliance

Every outgoing email must include a CAN-SPAM compliant unsubscribe note.
This is enforced via the system prompt decision rule:
```
8. All emails include CAN-SPAM compliant unsubscribe note
```
The `compose_booking_inquiry` tool is responsible for generating this content.
There is no dedicated opt-out list management in the current codebase — this
is a known gap for v2.0.

### 11.7 Web search API — Tavily or Brave (operator's choice)

SBIA uses one of two search APIs for convention discovery:
- **Tavily API** — recommended; purpose-built for AI agents
- **Brave Search API** — alternative; broader web coverage

The secret `sbia/web-search-api-key` holds whichever key the operator
provisions.  The code reads this key at runtime and passes it to `httpx`
HTTP calls in `discovery_tools.py`.  The engineering spec leaves the choice
to the operator; the code is API-agnostic at the key-lookup level.

### 11.8 Direct anthropic call in classify_response_sentiment

`classify_response_sentiment` (crm_tools.py) makes a **direct** `anthropic.Anthropic`
API call using `claude-sonnet-4-6` — it does not use the Strands Agent framework.
This is intentional: the classification needs a short, structured JSON response
(≤400 tokens) that is more efficiently handled via the raw messages API than
through the full Strands agent loop.

Compared to the fleet pattern, this could be `claude-haiku-4-5-20251001`
(3× cheaper) without loss of classification quality.  The current code uses
Sonnet — consistent with the engineering spec ("Uses Claude Sonnet to classify")
but not consistent with the fleet-wide haiku-for-classification cost optimization.
Changing to haiku is a future cost optimization opportunity, not a P3.x blocker.

---

## 12. Testing Conventions

### Framework: pytest with unittest.mock

Every agent has `tests/test_agent.py`. The testing approach:

```python
import pytest
from unittest.mock import patch, MagicMock
```

### Rule: mock boto3 resources at module level

AWS resources (DynamoDB tables, SES, SNS) are mocked using `patch()` on the
module-level objects, not via dependency injection. This is the pattern:

```python
def test_something():
    with patch("tools.physics_tools.model_t") as mock_table:
        mock_table.put_item.return_value = {}
        # Now import and call the tool function
        from tools.physics_tools import compute_attention_temperature
        result = compute_attention_temperature()
        assert result is not None
```

The key insight: mock the module-level boto3 resource (`tools.physics_tools.model_t`)
before importing the function, so the function sees the mock when it runs.

### Rule: import tool functions inside test methods

When the tool function under test uses a module-level boto3 resource,
import the function inside the test (or inside a `with patch(...)` block)
to ensure the mock is in place before the module initializes.

### What gets tested

Agent 1 exemplifies the standard test structure:
- **Physics unit tests**: pure math validation (Boltzmann normalization, entropy max/zero cases, variance edge cases)
- **Tool tests**: each `@tool` function tested in isolation with mocked AWS
- **Lambda handler tests**: routing tests verifying all task keys dispatch correctly
- **Agent creation tests**: verify `create_<name>_agent()` succeeds with env vars set

### No real AWS calls in unit tests

Never invoke real DynamoDB, SES, SNS, or Secrets Manager in unit tests.
Integration tests (Phase 3) will handle real-resource validation.

---

## 13. Scheduled Task Cadence

| Agent | Schedule | Tasks |
|---|---|---|
| 01 Resonance | Hourly / Daily 02:00 UTC / Sundays 04:00 UTC / Every 4h | data collection, physics update, backtest, alert check |
| 02 Sync Brief | Every 4h (platform scan) / Daily (catalog match) / Weekly | scan briefs, match catalog, weekly summary |
| 03 Sync Pitch | Weekly (Monday) / Event-driven (Agent 6 trigger) | pitch cycle, cultural-moment pitch |
| 04 Anime Gaming | Weekly / Monthly | convention scan, monthly summary |
| 05 Royalty | Monthly | statement reconciliation |
| 06 Cultural Moment | Every 30 minutes | moment detection, fleet notification |
| 07 Fan Behavior | Daily 06:00 UTC / Weekly Sunday 05:00 UTC / Monthly 1st | FES update, CLV/churn, strategic report |
| 08 A&R Catalog | Monthly | catalog gap review |
| 09 Customer Success | Daily 08:00 UTC / Daily 09:00 UTC / Mondays 09:00 UTC / Monthly 1st / Real-time | onboarding, churn scan, CS digest, metrics, support |
| 10 CyberSecurity | Every 15m (WAF/session) / Daily (content integrity) / Weekly (fraud) | security monitoring |
| 11 Fan Discovery | Weekly / Event-driven (Agent 6 trigger) | community scan, cultural moment outreach |
| 12 Social Media | Every 15m (mentions) / Daily / Event-driven (Agent 6) | mention monitor, content scheduling, moment deployment |
| SBIA Booking | Mondays 09:00 ET / Daily 10:00 ET / Every 4h | discovery run, followup dispatch, inbox monitor |

---

## 14. Cost Optimization Patterns (Built Into Every Agent)

These patterns are already implemented — not aspirational. Every agent uses them.

### Prompt caching

The `cache_control` parameter is set on the system prompt in every agent's
`get_model()` configuration. Strands Agents applies this automatically.
Saves ~90% on repeated system prompt token costs.

### Model tiering

The Strands Agent itself always uses `claude-sonnet-4-6`. Agents that need
classification (session anomaly detection, response sentiment scoring) use
`claude-haiku-4-5-20251001` via separate tool-level calls. This costs ~3× less.

### Batch API

Agents 1 (backtests), 3 (weekly pitch cycle), 5 (monthly reconciliation), 7
(CLV update, strategic report), and 8 (monthly review) use the Batch API for
non-urgent tasks. 50% discount on all tokens.

### Conditional early exit (Python checks before Claude)

Every monitoring agent checks for actionable data in pure Python first.
If nothing relevant was found, the function returns without ever calling Claude.
Example: Agent 12's mention monitor checks DynamoDB before invoking the LLM.

### Total fleet monthly cost: $21.23 (Claude API) + ~$29 (AWS infra) = ~$50/month

---

## 15. The Win³ Governing Principle

Every agent's behavior is ultimately governed by Win³:
- **Win for the Artist**: Every action grows revenue, reputation, or relationships for SkyBlew and OPP artists.
- **Win for the Fan**: Every fan interaction is authentic, respectful, and delivers value.
- **Win for the World**: No agent takes an action that compromises integrity, privacy, or ethics to achieve a business goal.

Win³ is not a tagline. It is the load-bearing ethical framework that governs
what agents do when there is no explicit rule. When in doubt, ask: does this
win for the artist, the fan, AND the world? If any of the three is a "no," the
action is not taken, and it escalates to H.F.

---

## 16. What the Shared Library Will and Will Not Do

### Will build (Phase 1)

| Module | Purpose |
|---|---|
| `shared/secrets.py` | `get_api_key(env_var, sm_key=None)` — env first, SM fallback |
| `shared/slack.py` | `post_slack(webhook_url, message, timeout=5)` — direct wrapper |
| `shared/dynamo.py` | `get_table(env_var, default_name)` — Table handle factory |
| `shared/approval.py` | `enqueue_for_approval(table, item)` / `get_pending_approvals(table)` |
| `shared/context.py` | Context window management utilities |
| `shared/boid.py` | BDI-O identity validation helpers |
| `shared/logging_config.py` | Structured JSON logging setup for Lambda |

### Will NOT do

- **Will not** force any agent to import from `shared/`. Existing agents work
  as-is without modification.
- **Will not** provide a shared Strands Agent factory. Each agent's factory
  is unique to that agent's system prompt and tool list.
- **Will not** create a shared Slack client or shared DynamoDB session.
  Per-agent env vars and table handles remain isolated.
- **Will not** implement a shared approval queue. Each agent owns its queue
  table and approval flow.
- **Will not** provide a shared dispatcher. The runner script handles
  dispatch externally; agents are not changed.

---

## 17. Surprising Observations from the Survey

These are patterns that were non-obvious and worth flagging explicitly:

1. **SBIA is the only agent that uses `trigger_type` instead of `task`** as
   the dispatch key. The runner must handle both or it will silently fail.

2. **Agent 9's `handle_inbound_support` creates its own agent** — it does not
   accept an agent parameter like every other task handler. This is the most
   structurally different function in the fleet.

3. **Agents 3, 4, 5, 6, 8 have all tools inline in agent.py** with an empty
   `tools/__init__.py`. There are no separate tool files. This is not an
   incomplete pattern — it is intentional for simpler agents.

4. **Agent 12 has seven DynamoDB tables** — the largest table count in the
   fleet. Social media state is inherently multi-dimensional: content calendar,
   approval queue, post performance, mentions, analytics, campaign tracking,
   voice consistency log.

5. **Agent 6 is the most connected agent** — it triggers Agents 2, 3, 11,
   and 12 when cultural moments peak. It fires every 30 minutes, which makes
   it the fleet's real-time nervous system.

6. **The `opp-catalog` table is shared between Agents 2 and 8** — both use
   `CATALOG_TABLE` as the env var name but both default to `opp-catalog`.
   If deployed together, they should point to the same table.

7. **Agent 10 has a hard real-time SLA**: critical security findings must
   page Eric within 60 seconds. This is the only agent with a sub-minute
   latency requirement, which has implications for EC2 vs. Lambda cold starts.

8. **SBIA's approach to credentials is the cleanest** — it is the only agent
   that documents all its Secrets Manager keys in the `.env.example` as
   comments explaining what each key holds. All other agents just reference
   them inline.

11. **SBIA uses domain-specific DynamoDB key names** (`convention_id`/`discovery_date`
    as PK/SK) instead of the generic `pk`/`sk` pattern used by every other
    agent. This is not an inconsistency — SBIA's tables are designed as a
    pipeline CRM, where readable key names matter for direct console access.
    See §11 (SBIA-Specific Patterns) for full schema details.

12. **SBIA will send real emails to real people** — it is the only agent in
    the fleet that reaches outside the three-company ecosystem into the public
    internet (booking contacts at third-party conventions). Every other agent's
    outputs stay within the Lumin / OPP / 2SATS operational boundary. The
    `dry_run` flag is the critical safety gate — see §11.3.

9. **Agent 9 uses `max_tokens=2048`** while every other agent uses `4096`.
   Customer success conversations are meant to be brief and direct. This is
   a deliberate cost optimization, not an oversight.

10. **The Apple Music gate (`APPLE_MUSIC_CONFIRMED=false`) in Agent 12**
    is an explicit hard-coded safety gate — both Agent 11 (Fan Discovery)
    and Agent 12 (Social Media) reference this: no outreach begins until
    DistroKid confirms Apple Music delivery for MoreLoveLessWar/FM & AM.

---

## 18. The CHAO Model and Decision Tiers

*Source: Lumin Agent Fleet Operations Guide, Sections II and VI (April 2026)*

The fleet operates under the **Collaborative Human-AI Orchestration (CHAO)** model — a four-tier decision framework that specifies which decisions agents make autonomously, which they escalate, and which are reserved for H.F. as sole authority.

| Tier | Name | Who Decides | Examples |
|------|------|-------------|---------|
| **1** | Autonomous | Agent decides and acts without notification | Resonance scoring, cultural moment detection, security monitoring, fan signal analysis |
| **2** | Inter-Agent Coordination | Agents coordinate through the shared blackboard (DynamoDB) | Agent 06 → triggers Agents 02, 03, 11, 12 via cultural moment event; Agent 07 → feeds Agent 11 community reprioritization |
| **3** | Lumin Synthesizes, H.F. Decides | Agent produces a recommendation; H.F. makes the call | Sync pitch strategy, A&R signing recommendations, booking engagement strategy |
| **4** | H.F. Sole Authority | No agent action without explicit human approval | All public communications, outbound emails, social posts, financial and legal decisions |

### Agents Operating Under Tier 4 Constraints

Six agents (plus parts of two others) have explicit human-approval queues as a **BDI-O Obligation**, not a configurable preference:

- **Agent 02** (Sync Brief Hunter) — sync brief summaries before acting on TIER 1 briefs
- **Agent 03** (Sync Pitch Campaign) — every pitch email requires H.F. approval via `#pending-approvals`
- **Agent 09** (Customer Success) — any non-standard CS response or escalation
- **Agent 11** (Fan Discovery & Outreach) — every outreach message queued in `#fan-discovery-queue`
- **Agent 12** (Social Media Director) — every post queued in `#pending-approvals` before publish
- **SBIA** (Booking Intelligence) — every booking email approved before send; `dry_run=True` mandatory for first 14 days

> **Constitutional note (cite: Section VI of Operations Guide):** The approval gates in these agents are BDI-O **Obligations** — first-class reasoning primitives that cannot be overridden by any Desire or Intention, regardless of how compelling the goal. Removing or bypassing an approval gate is a **constitutional violation of the BDI-O architecture**, not a performance optimization. Any developer who encounters an approval gate should treat it with the same weight as a legal compliance requirement.

**Exception:** Agent 10 (CyberSecurity) acts autonomously on confirmed CRITICAL threats (IP blocking, WAF rule updates) — this too is an Obligation. The agent's duty to protect the fleet overrides the overhead of human approval in time-sensitive security incidents. Agent 10 notifies via `#security-ops` immediately after acting, not before.

---

*Last updated: Phase 3.3 — April 2026 (Operations Guide ingested: CHAO model + decision tiers added)*
*Assembled from: 13 agent ZIPs + lumin_mas_architecture_guide.docx + lumin_adk_guide.docx + LuminAgentEngineeringSpecs1.pdf + lumin_ai_cost_report.docx + booking_agent_md_file.docx (SBIA ADK Spec v1.0.0) + Lumin_Agent_Fleet_Operations_Guide.pdf*
