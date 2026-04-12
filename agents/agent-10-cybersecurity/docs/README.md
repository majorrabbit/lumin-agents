# Agent 10: CyberSecurity & App Integrity Agent

**Lumin Luxe Inc. | AWS Strands Agents | Claude claude-sonnet-4-6**

Protects the SkyBlew Universe App and all three Lumin entities across seven security
layers — invisibly, so fans only ever see the bright sky they came for.

## Quick Start

```bash
cd agent-10-cybersecurity
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python agent.py        # interactive mode
```

## File Structure

```
agent-10-cybersecurity/
├── agent.py                  # Main agent + Lambda handler + scheduled tasks
├── requirements.txt
├── .env.example
├── tools/
│   ├── __init__.py
│   ├── waf_tools.py          # Layer 1: AWS WAF edge defense
│   ├── session_tools.py      # Layer 3: Session anomaly detection
│   ├── content_tools.py      # Layer 4: Asset integrity (Kid Sky, logo, app)
│   ├── guardduty_tools.py    # Layer 6: AWS GuardDuty threat intelligence
│   ├── fraud_tools.py        # Layer 7: Streaming fraud + GDPR privacy
│   ├── privacy_tools.py      # Re-exports from fraud_tools
│   └── alert_tools.py        # Slack + SNS notifications
├── tests/
│   └── test_agent.py         # Full test suite (pytest)
└── docs/
    └── DEPLOY.md             # Lambda deployment guide
```

## Scheduled Tasks (EventBridge)

| Cron | Task | Description |
|------|------|-------------|
| Hourly | `hourly_session_scan` | Scans active sessions for anomalies |
| Daily 02:00 UTC | `daily_content_integrity` | Verifies all app asset hashes |
| Daily 08:00 UTC | `daily_guardduty_digest` | Morning security briefing |
| Sundays 03:00 UTC | `weekly_fraud_scan` | Streaming fraud analysis |

## Lambda Event Format

```json
{
  "task": "daily_guardduty_digest",
  "params": {}
}
```

## The 21 Security Tools

| Group | Tools |
|-------|-------|
| WAF | check_waf_block_rate, get_waf_recent_blocked_requests, update_waf_ip_blocklist |
| Sessions | scan_active_sessions_for_anomalies, invalidate_session, get_session_risk_report |
| Content | verify_asset_integrity, reset_asset_baseline_hash, invalidate_cloudfront_cache |
| GuardDuty | get_guardduty_findings, acknowledge_guardduty_finding, get_security_summary |
| Fraud | scan_streaming_anomalies, get_fraud_risk_report, prepare_dsp_fraud_report |
| Privacy | process_gdpr_deletion_request, audit_data_retention_compliance, check_pii_exposure_in_logs |
| Alerts | post_security_alert_to_slack, send_critical_page_to_engineer, log_security_event |

## Run Tests

```bash
pytest tests/ -v
```

## Deploy to Lambda

See `docs/DEPLOY.md` for full deployment instructions.

**Core principle:** Security must be invisible to fans.
A fan loading Kid Sky's face should never see a raw error.
