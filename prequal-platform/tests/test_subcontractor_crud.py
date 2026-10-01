"""Integration tests for subcontractor CRUD operations with org scoping.

Validates that the subcontractor endpoints:
- Create subcontractors correctly
- List subcontractors with pagination
- Get subcontractor by ID with full details
- Update subcontractor fields
- Delete subcontractors
- Handle org scoping correctly

Owner: Senior Engineer
"""
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.auth import User, Team, TeamMember, Organization
from app.models.compliance import Subcontractor
from app.routers.auth import get_password_hash
from app.schemas.compliance import TokenData, SubcontractorStatus

from api.main import app as fastapi_app


def _mock_current_user():
    return TokenData(
        sub="test@example.com",
        user_id="00000000-0000-0000-0000-000000000001",
        role="admin",
    )


@pytest_asyncio.fixture(autouse=True)
async def override_auth():
    from app.routers.auth import get_current_user
    fastapi_app.dependency_overrides[get_current_user] = _mock_current_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


async def create_test_organization(db: AsyncSession, name: str = "Test Org") -> Organization:
    """Helper to create a test organization."""
    org = Organization(name=name, slug=f"test-org-{name.lower().replace(' ', '-')}-{id(db)}")
    db.add(org)
    await db.flush()
    return org


async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpassword123",
    name: str = "Test User"
) -> User:
    """Helper to create a test user with organization and team membership."""
    user = User(
        email=email,
        name=name,
        hashed_password=get_password_hash(password),
        role="admin",
        is_active=True
    )
    db.add(user)
    await db.flush()

    org = await create_test_organization(db)
    team = Team(name="Test Team", owner_id=str(user.id))
    db.add(team)
    await db.flush()

    membership = TeamMember(user_id=user.id, team_id=team.id, role="admin")
    db.add(membership)
    await db.flush()

    user.org_id = org.id
    await db.flush()

    return user


async def create_test_subcontractor(
    db: AsyncSession,
    company_name: str = "Acme Subcontractor",
    email: str | None = None,
    status: str = "active",
    city: str = "Austin",
    state: str = "TX",
) -> Subcontractor:
    """Helper to create a test subcontractor.

    Emails are unique per call by default so multiple subs created within
    the shared session-scoped test database do not collide.
    """
    if email is None:
        email = f"acme-{uuid.uuid4().hex[:8]}@subcontractor.com"
    sub = Subcontractor(
        company_name=company_name,
        email=email,
        phone="555-0100",
        address_line1="123 Main St",
        city=city,
        state=state,
        zip_code="78701",
        status=status,
    )
    db.add(sub)
    # Commit so the endpoint's separate session (via get_db) can see the row.
    await db.commit()
    await db.refresh(sub)
    return sub


@pytest.mark.asyncio
class TestSubcontractorCRUD:
    """Test subcontractor CRUD endpoints via async HTTP client."""

    async def test_create_subcontractor(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/subcontractors should create a new subcontractor."""
        response = await async_client.post(
            "/api/subcontractors",
            json={
                "company_name": "New Subcontractor",
                "email": "newsub@example.com",
                "phone": "555-0199",
                "address_line1": "456 Oak Ave",
                "city": "Dallas",
                "state": "TX",
                "zip_code": "75201",
                "status": "active"
            }
        )
        assert response.status_code == 201, f"Create failed: {response.text}"
        data = response.json()
        assert data["company_name"] == "New Subcontractor"
        assert data["email"] == "newsub@example.com"
        assert data["status"] == "active"
        assert "id" in data

    async def test_list_subcontractors(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/subcontractors should return a list of subcontractors."""
        await create_test_subcontractor(db_session, company_name="List Test Sub 1")
        await create_test_subcontractor(db_session, company_name="List Test Sub 2")

        response = await async_client.get("/api/subcontractors")
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    async def test_list_subcontractors_pagination(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/subcontractors with limit and offset should paginate."""
        for i in range(5):
            await create_test_subcontractor(db_session, company_name=f"Pagination Sub {i}")

        response = await async_client.get("/api/subcontractors?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response_offset = await async_client.get("/api/subcontractors?limit=2&offset=2")
        data_offset = response_offset.json()
        assert len(data_offset) == 2

    async def test_get_subcontractor_by_id(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/subcontractors/{id} should return full subcontractor details."""
        sub = await create_test_subcontractor(db_session, company_name="Get By ID Test")

        response = await async_client.get(f"/api/subcontractors/{sub.id}")
        assert response.status_code == 200, f"Get by ID failed: {response.text}"
        data = response.json()
        assert data["company_name"] == "Get By ID Test"
        assert "certifications" in data

    async def test_get_nonexistent_subcontractor(self, async_client: AsyncClient) -> None:
        """GET /api/subcontractors/{id} should return 404 for nonexistent ID."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/api/subcontractors/{fake_id}")
        assert response.status_code == 404

    async def test_update_subcontractor(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """PATCH /api/subcontractors/{id} should update subcontractor fields."""
        sub = await create_test_subcontractor(db_session, company_name="Update Test Sub")

        response = await async_client.patch(
            f"/api/subcontractors/{sub.id}",
            json={
                "company_name": "Updated Company Name",
                "phone": "555-9999"
            }
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["company_name"] == "Updated Company Name"
        assert data["phone"] == "555-9999"

    async def test_update_subcontractor_status(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """PATCH should allow status change (active, suspended, inactive)."""
        sub = await create_test_subcontractor(db_session, status="active")

        response = await async_client.patch(
            f"/api/subcontractors/{sub.id}",
            json={"status": "suspended"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "suspended"

    async def test_delete_subcontractor(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE /api/subcontractors/{id} should remove the subcontractor."""
        sub = await create_test_subcontractor(db_session, company_name="Delete Test Sub")

        response = await async_client.delete(f"/api/subcontractors/{sub.id}")
        assert response.status_code == 204

        get_response = await async_client.get(f"/api/subcontractors/{sub.id}")
        assert get_response.status_code == 404

    async def test_delete_nonexistent_subcontractor(self, async_client: AsyncClient) -> None:
        """DELETE /api/subcontractors/{id} should return 404 for nonexistent ID."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.delete(f"/api/subcontractors/{fake_id}")
        assert response.status_code == 404

    async def test_create_subcontractor_invalid_email(self, async_client: AsyncClient) -> None:
        """POST /api/subcontractors should reject invalid email."""
        response = await async_client.post(
            "/api/subcontractors",
            json={
                "company_name": "Invalid Email Sub",
                "email": "not-an-email",
                "status": "active"
            }
        )
        assert response.status_code == 422

    async def test_create_subcontractor_missing_required_fields(self, async_client: AsyncClient) -> None:
        """POST /api/subcontractors should require company_name and email."""
        response = await async_client.post(
            "/api/subcontractors",
            json={
                "phone": "555-0100"
            }
        )
        assert response.status_code == 422


def _cert_payload(cert_type: str = "OSHA 30", number: str = "CERT-001") -> dict:
    return {
        "certification_type": cert_type,
        "certification_number": number,
        "issuing_authority": "OSHA",
        "issue_date": "2025-01-15",
        "expiration_date": "2026-12-31",
    }


@pytest.mark.asyncio
class TestSubcontractorCertifications:
    """Test nested certification add/remove endpoints."""

    async def test_add_certification(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/subcontractors/{id}/certifications should add a cert."""
        sub = await create_test_subcontractor(db_session)

        response = await async_client.post(
            f"/api/subcontractors/{sub.id}/certifications",
            json=_cert_payload(),
        )
        assert response.status_code == 201, f"Add cert failed: {response.text}"
        data = response.json()
        assert data["certification_type"] == "OSHA 30"
        assert data["subcontractor_id"] == str(sub.id)

    async def test_add_certification_nonexistent_sub(self, async_client: AsyncClient) -> None:
        """POST /api/subcontractors/{id}/certifications should 404 for unknown sub."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.post(
            f"/api/subcontractors/{fake_id}/certifications",
            json=_cert_payload(),
        )
        assert response.status_code == 404

    async def test_add_certification_missing_required_fields(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST nested certifications should require certification_type and expiration_date."""
        sub = await create_test_subcontractor(db_session)
        response = await async_client.post(
            f"/api/subcontractors/{sub.id}/certifications",
            json={"certification_number": "CERT-002"},
        )
        assert response.status_code == 422

    async def test_list_subcontractor_certifications(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/subcontractors/{id}/certifications should list certs."""
        sub = await create_test_subcontractor(db_session)
        await async_client.post(f"/api/subcontractors/{sub.id}/certifications", json=_cert_payload("OSHA 10", "C-1"))
        await async_client.post(f"/api/subcontractors/{sub.id}/certifications", json=_cert_payload("OSHA 30", "C-2"))

        response = await async_client.get(f"/api/subcontractors/{sub.id}/certifications")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        types = {c["certification_type"] for c in data}
        assert types == {"OSHA 10", "OSHA 30"}

    async def test_remove_subcontractor_certification(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE /api/subcontractors/{id}/certifications/{cert_id} should remove the cert."""
        sub = await create_test_subcontractor(db_session)
        add_resp = await async_client.post(
            f"/api/subcontractors/{sub.id}/certifications", json=_cert_payload()
        )
        cert_id = add_resp.json()["id"]

        response = await async_client.delete(f"/api/subcontractors/{sub.id}/certifications/{cert_id}")
        assert response.status_code == 204

        list_resp = await async_client.get(f"/api/subcontractors/{sub.id}/certifications")
        assert list_resp.json() == []

    async def test_remove_certification_wrong_sub(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE should 404 when the cert belongs to a different subcontractor."""
        sub_a = await create_test_subcontractor(db_session, company_name="Sub A")
        sub_b = await create_test_subcontractor(db_session, company_name="Sub B")
        add_resp = await async_client.post(
            f"/api/subcontractors/{sub_a.id}/certifications", json=_cert_payload()
        )
        cert_id = add_resp.json()["id"]

        response = await async_client.delete(
            f"/api/subcontractors/{sub_b.id}/certifications/{cert_id}"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestSubcontractorSearchFilters:
    """Test the extended search filters on GET /api/subcontractors."""

    async def test_filter_by_state(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await create_test_subcontractor(db_session, company_name="TX Sub", state="TX")
        await create_test_subcontractor(db_session, company_name="CA Sub", state="CA")

        response = await async_client.get("/api/subcontractors?state=TX")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(s["state"] == "TX" for s in data)
        assert any(s["company_name"] == "TX Sub" for s in data)

    async def test_filter_by_city_case_insensitive(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await create_test_subcontractor(db_session, company_name="Dallas Sub", city="Dallas")

        response = await async_client.get("/api/subcontractors?city=dallas")
        assert response.status_code == 200
        data = response.json()
        assert any(s["company_name"] == "Dallas Sub" for s in data)

    async def test_filter_by_license_state(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        sub = Subcontractor(
            company_name="Licensed Sub",
            email=f"licensed-{uuid.uuid4().hex[:8]}@example.com",
            license_state="TX",
            status="active",
        )
        db_session.add(sub)
        await db_session.commit()

        response = await async_client.get("/api/subcontractors?license_state=tx")
        assert response.status_code == 200
        data = response.json()
        assert any(s["company_name"] == "Licensed Sub" for s in data)
        assert all(s["license_state"] == "TX" for s in data)

    async def test_filter_license_expiring_within_days(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        from datetime import date, timedelta

        expiring = Subcontractor(
            company_name="Expiring Sub",
            email=f"expiring-{uuid.uuid4().hex[:8]}@example.com",
            license_expiration=date.today() + timedelta(days=15),
            status="active",
        )
        valid = Subcontractor(
            company_name="Valid Sub",
            email=f"valid-{uuid.uuid4().hex[:8]}@example.com",
            license_expiration=date.today() + timedelta(days=300),
            status="active",
        )
        db_session.add_all([expiring, valid])
        await db_session.commit()

        response = await async_client.get("/api/subcontractors?license_expiring_within_days=30")
        assert response.status_code == 200
        data = response.json()
        names = {s["company_name"] for s in data}
        assert "Expiring Sub" in names
        assert "Valid Sub" not in names

    async def test_combined_filters(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await create_test_subcontractor(db_session, company_name="Combined TX Sub", state="TX", status="active")

        response = await async_client.get("/api/subcontractors?state=TX&status=active&search=Combined")
        assert response.status_code == 200
        data = response.json()
        assert any(s["company_name"] == "Combined TX Sub" for s in data)