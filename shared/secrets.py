"""
Credential resolution for the Lumin MAS fleet.

WHY THIS EXISTS:
Every agent needs an ANTHROPIC_API_KEY and most need third-party API keys
(Chartmetric, Spotify, etc.). The pattern is always the same: check the
environment variable first, fall back to AWS Secrets Manager only if the
env var is absent, and raise a clear error if neither source has a value.

Without this helper, each agent copies its own version of the SBIA-style
get_model() pattern. This module makes that pattern importable and testable
in one place.

CACHING:
Secrets Manager round trips are expensive (~10ms each). Once a secret is
fetched it is cached in the process for the process lifetime — the same
secret value won't be fetched twice. The cache can be cleared between calls
with _get_from_sm.cache_clear() (useful in tests).
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _get_from_sm(secret_id: str, secret_key: Optional[str]) -> str:
    """
    Fetch a value from AWS Secrets Manager, cached per (secret_id, secret_key).

    Args:
        secret_id:  The Secrets Manager secret name or ARN.
                    e.g. "lumin/anthropic-api-key"
        secret_key: If the secret is a JSON object, extract this key from it.
                    Pass None to return the raw SecretString.

    Returns:
        The secret value as a plain string.

    Raises:
        Exception: Any boto3 / Secrets Manager error propagates to the caller.
    """
    import boto3  # lazy import — keeps this module importable without AWS

    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_id)
    raw = response["SecretString"]

    if secret_key:
        return json.loads(raw)[secret_key]
    return raw


def get_credential(
    env_var: str,
    secret_id: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    Resolve a credential using env var first, Secrets Manager fallback.

    Tries sources in order:
      1. os.environ[env_var]          ← always checked first
      2. Secrets Manager (secret_id)  ← only if env var absent AND secret_id given
      3. EnvironmentError             ← raised with a helpful message

    This matches the SBIA get_model() pattern documented in PATTERNS.md §3.

    Args:
        env_var:    Name of the environment variable to check first.
                    e.g. "ANTHROPIC_API_KEY"
        secret_id:  AWS Secrets Manager secret name/ARN for the fallback.
                    e.g. "lumin/anthropic-api-key"
                    Pass None to disable Secrets Manager fallback entirely.
        secret_key: If the SM secret is a JSON object, extract this key.
                    e.g. "api_key" to get {"api_key": "sk-..."}.SecretString

    Returns:
        The credential value as a plain string.

    Raises:
        EnvironmentError: Neither the env var nor Secrets Manager had a value.

    Examples:
        # Simple env-var-only (most agents)
        key = get_credential("ANTHROPIC_API_KEY")

        # With SM fallback (SBIA pattern — recommended for production)
        key = get_credential(
            "ANTHROPIC_API_KEY",
            secret_id="lumin/anthropic-api-key",
        )

        # SM secret is a JSON object — extract one key
        token = get_credential(
            "CHARTMETRIC_API_KEY",
            secret_id="lumin/chartmetric-credentials",
            secret_key="api_key",
        )
    """
    value = os.environ.get(env_var)
    if value:
        return value

    if secret_id:
        try:
            logger.debug("Env var '%s' unset — trying Secrets Manager '%s'",
                         env_var, secret_id)
            return _get_from_sm(secret_id, secret_key)
        except Exception as exc:
            raise EnvironmentError(
                f"Credential not found. "
                f"Env var '{env_var}' is unset and Secrets Manager lookup "
                f"for '{secret_id}' failed: {exc}"
            ) from exc

    raise EnvironmentError(
        f"Required credential not found. "
        f"Set the '{env_var}' environment variable "
        f"(or pass secret_id= to enable Secrets Manager fallback)."
    )
