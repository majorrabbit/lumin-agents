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
