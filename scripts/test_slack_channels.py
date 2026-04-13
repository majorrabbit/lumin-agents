"""
scripts/test_slack_channels.py

Pre-deploy Slack channel verification script for the Lumin Agent Fleet.

Reads Incoming Webhook URLs from a local .env file and posts a single test
message to each channel. Run this after building the Slack workspace (per
docs/SLACK_WORKSPACE.md Section 2) and before starting Phase 4 deploy.

Usage:
    pip install requests python-dotenv
    python scripts/test_slack_channels.py

Prerequisites:
    Create a local .env file with all webhook URLs — see docs/SLACK_WORKSPACE.md
    Section 4 for the exact variable names and format.
    Do NOT commit the .env file — it contains live webhook secrets.

Exit codes:
    0 — all webhooks responded with HTTP 200
    1 — one or more webhooks failed or were not configured
"""

import os
import sys
import json
import time

import requests
from dotenv import load_dotenv

# Load .env from the project root (one level up from scripts/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_project_root, ".env"))

TEST_MESSAGE = "Lumin fleet pre-deploy test — if you see this, the channel is wired correctly."

# Maps env var name → human-readable channel label
# Order matches the morning workflow (docs/SLACK_WORKSPACE.md Section 1A)
WEBHOOK_MAP = [
    ("SLACK_RESONANCE_WEBHOOK",  "#resonance-intelligence  (Agent 01)"),
    ("SLACK_SYNC_WEBHOOK",       "#sync-queue              (Agent 02)"),
    ("SLACK_PITCH_WEBHOOK",      "#sync-pitches            (Agent 03)"),
    ("SLACK_AG_WEBHOOK",         "#anime-gaming-intel      (Agent 04)"),
    ("SLACK_ROYALTY_WEBHOOK",    "#royalty-reconciliation  (Agent 05)"),
    ("SLACK_CULTURAL_WEBHOOK",   "#cultural-moments        (Agent 06)"),
    ("SLACK_FAN_WEBHOOK",        "#fan-intelligence        (Agent 07)"),
    ("SLACK_AR_WEBHOOK",         "#ar-catalog              (Agent 08)"),
    ("SLACK_CS_WEBHOOK",         "#cs-escalations          (Agent 09)"),
    ("SLACK_SECURITY_WEBHOOK",   "#security-alerts         (Agent 10)"),
    ("SLACK_DISCOVERY_WEBHOOK",  "#fan-discovery-queue     (Agent 11)"),
    ("SLACK_APPROVAL_WEBHOOK",   "#social-approvals        (Agent 12 — approval)"),
    ("SLACK_SOCIAL_WEBHOOK",     "#social-intelligence     (Agent 12 — digest)"),
    ("SBIA_SLACK_WEBHOOK",       "#hot-leads               (SBIA)"),
]


def post_test_message(webhook_url: str, channel_label: str) -> dict:
    """Post the standard pre-deploy test message to one Slack webhook URL."""
    payload = {
        "text": TEST_MESSAGE,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"✅ *Lumin fleet pre-deploy test*\n"
                        f"Channel: `{channel_label.strip()}`\n"
                        f"If you see this, the channel is wired correctly."
                    ),
                },
            }
        ],
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return {
            "status": "SENT" if resp.ok else "FAILED",
            "http_status": resp.status_code,
            "body": resp.text[:120],
        }
    except requests.exceptions.RequestException as exc:
        return {"status": "ERROR", "error": str(exc)}


def main() -> int:
    print("=" * 70)
    print("Lumin Fleet — Slack Channel Pre-Deploy Verification")
    print("=" * 70)
    print(f"Test message: \"{TEST_MESSAGE}\"")
    print()

    results = []
    failures = 0

    for env_var, channel_label in WEBHOOK_MAP:
        url = os.environ.get(env_var, "")
        if not url:
            print(f"  SKIP    {env_var:<32} — not set in .env")
            results.append((env_var, channel_label, "SKIP"))
            failures += 1
            continue

        result = post_test_message(url, channel_label)
        status = result["status"]

        if status == "SENT":
            print(f"  SENT    {env_var:<32}  →  {channel_label.strip()}")
        elif status == "FAILED":
            http = result.get("http_status", "?")
            body = result.get("body", "")
            print(f"  FAILED  {env_var:<32}  →  {channel_label.strip()}  (HTTP {http}: {body})")
            failures += 1
        else:
            err = result.get("error", "unknown error")
            print(f"  ERROR   {env_var:<32}  →  {channel_label.strip()}  ({err})")
            failures += 1

        results.append((env_var, channel_label, status))

        # Small delay to avoid Slack rate limiting (1 req/sec is safe)
        time.sleep(0.5)

    print()
    print("=" * 70)

    sent_count = sum(1 for _, _, s in results if s == "SENT")
    skip_count = sum(1 for _, _, s in results if s == "SKIP")
    fail_count = sum(1 for _, _, s in results if s in ("FAILED", "ERROR"))

    print(f"Results: {sent_count} SENT  |  {skip_count} SKIPPED  |  {fail_count} FAILED/ERROR")
    print(f"Total webhooks configured: {len(WEBHOOK_MAP)}")
    print()

    if failures == 0:
        print("✅ All webhooks verified. Slack workspace is ready for Phase 4.")
        print()
        print("Next steps:")
        print("  1. Visually confirm each test message appeared in its channel in Slack")
        print("  2. Confirm H.F. and Eric can see messages in #security-ops and #security-alerts")
        print("  3. Delete the local .env file containing the webhook URLs")
        print("  4. Store all webhook URLs in AWS Secrets Manager (lumin/slack-webhooks/*)")
        return 0
    else:
        print(f"❌ {failures} webhook(s) failed or were not configured.")
        print()
        print("Fix steps:")
        print("  - SKIP: Add the missing webhook URL to your local .env file")
        print("  - FAILED: Check the webhook URL is correct and the channel exists")
        print("  - ERROR: Check network connectivity to hooks.slack.com")
        print()
        print("See docs/SLACK_WORKSPACE.md Section 2 for setup instructions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
