# Deployment Readiness Audit — Agent 11: Fan Discovery & Outreach

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-11-fan-discovery` |
| Display name | Fan Discovery & Outreach Agent |
| Entity | 2StepsAboveTheStars LLC |
| Layer | Fan Experience |
| Mission | Find everyone who should love SkyBlew — then introduce them, authentically, one community at a time. Never post anything without human approval. |
| Schedule | Daily (morning discovery scan + outreach queue generation + evening conversion report) · Weekly (community priority ranking) · Event-driven (Agent 06 cultural moment trigger) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py` or any tool file. The `.env.example` is clean — all API key fields are blank with clear instructions.

**Pre-deploy operational gate:** The distribution health check task (`run_distribution_health_check`) verifies MoreLoveLessWar is live on Apple Music before any outreach campaign launches. The Apple Music delivery issue is tracked in Agent 12's `APPLE_MUSIC_CONFIRMED` gate. Do not launch fan outreach for MoreLoveLessWar until this gate clears.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `fan-discovery-outreach-queue` (`OUTREACH_QUEUE_TABLE`) | Drafted outreach messages awaiting H.F. approval | Yes |
| DynamoDB table | `fan-discovery-communities` (`COMMUNITIES_TABLE`) | Discovered communities with engagement and conversion metadata | Yes |
| DynamoDB table | `fan-discovery-entry-points` (`ENTRY_POINTS_TABLE`) | Individual community posts/threads flagged as entry opportunities | Yes |
| DynamoDB table | `fan-discovery-conversions` (`CONVERSIONS_TABLE`) | Conversion tracking: post → stream/install/purchase | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |
| Secrets Manager | `lumin/chartmetric-api-key` | Chartmetric for streaming context in discovery | No — shared with Agents 01, 07, 10 |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| Reddit API | OAuth2 client credentials | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | — | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) — free, instant approval | < 1 day |
| YouTube Data API v3 | API key | `YOUTUBE_API_KEY` | `lumin/youtube-api-key` | Google Cloud Console — shared with Agents 01, 07 | < 1 day |
| TikTok Research API | API key (application approval required) | `TIKTOK_RESEARCH_API_KEY` | — | Apply at developers.tiktok.com/products/research-api — takes 1–2 weeks for approval | 1–2 weeks |
| Chartmetric | API key | `CHARTMETRIC_API_KEY` | `lumin/chartmetric-api-key` | chartmetric.com — paid subscription (shared) | 1–2 days |

**TikTok Research API is the longest lead-time item.** TikTok requires a developer account, a research project description, and organizational verification. Without it, the `scan_tiktok_hashtags()` tool will not function — and #nujabes (800M+ views) is the single highest-density fan discovery surface in the plan. Apply for TikTok Research API access immediately upon project kickoff.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `fan-discovery-conversions` → **Agent 07 (Fan Behavior Intelligence)** reads conversion data via `export_utm_conversion_feed()` to calibrate which communities are producing highest-CLV fans

**Reads from (produced by other agents):**
- **Agent 07** provides CLV by cohort and geo ranking data — Agent 11 uses this to prioritize which communities to target first
- **Agent 06 (Cultural Moment Detection)** triggers Agent 11 with a cultural moment signal — Agent 11 runs an event-driven discovery scan timed to the moment

**Signal flow:**
```
Agent 06 (cultural moment trigger)
  → event → Agent 11 (discovery scan timed to moment)
Agent 07 (CLV ranking)
  → community prioritization → Agent 11 (morning discovery queue)
    → fan-discovery-outreach-queue → H.F. (approval)
    → fan-discovery-conversions → Agent 07 (CLV calibration feedback)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — daily scans + outreach generation) | $2.57 |
| DynamoDB — 4 tables, on-demand (~300K R/W ops) | ~$0.45 |
| CloudWatch Logs | ~$0.15 |
| **Estimated monthly total** | **~$3.17** |

**Cost profile:** Agent 11 has the second-highest Claude API cost among the non-social-media agents. Each daily discovery scan involves multiple platform scans plus outreach message generation with 3 variants per entry point. Cost scales with the number of entry points discovered per day — higher-quality discovery = more Claude calls.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Register Reddit developer app (free, instant) | < 1 day |
| Obtain YouTube Data API key (shared with Agent 01) | < 1 day |
| **Apply for TikTok Research API (1–2 week approval)** | **7–14 days** |
| Provision Chartmetric API (shared with Agent 01) | 1–2 days |
| Create DynamoDB tables (4 tables) | < 1 day |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **7–14 working days** |

**TikTok Research API governs the timeline.** All other steps can complete in 2–3 days. The agent can be deployed and functional with Reddit + YouTube discovery while awaiting TikTok approval, but #nujabes outreach (the highest-ROI discovery surface) will not be available until TikTok access is granted.

---

## 8. Risk Callouts

1. **TikTok Research API approval is the longest lead time in the fan-facing tier.** The application requires a research project justification and organizational credentials. Submit the application as early as possible — during infrastructure setup, not after. TikTok #nujabes (800M+ views) is the primary discovery surface for SkyBlew's core audience.

2. **Human approval gate is architecturally enforced.** Agent 11's `submit_for_human_approval()` tool is the only path for outreach messages to leave the draft queue. This is a deliberate design constraint — SkyBlew's authentic voice requires H.F. review. Ensure H.F. has a clear process for reviewing the daily approval queue (expected volume: 3–10 messages/day at launch).

3. **Apple Music delivery gate.** The system prompt and `run_distribution_health_check()` task both check whether MoreLoveLessWar is live on Apple Music before running outreach. If Apple Music delivery is not confirmed (`APPLE_MUSIC_CONFIRMED=false` in Agent 12), running fan discovery for MoreLoveLessWar wastes first-impression opportunities. Apple Music delivery should be resolved before Agent 11 campaigns for that album.

4. **Reddit rate limits.** Reddit's API enforces 60 requests/minute for OAuth2 apps. The `scan_reddit_communities()` tool scans multiple subreddits per run. Verify request volume stays within limits, especially during cultural moment event-driven scans that may scan many communities simultaneously.

---

## 9. Deployment Checklist

- [ ] **Apply for TikTok Research API** at developers.tiktok.com/products/research-api (7–14 day wait — do this first)
- [ ] Register Reddit developer app at reddit.com/prefs/apps; set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`
- [ ] Set `REDDIT_USER_AGENT=LuminFanDiscovery/1.0 (by /u/SkyBlewOfficial)` in `.env`
- [ ] Obtain YouTube Data API key from Google Cloud Console (shared with Agents 01, 07)
- [ ] Provision Chartmetric API key (shared with Agents 01, 07, 10)
- [ ] Create DynamoDB tables: `fan-discovery-outreach-queue`, `fan-discovery-communities`, `fan-discovery-entry-points`, `fan-discovery-conversions` (on-demand billing)
- [ ] Configure Slack webhook (`SLACK_DISCOVERY_WEBHOOK`) and verify test message posts
- [ ] Run distribution health check: `python scripts/run_agent.py agent-11-fan-discovery distribution_health_check`
- [ ] Confirm Apple Music delivery status for MoreLoveLessWar before enabling MoreLoveLessWar outreach
- [ ] Run `python scripts/run_agent.py agent-11-fan-discovery morning_discovery` and verify clean JSON response
- [ ] Confirm at least one entry point is logged to `fan-discovery-entry-points` and routed to `fan-discovery-outreach-queue`
- [ ] Install and enable systemd timers for 06:00, 07:00, and 22:00 UTC daily runs

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 11 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**The daily opportunity queue: this is the most time-sensitive item in your morning workflow. The top-converting communities: r/BombRushCyberfunk and r/nujabes should appear here within the first two weeks of operation. Any community achieving >15% conversion rate — these are the relationships worth a direct partnership conversation.**

### Canonical Slack Channel

**`#fan-discovery-queue`** — H.F. checks at **8:15am** in the morning workflow. This is the last stop in the morning review. The daily queue contains 5–15 outreach opportunities, each with 3 message variants and the community context. H.F. selects which to approve, edit, or decline. **`#pending-approvals`** receives URGENT outreach when Agent 06 fires a MoreLoveLessWar cultural moment (Agent 11 activates to full deployment mode across all communities simultaneously).

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Daily opportunity queue to `#fan-discovery-queue` | Daily 07:00 UTC (morning generation) |
| Evening conversion report | Daily 22:00 UTC |
| Community ranking update | Weekly |
| Cultural moment event-driven outreach to `#pending-approvals` | When Agent 06 fires a MoreLoveLessWar PEAK signal |

### First 48 Hours — Acceptance Criteria

- [ ] First 06:00 UTC discovery scan runs and logs to CloudWatch with no `"error"` key
- [ ] Daily 07:00 UTC opportunity generation run produces at least 3 outreach opportunities in `fan-discovery-outreach-queue` table
- [ ] Opportunities appear in `#fan-discovery-queue` with 3 message variants each and approve/decline buttons
- [ ] **Approval gate verified**: confirm that no outreach message is posted to any community platform without H.F. explicitly approving it — check that `submit_for_human_approval()` is the only path for a message to leave the draft queue
- [ ] Distribution health check task runs and correctly flags MoreLoveLessWar Apple Music delivery status (gate must show `APPLE_MUSIC_CONFIRMED=false` until DistroKid confirms)
- [ ] Reddit API is functional: at least one Reddit community appears in the morning scan results
- [ ] systemd timers confirmed active for 06:00, 07:00, and 22:00 UTC runs
- [ ] **r/BombRushCyberfunk and r/nujabes appear in the first week's discovery results** — per Operations Guide §III, these are the expected top-converting communities and should surface within the first two weeks

### Red Flags

- **No opportunities in `#fan-discovery-queue` for 3+ consecutive days** — discovery scan may be rate-limited; check Reddit API quota (60 requests/minute), YouTube API quota, and TikTok Research API status (if approved).
- **An outreach message is posted to a community platform without H.F. approval** — this is a BDI-O Obligation violation. Pause Agent 11 immediately. Audit all community post logs for unauthorized entries.
- **r/BombRushCyberfunk and r/nujabes do not appear in discovery results within 2 weeks** — these subreddits are the highest-ROI discovery surfaces in the plan; their absence suggests Reddit scanning logic is not targeting the correct subreddits.
- **TikTok #nujabes results absent from queue** — TikTok Research API may not yet be approved (1–2 week wait); acceptable at launch, but flag as an operational gap while awaiting approval.
- **Conversion rate for all communities shows 0%** — UTM tracking pipeline to Agent 07 may be broken; verify `fan-discovery-conversions` table is receiving records and that UTM links are correctly formatted.
- **MoreLoveLessWar outreach launches before Apple Music delivery is confirmed** — this wastes first-impression opportunities; the gate must hold until `APPLE_MUSIC_CONFIRMED=true`.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**ADDITION — not in original audit §5:**  
The Operations Guide Section VII interaction map documents **Agent 11 → Agent 12**: "Fan art detections surface for resharing." The original audit §5 did not list Agent 12 as a consumer of Agent 11's outputs. Agent 12's audit §5 does mention it ("Agent 11 surfaces fan art and community interactions"), confirming this is a real connection — but Agent 11's audit missed the reverse direction. This integration is not yet explicitly coded in Agent 11 — it appears to be handled via Agent 12 polling `fan-discovery-entry-points` for fan art flags. Phase 6 target for explicit trigger.

Confirmed connections from Operations Guide (also in audit §5):
- **Agent 06 → Agent 11**: cultural moment signal triggers event-driven discovery — confirmed ✓
- **Agent 07 → Agent 11**: CLV ranking data prioritizes community targets — confirmed ✓
- **Agent 11 → Agent 07**: UTM conversion data closes the learning loop — confirmed ✓
- **Agent 11 → Agent 12** [ADDITION]: fan art detections surface for resharing — in Agent 12 §5 but missing from Agent 11 §5; Phase 6 explicit trigger target
