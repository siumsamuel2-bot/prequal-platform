"""Redis-backed response caching for the compliance API.

Provides an async, tenant-scoped cache with TTL, hit/miss monitoring and
invalidation helpers. The cache degrades gracefully to a no-op when Redis is
disabled, unconfigured, or unreachable so API correctness never depends on it.

Configuration (environment variables):
    REDIS_URL         e.g. ``redis://localhost:6379/0`` - cache backend
    REDIS_ENABLED     ``true``/``false`` (default ``true``)
    CACHE_TTL_SECONDS default TTL for cached responses (default ``300``)

Cache keys are always scoped by team/tenant to prevent cross-tenant reads:
    ``team:<team_id>:<prefix>[:<k=v>...]``
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
REDIS_URL = os.getenv("REDIS_URL")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"


class CacheStats:
    """In-process hit/miss/error counters for monitoring."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.errors = 0

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_error(self) -> None:
        self.errors += 1

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
        }

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        self.errors = 0


_stats = CacheStats()


def get_cache_stats() -> Dict[str, Any]:
    """Return the current cache hit/miss counters."""
    return _stats.get_stats()


def reset_cache_stats() -> None:
    """Reset the cache counters (primarily for tests)."""
    _stats.reset()


class AsyncCacheService:
    """Thin async wrapper around a Redis client with monitoring + invalidation."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._enabled = REDIS_ENABLED
        self._initialized = False

    async def _get_client(self) -> Optional[Any]:
        """Lazily create and ping the Redis client.

        The ``redis`` package is imported lazily so the application (and the
        test suite) can run without the optional dependency installed.
        """
        if not self._enabled:
            return None
        if self._initialized:
            return self._client
        self._initialized = True

        if not REDIS_URL:
            logger.info("REDIS_URL not configured; response caching disabled")
            self._enabled = False
            return None

        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await client.ping()
            self._client = client
            logger.info("Response cache connected to Redis")
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("Redis unavailable (%s); response caching disabled", exc)
            self._enabled = False
            self._client = None
        return self._client

    async def is_available(self) -> bool:
        """Return whether the Redis backend is currently reachable."""
        return (await self._get_client()) is not None

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for ``key`` or ``None`` on a miss/error."""
        client = await self._get_client()
        if client is None:
            _stats.record_miss()
            return None
        try:
            value = await client.get(key)
            if value is not None:
                _stats.record_hit()
                return json.loads(value)
            _stats.record_miss()
            return None
        except Exception:
            _stats.record_error()
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store ``value`` under ``key`` with a TTL (seconds)."""
        client = await self._get_client()
        if client is None:
            return False
        try:
            ttl = ttl or DEFAULT_CACHE_TTL_SECONDS
            payload = json.dumps(value, default=str)
            await client.set(key, payload, ex=ttl)
            return True
        except Exception:
            _stats.record_error()
            return False

    async def delete(self, key: str) -> bool:
        """Delete a single key."""
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception:
            _stats.record_error()
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete every key matching ``pattern`` using a non-blocking scan."""
        client = await self._get_client()
        if client is None:
            return 0
        deleted = 0
        try:
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                deleted += 1
            return deleted
        except Exception:
            _stats.record_error()
            return deleted

    async def invalidate_team_cache(self, team_id: Optional[Any]) -> int:
        """Invalidate all cached responses for a team/tenant."""
        scope = f"team:{team_id}" if team_id else "team:global"
        return await self.delete_pattern(f"{scope}:*")

    async def invalidate_all(self) -> int:
        """Invalidate every cached response (use sparingly)."""
        return await self.delete_pattern("team:*")


cache_service = AsyncCacheService()


def build_cache_key(prefix: str, team_id: Optional[Any], **params: Any) -> str:
    """Build a tenant-scoped cache key.

    Params are sorted so equivalent calls always produce the same key.
    """
    scope = f"team:{team_id}" if team_id else "team:global"
    param_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{scope}:{prefix}:{param_str}" if param_str else f"{scope}:{prefix}"
