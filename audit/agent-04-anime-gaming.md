# Deployment Readiness Audit — Agent 04: Anime & Gaming Market Scout

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-04-anime-gaming` |
| Display name | Anime & Gaming Market Scout |
| Entity | OPP Inc. + 2StepsAboveTheStars LLC |
| Layer | Revenue Operations |
| Mission | Monitor anime production announcements and game audio briefs worldwide — find every opportunity where SkyBlew's Rhythm Escapism™ sound belongs before anyone else gets there. |
| Schedule | Weekly (daily scout run) · Monthly (opportunity pipeline review) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

No hardcoded placeholder strings found in `agent.py`. The `.env.example` is clean — all values are either real defaults or clearly blank for the operator to fill in.

**Operational note:** The partner contact data embedded in `get_spine_sounds_pipeline()` (line ~187) references `info@spinesounds.com` and `japan-animemusic.com`. These are real-world contacts. Verify both are current before first live pitch run.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `anime-gaming-opportunities` (`SCOUT_TABLE`) | Scouted anime and gaming opportunities with match scores | Yes |
| DynamoDB table | `anime-gaming-pitches` (`AG_PITCHES_TABLE`) | Pitch drafts queued for H.F. approval | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

**Note:** Agent 04 uses `import anthropic` directly inside `generate_anime_pitch()` (inline client call, not via Strands). This is the same pattern as Agent 03. Both DynamoDB tables are owned exclusively by Agent 04 — no other agent reads from them.

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |

**Note:** Agent 04 does not call any third-party anime or gaming data APIs directly. It uses web research via `requests` (httpx equivalent) and Claude synthesis to discover opportunities. The Spine Sounds and JAM LAB pipeline checks are manual email-based workflows — no API credentials required.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Agent 04's `anime-gaming-opportunities` and `anime-gaming-pitches` tables are consumed only by H.F. for human review — no downstream agent reads from them.

**Reads from (produced by other agents):**
- None direct. Agent 04 operates independently, scanning external sources for opportunities.

**Signal flow:**
```
External sources (ANN, Crunchyroll, IGDB, Spine Sounds partner email)
  → Agent 04 (opportunity scoring + pitch draft)
    → anime-gaming-opportunities → H.F. (manual review)
    → anime-gaming-pitches → H.F. (approval queue)
```

**Note:** The architecture guide lists Agent 04 as one of the agents that reads demand signals from Agents 1, 2, 4, and 6. In the current code, Agent 04 does not read from other agents' DynamoDB tables. This integration is planned for a future phase.

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — weekly scout + pitch generation) | $0.31 |
| DynamoDB — 2 tables, on-demand (~50K R/W ops) | ~$0.08 |
| CloudWatch Logs | ~$0.03 |
| **Estimated monthly total** | **~$0.42** |

**Cost profile:** Agent 04 is the lowest-cost agent in the fleet. It runs once daily, exits early most days (no new Tier 1 opportunities), and only calls Claude for pitch generation when a score ≥ 8 opportunity is found.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Create DynamoDB tables (2 tables) | < 1 day |
| Configure Slack webhook (`SLACK_AG_WEBHOOK`) | < 1 day |
| Deploy agent and run smoke test | ½ day |
| Verify Spine Sounds and JAM LAB contact info is current | 1 day |
| **Total realistic TTL** | **1–2 working days** |

**Fastest deployment in the fleet.** No paid API subscriptions, no SES verification, no external OAuth flows required.

---

## 8. Risk Callouts

1. **Hardcoded partner contact data.** The `get_spine_sounds_pipeline()` tool (lines ~186–197) returns hardcoded contact info for Spine Sounds and JAM LAB Japan. These are real-world relationships that change. Verify contacts are current before deployment and add a quarterly review reminder.

2. **No actual API integration for discovery.** The production comment in `scan_anime_announcements()` (line ~74) says "In production: pull from ANN RSS + Crunchyroll API + Spine Sounds partner feed." The current code returns synthetic hardcoded data. At go-live, H.F. should understand that Agent 04 is not yet reading live data — it's drafting pitches from a curated starting set. Real-time scanning is a Phase 4 enhancement.

3. **Direct `anthropic` client call in pitch generation.** `generate_anime_pitch()` (line ~217) uses `import anthropic` and creates a direct Anthropic client rather than using the Strands agent. This is intentional (separate lightweight call) but means this function is not covered by the Strands retry/error handling. If the API call fails, the error is caught and returned as JSON — acceptable for a draft pitch generator.

---

## 9. Deployment Checklist

- [ ] Create DynamoDB tables: `anime-gaming-opportunities`, `anime-gaming-pitches` (on-demand billing)
- [ ] Configure Slack webhook (`SLACK_AG_WEBHOOK`) and test that scout alerts post to #anime-gaming-intel
- [ ] Verify Spine Sounds Tokyo contact (`info@spinesounds.com`) is current
- [ ] Verify JAM LAB Japan contact info is current (check `japan-animemusic.com`)
- [ ] Run `python scripts/run_agent.py agent-04-anime-gaming daily_scout` and verify clean JSON response
- [ ] Confirm at least one Tier 1 opportunity (score ≥ 8) triggers a Slack alert in the smoke test
- [ ] Install and enable systemd timer for weekly Monday scan
- [ ] Review synthetic opportunity data in `scan_anime_announcements()` and `scan_game_releases()` — replace with live data sources in Phase 4

---

## 10. Dashboard Watch Items (Operator Acceptance Criteria)

*Source: Lumin Agent Fleet Operations Guide, Section III — Agent 04 profile (April 2026)*

### 👁 What to Watch on Your Dashboard

**Match scores of 9-10: these are the deployments to act on immediately. The Spine Sounds Tokyo pipeline status — this is the Japan market gateway. Any Adult Swim, Netflix anime, or Major JRPG opportunity.**

### Canonical Slack Channel

**`#anime-gaming-intel`** — daily scan summaries and any score-8+ opportunity triggers an immediate alert. H.F. reviews asynchronously (not part of the 7:00am–8:15am morning window — check during the workday when time permits). Score 9-10 opportunities should be treated as time-sensitive and reviewed within the business day.

### Expected Cadence of Visible Output

| Output | Frequency |
|--------|-----------|
| Daily scan summary to `#anime-gaming-intel` | Daily |
| Score 8+ opportunity immediate alert | Only when a qualifying opportunity is found |
| Score 9-10 "act now" alert | Rare — highest-priority, Adult Swim / Netflix / major JRPG only |
| Spine Sounds Tokyo status check | Weekly |

H.F. should see **at least one daily message** from `#anime-gaming-intel` even on quiet days ("no new Tier 1 opportunities"). Silence for 2+ days indicates the agent is not running.

### First 48 Hours — Acceptance Criteria

- [ ] First daily scout run completes within 24 hours of deployment and logs to CloudWatch
- [ ] A scan summary (even "no new Tier 1 opportunities today") posts to `#anime-gaming-intel` within 24 hours
- [ ] At least one record written to `anime-gaming-opportunities` table after the first run
- [ ] systemd timer active for daily scout run
- [ ] Inject a test event with a score 8+ opportunity and verify an immediate Slack alert fires to `#anime-gaming-intel` with the project details and match rationale
- [ ] Spine Sounds Tokyo contact (`info@spinesounds.com`) is verified as reachable

### Red Flags

- **No daily summary in `#anime-gaming-intel` for 2+ consecutive days** — agent is not running; check systemd timer (`journalctl -u lumin-agent-04-anime-gaming.timer`) and CloudWatch.
- **Score 9-10 opportunity appears in DynamoDB table but no Slack alert fires** — webhook may have expired; test the `SLACK_AG_WEBHOOK` immediately.
- **Spine Sounds Tokyo pipeline shows no updates for 4+ weeks** — contact may be stale; verify `info@spinesounds.com` is still the correct address.
- **All opportunities scoring 5-7 with no 8+ scores** — the synthetic data at launch will show some 8+ scores; if live data integration (Phase 4) produces only mid-range scores, the match criteria may need recalibration.

### Inter-Agent Dependency Note (Section VII Cross-Reference)

**ADDITION — not in original audit §5:**  
The Operations Guide Section VII interaction map documents **Agent 04 → Agent 08**: "Anime/gaming demand signals feed catalog gap analysis." This connection was not present in the original audit §5 (which stated "Writes to: None"). This integration does not exist in the current Agent 04 code. It is planned for Phase 6 (Intelligence Network Activation).

Updated signal flow (Phase 6 target):
```
External sources (ANN, Crunchyroll, IGDB, Spine Sounds)
  → Agent 04 (opportunity scoring + pitch draft)
    → anime-gaming-opportunities → H.F. (manual review)
    → [Phase 6] demand signal → Agent 08 (catalog gap analysis)
```
