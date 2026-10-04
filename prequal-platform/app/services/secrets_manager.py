"""Runtime secrets loading for the Prequal API.

Production secrets live in AWS Secrets Manager (see
``docs/SECRETS_MANAGEMENT.md`` and ``terraform/main.tf``). ECS injects the
vaulted values as environment variables at task start, which is enough for the
common case, but we also want a single, auditable code path that:

* fetches secrets directly from AWS Secrets Manager when enabled,
* prefers already-present environment variables (so ECS injection, local
  ``.env`` files and tests keep working unchanged),
* never logs secret values, and
* degrades gracefully when AWS or ``boto3`` is unavailable (local/dev/test).

Existing application code keeps reading configuration with ``os.getenv``. Call
:func:`hydrate_environment` once during application startup to populate any
missing variables from the vault.

The loader is intentionally dependency-light: ``boto3`` is imported lazily so
that importing this module never requires AWS libraries or credentials.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, Iterable, List, Mapping, Optional

logger = logging.getLogger(__name__)

# Secret names/ARNs to hydrate into the process environment on startup.
# Comma-separated; empty/unset disables vault hydration entirely.
ENVIRONMENT_SECRETS_ENV = "SECRETS_MANAGER_ENVIRONMENT_SECRETS"

# Master switch. Accepts "1", "true", "yes", "on" (case-insensitive).
ENABLED_ENV = "SECRETS_MANAGER_ENABLED"

# Optional override for the AWS region used by the Secrets Manager client.
REGION_ENV = "SECRETS_MANAGER_REGION"


def _is_truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_secret_payload(payload: str) -> Dict[str, str]:
    """Normalise a Secrets Manager ``SecretString`` into a flat mapping.

    JSON objects (the format used by all Prequal secrets) are expanded into
    their keys. A plain string is returned under a synthetic ``"value"`` key so
    callers can still retrieve it via the secret name.
    """
    text = (payload or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Secret payload looked like JSON but failed to parse")
            return {"value": text}
        if isinstance(parsed, Mapping):
            return {str(k): "" if v is None else str(v) for k, v in parsed.items()}
    return {"value": text}


class SecretsManager:
    """Thin, cached wrapper around AWS Secrets Manager.

    Instances are cheap; a process-wide singleton is exposed as
    :data:`secrets_manager`.
    """

    def __init__(self, region: Optional[str] = None, enabled: Optional[bool] = None):
        self._region = region if region is not None else os.getenv(REGION_ENV)
        self._enabled = _is_truthy(os.getenv(ENABLED_ENV)) if enabled is None else enabled
        self._client = None
        self._client_lock = threading.Lock()
        self._cache: Dict[str, Dict[str, str]] = {}
        self._cache_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """Whether direct vault access is configured for this process."""
        return bool(self._enabled)

    def _get_client(self):
        """Lazily construct a boto3 Secrets Manager client.

        Returns ``None`` (and disables further attempts) when boto3 is missing
        or the client cannot be created, so callers fall back to env vars.
        """
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                import boto3  # imported lazily; optional in local/dev
            except ImportError:
                logger.warning(
                    "boto3 not installed; secrets manager vault access disabled"
                )
                self._enabled = False
                return None
            try:
                self._client = boto3.client(
                    "secretsmanager", region_name=self._region or None
                )
            except Exception as exc:  # pragma: no cover - depends on AWS env
                logger.warning("Could not create Secrets Manager client: %s", exc)
                self._enabled = False
                return None
            return self._client

    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return a single secret string value.

        Resolution order:
        1. environment variable with the same name (ECS injection / local dev),
        2. cached vault value,
        3. AWS Secrets Manager lookup,
        4. ``default``.
        """
        env_value = os.getenv(name)
        if env_value is not None:
            return env_value
        if default is None:
            # Only hit the vault when no explicit default was provided.
            payload = self._load_payload(name)
            if payload:
                return payload.get("value")
            return None
        payload = self._load_payload(name)
        if payload:
            return payload.get("value", default)
        return default

    def get_secrets(self, name: str) -> Dict[str, str]:
        """Return the full JSON mapping stored under ``name`` (cached)."""
        return dict(self._load_payload(name))

    def refresh(self, name: Optional[str] = None) -> None:
        """Drop the cache for ``name`` (or everything when ``name`` is None)."""
        with self._cache_lock:
            if name is None:
                self._cache.clear()
            else:
                self._cache.pop(name, None)

    def _load_payload(self, name: str) -> Dict[str, str]:
        if not self.enabled:
            return {}
        with self._cache_lock:
            cached = self._cache.get(name)
        if cached is not None:
            return cached

        client = self._get_client()
        if client is None:
            return {}
        try:
            response = client.get_secret_value(SecretId=name)
        except Exception as exc:  # pragma: no cover - depends on AWS env
            logger.warning("Failed to fetch secret '%s': %s", name, type(exc).__name__)
            return {}

        payload = _parse_secret_payload(response.get("SecretString", ""))
        with self._cache_lock:
            self._cache[name] = payload
        return payload

    def hydrate_environment(self, secret_names: Optional[Iterable[str]] = None) -> List[str]:
        """Populate missing environment variables from the vault.

        Existing environment variables are never overwritten, so ECS-injected
        values and test overrides always win. Returns the list of variable
        names that were set.
        """
        if not self.enabled:
            return []
        names = (
            list(secret_names)
            if secret_names is not None
            else [n.strip() for n in os.getenv(ENVIRONMENT_SECRETS_ENV, "").split(",") if n.strip()]
        )
        populated: List[str] = []
        for name in names:
            payload = self._load_payload(name)
            if not payload:
                continue
            if len(payload) == 1 and "value" in payload:
                # Plain-string secret: map the secret name itself to the value.
                key = name.rsplit("/", 1)[-1] or name
                targets = {key: payload["value"]}
            else:
                targets = payload
            for key, value in targets.items():
                if not key or key in os.environ:
                    continue
                os.environ[key] = value
                populated.append(key)
        if populated:
            logger.info("Hydrated %d environment variable(s) from Secrets Manager", len(populated))
        return populated


# Process-wide singleton.
secrets_manager = SecretsManager()


def hydrate_environment(secret_names: Optional[Iterable[str]] = None) -> List[str]:
    """Module-level convenience wrapper around ``secrets_manager``."""
    return secrets_manager.hydrate_environment(secret_names)
