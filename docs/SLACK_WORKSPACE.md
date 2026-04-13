# Lumin Fleet — Slack Workspace Architecture

**Phase 3.6 — April 2026**  
**Source of truth:** Lumin Agent Fleet Operations Guide §V (Morning Workflow) + §III (Agent Profiles) + agent code inspection

This document is both the **recipe for building the Slack workspace** and the **canonical reference** for which channel a given agent posts to. Future Claude Code sessions and deploy prompts should read this file to know correct channel names and env var mappings.

---

## Section 1 — Channel Inventory

### 1A — Canonical Channels (create all of these)

These channels are required for Day 1. Sources: Operations Guide §V morning workflow table + agent code cross-check.

| Channel | Agents | Cadence | Severity Range | Notes |
|---------|--------|---------|---------------|-------|
| `#pending-approvals` | 02, 03, 09, 11, 12, SBIA | As events occur | LOW to HIGH | First stop in H.F.'s morning workflow (7:00am). Every approval-gated output lands here. Agent 12 routes cultural moment content with URGENT flag (approve within 2–4h). Agent 11 routes URGENT outreach when Agent 06 fires. |
| `#cultural-moments` | 06 | As moments form | MEDIUM to HIGH | Agent 06 fires when a cultural signal crosses the MEDIUM threshold. Checked by H.F. at 7:05am. Central Signal Chain starts here — T+0:00. |
| `#sync-queue` | 02 | Every 4h when briefs found | LOW to CRITICAL | Sync licensing discovery queue. H.F. checks at 7:10am. Agent 02 posts here when briefs qualify (CRITICAL briefs bypass queue and go direct to H.F.). |
| `#sync-pitches` | 03 | Weekly | LOW | Agent 03 posts the weekly pitch selection (1–3 tracks per week). |
| `#anime-gaming-intel` | 04 | Daily | LOW to HIGH | Agent 04 daily anime/gaming trend digest. H.F. checks at 7:20am. |
| `#royalty-reconciliation` | 05 | Monthly | LOW to HIGH | Agent 05 monthly royalty audit report. |
| `#fan-intelligence` | 07 | Daily, weekly | LOW | Agent 07 daily fan behavior digest. |
| `#ar-catalog` | 08 | Monthly | LOW | Agent 08 monthly AR catalog strategy report. **Note: Agent 08 code (agent.py) references `#ar-strategy` — the webhook should be configured to post to this canonical `#ar-catalog` channel.** |
| `#cs-escalations` | 09 | As events occur | LOW to CRITICAL | Agent 09 customer-support escalation alerts. H.F. checks at 7:30am. |
| `#security-ops` | 10 | Daily digest + real-time | LOW to CRITICAL | Agent 10 daily security digest and non-critical alerts. Eric checks this channel. **Note: Agent 10 code routes to `#security-alerts` via `SLACK_SECURITY_WEBHOOK` — a second webhook configured to `#security-ops` is required for the daily digest (see §3).** |
| `#security-alerts` | 10 | Real-time critical events only | HIGH to CRITICAL | Agent 10 real-time HIGH/CRITICAL security alerts. Eric has mobile notifications enabled for this channel. |
| `#fan-discovery-queue` | 11 | Daily 07:00 UTC + evening | LOW | Agent 11 morning opportunity queue (5–15 outreach drafts with 3 variants each). H.F. checks at 8:15am. Evening conversion report at 22:00 UTC. |
| `#social-approvals` | 12 | Sunday 6pm weekly + daily | LOW to HIGH | Agent 12 content drafts for approval. Code (content_tools.py) explicitly references this channel name. Maps to `SLACK_APPROVAL_WEBHOOK`. |
| `#hot-leads` | SBIA | As responses arrive | HIGH | SBIA fires immediately when a convention replies with interest. H.F. checks at 8:00am. SBIA uses Secrets Manager (`sbia/slack-webhook-url`) not an env var — see §3. Monday weekly pipeline report also posts here. |
| `#lumin-critical-alerts` | All agents | Emergency only | CRITICAL | Fleet-wide emergency broadcast. No normal operations. Used for system-wide failures or multi-agent coordination emergencies. |

**Total canonical channels: 15**

---

### 1B — Additional Code-Referenced Channels (edge cases)

These channels appear in agent code but are not listed in Operations Guide §V. H.F. should decide whether to create them or treat them as aliases for existing canonical channels. **Do not modify agent code to change these names — they are hardcoded in the current codebase.**

| Channel | Agent | Where Referenced | Relationship to Canonical | Recommendation |
|---------|-------|-----------------|--------------------------|----------------|
| `#resonance-intelligence` | 01 | `report_tools_resonance.py`, `agent.py` | Not in Operations Guide §V | Create — Agent 01 posts phase transition alerts here. Configure `SLACK_RESONANCE_WEBHOOK` to post here. |
| `#sync-briefs` | 02 | `brief_tools.py` | May overlap with `#sync-queue` | Create or alias. Agent 02 uses one webhook (`SLACK_SYNC_WEBHOOK`) — both `#sync-queue` and `#sync-briefs` appear in code. The webhook can only point to one channel. |
| `#sync-intelligence` | 02 | `agent.py` system prompt | Internal ops channel | Investigate — if used for digest/summary separate from `#sync-queue`, create. Otherwise skip. |
| `#ar-strategy` | 08 | `agent.py` line 562 | Conflicts with canonical `#ar-catalog` | Do NOT create separately. Configure `SLACK_AR_WEBHOOK` to `#ar-catalog`. The system prompt uses the name `#ar-strategy` but posts via webhook URL — webhook routing takes precedence over the name in the prompt. |
| `#cs-alerts` | 09 | `agent.py` line 225 | Sub-channel of `#cs-escalations` | Investigate — may be an internal ops channel for non-customer-facing alerts. Agent 09 uses one webhook (`SLACK_CS_WEBHOOK`). Create if Agent 09 needs two alert tiers. |
| `#cs-leadership` | 09 | `agent.py` line 242 | Escalation to leadership | Create if there is a leadership team separate from H.F. who needs visibility into critical CS events. Otherwise skip. |
| `#social-intelligence` | 12 | `agent.py` | Weekly analytics digest | Create — Agent 12's `SLACK_SOCIAL_WEBHOOK` (second webhook) likely routes here. This is separate from `#social-approvals`. |

**Total code-referenced channels requiring H.F. decision: 7**

---

## Section 2 — Step-by-Step Slack Workspace Setup

Perform all steps in the Slack web UI (slack.com) and api.slack.com. Do not skip any step — the test script in §4 verifies the entire list before Phase 4 begins.

### Step 1 — Create All 15 Canonical Channels

In Slack web UI → left sidebar → + (Add channels) → Create a new channel:

Create each channel in this order (matches H.F.'s morning workflow):

| # | Channel name | Visibility |
|---|-------------|-----------|
| 1 | `pending-approvals` | Public |
| 2 | `cultural-moments` | Public |
| 3 | `sync-queue` | Public |
| 4 | `sync-pitches` | Public |
| 5 | `anime-gaming-intel` | Public |
| 6 | `royalty-reconciliation` | Public |
| 7 | `fan-intelligence` | Public |
| 8 | `ar-catalog` | Public |
| 9 | `cs-escalations` | Public |
| 10 | `security-ops` | **Private** — Eric + H.F. only |
| 11 | `security-alerts` | **Private** — Eric + H.F. only |
| 12 | `fan-discovery-queue` | Public |
| 13 | `social-approvals` | Public |
| 14 | `hot-leads` | Public |
| 15 | `lumin-critical-alerts` | Public |

Then create the recommended edge-case channels:

| # | Channel name | Visibility |
|---|-------------|-----------|
| 16 | `resonance-intelligence` | Public |
| 17 | `social-intelligence` | Public |

---

### Step 2 — Create Incoming Webhooks (one per channel, one per agent webhook env var)

For each channel that an agent posts to, you need one Incoming Webhook URL.

Go to: **api.slack.com/apps** → Create New App → From Scratch → name it "Lumin Fleet" → select your workspace.

Then: Incoming Webhooks → Activate → Add New Webhook to Workspace → select the target channel.

Create webhooks in this order (matches §3 env var table):

| Webhook # | Target Channel | Maps to Env Var | Maps to SM Key |
|-----------|---------------|-----------------|----------------|
| 1 | `#resonance-intelligence` | `SLACK_RESONANCE_WEBHOOK` | `lumin/slack-webhooks/resonance` |
| 2 | `#sync-queue` | `SLACK_SYNC_WEBHOOK` | `lumin/slack-webhooks/sync` |
| 3 | `#sync-pitches` | `SLACK_PITCH_WEBHOOK` | `lumin/slack-webhooks/pitch` |
| 4 | `#anime-gaming-intel` | `SLACK_AG_WEBHOOK` | `lumin/slack-webhooks/ag` |
| 5 | `#royalty-reconciliation` | `SLACK_ROYALTY_WEBHOOK` | `lumin/slack-webhooks/royalty` |
| 6 | `#cultural-moments` | `SLACK_CULTURAL_WEBHOOK` | `lumin/slack-webhooks/cultural` |
| 7 | `#fan-intelligence` | `SLACK_FAN_WEBHOOK` | `lumin/slack-webhooks/fan` |
| 8 | `#ar-catalog` | `SLACK_AR_WEBHOOK` | `lumin/slack-webhooks/ar` |
| 9 | `#cs-escalations` | `SLACK_CS_WEBHOOK` | `lumin/slack-webhooks/cs` |
| 10 | `#security-alerts` | `SLACK_SECURITY_WEBHOOK` | `lumin/slack-webhooks/security` |
| 11 | `#security-ops` | *(no env var — Agent 10 uses one webhook)* | `lumin/slack-webhooks/security-ops` *(store manually)* |
| 12 | `#fan-discovery-queue` | `SLACK_DISCOVERY_WEBHOOK` | `lumin/slack-webhooks/discovery` |
| 13 | `#social-approvals` | `SLACK_APPROVAL_WEBHOOK` | `lumin/slack-webhooks/approval` |
| 14 | `#social-intelligence` | `SLACK_SOCIAL_WEBHOOK` | `lumin/slack-webhooks/social` |
| 15 | `#hot-leads` | *(no env var — SBIA uses SM)* | `sbia/slack-webhook-url` |
| 16 | `#lumin-critical-alerts` | *(no dedicated agent webhook — emergency broadcast)* | `lumin/slack-webhooks/critical-alerts` *(store manually)* |

**Total webhooks to create: 16**

> **Note on `#security-ops`:** Agent 10's code only has one webhook env var (`SLACK_SECURITY_WEBHOOK`) which the code routes to `#security-alerts`. The `#security-ops` daily digest uses the same webhook. To have the daily digest land in `#security-ops` and real-time alerts in `#security-alerts`, Agent 10 needs a second webhook env var (`SLACK_SECURITY_OPS_WEBHOOK`) added to its `.env`. This is a Phase 4 deploy configuration decision — for now, create both channels and both webhooks; H.F. and Eric can decide whether to add the second webhook var to Agent 10.

---

### Step 3 — Store Webhook URLs in AWS Secrets Manager

For each webhook URL copied from Step 2, store it in AWS Secrets Manager under the `lumin/slack-webhooks/` path.

In AWS Console → Secrets Manager → Store a new secret → Other type of secret → key/value pair:

```
Secret name: lumin/slack-webhooks/resonance
Secret value: { "url": "https://hooks.slack.com/services/..." }
```

Repeat for every webhook in the table above. Keep a local record in a secure password manager as a backup.

---

### Step 4 — Invite H.F. to Every Channel

H.F. must be a member of all 15 canonical channels plus the 2 edge-case channels created above. In each channel → Members → Invite:

- Add H.F. to: `#pending-approvals`, `#cultural-moments`, `#sync-queue`, `#sync-pitches`, `#anime-gaming-intel`, `#royalty-reconciliation`, `#fan-intelligence`, `#ar-catalog`, `#cs-escalations`, `#security-ops`, `#security-alerts`, `#fan-discovery-queue`, `#social-approvals`, `#hot-leads`, `#lumin-critical-alerts`, `#resonance-intelligence`, `#social-intelligence`

---

### Step 5 — Invite Eric to Security and Critical Channels

Eric must be in the three channels where CRITICAL events page him within 60 seconds (per Operations Guide §III, Agent 10 profile):

- Add Eric to: `#security-ops`, `#security-alerts`, `#lumin-critical-alerts`

Ensure Eric has mobile push notifications **enabled** for `#security-alerts` and `#lumin-critical-alerts`. This is the 60-second page SLA for critical security findings.

---

### Step 6 — Pin Daily Workflow Message in `#pending-approvals`

In `#pending-approvals`, post and pin a message at the top explaining the daily workflow:

```
📋 PENDING APPROVALS — DAILY WORKFLOW (from Lumin Agent Fleet Operations Guide §V)

Every piece of content or action requiring H.F. approval lands here.

Morning check: 7:00am daily
—
• Content from Agent 12 (Social Media Director): approve/edit/decline each draft
• Escalations from Agent 09 (CS Director): review and respond within 4h
• Outreach from Agent 11 (Fan Discovery): approve/decline each community message
• URGENT flag = cultural moment content from Agent 12 (approve within 2–4h)

Nothing posts to any platform or sends to any customer until you approve it here.
```

Pin the message: click the three dots → Pin to channel.

---

## Section 3 — Env Var Naming Convention

Each agent reads its Slack webhook URL from a specific environment variable. This table is the authoritative cross-reference between env var names (as written in each agent's `.env.example`), the channel the webhook posts to, and the agent(s) that use it.

**Do not rename these env vars or change any agent code.** These names are read from the codebase as-is.

| Env Var | Channel Posted To | Agent(s) | Secrets Manager Key | Notes |
|---------|-----------------|---------|---------------------|-------|
| `SLACK_RESONANCE_WEBHOOK` | `#resonance-intelligence` | Agent 01 | `lumin/slack-webhooks/resonance` | Agent 01 posts phase transition alerts and RESONANCE intelligence reports |
| `SLACK_SYNC_WEBHOOK` | `#sync-queue` | Agent 02 | `lumin/slack-webhooks/sync` | Agent 02 brief discovery queue; code also references `#sync-briefs` and `#sync-intelligence` but uses one webhook |
| `SLACK_PITCH_WEBHOOK` | `#sync-pitches` | Agent 03 | `lumin/slack-webhooks/pitch` | Agent 03 weekly sync pitch selection |
| `SLACK_AG_WEBHOOK` | `#anime-gaming-intel` | Agent 04 | `lumin/slack-webhooks/ag` | Agent 04 daily anime/gaming trend digest |
| `SLACK_ROYALTY_WEBHOOK` | `#royalty-reconciliation` | Agent 05 | `lumin/slack-webhooks/royalty` | Agent 05 monthly royalty audit |
| `SLACK_CULTURAL_WEBHOOK` | `#cultural-moments` | Agent 06 | `lumin/slack-webhooks/cultural` | Agent 06 cultural moment detection — T+0:00 signal chain trigger |
| `SLACK_FAN_WEBHOOK` | `#fan-intelligence` | Agent 07 | `lumin/slack-webhooks/fan` | Agent 07 fan behavior intelligence digest |
| `SLACK_AR_WEBHOOK` | `#ar-catalog` | Agent 08 | `lumin/slack-webhooks/ar` | Agent 08 AR catalog strategy report. Code system prompt says `#ar-strategy` — webhook routing to `#ar-catalog` takes precedence. |
| `SLACK_CS_WEBHOOK` | `#cs-escalations` | Agent 09 | `lumin/slack-webhooks/cs` | Agent 09 customer support escalations. Code also references `#cs-alerts` and `#cs-leadership` — one webhook, routes everything to `#cs-escalations`. |
| `SLACK_SECURITY_WEBHOOK` | `#security-alerts` | Agent 10 | `lumin/slack-webhooks/security` | Agent 10 real-time security alerts. Code comments explicitly name `#security-alerts`. The `#security-ops` daily digest uses the same webhook — see §2 Step 2 note. |
| `SLACK_DISCOVERY_WEBHOOK` | `#fan-discovery-queue` | Agent 11 | `lumin/slack-webhooks/discovery` | Agent 11 daily opportunity queue (07:00 UTC) + evening conversion report (22:00 UTC) |
| `SLACK_APPROVAL_WEBHOOK` | `#social-approvals` | Agent 12 | `lumin/slack-webhooks/approval` | Agent 12 content drafts awaiting H.F. approval. Code (content_tools.py) explicitly references `#social-approvals`. |
| `SLACK_SOCIAL_WEBHOOK` | `#social-intelligence` | Agent 12 | `lumin/slack-webhooks/social` | Agent 12 analytics digest and weekly performance summary |
| *(SM only — no env var)* | `#hot-leads` | SBIA | `sbia/slack-webhook-url` | SBIA retrieves webhook URL from Secrets Manager via `_get_secret("sbia/slack-webhook-url")`. Not an env var. HOT_LEAD and BOOKING_CONFIRMED events only. |

**Total unique webhook env vars across the fleet: 13**  
**Total unique channels receiving agent posts: 15 canonical + 2 edge-case = 17**

---

## Section 4 — Post-Setup Verification Recipe

Once all channels and webhooks are created and stored in AWS Secrets Manager, run the test script to verify every channel is wired correctly before Phase 4 begins.

### Prerequisites

1. All webhook URLs collected in Step 2 above
2. Create a local `.env` file (do NOT commit this file — add it to `.gitignore`) with all webhook URLs:

```dotenv
# scripts/test_slack_channels.py reads this file
# Store webhook URLs here for pre-deploy verification only
# After verification, delete this file — use AWS Secrets Manager in production

SLACK_RESONANCE_WEBHOOK=https://hooks.slack.com/services/...
SLACK_SYNC_WEBHOOK=https://hooks.slack.com/services/...
SLACK_PITCH_WEBHOOK=https://hooks.slack.com/services/...
SLACK_AG_WEBHOOK=https://hooks.slack.com/services/...
SLACK_ROYALTY_WEBHOOK=https://hooks.slack.com/services/...
SLACK_CULTURAL_WEBHOOK=https://hooks.slack.com/services/...
SLACK_FAN_WEBHOOK=https://hooks.slack.com/services/...
SLACK_AR_WEBHOOK=https://hooks.slack.com/services/...
SLACK_CS_WEBHOOK=https://hooks.slack.com/services/...
SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/...
SLACK_DISCOVERY_WEBHOOK=https://hooks.slack.com/services/...
SLACK_APPROVAL_WEBHOOK=https://hooks.slack.com/services/...
SLACK_SOCIAL_WEBHOOK=https://hooks.slack.com/services/...
SBIA_SLACK_WEBHOOK=https://hooks.slack.com/services/...
```

3. Install the `requests` and `python-dotenv` libraries if not already present:

```bash
pip install requests python-dotenv
```

### Run the Test

```bash
python scripts/test_slack_channels.py
```

Expected output: 14 lines, each showing `SENT` — one for each webhook in the `.env` file. Any `FAILED` or `ERROR` line identifies a misconfigured webhook that must be fixed before Phase 4.

### Acceptance Criteria

All 14 webhooks report `SENT`. No `FAILED`. No `ERROR`. Then:
1. Verify each test message appears in its respective Slack channel
2. Confirm H.F. and Eric can see messages in the private channels (`#security-ops`, `#security-alerts`)
3. Delete the local `.env` file after verification is complete

The workspace is ready for Phase 4 when all 14 send confirmations are green.

---

*Generated by Claude Code — Phase 3.6 — April 2026*  
*Source: Lumin Agent Fleet Operations Guide §V + §III + agent codebase inspection*
