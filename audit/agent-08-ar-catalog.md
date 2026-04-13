# Deployment Readiness Audit — Agent 08: A&R & Catalog Growth

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-08-ar-catalog` |
| Display name | A&R & Catalog Growth Agent |
| Entity | OPP Inc. |
| Layer | Revenue Operations |
| Mission | Identify gaps in the OPP catalog that sync briefs keep requesting and can't be filled; find artists whose aesthetic lives in the Rhythm Escapism™ DNA; maintain catalog performance equity. |
| Schedule | Monthly (catalog gap analysis + A&R target review) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py`. The `.env.example` is clean.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `opp-catalog` (`CATALOG_TABLE`) | OPP Inc. full catalog with track metadata, ISRC, sync status | No — shared with Agent 02 |
| DynamoDB table | `opp-catalog-gaps` (`GAPS_TABLE`) | Catalog gap analysis: sonic categories that briefs request but OPP cannot fill | Yes |
| DynamoDB table | `opp-ar-targets` (`TARGETS_TABLE`) | A&R target artist profiles under consideration for OPP signing/licensing | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |

**Note:** Agent 08 does not call any external music discovery APIs directly at launch. It reads sync brief rejection data from `sync-briefs` (Agent 02's table) and OPP catalog data from `opp-catalog` to perform gap analysis. The A&R target discovery uses Claude synthesis — no third-party API credentials required.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Agent 08's `opp-catalog-gaps` and `opp-ar-targets` tables feed H.F.'s strategic A&R decisions — not other agents.

**Reads from (produced by other agents):**
- `sync-briefs` table → **Agent 02 (Sync Brief Hunter)** writes brief rejection patterns; Agent 08 reads these to infer what sonic categories OPP is failing to fill
- `sync-pitches` table → **Agent 03 (Sync Pitch Campaign)** writes brief acceptance/rejection data; Agent 08 reads these for supervisor preference signals
- `opp-catalog` → shared table populated by H.F. and read by both Agent 02 and Agent 08

**Signal flow:**
```
Agent 02 (brief rejections) + Agent 03 (pitch outcomes)
  → sync-briefs + sync-pitches → Agent 08 (catalog gap inference)
    → opp-catalog-gaps → H.F. (A&R decisions)
    → opp-ar-targets → H.F. (signing/licensing pipeline)
```

**Dependency note:** Agent 08 is the most downstream agent in the Revenue Operations tier. It should be deployed after Agents 02 and 03 are live and have accumulated at least one month of brief/pitch data for meaningful gap analysis.

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — Batch API, once/month) | $0.09 |
| DynamoDB — 3 tables, on-demand (~30K R/W ops) | ~$0.05 |
| CloudWatch Logs | ~$0.02 |
| **Estimated monthly total** | **~$0.16** |

**Cost profile:** Agent 08 is the second-lowest-cost agent in the fleet. It runs once per month, uses Batch API, and performs read-heavy analysis against existing tables — no external API calls or email sends.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Create DynamoDB tables (2 owned tables) | < 1 day |
| Verify `opp-catalog` table exists (owned by Agent 02) | Dependency on Agent 02 |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **1 working day** (after Agent 02 is live) |

---

## 8. Risk Callouts

1. **`opp-catalog` write conflict with Agent 02.** Both agents reference `opp-catalog`. Agent 02's audit (§8) notes that Agent 02 should be read-only from `opp-catalog` — only Agent 08 should write to it. Verify write permissions in the IAM role: Agent 02's role should have read-only access to `opp-catalog`; Agent 08 should have read-write. Enforce this at the IAM layer before deployment.

2. **Elvin Ross / Ronnie Garrett catalog integration.** The system prompt specifically calls out the "Elvin Ross / Ronnie Garrett catalog integration status — the binding constraint for OPP's sync business today." Agent 08 tracks this integration progress. Before first run, H.F. should seed the `opp-catalog` table with the current status of this catalog integration so Agent 08's gap analysis is accurate.

3. **Monthly cadence means slow feedback loop.** A&R insights generated in Month 1 inform signing decisions in Month 2 at the earliest. Brief rejection patterns from Agent 02 need at least 2–3 months of data before Agent 08's gap analysis is statistically meaningful. Set expectations with H.F. that Month 1's report is a baseline, not an actionable signal.

4. **No external A&R discovery API.** Agent 08 uses Claude synthesis for A&R target discovery — it cannot connect to Spotify's artist database, SoundCloud, or music discovery platforms. Its A&R target identification is based on Claude's knowledge of the Nujabes/conscious hip-hop ecosystem. External platform data integration is a Phase 4 enhancement.

---

## 9. Deployment Checklist

- [ ] Create DynamoDB tables: `opp-catalog-gaps`, `opp-ar-targets` (on-demand billing)
- [ ] Verify `opp-catalog` table exists (created by Agent 02) and contains OPP catalog data
- [ ] Set IAM permissions: Agent 08 read-write on `opp-catalog`; Agent 02 read-only on `opp-catalog`
- [ ] Seed `opp-catalog` with Elvin Ross / Ronnie Garrett catalog integration status
- [ ] Configure Slack webhook (`SLACK_AR_WEBHOOK`) and verify test message posts
- [ ] Deploy Agents 02 and 03 first — Agent 08 reads their output tables
- [ ] Run `python scripts/run_agent.py agent-08-ar-catalog monthly_catalog_review` and verify clean JSON response
- [ ] Verify `opp-catalog-gaps` receives at least one gap record in the smoke test
- [ ] Set up monthly trigger (1st of month) via EventBridge or systemd timer

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 08 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The Elvin Ross agreement status — it should be SIGNED, not PENDING. The RE™ DNA filter scores for any artist under consideration. The passive licensing action list — YouTube Content ID and Musicbed/Artlist registration for OPP instrumentals is pure revenue waiting to be collected.**

### Canonical Slack Channel

Agent 08 delivers its monthly A&R strategy report via **SES email** to H.F. and posts a summary to `#ar-catalog` (async — not part of the morning workflow). On-demand artist scoring results post immediately to `#ar-catalog`.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Monthly A&R strategy report (SES email + `#ar-catalog` summary) | First week of each month |
| Quarterly gap analysis report | Every 3 months |
| On-demand artist RE™ DNA score | When H.F. requests a specific artist evaluation |

Agent 08 is a **monthly agent**. H.F. should expect one substantial deliverable per month — a ranked gap report, emerging artist candidates, catalog performance equity analysis, and a 6-month priority action list.

### First 48 Hours — Acceptance Criteria

- [ ] Smoke test (`monthly_catalog_review`) runs and completes with no `"error"` key in CloudWatch
- [ ] At least one record written to `opp-catalog-gaps` table after the smoke test
- [ ] `opp-catalog` table is seeded and Agent 08 can read brief rejection patterns from `sync-briefs` (Agent 02's table)
- [ ] Elvin Ross / Ronnie Garrett catalog integration status is seeded in `opp-catalog` table before first run (this is the spec's binding constraint)
- [ ] On-demand artist scoring works: run a test artist through the RE™ DNA filter and verify a score is returned to `#ar-catalog`
- [ ] systemd timer or EventBridge rule active for monthly trigger

### Red Flags

- **Elvin Ross / Ronnie Garrett agreement still shows PENDING after 60 days** — the Operations Guide calls this out as the #1 status item to watch; it unlocks the cinematic instrumental gap (OPP's most-requested brief type). This is a business action item for H.F., not an agent failure.
- **Monthly report shows the same catalog gaps for 3 consecutive months with no new A&R targets** — either no new briefs are coming in (Agent 02 data is stale) or the Claude synthesis is not finding new artists; review system prompt for A&R discovery criteria.
- **YouTube Content ID and Musicbed/Artlist registration action list has been on the report for 2+ months** — the Operations Guide calls this "pure revenue waiting to be collected." These are passive licensing registrations, not complex decisions; escalate to H.F. as an immediate action item.
- **`opp-catalog-gaps` table remains empty after 2 months** — `sync-briefs` or `sync-pitches` tables may be empty (Agents 02/03 not writing); investigate upstream data sources.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**TWO ADDITIONS — not in original audit §5:**  
The Operations Guide Section VII interaction map documents two inputs to Agent 08 that were not in the original audit:

1. **Agent 04 → Agent 08**: "Anime/gaming demand signals feed catalog gap analysis." Original audit §5 listed only Agents 02 and 03 as data sources for Agent 08. Agent 04's demand signals are not yet in the current code — Phase 6 target.

2. **Agent 05 → Agent 08**: "Royalty performance data informs catalog equity." Original audit §5 did not list Agent 05 as a source. The royalty performance connection is not yet in the current code — Phase 6 target.

Updated signal flow (Phase 6 target additions in brackets):
```
Agent 02 (brief rejections) + Agent 03 (pitch outcomes)
  [+ Agent 04 (anime/gaming demand)] [+ Agent 05 (royalty performance)]
  → Agent 08 (catalog gap inference)
    → opp-catalog-gaps → H.F. (A&R decisions)
    → opp-ar-targets → H.F. (signing/licensing pipeline)
```
