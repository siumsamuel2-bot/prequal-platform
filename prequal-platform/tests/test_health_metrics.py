"""Tests for production monitoring endpoints and Prometheus instrumentation.

Covers MID-580: health probes, the readiness DB connectivity check,
and the /metrics endpoint consumed by the Prometheus scrape config.
Covers MID-690: /health/detailed is admin-only and /metrics is
token-gated outside developer environments.
"""

import pytest
from prometheus_client import REGISTRY

from api.main import app as fastapi_app  # noqa: F401
from app.metrics import setup_metrics
from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user, require_admin

# httpx ASGITransport does not execute lifespan events, so register the
# metrics middleware and /metrics route explicitly for the test session.
setup_metrics(fastapi_app)


def _mock_admin():
    return TokenData(sub="admin@example.com", user_id="admin-id", role="admin")


@pytest.fixture
def admin_auth():
    """Override auth dependencies so requests run as an authenticated admin."""
    fastapi_app.dependency_overrides[get_current_user] = _mock_admin
    fastapi_app.dependency_overrides[require_admin] = _mock_admin
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    fastapi_app.dependency_overrides.pop(require_admin, None)


async def test_health_basic(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["service"] == "prequal-api"


async def test_liveness(async_client):
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "alive"


async def test_readiness_reports_ready_with_healthy_db(async_client):
    resp = await async_client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] is True
    assert body["checks"]["redis"] is True


async def test_readiness_reports_not_ready_when_db_down(async_client, monkeypatch):
    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("simulated database outage")

    monkeypatch.setattr("app.database.engine", _BrokenEngine())

    resp = await async_client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] is False


async def test_detailed_health_requires_admin(async_client):
    """MID-690: anonymous callers get 401 (payload discloses uptime/versions)."""
    resp = await async_client.get("/health/detailed")
    assert resp.status_code == 401


async def test_detailed_health_reports_uptime_and_db(async_client, admin_auth):
    resp = await async_client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("healthy", "degraded")
    assert body["services"]["database"] == "healthy"
    assert body["uptime_seconds"] >= 0


async def test_metrics_endpoint_exposes_request_metrics(async_client):
    await async_client.get("/health")

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    payload = resp.text
    assert "http_requests_total" in payload
    assert "http_request_duration_seconds_bucket" in payload


async def test_metrics_disabled_without_token_outside_dev(async_client, monkeypatch):
    """MID-690: staging/prod without METRICS_AUTH_TOKEN fails closed (403)."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("METRICS_AUTH_TOKEN", raising=False)

    resp = await async_client.get("/metrics")
    assert resp.status_code == 403


async def test_metrics_requires_bearer_token_when_configured(async_client, monkeypatch):
    """MID-690: with METRICS_AUTH_TOKEN set, wrong/missing token gets 401."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("METRICS_AUTH_TOKEN", "scrape-secret")

    resp = await async_client.get("/metrics")
    assert resp.status_code == 401

    resp = await async_client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401

    resp = await async_client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


async def test_metrics_middleware_counts_http_requests(async_client):
    await async_client.get("/health")

    value = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "endpoint": "/health", "status": "200"},
    )
    assert value is not None
    assert value >= 1


async def test_setup_metrics_is_idempotent():
    routes_before = len(fastapi_app.routes)
    setup_metrics(fastapi_app)
    assert len(fastapi_app.routes) == routes_before
