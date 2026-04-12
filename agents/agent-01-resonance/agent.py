"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 1: RESONANCE INTELLIGENCE ADK          ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: Lumin Luxe Inc.                                         ║
║  Mission: The physics engine of the Lumin ecosystem —           ║
║           transforming streaming data into timestamped,         ║
║           investor-grade predictions no competitor can replicate.║
╚══════════════════════════════════════════════════════════════════╝

RESONANCE ANALYTICS™ — The Mathematical Foundation:

The Resonance Engine models the music attention economy as a statistical
mechanical system. Listener attention is finite and distributes across
artists according to a Boltzmann probability distribution, governed by
the partition function Z = Σ exp(-E_i / T), where:

  E_i = "energy cost" of attention = inverse of artist momentum
  T   = effective "temperature" = listener exploration tendency
       (measured via Shannon entropy of genre distribution)
  P_i = exp(-E_i / T) / Z  (probability of artist i capturing attention)

Phase transitions (breakout moments) are detected via Critical Slowing
Down signatures — variance surge and autocorrelation increase in the
entropy time series — which precede genre breakouts by 7-14 days.

Walk-forward backtesting with Brier scores provides the investor-grade
calibration proof that no existing commercial music analytics platform
publishes. This is the competitive moat.

EXCLUDED by design: Quantum mechanics (multi-body intractability).
The framework uses classical statistical mechanics exclusively.
"""

import os
from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.data_tools import (
    pull_chartmetric_streaming_data,
    pull_spotify_audio_features,
    pull_youtube_velocity,
    pull_soundcharts_radio,
)
from tools.physics_tools import (
    compute_boltzmann_distribution,
    compute_shannon_entropy,
    compute_partition_function,
    compute_attention_temperature,
)
from tools.trend_tools import (
    detect_phase_transitions,
    compute_variance_surge,
    get_active_trend_signals,
    archive_trend_signal,
)
from tools.backtest_tools import (
    run_walk_forward_backtest,
    compute_brier_score,
    compute_calibration_error,
    get_backtest_archive,
    store_prediction,
)
from tools.report_tools_resonance import (
    generate_weekly_resonance_digest,
    post_resonance_alert,
    build_investor_accuracy_narrative,
)

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are the Lumin Resonance Intelligence Agent — the physics engine of the
entire Lumin ecosystem. You maintain the Resonance Analytics™ Metadata Engine,
a proprietary system that applies statistical mechanics to streaming data to
produce calibrated, timestamped predictions about genre momentum and artist
trajectory.

THE PHYSICS FRAMEWORK:
Resonance Analytics treats listener attention as a finite resource that
distributes across artists and genres according to Boltzmann probability
distributions. Shannon entropy measures how fragmented or concentrated that
attention is. Phase transitions (breakout moments) are detected via
Critical Slowing Down signatures — variance surges in the entropy time series
that precede breakouts by 7-14 days.

This framework explicitly uses classical statistical mechanics. Quantum
mechanics is excluded by design — multi-body intractability makes it
inappropriate for this application.

YOUR THREE CORE RESPONSIBILITIES:

1. DATA PIPELINE: Pull streaming data hourly from Chartmetric, Spotify,
   Apple Music, and YouTube. Feed to the Kinesis stream.
   Tools: pull_chartmetric_streaming_data, pull_spotify_audio_features,
          pull_youtube_velocity, pull_soundcharts_radio

2. PHYSICS COMPUTATION: Run Boltzmann distribution updates daily.
   Compute partition function, attention temperature, entropy.
   Detect phase transition precursors (variance surge, autocorrelation rise).
   Tools: compute_boltzmann_distribution, compute_shannon_entropy,
          compute_partition_function, compute_attention_temperature,
          detect_phase_transitions, compute_variance_surge

3. WALK-FORWARD BACKTESTING: Every Sunday, compare last week's predictions
   to actual outcomes. Compute Brier score and calibration error.
   Store results in the investor track record archive.
   Tools: run_walk_forward_backtest, compute_brier_score,
          compute_calibration_error, store_prediction

THE INVESTOR TRACK RECORD:
Every prediction you make is timestamped and stored before the outcome is known.
This creates an auditable track record. The Brier score measures calibration —
are 70% confidence predictions right 70% of the time?
Brier score 0.0 = perfect, 0.25 = no skill, 1.0 = perfectly wrong.
Target: Brier score < 0.18 within 6 months (industry benchmark: 0.22).
This is the thing that makes Lumin defensible to sophisticated investors.

OUTPUT STANDARDS:
- Phase transition alerts require confidence ≥ 0.75 to post to Slack
- Predictions must be stored via store_prediction() BEFORE the outcome is known
- Brier score is computed weekly — never skip a Sunday backtest
- All entropy values and partition function outputs use 6 decimal precision
- When reporting to H.F., translate physics output to plain English
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

def create_resonance_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            pull_chartmetric_streaming_data,
            pull_spotify_audio_features,
            pull_youtube_velocity,
            pull_soundcharts_radio,
            compute_boltzmann_distribution,
            compute_shannon_entropy,
            compute_partition_function,
            compute_attention_temperature,
            detect_phase_transitions,
            compute_variance_surge,
            get_active_trend_signals,
            archive_trend_signal,
            run_walk_forward_backtest,
            compute_brier_score,
            compute_calibration_error,
            get_backtest_archive,
            store_prediction,
            generate_weekly_resonance_digest,
            post_resonance_alert,
            build_investor_accuracy_narrative,
        ],
    )

# ─── SCHEDULED TASK HANDLERS ───────────────────────────────────────────────

def run_hourly_data_collection(agent: Agent) -> dict:
    """Every hour — pull fresh data from all streaming APIs."""
    result = agent(
        "Run the hourly data collection cycle. "
        "1. Pull Chartmetric streaming data via pull_chartmetric_streaming_data(). "
        "2. Pull Spotify audio features via pull_spotify_audio_features(). "
        "3. Pull YouTube velocity via pull_youtube_velocity(). "
        "4. Pull Soundcharts radio data via pull_soundcharts_radio(). "
        "5. Log the total records written and any API errors. "
        "Return: data source status, records pulled, any failures."
    )
    return {"task": "hourly_data_collection", "result": str(result)}


def run_daily_physics_update(agent: Agent) -> dict:
    """
    02:00 UTC daily — Core Boltzmann model update.
    The heart of the Resonance Engine.
    """
    result = agent(
        "Run the daily Resonance Engine physics update. "
        "1. Call compute_attention_temperature() to measure current listener exploration index. "
        "2. Call compute_partition_function() with today's streaming momentum data. "
        "3. Call compute_boltzmann_distribution() to update attention probability distribution. "
        "4. Call compute_shannon_entropy() on the distribution — high entropy = fragmented attention, "
        "   low entropy = consolidating around specific artists/genres. "
        "5. Call detect_phase_transitions() on the last 30 days of entropy data. "
        "6. For any signal with confidence ≥ 0.75: call store_prediction() to timestamp it, "
        "   then call post_resonance_alert() to notify the team. "
        "Return: current entropy value, temperature, partition function Z, "
        "and any phase transition signals detected with confidence scores."
    )
    return {"task": "daily_physics_update", "result": str(result)}


def run_weekly_backtest(agent: Agent) -> dict:
    """
    Sundays 04:00 UTC — Walk-forward backtesting cycle.
    The investor-grade accuracy proof.
    """
    result = agent(
        "Run the weekly walk-forward backtesting cycle. "
        "1. Call run_walk_forward_backtest() to compare all predictions made 7-14 days ago "
        "   against their actual outcomes. "
        "2. Call compute_brier_score() on the results. "
        "   Brier score < 0.18 = excellent | 0.18-0.22 = good | > 0.22 = needs review. "
        "3. Call compute_calibration_error() — are our confidence levels accurate? "
        "4. Store all results via get_backtest_archive() and archive the week's record. "
        "5. Call build_investor_accuracy_narrative() to generate the investor-facing "
        "   summary of our prediction accuracy to date. "
        "6. Call generate_weekly_resonance_digest() and post to Slack #resonance-intelligence. "
        "Return: this week's Brier score, calibration error, running accuracy trend, "
        "and the investor narrative paragraph."
    )
    return {"task": "weekly_backtest", "result": str(result)}


def run_trend_alert_check(agent: Agent) -> dict:
    """Every 4 hours — Check for new high-confidence trend signals."""
    result = agent(
        "Check for new phase transition signals. "
        "Call get_active_trend_signals() to retrieve any signals detected in the last 4 hours. "
        "For each signal with confidence ≥ 0.75: "
        "  - Translate the physics output into plain English for H.F. "
        "    (e.g., 'Attention entropy variance up 2.4x over baseline — lo-fi conscious "
        "    hip-hop entering phase transition. Recommend: push LightSwitch and MoreLoveLessWar "
        "    to editorial contacts this week while the cultural window is open.') "
        "  - Call post_resonance_alert() with the plain-English interpretation. "
        "  - Make sure the prediction is stored before posting the alert. "
        "Return: number of signals checked, alerts posted."
    )
    return {"task": "trend_alert_check", "result": str(result)}


# ─── LAMBDA HANDLER ────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    agent = create_resonance_agent()
    task  = event.get("task", "hourly_data_collection")

    dispatch = {
        "hourly_data_collection": lambda: run_hourly_data_collection(agent),
        "daily_physics_update":   lambda: run_daily_physics_update(agent),
        "weekly_backtest":        lambda: run_weekly_backtest(agent),
        "trend_alert_check":      lambda: run_trend_alert_check(agent),
    }

    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()


# ─── LOCAL DEV RUNNER ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🔬 Resonance Intelligence Agent — Interactive Mode")
    print("   Commands: 'entropy' | 'backtest' | 'signals' | 'investor' | 'quit'\n")

    agent = create_resonance_agent()
    shortcuts = {
        "entropy":  "What is the current Shannon entropy of the music attention distribution? What does it tell us?",
        "backtest": "Show me the current Brier score and walk me through the accuracy trend.",
        "signals":  "Are there any active phase transition signals right now? What is their confidence level?",
        "investor": "Generate the investor-facing accuracy narrative for Resonance Analytics.",
    }
    while True:
        try:
            user_input = input("Resonance > ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if user_input.lower() in shortcuts:
                user_input = shortcuts[user_input.lower()]
            elif not user_input:
                continue
            print(f"\nAgent: {agent(user_input)}\n")
        except KeyboardInterrupt:
            print("\n\nResonance Agent offline.")
            break
