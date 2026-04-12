# Lumin MAS — Agent Index

All 13 agent folders under `agents/`. Each is a vendored, byte-identical copy
of the original ZIP delivery. Do not edit these files directly — read
`docs/PATTERNS.md` for the integration conventions and `INTEGRATION_REPORT.md`
(Phase 2.2) for any compatibility notes.

Baseline integrity hashes: `audit/baseline-hashes.json`

---

## Fleet Overview

| # | Folder | Entity | Layer | Schedule | Lines | Purpose |
|---|--------|--------|-------|----------|-------|---------|
| 01 | `agent-01-resonance` | Lumin Luxe Inc. | Strategic Intelligence | Hourly / Daily 02:00 UTC / Sundays 04:00 UTC | 292 | Physics engine of the Lumin ecosystem — transforms streaming data into Boltzmann/entropy-based, investor-grade predictions via walk-forward Brier backtesting. |
| 02 | `agent-02-sync-brief` | OPP Inc. | Revenue Operations | Every 4h / Daily / Weekly | 183 | Monitors every sync brief platform every 4 hours, matches OPP catalog to open briefs instantly, and prepares submission packages before deadline windows close. |
| 03 | `agent-03-sync-pitch` | OPP Inc. | Revenue Operations | Weekly / Event-driven (Agent 6) | 437 | Builds and maintains proactive music supervisor relationships so OPP is pitching before briefs are issued — not reacting to them. |
| 04 | `agent-04-anime-gaming` | OPP Inc. + 2StepsAboveTheStars LLC | Revenue Operations | Weekly / Monthly | 353 | Monitors global anime production announcements and game audio briefs to find every sync opportunity where SkyBlew's Rhythm Escapism sound belongs. |
| 05 | `agent-05-royalty` | OPP Inc. | Revenue Operations | Monthly (1st of month) | 397 | Reconciles every royalty statement from PROs (ASCAP, BMI, SoundExchange), the MLC, and DSPs — every discrepancy flagged, every dollar collected. |
| 06 | `agent-06-cultural` | All Three | Fan Experience | Every 30 min | 431 | Detects cultural moments 2–4 hours before they peak using Shannon entropy convergence across Reddit, Twitter, TikTok, YouTube, and news — then triggers Agents 02, 03, 11, 12. |
| 07 | `agent-07-fan-behavior` | 2StepsAboveTheStars LLC | Strategic Intelligence | Daily 06:00 UTC / Sundays 05:00 UTC / Monthly 1st | 249 | Turns SkyBlew's 35K monthly listeners into a deeply understood fan ecosystem — CLV models, churn prediction, and geographic intelligence feeding every downstream agent. |
| 08 | `agent-08-ar-catalog` | OPP Inc. | Revenue Operations | Monthly (1st of month) | 640 | Reads demand signals from Agents 1, 2, 4, and 6 to identify sonic gaps in the OPP catalog, then scouts artists whose aesthetic matches the Rhythm Escapism vision. |
| 09 | `agent-09-customer-success` | Lumin Luxe Inc. | Fan Experience | Daily 08:00 / 09:00 UTC · Mon 09:00 UTC · Real-time | 350 | Ensures every AskLumin subscriber succeeds — runs onboarding, churn, and weekly digest sweeps, and handles real-time inbound support with per-user context injection. |
| 10 | `agent-10-cybersecurity` | Lumin Luxe Inc. (all three) | Meta / Security | Every 15m / Daily / Weekly | 309 | Monitors WAF block rates, active sessions, content integrity, GuardDuty findings, fraud signals, and compliance posture with a hard <60s SLA for critical alerts. |
| 11 | `agent-11-fan-discovery` | 2StepsAboveTheStars LLC | Fan Experience | Weekly / Event-driven (Agent 6) | 295 | Discovers communities on Reddit, TikTok, YouTube, and Discord that should know SkyBlew, drafts culturally authentic outreach, and routes every message to H.F. for approval before posting. |
| 12 | `agent-12-social-media` | 2StepsAboveTheStars LLC | Fan Experience | Every 15m / Daily / Event-driven | 524 | The Creative Resonance Architect — monitors mentions, schedules content, deploys cultural moments, and reports on six platforms; drafts everything, H.F. approves everything. |
| SBIA | `agent-sbia-booking` | 2StepsAboveTheStars LLC | Revenue Operations / Booking | Mon 09:00 ET / Daily 10:00 ET / Every 4h | 372 | Discovers every US anime and nerd-culture convention, researches booking contacts, sends personalized outreach via Mailgun, tracks the full pipeline in Airtable, and surfaces warm leads to H.F. |

---

## Entity Key

| Entity | Abbreviation | Focus |
|--------|-------------|-------|
| Lumin Luxe Inc. | Lumin Luxe | Technology platform and IP holding company |
| OPP Inc. | OPP | Music publishing with one-stop sync clearance |
| 2StepsAboveTheStars LLC | 2SATS | SkyBlew's artist company and catalog |
| All Three | — | Agent 06 serves the full ecosystem |

---

## Layer Key

| Layer | Agents | Description |
|-------|--------|-------------|
| Strategic Intelligence | 01, 07 | Generates market signals and predictive models |
| Revenue Operations | 02, 03, 04, 05, 08, SBIA | Converts intelligence into placements, royalties, bookings |
| Fan Experience | 06, 09, 11, 12 | Fan-facing — communities, subscribers, social media |
| Meta / Security | 10 | Fleet-wide infrastructure protection |

---

## Tool Inventory

| Agent | Tool Files | Style |
|-------|-----------|-------|
| 01 Resonance | `backtest_tools`, `data_tools`, `physics_tools`, `report_tools_resonance`, `trend_tools` | A — separate files |
| 02 Sync Brief | `alert_tools_sync`, `brief_tools`, `catalog_tools`, `submission_tools` | A — separate files |
| 03 Sync Pitch | *(all inline in agent.py)* | B — inline |
| 04 Anime Gaming | *(all inline in agent.py)* | B — inline |
| 05 Royalty | *(all inline in agent.py)* | B — inline |
| 06 Cultural | *(all inline in agent.py)* | B — inline |
| 07 Fan Behavior | `clv_tools`, `genre_tools`, `geo_tools`, `report_tools`, `streaming_tools` | A — separate files |
| 08 A&R Catalog | *(all inline in agent.py)* | B — inline |
| 09 Customer Success | `context_tools`, `metrics_tools`, `onboarding_tools`, `retention_tools`, `support_tools` | A — separate files |
| 10 CyberSecurity | `alert_tools`, `content_tools`, `fraud_tools`, `guardduty_tools`, `privacy_tools`, `session_tools`, `waf_tools` | A — separate files |
| 11 Fan Discovery | `discovery_tools`, `distribution_tools`, `outreach_tools`, `tracking_tools` | A — separate files |
| 12 Social Media | `analytics_tools`, `campaign_tools`, `content_tools`, `monitoring_tools`, `platform_tools`, `voice_tools` | A — separate files |
| SBIA Booking | `alert_tools`, `crm_tools`, `discovery_tools`, `outreach_tools` | A — separate files |

Style B agents (03, 04, 05, 06, 08) have an empty `tools/__init__.py` as a
Python package placeholder. All `@tool`-decorated functions live in `agent.py`.

---

## Inter-Agent Signal Flows

```
Agent 01 (Resonance)
  └─> Agent 07 (entropy / temperature signal for fan behavior modeling)

Agent 06 (Cultural Moment)
  ├─> Agent 02 (sync brief — cultural moment pitch window open)
  ├─> Agent 03 (sync pitch — cultural moment supervisor outreach)
  ├─> Agent 11 (fan discovery — cultural moment community outreach)
  └─> Agent 12 (social media — cultural moment content deployment)

Agent 07 (Fan Behavior)
  ├─> Agent 11 (UTM conversion data for outreach targeting)
  └─> Agent 12 (genre affinity + geo cohort data for content strategy)

Agent 09 (Customer Success)
  └─> Lumin meta subscription data (monthly metrics report to H.F.)
```

---

## Dispatch Key Reference

| Agent | Dispatch Key | Default Task |
|-------|-------------|-------------|
| 01 through 12 | `event["task"]` | varies per agent |
| SBIA | `event["trigger_type"]` | `DISCOVERY_RUN` |

The fleet runner (`scripts/run_agent.py`) sets BOTH `task` and `trigger_type`
in every event, making it compatible with all dispatch patterns fleet-wide.

---

*Phase 2.1 ingestion — April 2026. Integrity baseline: `audit/baseline-hashes.json`.*
