# Agent 12: SkyBlew Social Media Director
## The Creative Resonance Architect

**2StepsAboveTheStars LLC | AWS Strands Agents | Claude claude-sonnet-4-6**

The bridge between SkyBlew's imagination and the daily heartbeat of his fans.
The agent drafts. H.F. approves. The music reaches everyone it belongs to.

---

## The Non-Negotiable Rule

**This agent NEVER posts without explicit human approval.**
Every caption, reply, and piece of content goes to H.F. first. Always.
SkyBlew's voice cannot be automated. It can be assisted.

---

## Quick Start

```bash
cd agent-12-social-media
pip install -r requirements.txt
cp .env.example .env   # fill in keys — APPLE_MUSIC_CONFIRMED=false initially
pytest tests/ -v       # run full test suite — all 30+ tests should pass
python agent.py        # interactive mode
```

## File Structure

```
agent-12-social-media/
├── agent.py                  # Main agent, Voice Book, 7 task handlers, Lambda
├── requirements.txt
├── .env.example
├── tools/
│   ├── __init__.py
│   ├── voice_tools.py        # Caption generation, Voice Book, validation, hashtags
│   ├── content_tools.py      # Calendar, approval queue, platform posting (6 platforms)
│   ├── platform_tools.py     # Re-exports from content_tools
│   ├── monitoring_tools.py   # Fan monitoring, analytics, FM&AM campaign, international
│   ├── analytics_tools.py    # Re-exports from monitoring_tools
│   └── campaign_tools.py     # Re-exports from monitoring_tools
├── tests/
│   └── test_agent.py         # 30+ tests covering voice model, approval gate, campaign
└── docs/
    ├── README.md
    └── DEPLOY.md
```

## The 30 Tools Across 5 Groups

| Group         | Tools |
|---------------|-------|
| Voice (4)     | generate_caption, load_voice_book, validate_voice_score, get_hashtag_set |
| Content (7)   | update_content_calendar, get_todays_content_queue, get_pending_approvals, send_approval_request, mark_content_approved, mark_content_posted, log_post_performance |
| Platforms (6) | post_to_instagram, post_to_tiktok, post_to_twitter, post_to_youtube_community, post_to_discord, post_to_threads |
| Monitoring (5)| monitor_all_mentions, classify_fan_interaction, draft_fan_reply, detect_fan_art, escalate_interaction |
| Analytics (4) | pull_platform_analytics, generate_weekly_digest, get_top_performing_content, generate_monthly_report |
| Campaign (4)  | run_fm_am_campaign_phase, get_campaign_status, generate_international_content, post_cultural_moment_content |

## EventBridge Schedule

| UTC Time | Task | Description |
|----------|------|-------------|
| 06:00 daily | morning_content_queue | Post approved content at optimal times |
| Every 15min | mention_monitor | Fan engagement monitoring across all platforms |
| 22:00 daily | daily_analytics_update | Pull and store performance data |
| Sundays 18:00 | weekly_content_generation | Generate coming week's calendar for Sunday Review |
| Mondays 09:00 | weekly_digest | Weekly performance digest to H.F. |
| On-demand | fm_am_campaign | Current FM & AM campaign phase execution |
| Agent 6 trigger | cultural_moment_response | Real-time cultural moment content generation |

## The FM & AM Campaign Gate

**CRITICAL:** `APPLE_MUSIC_CONFIRMED=false` in .env by default.
The campaign will not run until this is set to `true`.
Only set it after DistroKid confirms FM & AM is live on Apple Music.
First-impression streaming moments are permanently lost if Apple Music is missing.

## Run Tests

```bash
pytest tests/ -v --tb=short
```

Tests validate: Voice Model scoring, approval gate enforcement,
FM & AM campaign gate, cultural moment framing, fan interaction
classification, all 6 platform posting tools (dry-run mode).

## The Sunday Review

Every Sunday at 18:00 UTC, the agent generates the coming week's full
content calendar. H.F. and SkyBlew review it together in a 30-minute
session. They approve, edit, or replace. The agent executes the week.
This is the creative heartbeat of the operation.
