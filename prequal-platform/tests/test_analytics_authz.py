"""Authorization tests for platform-wide analytics endpoints (MID-545/MID-650).

GET /api/analytics/pilot-engagement returns cross-organization data (totals,
recently active organization names, trends). It must be restricted to admins
(platform-wide) or scoped to the caller's own team; a non-admin whose team
cannot be resolved from live membership must fail closed with 403.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Team, TeamMember
from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user
from api.main import app as fastapi_app


def _token(user_id, role="viewer", team_id=None) -> TokenData:
    return TokenData(
        sub="user@example.com",
        user_id=str(user_id),
        role=role,
        team_id=str(team_id) if team_id else None,
    )


def _viewer_without_team() -> TokenData:
    return _token(uuid.uuid4(), "viewer")


def _manager_without_team() -> TokenData:
    return _token(uuid.uuid4(), "manager")


def _admin_user() -> TokenData:
    return TokenData(sub="admin@example.com", user_id=str(uuid.uuid4()), role="admin")


@pytest.mark.asyncio
async def test_pilot_engagement_viewer_without_team_fails_closed(async_client: AsyncClient) -> None:
    """A non-admin with no resolvable team must not see platform-wide data."""
    fastapi_app.dependency_overrides[get_current_user] = _viewer_without_team
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 403, response.text
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_pilot_engagement_manager_without_team_fails_closed(async_client: AsyncClient) -> None:
    """A manager with no team membership is denied (fail closed)."""
    fastapi_app.dependency_overrides[get_current_user] = _manager_without_team
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 403, response.text
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


@pytest.mark.asyncio
async def test_pilot_engagement_member_with_team_allowed(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A non-admin with a live team membership sees their scoped view (200)."""
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Team(id=team_id, name=f"Team-{team_id.hex[:6]}", owner_id=user_id))
    db_session.add(TeamMember(team_id=team_id, user_id=user_id, role="member"))
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(user_id, "member", team_id)
    try:
        response = await async_client.get("/api/analytics/pilot-engagement")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "total_organizations" in data
        assert "recently_active_orgs" in data
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
