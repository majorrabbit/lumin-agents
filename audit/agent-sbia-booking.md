# Deployment Readiness Audit — SBIA: SkyBlew Booking Intelligence Agent

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-sbia-booking` |
| Display name | SkyBlew Booking Intelligence Agent (SBIA) |
| Entity | 2StepsAboveTheStars LLC (coordinated by Lumin Luxe Inc.) |
| Layer | Revenue Operations / Booking |
| Mission | Discover every anime, gaming, and nerd-culture convention in the United States. Research booking contacts. Send personalized outreach. Track the pipeline. Surface warm leads to H.F. immediately. Book SkyBlew. |
| Schedule | Monday 09:00 ET (discovery run) · Daily 10:00 ET (follow-up dispatch) · Every 4h (inbox monitoring) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

| File | Location | Placeholder | Required value |
|------|----------|-------------|----------------|
| `.env.example` | Line 18 | `SBIA_FOLLOWUP_LAMBDA_ARN=arn:aws:lambda:us-east-1:ACCOUNT:function:sbia-followup-dispatcher` | Replace `ACCOUNT` with the 12-digit AWS account ID |

The `SBIA_FOLLOWUP_LAMBDA_ARN` is used by `schedule_followup_event()` to create one-time EventBridge rules that invoke the follow-up dispatcher Lambda. If left as the placeholder, all scheduled follow-ups will fail silently — conventions that should receive FOLLOWUP_1 emails after 7 days will be skipped.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `sbia_conventions` (`SBIA_CONVENTIONS_TABLE`) | Convention CRM — all discovered conventions with status, contact info, and pipeline state | Yes |
| DynamoDB table | `sbia_outreach_log` (`SBIA_OUTREACH_LOG_TABLE`) | Complete audit trail of all outbound emails and responses | Yes |
| S3 bucket | `sbia-epk-assets` (`SBIA_EPK_BUCKET`) | EPK assets storage — signed URL generation for booking emails | Yes |
| S3 bucket | `sbia-booking-inbox` (`SBIA_EMAIL_INBOX_BUCKET`) | Incoming email responses stored by SES receive rule | Yes |
| SES | `booking@2stepsabovestars.com` (`SBIA_FROM_EMAIL`) | Outbound booking inquiry emails to convention contacts | Yes |
| SES receive rule | — | Route incoming replies to `booking@2stepsabovestars.com` → `sbia-booking-inbox` S3 bucket | Yes |
| Lambda function | `sbia-followup-dispatcher` | Follow-up dispatcher invoked by one-time EventBridge rules | Yes |
| Secrets Manager | `sbia/web-search-api-key` | Tavily or Brave Search API for convention discovery | Yes |
| Secrets Manager | `sbia/ses-sending-identity` | Verified SES sender email | Yes |
| Secrets Manager | `sbia/sns-alert-topic-arn` | SNS topic ARN for H.F. HOT/WARM lead alerts | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| Tavily Search API OR Brave Search API | API key | — | `sbia/web-search-api-key` | tavily.com or brave.com/search/api — Tavily preferred (better structured results for convention research) | < 1 day |
| AWS SES | IAM role / verified identity | `SBIA_FROM_EMAIL=booking@2stepsabovestars.com` | `sbia/ses-sending-identity` | Verify `booking@2stepsabovestars.com` in SES console; configure SES receive rule to deliver replies to `sbia-booking-inbox` S3 bucket; request production access | 1–3 days |

**SES dual-role setup required.** SBIA uses SES for both **sending** (booking inquiries) and **receiving** (booking replies). This requires:
1. Verify the `booking@2stepsabovestars.com` sender identity
2. Add `2stepsabovestars.com` domain to SES with MX record pointing to SES inbound endpoint
3. Create SES receipt rule: `booking@2stepsabovestars.com` → S3 bucket `sbia-booking-inbox`
4. Request SES production access (if account is in sandbox)

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. SBIA is intentionally self-contained. Its DynamoDB tables feed H.F.'s booking pipeline — not other agents.

**Reads from (produced by other agents):**
- None. SBIA does not read any other agent's tables or receive inter-agent triggers.

**Signal flow:**
```
External web search (Tavily/Brave) + SES inbox
  → Agent SBIA (convention discovery + booking pipeline)
    → sbia_conventions → H.F. (pipeline dashboard)
    → HOT/WARM alert → H.F. (immediate SNS/Slack notification)
    → sbia_outreach_log → audit trail
```

**SBIA is the only fully isolated agent in the fleet.** This is by design — booking operations involve real contractual relationships and must not be triggered by other agents' signals.

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (estimated — weekly discovery + daily follow-up + 6 inbox scans/day) | ~$1.00 |
| DynamoDB — 2 tables, on-demand (~100K R/W ops) | ~$0.15 |
| SES — outbound emails (~80 emails/month at 50/day max, not every day) | ~$0.01 |
| S3 — EPK assets + inbox storage | ~$0.05 |
| Tavily/Brave Search API — weekly discovery runs (~100 queries/month) | ~$0.10 |
| CloudWatch Logs | ~$0.05 |
| **Estimated monthly total** | **~$1.36** |

**Email volume note:** SBIA rate-limits outbound to 50 emails/day maximum and 5 emails/hour. In practice, the weekly Monday discovery run may find 10–20 new qualifying conventions, generating 10–20 initial emails plus follow-ups over the following 2 weeks. Monthly email volume is unlikely to exceed 80–100 total.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Verify SES sender identity for `booking@2stepsabovestars.com` | 1–2 days |
| Configure SES domain receipt rules (MX record + receipt rule → S3) | 1–2 days |
| Request SES production access if in sandbox | 1–3 days |
| Obtain Tavily or Brave Search API key | < 1 day |
| Seed `sbia-epk-assets` S3 bucket with EPK assets (6 files required) | 1 day |
| Seed `sbia_conventions` table with 22 seed conventions (12 A-tier + 7 B-tier + 3 C-tier) | 1 day |
| Create DynamoDB tables (2 tables) and S3 buckets | < 1 day |
| Deploy `sbia-followup-dispatcher` Lambda (standalone deployment) | ½ day |
| Replace `ACCOUNT` in `SBIA_FOLLOWUP_LAMBDA_ARN` and deploy main agent | ½ day |
| First discovery run in dry_run mode | ½ day |
| Enable live sending after dry_run validation | ½ day |
| **Total realistic TTL** | **4–6 working days** |

---

## 8. Risk Callouts

1. **`dry_run=true` is mandatory for the first 2 weeks.** The SBIA spec explicitly requires running `{"trigger_type": "DISCOVERY_RUN", "dry_run": true}` for the first 14 days. This composes emails but does not call `send_booking_email()`. Use this period to validate email content, pitch quality, and contact accuracy before any live outreach reaches real convention organizers. Reputation damage from a poorly calibrated first run cannot be undone.

2. **EPK S3 assets must be present before any live email sends.** `generate_epk_signed_url()` generates a pre-signed S3 URL that points to the EPK package. The spec requires 6 specific files in `sbia-epk-assets/epk/`:
   - `epk.pdf` — one-page artist overview
   - `skyblew_bio.txt` — long-form bio
   - `press_photo_hires.jpg` — high-resolution press photo
   - `stage_plot.pdf` — technical requirements
   - `rider.pdf` — hospitality rider
   - `sample_setlist.pdf` — representative set
   If any of these are missing, the EPK URL will return a 403 and the email's value proposition collapses.

3. **SES sandbox restriction blocks ALL outbound email at launch.** New AWS accounts start in SES sandbox mode with a 200 emails/day limit and delivery only to verified addresses. Request SES production access immediately — it requires a support ticket and takes 1–3 business days. Until production access is granted, SBIA cannot send to real convention contacts.

4. **`SBIA_FOLLOWUP_LAMBDA_ARN` placeholder causes silent follow-up failure.** If this ARN is not corrected, `schedule_followup_event()` will create EventBridge rules pointing to a non-existent Lambda. The Monday discovery run will appear to succeed, but all follow-ups will silently fail. Conventions that need FOLLOWUP_1 will age out to GHOSTED without receiving the follow-up email.

5. **CAN-SPAM and reputation management.** SBIA sends outbound emails to real convention organizers. The system prompt enforces CAN-SPAM compliance (unsubscribe note in every email) and a 365-day no-re-contact window for DECLINED events. Verify the `send_booking_email()` tool includes the unsubscribe note in the rendered email body before enabling live sending.

6. **Seed convention database is required for meaningful Day 1.** The spec requires 22 seed conventions pre-loaded before the first live run. Without seeds, the Monday discovery run starts from a cold start with no historical pipeline data. The seed conventions ensure the pipeline report on Day 1 has a realistic baseline.

---

## 9. Deployment Checklist

- [ ] Verify SES sender identity for `booking@2stepsabovestars.com` in AWS SES console
- [ ] Add `2stepsabovestars.com` domain MX record pointing to SES inbound SMTP endpoint
- [ ] Create SES receipt rule: `booking@2stepsabovestars.com` → S3 `sbia-booking-inbox`
- [ ] Request SES production access (support ticket — 1–3 days)
- [ ] Obtain Tavily or Brave Search API key; store in Secrets Manager at `sbia/web-search-api-key`
- [ ] Create S3 bucket `sbia-epk-assets` and upload all 6 EPK asset files to `sbia-epk-assets/epk/`
- [ ] Create S3 bucket `sbia-booking-inbox`
- [ ] Create DynamoDB tables: `sbia_conventions`, `sbia_outreach_log` (on-demand billing)
- [ ] Seed `sbia_conventions` with 22 starting conventions (12 Tier A anime/gaming + 7 Tier B adjacent + 3 Tier C general)
- [ ] Deploy `sbia-followup-dispatcher` Lambda function
- [ ] Replace `ACCOUNT` in `SBIA_FOLLOWUP_LAMBDA_ARN` env var with actual 12-digit AWS account ID
- [ ] Configure SNS topic for H.F. alerts; store ARN at `sbia/sns-alert-topic-arn`
- [ ] Run first discovery in dry_run mode: `python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN --dry_run=true`
- [ ] Review all composed emails for quality, tone, and CAN-SPAM compliance
- [ ] Maintain dry_run mode for minimum 14 days before enabling live sending
- [ ] After dry_run validation: run `python scripts/run_agent.py agent-sbia-booking DISCOVERY_RUN` (live)
- [ ] Install and enable EventBridge rules for Monday 09:00 ET, daily 10:00 ET, and 4-hourly inbox monitoring
