"""Integration tests for the auth router (login/register/token refresh/logout).

Validates that the auth endpoints:
- Register new users correctly
- Login with valid credentials
- Reject invalid credentials
- Token refresh works correctly
- /me endpoint returns user data

Owner: Senior Engineer
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Team, TeamMember, Organization
from app.routers.auth import get_password_hash


async def create_test_organization(db: AsyncSession, name: str = "Test Org") -> Organization:
    """Helper to create a test organization with a unique slug."""
    slug = f"test-org-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
    org = Organization(name=name, slug=slug)
    db.add(org)
    await db.flush()
    return org


async def create_test_team(db: AsyncSession, name: str = "Test Team", owner_id=None) -> Team:
    """Helper to create a test team."""
    if owner_id is None:
        owner_id = uuid.uuid4()
    elif isinstance(owner_id, str):
        owner_id = uuid.UUID(owner_id)
    team = Team(name=name, owner_id=owner_id)
    db.add(team)
    await db.flush()
    return team


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
    team = await create_test_team(db, owner_id=user.id)

    membership = TeamMember(user_id=user.id, team_id=team.id, role="admin")
    db.add(membership)
    await db.flush()

    user.org_id = org.id
    # Commit so the API (which uses its own session) can see these rows.
    await db.commit()
    await db.refresh(user)

    return user


@pytest.mark.asyncio
class TestAuthIntegration:
    """Test auth router endpoints via async HTTP client."""

    async def test_register_new_user(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/register should create a new user."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "Secure-Pass123",
                "name": "New User"
            }
        )
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        user_response = await async_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        assert user_response.status_code == 200
        me_data = user_response.json()
        assert me_data["email"] == "newuser@example.com"
        assert me_data["name"] == "New User"

    async def test_register_duplicate_email(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/register should reject duplicate emails."""
        await create_test_user(db_session, email="duplicate@example.com")

        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "Another-Pass1",
                "name": "Duplicate User"
            }
        )
        assert response.status_code == 400

    async def test_login_valid_credentials(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/login should return access token for valid credentials."""
        test_email = "logintest@example.com"
        test_password = "loginpassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": test_email,
                "password": test_password
            }
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/login should reject invalid password."""
        test_email = "wrongpw@example.com"
        await create_test_user(db_session, email=test_email, password="correctpassword")

        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": test_email,
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, async_client: AsyncClient) -> None:
        """POST /api/auth/login should return 401 for nonexistent user."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent@example.com",
                "password": "anypassword"
            }
        )
        assert response.status_code == 401

    async def test_token_oauth2_endpoint(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/token should work with OAuth2 form data."""
        test_email = "oauthtest@example.com"
        test_password = "oauthpassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        response = await async_client.post(
            "/api/auth/token",
            data={
                "username": test_email,
                "password": test_password
            }
        )
        assert response.status_code == 200, f"OAuth2 token failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/refresh should return new access token."""
        test_email = "refreshtest@example.com"
        test_password = "refreshpassword123"
        user = await create_test_user(db_session, email=test_email, password=test_password)

        login_response = await async_client.post(
            "/api/auth/login",
            json={
                "username": test_email,
                "password": test_password
            }
        )
        # Use the refresh token actually issued and stored by /login.
        refresh_token = login_response.json()["refresh_token"]

        response = await async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200, f"Refresh failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token_rejects_query_parameter(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Refresh tokens must not be accepted via query string (logged by proxies)."""
        test_email = "refreshquery@example.com"
        test_password = "refreshpassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        login_response = await async_client.post(
            "/api/auth/login",
            json={"username": test_email, "password": test_password},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await async_client.post(
            f"/api/auth/refresh?refresh_token={refresh_token}"
        )
        assert response.status_code == 401, (
            "Query-parameter refresh tokens must be rejected"
        )

    async def test_refresh_token_accepts_authorization_header(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Refresh tokens may be supplied via Authorization: Bearer header."""
        test_email = "refreshheader@example.com"
        test_password = "refreshpassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        login_response = await async_client.post(
            "/api/auth/login",
            json={"username": test_email, "password": test_password},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await async_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 200, f"Refresh failed: {response.text}"
        assert "access_token" in response.json()

    async def test_refresh_token_requires_credentials(
        self, async_client: AsyncClient
    ) -> None:
        """POST /api/auth/refresh without a token must return 401."""
        response = await async_client.post("/api/auth/refresh")
        assert response.status_code == 401, response.text

    async def test_me_endpoint(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/auth/me should return current user data."""
        test_email = "metest@example.com"
        test_password = "mepassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        login_response = await async_client.post(
            "/api/auth/login",
            json={
                "username": test_email,
                "password": test_password
            }
        )
        access_token = login_response.json()["access_token"]

        response = await async_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200, f"/me failed: {response.text}"
        data = response.json()
        assert data["email"] == test_email
        assert data["name"] == "Test User"
        assert "role" in data

    async def test_me_endpoint_no_token(self, async_client: AsyncClient) -> None:
        """GET /api/auth/me should return 401 without token."""
        response = await async_client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_logout(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/auth/logout should invalidate the token (client-side)."""
        test_email = "logouttest@example.com"
        test_password = "logoutpassword123"
        await create_test_user(db_session, email=test_email, password=test_password)

        login_response = await async_client.post(
            "/api/auth/login",
            json={
                "username": test_email,
                "password": test_password
            }
        )
        access_token = login_response.json()["access_token"]

        response = await async_client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200

        me_response = await async_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_response.status_code == 401