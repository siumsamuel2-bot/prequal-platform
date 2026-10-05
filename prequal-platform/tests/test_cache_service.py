"""Tests for the Redis-backed compliance response cache.

Covers tenant-scoped key building, hit/miss monitoring, TTL handling and
the invalidation strategies used after compliance writes.
"""
import fnmatch
import uuid
from datetime import datetime

import pytest

from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from app.services.cache_service import (
    AsyncCacheService,
    CacheStats,
    build_cache_key,
    get_cache_stats,
    reset_cache_stats,
)


class FakeAsyncRedis:
    """Minimal async stand-in for redis.asyncio.Redis."""

    def __init__(self):
        self.store = {}
        self.expirations = {}

    async def ping(self):
        return True

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.expirations[key] = ex
        return True

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    async def scan_iter(self, match=None):
        for key in list(self.store):
            if match is None or fnmatch.fnmatch(key, match):
                yield key


def make_service():
    service = AsyncCacheService()
    service._enabled = True
    service._initialized = True
    service._client = FakeAsyncRedis()
    return service


@pytest.fixture(autouse=True)
def _reset_stats():
    reset_cache_stats()
    yield
    reset_cache_stats()


class TestBuildCacheKey:
    def test_team_scoped_key(self):
        assert build_cache_key("compliance:summary", 42) == "team:42:compliance:summary"

    def test_key_includes_params(self):
        key = build_cache_key("compliance:trends", 7, days=30)
        assert key == "team:7:compliance:trends:days=30"

    def test_params_sorted_for_stable_keys(self):
        assert build_cache_key("x", 1, b="2", a="1") == "team:1:x:a=1:b=2"

    def test_different_teams_are_isolated(self):
        assert build_cache_key("compliance:summary", 1) != build_cache_key("compliance:summary", 2)

    def test_missing_team_uses_global_scope(self):
        assert build_cache_key("compliance:summary", None) == "team:global:compliance:summary"


class TestCacheStats:
    def test_hit_rate(self):
        stats = CacheStats()
        for _ in range(3):
            stats.record_hit()
        stats.record_miss()
        result = stats.get_stats()
        assert result["hits"] == 3
        assert result["misses"] == 1
        assert result["total_requests"] == 4
        assert result["hit_rate_percent"] == 75.0

    def test_hit_rate_zero_without_requests(self):
        assert CacheStats().get_stats()["hit_rate_percent"] == 0

    def test_reset(self):
        stats = CacheStats()
        stats.record_hit()
        stats.record_error()
        stats.reset()
        assert stats.get_stats() == {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0,
            "hit_rate_percent": 0,
        }


class TestAsyncCacheService:
    async def test_get_set_roundtrip(self):
        service = make_service()
        assert await service.set("k", {"a": 1})
        assert await service.get("k") == {"a": 1}

    async def test_default_ttl_applied(self):
        service = make_service()
        await service.set("k", "v")
        assert service._client.expirations["k"] is not None

    async def test_explicit_ttl_applied(self):
        service = make_service()
        await service.set("k", "v", ttl=17)
        assert service._client.expirations["k"] == 17

    async def test_miss_is_recorded(self):
        service = make_service()
        assert await service.get("absent") is None
        assert get_cache_stats()["misses"] == 1

    async def test_hit_is_recorded(self):
        service = make_service()
        await service.set("k", [1, 2, 3])
        assert await service.get("k") == [1, 2, 3]
        assert get_cache_stats()["hits"] == 1

    async def test_datetimes_are_serialized(self):
        service = make_service()
        await service.set("k", {"ts": datetime(2026, 1, 1, 12, 0, 0)})
        assert await service.get("k") == {"ts": "2026-01-01 12:00:00"}

    async def test_disabled_cache_is_noop(self):
        service = AsyncCacheService()
        service._enabled = False
        service._initialized = True
        assert await service.get("k") is None
        assert await service.set("k", "v") is False
        assert get_cache_stats()["misses"] == 1

    async def test_invalidate_team_cache_is_scoped(self):
        service = make_service()
        await service.set("team:1:compliance:summary", "a")
        await service.set("team:1:compliance:trends:days=30", "b")
        await service.set("team:2:compliance:summary", "c")
        removed = await service.invalidate_team_cache(1)
        assert removed == 2
        assert await service.get("team:1:compliance:summary") is None
        assert await service.get("team:2:compliance:summary") == "c"

    async def test_invalidate_all(self):
        service = make_service()
        await service.set("team:1:compliance:summary", "a")
        await service.set("team:2:compliance:summary", "b")
        assert await service.invalidate_all() == 2

    async def test_delete_pattern_returns_count(self):
        service = make_service()
        await service.set("team:9:certification:1:x", "a")
        await service.set("team:9:certification:2:x", "b")
        assert await service.delete_pattern("team:9:certification:*") == 2


class TestCacheStatsEndpoint:
    async def test_cache_stats_endpoint_requires_auth(self, async_client):
        resp = await async_client.get("/api/cache/stats")
        assert resp.status_code == 401

    async def test_cache_stats_endpoint_returns_monitoring_shape(
        self, async_client, db_engine
    ):
        from api.main import app

        app.dependency_overrides[get_current_user] = lambda: TokenData(
            user_id=str(uuid.uuid4()),
            team_id=str(uuid.uuid4()),
            role="admin",
        )
        try:
            resp = await async_client.get("/api/cache/stats")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        body = resp.json()
        assert set(body) >= {
            "hits",
            "misses",
            "errors",
            "total_requests",
            "hit_rate_percent",
            "cache_available",
        }
