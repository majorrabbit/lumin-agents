# Deployment Readiness Audit — Agent 03: Sync Pitch Campaign

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-03-sync-pitch` |
| Display name | Sync Pitch Campaign Agent |
| Entity | OPP Inc. |
| Layer | Revenue Operations |
| Mission | Build and maintain proactive music supervisor relationships so OPP is pitching before briefs are issued — not reacting to them. |
| Schedule | Weekly (Monday pitch cycle) · Event-driven (Agent 6 cultural moment trigger) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py`. All tool functions are defined inline (Style B). The `.env.example` is clean.

**One operational note:** The `SUPERVISOR_DATABASE` list in `agent.py` (lines ~22–49) contains hardcoded music supervisor contact data (emails, companies, credits). These are real-world contacts whose details may change. Before going live, verify all 6 supervisor entries are current and that emails are accurate.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `sync-supervisors` (`SUPERVISORS_TABLE`) | Music supervisor relationship CRM and pitch history | Yes |
| DynamoDB table | `sync-pitches` (`PITCHES_TABLE`) | Outbound pitch records, status, response tracking | Yes |
| SES | verified sender `sync@opp.pub` | Personalized pitch emails to music supervisors | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| AWS SES | IAM role / verified identity | `FROM_EMAIL=sync@opp.pub` | — | Verify `sync@opp.pub` in SES console; request production access | 1–2 days |

**Note:** Agent 03 does not call any third-party music data APIs. Its intelligence comes from the hardcoded supervisor database and Claude's synthesis of cultural moment data passed via the event payload. The only credential requirement beyond Anthropic is SES sender verification.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `sync-pitches` table — brief acceptance/rejection data is referenced by **Agent 8 (A&R Catalog Growth)** to identify gaps in the OPP catalog based on what supervisors are requesting

**Reads from (produced by other agents):**
- **Agent 6 (Cultural Moment Detection)** triggers Agent 03 with a cultural moment signal, telling it which supervisors to contact for proactive pitches timed to the moment
- The trigger arrives via the event payload: `{"task": "weekly_pitch_cycle", "cultural_moment": {...}}`

**Signal flow:**
```
Agent 06 (Cultural Moment peak)
  → event trigger → Agent 03 (pitch supervisor matching the moment)
    → sync-pitches → Agent 08 (catalog gap inference)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — Batch API, weekly runs) | $0.66 |
| DynamoDB — 2 tables, on-demand (~100K R/W ops) | ~$0.15 |
| SES — weekly pitch emails (~20 emails/month) | ~$0.01 |
| CloudWatch Logs | ~$0.05 |
| **Estimated monthly total** | **~$0.90** |

**Batch API optimization:** Agent 03 uses the Anthropic Batch API for pitch generation (50% cost reduction). This is why the Claude cost is low despite Sonnet being used for nuanced supervisor relationship writing.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Verify SES sender identity for `sync@opp.pub` | 1–2 days |
| Request SES production access if in sandbox | 1–3 days |
| Create DynamoDB tables (2 tables) | < 1 day |
| Verify supervisor contact database is current | 1 day |
| Deploy and run smoke test | ½ day |
| **Total realistic TTL** | **3–5 working days** |

---

## 8. Risk Callouts

1. **Hardcoded supervisor contacts are a data maintenance risk.** The 6 supervisors in `SUPERVISOR_DATABASE` (lines 22–49) have hardcoded emails, companies, and credits. Music supervisors change companies. Before go-live and periodically thereafter, verify these contacts. A pitch to a stale email address damages OPP's reputation.

2. **SES cold-sending reputation.** `sync@opp.pub` is a new sender identity. SES starts with conservative daily limits. Warm up sending reputation before running the first full pitch cycle — send test emails to known-good addresses and monitor bounce/complaint rates.

3. **Agent 03 uses the Batch API**, which means pitch results may not be available for 15–30 minutes. This is acceptable for the weekly cycle but may be surprising if a cultural moment trigger arrives during a batch run. Verify the batch API timeout doesn't block a time-sensitive cultural moment pitch.

4. **No opt-out mechanism.** Agent 03 sends emails to real music industry contacts. If a supervisor requests removal from OPP's outreach list, this must be handled manually by H.F. — there is no automated unsubscribe mechanism in the current code.

---

## 9. Deployment Checklist

- [ ] Verify SES sender identity for `sync@opp.pub` in AWS SES console
- [ ] Request SES production access if account is in sandbox mode
- [ ] Create DynamoDB tables: `sync-supervisors`, `sync-pitches` (on-demand billing)
- [ ] Verify all 6 supervisor entries in `SUPERVISOR_DATABASE` have current email addresses
- [ ] Configure Slack webhook (`SLACK_PITCH_WEBHOOK`) and test notification
- [ ] Run `python scripts/run_agent.py agent-03-sync-pitch weekly_pitch_cycle` and verify clean JSON response
- [ ] Send warm-up test emails via SES before first live pitch run
- [ ] Install and enable systemd timer for weekly Monday pitch cycle
- [ ] Verify the first scheduled weekly run completes and posts a summary to Slack
