"""Tests for API rate limiting and DDoS protection (MID-593).

Run:  pytest tests/test_rate_limiting.py -v
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import (
    DEFAULT_TIERS,
    ConfigurableRateLimitMiddleware,
    DDoSProtectionMiddleware,
    RateLimitConfigStore,
    RateLimitMetrics,
    RateLimitRule,
    RateLimitTiers,
    _rate_storage,
    get_tier_limit,
    rate_limit_config,
    rate_limit_key,
    reset_rate_limit_config,
    setup_rate_limiting,
)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Reset dynamic config and counters between tests."""
    reset_rate_limit_config()
    RateLimitMetrics.clear()
    for blocked in rate_limit_config.list_blocked():
        rate_limit_config.unblock_ip(blocked["ip"])
    try:
        _rate_storage._strategy.storage.reset()
    except Exception:
        pass
    yield
    reset_rate_limit_config()
    RateLimitMetrics.clear()


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    @app.post("/echo")
    async def echo():
        return {"ok": True}

    setup_rate_limiting(app)
    return app


def _add_limit(path: str, limit: str, methods=None, applies_to="unauthenticated"):
    rate_limit_config.set_tier("test_tier", limit)
    rate_limit_config.upsert_rule(
        RateLimitRule(
            rule_id="test-rule",
            path_prefix=path,
            methods=methods or ["GET"],
            tier="test_tier",
            applies_to=applies_to,
        )
    )


class TestTierDefaults:
    def test_static_tiers_are_strings(self):
        assert RateLimitTiers.UNAUTHENTICATED_LOGIN == "10/minute"
        assert RateLimitTiers.AUTHENTICATED_READ == "200/minute"

    def test_dynamic_tier_reads_store(self):
        rate_limit_config.set_tier("unauthenticated_login", "7/minute")
        assert get_tier_limit("unauthenticated_login") == "7/minute"
        assert get_tier_limit("missing") == DEFAULT_TIERS["unauthenticated_default"]

    def test_get_tier_limit_falls_back(self):
        assert get_tier_limit("authenticated_write") == "50/minute"


class TestRateLimitKey:
    def test_per_user_key_from_jwt(self):
        from unittest.mock import MagicMock
        import jwt

        request = MagicMock()
        token = jwt.encode(
            {"user_id": "user-123"}, "secret", algorithm="HS256"
        )
        request.headers.get.return_value = f"Bearer {token}"
        assert rate_limit_key(request) == "user:user-123"

    def test_per_ip_key_without_jwt(self):
        from unittest.mock import MagicMock
        from slowapi.util import get_remote_address

        request = MagicMock()
        request.headers.get.return_value = ""
        request.client = None
        assert rate_limit_key(request) == f"ip:{get_remote_address(request)}"


class TestConfigStore:
    def test_invalid_limit_rejected(self):
        with pytest.raises(ValueError):
            rate_limit_config.set_tier("bad", "lots/minute")

    def test_rule_precedence_over_default(self):
        _add_limit("/api/analytics", "5/minute", methods=["POST"], applies_to="any")
        limit, source = rate_limit_config.resolve_limit(
            "/api/analytics/report", "POST", authenticated=True
        )
        assert limit == "5/minute"
        assert source == "rule:test-rule"

    def test_default_resolution_by_method_and_auth(self):
        read_limit, read_source = rate_limit_config.resolve_limit(
            "/api/other", "GET", authenticated=True
        )
        assert read_limit == "200/minute"
        assert read_source == "authenticated_read"

        write_limit, write_source = rate_limit_config.resolve_limit(
            "/api/other", "POST", authenticated=True
        )
        assert write_limit == "50/minute"
        assert write_source == "authenticated_write"

    def test_delete_rule(self):
        _add_limit("/api/x", "5/minute")
        assert rate_limit_config.delete_rule("test-rule") is True
        assert rate_limit_config.delete_rule("test-rule") is False

    def test_ip_ban_lifecycle(self):
        rate_limit_config.block_ip("10.0.0.9", 60)
        assert rate_limit_config.is_blocked("10.0.0.9") is True
        assert rate_limit_config.unblock_ip("10.0.0.9") is True
        assert rate_limit_config.is_blocked("10.0.0.9") is False

    def test_config_store_isolated_instance(self):
        store = RateLimitConfigStore()
        store.set_tier("unauthenticated_login", "3/minute")
        assert store.get_tier("unauthenticated_login") == "3/minute"
        assert rate_limit_config.get_tier("unauthenticated_login") == "10/minute"


class TestRateLimitEnforcement:
    def test_requests_allowed_then_blocked_with_headers(self):
        _add_limit("/limited", "2/minute")
        client = TestClient(_build_app())

        first = client.get("/limited")
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "2"
        assert "X-RateLimit-Remaining" in first.headers
        assert "X-RateLimit-Reset" in first.headers

        client.get("/limited")
        third = client.get("/limited")
        assert third.status_code == 429
        assert "Retry-After" in third.headers
        assert third.headers["X-RateLimit-Remaining"] == "0"

    def test_exempt_paths_not_limited(self):
        _add_limit("/", "1/minute")
        client = TestClient(_build_app())
        for _ in range(5):
            assert client.get("/health").status_code in (200, 404)


class TestDDoSProtection:
    def test_request_size_limit(self, monkeypatch):
        monkeypatch.setenv("DDOS_MAX_BODY_BYTES", "10")
        client = TestClient(_build_app())
        response = client.post("/echo", content=b"x" * 100)
        assert response.status_code == 413

    def test_suspicious_path_traversal_rejected(self):
        client = TestClient(_build_app())
        response = client.get("/limited", params={"q": "../../etc/passwd"})
        assert response.status_code == 400

    def test_suspicious_sql_injection_rejected(self):
        client = TestClient(_build_app())
        response = client.get("/limited", params={"q": "1 union select password from users"})
        assert response.status_code == 400

    def test_query_length_limit(self, monkeypatch):
        monkeypatch.setenv("DDOS_MAX_QUERY_LENGTH", "16")
        client = TestClient(_build_app())
        response = client.get("/limited", params={"q": "a" * 100})
        assert response.status_code == 400

    def test_too_many_headers_rejected(self, monkeypatch):
        monkeypatch.setenv("DDOS_MAX_HEADER_COUNT", "3")
        client = TestClient(_build_app())
        response = client.get(
            "/limited", headers={"X-A": "1", "X-B": "2", "X-C": "3", "X-D": "4"}
        )
        assert response.status_code == 400

    def test_blocked_ip_is_rejected(self):
        rate_limit_config.block_ip("testclient", 60)
        client = TestClient(_build_app())
        response = client.get("/limited")
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_auto_ban_after_repeated_violations(self, monkeypatch):
        monkeypatch.setenv("DDOS_VIOLATION_THRESHOLD", "2")
        monkeypatch.setenv("DDOS_BAN_SECONDS", "60")
        client = TestClient(_build_app())
        client.get("/limited", params={"q": "../../etc/passwd"})
        client.get("/limited", params={"q": "../../etc/passwd"})
        assert rate_limit_config.is_blocked("testclient") is True


class TestAdminRateLimitAPI:
    @pytest.mark.asyncio
    async def test_admin_endpoints_require_auth(self, async_client):
        response = await async_client.get("/api/admin/rate-limits/tiers")
        assert response.status_code == 401
