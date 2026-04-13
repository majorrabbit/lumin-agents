# Deployment Readiness Audit — Agent 09: AskLumin Customer Success

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-09-customer-success` |
| Display name | AskLumin Customer Success Agent |
| Entity | Lumin Luxe Inc. |
| Layer | Fan Experience |
| Mission | Every AskLumin subscriber succeeds — or we know why. Defer the need for a CS hire by 6–9 months while generating the training corpus that makes AskLumin progressively better. |
| Schedule | Real-time (inbound support) · Daily (proactive onboarding + churn scan) · Weekly (metrics digest) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

| File | Line | Placeholder | Required value |
|------|------|-------------|----------------|
| `.env.example` | 9 | `SNS_ESCALATION_TOPIC=arn:aws:sns:us-east-1:ACCOUNT:lumin-cs-escalations` | Replace `ACCOUNT` with the 12-digit AWS account ID |

**Additional defect — do not deploy until resolved:**  
`tools/support_tools.py:557` contains a **Python SyntaxError**: a DynamoDB `query()` call uses the keyword argument `ExpressionAttributeValues` twice. Python 3.9+ raises `SyntaxError: keyword argument repeated` at compile time, which means **the entire `agent-09-customer-success` module cannot be imported**. The integration smoke test marks this agent as `xfail(strict=True)` for this reason.

This defect must be fixed before Agent 09 can deploy. The fix is straightforward: merge the two `ExpressionAttributeValues` dicts into one call. No new logic required.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `ask-lumin-sessions` (`SESSIONS_TABLE`) | AskLumin subscriber session and usage history | Yes |
| DynamoDB table | `ask-lumin-cs-tickets` (`CS_TICKETS_TABLE`) | Support ticket tracking — open, in-progress, resolved | Yes |
| DynamoDB table | `ask-lumin-cs-metrics` (`CS_METRICS_TABLE`) | CS performance metrics — deflection rate, resolution time | Yes |
| DynamoDB table | `ask-lumin-onboarding` (`ONBOARDING_TABLE`) | Per-subscriber onboarding checklist and touchpoint status | Yes |
| DynamoDB table | `ask-lumin-nps` (`NPS_TABLE`) | Net Promoter Score responses and trend | Yes |
| SES | verified sender `hello@lumin.luxe` | Onboarding touchpoint emails, churn-rescue emails | No — shared with Agent 02 |
| SNS topic | `lumin-cs-escalations` (`SNS_ESCALATION_TOPIC`) | Escalation alerts when Agent 09 cannot resolve a subscriber issue | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| AWS SES | IAM role / verified identity | `FROM_EMAIL=hello@lumin.luxe` | — | Verify `hello@lumin.luxe` sender identity in SES console (shared with Agent 02) | 1–2 days |

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Agent 09's tables feed H.F.'s CS dashboard and the AskLumin product team — not other agents.

**Reads from (produced by other agents):**
- **Agent 01 (Resonance Intelligence)** outputs are referenced for "value demonstration" in retention scenarios — showing high-churn subscribers concrete examples of the intelligence AskLumin surfaces. This is a loose coupling (content reference, not table dependency).

**Signal flow:**
```
AskLumin subscriber interaction (inbound message / scheduled trigger)
  → Agent 09 (CS response + risk scoring)
    → ask-lumin-cs-tickets → H.F. (escalated issues)
    → ask-lumin-nps → Product team (NPS trend)
    → SNS lumin-cs-escalations → H.F. / Eric (critical escalation)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — real-time support + daily scans) | $3.99 |
| DynamoDB — 5 tables, on-demand (~400K R/W ops, real-time traffic) | ~$0.60 |
| SES — onboarding and churn-rescue emails (~100 emails/month) | ~$0.01 |
| SNS — escalation notifications | ~$0.01 |
| CloudWatch Logs | ~$0.20 |
| **Estimated monthly total** | **~$4.81** |

**Note:** Agent 09 has the third-highest Claude API cost in the fleet ($3.99/mo) because it operates in real-time response mode — each subscriber interaction triggers a Claude call. Cost scales directly with the AskLumin subscriber count. At current early-stage subscriber volumes, $3.99/month is accurate; revisit this estimate when AskLumin reaches 500+ active subscribers.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| **Fix SyntaxError in `tools/support_tools.py:557`** | ½ day |
| Verify SES sender identity (`hello@lumin.luxe`) | 1–2 days (shared with Agent 02) |
| Create SNS topic `lumin-cs-escalations` and subscribe H.F.'s email | < 1 day |
| Create DynamoDB tables (5 tables) | < 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **3–4 working days** |

**Blocking issue:** The SyntaxError in `support_tools.py:557` must be resolved before any other deployment step. The agent cannot import until this is fixed.

---

## 8. Risk Callouts

1. **SyntaxError in `support_tools.py:557` — DEPLOY BLOCKER.** The `ExpressionAttributeValues` keyword argument is duplicated in a DynamoDB `query()` call at line 557. Python 3.9+ raises a `SyntaxError` at compile time — the module cannot be imported. This is a code defect, not a configuration issue. Fix it before any deployment attempt.

2. **Real-time mode means no warm-up period.** Unlike other agents that run on scheduled cycles, Agent 09 responds to inbound subscriber messages immediately. The first AskLumin subscriber to send a support message after deployment will interact with the agent. Ensure the system prompt, escalation thresholds, and SES sender identity are all verified before enabling real-time mode.

3. **Five DynamoDB tables — same footprint as Agent 07.** The `ask-lumin-sessions` table is the most critical: it stores the context that Agent 09 uses to personalize every subscriber interaction. If this table is empty on Day 1, Agent 09 responds without subscriber context. Pre-populate with initial session records for existing AskLumin subscribers before enabling live mode.

4. **`hello@lumin.luxe` is shared with Agent 02.** Both agents send from this address. SES sending reputation is shared. If Agent 02 triggers a bounce or complaint rate spike, it could impact Agent 09's onboarding email deliverability. Monitor bounce rates across both agents jointly.

5. **No opt-out mechanism for proactive touchpoints.** Agent 09 sends proactive onboarding and churn-rescue emails via SES. If a subscriber wants to opt out of proactive emails, this must be handled manually — there is no automated unsubscribe in the current code.

---

## 9. Deployment Checklist

- [ ] **Fix SyntaxError in `tools/support_tools.py:557`** — merge duplicate `ExpressionAttributeValues` keyword argument before any other step
- [ ] Verify SES sender identity for `hello@lumin.luxe` (shared with Agent 02)
- [ ] Create SNS topic `lumin-cs-escalations`, subscribe H.F.'s email and/or Slack webhook
- [ ] Replace `ACCOUNT` placeholder in `SNS_ESCALATION_TOPIC` env var with actual 12-digit AWS account ID
- [ ] Create DynamoDB tables: `ask-lumin-sessions`, `ask-lumin-cs-tickets`, `ask-lumin-cs-metrics`, `ask-lumin-onboarding`, `ask-lumin-nps` (on-demand billing)
- [ ] Pre-populate `ask-lumin-sessions` with existing AskLumin subscriber records
- [ ] Configure Slack webhook (`SLACK_CS_WEBHOOK`) and verify test message posts
- [ ] Run `python scripts/run_agent.py agent-09-customer-success daily_onboarding_scan` and verify clean JSON (post SyntaxError fix)
- [ ] Test inbound support scenario: send a test subscriber message and confirm Agent 09 responds and logs interaction
- [ ] Verify escalation path: trigger a scenario that exceeds Agent 09's resolution authority and confirm SNS alert fires

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 09 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The deflection rate: above 75% means Agent 9 is handling support effectively. NPS trending — the target is above 50. The churn risk list: any subscriber who represents more than $500 MRR is worth a personal call from H.F.**

### Canonical Slack Channel

**`#cs-escalations`** — escalations that Agent 09 cannot resolve (billing disputes, complex account issues, complaints). H.F. must respond to any escalation within the business day. **`#pending-approvals`** — any proactive outreach draft Agent 09 generates for a churn-risk subscriber lands here for H.F. approval before send. Neither channel is part of the morning workflow but should be checked at least once per business day.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Daily onboarding sweep (CloudWatch log) | Daily |
| Daily churn risk scan (CloudWatch log) | Daily |
| Onboarding progress report | Daily (Days 1–7 for new subscribers) |
| Churn risk outreach draft to `#pending-approvals` | Only when a subscriber shows ≥3 churn signals |
| Weekly NPS score and deflection rate digest | Weekly |
| Escalation to `#cs-escalations` | Real-time, only when Agent 09 cannot resolve |

### First 48 Hours — Acceptance Criteria

- [ ] **SyntaxError in `tools/support_tools.py:557` is confirmed fixed** — the module imports cleanly (`python -c "import agents.agent_09_customer_success.tools.support_tools"` with no error)
- [ ] Smoke test (`daily_onboarding_scan`) completes with no `"error"` key in CloudWatch
- [ ] `ask-lumin-sessions` table is pre-populated with existing subscriber records before enabling real-time mode
- [ ] Test inbound support: send a test subscriber message and confirm Agent 09 responds with a contextual reply logged to `ask-lumin-cs-tickets`
- [ ] **Approval gate verified**: trigger a scenario where Agent 09 drafts a churn-risk outreach message — confirm it lands in `#pending-approvals` and is NOT sent automatically
- [ ] Escalation path verified: trigger a scenario exceeding Agent 09's resolution authority and confirm SNS `lumin-cs-escalations` fires and H.F. receives the alert
- [ ] systemd timers confirmed active for: daily onboarding sweep, daily churn scan, weekly NPS digest

### Red Flags

- **Deflection rate below 30% after Month 2** — Agent 09 is not resolving support effectively; review system prompt and add more resolution paths. This is the kill criterion from the deploy plan.
- **NPS trending below 40 for 4 consecutive weeks** — subscribers are unhappy with the AskLumin experience; audit recent escalated tickets for patterns.
- **A proactive churn-rescue email is sent without H.F. approval** — this is a BDI-O Obligation violation. Pause Agent 09 immediately; audit SES send logs.
- **Any subscriber representing >$500 MRR in the churn risk list** — the Operations Guide calls this out as warranting a personal call from H.F. Do not let this subscriber churn without direct human contact.
- **`#cs-escalations` is empty after 30 days of operation** — either all issues are being resolved (good) or the escalation path is broken (bad); verify by triggering a manual escalation scenario.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**ADDITION — not in original audit §5:**  
The Operations Guide Section VII interaction map documents **Agent 07 → Agent 09**: "Declining usage triggers proactive CS outreach." The original audit §5 described a loose coupling with Agent 01 (value demonstration in retention scenarios) but did not document the Agent 07 → Agent 09 signal. In the guide, when Agent 07 identifies a Core fan with declining engagement, it surfaces the signal to Agent 09, which drafts a proactive outreach message for H.F.'s approval. This integration is not yet in the current Agent 07 or Agent 09 code — it is a Phase 6 target.

Confirmed existing connection (also in audit §5):
- **Agent 01 → Agent 09** (loose): Resonance Analytics outputs referenced for subscriber value demonstration — confirmed in audit §5 (described as "loose coupling") ✓

Addition from Operations Guide:
- **Agent 07 → Agent 09** [ADDITION]: declining-usage signal triggers proactive CS outreach draft — NOT in audit §5; Phase 6 target
