# Deployment Readiness Audit — Agent 06: Cultural Moment Detection

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-06-cultural` |
| Display name | Cultural Moment Detection Agent |
| Entity | OPP Inc. / 2StepsAboveTheStars (all three entities) |
| Layer | Fan Experience |
| Mission | Detect cultural moments 2–4 hours before they peak in mainstream coverage, match OPP catalog to them, and trigger Agents 02, 03, 11, and 12 while the window is still open. |
| Schedule | Every 30 minutes (continuous entropy scan) · Event-driven (Agent 01 entropy baseline update) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py`. The `.env.example` is clean.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `cultural-moments` (`MOMENTS_TABLE`) | Active cultural moments with convergence scores and catalog matches | Yes |
| DynamoDB table | `cultural-entropy-log` (`ENTROPY_TABLE`) | Shannon entropy convergence time series | Yes |
| Kinesis Data Stream | `cultural-signal-stream` | Outbound trigger signals to Agents 02, 03, 11, 12 | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

**Note:** The `cultural-entropy-log` table is also read by **Agent 01** to calibrate its Boltzmann/entropy thresholds. Agent 06 owns this table but Agent 01 consumes it.

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |

**Note:** Agent 06 does not connect directly to Twitter/X Streaming API, Reddit, TikTok Research API, or Google Trends at launch. The `scan_trending_topics()` tool currently returns curated synthetic data representative of real trending patterns. Live platform API integration is a Phase 4 enhancement. At launch, the entropy math and catalog-matching logic are fully functional — only the data source is synthetic.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `cultural-moments` → **Agents 02, 03, 11, 12** receive cultural moment triggers (via Kinesis `cultural-signal-stream` or DynamoDB event)
- `cultural-entropy-log` → **Agent 01** reads entropy baseline data for Boltzmann threshold calibration

**Reads from (produced by other agents):**
- **Agent 01** provides entropy/temperature baseline signals via `resonance-model-params` table — Agent 06 uses these to calibrate what "normal" entropy looks like vs. a genuine cultural spike

**Signal flow:**
```
Agent 01 (Boltzmann baseline)
  → entropy calibration → Agent 06 (moment detection)
    → cultural-moments → Agents 02, 03, 11, 12 (triggered actions)
    → cultural-entropy-log → Agent 01 (feedback loop)
```

**Agent 06 is the fleet's cultural hub.** Four agents (02, 03, 11, 12) depend on it for event-driven triggers. It is also in a bidirectional feedback loop with Agent 01. Deploy Agent 01 first, then Agent 06, then Agents 02/03/11/12.

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — every-30min cadence) | $1.28 |
| DynamoDB — 2 tables, on-demand (~300K R/W ops at 30-min cadence) | ~$0.45 |
| Kinesis Data Stream — `cultural-signal-stream` (1 shard) | $10.80 |
| CloudWatch Logs | ~$0.15 |
| **Estimated monthly total** | **~$12.68** |

**Dominant cost:** Kinesis `cultural-signal-stream` ($10.80) accounts for 85% of this agent's cost — the same pattern as Agent 01's `resonance-raw-stream`. If the inter-agent trigger mechanism is implemented via DynamoDB streams instead of Kinesis, monthly cost drops to ~$1.88. Evaluate before provisioning.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Create DynamoDB tables (2 tables) | < 1 day |
| Create Kinesis `cultural-signal-stream` (1 shard) | < 1 day |
| Deploy agent and run smoke test | ½ day |
| Verify Agent 01 is deployed (dependency for entropy calibration) | Parallel with Agent 01 TTL |
| **Total realistic TTL** | **1–2 working days** (after Agent 01 is live) |

---

## 8. Risk Callouts

1. **Kinesis cost vs. DynamoDB alternative.** Two agents (01 and 06) each own a Kinesis shard at $10.80/month. Together they contribute $21.60/month to the fleet's AWS bill — more than all other non-Kinesis AWS resources combined. Both streams serve as event buses for inter-agent triggers. DynamoDB Streams + EventBridge achieves the same result at ~$0.10/month. Flag for architecture review before provisioning.

2. **30-minute cadence at launch with synthetic data.** Running every 30 minutes against synthetic trend data means Agent 06 will never detect a real cultural moment until live platform APIs are wired in. At launch, the agent will faithfully fire every 30 minutes, process its hardcoded sample topics, and post sample alerts to Slack. H.F. should treat Agent 06 as "warming up" until Phase 4 adds real data sources.

3. **Four downstream agents depend on Agent 06's triggers.** If Agent 06 is misconfigured or fails silently, Agents 02, 03, 11, and 12 lose their event-driven trigger path. They will still run on their scheduled cycles but will miss culturally-timed opportunities. Monitor Agent 06's CloudWatch logs as a fleet health proxy.

4. **MoreLoveLessWar is a standing Tier 1 match** for any global peace/conflict moment (per system prompt). This means any significant conflict or peace news event will trigger Agent 06 to immediately alert H.F. and trigger catalog match recommendations. Ensure the Slack channel for cultural alerts is monitored — these windows close in 2–4 hours.

---

## 9. Deployment Checklist

- [ ] Create DynamoDB tables: `cultural-moments`, `cultural-entropy-log` (on-demand billing)
- [ ] Decide: Kinesis `cultural-signal-stream` vs. DynamoDB Streams for inter-agent triggers (cost decision)
- [ ] If using Kinesis: create `cultural-signal-stream` (1 shard, us-east-1)
- [ ] Configure Slack webhook (`SLACK_CULTURAL_WEBHOOK`) and test that moment alerts post
- [ ] Deploy Agent 01 first — Agent 06 needs the entropy baseline from `resonance-model-params`
- [ ] Run `python scripts/run_agent.py agent-06-cultural scan_trending` and verify JSON response with entropy scores
- [ ] Verify that at least one PEAK moment triggers a catalog match recommendation in the smoke test
- [ ] Install and enable systemd timer for 30-minute cadence
- [ ] Confirm the first real run writes at least one record to `cultural-moments`
- [ ] Wire Agent 06 trigger → Agents 02, 03, 11, 12 (Phase 6 integration task)

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Sections III and IV — Agent 06 profile + Central Signal Chain (April 2026)*

### 👁 What to Watch on Your Dashboard

**The convergence score and stage for any active cultural moments. How many times per week it fires for MoreLoveLessWar topics — this is a key health indicator for the song's cultural relevance. Whether the downstream agents (2, 3, 11, 12) are executing their responses within the window.**

### Canonical Slack Channel

**`#cultural-moments`** — H.F. checks at **7:15am** in the morning workflow. Any FORMING (convergence ≥ 0.50) or PEAK moment appears here. MoreLoveLessWar content queued by this trigger must be approved **within 2–4 hours** — the cultural window closes. The `#pending-approvals` channel receives the downstream content from Agents 11 and 12 that Agent 06's signal activated.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| 30-minute entropy scan (CloudWatch) | Every 30 minutes, 24/7 |
| `#cultural-moments` Slack alert | Only when convergence ≥ 0.50 (FORMING) or ≥ 0.80 (PEAK) — expected 0–5 per week |
| MoreLoveLessWar STANDING TIER 1 trigger | Any time a peace/conflict/unity/healing topic reaches any stage |
| URGENT PEAK alert (2-4 hour window) | When a moment reaches PEAK stage |

Agent 06 runs **every 30 minutes, 24 hours a day** — it is the most frequent agent in the fleet. The absence of `#cultural-moments` activity for a full week is meaningful, not a failure — it means no qualifying moments were detected.

### First 48 Hours — Acceptance Criteria

- [ ] First 30-minute scan runs within 30 minutes of deployment and logs to CloudWatch
- [ ] At least one `cultural-moments` DynamoDB record written after the first run
- [ ] A test FORMING-stage moment posts to `#cultural-moments` in the smoke test (inject a convergence score ≥ 0.50)
- [ ] A test PEAK-stage moment generates URGENT flag and posts to `#cultural-moments` with the 2–4 hour window warning
- [ ] MoreLoveLessWar triggers an immediate alert regardless of convergence score (STANDING TIER 1 designation verified)
- [ ] systemd timer active for every-30-minute scan cadence

#### T+0:00 to T+0:30 Activation Chain (Section IV — Central Signal Chain)

When Agent 06 detects a PEAK cultural moment, the following downstream sequence must execute within 30 minutes. **This chain must be verified end-to-end before the deployment is considered successful:**

| Time | What Must Happen |
|------|-----------------|
| **T+0:00** | Agent 06 fires. Entropy convergence ≥ 0.80. Alert posted to `#cultural-moments` with catalog match and URGENT flag. |
| **T+0:01** | Agent 02 receives the trigger and immediately scans all platforms for open briefs matching the moment's theme. If found: URGENT submission package queued to `#pending-approvals`. |
| **T+0:02** | Agent 03 receives the trigger and identifies which supervisors are working on relevant projects. Pitch variants queued to `#pending-approvals`. |
| **T+0:05** | Agent 11 receives the trigger and generates community outreach messages for the relevant fan segments. Variants queued to `#fan-discovery-queue`. |
| **T+0:10** | Agent 12 receives the trigger and generates content for all 6 platforms. Queued to `#pending-approvals` with URGENT flag. |
| **T+0:30** | H.F. sees a bundled `#cultural-moments` digest: "Cultural Moment PEAK: [topic]. MoreLoveLessWar activated across 4 agents. [N] items queued for your approval." |

**Note:** At Phase 2 deployment, the T+0 chain is wired but the downstream agents (02, 03, 11, 12) are on their own scheduled cycles — true real-time inter-agent triggering is a Phase 6 integration target. Verify the chain is functional before Phase 6 activation.

### Red Flags

- **Agent 06 fires fewer than once per week for MoreLoveLessWar topics** — this is the guide's explicit health indicator for the song's cultural relevance. If no MoreLoveLessWar triggers fire in 2 weeks, check whether the standing TIER 1 designation is correctly configured in the system prompt.
- **FORMING/PEAK moment fires but downstream agents (02, 03, 11, 12) do not respond within the documented windows** — the inter-agent trigger chain is broken; investigate whether Kinesis or DynamoDB Streams trigger mechanism is functional.
- **Agent 06 generates >5 false-positive FORMING alerts per week for 3 consecutive weeks** — entropy threshold may be too sensitive; reduce the convergence floor and review entropy convergence parameters with Eric.
- **`cultural-entropy-log` table stops being written** — Agent 01 will lose its feedback loop calibration signal; both agents become uncalibrated simultaneously.
- **30-minute timer gap > 60 minutes in CloudWatch** — systemd timer has failed; the fleet's cultural hub is offline.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

The Operations Guide interaction map (Section VII) confirms:
- **Agent 01 → Agent 06**: entropy baseline calibration — confirmed in audit §5 ✓
- **Agent 06 → Agents 02, 03, 11, 12**: cultural moment signal activates all four simultaneously — confirmed in audit §5 ✓
- **Agent 06 → Agent 01** (feedback loop via `cultural-entropy-log`): confirmed in audit §5 ✓

No discrepancies between the Operations Guide and audit §5. Agent 06 is the only agent with the bidirectional feedback loop with Agent 01.
