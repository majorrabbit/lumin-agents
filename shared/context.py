"""
Context-enrichment helper for Strands Agent system prompt construction.

WHY THIS EXISTS:
Agent 9 (Customer Success) has the most sophisticated agent factory in the
fleet: before creating the Strands Agent, it pulls the current user's
subscription tier, usage history, and churn risk from DynamoDB, formats that
data into a block of text, and injects it into the system prompt template via
str.replace(). This makes every conversation feel personalized — the agent
already knows who it's talking to.

The pattern is:
    enriched_prompt = SYSTEM_PROMPT.replace("{user_context}", user_context_block)

This module formalizes that mechanic so that Agents 3 (target supervisor
context), 11 (community characteristics), and 12 (cultural moment context)
can adopt it in the future without copying Agent 9's implementation.

The function is intentionally minimal — it does one thing and has no
dependencies outside the standard library.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Default formatter: render context dict as multiline "key: value" block.
# Matches Agent 9's manual formatting style.
def _default_formatter(context: dict[str, Any]) -> str:
    lines = []
    for k, v in context.items():
        if isinstance(v, list):
            v = ", ".join(str(i) for i in v) or "None"
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def enrich_system_prompt(
    template: str,
    placeholder: str,
    context: dict[str, Any],
    *,
    formatter: Optional[Callable[[dict[str, Any]], str]] = None,
) -> str:
    """
    Replace a placeholder in a system prompt template with formatted context.

    Formalizes the Agent 9 pattern of injecting per-user/per-target context
    into a system prompt before instantiating a Strands Agent. This makes the
    agent aware of its current subject before the first message arrives.

    Args:
        template:    The system prompt string containing the placeholder.
                     e.g. SYSTEM_PROMPT with "{user_context}" embedded.
        placeholder: The exact substring to replace. e.g. "{user_context}".
                     Must appear in template — logs a warning if not found.
        context:     Dict of key-value pairs to render into the placeholder.
                     e.g. {"tier": "Resonance Pro", "usage_trend": "DECLINING"}
        formatter:   Optional callable(context) -> str. If None, defaults to
                     a multiline "key: value" rendering. Provide a custom
                     formatter for agents with specific formatting needs
                     (e.g. Agent 3 might want "Supervisor: Jen Malone\n...").

    Returns:
        The template string with the placeholder replaced by the formatted
        context block.

    Examples:
        # Agent 9 style (uses default formatter):
        enriched = enrich_system_prompt(
            SYSTEM_PROMPT,
            "{user_context}",
            {
                "tier": "Resonance Pro",
                "account_age_days": 14,
                "features_used": ["Sync Brief Scanner", "Resonance Dashboard"],
                "usage_trend": "GROWING",
            }
        )

        # Agent 3 style (custom formatter):
        enriched = enrich_system_prompt(
            SYSTEM_PROMPT,
            "{supervisor_context}",
            supervisor_data,
            formatter=lambda ctx: (
                f"Target supervisor: {ctx['name']} ({ctx['company']})\n"
                f"Credits: {ctx['credits']}\n"
                f"Last pitched: {ctx.get('last_pitched', 'Never')}"
            ),
        )
    """
    if placeholder not in template:
        logger.warning(
            "Placeholder '%s' not found in template — system prompt returned unchanged.",
            placeholder,
        )
        return template

    render = formatter if formatter is not None else _default_formatter

    try:
        context_block = render(context)
    except Exception as exc:
        logger.warning(
            "Context formatter raised %s — using empty context block: %s",
            type(exc).__name__, exc,
        )
        context_block = "(context unavailable)"

    return template.replace(placeholder, context_block)
