# Deployment Readiness Audit — Agent 05: Royalty Reconciliation

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-05-royalty` |
| Display name | Royalty Reconciliation Agent |
| Entity | OPP Inc. |
| Layer | Revenue Operations |
| Mission | Every dollar owed to OPP artists gets collected. No discrepancy goes unnoticed. No statement goes unchecked. |
| Schedule | Monthly (statement reconciliation) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py`. The `.env.example` is clean — all values are either real defaults or clearly blank for the operator to fill in.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `opp-royalty-statements` (`ROYALTY_TABLE`) | PRO statement data, period totals, track-level breakdown | Yes |
| DynamoDB table | `opp-royalty-issues` (`ISSUES_TABLE`) | Flagged discrepancies requiring investigation | Yes |
| SES | verified sender `royalties@opp.pub` | Escalation emails to H.F. when discrepancies > $500 found | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| AWS SES | IAM role / verified identity | `FROM_EMAIL=royalties@opp.pub` | — | Verify `royalties@opp.pub` in SES console; request production access if in sandbox | 1–2 days |

**Note:** Agent 05 does not connect to ASCAP, BMI, SoundExchange, or MLC APIs directly. The current production code uses synthetic statement data representative of OPP's catalog. Real PRO portal integration is a future enhancement — at launch, H.F. manually imports statement data. The agent's value at launch is discrepancy analysis and flagging, not automated ingestion.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Royalty data remains within Agent 05's tables and is consumed by H.F. for review.

**Reads from (produced by other agents):**
- None direct. Agent 05 reads from its own DynamoDB tables and from synthetic/manually imported PRO statement data.

**Signal flow:**
```
PRO statement data (manual import or future API integration)
  → Agent 05 (reconciliation + discrepancy detection)
    → opp-royalty-issues → H.F. (escalation email via SES)
    → Slack #royalty-alerts (monthly summary)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — Batch API, once/month) | $0.02 |
| DynamoDB — 2 tables, on-demand (~20K R/W ops) | ~$0.03 |
| SES — escalation emails (~5 emails/month) | ~$0.01 |
| CloudWatch Logs | ~$0.02 |
| **Estimated monthly total** | **~$0.08** |

**Lowest Claude cost in the fleet.** Agent 05 runs once per month and uses the Batch API. The $0.02 Claude cost reflects a single monthly reconciliation run with minimal token usage.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Verify SES sender identity for `royalties@opp.pub` | 1–2 days |
| Request SES production access if in sandbox | 1–3 days |
| Create DynamoDB tables (2 tables) | < 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **2–4 working days** |

---

## 8. Risk Callouts

1. **No live PRO API integration at launch.** Agent 05's `fetch_pro_statements()` tool returns synthetic hardcoded statement data. H.F. must manually import real ASCAP, BMI, SoundExchange, and MLC statements into the `opp-royalty-statements` table before the reconciliation is meaningful. Until this seeding step happens, Agent 05 is running against test data.

2. **SES sender reputation for `royalties@opp.pub`.** This is a separate sender identity from `sync@opp.pub` (Agent 03) and `hello@lumin.luxe` (Agents 02 and 09). A third OPP sender identity requires its own SES verification and reputation warming. Verify all three sender identities are in the same SES account.

3. **MLC registration gap detection is critical.** The spec calls out MLC registration as the single most recoverable royalty loss — works not registered with the MLC generate zero mechanical royalties from US streaming. Ensure H.F. understands that Agent 05's MLC gap detection tool requires the `opp-catalog` table to be pre-populated with all OPP ISRCs before the first monthly run.

4. **Monthly cadence means late detection.** A royalty discrepancy that occurred in January may not be flagged until early February's monthly run. This is acceptable for the current scale but becomes an issue as catalog revenue grows. Monitor whether a bi-weekly run makes sense once LightSwitch streaming revenue compounds.

---

## 9. Deployment Checklist

- [ ] Verify SES sender identity for `royalties@opp.pub` in AWS SES console
- [ ] Request SES production access if account is in sandbox mode
- [ ] Create DynamoDB tables: `opp-royalty-statements`, `opp-royalty-issues` (on-demand billing)
- [ ] Seed `opp-royalty-statements` with H.F.'s most recent ASCAP, BMI, SoundExchange, and MLC statements
- [ ] Configure Slack webhook (`SLACK_ROYALTY_WEBHOOK`) and verify test message posts
- [ ] Run `python scripts/run_agent.py agent-05-royalty monthly_reconciliation` and verify clean JSON response
- [ ] Confirm at least one issue record is written to `opp-royalty-issues` table in smoke test
- [ ] Set up monthly trigger (1st of month) via EventBridge or systemd timer
- [ ] Verify first real-data monthly run detects any actual MLC registration gaps in the OPP catalog

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 05 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The Apple Music delivery status for MoreLoveLessWar — this must be resolved before any promotional campaign can be effective. The MLC unmatched works count — each unmatched work is missing mechanical royalties every day it remains unregistered. Any discrepancy over $100 requires your personal review.**

### Canonical Slack Channel

Agent 05 posts to `#pending-approvals` for discrepancies requiring H.F. action. The monthly reconciliation report is also delivered by **SES email from `royalties@opp.pub`** to H.F. directly. There is no dedicated high-frequency Slack channel for Agent 05 — it is a monthly agent and its outputs are email-first.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Monthly reconciliation report (SES email to H.F.) | First week of each month |
| Discrepancy escalation email (>$500 flags) | Only when a qualifying discrepancy is found |
| MLC registration gap alert | Any time an unregistered work is detected in the monthly run |
| Apple Music delivery status flag | Every monthly run until resolved |

Agent 05 is a **monthly agent** — no daily or weekly Slack presence is expected. If H.F. receives the monthly email, the agent is working.

### First 48 Hours — Acceptance Criteria

- [ ] Agent deploys and the smoke test run (`monthly_reconciliation`) completes with no `"error"` key in the JSON response
- [ ] At least one record written to `opp-royalty-issues` table in the smoke test (confirms discrepancy detection logic is live)
- [ ] SES email from `royalties@opp.pub` is received by H.F. after the smoke test reconciliation run
- [ ] systemd timer or EventBridge rule active for monthly trigger (1st of month)
- [ ] `opp-royalty-statements` table is seeded with at least one real PRO statement — smoke test against live data produces a meaningful (non-synthetic) output
- [ ] Apple Music delivery status for MoreLoveLessWar is flagged in the first report output (this is a standing CRITICAL flag until resolved)

### Red Flags

- **Monthly email from `royalties@opp.pub` does not arrive in the first week of the month** — agent failed to run; check EventBridge or systemd timer; check SES bounce logs.
- **MLC unmatched works count increases month-over-month** — new tracks are being added to the catalog without MLC registration; the gap is compounding daily.
- **Apple Music delivery status for MoreLoveLessWar still flagged after Month 2** — this is a business action item for H.F. to resolve with DistroKid, not an agent failure; but Agent 05 should keep surfacing it until the flag clears.
- **Any discrepancy >$500 not escalated to H.F.** — the SES escalation email should fire automatically; if H.F. sees the DynamoDB record but received no email, the SES sender identity (`royalties@opp.pub`) may have a delivery issue.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**ADDITION — not in original audit §5:**  
The Operations Guide Section VII interaction map documents **Agent 05 → Agent 08**: "Royalty performance data informs catalog equity." This connection was not present in the original audit §5 (which stated "Writes to: None"). This integration does not exist in the current Agent 05 code. It is planned for Phase 6 (Intelligence Network Activation).

Updated signal flow (Phase 6 target):
```
PRO statement data (manual import)
  → Agent 05 (reconciliation + discrepancy detection)
    → opp-royalty-issues → H.F. (escalation email)
    → [Phase 6] royalty performance data → Agent 08 (catalog equity analysis)
```
