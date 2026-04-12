"""
tools/content_tools.py — App content integrity checking for Agent 10.
Verifies Kid Sky, SkyBlew Logo, and all critical app assets are untampered.
"""
import json, hashlib, boto3
from datetime import datetime, timezone
from strands import tool

s3 = boto3.client("s3", region_name="us-east-1")
cf = boto3.client("cloudfront", region_name="us-east-1")
dynamo = boto3.resource("dynamodb", region_name="us-east-1")
hashes_table = dynamo.Table("security-asset-hashes")

BUCKET = "skyblew-universe-app-assets"
CF_DISTRIBUTION_ID = "EXXXXXXXXXXXXXX"   # Replace with actual CloudFront ID

PROTECTED_ASSETS = [
    "Kid_Sky.png",
    "SkyBlew_Logo_-_No_BG.PNG",
    "SkyBlewUniverseApp.html",
    "index.js",
    "styles.css",
    "manifest.json",
]


@tool
def verify_asset_integrity() -> str:
    """
    Compute the current SHA-256 hash of every protected SkyBlew Universe App
    asset in S3 and compare against the stored baseline hashes in DynamoDB.
    Returns a full integrity report: which assets passed, which failed, and
    recommended actions for any mismatch detected.

    Returns:
        JSON report with passed/failed assets, hashes, and recommended actions.
    """
    results = {"passed": [], "failed": [], "new_baselines": [], "checked_at": datetime.now(timezone.utc).isoformat()}

    for asset in PROTECTED_ASSETS:
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=asset)
            current_hash = hashlib.sha256(obj["Body"].read()).hexdigest()

            stored_resp = hashes_table.get_item(
                Key={"asset_key": asset, "environment": "production"}
            )
            stored = stored_resp.get("Item")

            if not stored:
                # First run — establish baseline
                hashes_table.put_item(Item={
                    "asset_key": asset,
                    "environment": "production",
                    "sha256": current_hash,
                    "baseline_set_at": datetime.now(timezone.utc).isoformat(),
                })
                results["new_baselines"].append({"asset": asset, "hash": current_hash})
            elif stored["sha256"] != current_hash:
                results["failed"].append({
                    "asset": asset,
                    "stored_hash": stored["sha256"],
                    "current_hash": current_hash,
                    "baseline_set_at": stored.get("baseline_set_at"),
                    "action": "INVALIDATE_CF_CACHE + ALERT_CRITICAL",
                })
            else:
                results["passed"].append({"asset": asset, "hash": current_hash})

        except Exception as e:
            results["failed"].append({"asset": asset, "error": str(e), "action": "INVESTIGATE_S3_ACCESS"})

    results["integrity_status"] = "CLEAN" if not results["failed"] else "TAMPERED"
    return json.dumps(results)


@tool
def reset_asset_baseline_hash(asset_name: str, confirmed_by: str) -> str:
    """
    Reset the stored baseline hash for a specific asset to its current value.
    Only use this after a legitimate intentional update to the app (e.g., Eric
    pushed a new version of Kid_Sky.png). Requires confirmed_by name for audit trail.

    Args:
        asset_name: The filename of the asset to reset (must be in protected list).
        confirmed_by: Name of the person authorizing the reset (audit log).

    Returns:
        JSON confirmation with old hash, new hash, and audit record.
    """
    if asset_name not in PROTECTED_ASSETS:
        return json.dumps({"error": f"{asset_name} is not in the protected assets list.", "protected_assets": PROTECTED_ASSETS})

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=asset_name)
        new_hash = hashlib.sha256(obj["Body"].read()).hexdigest()

        stored = hashes_table.get_item(
            Key={"asset_key": asset_name, "environment": "production"}
        ).get("Item", {})
        old_hash = stored.get("sha256", "NONE")

        hashes_table.put_item(Item={
            "asset_key": asset_name,
            "environment": "production",
            "sha256": new_hash,
            "baseline_set_at": datetime.now(timezone.utc).isoformat(),
            "reset_by": confirmed_by,
            "previous_hash": old_hash,
        })

        return json.dumps({
            "status": "BASELINE_RESET",
            "asset": asset_name,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "reset_by": confirmed_by,
            "reset_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def invalidate_cloudfront_cache(asset_names: list) -> str:
    """
    Immediately invalidate the CloudFront cache for one or more assets.
    Use when content integrity check detects a hash mismatch — prevents
    fans from receiving tampered content while the issue is investigated.
    This is a safe, reversible action and does not require human approval.

    Args:
        asset_names: List of asset filenames to invalidate (e.g., ["index.js"]).

    Returns:
        JSON with invalidation ID and estimated completion time.
    """
    try:
        paths = [f"/{name}" for name in asset_names]
        response = cf.create_invalidation(
            DistributionId=CF_DISTRIBUTION_ID,
            InvalidationBatch={
                "Paths": {"Quantity": len(paths), "Items": paths},
                "CallerReference": str(datetime.now(timezone.utc).timestamp()),
            },
        )
        inv = response.get("Invalidation", {})
        return json.dumps({
            "status": "INVALIDATION_CREATED",
            "invalidation_id": inv.get("Id"),
            "assets_invalidated": asset_names,
            "estimated_completion": "5-10 minutes",
            "note": "Fans will receive fresh content from S3 after propagation.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
