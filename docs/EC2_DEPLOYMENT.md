# Lumin Fleet — EC2 Deployment Runbook

**Keep this open on a second monitor during all deployment phases.**  
**Phase 3.7 — April 2026**  
**Audience:** Eric (CTO) — primary executor · H.F. (CEO) — verification and approvals

This runbook is standalone. It does not require re-reading audit reports or the Operations Guide during deployment. All relevant facts are duplicated here intentionally.

---

## Section 1 — Pre-Flight

**Before touching anything:**

> Open `docs/PRE_DEPLOY_CHECKLIST.md` and verify every box is checked. If any box is unchecked, stop and handle it first. Do not begin Wave 1 with unresolved pre-flight items.

The most common pre-flight gaps that block deployment:

| Gap | Blocker for |
|-----|-------------|
| SES production access not approved | Agents 02, 03, 05, 09, SBIA |
| Chartmetric subscription not activated | Agents 01, 07, 10 |
| `ACCOUNT` placeholder in any `.env` | Agents 01, 09, 10, SBIA |
| Agent 09 SyntaxError not fixed | Agent 09 (`tools/support_tools.py:557`) |
| Agent 10 five placeholders not replaced | Agent 10 |
| Slack workspace not built and verified | All agents |
| `sbia-epk-assets` S3 bucket not seeded | SBIA (all 6 EPK files required) |
| TikTok Research API not submitted | Agent 11 (7–14 day approval) |

---

## Section 2 — The Deployment Pattern (Universal)

Every agent follows this same 12-step sequence. Only the specifics differ. Learn it once and apply it to all 13 agents.

All `make` commands run from the repo root (`/opt/lumin-agents`).

| Step | Command | Success looks like | If it fails |
|------|---------|-------------------|-------------|
| **1. Provision AWS resources** | See agent card (Section 3) | DynamoDB tables visible in AWS console; SM placeholders created | Check IAM role permissions; run `aws sts get-caller-identity` to confirm EC2 role is active |
| **2. Populate secrets** | AWS Secrets Manager console or `aws secretsmanager put-secret-value` | `aws secretsmanager get-secret-value --secret-id <key>` returns real value, not placeholder | Ensure Secret exists before putting value; SM key names are case-sensitive |
| **3. Prepare the EC2 box** | `git -C /opt/lumin-agents pull && sudo chown -R lumin:lumin /opt/lumin-agents` | Repo is at latest commit; `lumin` user owns all files | If repo is stale, pull. If ownership is wrong, `chown -R` from root. |
| **4. Configure .env** | Copy `.env.example` → `.env` in agent folder; fill in all values | `cat agents/agent-<N>/.env \| grep -v "^#"` shows no blank values and no placeholder strings | Run `grep "ACCOUNT\|EXXXXXX\|sk-ant-\.\.\." agents/agent-<N>/.env` — any match means unfilled placeholder |
| **5. Install venv and dependencies** | `make install AGENT=<N>` | `Done. venv ready.` printed; `agents/agent-<N>/venv/` exists | Check Python 3.12 is on PATH; check `requirements.txt` has no version conflicts |
| **6. Run local smoke tests** | `make test-agent AGENT=<N>` | All tests pass; no `FAILED` or `ERROR` lines | Read the specific test failure; most common cause is missing env var or unreachable table |
| **7. Manual first run (dry-run)** | `make run AGENT=<N> TASK=<first-task>` | Clean JSON response; no `"error"` key in output | Run with `--dry_run=true` for SBIA. Check CloudWatch Logs immediately after for stack traces. |
| **8. Install systemd service and timers** | `make install-systemd AGENT=<N>` | `systemctl status lumin-agent-<N>*` shows loaded (not active — timers haven't fired yet) | Check `/etc/systemd/system/` for copied unit files; run `systemctl daemon-reload` if units not found |
| **9. Verify timers scheduled** | `systemctl list-timers \| grep lumin` | Agent's timers appear with next trigger time | If timer not listed: `systemctl enable lumin-agent-<N>-<task>.timer && systemctl start lumin-agent-<N>-<task>.timer` |
| **10. Wait for first scheduled run** | `make logs AGENT=<N>` | JSON output appears in journal; no Python exception | If run doesn't fire: check timer is active, check service `ExecStart` path is correct, check `lumin` user can execute |
| **11. Verify human-facing surface** | Open the agent's Slack channel | Expected message appears in channel | If Slack silent: check webhook env var is set; test with `scripts/test_slack_channels.py` |
| **12. Document in DEPLOY_LOG.md** | Append entry to `docs/DEPLOY_LOG.md` | Entry records: agent name, deploy date, wave, who deployed, first-run result, any issues | Do not skip — DEPLOY_LOG is the audit trail for the fleet |

**AGENT= value for `make` commands:**  
Use the agent folder name minus the `agent-` prefix. Examples:
- `AGENT=04-anime-gaming` → folder `agents/agent-04-anime-gaming`
- `AGENT=sbia-booking` → folder `agents/agent-sbia-booking`

---

## Section 3 — Per-Agent Quick-Reference Cards

One card per agent. Each card is self-contained — no need to open the audit report during deployment.

For full detail on any field, see: `audit/agent-<N>-<name>.md`

---

### Card A01 — Resonance Intelligence Agent

| Field | Value |
|-------|-------|
| **Display name** | Resonance Intelligence Agent |
| **Entity** | Lumin Luxe Inc. |
| **Wave** | Wave 2 — Strategic Intelligence (Week 2) |
| **Deploy order** | First in Wave 2 — Agents 06 and 07 depend on its output |
| **Upstream deps** | None (reads external APIs only) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `resonance-model-params` | On-demand billing |
| DynamoDB table | `resonance-trend-signals` | On-demand billing |
| DynamoDB table | `resonance-backtest-log` | On-demand billing |
| DynamoDB table | `resonance-predictions` | On-demand billing |
| Kinesis stream OR DynamoDB Stream | `resonance-raw-stream` | **Decision required first** — see DEPLOY_PLAN.md §4 |
| S3 bucket | `lumin-backtest-archive` | Standard storage class |
| SNS topic | `lumin-resonance-alerts` | Subscribe H.F.'s email |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `lumin/chartmetric-api-key` | Paid subscription — chartmetric.com |
| `lumin/soundcharts-api-key` | Paid subscription — soundcharts.com |
| `lumin/spotify-oauth-token` | developer.spotify.com — free |
| `lumin/youtube-api-key` | Google Cloud Console — free quota |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY        CHARTMETRIC_API_KEY      SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET    SOUNDCHARTS_API_KEY       YOUTUBE_API_KEY
KINESIS_STREAM           S3_BACKTEST_BUCKET        SLACK_RESONANCE_WEBHOOK
SNS_RESONANCE_TOPIC      MODEL_TABLE               SIGNALS_TABLE
BACKTEST_TABLE           PREDICT_TABLE
```
Replace `ACCOUNT` in `SNS_RESONANCE_TOPIC`.

**First Task:** `make run AGENT=01-resonance TASK=hourly_data_collection`

**Systemd Timers (pre-written in `infra/systemd/example-timers/`):**

| Timer file | Schedule |
|-----------|---------|
| `lumin-agent-01-hourly-data.timer` | Every hour |
| `lumin-agent-01-daily-physics.timer` | Daily 02:00 UTC |
| `lumin-agent-01-weekly-backtest.timer` | Sunday 04:00 UTC |

**Slack Channel(s):** `#resonance-intelligence` (phase transition alerts, no morning workflow slot)

**48-Hour Acceptance Criteria:**
- [ ] Hourly data collection fires within 1 hour and writes to `resonance-trend-signals`
- [ ] `resonance-model-params` table receives Boltzmann update within 24h (Agent 06 dependency gate)
- [ ] SNS topic `lumin-resonance-alerts` fires — H.F. email received
- [ ] All 3 systemd timers active
- [ ] No `"error"` key in any run output

**Risk Callouts (top 2):**
1. Kinesis $10.80/month — confirm Kinesis vs. DynamoDB Streams decision before provisioning
2. `SKYBLEW_CM_ID` is Agent 07's placeholder, not 01 — don't confuse

---

### Card A02 — Sync Brief Hunter

| Field | Value |
|-------|-------|
| **Display name** | Sync Brief Hunter |
| **Entity** | OPP Inc. |
| **Wave** | Wave 3 — Revenue Operations (Week 3) |
| **Deploy order** | Any order within Wave 3; Agent 08 benefits from its accumulated data |
| **Upstream deps** | Agent 06 (cultural moment triggers via Kinesis/DynamoDB stream) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `sync-briefs` | On-demand billing |
| DynamoDB table | `opp-catalog` | Shared with Agents 03, 08 — seed before deploy |
| DynamoDB table | `sync-submissions` | On-demand billing |
| SES verified identity | `hello@lumin.luxe` | Shared with Agent 09 |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   FROM_EMAIL=hello@lumin.luxe   HF_EMAIL=hf@lumin.luxe
SLACK_SYNC_WEBHOOK  BRIEFS_TABLE                  CATALOG_TABLE
SUBS_TABLE
```

**First Task:** `make run AGENT=02-sync-brief TASK=brief_scan`

**Systemd Timers:** No pre-written files. Create a timer for every-4-hour cadence using the standard `lumin-agent@.service` template. Schedule: `OnCalendar=*-*-* 00,04,08,12,16,20:00:00`

**Slack Channel(s):** `#sync-queue` (brief discovery queue, 7:30am morning check) · `#pending-approvals` (TIER 1 brief approval requests)

**48-Hour Acceptance Criteria:**
- [ ] First 4-hour scan runs and logs to CloudWatch with no `"error"` key
- [ ] Scan result posts to `#sync-queue` within 8 hours of deployment
- [ ] `opp-catalog` table seeded and returns catalog matches in first run
- [ ] Approval gate verified: TIER 1 brief lands in `#pending-approvals` (not sent automatically)

**Risk Callouts (top 2):**
1. `opp-catalog` must be seeded with OPP catalog data before meaningful matching
2. Platform scraping — no API credentials; Cloudflare or anti-bot may silently block brief discovery

---

### Card A03 — Sync Pitch Campaign

| Field | Value |
|-------|-------|
| **Display name** | Sync Pitch Campaign Agent |
| **Entity** | OPP Inc. |
| **Wave** | Wave 3 — Revenue Operations (Week 3) |
| **Deploy order** | Any order within Wave 3 |
| **Upstream deps** | Agent 06 (cultural moment triggers) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `sync-supervisors` | On-demand billing |
| DynamoDB table | `sync-pitches` | On-demand billing |
| SES verified identity | `sync@opp.pub` | New sender identity — warm up carefully |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   FROM_EMAIL=sync@opp.pub   SLACK_PITCH_WEBHOOK
SUPERVISORS_TABLE   PITCHES_TABLE
```

**First Task:** `make run AGENT=03-sync-pitch TASK=weekly_pitch_cycle`

**Systemd Timers:** No pre-written files. Create a timer for Monday weekly cadence. Schedule: `OnCalendar=Mon *-*-* 10:00:00`

**Slack Channel(s):** `#pending-approvals` (pitch email variants for H.F. approval) · `#sync-pitches` (weekly cycle summaries)

**48-Hour Acceptance Criteria:**
- [ ] Pitch cycle runs and produces 3 email variants per supervisor in `#pending-approvals`
- [ ] H.F. approval gate confirmed: no pitch email sent without explicit approval
- [ ] `sync-pitches` weekly summary posts after cycle completes
- [ ] Joel C. High (Tyler Perry Studios) appears as top-priority target in first pitch cycle

**Risk Callouts (top 2):**
1. Verify all 6 supervisor contacts before live run — hardcoded emails may be outdated
2. No opt-out mechanism — if a supervisor requests removal, handle manually

---

### Card A04 — Anime & Gaming Market Scout

| Field | Value |
|-------|-------|
| **Display name** | Anime & Gaming Market Scout |
| **Entity** | OPP Inc. + 2StepsAboveTheStars LLC |
| **Wave** | Wave 1 — Foundation (Week 1, first agent) |
| **Deploy order** | First agent in entire fleet — proves the infrastructure foundation |
| **Upstream deps** | None |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `anime-gaming-opportunities` | On-demand billing |
| DynamoDB table | `anime-gaming-pitches` | On-demand billing |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   SLACK_AG_WEBHOOK   SCOUT_TABLE   AG_PITCHES_TABLE
```

**First Task:** `make run AGENT=04-anime-gaming TASK=daily_scout`

**Systemd Timers:** No pre-written files. Create a timer for daily cadence. Schedule: `OnCalendar=*-*-* 09:00:00`

**Slack Channel(s):** `#anime-gaming-intel` (daily scout summaries and score-8+ alerts, async review)

**48-Hour Acceptance Criteria:**
- [ ] First daily scout run posts to `#anime-gaming-intel` within 24h
- [ ] At least one record in `anime-gaming-opportunities` table
- [ ] Score-8+ opportunity fires immediate Slack alert (inject test record to verify)
- [ ] No Python exceptions in CloudWatch

**Risk Callouts (top 2):**
1. Code currently returns synthetic hardcoded data — H.F. must understand Agent 04 is not yet reading live ANN/Crunchyroll APIs
2. Spine Sounds Tokyo contact (`info@spinesounds.com`) — verify before pitching

---

### Card A05 — Royalty Reconciliation

| Field | Value |
|-------|-------|
| **Display name** | Royalty Reconciliation Agent |
| **Entity** | OPP Inc. |
| **Wave** | Wave 1 — Foundation (Week 1, second agent) |
| **Deploy order** | After Agent 04 in Wave 1 |
| **Upstream deps** | None |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `opp-royalty-statements` | Seed with at least 1 real PRO statement |
| DynamoDB table | `opp-royalty-issues` | On-demand billing |
| SES verified identity | `royalties@opp.pub` | |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   FROM_EMAIL=royalties@opp.pub   SLACK_ROYALTY_WEBHOOK
ROYALTY_TABLE       ISSUES_TABLE
```

**First Task:** `make run AGENT=05-royalty TASK=monthly_reconciliation`

**Systemd Timers:** No pre-written files. Create a monthly timer. Schedule: `OnCalendar=*-*-1 09:00:00` (1st of each month)

**Slack Channel(s):** `#pending-approvals` (discrepancy alerts); SES email to H.F. for monthly report (no dedicated Slack channel for routine output)

**48-Hour Acceptance Criteria:**
- [ ] Smoke test completes with at least one record in `opp-royalty-issues`
- [ ] SES email from `royalties@opp.pub` received by H.F. after first run
- [ ] `opp-royalty-statements` seeded with real PRO statement before considering output meaningful

**Risk Callouts (top 2):**
1. `fetch_pro_statements()` returns synthetic data — first meaningful output requires manually imported ASCAP/BMI/SoundExchange/MLC statements
2. Monthly cadence means late detection — flag important discrepancies early in the PRO import process

---

### Card A06 — Cultural Moment Detection

| Field | Value |
|-------|-------|
| **Display name** | Cultural Moment Detection Agent |
| **Entity** | OPP Inc. / 2StepsAboveTheStars / Lumin Luxe (all three entities) |
| **Wave** | Wave 2 — Strategic Intelligence (Week 2, last in wave) |
| **Deploy order** | After Agent 01 has at least 24 hours of entropy data in `resonance-model-params` |
| **Upstream deps** | Agent 01 (entropy baseline from `resonance-model-params`) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `cultural-moments` | On-demand billing |
| DynamoDB table | `cultural-entropy-log` | On-demand billing |
| Kinesis stream OR DynamoDB Stream | `cultural-signal-stream` | Same decision as Agent 01 — must match |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   SLACK_CULTURAL_WEBHOOK   MOMENTS_TABLE   ENTROPY_TABLE
```

**First Task:** `make run AGENT=06-cultural TASK=scan_trending`

**Systemd Timers (pre-written in `infra/systemd/example-timers/`):**

| Timer file | Schedule |
|-----------|---------|
| `lumin-agent-06-thirty-min-scan.timer` | Every 30 minutes |

**Slack Channel(s):** `#cultural-moments` (H.F. checks at 7:15am)

**48-Hour Acceptance Criteria:**
- [ ] First 30-min scan runs within 30 minutes of deployment
- [ ] Test FORMING moment (convergence ≥0.50) posts to `#cultural-moments`
- [ ] Test PEAK moment generates URGENT flag in `#cultural-moments`
- [ ] MoreLoveLessWar standing Tier 1 match verified: any peace/conflict topic triggers alert regardless of score
- [ ] Central Signal Chain tested: PEAK moment → Agents 02, 03, 11, 12 all activate within documented windows (see Section 4)

**Risk Callouts (top 2):**
1. Four agents depend on Agent 06 — if it fails silently, the entire event-driven tier breaks. Monitor as fleet health proxy.
2. Kinesis $10.80/month — confirm stream type decision before provisioning

---

### Card A07 — Fan Behavior Intelligence

| Field | Value |
|-------|-------|
| **Display name** | Fan Behavior Intelligence Agent |
| **Entity** | 2StepsAboveTheStars LLC |
| **Wave** | Wave 2 — Strategic Intelligence (Week 2) |
| **Deploy order** | Parallel with Agent 01 at Wave 2 start (minor dependency on Agent 01's Boltzmann signals) |
| **Upstream deps** | Agent 01 (Boltzmann temperature/entropy signals for CLV threshold calibration) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `fan-behavior-metrics` | On-demand billing |
| DynamoDB table | `fan-clv-model` | Agent 11 reads this — create before Wave 4 |
| DynamoDB table | `fan-geographic-index` | On-demand billing |
| DynamoDB table | `fan-genre-affinity` | Agent 12 reads this |
| DynamoDB table | `skyblew-app-config` | On-demand billing |
| S3 bucket | `lumin-fan-intelligence` | Standard storage class |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `lumin/chartmetric-api-key` | Shared with Agents 01, 10 |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   CHARTMETRIC_API_KEY   SKYBLEW_CM_ID   SLACK_FAN_WEBHOOK
S3_REPORTS_BUCKET   FES_TABLE             CLV_TABLE        GEO_TABLE
AFFI_TABLE          APP_CONFIG_TABLE
```
**Critical:** Replace `SKYBLEW_CM_ID=skyblew_chartmetric_artist_id` with SkyBlew's real Chartmetric artist ID (find it in the Chartmetric dashboard — artist profile URL contains the numeric ID).

**First Task:** `make run AGENT=07-fan-behavior TASK=daily_metrics_update`

**Systemd Timers:** No pre-written files. Create timers for:
- Daily: `OnCalendar=*-*-* 07:00:00`
- Weekly: `OnCalendar=Sun *-*-* 06:00:00`
- Monthly: `OnCalendar=*-*-1 08:00:00`

**Slack Channel(s):** `#fan-intelligence` (daily/weekly/monthly reports, async)

**48-Hour Acceptance Criteria:**
- [ ] Daily 07:00 UTC run completes and writes FES record to `fan-behavior-metrics`
- [ ] `SKYBLEW_CM_ID` confirmed correct — Chartmetric returns SkyBlew's data specifically (not error or wrong artist)
- [ ] `fan-clv-model` receives records (unblocks Agent 11)
- [ ] `fan-genre-affinity` receives records (unblocks Agent 12)
- [ ] S3 bucket receives at least one report object

**Risk Callouts (top 2):**
1. Wrong `SKYBLEW_CM_ID` is a silent failure — all CLV/FES data will be for wrong artist; verify before first run
2. Model needs 4–6 weeks of data before output is meaningful; don't judge output quality in Week 1

---

### Card A08 — A&R & Catalog Growth

| Field | Value |
|-------|-------|
| **Display name** | A&R & Catalog Growth Agent |
| **Entity** | OPP Inc. |
| **Wave** | Wave 3 — Revenue Operations (Week 3) |
| **Deploy order** | After Agents 02 and 03 have been live and accumulating data |
| **Upstream deps** | Agent 02 (brief rejection patterns in `sync-briefs`) · Agent 03 (pitch outcomes in `sync-pitches`) |

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `opp-catalog` | Shared with Agents 02, 03 — already exists from Wave 3 |
| DynamoDB table | `opp-catalog-gaps` | On-demand billing |
| DynamoDB table | `opp-ar-targets` | On-demand billing |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   SLACK_AR_WEBHOOK   CATALOG_TABLE   GAPS_TABLE   TARGETS_TABLE
```

**First Task:** `make run AGENT=08-ar-catalog TASK=monthly_catalog_review`

**Systemd Timers:** No pre-written files. Create a monthly timer. Schedule: `OnCalendar=*-*-1 10:00:00`

**Slack Channel(s):** `#ar-catalog` (monthly A&R strategy report and on-demand artist scoring)

> **Note:** Agent 08 code system prompt references `#ar-strategy` — the webhook (`SLACK_AR_WEBHOOK`) is configured to `#ar-catalog`, which is the canonical channel name. No code change needed — webhook routing takes precedence.

**48-Hour Acceptance Criteria:**
- [ ] Smoke test writes at least one record to `opp-catalog-gaps`
- [ ] `opp-catalog` seeded with OPP Inc. catalog and Elvin Ross / Ronnie Garrett integration status
- [ ] On-demand artist scoring: test artist through RE™ DNA filter returns score to `#ar-catalog`

**Risk Callouts (top 2):**
1. `opp-catalog` write authority — Agent 08 writes; Agents 02/03 read-only. Enforce at IAM if possible.
2. Gap analysis needs 2–3 months of data before statistically meaningful; don't judge Month 1 output harshly

---

### Card A09 — AskLumin Customer Success

| Field | Value |
|-------|-------|
| **Display name** | AskLumin Customer Success Agent |
| **Entity** | Lumin Luxe Inc. |
| **Wave** | Wave 4 — Public-Facing (Week 4) |
| **Deploy order** | First in Wave 4 |
| **Upstream deps** | None hard (Agent 01 optional for value demo content) |

> **DEPLOY BLOCKER — fix before attempting install:**  
> `agents/agent-09-customer-success/tools/support_tools.py:557` — duplicate `ExpressionAttributeValues` keyword argument in a DynamoDB `query()` call. Python 3.9+ raises `SyntaxError` at import time. The entire agent module fails to load. Fix is ~30 minutes. `make test-agent AGENT=09-customer-success` will fail until this is resolved.

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `ask-lumin-sessions` | Pre-populate with existing subscriber records before enabling |
| DynamoDB table | `ask-lumin-cs-tickets` | On-demand billing |
| DynamoDB table | `ask-lumin-cs-metrics` | On-demand billing |
| DynamoDB table | `ask-lumin-onboarding` | On-demand billing |
| DynamoDB table | `ask-lumin-nps` | On-demand billing |
| SES verified identity | `hello@lumin.luxe` | Shared with Agent 02 — may already exist |
| SNS topic | `lumin-cs-escalations` | Subscribe H.F.'s email |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY   FROM_EMAIL=hello@lumin.luxe   SLACK_CS_WEBHOOK
SNS_ESCALATION_TOPIC   SESSIONS_TABLE   CS_TICKETS_TABLE
CS_METRICS_TABLE   ONBOARDING_TABLE   NPS_TABLE
```
Replace `ACCOUNT` in `SNS_ESCALATION_TOPIC`.

**First Task:** `make run AGENT=09-customer-success TASK=daily_onboarding_scan`

**Systemd Timers (pre-written in `infra/systemd/example-timers/`):**

| Timer file | Schedule |
|-----------|---------|
| `lumin-agent-09-onboarding-sweep.timer` | Daily |
| `lumin-agent-09-churn-scan.timer` | Daily |
| `lumin-agent-09-weekly-digest.timer` | Weekly |

**Slack Channel(s):** `#cs-escalations` (escalations H.F. cannot resolve) · `#pending-approvals` (proactive outreach drafts)

**48-Hour Acceptance Criteria:**
- [ ] SyntaxError in `tools/support_tools.py:557` confirmed fixed — `import` of module succeeds
- [ ] `make test-agent AGENT=09-customer-success` passes all tests
- [ ] `ask-lumin-sessions` pre-populated with existing subscriber records
- [ ] Approval gate verified: churn-risk outreach appears in `#pending-approvals`, NOT sent automatically
- [ ] Escalation path verified: test escalation triggers SNS `lumin-cs-escalations` and H.F. receives alert
- [ ] All 3 systemd timers active

**Risk Callouts (top 2):**
1. SyntaxError is the deploy blocker — fix first, run `make test-agent` to confirm before any other steps
2. `ask-lumin-sessions` must be pre-seeded — agent has no context for subscriber-specific responses without it

---

### Card A10 — CyberSecurity Agent

| Field | Value |
|-------|-------|
| **Display name** | CyberSecurity Agent |
| **Entity** | Lumin Luxe Inc. |
| **Wave** | Wave 4 — Public-Facing (Week 4) |
| **Deploy order** | After Agent 09 in Wave 4 |
| **Upstream deps** | Reads `skyblew-sessions` (SkyBlew app backend) · Reads `fan-behavior-metrics` (Agent 07) · Reads `ask-lumin-*` tables (Agent 09) for GDPR deletion |

> **FIVE PLACEHOLDERS MUST BE REPLACED:**  
> `grep -n "LUMIN-WAF-ACL-ID\|EXXXXXXXXXXXXXX\|LUMIN-GUARDDUTY-DETECTOR-ID\|ACCOUNT" agents/agent-10-cybersecurity/tools/*.py agents/agent-10-cybersecurity/.env`  
> All 5 must return no matches before deployment.

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `skyblew-sessions` | May already exist (SkyBlew app) |
| DynamoDB table | `security-asset-hashes` | Seed with SHA-256 hashes of 5 assets before first run |
| DynamoDB table | `security-events` | On-demand billing |
| DynamoDB table | `security-alerts` | On-demand billing |
| DynamoDB table | `security-fraud-reports` | On-demand billing |
| AWS GuardDuty | Enable in us-east-1 | Run `aws guardduty list-detectors` after enabling to get detector ID |
| SNS topic | `lumin-security-alerts` | Subscribe `#security-alerts` Slack webhook |
| SNS topic | `lumin-critical-page` | Subscribe Eric's phone number via SMS |

**Five Placeholder Replacements:**

| File | Placeholder | Replace with |
|------|-------------|-------------|
| `tools/waf_tools.py:15` | `LUMIN-WAF-ACL-ID` | WAF ACL ID from AWS console |
| `tools/waf_tools.py:97` | `ACCOUNT` (in ARN) | 12-digit AWS account ID |
| `tools/content_tools.py:15` + `.env` | `EXXXXXXXXXXXXXX` | CloudFront distribution ID |
| `tools/guardduty_tools.py:13` | `LUMIN-GUARDDUTY-DETECTOR-ID` | GuardDuty detector ID |
| `.env` `SNS_SECURITY_TOPIC` | `ACCOUNT` | 12-digit AWS account ID |
| `.env` `SNS_CRITICAL_TOPIC` | `ACCOUNT` | 12-digit AWS account ID |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `lumin/chartmetric-api-key` | Shared with Agents 01, 07 |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY        SLACK_SECURITY_WEBHOOK     SNS_SECURITY_TOPIC
SNS_CRITICAL_TOPIC       CHARTMETRIC_API_KEY        CF_DISTRIBUTION_ID
SESSIONS_TABLE           ASSET_HASHES_TABLE         SECURITY_EVENTS_TABLE
SECURITY_ALERTS_TABLE    FRAUD_REPORTS_TABLE
```

**First Task:** `make run AGENT=10-cybersecurity TASK=daily_guardduty_digest`

**Systemd Timers:** No pre-written files. Create timers for:
- Every 15 min session scan: `OnCalendar=*-*-* *:00,15,30,45:00`
- Daily 02:00 content integrity: `OnCalendar=*-*-* 02:00:00`
- Daily 08:00 GuardDuty digest: `OnCalendar=*-*-* 08:00:00`
- Sunday 03:00 fraud scan: `OnCalendar=Sun *-*-* 03:00:00`

**Slack Channel(s):** `#security-ops` (daily digest, H.F. checks at 7:45am) · `#security-alerts` (CRITICAL events only; Eric's mobile notifications enabled)

**48-Hour Acceptance Criteria:**
- [ ] All 5 placeholders replaced — `grep` returns zero matches
- [ ] `security-asset-hashes` seeded with SHA-256 hashes for all 5 protected assets
- [ ] Daily GuardDuty digest posts to `#security-ops`
- [ ] 60-second Eric page verified: test CRITICAL event → SNS → Eric SMS within 60 seconds
- [ ] Content integrity check completes without false-positive tamper alerts
- [ ] Auto-block authority verified: CRITICAL finding logs action to `#security-ops` without waiting for human approval

**Risk Callouts (top 2):**
1. All 5 placeholders unresolved = silent monitoring failures in 5 separate security functions — verify with grep before any deployment step
2. `security-asset-hashes` empty on Day 1 = every asset triggers false tamper alert — seed immediately after table creation

---

### Card A11 — Fan Discovery & Outreach

| Field | Value |
|-------|-------|
| **Display name** | Fan Discovery & Outreach Agent |
| **Entity** | 2StepsAboveTheStars LLC |
| **Wave** | Wave 4 — Public-Facing (Week 4) |
| **Deploy order** | After Agents 06 (triggers) and 07 (CLV data) are live |
| **Upstream deps** | Agent 06 (cultural moment triggers) · Agent 07 (CLV ranking from `fan-clv-model`) |

> **TikTok Research API — 7 to 14 day approval.** Submit the application at developers.tiktok.com/products/research-api by end of Wave 2 Week 2. Agent 11 can deploy without it (Reddit + YouTube work immediately) but `#nujabes` TikTok outreach — the single highest-ROI discovery surface — is unavailable until approval arrives.

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `fan-discovery-outreach-queue` | On-demand billing |
| DynamoDB table | `fan-discovery-communities` | On-demand billing |
| DynamoDB table | `fan-discovery-entry-points` | On-demand billing |
| DynamoDB table | `fan-discovery-conversions` | On-demand billing |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `lumin/chartmetric-api-key` | Shared with Agents 01, 07, 10 |
| `lumin/youtube-api-key` | Shared with Agents 01, 07 |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY       REDDIT_CLIENT_ID           REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT       YOUTUBE_API_KEY            TIKTOK_RESEARCH_API_KEY
CHARTMETRIC_API_KEY     SLACK_DISCOVERY_WEBHOOK    OUTREACH_QUEUE_TABLE
COMMUNITIES_TABLE       ENTRY_POINTS_TABLE         CONVERSIONS_TABLE
```

**First Task:** `make run AGENT=11-fan-discovery TASK=morning_discovery`

**Systemd Timers:** No pre-written files. Create timers for:
- 06:00 UTC discovery scan: `OnCalendar=*-*-* 06:00:00`
- 07:00 UTC queue generation: `OnCalendar=*-*-* 07:00:00`
- 22:00 UTC conversion report: `OnCalendar=*-*-* 22:00:00`
- Weekly community ranking: `OnCalendar=Mon *-*-* 08:00:00`

**Slack Channel(s):** `#fan-discovery-queue` (daily 07:00 UTC queue, H.F. checks at 8:15am) · `#pending-approvals` (URGENT cultural moment outreach when Agent 06 fires)

**48-Hour Acceptance Criteria:**
- [ ] 06:00 UTC scan runs and logs to CloudWatch
- [ ] 07:00 UTC run produces at least 3 outreach opportunities in `fan-discovery-outreach-queue`
- [ ] Opportunities appear in `#fan-discovery-queue` with 3 message variants each
- [ ] Approval gate verified: no outreach posted to any platform without H.F. explicit approval
- [ ] Distribution health check confirms MoreLoveLessWar Apple Music gate status
- [ ] r/BombRushCyberfunk and r/nujabes appear in first week's discovery results

**Risk Callouts (top 2):**
1. TikTok Research API approval governs full deployment — without it, #nujabes (800M+ TikTok views) is inaccessible
2. Human approval gate is architecturally enforced — confirm `submit_for_human_approval()` is the only exit from draft queue

---

### Card A12 — Social Media Director

| Field | Value |
|-------|-------|
| **Display name** | Social Media Director (Creative Resonance Architect) |
| **Entity** | 2StepsAboveTheStars LLC |
| **Wave** | Wave 4 — Public-Facing (Week 4) |
| **Deploy order** | Last in Wave 4; requires Agents 06, 07, 11 all live |
| **Upstream deps** | Agent 06 (cultural triggers) · Agent 07 (genre affinity from `fan-genre-affinity`) · Agent 11 (fan art detections) |

> **Three gates must clear before meaningful operation:**  
> 1. `skyblew/voice-book` SM secret must be authored by H.F. + SkyBlew and populated  
> 2. `APPLE_MUSIC_CONFIRMED=false` → set `true` only after DistroKid confirms Apple Music delivery  
> 3. All 6 platform OAuth tokens must be obtained (2–5 days each for some)

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `skyblew-content-calendar` | On-demand billing |
| DynamoDB table | `skyblew-approval-queue` | On-demand billing |
| DynamoDB table | `skyblew-post-performance` | On-demand billing |
| DynamoDB table | `skyblew-fan-interactions` | On-demand billing |
| DynamoDB table | `skyblew-analytics` | On-demand billing |
| DynamoDB table | `skyblew-fm-am-campaign` | On-demand billing |
| DynamoDB table | `skyblew-voice-log` | On-demand billing |
| SM secret | `skyblew/voice-book` | H.F. + SkyBlew must author content — allow 1 day |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `skyblew/voice-book` | H.F. + SkyBlew author in Sunday session before deploy |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY         APPLE_MUSIC_CONFIRMED     INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_USER_ID         TIKTOK_ACCESS_TOKEN       TWITTER_API_KEY
TWITTER_API_SECRET        TWITTER_ACCESS_TOKEN      TWITTER_ACCESS_TOKEN_SECRET
YOUTUBE_OAUTH_TOKEN       DISCORD_BOT_TOKEN         DISCORD_GUILD_ID
DISCORD_CHANNEL_ID        THREADS_ACCESS_TOKEN      THREADS_USER_ID
SLACK_APPROVAL_WEBHOOK    SLACK_SOCIAL_WEBHOOK      SKYBLEW_VOICE_BOOK_SECRET_KEY
CALENDAR_TABLE            QUEUE_TABLE               PERF_TABLE
MENTIONS_TABLE            ANALYTICS_TABLE           CAMPAIGN_TABLE
VOICE_TABLE
```

**First Task:** `make run AGENT=12-social-media TASK=content_queue`

**Systemd Timers:** No pre-written files. Create timers for:
- Every 15 min mention monitoring: `OnCalendar=*-*-* *:00,15,30,45:00`
- Daily content queue: `OnCalendar=*-*-* 09:00:00`
- Sunday 18:00 UTC content calendar: `OnCalendar=Sun *-*-* 18:00:00`

**Slack Channel(s):** `#social-approvals` (content drafts for H.F. approval, H.F. checks at 7:00am) · `#social-intelligence` (analytics digest)

**48-Hour Acceptance Criteria:**
- [ ] Voice Book (`skyblew/voice-book`) seeded — `load_voice_book()` returns non-empty content
- [ ] First content queue run produces at least 1 draft in `skyblew-approval-queue`
- [ ] Draft post routes to `#social-approvals` with approve/edit/decline options
- [ ] Approval gate verified: no post published to any platform without H.F. explicit approval
- [ ] Full cycle tested: draft → H.F. approves → `post_approved_message()` → `skyblew-post-performance` record
- [ ] Sunday 18:00 UTC content calendar timer active
- [ ] MoreLoveLessWar campaign phase shows `STATIC` or `MYSTERY` (NOT `BROADCAST` — requires Apple Music gate)

**Risk Callouts (top 2):**
1. Highest Claude API cost in fleet ($7.55/mo) — 15-min mention monitoring at scale; build a cost alert at $15/mo
2. Any post published without H.F. approval is a BDI-O Obligation violation and immediate pause trigger

---

### Card SBIA — SkyBlew Booking Intelligence Agent

| Field | Value |
|-------|-------|
| **Display name** | SkyBlew Booking Intelligence Agent (SBIA) |
| **Entity** | 2StepsAboveTheStars LLC |
| **Wave** | Wave 3 — Revenue Operations (Week 3) |
| **Deploy order** | Any order within Wave 3; 14-day dry_run window starts at deploy |
| **Upstream deps** | None (fully isolated agent — by design) |

> **14-DAY DRY_RUN IS MANDATORY.** SBIA sends real emails to real convention organizers. Run `{"trigger_type": "DISCOVERY_RUN", "dry_run": true}` for a minimum of 14 days before enabling live sending. Reputational damage from a poorly calibrated first run cannot be undone. Do not skip the dry_run period under any business pressure.

> **`SBIA_FOLLOWUP_LAMBDA_ARN` placeholder:** Replace `ACCOUNT` with the 12-digit AWS account ID before deployment. If unresolved, all 7-day follow-up emails fail silently.

**AWS Resources to Create:**

| Resource | Name | Notes |
|----------|------|-------|
| DynamoDB table | `sbia_conventions` | Seed with 22 starter conventions before first run |
| DynamoDB table | `sbia_outreach_log` | On-demand billing |
| S3 bucket | `sbia-epk-assets` | Upload all 6 EPK files to `sbia-epk-assets/epk/` |
| S3 bucket | `sbia-booking-inbox` | SES receive rule routes here |
| SES verified identity | `booking@2stepsabovestars.com` | Also needs SES receive rule and MX record |
| SES receive rule | `booking@2stepsabovestars.com` → `sbia-booking-inbox` | Configure SES receipt rules |
| Lambda function | `sbia-followup-dispatcher` | Deploy standalone before main agent |
| SNS topic | (from `sbia/sns-alert-topic-arn`) | H.F. + SMS HOT LEAD alerts |

**Secrets to Populate:**

| SM Key | Value Source |
|--------|-------------|
| `lumin/anthropic-api-key` | Shared fleet key |
| `sbia/web-search-api-key` | Tavily or Brave Search API |
| `sbia/ses-sending-identity` | Verified SES sender |
| `sbia/sns-alert-topic-arn` | SNS topic ARN for H.F. alerts |
| `sbia/slack-webhook-url` | Incoming webhook for `#hot-leads` (SM-stored, no env var) |

**Env Vars to Set in `.env`:**

```
ANTHROPIC_API_KEY       SBIA_FROM_EMAIL            SBIA_REPLY_TO
SBIA_CONVENTIONS_TABLE  SBIA_OUTREACH_LOG_TABLE    SBIA_EPK_BUCKET
SBIA_EMAIL_INBOX_BUCKET SBIA_FOLLOWUP_LAMBDA_ARN
```
Replace `ACCOUNT` in `SBIA_FOLLOWUP_LAMBDA_ARN`.

**First Task:** `make run AGENT=sbia-booking TASK=DISCOVERY_RUN PARAMS="dry_run=true"`

**Systemd Timers (pre-written in `infra/systemd/example-timers/`):**

| Timer file | Schedule |
|-----------|---------|
| `lumin-agent-sbia-discovery.timer` | Monday 09:00 ET |
| `lumin-agent-sbia-followup.timer` | Daily 10:00 ET |
| `lumin-agent-sbia-inbox-monitor.timer` | Every 4 hours |

**Slack Channel(s):** `#hot-leads` (HOT/WARM lead alerts, H.F. checks at 8:00am); SBIA uses `sbia/slack-webhook-url` SM secret — not an env var. **H.F. must have mobile notifications enabled for `#hot-leads`.** HOT LEAD response window is time-sensitive.

**EPK S3 Asset Checklist (all 6 required before first email send):**
- [ ] `sbia-epk-assets/epk/epk.pdf`
- [ ] `sbia-epk-assets/epk/skyblew_bio.txt`
- [ ] `sbia-epk-assets/epk/press_photo_hires.jpg`
- [ ] `sbia-epk-assets/epk/stage_plot.pdf`
- [ ] `sbia-epk-assets/epk/rider.pdf`
- [ ] `sbia-epk-assets/epk/sample_setlist.pdf`

**48-Hour Acceptance Criteria:**
- [ ] `SBIA_FOLLOWUP_LAMBDA_ARN` contains no `ACCOUNT` placeholder — `grep "ACCOUNT" .env` returns nothing
- [ ] First dry_run discovery run completes Monday 09:00 ET with no `"error"` key
- [ ] 22 seed conventions exist in `sbia_conventions` before first run
- [ ] Dry-run report shows composed emails (not sent) — review tone, personalization, CAN-SPAM compliance
- [ ] HOT LEAD alert path verified: set test convention to `status=RESPONDED, intent=Interested` → Slack alert fires to `#hot-leads` immediately
- [ ] All 3 systemd timers active
- [ ] dry_run mode confirmed active for 14 days minimum — live_send NOT enabled

**Risk Callouts (top 3):**
1. `SBIA_FOLLOWUP_LAMBDA_ARN` placeholder = all 7-day follow-up emails fail silently; verify with grep before every step
2. EPK assets must all 6 exist before live email sends — missing asset = 403 error in every email
3. SES sandbox restriction blocks all outbound email at launch — request production access on Day 1 of the project

---

## Section 4 — The Cultural Moment Verification Test

**Run this test once Agents 06, 02, 03, 11, and 12 are all live and healthy.**

This is the cross-agent integration test that validates the Central Signal Chain. It is the most important integration test in the fleet.

### The Chain (from Operations Guide §IV)

| Timeline | What Happens |
|----------|--------------|
| **T+0:00 Agent 06 fires** | Convergence threshold crosses 0.80 (PEAK stage). Topic: "peace talks ceasefire". Catalog match: MoreLoveLessWar. Alert sent to all downstream agents simultaneously. Posts URGENT to `#cultural-moments`. |
| **T+0:01 Agent 02 activates** | Sync Brief Hunter immediately searches all platforms for any open brief matching the theme. If found: an URGENT <6-hour submission package is prepared. H.F. receives a HOT BRIEF alert within minutes. |
| **T+0:02 Agent 03 activates** | Sync Pitch Campaign identifies which supervisors are currently working on peace-related or social-justice-themed projects. Proactive pitch generated for MoreLoveLessWar to Jen Malone, Morgan Rhodes, and Fam Udeoqj simultaneously. Drafts queue for H.F. approval. |
| **T+0:05 Agent 11 activates** | Fan Discovery generates community outreach messages for r/nujabes and related communities. 3 variants per community, MoreLoveLessWar in the context of the moment, queued for H.F. approval. |
| **T+0:10 Agent 12 activates** | Social Media Director generates content for all 6 platforms: Instagram aesthetic hook, Twitter reflection, YouTube Community post, Discord message, Threads narrative. All queued in `#social-approvals` with URGENT flag. |
| **T+0:30 H.F. Slack digest** | Bundled notification appears: "Cultural Moment PEAK: Peace talks, MoreLoveLessWar activated across 4 agents. 23 items queued for your approval." One click per item to approve. |

### Step-by-Step Simulation

**Step 1 — Insert test record into `cultural-moments` table:**

```bash
aws dynamodb put-item \
  --table-name cultural-moments \
  --item '{
    "moment_id": {"S": "TEST-MOMENT-001"},
    "topic": {"S": "peace talks test"},
    "stage": {"S": "PEAK"},
    "confidence": {"N": "0.85"},
    "catalog_match": {"S": "MoreLoveLessWar"},
    "created_at": {"S": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
    "test_record": {"BOOL": true}
  }'
```

**Step 2 — Trigger Agent 06 manually to broadcast the signal:**

```bash
make run AGENT=06-cultural TASK=scan_trending
```

**Step 3 — Watch the chain activate (check each within its window):**

| Window | What to verify | Where to look |
|--------|---------------|---------------|
| T+0:00–0:01 | PEAK moment alert appears in `#cultural-moments` with URGENT flag | Slack `#cultural-moments` |
| T+0:01–0:05 | `#pending-approvals` receives TIER 1 brief search result from Agent 02 | Slack `#pending-approvals` |
| T+0:02–0:10 | Pitch draft variants for MoreLoveLessWar appear in `#pending-approvals` from Agent 03 | Slack `#pending-approvals` |
| T+0:05–0:15 | Fan outreach variants appear in `#fan-discovery-queue` from Agent 11 (or `#pending-approvals` for URGENT) | Slack |
| T+0:10–0:30 | Social content bundle with URGENT flag appears in `#social-approvals` from Agent 12 | Slack `#social-approvals` |
| T+0:30 | Bundled digest message shows all queued items | Slack `#cultural-moments` or `#pending-approvals` |

**Step 4 — Do NOT approve any items during the test.** This is a verification run only.

**Step 5 — Cleanup (immediately after test):**

```bash
aws dynamodb delete-item \
  --table-name cultural-moments \
  --key '{"moment_id": {"S": "TEST-MOMENT-001"}}'
```

Verify deletion: `aws dynamodb get-item --table-name cultural-moments --key '{"moment_id": {"S": "TEST-MOMENT-001"}}'` should return empty.

**Pass criteria:** All 5 agent responses arrive within their documented windows. No responses means the trigger signal is not propagating — check the Kinesis/DynamoDB stream connection between Agent 06 and downstream agents.

---

## Section 5 — Morning Workflow Acceptance Test

**The fleet is not deployed until H.F. can execute this workflow uninterrupted on a live morning.**

This is the operator-level acceptance test. Run it on the first business day after all 13 agents have been live for at least 24 hours. H.F. sits down at 7:00am and walks through every step.

*(From Lumin Agent Fleet Operations Guide §V — Your Daily Workflow)*

| Time | Check | Expected result | Pass? |
|------|-------|----------------|-------|
| **7:00am** | Open Slack `#pending-approvals` | Content drafts from Agent 12 present. Outreach messages from Agent 11 present (if applicable). Sync pitches from Agent 03 present (if weekly cycle ran). Any SBIA booking alerts present. Work through the list before moving to any other channel. | [ ] |
| **7:15am** | Check `#cultural-moments` | Has Agent 06 fired since yesterday? If a FORMING or PEAK moment is present: MoreLoveLessWar content queued must be approved within 2–4 hours — the window closes. If empty: note it as normal (not every day has a moment). | [ ] |
| **7:30am** | Check `#sync-queue` | New sync briefs from Agent 02. TIER 1 briefs (major streaming platform, >$5K fee, cultural relevance) need a decision today. DEADLINE CRITICAL means act now. If empty: no qualifying briefs found since last check — acceptable. | [ ] |
| **7:45am** | Check `#security-ops` | Alerts from Agent 10. **In normal operation this channel should be empty.** Any CRITICAL or HIGH alert requires immediate escalation to Eric — stop the morning workflow and call Eric now. | [ ] |
| **8:00am** | Check `#hot-leads` | Any booking inquiries from SBIA that received an interested response overnight? These are time-sensitive — convention response windows close. SBIA has the full response email and suggested next action ready. | [ ] |
| **8:15am** | Check `#fan-discovery-queue` | Agent 11's daily opportunity queue. 5–15 outreach messages each with 3 variants, community context, and approve/decline buttons. Select the ones that feel most authentic and appropriate today. | [ ] |

**Total time on a normal day:** 15–20 minutes. Longer if Agent 06 has fired a PEAK moment or SBIA has active HOT leads.

**The deployment is complete when H.F. checks all 6 boxes above on a real morning.**

If any step fails:
- No content in `#pending-approvals` → check Agent 12 timer, check approval webhook
- `#cultural-moments` completely silent for 5+ days → check Agent 06 30-minute timer
- `#sync-queue` silent for 2+ weeks → check Agent 02 4-hour timer and Chartmetric API
- Any content in `#security-ops` → escalate to Eric immediately regardless of severity label
- `#hot-leads` silent for 60+ days → review SBIA email quality (see SBIA audit §8, Risk #3)
- `#fan-discovery-queue` empty for 3+ days → check Reddit/TikTok API health (see Agent 11 audit §8)

---

## Section 6 — Troubleshooting Cookbook

### 1. `ANTHROPIC_API_KEY` not set on deployed agent

**Symptom:** Agent run returns `{"error": "ANTHROPIC_API_KEY not found"}` or `AuthenticationError` from the Anthropic SDK.

**Most likely cause:** The `.env` file was not created from `.env.example`, or the systemd service does not load the `.env` file. Systemd services do not inherit the shell environment — env vars must be explicitly passed.

**Fix:**
```bash
# Verify .env exists and has the key
grep ANTHROPIC_API_KEY /opt/lumin-agents/agents/agent-<N>/.env

# Check that the systemd service ExecStart loads the .env
cat /etc/systemd/system/lumin-agent-<N>-<task>.service | grep EnvironmentFile

# If missing, add to service unit:
# EnvironmentFile=/opt/lumin-agents/agents/agent-<N>/.env
# Then: systemctl daemon-reload && systemctl restart lumin-agent-<N>-<task>
```

---

### 2. Tests pass locally but fail on EC2 with "Table not found"

**Symptom:** `make test-agent AGENT=<N>` passes on local machine. On EC2, the same command throws `ResourceNotFoundException: Table not found`.

**Most likely cause:** Table name mismatch between `.env` var and the DynamoDB table actually created in AWS. Common causes: typo in table name during creation, wrong AWS region, or the table was created in a different account.

**Fix:**
```bash
# Check the table name in .env
grep _TABLE /opt/lumin-agents/agents/agent-<N>/.env

# List all DynamoDB tables in the correct region
aws dynamodb list-tables --region us-east-1 | grep <table-name>

# If names don't match: either recreate the table with the correct name
# or update the env var to match the actual table name
```

---

### 3. A scheduled run fires but the agent does nothing

**Symptom:** `systemctl list-timers` shows the timer triggered. CloudWatch Logs show the service started. But no DynamoDB records were written and no Slack message arrived.

**Most likely cause:** The agent ran but encountered a handled exception that returned a graceful error response (no crash, but no action). Or the task name passed to the runner doesn't match any task in the agent.

**Fix:**
```bash
# Read the full CloudWatch log for the run
make logs AGENT=<N>

# Look for lines like: {"status": "DRY_RUN"} or {"status": "SKIPPED"}
# or: {"error": "..."}

# If "DRY_RUN": webhook env var not set — the agent is running in dry-run mode
# If "SKIPPED": qualifying condition not met (e.g., no open briefs today — may be correct)
# If "error": read the error message for root cause

# Verify the task name matches the agent's available tasks
python /opt/lumin-agents/scripts/run_agent.py agent-<N> --list-tasks 2>/dev/null \
  || grep "@tool" /opt/lumin-agents/agents/agent-<N>/tools/*.py | head -20
```

---

### 4. Slack alerts not arriving

**Symptom:** Agent completes successfully (DynamoDB records written, no error in CloudWatch) but no message appears in the Slack channel.

**Most likely cause:** The `SLACK_*_WEBHOOK` env var is not set, is set to the wrong URL, or the webhook was revoked in Slack.

**Fix:**
```bash
# Confirm webhook env var is set
grep SLACK_ /opt/lumin-agents/agents/agent-<N>/.env

# Test the webhook directly
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Lumin webhook test"}' \
  $(grep SLACK_ /opt/lumin-agents/agents/agent-<N>/.env | head -1 | cut -d= -f2)

# If curl returns "ok": webhook works but agent isn't calling it correctly
# If curl returns "invalid_token": regenerate webhook in api.slack.com/apps
# If curl returns "channel_not_found": channel was renamed or deleted in Slack
```

---

### 5. `ImportError` on EC2

**Symptom:** Agent run exits immediately with `ImportError: No module named 'strands'` (or similar).

**Most likely cause:** The agent's virtual environment was not created, or the `make install` step was skipped. EC2's system Python does not have the required packages.

**Fix:**
```bash
# Re-run install for the agent
cd /opt/lumin-agents && make install AGENT=<N>

# Verify venv was created
ls agents/agent-<N>/venv/lib/python3.12/site-packages/strands 2>/dev/null

# If using systemd service, confirm ExecStart uses venv Python:
cat /etc/systemd/system/lumin-agent-<N>-<task>.service | grep ExecStart
# Should look like: ExecStart=/opt/lumin-agents/agents/agent-<N>/venv/bin/python ...
```

---

### 6. The runner can't find the agent module

**Symptom:** `make run AGENT=<N> TASK=<task>` exits with `ModuleNotFoundError: No module named 'agent'` or `FileNotFoundError: agents/agent-<N>/agent.py not found`.

**Most likely cause:** Wrong `AGENT=` value, or the `scripts/run_agent.py` working directory assumption doesn't match the actual repo layout.

**Fix:**
```bash
# Confirm the agent folder exists
ls /opt/lumin-agents/agents/ | grep <N>

# The AGENT= value must be the folder name WITHOUT the 'agent-' prefix:
# Folder: agents/agent-09-customer-success
# Correct: make run AGENT=09-customer-success TASK=daily_onboarding_scan
# Wrong:   make run AGENT=agent-09-customer-success TASK=...
# Wrong:   make run AGENT=09 TASK=...

# Always run make commands from the repo root
pwd  # Should be /opt/lumin-agents
```

---

## Section 7 — Rollback Procedures

### Stop a Specific Agent

```bash
# Disable and stop all timers for an agent
systemctl disable --now lumin-agent-<N>-*.timer
systemctl stop lumin-agent-<N>-*.service

# Verify it stopped
systemctl list-timers | grep lumin-agent-<N>
# Should show no entries
```

### Revert the Fleet to a Previous Git Tag

```bash
# On EC2, as lumin user:
cd /opt/lumin-agents

# List available tags
git tag --list

# Check out a specific tag (e.g., v0.3-audit-complete)
git checkout v0.3-audit-complete

# Re-install all active agents (repeat for each deployed agent)
make install AGENT=<N>
systemctl daemon-reload
make install-systemd AGENT=<N>
systemctl restart lumin-agent-<N>-*.timer

# To return to latest:
git checkout master && git pull
```

> **Caution:** Reverting code does not revert DynamoDB data. If the rollback is due to bad data writes, inspect the relevant tables manually before re-enabling the agent.

### Invoke the Kill Criteria (from DEPLOY_PLAN.md §7)

```bash
# --- PAUSE A SINGLE AGENT ---
systemctl disable --now lumin-agent-<N>-*.timer
# Do NOT delete DynamoDB records — they are the audit trail
# CloudWatch log is the root cause source — read last 24h before modifying anything
make logs AGENT=<N>

# --- FLEET-LEVEL PAUSE (all agents) ---
systemctl disable --now lumin-agent-*.timer
systemctl stop lumin-agent-*.service

# --- CHECK STATUS AFTER PAUSE ---
make status   # shows all lumin timers and their state
```

**Fleet-level kill criteria triggers (from DEPLOY_PLAN.md §7):**

| Condition | Immediate action |
|-----------|-----------------|
| Anthropic API spend >$200/mo for 2 consecutive weeks | Pause all agents |
| Any agent posts content publicly without H.F. approval | Pause Agents 11 and 12 immediately |
| AWS bill >$150/mo for 2 consecutive months | Audit Kinesis streams first |
| Agent 10 CRITICAL severity affecting fan data | Pause Agents 09, 11, 12; do not resume until Agent 10 confirms containment |

**Recovery protocol (always in this order):**
1. Pause the agent (disable timer)
2. Preserve state (do not delete DynamoDB records)
3. Root cause (read last 24h of CloudWatch logs)
4. Document (one paragraph in the agent's audit file)
5. Deliberate resume (modified configuration only — not the same one that caused the issue)

---

*Lumin Fleet — EC2 Deployment Runbook — Phase 3.7 — April 2026*  
*H.F. (CEO) · Eric (CTO)*  
*Win for the Artist · Win for the Fan · Win for the World*
