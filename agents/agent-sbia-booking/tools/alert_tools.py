# tools/alert_tools.py — Re-exports from crm_tools.py
from tools.crm_tools import (  # noqa: F401
    monitor_email_responses,
    classify_response_sentiment,
    send_alert_to_hf,
)
