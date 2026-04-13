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

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 03 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The pitch calendar: which supervisors are overdue for contact. The response tracking: any supervisor who replied (even a pass) represents a relationship warming. Watch particularly for Joel C. High — the Tyler Perry Studios pipeline depends on that relationship.**

### Canonical Slack Channel

**`#pending-approvals`** — every pitch email variant (3 options: precise, warm, expansive) routes here for H.F. selection before any send. H.F. checks at **7:00am** in the morning workflow. **`#sync-pitches`** receives weekly pitch cycle summaries and monthly relationship status reports.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Weekly pitch cycle — 3 email variants per due supervisor to `#pending-approvals` | Every Monday |
| Weekly pitch summary to `#sync-pitches` | Every Monday |
| Follow-up prompt (7 days after unanswered pitch) | 7 days post-send |
| Monthly pitch relationship history report | First week of each month |
| Cultural moment event-driven pitch (Agent 06 trigger) | When Agent 06 fires a PEAK signal for a relevant topic |

### First 48 Hours — Acceptance Criteria

- [ ] First Monday pitch cycle runs and logs to CloudWatch with no `"error"` key
- [ ] **Approval gate verified**: 3 pitch email variants (precise, warm, expansive) appear in `#pending-approvals` for each due supervisor — none sent until H.F. selects one
- [ ] `sync-supervisors` table receives relationship records after first run
- [ ] `sync-pitches` table receives draft records tied to each queued email
- [ ] Weekly summary posts to `#sync-pitches` after the cycle completes
- [ ] **Joel C. High (Tyler Perry Studios) appears in the first pitch cycle** — this is the highest-priority relationship; his absence from the first queue is a red flag
- [ ] Test cultural moment path: inject a mock Agent 06 signal and verify pitch variants are queued in `#pending-approvals` but not sent

### Red Flags

- **A pitch email is sent to a supervisor without H.F. selection** — this is a BDI-O Obligation violation. Pause Agent 03 immediately; audit `sync-pitches` table for unauthorized `status=SENT` records.
- **Joel C. High receives no outreach within 14 days of deployment** — the Tyler Perry Studios pipeline is gated on this relationship; it is the single most important supervisor contact in the queue.
- **0% supervisor response rate after 4 weeks** — check whether `sync@opp.pub` has an SES reputation issue; verify pitch emails are reaching inboxes, not spam folders.
- **Batch API result arrives after the cultural moment window closes** — Agent 03 uses Batch API (15–30 min delay); if an Agent 06 PEAK signal fires with a 2-hour window, verify the batch result is returned before the window closes.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

The Operations Guide interaction map (Section VII) confirms:
- **Agent 06 → Agent 03**: cultural moment signal triggers proactive supervisor pitch — confirmed in audit §5 ✓
- **Agent 03 → Agent 08**: pitch outcome data (acceptance/rejection patterns) feeds Agent 08's A&R synthesis — confirmed in audit §5 ✓

No discrepancies between the Operations Guide and audit §5.
