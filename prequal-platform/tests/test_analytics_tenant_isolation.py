"""Cross-tenant isolation regression tests for analytics reads (MID-650).

The pre-fix analytics router let *any* authenticated user read every
organization's data because the read endpoints never used the caller's
team/org, and ``/pilot-engagement`` fell back to unfiltered queries whenever a
user id could not be parsed (F2). These tests lock in the fix:

* non-admin reads are scoped to the caller's live team membership,
* a non-admin whose team cannot be resolved fails closed (403),
* admins retain platform-wide access,
* platform-only aggregates (no tenant dimension) are admin-only,
* team A genuinely cannot read team B's rows end-to-end.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.auth import Team, TeamMember
from app.models.compliance import Certification, Project, Subcontractor
from app.routers import analytics as analytics_router
from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from app.services.analytics_pipeline import (
    get_all_project_compliance,
    get_certification_export_rows,
)
from api.main import app as fastapi_app

TEAM_A = uuid.uuid4()
TEAM_B = uuid.uuid4()
USER_A = uuid.uuid4()


def _member(role: str = "member", user_id=USER_A, team_id=TEAM_A) -> TokenData:
    return TokenData(
        sub="a@example.com", user_id=str(user_id), role=role, team_id=str(team_id)
    )


def _admin() -> TokenData:
    return TokenData(sub="admin@example.com", user_id=str(uuid.uuid4()), role="admin")


def _flex_db(team_id):
    """AsyncMock DB whose first execute resolves the caller's team."""
    db = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = team_id
    res.scalar.return_value = 0
    res.all.return_value = []
    res.scalars.return_value.all.return_value = []
    db.execute.return_value = res
    return db


def _compiled(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))


def _norm(value) -> str:
    """Normalise a UUID for comparison (SQLite raw SQL returns 32-char hex)."""
    return str(value).replace("-", "").lower()


# ---------------------------------------------------------------------------
# Router-level scoping (asserted on generated SQL)
# ---------------------------------------------------------------------------

class TestEventReadScoping:
    @pytest.mark.asyncio
    async def test_events_scoped_to_caller_team(self):
        db = _flex_db(TEAM_A)
        await analytics_router.get_events(
            skip=0, limit=50, event_type=None, user_id=None, days=7,
            db=db, current_user=_member(),
        )
        events_stmt = db.execute.call_args_list[1].args[0]
        assert "team_members" in _compiled(events_stmt)

    @pytest.mark.asyncio
    async def test_events_unscoped_for_admin(self):
        db = _flex_db(None)
        await analytics_router.get_events(
            skip=0, limit=50, event_type=None, user_id=None, days=7,
            db=db, current_user=_admin(),
        )
        events_stmt = db.execute.call_args_list[0].args[0]
        assert "team_members" not in _compiled(events_stmt)


class TestSummaryScoping:
    @pytest.mark.asyncio
    async def test_summary_scoped_to_caller_team(self):
        db = _flex_db(TEAM_A)
        await analytics_router.get_analytics_summary(db=db, current_user=_member())
        stmts = [c.args[0] for c in db.execute.call_args_list]
        # first call is the team lookup; every data query after it must be scoped
        assert all("team_members" in _compiled(s) for s in stmts[1:])
        assert len(stmts) > 1

    @pytest.mark.asyncio
    async def test_summary_unscoped_for_admin(self):
        db = _flex_db(None)
        await analytics_router.get_analytics_summary(db=db, current_user=_admin())
        assert all(
            "team_members" not in _compiled(c.args[0])
            for c in db.execute.call_args_list
        )


class TestFeedbackScoping:
    @pytest.mark.asyncio
    async def test_feedback_scoped_to_caller_team(self):
        db = _flex_db(TEAM_A)
        await analytics_router.get_feedback(
            skip=0, limit=50, feedback_type=None, db=db, current_user=_member()
        )
        stmt = db.execute.call_args_list[1].args[0]
        assert "team_members" in _compiled(stmt)


class TestPilotEngagementScoping:
    @pytest.mark.asyncio
    async def test_member_without_team_denied(self):
        db = _flex_db(None)
        with pytest.raises(HTTPException) as exc:
            await analytics_router.get_pilot_engagement(
                days=30, db=db, current_user=_member()
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_member_queries_are_team_scoped(self):
        db = _flex_db(TEAM_A)
        await analytics_router.get_pilot_engagement(
            days=3, db=db, current_user=_member()
        )
        stmts = [c.args[0] for c in db.execute.call_args_list]
        assert all("team_members" in _compiled(s) for s in stmts[1:])

    @pytest.mark.asyncio
    async def test_admin_queries_are_unscoped(self):
        db = _flex_db(None)
        await analytics_router.get_pilot_engagement(
            days=3, db=db, current_user=_admin()
        )
        assert all(
            "team_members" not in _compiled(c.args[0])
            for c in db.execute.call_args_list
        )


# ---------------------------------------------------------------------------
# Pipeline-level scoping
# ---------------------------------------------------------------------------

class TestPipelineScoping:
    @pytest.mark.asyncio
    async def test_project_compliance_scopes_team(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(
            mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        await get_all_project_compliance(db, limit=10, offset=0, team_id=str(TEAM_A))
        sql = db.execute.call_args.args[0].text
        params = db.execute.call_args.args[1]
        assert "projects" in sql and "team_id" in sql
        assert str(params["team_id"]) == str(TEAM_A)

    @pytest.mark.asyncio
    async def test_project_compliance_admin_unscoped(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(
            mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        await get_all_project_compliance(db, limit=10, offset=0, team_id=None)
        assert "team_id" not in db.execute.call_args.args[0].text

    @pytest.mark.asyncio
    async def test_certification_export_scopes_team(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(
            mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        await get_certification_export_rows(db, team_id=str(TEAM_A))
        sql = db.execute.call_args.args[0].text
        params = db.execute.call_args.args[1]
        assert "subcontractors" in sql and "team_id" in sql
        assert str(params["team_id"]) == str(TEAM_A)


# ---------------------------------------------------------------------------
# HTTP fail-closed behaviour
# ---------------------------------------------------------------------------

PLATFORM_ONLY_ENDPOINTS = [
    "/api/analytics/compliance/summary",
    "/api/analytics/compliance/trends",
    "/api/analytics/feature-adoption",
    "/api/analytics/system-health",
    "/api/analytics/performance",
]

SCOPED_ENDPOINTS = [
    "/api/analytics/events",
    "/api/analytics/summary",
    "/api/analytics/feedback",
    "/api/analytics/projects",
    "/api/analytics/compliance/export",
    "/api/analytics/alerts/recent",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PLATFORM_ONLY_ENDPOINTS)
async def test_platform_endpoints_require_admin(async_client: AsyncClient, path: str) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _member
    try:
        response = await async_client.get(path)
        assert response.status_code == 403, (path, response.text)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SCOPED_ENDPOINTS)
async def test_scoped_endpoints_fail_closed_without_team(
    async_client: AsyncClient, path: str
) -> None:
    # Valid UUID but no live team membership → must deny, never leak.
    fastapi_app.dependency_overrides[get_current_user] = _member
    try:
        response = await async_client.get(path)
        assert response.status_code == 403, (path, response.text)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_platform_endpoints_allowed_for_admin(async_client: AsyncClient) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _admin
    try:
        for path in ("/api/analytics/compliance/summary", "/api/analytics/feature-adoption"):
            response = await async_client.get(path)
            assert response.status_code == 200, (path, response.text)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# End-to-end cross-tenant data isolation
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def tenant_data(db_session: AsyncSession):
    """Two teams with a project, a subcontractor (+cert) and events each."""
    team_a, team_b = uuid.uuid4(), uuid.uuid4()
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    db_session.add_all([
        Team(id=team_a, name=f"A-{team_a.hex[:6]}", owner_id=user_a),
        Team(id=team_b, name=f"B-{team_b.hex[:6]}", owner_id=user_b),
    ])
    await db_session.flush()

    proj_a = Project(project_name="Proj-A", project_number=f"A-{uuid.uuid4().hex[:8]}",
                     status="active", team_id=team_a)
    proj_b = Project(project_name="Proj-B", project_number=f"B-{uuid.uuid4().hex[:8]}",
                     status="active", team_id=team_b)
    sub_a = Subcontractor(company_name="Sub-A", email=f"a-{uuid.uuid4().hex[:8]}@x.com",
                          phone="555-0001", address_line1="1 A St", city="Austin",
                          state="TX", zip_code="78701", status="active", team_id=team_a)
    sub_b = Subcontractor(company_name="Sub-B", email=f"b-{uuid.uuid4().hex[:8]}@x.com",
                          phone="555-0002", address_line1="2 B St", city="Austin",
                          state="TX", zip_code="78701", status="active", team_id=team_b)
    db_session.add_all([proj_a, proj_b, sub_a, sub_b])
    await db_session.flush()

    db_session.add_all([
        Certification(subcontractor_id=sub_a.id, certification_type="OSHA-30",
                      expiration_date=date.today() + timedelta(days=180), status="valid"),
        Certification(subcontractor_id=sub_b.id, certification_type="OSHA-30",
                      expiration_date=date.today() + timedelta(days=180), status="valid"),
        TeamMember(team_id=team_a, user_id=user_a, role="member"),
        TeamMember(team_id=team_b, user_id=user_b, role="member"),
        AnalyticsEvent(event_type="page_view", event_name="event-a", user_id=user_a),
        AnalyticsEvent(event_type="page_view", event_name="event-b", user_id=user_b),
    ])
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = lambda: TokenData(
        sub="a@example.com", user_id=str(user_a), role="member", team_id=str(team_a)
    )
    try:
        yield {
            "team_a": team_a, "team_b": team_b, "user_a": user_a, "user_b": user_b,
            "proj_a": proj_a.id, "proj_b": proj_b.id,
            "sub_a": sub_a.id, "sub_b": sub_b.id,
        }
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_projects_team_a_cannot_read_team_b(async_client: AsyncClient, tenant_data) -> None:
    response = await async_client.get("/api/analytics/projects")
    assert response.status_code == 200, response.text
    ids = {_norm(row["project_id"]) for row in response.json()}
    assert _norm(tenant_data["proj_a"]) in ids
    assert _norm(tenant_data["proj_b"]) not in ids


@pytest.mark.asyncio
async def test_export_team_a_cannot_read_team_b(async_client: AsyncClient, tenant_data) -> None:
    response = await async_client.get("/api/analytics/compliance/export")
    assert response.status_code == 200, response.text
    ids = {_norm(row["subcontractor_id"]) for row in response.json()}
    assert _norm(tenant_data["sub_a"]) in ids
    assert _norm(tenant_data["sub_b"]) not in ids


@pytest.mark.asyncio
async def test_events_team_a_cannot_read_team_b(async_client: AsyncClient, tenant_data) -> None:
    response = await async_client.get("/api/analytics/events")
    assert response.status_code == 200, response.text
    names = {row["event_name"] for row in response.json()}
    assert "event-a" in names
    assert "event-b" not in names
