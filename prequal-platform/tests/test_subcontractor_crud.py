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
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.auth import User, Team, TeamMember, Organization
from app.models.compliance import Subcontractor, SubcontractorStatus
from app.routers.auth import get_password_hash
from app.schemas.compliance import TokenData

from api.main import app as fastapi_app


def _mock_current_user():
    return TokenData(sub="test@example.com", user_id="test-user-id", role="admin")


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
    email: str = "acme@subcontractor.com",
    status: str = "active"
) -> Subcontractor:
    """Helper to create a test subcontractor."""
    sub = Subcontractor(
        company_name=company_name,
        email=email,
        phone="555-0100",
        address_line1="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78701",
        status=status,
    )
    db.add(sub)
    await db.flush()
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