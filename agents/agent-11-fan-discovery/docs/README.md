# Agent 11: Fan Discovery & Global Outreach Agent

**2StepsAboveTheStars LLC | AWS Strands Agents | Claude claude-sonnet-4-6**

Finds every community worldwide where SkyBlew's music belongs, then introduces
them to it — authentically, specifically, and only with human approval.

## The One Rule

**This agent NEVER posts anything without H.F.'s explicit approval.**
Every message goes to the Slack approval queue. Always.

## Quick Start

```bash
cd agent-11-fan-discovery
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python agent.py        # interactive mode
```

## File Structure

```
agent-11-fan-discovery/
├── agent.py                   # Main agent + Lambda handler + campaign tasks
├── requirements.txt
├── .env.example
├── tools/
│   ├── __init__.py
│   ├── discovery_tools.py     # Reddit, TikTok, YouTube, Discord scanners
│   ├── outreach_tools.py      # Message generation + human approval queue
│   ├── tracking_tools.py      # Re-exports (UTM, conversions, reporting)
│   └── distribution_tools.py  # DistroKid, platform status, editorial pitches
├── tests/
│   └── test_agent.py
└── docs/
    ├── README.md
    └── DEPLOY.md
```

## Daily Schedule (EventBridge)

| UTC Time | Task | Description |
|----------|------|-------------|
| 06:00 | `morning_discovery` | Scan all target communities |
| 07:00 | `generate_outreach_queue` | Generate messages, submit for approval |
| 22:00 | `evening_report` | Conversion report to H.F. |

## Target Communities

| Platform | Community | Why |
|----------|-----------|-----|
| Reddit | r/nujabes | Highest taste match — sonic ancestor |
| Reddit | r/BombRushCyberfunk | Already heard LightSwitch |
| Reddit | r/hiphopheads | 4.5M conscious hip-hop fans |
| Reddit | r/LupeFiasco, r/Common | Direct taste community |
| TikTok | #nujabes | 800M+ views |
| TikTok | #lofi | 12B+ views |
| Discord | Nujabes Legacy, BRC Community | Tier 1 targets |

## The 16 Agent Tools

| Group | Tools |
|-------|-------|
| Discovery | scan_reddit_communities, scan_tiktok_hashtags, scan_youtube_comments, find_discord_communities |
| Outreach | generate_outreach_message, submit_for_human_approval, post_approved_message, get_pending_approvals |
| Tracking | log_community_entry, record_conversion_event, get_conversion_report, get_top_converting_communities |
| Distribution | check_distrokid_delivery_status, build_utm_link, get_streaming_platform_status, prepare_editorial_pitch |

## BEFORE Running Any Campaign

```bash
# Always check distribution first
python agent.py
> distro
# Verify Apple Music shows LIVE for both LightSwitch and MoreLoveLessWar
# If not live, fix DistroKid first. Do not run outreach on unavailable tracks.
```

## Run Tests

```bash
pytest tests/ -v
```
