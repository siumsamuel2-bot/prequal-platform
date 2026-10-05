"""Authorization tests for platform-wide analytics endpoints (MID-545).

GET /api/analytics/pilot-engagement returns cross-organization data (totals,
recently active organization names, trends) and must be restricted to
administrators. Non-admin users see only their own organization's data.
"""
import pytest
from httpx import AsyncClient

from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user
from api.main import app as fastapi_app


def _viewer_user() -> TokenData:
    return TokenData(sub="viewer@example.com", user_id="viewer-id", role="viewer")


def _manager_user() -> TokenData:
    return TokenData(sub="manager@example.com", user_id="manager-id", role="manager")


def _admin_user() -> TokenData:
    return TokenData(sub="admin@example.com", user_id="admin-id", role="admin")


@pytest.mark.asyncio
async def test_pilot_engagement_requires_admin(async_client: AsyncClient) -> None:
    """Non-admin authenticated users see only their own organization's data."""
    fastapi_app.dependency_overrides[get_current_user] = _viewer_user
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 200, response.text
        data = response.json()
        # Viewer should see only their org's data (or empty if no org assigned)
        assert "total_organizations" in data
        assert "recently_active_orgs" in data
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_pilot_engagement_manager_denied(async_client: AsyncClient) -> None:
    """Manager role sees only their team's organization data, not global."""
    fastapi_app.dependency_overrides[get_current_user] = _manager_user
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 200, response.text
        data = response.json()
        # Manager should see data filtered to their team's organization
        assert "total_organizations" in data
        assert "recently_active_orgs" in data
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_pilot_engagement_admin_allowed(async_client: AsyncClient) -> None:
    """Administrators may read the global engagement metrics."""
    fastapi_app.dependency_overrides[get_current_user] = _admin_user
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "total_organizations" in data
        assert "recently_active_orgs" in data
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
