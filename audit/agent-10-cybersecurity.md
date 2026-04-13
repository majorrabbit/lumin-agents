# Deployment Readiness Audit — Agent 10: CyberSecurity

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-10-cybersecurity` |
| Display name | CyberSecurity Agent |
| Entity | Lumin Luxe Inc. |
| Layer | Meta (fleet-wide infrastructure protection) |
| Mission | Protect every layer of the SkyBlew Universe App and all three Lumin entities — Lumin Luxe, OPP Inc., and 2SATS — while keeping security invisible to fans. |
| Schedule | Every 15 min (session integrity) · Daily 02:00 UTC (content integrity) · Daily 08:00 UTC (GuardDuty digest) · Sundays 03:00 UTC (streaming fraud scan) · Event-driven (GDPR requests) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

Agent 10 has the **highest placeholder count in the fleet** — 5 hardcoded values across 3 tool files and 2 env vars that will cause runtime failures if not replaced.

| File | Line | Placeholder | Required value |
|------|------|-------------|----------------|
| `tools/waf_tools.py` | 15 | `WAF_ACL_ID = "LUMIN-WAF-ACL-ID"` | Replace with actual WAF ACL ID from AWS WAF console |
| `tools/waf_tools.py` | ~97 | WAF ACL ARN `arn:aws:wafv2:us-east-1:ACCOUNT:global/webacl/...` | Replace `ACCOUNT` with 12-digit AWS account ID |
| `tools/content_tools.py` | 15 | `CF_DISTRIBUTION_ID = "EXXXXXXXXXXXXXX"` | Replace with actual CloudFront distribution ID |
| `tools/guardduty_tools.py` | 13 | `DETECTOR_ID = "LUMIN-GUARDDUTY-DETECTOR-ID"` | Replace with actual GuardDuty detector ID (`aws guardduty list-detectors`) |
| `.env.example` | 15 | `SNS_SECURITY_TOPIC=arn:aws:sns:us-east-1:ACCOUNT:lumin-security-alerts` | Replace `ACCOUNT` with 12-digit AWS account ID |
| `.env.example` | 16 | `SNS_CRITICAL_TOPIC=arn:aws:sns:us-east-1:ACCOUNT:lumin-critical-page` | Replace `ACCOUNT` with 12-digit AWS account ID |

**Impact of unresolved placeholders:**
- `WAF_ACL_ID` left as `"LUMIN-WAF-ACL-ID"`: `check_waf_block_rate()` and `update_waf_ip_blocklist()` will fail with AWS API errors — the primary edge defense monitoring goes silent
- `CF_DISTRIBUTION_ID` left as `"EXXXXXXXXXXXXXX"`: `invalidate_cloudfront_cache()` will call CloudFront with an invalid distribution ID — cache invalidation on tamper detection fails
- `DETECTOR_ID` left as `"LUMIN-GUARDDUTY-DETECTOR-ID"`: all GuardDuty calls fail — threat intelligence goes blind

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `skyblew-sessions` (`SESSIONS_TABLE`) | Active user sessions for anomaly detection | No — shared with SkyBlew Universe App |
| DynamoDB table | `security-asset-hashes` (`ASSET_HASHES_TABLE`) | SHA-256 baseline hashes for protected app assets | Yes |
| DynamoDB table | `security-events` (`SECURITY_EVENTS_TABLE`) | All security events log | Yes |
| DynamoDB table | `security-alerts` (`SECURITY_ALERTS_TABLE`) | GuardDuty findings and alert records | Yes |
| DynamoDB table | `security-fraud-reports` (`FRAUD_REPORTS_TABLE`) | Streaming fraud analysis reports | Yes |
| AWS WAF v2 | `SkyBlewWAF` (CLOUDFRONT scope) | Edge defense — block malicious traffic before reaching app | No — pre-existing infrastructure |
| CloudFront distribution | `EXXXXXXXXXXXXXX` | CDN for SkyBlew Universe App assets | No — pre-existing infrastructure |
| AWS GuardDuty | Detector ID required | Threat intelligence — account-level findings | No — account-wide service |
| SNS topic | `lumin-security-alerts` (`SNS_SECURITY_TOPIC`) | Medium/High severity alerts to Slack and H.F. | Yes |
| SNS topic | `lumin-critical-page` (`SNS_CRITICAL_TOPIC`) | Critical severity page to Eric directly | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |
| Secrets Manager | `lumin/chartmetric-api-key` | Chartmetric for streaming anomaly detection | No — shared with Agents 01, 07 |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| Chartmetric | API key | `CHARTMETRIC_API_KEY` | `lumin/chartmetric-api-key` | chartmetric.com — paid subscription (shared with Agents 01, 07) | 1–2 days |
| AWS WAF v2 | IAM role | `CF_DISTRIBUTION_ID` env var | — | Retrieve from AWS WAF console; ensure WAF is attached to the CloudFront distribution | < 1 day |
| AWS GuardDuty | IAM role | — | — | Enable GuardDuty in us-east-1 via AWS console; retrieve detector ID via `aws guardduty list-detectors` | < 1 day |

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Agent 10 is a monitoring/protection agent. Its outputs (security events, alerts) go to H.F., Eric, and Slack — not to other agents.

**Reads from (produced by other agents):**
- Agent 10 monitors the `skyblew-sessions` table written by the SkyBlew Universe App backend (not an agent).
- The GDPR deletion task (`handle_gdpr_request`) reads across **multiple agents' DynamoDB tables**: `skyblew-sessions`, `fan-behavior-metrics` (Agent 07), `ask-lumin-cs-tickets` (Agent 09), and `ask-lumin-onboarding` (Agent 09). This gives Agent 10 the broadest read scope in the fleet.

**Signal flow:**
```
AWS WAF logs + GuardDuty + session table + CloudFront + Chartmetric streaming data
  → Agent 10 (threat analysis + fraud detection)
    → security-events + security-alerts → compliance archive
    → SNS lumin-security-alerts → H.F. / Eric (medium/high severity)
    → SNS lumin-critical-page → Eric (critical severity — page immediately)
    → Slack #security-alerts (real-time alerts)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — every-15min session scan + daily tasks) | $1.06 |
| DynamoDB — 4 owned tables + cross-agent reads (~200K R/W ops) | ~$0.30 |
| SNS — two topics, security alerts (~50 notifications/month) | ~$0.01 |
| GuardDuty — 30 days at minimal finding volume | ~$1.00 |
| CloudWatch Logs — security event log volume | ~$0.20 |
| **Estimated monthly total** | **~$2.57** |

**GuardDuty cost note:** GuardDuty billing is based on the volume of analyzed data (VPC Flow Logs, DNS logs, CloudTrail events). For a small-scale infrastructure, $1.00/month is a conservative estimate. Actual cost depends on account-wide data volume.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| **Replace all 5 code/env placeholders** (WAF ACL ID, CF dist ID, GuardDuty detector ID, 2 SNS ARNs) | ½ day |
| Enable AWS GuardDuty if not already active | < 1 day |
| Verify WAF ACL is attached to CloudFront distribution | < 1 day |
| Seed `security-asset-hashes` with SHA-256 hashes of all 5 protected assets | ½ day |
| Create DynamoDB tables (4 owned tables) | < 1 day |
| Create SNS topics (2 topics) and subscribe H.F. + Eric | < 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **2–3 working days** |

---

## 8. Risk Callouts

1. **Five unresolved placeholders — highest risk in the fleet.** All 5 must be replaced before deployment. Running with any placeholder creates a silent monitoring gap: WAF block rates go unmeasured, CloudFront cache invalidation fails on tamper detection, GuardDuty findings are never retrieved. The agent will appear to run successfully (no crash) but protection layer 1, 4, and 6 will be non-functional.

2. **Every-15-minute session scan at $1.06/month.** The hourly cadence of Agent 01 and 30-minute cadence of Agent 06 are expensive relative to their output value. Agent 10's 15-minute cadence is justified by its <60-second SLA for critical security response — this is one of only two agents (along with Agent 10's planned sub-MAS in Phase 5) where the fast cadence is architecturally required.

3. **GDPR deletion reads across four agents' tables.** `handle_gdpr_request()` must delete user data from `skyblew-sessions`, `fan-behavior-metrics`, `ask-lumin-cs-tickets`, and `ask-lumin-onboarding`. This requires Agent 10's IAM role to have delete permissions on tables owned by Agents 07 and 09. This is the broadest IAM permission grant in the fleet — review carefully and document the cross-agent delete permission explicitly.

4. **`security-asset-hashes` must be seeded before first content integrity run.** The daily content integrity check (`verify_asset_integrity`) compares current asset hashes against stored baselines. If the table is empty on Day 1, every asset will appear "tampered" (no stored baseline to compare against). Seed the table with current SHA-256 hashes of all 5 protected assets immediately after deployment.

5. **Phase 5 will replace this agent with a 6-agent sub-MAS.** The current Agent 10 is the single-agent version of what Phase 5 will expand into Agent 10A-10F (WAF, Session, Content, GuardDuty, Fraud, Compliance) plus a coordinator. Deploy the current Agent 10 as a functional placeholder — understand that its architecture will be replaced in Phase 5.

---

## 9. Deployment Checklist

- [ ] Replace `WAF_ACL_ID = "LUMIN-WAF-ACL-ID"` in `tools/waf_tools.py:15` with actual WAF ACL ID
- [ ] Replace WAF ACL ARN `ACCOUNT` placeholder in `tools/waf_tools.py` (~line 97) with AWS account ID
- [ ] Replace `CF_DISTRIBUTION_ID = "EXXXXXXXXXXXXXX"` in `tools/content_tools.py:15` with actual CloudFront distribution ID
- [ ] Replace `DETECTOR_ID = "LUMIN-GUARDDUTY-DETECTOR-ID"` in `tools/guardduty_tools.py:13` with GuardDuty detector ID (`aws guardduty list-detectors`)
- [ ] Replace `ACCOUNT` in both SNS ARNs in `.env` (`SNS_SECURITY_TOPIC`, `SNS_CRITICAL_TOPIC`)
- [ ] Enable AWS GuardDuty in us-east-1 if not already active
- [ ] Verify AWS WAF `SkyBlewWAF` ACL is attached to the CloudFront distribution
- [ ] Create DynamoDB tables: `security-asset-hashes`, `security-events`, `security-alerts`, `security-fraud-reports` (on-demand billing)
- [ ] Create SNS topics `lumin-security-alerts` and `lumin-critical-page`; subscribe H.F. and Eric
- [ ] Seed `security-asset-hashes` with SHA-256 hashes of: `Kid_Sky.png`, `SkyBlew_Logo_-_No_BG.PNG`, `SkyBlewUniverseApp.html`, `index.js`, `styles.css`
- [ ] Set Agent 10 IAM role with cross-agent delete permissions on `fan-behavior-metrics`, `ask-lumin-cs-tickets`, `ask-lumin-onboarding` (for GDPR compliance)
- [ ] Run `python scripts/run_agent.py agent-10-cybersecurity daily_guardduty_digest` and verify clean JSON response
- [ ] Install and enable systemd timers for 15-min session scan and daily/weekly tasks

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Sections III and VI — Agent 10 profile + BDI-O authority discussion (April 2026)*

### 👁 What to Watch on Your Dashboard

**The CRITICAL and HIGH alert counts should be zero or very low in normal operation. Any content hash mismatch is a drop-everything event. The streaming fraud confidence scores for LightSwitch and MoreLoveLessWar — the BRC/Nintendo organic growth should register as legitimate (save rate normal, geographic distribution expected).**

### Canonical Slack Channel

**`#security-ops`** — H.F. checks at **7:45am** in the morning workflow. In normal operation, this channel should be **empty**. Any CRITICAL or HIGH alert requires **immediate escalation to Eric**. **`#security-alerts`** is a separate channel for CRITICAL-severity page notifications — this channel should receive direct SMS/push notifications for Eric at all times.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Daily security briefing summary to `#security-ops` | Daily |
| Weekly comprehensive security digest (WAF, GuardDuty, fraud) | Weekly |
| 15-minute session integrity scan (CloudWatch log) | Every 15 minutes |
| Streaming fraud confidence report (LightSwitch + MoreLoveLessWar) | Weekly (Sundays 03:00 UTC) |
| CRITICAL/HIGH alert to `#security-ops` and `#security-alerts` | Real-time, event-driven — rare in normal operation |
| **Eric SMS page (CRITICAL events)** | Within 60 seconds of detection — see below |

### First 48 Hours — Acceptance Criteria

- [ ] All 5 code placeholders replaced (WAF ACL ID, CF distribution ID, GuardDuty detector ID, 2 SNS ARNs) — verify with a `grep -r "ACCOUNT\|EXXXXXX\|LUMIN-WAF\|LUMIN-GUARDDUTY"` before deployment
- [ ] Daily GuardDuty digest runs and posts a briefing to `#security-ops`
- [ ] `security-asset-hashes` table is seeded with SHA-256 hashes for all 5 protected assets before the first content integrity run
- [ ] Daily 02:00 UTC content integrity run completes without false-positive tamper alerts (empty table = all assets "tampered" — the seeding step is critical)
- [ ] **60-second Eric page verified**: trigger a test CRITICAL event and confirm Eric receives an SNS alert (SMS or email) within 60 seconds. This is the Agent 10 real-time SLA per the BDI-O authority discussion in Operations Guide §VI.
- [ ] streaming fraud Sunday scan runs and posts confidence scores for LightSwitch and MoreLoveLessWar to `#security-ops`
- [ ] systemd timers confirmed active for: 15-min session scan, daily 02:00 content integrity, daily 08:00 GuardDuty digest, Sunday 03:00 fraud scan
- [ ] **Auto-block authority verified**: confirm that if a CRITICAL WAF/GuardDuty finding fires, Agent 10 logs the action AND notifies `#security-ops` — it does NOT wait for human approval before blocking (per BDI-O Obligation)

### Red Flags

- **Any CRITICAL or HIGH alert in `#security-ops`** — this is the primary operator action trigger. In normal operation this channel is empty. Any entry here requires immediate escalation to Eric.
- **Content hash mismatch detected** — a drop-everything event. Agent 10 will automatically invalidate the CloudFront cache. H.F. and Eric are both alerted. Do not dismiss this alert without verifying asset integrity manually.
- **Eric is not paged within 60 seconds of a CRITICAL event** — the Operations Guide (§VI) specifically states that CRITICAL security events must page Eric within 60 seconds. If this SLA is not met, the SNS topic `lumin-critical-page` subscription is not correctly configured.
- **LightSwitch or MoreLoveLessWar streaming fraud confidence score increases to HIGH** — the BRC/Nintendo organic growth is expected to be flagged as legitimate; if confidence scores trend upward, investigate whether DSP anomaly detection is flagging legitimate organic growth.
- **15-minute session scan timer shows a gap > 30 minutes in CloudWatch** — the fleet's fastest-running agent has stopped; security monitoring is offline. Alert Eric immediately.
- **GDPR deletion request not completed within 72 hours** — the Operations Guide (§III) specifies a 72-hour completion window; check Agent 10's cross-agent table delete permissions.

### BDI-O Auto-Block Authority (Per Operations Guide §VI)

Agent 10 is the **only agent with autonomous action authority on confirmed threats**. Per the BDI-O architecture: the duty to protect the fleet overrides the overhead of human approval for time-sensitive security incidents. Agent 10 will:
- **Block malicious IPs via WAF** without prior approval
- **Invalidate CloudFront cache** on content hash mismatch without prior approval
- **Log every autonomous action** to `security-events` table and post to `#security-ops` immediately after acting

This is not a misconfiguration — it is an Obligation. Do not remove or add an approval gate to Agent 10's auto-block path.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

The Operations Guide interaction map (Section VII) confirms:
- **Agent 10 → All**: security monitoring covers all agent data pipelines — confirmed in audit §5 (via GDPR cross-table reads) ✓

The audit §5 also notes the GDPR deletion cross-table reads from `fan-behavior-metrics` (Agent 07) and `ask-lumin-cs-tickets` + `ask-lumin-onboarding` (Agent 09). The Operations Guide confirms this scope as the broadest IAM footprint in the fleet. No discrepancies.
