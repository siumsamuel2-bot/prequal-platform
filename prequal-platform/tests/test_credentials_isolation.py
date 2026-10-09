"""Tenant-isolation tests for credential upload endpoints (MID-547).

A user in Team A must not be able to read, process, convert, or delete
credential files that belong to a subcontractor owned by Team B, even when the
UUID is known.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Team, TeamMember, User
from app.models.compliance import Subcontractor
from app.models.credential_upload import UploadedCredential
from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user
from api.main import app as fastapi_app


def _user_for_team(team_id: uuid.UUID, user_id: uuid.UUID, role: str = "member"):
    def _inner() -> TokenData:
        return TokenData(
            sub="user@example.com",
            user_id=str(user_id),
            role=role,
            # Deliberately stale/None claim: tenant scope must come from the
            # live team_members row, not the token.
            team_id=None,
        )

    return _inner


async def _create_user_with_membership(
    db: AsyncSession, team_id: uuid.UUID, role: str = "member"
) -> User:
    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        name="Team Member",
        hashed_password="x",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(TeamMember(user_id=user.id, team_id=team_id, role=role))
    await db.flush()
    return user


async def _create_sub(db: AsyncSession, team_id: uuid.UUID, name: str) -> Subcontractor:
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


async def _create_upload(db: AsyncSession, sub_id: uuid.UUID) -> UploadedCredential:
    upload = UploadedCredential(
        subcontractor_id=sub_id,
        original_filename="cert.pdf",
        stored_filename=f"cert-{uuid.uuid4().hex}.pdf",
        file_path="/tmp/cert.pdf",
        file_size=123,
        mime_type="application/pdf",
    )
    db.add(upload)
    await db.flush()
    return upload


@pytest_asyncio.fixture
async def records(db_session: AsyncSession):
    """Create two teams with a subcontractor + upload each; authenticate as Team A."""
    team_a = uuid.uuid4()
    team_b = uuid.uuid4()
    db_session.add_all([
        Team(id=team_a, name=f"TeamA-{team_a.hex[:6]}", owner_id=uuid.uuid4()),
        Team(id=team_b, name=f"TeamB-{team_b.hex[:6]}", owner_id=uuid.uuid4()),
    ])
    await db_session.flush()

    sub_a = await _create_sub(db_session, team_a, "SubA")
    sub_b = await _create_sub(db_session, team_b, "SubB")
    up_a = await _create_upload(db_session, sub_a.id)
    up_b = await _create_upload(db_session, sub_b.id)

    # MID-651: tenant scope is resolved from live team membership, so the
    # caller must have a real users/team_members row (the JWT team_id claim is
    # no longer trusted).
    user_a = await _create_user_with_membership(db_session, team_a)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _user_for_team(team_a, user_a.id)
    try:
        yield {
            "team_a": team_a,
            "team_b": team_b,
            "sub_a": sub_a.id,
            "sub_b": sub_b.id,
            "up_a": up_a.id,
            "up_b": up_b.id,
        }
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_cross_team_subcontractor_uploads_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.get(
        f"/api/subcontractors/{records['sub_b']}/credentials/uploads"
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_own_team_subcontractor_uploads_allowed(async_client: AsyncClient, records) -> None:
    response = await async_client.get(
        f"/api/subcontractors/{records['sub_a']}/credentials/uploads"
    )
    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert str(records["up_a"]) in ids


@pytest.mark.asyncio
async def test_cross_team_upload_get_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.get(f"/api/credentials/uploads/{records['up_b']}")
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_own_team_upload_get_allowed(async_client: AsyncClient, records) -> None:
    response = await async_client.get(f"/api/credentials/uploads/{records['up_a']}")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_cross_team_upload_post_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.post(
        f"/api/subcontractors/{records['sub_b']}/credentials/upload",
        files={"file": ("cert.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"certification_type": "OSHA"},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_cross_team_process_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.post(
        f"/api/credentials/uploads/{records['up_b']}/process"
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_cross_team_create_certification_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.post(
        f"/api/credentials/uploads/{records['up_b']}/create-certification"
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_cross_team_delete_denied(async_client: AsyncClient, records) -> None:
    response = await async_client.delete(f"/api/credentials/uploads/{records['up_b']}")
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# MID-651: fail-open regression — a valid token whose user has no live team
# membership must be denied instead of returning every tenant's data.
# ---------------------------------------------------------------------------


def _no_team_user() -> TokenData:
    return TokenData(
        sub="orphan@example.com",
        user_id=str(uuid.uuid4()),
        role="member",
        team_id=None,
    )


async def _get_as_no_team(async_client: AsyncClient, url: str):
    fastapi_app.dependency_overrides[get_current_user] = _no_team_user
    try:
        return await async_client.get(url)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_no_team_token_denied_for_uploads_list(
    async_client: AsyncClient, records
) -> None:
    """No live membership → deny; must not list any team's uploads."""
    response = await _get_as_no_team(
        async_client, f"/api/subcontractors/{records['sub_a']}/credentials/uploads"
    )
    assert response.status_code in (403, 404), response.text
    assert response.status_code != 200


@pytest.mark.asyncio
async def test_no_team_token_denied_for_upload_detail(
    async_client: AsyncClient, records
) -> None:
    response = await _get_as_no_team(
        async_client, f"/api/credentials/uploads/{records['up_a']}"
    )
    assert response.status_code in (403, 404), response.text


@pytest.mark.asyncio
async def test_no_team_token_denied_for_upload_post(
    async_client: AsyncClient, records
) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _no_team_user
    try:
        response = await async_client.post(
            f"/api/subcontractors/{records['sub_a']}/credentials/upload",
            files={"file": ("cert.pdf", b"%PDF-1.4 test", "application/pdf")},
            data={"certification_type": "OSHA"},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code in (403, 404), response.text


@pytest.mark.asyncio
async def test_stale_team_claim_without_membership_denied(
    async_client: AsyncClient, records
) -> None:
    """A token carrying a team_id claim but no live membership is still denied.

    Proves tenant scope is resolved from the DB, not the (possibly stale) JWT
    claim.
    """
    def _stale_user() -> TokenData:
        return TokenData(
            sub="stale@example.com",
            user_id=str(uuid.uuid4()),
            role="member",
            team_id=str(records["team_a"]),
        )

    fastapi_app.dependency_overrides[get_current_user] = _stale_user
    try:
        response = await async_client.get(
            f"/api/subcontractors/{records['sub_a']}/credentials/uploads"
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code in (403, 404), response.text
