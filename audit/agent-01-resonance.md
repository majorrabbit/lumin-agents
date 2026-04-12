# Deployment Readiness Audit — Agent 01: Resonance Intelligence

**Generated:** Phase 3.1 — April 2026  
**Auditor:** Claude Code (automated audit from source)

---

## 1. Identity

| Field | Value |
|-------|-------|
| Folder | `agents/agent-01-resonance` |
| Display name | Resonance Intelligence Agent |
| Entity | Lumin Luxe Inc. |
| Layer | Strategic Intelligence |
| Mission | Transform streaming data into Boltzmann/entropy-based, investor-grade predictions via walk-forward Brier backtesting. |
| Schedule | Hourly (data collection) · Daily 02:00 UTC (physics update) · Sundays 04:00 UTC (backtest) · Every 4h (trend alert check) |
| ADK status | Complete — ZIP delivered |

---

## 2. Code Placeholders That Must Be Replaced

| File | Line | Placeholder | Required value |
|------|------|-------------|----------------|
| `.env.example` | 13 | `SNS_RESONANCE_TOPIC=arn:aws:sns:us-east-1:ACCOUNT:lumin-resonance-alerts` | Replace `ACCOUNT` with the 12-digit AWS account ID (e.g., `123456789012`) |

No hardcoded placeholders found in `agent.py` or any `tools/*.py` file. The `ACCOUNT` token appears only in the `.env.example` comment-style default value. At runtime, the agent reads the env var `SNS_RESONANCE_TOPIC`, so this becomes a configuration error only if the `.env` is copied verbatim from `.env.example` without substitution.

---

## 3. AWS Resources Required

| Resource type | Name / Default | Purpose | Owned by this agent? |
|---------------|---------------|---------|----------------------|
| DynamoDB table | `resonance-model-params` (`MODEL_TABLE`) | Boltzmann distribution outputs and model parameters | Yes |
| DynamoDB table | `resonance-trend-signals` (`SIGNALS_TABLE`) | Active phase-transition signals with confidence scores | Yes |
| DynamoDB table | `resonance-backtest-log` (`BACKTEST_TABLE`) | Walk-forward backtest results and Brier score archive | Yes |
| DynamoDB table | `resonance-predictions` (`PREDICT_TABLE`) | Timestamped predictions stored before outcomes are known | Yes |
| Kinesis Data Stream | `resonance-raw-stream` (`KINESIS_STREAM`) | Real-time streaming data ingestion from Chartmetric/Spotify/YouTube | Yes |
| S3 bucket | `lumin-backtest-archive` (`S3_BACKTEST_BUCKET`) | Compressed backtest archives for investor audit trail | Yes |
| SNS topic | `lumin-resonance-alerts` (`SNS_RESONANCE_TOPIC`) | High-confidence phase-transition alerts to H.F. | Yes |
| Secrets Manager | `lumin/anthropic-api-key` | Claude API key (fallback if env var absent) | No — shared fleet |
| Secrets Manager | `lumin/chartmetric-api-key` | Chartmetric streaming data API | No — shared with Agent 7 |
| Secrets Manager | `lumin/spotify-oauth-token` | Spotify Web API access | No — shared |
| Secrets Manager | `lumin/youtube-api-key` | YouTube Data API v3 | No — shared with Agent 11 |
| Secrets Manager | `lumin/soundcharts-api-key` | Soundcharts radio airplay data | Yes |

**Create order:** Kinesis stream → DynamoDB tables (4) → S3 bucket → SNS topic → Secrets Manager secrets.

---

## 4. External APIs and Credentials Needed

| Service | Auth method | Env var | SM key | How to obtain | Est. time |
|---------|-------------|---------|--------|---------------|-----------|
| Chartmetric | API key | `CHARTMETRIC_API_KEY` | `lumin/chartmetric-api-key` | [chartmetric.com/api](https://chartmetric.com) — paid subscription required | 1–2 days |
| Spotify Web API | OAuth client credentials | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | `lumin/spotify-oauth-token` | [developer.spotify.com](https://developer.spotify.com) — free, instant approval | < 1 day |
| YouTube Data API v3 | API key | `YOUTUBE_API_KEY` | `lumin/youtube-api-key` | [console.cloud.google.com](https://console.cloud.google.com) — enable YouTube Data API v3, free quota | < 1 day |
| Soundcharts | API key | `SOUNDCHARTS_API_KEY` | `lumin/soundcharts-api-key` | [soundcharts.com](https://soundcharts.com) — paid subscription | 1–2 days |
| Anthropic API | API key | `ANTHROPIC_API_KEY` | `lumin/anthropic-api-key` | [console.anthropic.com](https://console.anthropic.com) | < 1 day |

**Note:** Chartmetric requires paid access for streaming velocity data. Soundcharts requires a subscription for radio airplay. Both should be budgeted before deploying Agent 01.

---

## 5. Inter-Agent Dependencies

**Writes to (consumed by other agents):**
- `resonance-model-params` DynamoDB table → read by **Agent 7** to calibrate CLV thresholds using entropy/temperature signals
- `cultural-entropy-log` DynamoDB table → read by **Agent 6** to calibrate cultural moment detection convergence thresholds
- Kinesis `resonance-raw-stream` → raw data pipeline (internal only; no other agent reads this directly)

**Reads from (produced by other agents):**
- None. Agent 01 reads exclusively from external streaming APIs and its own DynamoDB tables.

**Signal flow summary:**
```
External APIs (Chartmetric, Spotify, YouTube, Soundcharts)
  → Agent 01 (physics model)
    → resonance-model-params → Agent 07 (CLV calibration)
    → cultural-entropy-log   → Agent 06 (threshold calibration)
    → SNS alert              → H.F. (investor narrative)
```

---

## 6. Cost Estimate (Monthly)

| Component | Monthly cost |
|-----------|-------------|
| Claude API (from cost report) | $1.19 |
| Kinesis Data Stream — 1 shard (`resonance-raw-stream`) | $10.80 |
| DynamoDB — 4 tables, on-demand (~400K R/W ops) | ~$0.60 |
| S3 — backtest archive storage (~1 GB/month) | ~$0.03 |
| SNS — alert notifications | ~$0.01 |
| Secrets Manager — Soundcharts key (~1 secret owned) | $0.40 |
| CloudWatch Logs — hourly run log volume | ~$0.30 |
| **Estimated monthly total** | **~$13.30** |

**Dominant cost:** Kinesis Data Stream ($10.80) accounts for 81% of this agent's cost. If Kinesis is replaced with DynamoDB polling for the data pipeline, monthly cost drops to ~$2.50. Evaluate whether the Kinesis stream adds sufficient real-time value to justify the cost at current scale.

---

## 7. Time-to-Live Estimate

| Task | Working days |
|------|-------------|
| Provision Chartmetric API access (paid subscription) | 1–2 days |
| Provision Spotify + YouTube API keys (self-serve) | < 1 day |
| Provision Soundcharts subscription | 1–2 days |
| Create AWS resources (DynamoDB tables, Kinesis, S3, SNS) | < 1 day |
| Deploy agent and run smoke test against real AWS | 1 day |
| First successful scheduled run (hourly data collection) | ½ day |
| **Total realistic TTL** | **3–5 working days** |

Blocking dependency: Chartmetric paid subscription approval. All other steps can run in parallel.

---

## 8. Risk Callouts

1. **Kinesis cost at current scale.** $10.80/month for a single Kinesis shard delivering data to one consumer agent is expensive relative to the Claude API cost ($1.19). If throughput requirements don't justify a dedicated stream, DynamoDB on-demand reads achieve the same result at 1/10th the cost. Flag for review before provisioning.

2. **Chartmetric and Soundcharts are paid subscriptions.** Neither is free-tier eligible. Both are required for the core physics model. Budget approval needed before deploy.

3. **Walk-forward backtest track record is an investor narrative asset.** The first Brier score is computed in Week 1. It takes 6+ months of weekly backtests to build the investor-grade accuracy track record described in the spec. Deploy early — the clock starts ticking only when Agent 01 is live.

4. **No rate limiting on external API calls.** The `pull_chartmetric_streaming_data`, `pull_spotify_audio_features`, etc. tool functions call external APIs in a tight loop. If Chartmetric enforces hourly rate limits (common), the agent may silently return partial data. Review rate limit headers in tool code.

5. **SkyBlew Chartmetric artist ID (`SKYBLEW_CM_ID`) is needed only by Agent 7**, not Agent 01. Agent 01 pulls market-wide streaming data, not artist-specific data. No action needed here.

---

## 9. Deployment Checklist

- [ ] Obtain Chartmetric API key (paid subscription; approve budget first)
- [ ] Obtain Soundcharts API key (paid subscription)
- [ ] Create Spotify Developer app and obtain `client_id` + `client_secret`
- [ ] Enable YouTube Data API v3 in Google Cloud Console and create API key
- [ ] Create Kinesis Data Stream `resonance-raw-stream` (1 shard, us-east-1)
- [ ] Create DynamoDB tables: `resonance-model-params`, `resonance-trend-signals`, `resonance-backtest-log`, `resonance-predictions` (on-demand billing)
- [ ] Create S3 bucket `lumin-backtest-archive` with versioning enabled
- [ ] Create SNS topic `lumin-resonance-alerts` and subscribe H.F.'s email
- [ ] Populate Secrets Manager: `lumin/chartmetric-api-key`, `lumin/soundcharts-api-key`, `lumin/spotify-oauth-token`, `lumin/youtube-api-key`
- [ ] Copy `.env.example` to `.env`, fill in all values, replace `ACCOUNT` in `SNS_RESONANCE_TOPIC`
- [ ] Run `python scripts/run_agent.py agent-01-resonance hourly_data_collection` and verify JSON response with no `"error"` key
- [ ] Install systemd timers from `infra/systemd/example-timers/` and enable them
- [ ] Verify the first scheduled hourly run completes successfully and writes at least one record to `resonance-trend-signals`
