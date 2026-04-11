"""
Lumin MAS shared helper library.

Optional helpers that any agent in the fleet may import to get consistent
fleet-wide behavior for credential resolution, Slack alerts, DynamoDB access,
approval queue submissions, BOID-structured audit logging, structured JSON
logging, and context-enriched system prompt construction.

None of these modules are required. Every agent in the fleet works without
importing from this package. The helpers exist to eliminate copy-paste and
ensure that agents built after Phase 1 start from a consistent foundation.

Usage:
    from shared.secrets import get_credential
    from shared.slack import post_alert
    from shared.dynamo import put_record, query_latest
    from shared.approval import submit_for_approval
    from shared.context import enrich_system_prompt
    from shared.boid import log_action
    from shared.logging_config import configure_logging
"""
