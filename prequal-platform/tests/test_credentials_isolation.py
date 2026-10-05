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

from app.models.auth import Team
from app.models.compliance import Subcontractor
from app.models.credential_upload import UploadedCredential
from app.schemas.compliance import TokenData
from app.routers.auth import get_current_user
from api.main import app as fastapi_app


def _user_for_team(team_id: uuid.UUID):
    def _inner() -> TokenData:
        return TokenData(
            sub="user@example.com",
            user_id=str(uuid.uuid4()),
            role="admin",
            team_id=str(team_id),
        )

    return _inner


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
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _user_for_team(team_a)
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
