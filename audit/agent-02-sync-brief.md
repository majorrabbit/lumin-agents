# Deployment Readiness Audit — Agent 02: Sync Brief Hunter

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-02-sync-brief` |
| Display name | Sync Brief Hunter |
| Entity | OPP Inc. |
| Layer | Revenue Operations |
| Mission | Monitor every sync brief platform every 4 hours, match OPP catalog to open briefs instantly, and prepare submission packages before deadline windows close. |
| Schedule | Every 4h (brief scan) · Daily (catalog match + deadline monitor) · Weekly digest |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py` or `tools/*.py`. The `.env.example` is clean — all values are either real defaults or clearly blank for the operator to fill in. No `ACCOUNT`, `TODO`, or `EXXXXXX` tokens found anywhere in the agent code.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `sync-briefs` (`BRIEFS_TABLE`) | Open sync briefs with deadline, platform, requirements | Yes |
| DynamoDB table | `opp-catalog` (`CATALOG_TABLE`) | OPP Inc. catalog with track metadata for matching | No — shared with Agent 8 |
| DynamoDB table | `sync-submissions` (`SUBS_TABLE`) | Submission packages sent to brief platforms | Yes |
| SES | verified sender `hello@lumin.luxe` | Submission confirmation emails + deadline alerts | No — shared sender identity |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| AWS SES | IAM role | `FROM_EMAIL=hello@lumin.luxe` | — | Verify `hello@lumin.luxe` sender identity in SES console; request production access if in sandbox | 1–2 days |
| Sync brief platforms | Web scraping / platform-specific | None (Claude + httpx web research) | — | No API key required — Agent 02 uses Claude to research platforms; no platform API tokens needed | — |

**Note:** Agent 02 does not use any third-party music data APIs. It relies on Claude's web-search capability via httpx to scan brief platforms. The main external dependency is SES sender identity verification.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `sync-briefs` table — **Agent 8 (A&R Catalog Growth)** reads brief rejection patterns to identify catalog gaps
- `opp-catalog` — Agent 02 reads this table and may update submission status fields; Agent 8 also reads it

**Reads from (produced by other agents):**
- `cultural-moments` table / cultural-signal-stream — **Agent 6 (Cultural Moment Detection)** triggers Agent 02 to scan for matching briefs when a cultural moment peaks. The trigger is a Kinesis or DynamoDB signal that tells Agent 02 "there is an open window — scan now."

**Signal flow:**
```
Agent 06 (Cultural Moment peak)
  → trigger → Agent 02 (brief scan against cultural moment)
    → sync-briefs → Agent 08 (catalog gap identification)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — 30% hit rate on 180 runs/month) | $1.62 |
| DynamoDB — 3 tables, on-demand (~250K R/W ops) | ~$0.38 |
| SES — submission emails (~30 emails/month) | ~$0.01 |
| CloudWatch Logs | ~$0.10 |
| **Estimated monthly total** | **~$2.10** |

**Cost optimization already in place:** 70% of Agent 02's scheduled runs exit early (no new briefs found) without calling Claude. Only 30% actually invoke the model, which is why the Claude cost is relatively low despite 4-hour cadence.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Verify SES sender identity (`hello@lumin.luxe`) | 1–2 days |
| Request SES production access (if in sandbox) | 1–3 days |
| Create DynamoDB tables (3 tables) | < 1 day |
| Seed `opp-catalog` with OPP catalog data | 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **3–5 working days** |

**Note:** The `opp-catalog` table must be pre-populated with OPP's music catalog before Agent 02 can make meaningful brief matches. This is likely the longest step if catalog data needs to be formatted and imported.

---

## 8. Risk Callouts

1. **`opp-catalog` is shared with Agent 8.** If both agents write to this table, a schema conflict or simultaneous write could corrupt catalog records. Review write patterns — Agent 02 should read-only from `opp-catalog`; only Agent 8 should write.

2. **No brief platform API credentials.** Agent 02 uses Claude + web scraping to monitor platforms. Platform-specific rate limiting or anti-scraping measures could break brief discovery silently. Monitor CloudWatch logs for 4xx / 429 responses.

3. **Submission deadline windows are time-sensitive.** If the 4-hour scan misses a brief that closes in < 4 hours, the opportunity is lost. Consider whether the cadence should tighten to 2h for certain A-tier platform checks.

4. **`HF_EMAIL` is hardcoded to `hf@lumin.luxe` in .env.example.** Confirm this is H.F.'s actual email before deployment; otherwise deadline alerts go nowhere.

---

## 9. Deployment Checklist

- [ ] Verify SES sender identity for `hello@lumin.luxe` in AWS SES console
- [ ] Request SES production access if account is in sandbox mode
- [ ] Create DynamoDB tables: `sync-briefs`, `opp-catalog`, `sync-submissions` (on-demand billing)
- [ ] Seed `opp-catalog` with OPP Inc. catalog data (title, ISRC, genre tags, one-stop clearance status)
- [ ] Set `HF_EMAIL` to H.F.'s real email address in `.env`
- [ ] Configure Slack webhook (`SLACK_SYNC_WEBHOOK`) and verify a test message posts
- [ ] Run `python scripts/run_agent.py agent-02-sync-brief brief_scan` and verify clean JSON response
- [ ] Install and enable systemd timer `lumin-agent-02-sync-brief-four-hour-scan.timer`
- [ ] Verify the first scheduled 4-hour run completes successfully and logs to CloudWatch

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 02 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**Tier 1 brief alerts (these need your action within 4 hours). The pending approval count for submission packages. Any brief with < 6 hours remaining flagged as DEADLINE CRITICAL.**

### Canonical Slack Channel

**`#sync-queue`** — H.F. checks at **7:30am** in the morning workflow. TIER 1 brief alerts (major streaming platform, >$5K fee, cultural relevance) appear here. DEADLINE CRITICAL warnings fire when a brief has < 6 hours remaining and have not yet received a submission. **`#pending-approvals`** receives submission package approval requests — H.F. selects approve or decline before any package is sent.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Brief scan log (CloudWatch) | Every 4 hours |
| TIER 1 brief alert to `#sync-queue` | Only when a qualifying brief is found — typically 0–5 per week |
| DEADLINE CRITICAL warning | Only when a brief has < 6 hours remaining |
| Submission package approval request in `#pending-approvals` | Each time a TIER 1 match is packaged |

If `#sync-queue` shows **no activity for 2+ weeks**, either no qualifying briefs exist on monitored platforms (possible during slow periods) or the scanning logic is failing silently.

### First 48 Hours — Acceptance Criteria

- [ ] First 4-hour scan runs within 4 hours of deployment and logs to CloudWatch with no `"error"` key
- [ ] A scan result (even "no briefs found today") posts to `#sync-queue` within 8 hours of deployment
- [ ] At least one `sync-briefs` table record exists after the first successful run
- [ ] **Approval gate verified**: manually inject a test TIER 1 brief event and confirm the submission package lands in `#pending-approvals` with approve/decline buttons — confirm it is NOT sent to any brief platform before H.F. approval
- [ ] systemd timer active for every-4-hour scan cadence (`systemctl list-timers | grep agent-02`)
- [ ] `opp-catalog` table is seeded and Agent 02 returns catalog matches in the smoke test response

### Red Flags

- **No briefs surfaced for 2 consecutive weeks** — verify platform scanning is not being rate-limited; check CloudWatch logs for 429 or connection errors from brief platforms.
- **A submission package is sent without H.F. approval** — this is architecturally blocked (BDI-O Obligation). If it happens anyway, pause Agent 02 immediately and audit `sync-submissions` table for unauthorized entries.
- **DEADLINE CRITICAL brief fires but H.F. sees it after the window closes** — verify Slack webhook is posting to `#sync-queue` in real time and H.F. has urgent-keyword notifications enabled for that channel.
- **Brief rejection rate consistently above 80%** — `opp-catalog` tags may not match brief category requirements; route to Agent 08 for catalog gap analysis.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

The Operations Guide interaction map (Section VII) confirms:
- **Agent 06 → Agent 02**: cultural moment signal triggers immediate brief scan — confirmed in audit §5 ✓
- **Agent 02 → Agent 08**: brief rejection patterns identify catalog gaps — confirmed in audit §5 ✓

No discrepancies between the Operations Guide and audit §5.
