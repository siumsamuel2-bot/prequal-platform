"""Tests for production monitoring endpoints and Prometheus instrumentation.

Covers MID-580: health probes, the readiness DB connectivity check,
and the /metrics endpoint consumed by the Prometheus scrape config.
"""

import pytest
from prometheus_client import REGISTRY

from api.main import app as fastapi_app  # noqa: F401
from app.metrics import setup_metrics

# httpx ASGITransport does not execute lifespan events, so register the
# metrics middleware and /metrics route explicitly for the test session.
setup_metrics(fastapi_app)


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


async def test_detailed_health_reports_uptime_and_db(async_client):
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
