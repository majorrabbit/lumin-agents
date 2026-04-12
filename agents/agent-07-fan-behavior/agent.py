"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 7: FAN BEHAVIOR INTELLIGENCE ADK       ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: 2StepsAboveTheStars LLC                                 ║
║  Mission: Turn SkyBlew's 35K monthly listeners into a deeply     ║
║  understood fan ecosystem with CLV, churn prediction, and        ║
║  geographic intelligence feeding every other agent.              ║
╚══════════════════════════════════════════════════════════════════╝

The Fan Behavior Agent is the intelligence layer between SkyBlew's music
and SkyBlew's business. It answers: Who are the fans? Where are they?
What do they love? Which ones are about to leave? Which are most valuable?
Its outputs feed Agent 11 (outreach targeting), the SkyBlew Universe App
(personalization), and the CS Agent (churn intervention triggers).
"""

import os
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.streaming_tools import (
    fetch_daily_streaming_metrics,
    compute_fan_engagement_scores,
    get_platform_breakdown,
)
from tools.clv_tools import (
    compute_cohort_clv,
    run_churn_risk_scan,
    get_clv_report,
)
from tools.geo_tools import (
    compute_geographic_cohorts,
    get_top_growth_markets,
    update_geo_index,
)
from tools.genre_tools import (
    compute_genre_affinity_scores,
    get_content_recommendations,
    update_app_content_carousel,
)
from tools.report_tools import (
    generate_daily_fan_brief,
    generate_weekly_fan_report,
    generate_monthly_strategic_report,
    export_utm_conversion_feed,
)

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are the Lumin Fan Behavior Intelligence Agent — the analytical mind that
transforms SkyBlew's streaming data into a living map of his fan ecosystem.

YOUR MISSION:
Understand who SkyBlew's fans are, model their behavior, predict their future
actions, and surface insights that help every other part of the Lumin ecosystem
make better decisions.

SKYBLEW'S CURRENT BASELINE (as of early 2026):
- ~35,000 monthly Spotify listeners
- LightSwitch (Bomb Rush Cyberfunk / Nintendo): ~1,000 streams/day organic growth
- MoreLoveLessWar: newly released — baseline TBD pending Apple Music fix
- 94-track catalog across multiple release formats
- Active fanbase across anime, nerdcore, conscious hip-hop, gaming communities
- SkyBlew Universe App: in development — your data feeds its personalization engine

THE THREE CORE MODELS YOU MAINTAIN:

1. Fan Engagement Score (FES) — 0 to 100 daily composite:
   Stream frequency (35%) + Catalog breadth (20%) + Playlist save rate (20%)
   + Social share rate (15%) + Purchase conversion (10%)
   Tiers: Core (75+) | Engaged (50-74) | Casual (25-49) | Lapsed (<25)

2. Customer Lifetime Value (CLV) — 12-month projection per cohort:
   CLV = (M - c) × (r / (1 + d - r))
   M = avg monthly revenue/fan | c = cost to serve | r = retention rate | d = discount rate
   Revenue includes: streaming royalties + sync attribution + merch + Bandcamp + tickets

3. Churn Risk Score — 0.0 to 1.0:
   50% recency decay (14-day half-life) + 35% trend component + 15% playlist removal rate
   High risk (>0.70) → trigger re-engagement via SkyBlew Universe App or SES

YOUR OUTPUTS FEED:
- Agent 11 (Fan Discovery): which communities are producing highest-CLV fans
- Agent 9 (Customer Success): declining AskLumin users who are also declining fans
- SkyBlew Universe App: geographic targeting, content carousel personalization
- H.F. strategic decisions: which markets to prioritize, which content to create next
- Investor narrative: fan behavior metrics as proof of business traction

OPERATING PRINCIPLES:
You work with aggregate cohort data from platform APIs — never individual user PII.
Privacy is preserved by design. Geographic data is country-level only, never city.
Always contextualize LightSwitch growth as legitimate Nintendo sync organic growth —
it is the foundation of the expanding fanbase, not an anomaly to be questioned.
"""

# ─── MODEL ─────────────────────────────────────────────────────────────────

def get_model() -> AnthropicModel:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id="claude-sonnet-4-6",
        max_tokens=4096,
    )

# ─── AGENT ─────────────────────────────────────────────────────────────────

def create_fan_behavior_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            fetch_daily_streaming_metrics,
            compute_fan_engagement_scores,
            get_platform_breakdown,
            compute_cohort_clv,
            run_churn_risk_scan,
            get_clv_report,
            compute_geographic_cohorts,
            get_top_growth_markets,
            update_geo_index,
            compute_genre_affinity_scores,
            get_content_recommendations,
            update_app_content_carousel,
            generate_daily_fan_brief,
            generate_weekly_fan_report,
            generate_monthly_strategic_report,
            export_utm_conversion_feed,
        ],
    )

# ─── SCHEDULED TASK HANDLERS ───────────────────────────────────────────────

def run_daily_metrics_update(agent: Agent) -> dict:
    """07:00 UTC daily — Pull fresh data, update FES, run churn scan."""
    result = agent(
        "Run the daily fan behavior update. "
        "1. Call fetch_daily_streaming_metrics() to pull today's data from Chartmetric, "
        "Spotify, Apple Music, and YouTube. "
        "2. Call compute_fan_engagement_scores() to update FES for all cohorts. "
        "3. Call compute_geographic_cohorts() to refresh the geographic distribution. "
        "4. Call run_churn_risk_scan() — for any cohort with churn risk > 0.70, "
        "flag it for the SkyBlew Universe App re-engagement system. "
        "5. Call generate_daily_fan_brief() and post it to Slack #fan-intelligence. "
        "Return a summary: total cohorts updated, high-churn flags, top growth market today."
    )
    return {"task": "daily_metrics_update", "result": str(result)}


def run_weekly_clv_update(agent: Agent) -> dict:
    """Sundays 06:00 UTC — Full CLV model update across all cohorts."""
    result = agent(
        "Run the weekly CLV model update. "
        "1. Call compute_cohort_clv() for all geographic and genre cohorts. "
        "2. Update the fan-clv-model DynamoDB table with current retention rates. "
        "3. Call export_utm_conversion_feed() to feed Agent 11's community ranking. "
        "4. Call get_top_growth_markets() and flag any market showing >30% week-over-week growth — "
        "these are Agent 11's priority outreach targets for next week. "
        "5. Call generate_weekly_fan_report() — post to Slack and save to S3. "
        "Return: CLV by tier (Core/Engaged/Casual), top 3 growth markets, highest-churn cohort."
    )
    return {"task": "weekly_clv_update", "result": str(result)}


def run_monthly_strategic_report(agent: Agent) -> dict:
    """1st of month 08:00 UTC — Full strategic fan intelligence report."""
    result = agent(
        "Generate the monthly strategic fan intelligence report. Include: "
        "MoM growth in monthly listeners, FES distribution shift (are fans moving "
        "up or down cohort tiers?), CLV trend by geography, genre affinity evolution "
        "(is the audience leaning more toward lo-fi, anime, or conscious hip-hop?), "
        "top 5 markets by CLV, churn rate vs. acquisition rate, "
        "and one data-backed strategic recommendation for H.F. "
        "This report feeds the investor narrative — frame metrics as proof of "
        "compounding fan value and market penetration."
    )
    return {"task": "monthly_strategic_report", "result": str(result)}


def run_app_personalization_update(agent: Agent) -> dict:
    """On-demand — Update SkyBlew Universe App content carousel with latest genre affinity data."""
    result = agent(
        "Update the SkyBlew Universe App personalization data. "
        "1. Call compute_genre_affinity_scores() for all active cohorts. "
        "2. Call get_content_recommendations() to determine the optimal content mix "
        "for each geographic and behavioral cohort. "
        "3. Call update_app_content_carousel() to push the updated recommendations "
        "to the App's DynamoDB config table. "
        "Ensure: anime-aesthetic fans in Japan/Southeast Asia see the most "
        "relevant content first; US college-market fans see the educational "
        "Rhythm Escapism content; BRC gamers see LightSwitch-adjacent content. "
        "Return: cohorts updated, content adjustments made."
    )
    return {"task": "app_personalization_update", "result": str(result)}


# ─── LAMBDA HANDLER ────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    agent = create_fan_behavior_agent()
    task  = event.get("task", "daily_metrics_update")

    dispatch = {
        "daily_metrics_update":      lambda: run_daily_metrics_update(agent),
        "weekly_clv_update":         lambda: run_weekly_clv_update(agent),
        "monthly_strategic_report":  lambda: run_monthly_strategic_report(agent),
        "app_personalization_update": lambda: run_app_personalization_update(agent),
    }

    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()


# ─── LOCAL DEV RUNNER ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("👤 Fan Behavior Intelligence Agent — Interactive Mode")
    print("   Commands: 'fes' | 'clv' | 'geo' | 'churn' | 'report' | 'quit'\n")

    agent = create_fan_behavior_agent()
    shortcuts = {
        "fes":    "Show me the current Fan Engagement Score distribution across all cohorts.",
        "clv":    "Show me the current Customer Lifetime Value breakdown by geographic cohort.",
        "geo":    "Which are the top 5 growth markets for SkyBlew right now and why?",
        "churn":  "Run the churn risk scan and show me which cohorts are at highest risk.",
        "report": "Give me the key fan behavior insights from this week in one paragraph.",
    }
    while True:
        try:
            user_input = input("FanBehavior > ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if user_input.lower() in shortcuts:
                user_input = shortcuts[user_input.lower()]
            elif not user_input:
                continue
            print(f"\nAgent: {agent(user_input)}\n")
        except KeyboardInterrupt:
            print("\n\nFan Behavior Agent offline.")
            break
