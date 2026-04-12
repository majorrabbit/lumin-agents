# Deployment Readiness Audit — Agent 12: Social Media Director

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-12-social-media` |
| Display name | Social Media Director (Creative Resonance Architect) |
| Entity | 2StepsAboveTheStars LLC |
| Layer | Fan Experience |
| Mission | Every word published under SkyBlew's name is a brushstroke in the world he is painting. Agent drafts, monitors, and analyses. H.F. approves. SkyBlew's authentic voice cannot be automated — it can be assisted. |
| Schedule | Every 15 min (mention monitoring) · Daily (content queue + analytics) · Weekly (Sunday performance review) · Event-driven (Agent 06 cultural moment trigger) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

| File | Location | Placeholder | Required value |
|------|----------|-------------|----------------|
| `.env.example` | Line 6 | `APPLE_MUSIC_CONFIRMED=false` | Set to `true` ONLY after DistroKid confirms MoreLoveLessWar delivery to Apple Music. This is a hard gate — not a placeholder to fill in, but a gate to release when Apple Music delivery is confirmed. |

All platform API token fields in `.env.example` are intentionally blank (no placeholder text). Each token must be obtained separately.

**Platform tokens required (all blank at install):**

| Platform | Token fields |
|----------|-------------|
| Instagram | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` |
| TikTok | `TIKTOK_ACCESS_TOKEN` |
| Twitter/X | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET` |
| YouTube | `YOUTUBE_OAUTH_TOKEN` |
| Discord | `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID` |
| Threads | `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` |

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `skyblew-content-calendar` (`CALENDAR_TABLE`) | Content calendar — scheduled posts by platform and date | Yes |
| DynamoDB table | `skyblew-approval-queue` (`QUEUE_TABLE`) | Drafted content awaiting H.F. approval | Yes |
| DynamoDB table | `skyblew-post-performance` (`PERF_TABLE`) | Post performance metrics after publishing | Yes |
| DynamoDB table | `skyblew-fan-interactions` (`MENTIONS_TABLE`) | Fan mentions, comments, and DMs requiring a response draft | Yes |
| DynamoDB table | `skyblew-analytics` (`ANALYTICS_TABLE`) | Weekly/monthly platform analytics archive | Yes |
| DynamoDB table | `skyblew-fm-am-campaign` (`CAMPAIGN_TABLE`) | FM-AM campaign phase tracking | Yes |
| DynamoDB table | `skyblew-voice-log` (`VOICE_TABLE`) | Voice Book usage log — which prompts produced approved content | Yes |
| Secrets Manager | `skyblew/voice-book` (`SKYBLEW_VOICE_BOOK_SECRET_KEY`) | The SkyBlew Voice Book™ — SkyBlew's authentic creative voice guide | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key | No — shared fleet |

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |
| Instagram Graph API | Meta developer OAuth | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` | — | Meta Developer portal — requires Facebook Page linked to Instagram Business account | 2–3 days |
| TikTok Content API | OAuth | `TIKTOK_ACCESS_TOKEN` | — | TikTok for Developers — requires app creation and content posting scope | 2–3 days |
| Twitter/X API v2 | OAuth 1.0a (write access) | `TWITTER_API_KEY` + 3 secret/token fields | — | developer.twitter.com — Free tier may not allow write access; Elevated or Pro tier needed | 2–5 days |
| YouTube Data API v3 | OAuth 2.0 (Community posts scope) | `YOUTUBE_OAUTH_TOKEN` | — | Google Cloud Console — shared API project with Agents 01/07/11 | < 1 day |
| Discord Bot | Bot token | `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID` | — | discord.com/developers — create bot, invite to SkyBlew Discord server | < 1 day |
| Threads API | Meta developer OAuth | `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` | — | Meta Developer portal (same app as Instagram) | 1–2 days |

**Twitter/X access tier note:** The Twitter/X API's free tier does not reliably support write operations at scale. The Elevated tier ($100/month) or Pro tier is required for consistent content posting. Budget accordingly.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- None. Agent 12's tables feed H.F.'s content calendar and analytics — not other agents.

**Reads from (produced by other agents):**
- **Agent 06 (Cultural Moment Detection)** triggers Agent 12 with cultural moment signals — Agent 12 runs a special content creation pass timed to the moment
- **Agent 07 (Fan Behavior Intelligence)** provides genre affinity and geographic cohort data — Agent 12 uses this for content targeting decisions
- **Agent 11 (Fan Discovery)** surfaces fan art and community interactions that Agent 12 may respond to or amplify (human-approved)

**Signal flow:**
```
Agent 06 (cultural moment) + Agent 07 (fan behavior data)
  → cultural content trigger → Agent 12 (draft + approval queue)
Agent 11 (fan engagement discovery)
  → fan art / interaction signal → Agent 12 (draft reply for H.F. approval)
    → skyblew-approval-queue → H.F. (approval)
    → [approved] → 6 platforms (Instagram, TikTok, Twitter, YouTube, Discord, Threads)
    → skyblew-post-performance (analytics tracking)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report — every-15min monitoring + daily content) | $7.55 |
| DynamoDB — 7 tables, on-demand (~500K R/W ops at 15-min monitoring cadence) | ~$0.75 |
| CloudWatch Logs — high log volume from 15-min cadence | ~$0.25 |
| **Estimated monthly total** | **~$8.55** |

**Highest Claude API cost in the fleet.** Agent 12's 15-minute mention monitoring, multi-platform content generation, voice validation, and campaign analysis combine to produce the highest per-month token usage. Cost scales with posting volume and the number of fan interactions processed.

**Twitter/X API tier cost (not in Claude estimate):** If Twitter/X Elevated or Pro tier is required, add $100–$500/month to the external API budget.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Set up Instagram Graph API (Meta Developer portal) | 2–3 days |
| Set up TikTok Content API | 2–3 days |
| Set up Twitter/X API (may require tier upgrade) | 2–5 days |
| Set up YouTube Community Posts OAuth | < 1 day |
| Set up Discord bot and invite to server | < 1 day |
| Set up Threads API (same Meta app as Instagram) | 1–2 days |
| Create Secrets Manager secret `skyblew/voice-book` and seed with Voice Book content | < 1 day |
| Create DynamoDB tables (7 tables) | < 1 day |
| Resolve Apple Music delivery (`APPLE_MUSIC_CONFIRMED`) | Unblocked externally |
| Deploy agent and run smoke test | ½ day |
| **Total realistic TTL** | **5–7 working days** |

---

## 8. Risk Callouts

1. **Highest Claude API cost in the fleet ($7.55/mo).** Every 15-minute mention scan calls Claude to classify fan interactions. If fan engagement scales (target: 35K → 100K+ monthly listeners), this cost grows proportionally. Build a cost monitoring alert when Claude spend exceeds $15/month for Agent 12.

2. **Apple Music delivery gate blocks MoreLoveLessWar campaigns.** `APPLE_MUSIC_CONFIRMED=false` prevents MoreLoveLessWar social campaigns from launching. The Apple Music issue is the single most operationally urgent item in the 2SATS layer — every day of delay on this is a day of lost first-impression opportunities with new fans discovered by Agent 11.

3. **Six platform API credentials — highest credential surface area in the fleet.** Each platform API has its own OAuth flow, token expiry schedule, rate limits, and terms of service. Token expiry is a silent failure mode: if a platform token expires, posts fail without error-level logging. Implement token expiry monitoring or use a token rotation reminder system.

4. **`skyblew/voice-book` Secrets Manager secret must be seeded before first content generation.** The Voice Book is the creative foundation for all generated content. If the secret is empty or missing, `load_voice_book()` fails and content generation produces generic (off-brand) output. H.F. and SkyBlew must populate the Voice Book in Secrets Manager before Agent 12 is enabled.

5. **Human approval gate must be operationally maintained.** Agent 12 generates content for 6 platforms daily. At 3+ posts/day, the approval queue will accumulate ~100+ items per month. H.F. must commit to a daily review cadence or the queue will back up and the agent's output value collapses. Consider setting a SLA: approvals within 4 hours of generation for time-sensitive cultural moment content.

6. **Threads API uses Meta's same app as Instagram.** Both tokens come from the same Meta Developer app. If the Meta app is rejected or suspended, both Instagram and Threads posting capability go offline simultaneously.

---

## 9. Deployment Checklist

- [ ] Create Instagram Business account and link to Facebook Page; register Meta Developer app
- [ ] Obtain `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` from Meta Developer portal
- [ ] Obtain `THREADS_ACCESS_TOKEN` and `THREADS_USER_ID` (same Meta app as Instagram)
- [ ] Create TikTok developer app and obtain `TIKTOK_ACCESS_TOKEN` with content posting scope
- [ ] Register Twitter/X developer app; verify tier supports write operations; obtain all 4 Twitter credential fields
- [ ] Obtain YouTube OAuth token for Community Posts from Google Cloud Console
- [ ] Create Discord bot, invite to SkyBlew Discord server, set `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID`
- [ ] Create Secrets Manager secret `skyblew/voice-book` and populate with SkyBlew Voice Book content (H.F. + SkyBlew to author)
- [ ] Create DynamoDB tables: `skyblew-content-calendar`, `skyblew-approval-queue`, `skyblew-post-performance`, `skyblew-fan-interactions`, `skyblew-analytics`, `skyblew-fm-am-campaign`, `skyblew-voice-log` (on-demand billing)
- [ ] Configure Slack webhooks (`SLACK_APPROVAL_WEBHOOK`, `SLACK_SOCIAL_WEBHOOK`) and verify test messages post
- [ ] Resolve MoreLoveLessWar Apple Music delivery and set `APPLE_MUSIC_CONFIRMED=true`
- [ ] Run `python scripts/run_agent.py agent-12-social-media content_queue` and verify clean JSON response
- [ ] Verify a drafted post appears in `skyblew-approval-queue` and routes correctly to the approval Slack channel
- [ ] Test one full cycle: draft → H.F. approves → `post_approved_message()` → `log_post_performance()`
- [ ] Install and enable systemd timer for 15-minute monitoring cadence
