# Lumin MAS — Pre-Deploy Checklist

**Document:** Phase 3.5 — April 2026  
**Purpose:** Walk through this checklist before starting Prompt P4.1 (first live EC2 deployment).  
**Audience:** Eric (infrastructure) · H.F. (approval and credentials)  
**Source:** Synthesized from `docs/DEPLOY_PLAN.md` §4 and per-agent audit reports in `audit/`.

> **Do not start Prompt P4.1 until every box on this checklist is checked.**

Treat each checkbox as a gate. A partially-configured environment is more dangerous than an un-deployed one — a running agent with a missing credential will fail silently in ways that are harder to diagnose than "the agent never started."

---

## 1. AWS Account Readiness

### Identity & Access

- [ ] AWS account ID is known and documented (12-digit number, format: `123456789012`)
- [ ] AWS root account has MFA enabled
- [ ] IAM user or role for **Eric** exists with console and CLI access; MFA enabled
- [ ] IAM user or role for **H.F.** exists with read access to Cost Explorer and billing; MFA enabled
- [ ] IAM role `lumin-agent-ec2-role` created as an **instance profile** with the following least-privilege policies:

```
DynamoDB — Read/Write on tables matching these prefixes:
  lumin-*          ask-lumin-*      resonance-*      skyblew-*
  fan-*            fan-discovery-*  cultural-*       sbia_*
  opp-*            anime-gaming-*   sync-*           security-*

Secrets Manager — GetSecretValue on: lumin/*, skyblew/*, sbia/*

S3 — Read/Write on: lumin-*, skyblew-*, sbia-*

SES — SendEmail, SendRawEmail

SNS — Publish on: lumin-*, skyblew-*

DynamoDB Streams — GetRecords, GetShardIterator, DescribeStream on cultural-*, resonance-*
  (or Kinesis: PutRecord, GetRecords on resonance-raw-stream, cultural-signal-stream
   — depending on the Kinesis vs. DynamoDB Streams decision made in §6 below)

CloudWatch Logs — CreateLogGroup, CreateLogStream, PutLogEvents

Lambda — InvokeFunction on sbia-followup-dispatcher  (SBIA only)

GuardDuty — GetFindings, ListFindings                (Agent 10 only)

WAFv2 — GetWebACL, GetSampledRequests (read-only)    (Agent 10 only)

CloudFront — CreateInvalidation                      (Agent 10 only)
```

### Cost Controls

- [ ] AWS monthly budget alert set at **$100/month** (fleet estimate: ~$51/month; alert at 2× estimate)
- [ ] AWS Cost Explorer enabled and accessible to both Eric and H.F.
- [ ] CloudWatch log retention policy set to **14 days** on all `/aws/lambda/lumin-*` log groups

---

## 2. EC2 Host Readiness

### Instance

- [ ] Target EC2 instance launched; hostname or IP documented here: `_______________`
- [ ] Instance type confirmed: **t3.medium** ($29.95/month) or t3.small ($15/month for early stages)
- [ ] Region: **us-east-1** (must match SES and GuardDuty configuration)
- [ ] Ubuntu **24.04 LTS** confirmed (`lsb_release -a` shows `Ubuntu 24.04`)
- [ ] IAM instance profile `lumin-agent-ec2-role` attached to the instance

### Runtime Environment

- [ ] Python 3.12 installed system-wide (`python3.12 --version` returns `3.12.x`)
- [ ] `pip` for Python 3.12 available (`python3.12 -m pip --version`)
- [ ] `git` installed (`git --version`)
- [ ] `systemd` is the init system (`systemctl --version`)

### User & Directory Setup

- [ ] `lumin` system user created (`sudo useradd -r -m -s /bin/bash lumin`)
- [ ] `/opt/lumin-agents` directory created and writable by `lumin` user
- [ ] Repo cloned to `/opt/lumin-agents` as the `lumin` user (`git clone git@github.com:majorrabbit/lumin-agents.git /opt/lumin-agents`)
- [ ] Shared library installed: `cd /opt/lumin-agents && python3.12 -m pip install -e shared/`
- [ ] Shared library test suite passes on the EC2 host: `python3.12 -m pytest tests/shared/ -q` → all green

### Observability

- [ ] CloudWatch unified agent installed (`amazon-cloudwatch-agent --version`)
- [ ] CloudWatch agent configured to ship `/var/log/lumin-agents/*.log` and journal entries to CloudWatch log group `/lumin/agents/`
- [ ] CloudWatch agent running (`systemctl status amazon-cloudwatch-agent`)

---

## 3. Credentials in Hand

### Required Before Phase 4 Starts (Wave 1 — Foundation Agents)

These credentials are needed before deploying **any** agent. Obtain them before Phase 4 begins — do not start the EC2 provisioning session without them already in hand.

| Credential | Where to Get It | Where to Store It | Status |
|-----------|----------------|-------------------|--------|
| **Anthropic API key** | [console.anthropic.com](https://console.anthropic.com) | AWS Secrets Manager: `lumin/anthropic-api-key` | - [ ] |
| **AWS account ID** | AWS console top-right corner | Document here + in `/opt/lumin-agents/.env` | - [ ] |

### Required Before Wave 1 (Agents 04 and 05 — Foundation)

| Credential | Where to Get It | Env Var / SM Key | Status |
|-----------|----------------|------------------|--------|
| Slack webhook URL — `#anime-gaming-intel` | Slack App > Incoming Webhooks | `lumin/slack/anime-gaming-intel-webhook` | - [ ] |
| Slack webhook URL — `#pending-approvals` | Slack App > Incoming Webhooks | `lumin/slack/pending-approvals-webhook` | - [ ] |

### Required Before Wave 2 (Agents 01, 06, 07 — Strategic Intelligence)

| Credential | Where to Get It | Env Var / SM Key | Status |
|-----------|----------------|------------------|--------|
| **Chartmetric API key** (paid subscription) | [chartmetric.com](https://chartmetric.com) | `lumin/chartmetric-api-key` | - [ ] |
| **Soundcharts API key** (paid subscription) | [soundcharts.com](https://soundcharts.com) | `lumin/soundcharts-api-key` | - [ ] |
| **Spotify Client ID + Secret** | [developer.spotify.com](https://developer.spotify.com) | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | - [ ] |
| **YouTube Data API v3 key** | Google Cloud Console | `lumin/youtube-api-key` | - [ ] |
| **SkyBlew Chartmetric artist ID** | Chartmetric dashboard (after provisioning) | `SKYBLEW_CM_ID` in Agent 07 `.env` | - [ ] |
| SNS topic ARN for Resonance alerts | AWS SNS console | `SNS_RESONANCE_TOPIC` in Agent 01 `.env` | - [ ] |

### Required Before Wave 3 (Revenue Operations)

| Credential | Where to Get It | Env Var / SM Key | Status |
|-----------|----------------|------------------|--------|
| **SES production access** (support ticket) | AWS console → SES → Account Dashboard | — (account-level) | - [ ] |
| SES verified sender: `hello@lumin.luxe` | AWS SES → Verified Identities | — | - [ ] |
| SES verified sender: `sync@opp.pub` | AWS SES → Verified Identities | — | - [ ] |
| SES verified sender: `royalties@opp.pub` | AWS SES → Verified Identities | — | - [ ] |
| SES verified sender: `booking@2stepsabovestars.com` + receipt rules | AWS SES → Verified Identities + Receipt Rules | — | - [ ] |
| **Tavily or Brave Search API key** (SBIA) | [tavily.com](https://tavily.com) or [brave.com/search/api](https://brave.com/search/api) | `sbia/web-search-api-key` | - [ ] |
| SBIA followup Lambda ARN | AWS Lambda console | `SBIA_FOLLOWUP_LAMBDA_ARN` in SBIA `.env` | - [ ] |

### Required Before Wave 4 (Public-Facing Agents)

| Credential | Where to Get It | Env Var / SM Key | Status |
|-----------|----------------|------------------|--------|
| Agent 09 SyntaxError fix | `tools/support_tools.py:557` — merge duplicate `ExpressionAttributeValues` | — (code fix, not credential) | - [ ] |
| SNS escalation topic ARN (Agent 09) | AWS SNS console | `SNS_ESCALATION_TOPIC` in Agent 09 `.env` | - [ ] |
| AWS WAF ACL ID | AWS WAF console | `WAF_ACL_ID` in `tools/waf_tools.py:15` | - [ ] |
| CloudFront distribution ID | AWS CloudFront console | `CF_DISTRIBUTION_ID` in `tools/content_tools.py:15` | - [ ] |
| GuardDuty detector ID | `aws guardduty list-detectors` | `DETECTOR_ID` in `tools/guardduty_tools.py:13` | - [ ] |
| SNS security topics (2 ARNs) | AWS SNS console | `.env` lines 15–16 for Agent 10 | - [ ] |
| **Reddit API credentials** | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | - [ ] |
| **TikTok Research API key** (1–2 week approval) | [developers.tiktok.com](https://developers.tiktok.com/products/research-api) — **apply immediately** | `TIKTOK_RESEARCH_API_KEY` | - [ ] |
| **Instagram + Threads OAuth tokens** | Meta Developer portal | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `THREADS_ACCESS_TOKEN` | - [ ] |
| **Twitter/X API v2 write access** (Elevated or Pro tier may be required) | [developer.twitter.com](https://developer.twitter.com) | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET` | - [ ] |
| **TikTok Content API token** | TikTok for Developers | `TIKTOK_ACCESS_TOKEN` | - [ ] |
| **Discord bot token** | [discord.com/developers](https://discord.com/developers) | `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID` | - [ ] |
| **YouTube OAuth token** (Community Posts scope) | Google Cloud Console | `YOUTUBE_OAUTH_TOKEN` | - [ ] |
| `skyblew/voice-book` Secrets Manager secret | AWS Secrets Manager (H.F. + SkyBlew to author content) | `skyblew/voice-book` | - [ ] |

---

## 4. Slack Workspace Readiness

All 10 channels must be created **before** the corresponding agent is deployed. The channel names are canonical — do not abbreviate or modify them. They are the exact names H.F. will look for in the morning workflow.

| Channel | Required Before | Webhook URL Stored | Status |
|---------|----------------|-------------------|--------|
| `#pending-approvals` | Wave 1 | `lumin/slack/pending-approvals-webhook` in Secrets Manager | - [ ] |
| `#cultural-moments` | Wave 2 | `lumin/slack/cultural-moments-webhook` | - [ ] |
| `#sync-queue` | Wave 3 | `lumin/slack/sync-queue-webhook` | - [ ] |
| `#security-ops` | Wave 4 | `lumin/slack/security-ops-webhook` | - [ ] |
| `#hot-leads` | Wave 3 | `lumin/slack/hot-leads-webhook` | - [ ] |
| `#fan-discovery-queue` | Wave 4 | `lumin/slack/fan-discovery-queue-webhook` | - [ ] |
| `#anime-gaming-intel` | Wave 1 | `lumin/slack/anime-gaming-intel-webhook` | - [ ] |
| `#sync-pitches` | Wave 3 | `lumin/slack/sync-pitches-webhook` | - [ ] |
| `#cs-escalations` | Wave 4 | `lumin/slack/cs-escalations-webhook` | - [ ] |
| `#security-alerts` | Wave 4 | `lumin/slack/security-alerts-webhook` | - [ ] |

**Important:** Webhook URLs must be stored in AWS Secrets Manager — **never in git**. The `.gitignore` excludes `.env` files. Verify with `git status` that no `.env` file appears as untracked before any commit.

---

## 5. Infrastructure Decisions Required

These are architectural choices that must be made before provisioning begins. Once infrastructure is provisioned, changing these decisions requires tearing down and rebuilding AWS resources.

### Kinesis vs. DynamoDB Streams (cost impact: ~$250/year)

Agents 01 and 06 each own an inter-agent signal stream. Two options:

| Option | Monthly Cost | Latency | When to Choose |
|--------|-------------|---------|----------------|
| **Kinesis Data Streams** (2 shards) | $21.60 | Seconds | If real-time cultural moment response (<60s) is required at launch |
| **DynamoDB Streams + EventBridge** | ~$0.20 | 1–2 minutes | Recommended for launch — upgrade to Kinesis after 90 days if latency is a bottleneck |

- [ ] Decision made and documented: `[ ] Kinesis` or `[ ] DynamoDB Streams`
- [ ] If DynamoDB Streams: EventBridge Pipe configured to route stream events between agents

### SES Region

- [ ] SES region confirmed: **us-east-1** (must match EC2 instance region for lowest latency)
- [ ] SES production access request submitted (support ticket — 1–3 business days; submit Day 1)

---

## 6. Data Seeding Required Before First Runs

Certain agents require data in DynamoDB tables before their first run produces meaningful output. Missing seeds produce silent failures.

| Agent | Table to Seed | What to Seed | When |
|-------|--------------|--------------|------|
| **Agent 02** | `opp-catalog` | OPP Inc. catalog: titles, ISRCs, genre tags, one-stop clearance status | Before Wave 3 |
| **Agent 05** | `opp-royalty-statements` | Most recent ASCAP, BMI, SoundExchange, MLC statements (manual import) | Before first monthly run |
| **Agent 08** | `opp-catalog` | Elvin Ross / Ronnie Garrett catalog integration status | Before first monthly run |
| **Agent 09** | `ask-lumin-sessions` | Existing AskLumin subscriber records | Before enabling real-time mode |
| **Agent 10** | `security-asset-hashes` | SHA-256 hashes of 5 protected assets (Kid_Sky.png, SkyBlew_Logo_-_No_BG.PNG, SkyBlewUniverseApp.html, index.js, styles.css) | Before first content integrity run |
| **SBIA** | `sbia_conventions` | 22 seed conventions: 12 Tier A (anime/gaming) + 7 Tier B (adjacent) + 3 Tier C (general) | Before first Monday discovery run |
| **SBIA** | `sbia-epk-assets` S3 | 6 EPK files: epk.pdf, skyblew_bio.txt, press_photo_hires.jpg, stage_plot.pdf, rider.pdf, sample_setlist.pdf | Before first live email send |
| **Agent 12** | `skyblew/voice-book` Secrets Manager | SkyBlew Voice Book content (H.F. + SkyBlew to author) | Before first content generation |

---

## 7. Code Fix Required (Pre-Deploy Blocker)

This is the only code change required before deployment. It is a bug, not a feature.

- [ ] **Agent 09 SyntaxError fixed before deployment:**  
  File: `agents/agent-09-customer-success/tools/support_tools.py:557`  
  Issue: Duplicate `ExpressionAttributeValues` keyword argument in a `query()` call.  
  Fix: Merge the two `ExpressionAttributeValues` dicts into a single argument.  
  Verify: `python -c "import importlib; importlib.import_module('tools.support_tools')"` from the agent directory returns no error.  
  Tests: `python -m pytest tests/integration/ -v` — Agent 09 test changes from `XFAIL` to `PASSED`.

---

## 8. Documentation Readiness

These are not technical gates — they are team readiness gates. Deployment that proceeds without the humans understanding the system produces undetected failures.

- [ ] **Eric** has read `audit/agent-09-customer-success.md` in full (the deploy blocker is documented in §2 and §8)
- [ ] **Eric** has read `docs/DEPLOY_PLAN.md` in full — understands the 4-wave deploy order and each wave's verification gate
- [ ] **H.F.** has read `docs/DEPLOY_PLAN.md` in full and has **explicitly approved** the deploy order and kill criteria in §7
- [ ] **H.F.** has read `docs/ROADMAP.md` "Operational Rhythm Post-Deployment" section — understands the 7:00am morning workflow and Sunday Review ritual
- [ ] `docs/EC2_DEPLOYMENT.md` runbook (produced in Prompt P3.8) is available on a second monitor or printed during the Phase 4 session
- [ ] Both H.F. and Eric have reviewed the per-agent dashboard watch items in `docs/DEPLOY_PLAN.md` §6 — they know what "success" looks like for each agent

---

## 9. Sanity Sweep Results (Phase 3.5)

Run these before starting Phase 4. They should all pass on a clean clone of the repo.

| Check | Command | Expected Result |
|-------|---------|----------------|
| Shared library tests | `python -m pytest tests/shared/ -v` | All green (119 tests) |
| Integration smoke tests | `python -m pytest tests/integration/ -v` | 12 passed, 1 xfailed (Agent 09 — known SyntaxError) |
| Git status | `git status` | `nothing to commit, working tree clean` |
| Agent file integrity | Run hash check script (see below) | `92 files checked, 0 missing, 0 drifted` |
| Tag present | `git tag -l` | `v0.3-audit-complete` present |

**Hash check command:**

```bash
python -c "
import json, hashlib, pathlib
with open('audit/baseline-hashes.json') as f:
    baseline = json.load(f)
total, missing, drifted = 0, [], []
for agent_name, files in baseline.items():
    for rel_file, expected_hash in files.items():
        expected = expected_hash.replace('sha256:', '')
        p = pathlib.Path('agents') / agent_name / rel_file
        total += 1
        if not p.exists():
            missing.append(str(p))
        else:
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != expected:
                drifted.append((str(p), expected[:12], actual[:12]))
print(f'{total} files checked, {len(missing)} missing, {len(drifted)} drifted')
if missing: [print(f'  MISSING: {m}') for m in missing]
if drifted: [print(f'  DRIFT: {r}') for r, e, a in drifted]
"
```

---

## 10. Final Gate

- [ ] Every box in sections 1–8 is checked
- [ ] The sanity sweep in section 9 passes cleanly on the EC2 host (not just the dev machine)
- [ ] H.F. has explicitly said "go" for Phase 4

> **Do not start Prompt P4.1 until every box on this checklist is checked.**

---

*Lumin MAS Pre-Deploy Checklist — Phase 3.5 — April 2026*  
*H.F. (CEO) · Eric (CTO) · ask.lumin.luxe*  
*Win for the Artist · Win for the Fan · Win for the World*
