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
