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
