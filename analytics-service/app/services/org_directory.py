"""Cross-service organization directory lookup.

Per ADR-001, cross-service data needs are resolved via API calls. When the
organization service is not configured or unreachable, lookups degrade
gracefully to None so reporting never fails.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict = {}


def get_organization_name(org_id: str) -> Optional[str]:
    """Resolve an organization name from the organization service (cached)."""
    if not settings.ORG_SERVICE_URL:
        return None
    if org_id in _cache:
        return _cache[org_id]
    try:
        resp = httpx.get(
            f"{settings.ORG_SERVICE_URL.rstrip('/')}/api/v1/organizations/{org_id}",
            timeout=settings.ORG_SERVICE_TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            name = resp.json().get("name")
            _cache[org_id] = name
            return name
    except Exception as exc:
        logger.warning("Organization lookup failed for %s: %s", org_id, exc)
    return None


def reset_cache() -> None:
    _cache.clear()
