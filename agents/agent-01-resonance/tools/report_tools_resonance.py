"""
tools/report_tools_resonance.py — Human-readable reporting for Agent 1.
Translates physics output into actionable intelligence for H.F. and investors.
"""

import json, os, boto3, requests
from datetime import datetime, timezone
from strands import tool

dynamo     = boto3.resource("dynamodb", region_name="us-east-1")
backtest_t = dynamo.Table(os.environ.get("BACKTEST_TABLE", "resonance-backtest-log"))
signals_t  = dynamo.Table(os.environ.get("SIGNALS_TABLE",  "resonance-trend-signals"))

SLACK_RESONANCE_WEBHOOK = os.environ.get("SLACK_RESONANCE_WEBHOOK", "")
SNS_RESONANCE_TOPIC     = os.environ.get("SNS_RESONANCE_TOPIC",     "")
sns = boto3.client("sns", region_name="us-east-1")


@tool
def post_resonance_alert(
    signal_type: str,
    confidence: float,
    plain_english_summary: str,
    recommended_action: str,
) -> str:
    """
    Post a phase transition alert to Slack #resonance-intelligence.
    Only call for signals with confidence ≥ 0.75 — lower confidence
    signals go in the weekly digest, not the immediate alert.

    Args:
        signal_type:           Type of signal (PHASE_TRANSITION / GENRE_BREAKOUT).
        confidence:            Confidence score 0.0-1.0.
        plain_english_summary: Non-technical description of what was detected.
        recommended_action:    What H.F. should do in response.

    Returns:
        JSON with Slack post status.
    """
    if confidence < 0.75:
        return json.dumps({
            "status": "NOT_POSTED",
            "reason": f"Confidence {confidence:.0%} below 0.75 threshold. Include in weekly digest only.",
        })

    emoji = "🔬" if confidence >= 0.90 else "📡"
    ts    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    msg = {
        "text": f"{emoji} *Resonance Alert — Phase Transition Detected*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} Resonance Analytics™ Alert"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Signal:*\n{signal_type}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence:.0%}"},
                    {"type": "mrkdwn", "text": f"*Detected:*\n{ts}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*What the Physics is Saying:*\n{plain_english_summary}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Recommended Action:*\n{recommended_action}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                    "text": "_This prediction has been timestamped in the Resonance Engine track record. resonance.opp.pub/admin/signals_"},
            },
        ],
    }

    status = "NOT_SENT"
    if SLACK_RESONANCE_WEBHOOK:
        try:
            r = requests.post(SLACK_RESONANCE_WEBHOOK, json=msg, timeout=5)
            status = "SENT" if r.ok else f"FAILED: {r.status_code}"
        except Exception as e:
            status = f"ERROR: {e}"
    else:
        status = "DRY_RUN — SLACK_RESONANCE_WEBHOOK not configured"

    return json.dumps({
        "status":     status,
        "confidence": round(confidence, 4),
        "signal":     signal_type,
        "posted_at":  datetime.now(timezone.utc).isoformat(),
    })


@tool
def generate_weekly_resonance_digest() -> str:
    """
    Generate the weekly Resonance Intelligence digest for H.F. and the team.
    Combines this week's Brier score, active trend signals, entropy status,
    and top insight into a single Slack-ready message posted every Monday 09:00 UTC.

    Returns:
        JSON with digest text and Slack post status.
    """
    week = datetime.now(timezone.utc).strftime("%Y-W%W")

    # Pull latest Brier score
    try:
        bt_resp = backtest_t.get_item(
            Key={"pk": "BACKTEST#WEEKLY", "sk": week}
        )
        bt = bt_resp.get("Item", {})
        brier_str  = bt.get("brier_score", "Pending")
        brier_tier = bt.get("tier", "Not yet computed")
    except Exception:
        brier_str  = "Pending"
        brier_tier = "Run weekly_backtest first"

    # Pull recent signals
    from datetime import timedelta
    from tools.trend_tools import get_active_trend_signals
    signals_raw = json.loads(get_active_trend_signals())
    sig_count   = signals_raw.get("active_signals", 0)
    top_signal  = signals_raw.get("signals", [{}])[0] if sig_count > 0 else {}

    digest = (
        f"*Resonance Analytics™ Weekly Digest — {week}*\n\n"
        f"📊 *Model Accuracy:* Brier Score {brier_str} ({brier_tier})\n"
        f"   Target: <0.18 | Random baseline: 0.25 | Better = lower\n\n"
        f"📡 *Active Signals:* {sig_count} phase transition signal(s) in last 24h\n"
    )

    if top_signal:
        digest += (
            f"   Top signal: {top_signal.get('confidence', 0):.0%} confidence — "
            f"{top_signal.get('tte_days', 'unknown')} window\n"
            f"   Action: {top_signal.get('recommendation', 'See dashboard')[:120]}\n"
        )
    else:
        digest += "   No high-confidence signals active — system in normal monitoring mode.\n"

    digest += (
        f"\n_Resonance Engine runs hourly · Physics update daily · Backtesting weekly_\n"
        f"_resonance.opp.pub/admin — Lumin Luxe Inc._"
    )

    status = "NOT_SENT"
    if SLACK_RESONANCE_WEBHOOK:
        try:
            r = requests.post(SLACK_RESONANCE_WEBHOOK, json={"text": digest}, timeout=5)
            status = "SENT" if r.ok else f"FAILED: {r.status_code}"
        except Exception as e:
            status = f"ERROR: {e}"
    else:
        status = "DRY_RUN — SLACK_RESONANCE_WEBHOOK not set"

    return json.dumps({
        "week":       week,
        "digest":     digest,
        "brier_score":brier_str,
        "sig_count":  sig_count,
        "slack":      status,
    })


@tool
def build_investor_accuracy_narrative() -> str:
    """
    Generate an investor-facing narrative paragraph summarizing Resonance Analytics'
    prediction accuracy track record. This is designed for inclusion in pitch decks,
    investor updates, and due diligence materials.

    Frames the Brier score and calibration error in terms sophisticated investors
    understand — comparing to weather forecasting benchmarks and financial model
    accuracy standards.

    Returns:
        JSON with the narrative paragraph and supporting data points.
    """
    # Pull full backtest archive
    try:
        resp = backtest_t.query(
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": "BACKTEST#WEEKLY"},
            ScanIndexForward=True,
        )
        records = resp.get("Items", [])
    except Exception:
        records = []

    if not records:
        narrative = (
            "Resonance Analytics™ is currently in its initial calibration phase. "
            "The walk-forward backtesting infrastructure is operational and generating "
            "its first timestamped prediction track record. Brier score reporting will "
            "begin following the first complete weekly backtesting cycle. "
            "All predictions are stored immutably before outcomes are known — "
            "ensuring the track record is auditable and tamper-proof from day one."
        )
        return json.dumps({
            "narrative": narrative,
            "status": "CALIBRATION_PHASE",
            "weeks_complete": 0,
        })

    scores     = [float(r.get("brier_score", 0.25)) for r in records]
    latest_bs  = scores[-1]
    best_bs    = min(scores)
    weeks      = len(records)
    avg_bs     = round(sum(scores) / weeks, 4)
    improving  = len(scores) > 2 and scores[-1] < scores[0]

    tier_text  = (
        "elite-tier predictive accuracy" if latest_bs < 0.10 else
        "above-benchmark accuracy"       if latest_bs < 0.18 else
        "at-benchmark accuracy"          if latest_bs < 0.22 else
        "developing model accuracy"
    )

    narrative = (
        f"Resonance Analytics™ has generated {weeks} weeks of walk-forward backtested "
        f"predictions with a current Brier score of {latest_bs:.3f} ({tier_text}). "
        f"For reference: random forecasting produces a Brier score of 0.25; "
        f"professional weather forecasting benchmarks target 0.15-0.18. "
        f"Lumin's {latest_bs:.3f} score {'places it above this benchmark' if latest_bs < 0.18 else 'is converging toward this benchmark'}. "
    )

    if improving:
        narrative += (
            f"The model has improved {(scores[0] - latest_bs):.3f} Brier points since inception, "
            f"demonstrating systematic learning as the training corpus grows. "
        )

    narrative += (
        f"All predictions are timestamped and stored before outcomes are known, "
        f"creating an auditable track record. No commercial music analytics platform "
        f"currently publishes calibrated predictions with verifiable Brier scores — "
        f"this constitutes a defensible and replicable competitive moat."
    )

    return json.dumps({
        "narrative":       narrative,
        "weeks_tracked":   weeks,
        "latest_brier":    latest_bs,
        "best_brier":      best_bs,
        "average_brier":   avg_bs,
        "target_brier":    0.18,
        "improving":       improving,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
    })
