"""
Tests for shared/dynamo.py

Scenarios:
- coerce_floats: simple float, dict with floats, nested dict, list, set, no-op types
- now_iso: returns valid ISO string with UTC timezone marker
- put_record: writes correct item structure, floats coerced, SK optional
- query_latest: calls query with ScanIndexForward=False and Limit
- query_since: calls query with >= SK condition
- get_item: returns Item or None
- update_attribute: calls update_item with correct expressions
"""

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

import shared.dynamo as dyn
from shared.dynamo import (
    coerce_floats,
    get_item,
    now_iso,
    put_record,
    query_latest,
    query_since,
    update_attribute,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_dynamo_resource():
    """Reset the lazy _resource to None before each test."""
    original = dyn._resource
    dyn._resource = None
    yield
    dyn._resource = original


@pytest.fixture
def mock_table():
    """Return a MagicMock that stands in for a boto3 DynamoDB Table."""
    tbl = MagicMock()
    tbl.put_item.return_value = {}
    tbl.query.return_value = {"Items": []}
    tbl.get_item.return_value = {}
    tbl.update_item.return_value = {"Attributes": {}}
    tbl.scan.return_value = {"Items": []}
    return tbl


@pytest.fixture
def patched_dynamo(mock_table):
    """Patch boto3.resource so table() returns mock_table."""
    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_table
        yield mock_table


# ─── coerce_floats ───────────────────────────────────────────────────────────

class TestCoerceFloats:
    def test_simple_float(self):
        assert coerce_floats(3.14) == Decimal("3.14")

    def test_int_unchanged(self):
        assert coerce_floats(42) == 42
        assert isinstance(coerce_floats(42), int)

    def test_string_unchanged(self):
        assert coerce_floats("hello") == "hello"

    def test_none_unchanged(self):
        assert coerce_floats(None) is None

    def test_bool_unchanged(self):
        assert coerce_floats(True) is True

    def test_dict_float_values(self):
        result = coerce_floats({"score": 0.91, "label": "high"})
        assert result["score"] == Decimal("0.91")
        assert result["label"] == "high"

    def test_nested_dict(self):
        result = coerce_floats({"outer": {"inner": 1.5}})
        assert result["outer"]["inner"] == Decimal("1.5")

    def test_list_of_floats(self):
        result = coerce_floats([1.0, 2.0, 3])
        assert result[0] == Decimal("1.0")
        assert result[1] == Decimal("2.0")
        assert result[2] == 3

    def test_list_with_nested_dict(self):
        result = coerce_floats([{"x": 0.5}])
        assert result[0]["x"] == Decimal("0.5")

    def test_set_of_floats(self):
        result = coerce_floats({1.1, 2.2})
        assert Decimal("1.1") in result
        assert Decimal("2.2") in result

    def test_deeply_nested(self):
        result = coerce_floats({"a": {"b": {"c": 9.9}}})
        assert result["a"]["b"]["c"] == Decimal("9.9")

    def test_zero_float(self):
        assert coerce_floats(0.0) == Decimal("0.0")

    def test_negative_float(self):
        assert coerce_floats(-3.14) == Decimal("-3.14")


# ─── now_iso ─────────────────────────────────────────────────────────────────

class TestNowIso:
    def test_returns_string(self):
        result = now_iso()
        assert isinstance(result, str)

    def test_contains_utc_marker(self):
        result = now_iso()
        # datetime.isoformat() with UTC timezone includes +00:00
        assert "+00:00" in result or result.endswith("Z")

    def test_is_sortable(self):
        """Two consecutive calls should produce sortable timestamps."""
        t1 = now_iso()
        t2 = now_iso()
        assert t1 <= t2  # ISO strings sort lexicographically == chronologically

    def test_length_reasonable(self):
        result = now_iso()
        assert 20 <= len(result) <= 35


# ─── put_record ──────────────────────────────────────────────────────────────

class TestPutRecord:
    def test_basic_write_with_sk(self, patched_dynamo):
        put_record("my-table", "PK#test", "SK#001", score=0.75, label="high")
        patched_dynamo.put_item.assert_called_once()
        item = patched_dynamo.put_item.call_args[1]["Item"]
        assert item["pk"] == "PK#test"
        assert item["sk"] == "SK#001"
        assert item["score"] == Decimal("0.75")
        assert item["label"] == "high"

    def test_write_without_sk(self, patched_dynamo):
        put_record("my-table", "PK#only", name="Alice")
        item = patched_dynamo.put_item.call_args[1]["Item"]
        assert "sk" not in item
        assert item["pk"] == "PK#only"

    def test_floats_coerced(self, patched_dynamo):
        put_record("t", "PK#1", "SK#1", entropy=1.4142)
        item = patched_dynamo.put_item.call_args[1]["Item"]
        assert isinstance(item["entropy"], Decimal)


# ─── query_latest ────────────────────────────────────────────────────────────

class TestQueryLatest:
    def test_queries_correct_pk(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": [{"pk": "X", "sk": "t1"}]}
        results = query_latest("my-table", "PK#resonance")
        call_kwargs = patched_dynamo.query.call_args[1]
        assert call_kwargs.get("ScanIndexForward") is False

    def test_default_limit_30(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": []}
        query_latest("my-table", "PK#x")
        call_kwargs = patched_dynamo.query.call_args[1]
        assert call_kwargs.get("Limit") == 30

    def test_custom_limit(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": []}
        query_latest("my-table", "PK#x", limit=5)
        call_kwargs = patched_dynamo.query.call_args[1]
        assert call_kwargs.get("Limit") == 5

    def test_returns_items_list(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": [{"pk": "A"}, {"pk": "B"}]}
        results = query_latest("my-table", "PK#x")
        assert len(results) == 2

    def test_empty_result(self, patched_dynamo):
        patched_dynamo.query.return_value = {}
        results = query_latest("my-table", "PK#x")
        assert results == []


# ─── query_since ─────────────────────────────────────────────────────────────

class TestQuerySince:
    def test_scans_forward(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": []}
        query_since("my-table", "PK#x", "2026-04-01T00:00:00+00:00")
        call_kwargs = patched_dynamo.query.call_args[1]
        assert call_kwargs.get("ScanIndexForward") is True

    def test_returns_items(self, patched_dynamo):
        patched_dynamo.query.return_value = {"Items": [{"pk": "A", "sk": "t"}]}
        results = query_since("my-table", "PK#x", "2026-01-01T00:00:00+00:00")
        assert len(results) == 1


# ─── get_item ────────────────────────────────────────────────────────────────

class TestGetItem:
    def test_returns_item_when_found(self, patched_dynamo):
        patched_dynamo.get_item.return_value = {"Item": {"pk": "P", "sk": "S", "val": 1}}
        result = get_item("t", "P", "S")
        assert result == {"pk": "P", "sk": "S", "val": 1}

    def test_returns_none_when_not_found(self, patched_dynamo):
        patched_dynamo.get_item.return_value = {}
        result = get_item("t", "P", "S")
        assert result is None

    def test_calls_with_correct_key(self, patched_dynamo):
        patched_dynamo.get_item.return_value = {}
        get_item("my-table", "PK#1", "SK#2")
        call_kwargs = patched_dynamo.get_item.call_args[1]
        assert call_kwargs["Key"] == {"pk": "PK#1", "sk": "SK#2"}


# ─── update_attribute ────────────────────────────────────────────────────────

class TestUpdateAttribute:
    def test_calls_update_item(self, patched_dynamo):
        patched_dynamo.update_item.return_value = {"Attributes": {"pk": "P", "status": "DONE"}}
        result = update_attribute("t", "P", "S", "status", "DONE")
        patched_dynamo.update_item.assert_called_once()

    def test_returns_attributes(self, patched_dynamo):
        patched_dynamo.update_item.return_value = {"Attributes": {"x": 1}}
        result = update_attribute("t", "P", "S", "x", 1)
        assert result == {"x": 1}

    def test_float_value_coerced(self, patched_dynamo):
        patched_dynamo.update_item.return_value = {"Attributes": {}}
        update_attribute("t", "P", "S", "score", 0.88)
        call_kwargs = patched_dynamo.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":val"] == Decimal("0.88")

    def test_uses_expression_attribute_names(self, patched_dynamo):
        """Reserved words like 'status' must be escaped."""
        patched_dynamo.update_item.return_value = {"Attributes": {}}
        update_attribute("t", "P", "S", "status", "ACTIVE")
        call_kwargs = patched_dynamo.update_item.call_args[1]
        assert "#attr" in call_kwargs["ExpressionAttributeNames"]
        assert call_kwargs["ExpressionAttributeNames"]["#attr"] == "status"
