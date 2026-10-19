"""Coverage for app/routers/rate_limits.py (MID-676).

Exercises the admin rate-limit management API end-to-end through the ASGI
client. Auth is overridden to an admin; the underlying in-memory
``rate_limit_config`` / ``RateLimitMetrics`` stores are the real ones.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from api.main import app as fastapi_app
from app.routers.auth import require_admin
from app.schemas.compliance import TokenData

PREFIX = "/api/admin/rate-limits"


def _mock_admin():
    return TokenData(sub="admin@example.com", user_id="admin-id", role="admin")


@pytest.fixture
def admin_auth():
    fastapi_app.dependency_overrides[require_admin] = _mock_admin
    yield
    fastapi_app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_requires_admin(async_client: AsyncClient):
    fastapi_app.dependency_overrides.pop(require_admin, None)
    response = await async_client.get(f"{PREFIX}/tiers")
    assert response.status_code in (401, 403), response.text


@pytest.mark.asyncio
async def test_list_and_update_tiers(async_client: AsyncClient, admin_auth):
    listed = await async_client.get(f"{PREFIX}/tiers")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert "defaults" in body and "tiers" in body
    tier_name = next(iter(body["tiers"]))

    ok = await async_client.put(
        f"{PREFIX}/tiers/{tier_name}", json={"limit": "42/minute"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == tier_name

    bad = await async_client.put(
        f"{PREFIX}/tiers/{tier_name}", json={"limit": "not-a-limit"}
    )
    assert bad.status_code == 400, bad.text


@pytest.mark.asyncio
async def test_reset_tiers(async_client: AsyncClient, admin_auth):
    response = await async_client.post(f"{PREFIX}/tiers/reset")
    assert response.status_code == 200, response.text
    assert "tiers" in response.json()


@pytest.mark.asyncio
async def test_rule_lifecycle(async_client: AsyncClient, admin_auth):
    tiers = (await async_client.get(f"{PREFIX}/tiers")).json()["tiers"]
    tier_name = next(iter(tiers))

    unknown_tier = await async_client.post(
        f"{PREFIX}/rules",
        json={"path_prefix": "/api/x", "tier": "does-not-exist"},
    )
    assert unknown_tier.status_code == 400, unknown_tier.text

    bad_scope = await async_client.post(
        f"{PREFIX}/rules",
        json={"path_prefix": "/api/x", "tier": tier_name, "applies_to": "weird"},
    )
    assert bad_scope.status_code == 400, bad_scope.text

    created = await async_client.post(
        f"{PREFIX}/rules",
        json={
            "id": "testrule01",
            "path_prefix": "/api/x",
            "methods": ["GET"],
            "tier": tier_name,
            "applies_to": "authenticated",
            "description": "test",
        },
    )
    assert created.status_code == 200, created.text

    listed = await async_client.get(f"{PREFIX}/rules")
    assert listed.status_code == 200
    assert any(
        "testrule01" in (r.get("id"), r.get("rule_id"))
        for r in listed.json()["rules"]
    )

    deleted = await async_client.delete(f"{PREFIX}/rules/testrule01")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] == "testrule01"

    missing = await async_client.delete(f"{PREFIX}/rules/testrule01")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_resolve_limit(async_client: AsyncClient, admin_auth):
    response = await async_client.post(
        f"{PREFIX}/resolve",
        json={"path": "/api/analytics/overview", "method": "GET", "authenticated": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["path"] == "/api/analytics/overview"
    assert "limit" in body and "source" in body


@pytest.mark.asyncio
async def test_stats(async_client: AsyncClient, admin_auth):
    response = await async_client.get(f"{PREFIX}/stats")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "limits" in body and "blocked" in body


@pytest.mark.asyncio
async def test_blocked_lifecycle(async_client: AsyncClient, admin_auth):
    assert (await async_client.get(f"{PREFIX}/blocked")).status_code == 200

    blocked = await async_client.post(
        f"{PREFIX}/blocked", json={"ip": "203.0.113.7", "seconds": 60}
    )
    assert blocked.status_code == 200, blocked.text

    unblocked = await async_client.delete(f"{PREFIX}/blocked/203.0.113.7")
    assert unblocked.status_code == 200, unblocked.text

    missing = await async_client.delete(f"{PREFIX}/blocked/203.0.113.7")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_reset_metrics(async_client: AsyncClient, admin_auth):
    response = await async_client.post(f"{PREFIX}/reset-metrics")
    assert response.status_code == 200, response.text
    assert response.json() == {"reset": True}
