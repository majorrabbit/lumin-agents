"""
Tests for shared/context.py

Scenarios:
- Placeholder replaced with default formatter output
- Custom formatter callable used when provided
- List values in context rendered as comma-separated string
- Placeholder not found in template: returns template unchanged, logs warning
- Formatter raises: returns template with "(context unavailable)" block
- Empty context dict: no crash
"""

import logging
from unittest.mock import patch

import pytest

from shared.context import enrich_system_prompt


# ─── Default formatter ────────────────────────────────────────────────────────

def test_placeholder_replaced():
    template = "Hello {ctx} world"
    result = enrich_system_prompt(template, "{ctx}", {"name": "Alice"})
    assert "{ctx}" not in result
    assert "name: Alice" in result


def test_all_context_keys_present():
    template = "CONTEXT: {ctx}"
    ctx = {"tier": "Resonance Pro", "age": 14, "trend": "GROWING"}
    result = enrich_system_prompt(template, "{ctx}", ctx)
    assert "tier: Resonance Pro" in result
    assert "age: 14" in result
    assert "trend: GROWING" in result


def test_list_value_rendered_as_csv():
    template = "{ctx}"
    ctx = {"features": ["Sync Scanner", "Resonance Dashboard"]}
    result = enrich_system_prompt(template, "{ctx}", ctx)
    assert "Sync Scanner" in result
    assert "Resonance Dashboard" in result


def test_empty_list_renders_none():
    template = "{ctx}"
    ctx = {"features": []}
    result = enrich_system_prompt(template, "{ctx}", ctx)
    assert "features: None" in result


def test_empty_context_no_crash():
    template = "Prompt {ctx} end"
    result = enrich_system_prompt(template, "{ctx}", {})
    assert "{ctx}" not in result


# ─── Custom formatter ─────────────────────────────────────────────────────────

def test_custom_formatter_used():
    template = "TARGET: {sup}"
    formatter = lambda ctx: f"Name={ctx['name']} Company={ctx['company']}"
    result = enrich_system_prompt(
        template, "{sup}",
        {"name": "Jen Malone", "company": "Black & White Music"},
        formatter=formatter,
    )
    assert "Name=Jen Malone" in result
    assert "Company=Black & White Music" in result


def test_custom_formatter_output_replaces_placeholder():
    template = "A {p} B"
    result = enrich_system_prompt(template, "{p}", {"k": "v"}, formatter=lambda c: "CUSTOM")
    assert result == "A CUSTOM B"


# ─── Placeholder not in template ─────────────────────────────────────────────

def test_missing_placeholder_returns_unchanged(caplog):
    template = "No placeholder here"
    with caplog.at_level(logging.WARNING, logger="shared.context"):
        result = enrich_system_prompt(template, "{MISSING}", {"k": "v"})
    assert result == template
    assert "MISSING" in caplog.text


# ─── Formatter exception ─────────────────────────────────────────────────────

def test_formatter_exception_returns_unavailable_block(caplog):
    def bad_formatter(ctx):
        raise ValueError("intentional failure")

    template = "Start {ctx} End"
    with caplog.at_level(logging.WARNING, logger="shared.context"):
        result = enrich_system_prompt(
            template, "{ctx}", {"k": "v"}, formatter=bad_formatter
        )
    assert "context unavailable" in result
    assert "intentional failure" in caplog.text


# ─── Multiple placeholders ────────────────────────────────────────────────────

def test_only_specified_placeholder_replaced():
    template = "A {ctx} B {other} C"
    result = enrich_system_prompt(template, "{ctx}", {"x": "1"})
    assert "{ctx}" not in result
    assert "{other}" in result  # unrelated placeholder left alone


# ─── Agent 9 realistic scenario ───────────────────────────────────────────────

def test_agent9_style_enrichment():
    """Replicate Agent 9's create_cs_agent() context injection."""
    system_prompt = (
        "You are Lumin.\n"
        "WHAT YOU KNOW ABOUT THIS USER:\n"
        "{user_context}\n"
        "YOUR ROLE: help them succeed."
    )
    user_data = {
        "tier": "Resonance Pro",
        "account_age_days": 7,
        "last_active": "2026-04-10",
        "features_used": ["Sync Brief Scanner"],
        "features_not_used": ["Export to PDF", "API Access"],
        "usage_trend": "GROWING",
        "open_tickets": 0,
        "churn_risk": "LOW",
    }
    result = enrich_system_prompt(system_prompt, "{user_context}", user_data)
    assert "tier: Resonance Pro" in result
    assert "usage_trend: GROWING" in result
    assert "{user_context}" not in result
