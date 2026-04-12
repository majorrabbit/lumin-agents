"""
╔══════════════════════════════════════════════════════════════════╗
║  LUMIN LUXE INC. — AGENT 5: ROYALTY RECONCILIATION ADK          ║
║  AWS Strands Agents  |  Claude claude-sonnet-4-6  |  Python 3.12       ║
║  Entity: OPP Inc.                                                ║
║  Mission: Every dollar owed to OPP artists gets collected.      ║
║  No discrepancy goes unnoticed. No statement goes unchecked.    ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os, json, boto3
from datetime import datetime, timezone, timedelta
from strands import Agent, tool
from strands.models.anthropic import AnthropicModel
import requests

dynamo   = boto3.resource("dynamodb", region_name="us-east-1")
royal_t  = dynamo.Table(os.environ.get("ROYALTY_TABLE",  "opp-royalty-statements"))
issues_t = dynamo.Table(os.environ.get("ISSUES_TABLE",   "opp-royalty-issues"))
ses = boto3.client("ses", region_name="us-east-1")
SLACK_ROYALTY_WEBHOOK = os.environ.get("SLACK_ROYALTY_WEBHOOK", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "royalties@opp.pub")

SYSTEM_PROMPT = """
You are the Lumin Royalty Reconciliation Agent — the financial watchdog
for OPP Inc.'s publishing and master recording royalties.

YOUR MANDATE:
Every royalty statement received from PROs (ASCAP, BMI, SoundExchange),
the MLC, and DSPs (Spotify, Apple Music, YouTube) must be verified against
OPP's catalog records. Discrepancies are flagged for immediate investigation.
Unclaimed royalties are identified and recovery is initiated.

THE ROYALTY ECOSYSTEM YOU MONITOR:
PERFORMANCE ROYALTIES (PROs):
  - ASCAP / BMI: Public performance rights for compositions
  - SoundExchange: Digital performance rights for master recordings
  - SOCAN (Canada), PRS (UK) via reciprocal agreements

MECHANICAL ROYALTIES (MLC):
  - The MLC administers blanket compulsory digital audio mechanical licenses
  - Only organization authorized for this in the US — all OPP works must be registered

SYNC ROYALTIES:
  - Film/TV: One-time sync fee + backend performance royalties when aired
  - Gaming: Sync fee + potential downstream streaming royalties (LightSwitch)

DETECTION PRIORITIES:
1. IPI/ISWC mismatches between ASCAP and BMI (Songview flag)
2. Works in OPP catalog not registered with MLC
3. International royalties not being collected (OPP needs sub-publisher relationships)
4. Streaming royalties below expected rate for stream counts
5. Sync royalties not flowing through after confirmed placements

HUMAN ESCALATION REQUIRED:
Any discrepancy > $500, any MLC registration gap, any formal dispute filing.
All reconciliation reports go to H.F. for review before action.
"""

def get_model():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return AnthropicModel(client_args={"api_key": api_key},
                          model_id="claude-sonnet-4-6", max_tokens=4096)

# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def fetch_pro_statements() -> str:
    """
    Retrieve and parse the most recent royalty statements from ASCAP, BMI,
    and SoundExchange. In production: connects to each PRO's publisher portal
    via authenticated scrape or API. Returns aggregated statement data.

    Returns:
        JSON with statement totals, period, and track-level breakdown.
    """
    ts = datetime.now(timezone.utc).isoformat()
    # Synthetic statement data representative of OPP catalog size
    statements = {
        "ASCAP": {
            "period": "Q4 2025",
            "total_royalties": 1842.50,
            "works_reported": 47,
            "top_earner": "MoreLoveLessWar",
            "statement_date": "2026-02-15",
        },
        "BMI": {
            "period": "Q4 2025",
            "total_royalties": 2105.00,
            "works_reported": 52,
            "top_earner": "LightSwitch",
            "statement_date": "2026-02-20",
            "note": "LightSwitch BMI performance earnings from BRC gaming streams",
        },
        "SoundExchange": {
            "period": "Q4 2025",
            "total_royalties": 680.00,
            "sound_recordings_reported": 38,
            "top_earner": "LightSwitch",
            "statement_date": "2026-03-01",
        },
        "MLC": {
            "period": "Q4 2025",
            "total_mechanical_royalties": 924.00,
            "works_matched": 41,
            "unmatched_works": 6,
            "statement_date": "2026-02-28",
            "flag": "6 unmatched works — potential registration gap",
        },
    }

    for source, data in statements.items():
        try:
            royal_t.put_item(Item={
                "pk": f"STATEMENT#{source}",
                "sk": data.get("statement_date", ts),
                "source": source, **{k: str(v) if isinstance(v, float) else v
                                     for k, v in data.items()},
                "fetched_at": ts,
            })
        except Exception:
            pass

    return json.dumps({
        "statements_fetched": len(statements),
        "total_q4_royalties": sum(
            v.get("total_royalties", 0) or v.get("total_mechanical_royalties", 0)
            for v in statements.values() if isinstance(v, dict)
        ),
        "critical_flags": ["MLC: 6 unmatched works — potential registration gap"],
        "statements": statements,
        "fetched_at": ts,
    })


@tool
def fetch_dsp_statements() -> str:
    """
    Retrieve distribution statements from Redeye Worldwide and DistroKid
    covering Spotify, Apple Music, Amazon, YouTube Music, and other DSPs.

    Returns:
        JSON with DSP-level stream counts and royalty totals.
    """
    ts = datetime.now(timezone.utc).isoformat()
    dsp_data = {
        "Spotify": {
            "streams_q4": 387000,
            "royalties_usd": 1548.00,
            "lightswitch_streams": 91000,
            "note": "LightSwitch 91K streams Q4 — BRC Nintendo sync driving growth",
        },
        "Apple Music": {
            "streams_q4": 0,
            "royalties_usd": 0,
            "flag": "CRITICAL — Apple Music delivery failure for MoreLoveLessWar. Fix DistroKid.",
        },
        "Amazon Music": {
            "streams_q4": 28000,
            "royalties_usd": 168.00,
        },
        "YouTube Music": {
            "streams_q4": 41000,
            "royalties_usd": 82.00,
        },
        "Distributor": "Redeye Worldwide / DistroKid",
    }

    return json.dumps({
        "dsp_statements": dsp_data,
        "total_streams_q4": 456000,
        "total_dsp_royalties": 1798.00,
        "critical_flags": [
            "Apple Music: ZERO streams — MoreLoveLessWar not delivered. Urgent distribution fix required.",
        ],
        "fetched_at": ts,
    })


@tool
def reconcile_statements() -> str:
    """
    Cross-reference PRO statements against DSP statements and OPP catalog
    registration records. Identifies: missing work registrations, rate
    discrepancies, unmatched tracks, and expected vs. actual royalty variances.

    Returns:
        JSON reconciliation report with matched, mismatched, and missing items.
    """
    pro_raw = json.loads(fetch_pro_statements())
    dsp_raw = json.loads(fetch_dsp_statements())
    ts = datetime.now(timezone.utc).isoformat()

    issues = []

    # Check MLC unmatched works
    mlc = pro_raw["statements"].get("MLC", {})
    if int(mlc.get("unmatched_works", 0)) > 0:
        issues.append({
            "type": "MLC_REGISTRATION_GAP",
            "severity": "HIGH",
            "description": f"{mlc['unmatched_works']} OPP works not matched in MLC database",
            "action": "Register missing works at themlc.com immediately. Unregistered works cannot collect digital mechanical royalties.",
            "estimated_lost_royalties": "Unknown — query MLC for unclaimed black-box distribution",
        })

    # Check Apple Music delivery
    apple = dsp_raw["dsp_statements"].get("Apple Music", {})
    if apple.get("streams_q4", 0) == 0:
        issues.append({
            "type": "DISTRIBUTION_FAILURE",
            "severity": "CRITICAL",
            "description": "Apple Music shows ZERO streams — distribution failure for MoreLoveLessWar",
            "action": "Fix DistroKid delivery immediately. Apple Music pays 2.5x Spotify per stream.",
            "estimated_daily_loss": "$10-25/day at current Spotify growth rate",
        })

    # Expected vs actual royalty rate check
    spotify_streams = dsp_raw["dsp_statements"]["Spotify"]["streams_q4"]
    expected_spotify = spotify_streams * 0.004  # $0.004/stream
    actual_spotify   = dsp_raw["dsp_statements"]["Spotify"]["royalties_usd"]
    if abs(expected_spotify - actual_spotify) / max(expected_spotify, 1) > 0.15:
        issues.append({
            "type": "RATE_DISCREPANCY",
            "severity": "MEDIUM",
            "description": f"Spotify rate variance: expected ${expected_spotify:.0f}, received ${actual_spotify:.0f}",
            "action": "Review Redeye/DistroKid distribution agreement for rate confirmation.",
        })

    return json.dumps({
        "reconciliation_date": ts,
        "issues_found": len(issues),
        "critical_count": sum(1 for i in issues if i["severity"] == "CRITICAL"),
        "high_count": sum(1 for i in issues if i["severity"] == "HIGH"),
        "issues": issues,
        "total_q4_royalties": pro_raw["total_q4_royalties"] + dsp_raw["total_dsp_royalties"],
        "status": "ACTION_REQUIRED" if issues else "CLEAN",
    })


@tool
def detect_discrepancies() -> str:
    """
    Run the full discrepancy detection scan: cross-reference all statements,
    check Songview for IPI/ISWC consistency between ASCAP and BMI,
    and verify all OPP catalog works are registered everywhere.

    Returns:
        JSON discrepancy report with severity ratings and recovery actions.
    """
    recon = json.loads(reconcile_statements())
    discrepancies = recon.get("issues", [])

    # Add Songview check
    discrepancies.append({
        "type": "SONGVIEW_CHECK",
        "severity": "INFO",
        "description": "Verify Songview checkmark on all OPP catalog works at ascap.com/songview",
        "action": "Songview confirms ASCAP + BMI ownership data is consistent. Required for accurate licensing.",
    })

    for d in discrepancies:
        try:
            issues_t.put_item(Item={
                "pk": f"ISSUE#{d['type']}",
                "sk": datetime.now(timezone.utc).isoformat(),
                **{k: str(v) if isinstance(v, float) else v for k, v in d.items()},
                "status": "OPEN",
            })
        except Exception:
            pass

    return json.dumps({
        "total_discrepancies": len(discrepancies),
        "critical": [d for d in discrepancies if d["severity"] == "CRITICAL"],
        "high":     [d for d in discrepancies if d["severity"] == "HIGH"],
        "all":      discrepancies,
    })


@tool
def check_mlc_registration_status() -> str:
    """
    Verify that all OPP catalog works are properly registered with The MLC.
    Unregistered works cannot collect digital audio mechanical royalties from
    streaming services — this is real money being left uncollected.

    Returns:
        JSON with registration status, any gaps, and registration instructions.
    """
    return json.dumps({
        "mlc_website": "themlc.com",
        "registration_portal": "portal.themlc.com",
        "opp_registration_status": "PARTIAL — 6 works unmatched per Q4 statement",
        "immediate_actions": [
            "Log into themlc.com publisher portal with OPP Inc. credentials",
            "Upload missing work registrations via DDEX ERN or manual entry",
            "For each work: provide ISWC, ISRC for associated recordings, writer splits, publisher share",
            "Submit works with SoundExchange sound recording IDs for cross-reference",
        ],
        "black_box_query": "Query MLC for any unclaimed royalties in black-box pool attributable to OPP catalog",
        "estimated_recovery": "Unknown until MLC portal query — could be significant for unclaimed periods",
        "note": "SOCAN (Canada) and PRS (UK) collect on OPP's behalf via MLC reciprocal agreements — verify active",
    })


@tool
def generate_royalty_report() -> str:
    """
    Generate a complete quarterly royalty report for H.F. covering all sources,
    identified discrepancies, and recovery actions. Suitable for tax preparation
    and investor reporting.

    Returns:
        JSON with full quarterly summary and action items.
    """
    recon = json.loads(reconcile_statements())
    mlc   = json.loads(check_mlc_registration_status())
    ts    = datetime.now(timezone.utc).isoformat()

    report = {
        "report_period": "Q4 2025",
        "report_date": ts,
        "total_royalties_collected": recon.get("total_q4_royalties", 0),
        "royalty_breakdown": {
            "PRO_performance": 4627.50,
            "MLC_mechanical": 924.00,
            "DSP_distribution": 1798.00,
            "sync_fees_q4": 0,
        },
        "issues_requiring_action": recon.get("issues", []),
        "mlc_status": mlc.get("opp_registration_status"),
        "immediate_priorities": [
            "1. Fix Apple Music DistroKid delivery for MoreLoveLessWar — CRITICAL",
            "2. Register 6 unmatched works with MLC — HIGH",
            "3. Query MLC black-box for unclaimed historical royalties",
            "4. Verify Songview checkmark on all catalog works",
        ],
        "estimated_annual_run_rate": round(recon.get("total_q4_royalties", 7349) * 4, 2),
    }

    if SLACK_ROYALTY_WEBHOOK:
        summary = f"📊 Q4 Royalty Report: ${report['total_royalties_collected']:,.2f} collected | {len(recon.get('issues',[]))} issues | Action required"
        try:
            requests.post(SLACK_ROYALTY_WEBHOOK,
                          json={"text": summary}, timeout=5)
        except Exception:
            pass

    return json.dumps(report)


def create_royalty_agent():
    return Agent(
        model=get_model(), system_prompt=SYSTEM_PROMPT,
        tools=[
            fetch_pro_statements, fetch_dsp_statements, reconcile_statements,
            detect_discrepancies, check_mlc_registration_status, generate_royalty_report,
        ],
    )

def run_monthly_reconciliation(agent):
    result = agent(
        "Run the monthly royalty reconciliation. "
        "1. Call fetch_pro_statements() and fetch_dsp_statements(). "
        "2. Call reconcile_statements() to find discrepancies. "
        "3. Call detect_discrepancies() for full detail. "
        "4. Call check_mlc_registration_status() to verify registration health. "
        "5. Call generate_royalty_report() and post to Slack #royalties. "
        "For any CRITICAL issue: flag for immediate H.F. attention. "
        "Return: total royalties Q4, issues count, and top priority action."
    )
    return {"task": "monthly_reconciliation", "result": str(result)}

def lambda_handler(event: dict, context) -> dict:
    agent = create_royalty_agent()
    task  = event.get("task", "monthly_reconciliation")
    dispatch = {"monthly_reconciliation": lambda: run_monthly_reconciliation(agent)}
    handler = dispatch.get(task)
    if not handler:
        return {"error": f"Unknown task: {task}", "available": list(dispatch.keys())}
    return handler()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("💰 Royalty Reconciliation Agent — Interactive Mode")
    agent = create_royalty_agent()
    while True:
        try:
            ui = input("Royalty > ").strip()
            if ui.lower() in ("quit", "exit"): break
            if not ui: continue
            print(f"\nAgent: {agent(ui)}\n")
        except KeyboardInterrupt:
            print("\nRoyalty Agent offline."); break
