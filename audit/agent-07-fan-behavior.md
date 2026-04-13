# Deployment Readiness Audit — Agent 07: Fan Behavior Intelligence

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-07-fan-behavior` |
| Display name | Fan Behavior Intelligence Agent |
| Entity | 2StepsAboveTheStars LLC |
| Layer | Strategic Intelligence |
| Mission | Turn SkyBlew's 35K monthly listeners into a deeply understood fan ecosystem with CLV, churn prediction, and geographic intelligence feeding every other agent. |
| Schedule | Daily 07:00 UTC (metrics update) · Sundays 06:00 UTC (CLV update) · Monthly 1st 08:00 UTC (strategic report) · On-demand (app personalization) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

| File | Line | Placeholder | Required value |
|------|------|-------------|----------------|
| `.env.example` | 6 | `SKYBLEW_CM_ID=skyblew_chartmetric_artist_id` | Replace with SkyBlew's actual Chartmetric artist ID (numeric string) |

The `SKYBLEW_CM_ID` is used by Chartmetric streaming data pulls to identify SkyBlew's artist profile. Without the correct ID, all Chartmetric-based fan metrics return data for the wrong artist or fail entirely. This is the most critical pre-deploy step for Agent 07.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `fan-behavior-metrics` (`FES_TABLE`) | Fan Engagement Score (FES) time series by cohort | Yes |
| DynamoDB table | `fan-clv-model` (`CLV_TABLE`) | Customer Lifetime Value model by geographic and genre cohort | Yes |
| DynamoDB table | `fan-geographic-index` (`GEO_TABLE`) | Country-level geographic distribution of fan cohorts | Yes |
| DynamoDB table | `fan-genre-affinity` (`AFFI_TABLE`) | Genre affinity scores per cohort (lo-fi, anime, conscious hip-hop) | Yes |
| DynamoDB table | `skyblew-app-config` (`APP_CONFIG_TABLE`) | SkyBlew Universe App content carousel personalization config | Yes |
| S3 bucket | `lumin-fan-intelligence` (`S3_REPORTS_BUCKET`) | Weekly and monthly fan intelligence reports | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |
| Secrets Manager | `lumin/chartmetric-api-key` | Chartmetric streaming data API | No — shared with Agent 01 |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| Chartmetric | API key | `CHARTMETRIC_API_KEY` | `lumin/chartmetric-api-key` | chartmetric.com — paid subscription required | 1–2 days |

**Note:** Chartmetric is shared with Agent 01. If Agent 01's Chartmetric subscription is already provisioned, Agent 07 reuses the same secret. Obtain SkyBlew's specific Chartmetric artist ID from the Chartmetric dashboard after provisioning access.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `fan-clv-model` → **Agent 11 (Fan Discovery)** reads CLV by cohort to prioritize outreach targets (highest-CLV communities get first-priority discovery runs)
- `fan-genre-affinity` → **Agent 12 (Social Media Director)** uses genre affinity data to target content by community
- `fan-geographic-index` → **Agent 11** uses geo cohort data to identify emerging markets for outreach

**Reads from (produced by other agents):**
- `resonance-model-params` → **Agent 01** provides Boltzmann temperature and entropy signals that Agent 07 uses to calibrate CLV threshold sensitivity

**Signal flow:**
```
Agent 01 (Boltzmann temperature signal)
  → CLV threshold calibration → Agent 07 (fan behavior model)
    → fan-clv-model → Agent 11 (outreach prioritization)
    → fan-genre-affinity → Agent 12 (content targeting)
    → Slack #fan-intelligence (daily/weekly/monthly briefs)
    → S3 lumin-fan-intelligence (report archive)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — daily + weekly + monthly runs) | $0.90 |
| DynamoDB — 5 tables, on-demand (~200K R/W ops) | ~$0.30 |
| S3 — report storage (~500 MB/month) | ~$0.01 |
| CloudWatch Logs | ~$0.10 |
| **Estimated monthly total** | **~$1.31** |

**Cost note:** Chartmetric is a shared subscription cost already counted under Agent 01. Agent 07 adds no incremental Chartmetric spend — it uses the same API key and the same Chartmetric plan.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Provision Chartmetric API key (if not already provisioned for Agent 01) | 1–2 days |
| Obtain SkyBlew's Chartmetric artist ID and set `SKYBLEW_CM_ID` | < 1 day |
| Create DynamoDB tables (5 tables) | < 1 day |
| Create S3 bucket `lumin-fan-intelligence` | < 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **2–3 working days** |

**Blocking dependency:** `SKYBLEW_CM_ID` must be set correctly before any meaningful Chartmetric data is pulled.

---

## 8. Risk Callouts

1. **`SKYBLEW_CM_ID` placeholder is a silent failure mode.** If deployed with the placeholder value `skyblew_chartmetric_artist_id`, the agent will call Chartmetric with an invalid artist ID. Chartmetric may return an error or may return data for a different artist. The agent will then compute CLV, FES, and geo cohort models against wrong data. All downstream agents (11, 12) will receive poisoned targeting signals. Verify the artist ID before first run.

2. **`skyblew-app-config` table feeds the SkyBlew Universe App.** This table is written by Agent 07's `update_app_content_carousel()` tool. If the App is not yet live, writes will succeed but have no effect. Once the App launches, Agent 07's content updates become fan-visible. Coordinate App launch timing with Agent 07 deployment.

3. **Five DynamoDB tables — highest table count for a single agent.** Each table is small (~35K fan cohorts) but the 5-table footprint increases the risk of schema drift if tables are manually edited. Document the DynamoDB schema for each table before deploying, especially `fan-clv-model` which is read by Agent 11.

4. **Baseline data required for meaningful Day 1 output.** Agent 07's first run will produce CLV and FES scores with no historical baseline to compare against. The agent's value compounds over time — month-over-month comparisons require multiple runs. Set expectations with H.F. that the first 4 weeks are "model warming" and the strategic report becomes truly actionable around Week 6–8.

---

## 9. Deployment Checklist

- [ ] Provision Chartmetric API key (if not already done for Agent 01)
- [ ] Obtain SkyBlew's Chartmetric artist ID and set `SKYBLEW_CM_ID` in `.env`
- [ ] Create DynamoDB tables: `fan-behavior-metrics`, `fan-clv-model`, `fan-geographic-index`, `fan-genre-affinity`, `skyblew-app-config` (on-demand billing)
- [ ] Create S3 bucket `lumin-fan-intelligence` with versioning enabled
- [ ] Configure Slack webhook (`SLACK_FAN_WEBHOOK`) and verify test message posts
- [ ] Run `python scripts/run_agent.py agent-07-fan-behavior daily_metrics_update` and verify clean JSON response
- [ ] Confirm `fan-behavior-metrics` table receives at least one FES record after smoke test
- [ ] Deploy Agent 01 first — Agent 07 uses Agent 01's Boltzmann temperature signals for CLV calibration
- [ ] Install and enable systemd timers for daily (07:00 UTC), weekly (Sunday 06:00 UTC), and monthly (1st 08:00 UTC) runs
- [ ] Verify first weekly CLV run completes and writes `fan-clv-model` records that Agent 11 can read

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 07 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The churn risk list: any Core fan showing declining engagement is worth a personal touch. The geographic growth leaders — Japan and Philippines showing fastest growth right now. The conversion rate from Casual to Engaged: this is the most actionable lever for fan growth.**

### Canonical Slack Channel

Agent 07 posts daily/weekly/monthly reports via **S3 `lumin-fan-intelligence`** bucket and an associated Slack channel. The daily churn risk alert goes to `#pending-approvals` if Agent 07 drafts a proactive outreach message for H.F. review (via the Agent 09 connection — see §5 addition below). Weekly and monthly strategic reports are delivered to `#fan-intelligence` (async, not part of morning workflow).

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Daily FES score update + churn risk flags | Daily 07:00 UTC |
| Weekly CLV report by geographic cohort | Sundays 06:00 UTC |
| Monthly strategic fanbase report | 1st of month 08:00 UTC |
| On-demand app personalization update | Event-driven |

### First 48 Hours — Acceptance Criteria

- [ ] Daily 07:00 UTC metrics run completes within 30 minutes of schedule and logs to CloudWatch with no `"error"` key
- [ ] At least one FES record written to `fan-behavior-metrics` table after the first daily run
- [ ] `SKYBLEW_CM_ID` is confirmed correct — the daily run returns Chartmetric data for SkyBlew specifically (not a wrong artist or error)
- [ ] `fan-clv-model` table receives records after the first Sunday 06:00 UTC CLV run — Agent 11 is unblocked for community prioritization
- [ ] `fan-genre-affinity` table receives records — Agent 12 is unblocked for content calendar targeting
- [ ] S3 bucket `lumin-fan-intelligence` receives at least one report object within 48 hours
- [ ] systemd timers confirmed active for: daily (07:00 UTC), weekly Sunday (06:00 UTC), monthly 1st (08:00 UTC)

### Red Flags

- **`SKYBLEW_CM_ID` returns data for the wrong artist** — all CLV, FES, and geo cohort models are corrupted; downstream agents (11, 12) receive poisoned targeting signals. This is the highest-risk failure mode for this agent. Verify the artist ID before any downstream agent goes live.
- **`fan-clv-model` table is empty after the first weekly run** — Agent 11 has no community prioritization data; all outreach defaults to equal-weight targeting.
- **Japan and Philippines do not appear in the geographic growth leaders within the first month** — the Operations Guide specifically calls out these markets; if they're absent, verify that Chartmetric geo data is being pulled for the correct artist.
- **Core fan churn risk list is always empty** — the model may not be computing FES drops correctly; every fan cohort should show some variance in engagement scores.
- **Weekly CLV report does not arrive in `#fan-intelligence` on Sunday** — systemd timer for the Sunday run may have failed; check `journalctl`.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**ADDITION — not in original audit §5:**  
The Operations Guide Section VII interaction map documents **Agent 07 → Agent 09**: "Declining usage triggers proactive CS outreach." This connection was not present in the original audit §5 (which listed only Agents 11 and 12 as consumers of Agent 07's data). In the guide, when Agent 07 detects a declining-usage Core fan, it surfaces that signal to Agent 09 (AskLumin Customer Success), which drafts a proactive outreach message for H.F.'s approval. This integration is not yet in the current Agent 07 or Agent 09 code. It is a Phase 6 target.

Confirmed connections from Operations Guide (all also in audit §5):
- **Agent 01 → Agent 07**: market temperature data — confirmed ✓
- **Agent 07 → Agent 11**: CLV by cohort prioritizes outreach — confirmed ✓
- **Agent 07 → Agent 12**: genre affinity and geo-cohort personalizes content calendar — confirmed ✓
- **Agent 07 → Agent 09** [ADDITION]: declining usage triggers proactive CS outreach — NOT in audit §5; Phase 6 target
