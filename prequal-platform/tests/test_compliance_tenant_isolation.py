"""Tenant-isolation regression tests for the compliance router (MID-651).

The compliance CRUD endpoints used to scope by the JWT ``team_id`` claim only
when present. A valid token whose user had no team membership therefore
dropped the tenant predicate and returned every tenant's rows.

These tests prove the fix:

* a team-A member (resolved from the live ``team_members`` table) cannot
  enumerate or read team B's subcontractors / certifications / violations /
  projects; and
* a valid token with no live team membership is denied (fail closed) rather
  than served unscoped data — including when the token still carries a
  (stale) ``team_id`` claim.
"""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Team, TeamMember, User
from app.models.compliance import (
    Certification,
    Project,
    Subcontractor,
    Violation,
)
from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from api.main import app as fastapi_app


def _token(user_id: uuid.UUID, role: str = "member", team_id=None) -> TokenData:
    return TokenData(
        sub="member@example.com",
        user_id=str(user_id),
        role=role,
        team_id=str(team_id) if team_id is not None else None,
    )


async def _team(db: AsyncSession, label: str) -> Team:
    team = Team(name=f"{label}-{uuid.uuid4().hex[:6]}", owner_id=uuid.uuid4())
    db.add(team)
    await db.flush()
    return team


async def _sub(db: AsyncSession, team_id: uuid.UUID, name: str) -> Subcontractor:
    sub = Subcontractor(
        company_name=name,
        email=f"{name.lower()}-{uuid.uuid4().hex[:8]}@example.com",
        phone="555-0100",
        address_line1="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78701",
        status="active",
        team_id=team_id,
    )
    db.add(sub)
    await db.flush()
    return sub


async def _cert(db: AsyncSession, sub_id: uuid.UUID, ctype: str) -> Certification:
    cert = Certification(
        subcontractor_id=sub_id,
        certification_type=ctype,
        expiration_date=date.today() + timedelta(days=90),
        status="valid",
    )
    db.add(cert)
    await db.flush()
    return cert


async def _violation(db: AsyncSession, sub_id: uuid.UUID) -> Violation:
    viol = Violation(
        subcontractor_id=sub_id,
        violation_type="OSHA",
        description="Test violation",
        issued_date=date.today(),
        status="open",
    )
    db.add(viol)
    await db.flush()
    return viol


async def _project(db: AsyncSession, team_id: uuid.UUID, name: str) -> Project:
    proj = Project(
        project_name=name,
        project_number=f"{name}-{uuid.uuid4().hex[:6]}",
        status="active",
        team_id=team_id,
    )
    db.add(proj)
    await db.flush()
    return proj


@pytest_asyncio.fixture
async def records(db_session: AsyncSession):
    """Seed two tenants and authenticate as a live member of team A."""
    team_a = await _team(db_session, "TeamA")
    team_b = await _team(db_session, "TeamB")
    await db_session.flush()

    sub_a = await _sub(db_session, team_a.id, "AlphaSub")
    sub_b = await _sub(db_session, team_b.id, "BravoSub")
    cert_a = await _cert(db_session, sub_a.id, "OSHA-10")
    cert_b = await _cert(db_session, sub_b.id, "OSHA-30")
    viol_a = await _violation(db_session, sub_a.id)
    viol_b = await _violation(db_session, sub_b.id)
    proj_a = await _project(db_session, team_a.id, "AlphaProject")
    proj_b = await _project(db_session, team_b.id, "BravoProject")

    user_a = User(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        name="User A",
        hashed_password="x",
        role="member",
        is_active=True,
    )
    db_session.add(user_a)
    await db_session.flush()
    db_session.add(TeamMember(user_id=user_a.id, team_id=team_a.id, role="member"))
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(user_a.id)
    try:
        yield {
            "team_a": team_a.id,
            "team_b": team_b.id,
            "user_a": user_a.id,
            "sub_a": sub_a.id,
            "sub_b": sub_b.id,
            "cert_a": cert_a.id,
            "cert_b": cert_b.id,
            "viol_a": viol_a.id,
            "viol_b": viol_b.id,
            "proj_a": proj_a.id,
            "proj_b": proj_b.id,
        }
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Team A member: cross-tenant reads are denied / filtered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_member_list_subcontractors_excludes_other_team(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get("/api/subcontractors")
    assert response.status_code == 200, response.text
    names = {row["company_name"] for row in response.json()}
    assert "AlphaSub" in names
    assert "BravoSub" not in names


@pytest.mark.asyncio
async def test_member_cannot_read_other_team_subcontractor(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get(f"/api/subcontractors/{records['sub_b']}")
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_member_cannot_read_other_team_certification(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get(f"/api/certifications/{records['cert_b']}")
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_member_certifications_list_is_scoped(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get("/api/certifications")
    assert response.status_code == 200, response.text
    ids = {row["id"] for row in response.json()}
    assert str(records["cert_a"]) in ids
    assert str(records["cert_b"]) not in ids


@pytest.mark.asyncio
async def test_member_cannot_read_other_team_violation(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get(f"/api/violations/{records['viol_b']}")
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_member_cannot_read_other_team_project(
    async_client: AsyncClient, records
) -> None:
    response = await async_client.get(f"/api/projects/{records['proj_b']}")
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# No live team membership: fail closed (deny, never unscoped)
# ---------------------------------------------------------------------------


def _set_no_team_override(team_id=None):
    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(
        uuid.uuid4(), team_id=team_id
    )


@pytest.mark.asyncio
async def test_no_team_list_subcontractors_denied(
    async_client: AsyncClient, records
) -> None:
    _set_no_team_override()
    try:
        response = await async_client.get("/api/subcontractors")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_no_team_detail_subcontractor_denied(
    async_client: AsyncClient, records
) -> None:
    _set_no_team_override()
    try:
        response = await async_client.get(f"/api/subcontractors/{records['sub_a']}")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code in (403, 404), response.text


@pytest.mark.asyncio
async def test_no_team_create_subcontractor_denied(
    async_client: AsyncClient, records
) -> None:
    _set_no_team_override()
    try:
        response = await async_client.post(
            "/api/subcontractors",
            json={
                "company_name": "ShouldNotExist",
                "email": f"nope-{uuid.uuid4().hex[:8]}@example.com",
                "status": "active",
            },
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_no_team_create_certification_denied(
    async_client: AsyncClient, records
) -> None:
    _set_no_team_override()
    try:
        response = await async_client.post(
            "/api/certifications",
            json={
                "subcontractor_id": str(records["sub_a"]),
                "certification_type": "OSHA-10",
                "expiration_date": str(date.today() + timedelta(days=30)),
            },
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_stale_team_claim_without_membership_denied(
    async_client: AsyncClient, records
) -> None:
    """A token with a team_id claim but no live membership is still denied."""
    _set_no_team_override(team_id=records["team_a"])
    try:
        response = await async_client.get(f"/api/subcontractors/{records['sub_a']}")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code in (403, 404), response.text


@pytest.mark.asyncio
async def test_admin_without_team_is_unscoped(async_client: AsyncClient, records) -> None:
    """Authorized global admins keep platform-wide read access (no regression)."""
    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(
        uuid.uuid4(), role="admin"
    )
    try:
        response = await async_client.get("/api/subcontractors")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200, response.text
    names = {row["company_name"] for row in response.json()}
    assert {"AlphaSub", "BravoSub"} <= names
