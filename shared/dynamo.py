"""
DynamoDB convenience helpers for the Lumin MAS fleet.

WHY THIS EXISTS:
Two friction points recur across every agent that writes to DynamoDB:
  1. Python floats are rejected by DynamoDB — every agent has to convert
     them to Decimal before writing, and every agent gets this slightly wrong
     or does it redundantly.
  2. The boto3 resource is created at module load in agent code, which breaks
     unit tests that import tool functions without AWS credentials set up.

This module solves both. The boto3 resource is lazy-initialized on first use.
coerce_floats() handles the float → Decimal conversion recursively so callers
never have to think about it.

TABLE KEY CONVENTION (from PATTERNS.md §5):
All agents in the fleet use lowercase 'pk' and 'sk' as the DynamoDB attribute
names for partition key and sort key. The helpers here assume this convention.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger(__name__)

# Lazy-initialized module-level resource. None until first call to get_dynamo().
# Tests can patch this to a MagicMock without needing real AWS credentials.
_resource = None


def get_dynamo():
    """
    Return the shared boto3 DynamoDB resource, initializing it on first call.

    Lazy initialization means this module can be imported and its pure
    helper functions (coerce_floats, now_iso) used in tests without
    any AWS credentials being present.
    """
    global _resource
    if _resource is None:
        import boto3
        _resource = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
    return _resource


def table(name: str):
    """Return a boto3 DynamoDB Table object for the given table name."""
    return get_dynamo().Table(name)


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string. Sortable in DynamoDB SK."""
    return datetime.now(timezone.utc).isoformat()


def coerce_floats(value: Any) -> Any:
    """
    Recursively convert Python floats to Decimal for DynamoDB compatibility.

    DynamoDB's boto3 resource rejects Python float values outright. Every
    numeric value that may be a float must be converted to Decimal(str(v))
    before writing. This function walks nested dicts, lists, and sets.

    Args:
        value: Any Python value — dict, list, set, float, or scalar.

    Returns:
        The same structure with all floats replaced by Decimal equivalents.
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: coerce_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [coerce_floats(v) for v in value]
    if isinstance(value, set):
        return {coerce_floats(v) for v in value}
    return value


def put_record(
    table_name: str,
    pk: str,
    sk: Optional[str] = None,
    **attrs: Any,
) -> dict:
    """
    Write a record to a DynamoDB table using the fleet's pk/sk key convention.

    Floats in attrs are coerced to Decimal automatically.

    Args:
        table_name: DynamoDB table name.
        pk:         Partition key value. e.g. "SIGNAL#PHASE_TRANSITION"
        sk:         Sort key value. e.g. ISO timestamp. Omit for PK-only tables.
        **attrs:    Additional attributes to store with the record.

    Returns:
        The boto3 put_item response dict.
    """
    item: dict[str, Any] = {"pk": pk}
    if sk is not None:
        item["sk"] = sk
    item.update(attrs)
    item = coerce_floats(item)
    return table(table_name).put_item(Item=item)


def query_latest(
    table_name: str,
    pk: str,
    limit: int = 30,
) -> list[dict]:
    """
    Query the most recent records for a partition key, newest first.

    Args:
        table_name: DynamoDB table name.
        pk:         Partition key value.
        limit:      Maximum number of records to return. Default 30.

    Returns:
        List of item dicts, sorted newest-first (ScanIndexForward=False).
    """
    resp = table(table_name).query(
        KeyConditionExpression=Key("pk").eq(pk),
        ScanIndexForward=False,
        Limit=limit,
    )
    return resp.get("Items", [])


def query_since(
    table_name: str,
    pk: str,
    since_iso: str,
) -> list[dict]:
    """
    Query all records for a partition key with sort key >= since_iso.

    Useful for "give me everything from the last N days" queries where
    the SK is an ISO timestamp. Results are returned oldest-first.

    Args:
        table_name: DynamoDB table name.
        pk:         Partition key value.
        since_iso:  ISO 8601 timestamp lower bound (inclusive).

    Returns:
        List of item dicts in ascending SK order.
    """
    resp = table(table_name).query(
        KeyConditionExpression=Key("pk").eq(pk) & Key("sk").gte(since_iso),
        ScanIndexForward=True,
    )
    return resp.get("Items", [])


def get_item(
    table_name: str,
    pk: str,
    sk: str,
) -> Optional[dict]:
    """
    Retrieve a single record by its exact pk + sk.

    Args:
        table_name: DynamoDB table name.
        pk:         Partition key value.
        sk:         Sort key value.

    Returns:
        The item dict, or None if not found.
    """
    resp = table(table_name).get_item(Key={"pk": pk, "sk": sk})
    return resp.get("Item")


def update_attribute(
    table_name: str,
    pk: str,
    sk: str,
    attribute: str,
    value: Any,
) -> dict:
    """
    Update a single attribute on an existing record.

    Uses ExpressionAttributeNames to safely handle reserved word attribute
    names (e.g. 'status', 'name'). Floats in value are coerced to Decimal.

    Args:
        table_name: DynamoDB table name.
        pk:         Partition key value.
        sk:         Sort key value.
        attribute:  Attribute name to update.
        value:      New value (floats coerced automatically).

    Returns:
        The updated item's full attribute map (ReturnValues=ALL_NEW).
    """
    resp = table(table_name).update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET #attr = :val",
        ExpressionAttributeNames={"#attr": attribute},
        ExpressionAttributeValues={":val": coerce_floats(value)},
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes", {})
