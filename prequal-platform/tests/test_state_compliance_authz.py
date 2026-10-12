"""Security regression tests for state-compliance write/sync endpoints (MID-689).

The state-compliance router previously exposed two state-changing endpoints
without any authentication dependency:

* ``POST /api/compliance/states/sync/{state_code}`` — triggered the external
  compliance sync pipeline anonymously, and
* ``POST /api/compliance/states/sources`` — let anonymous callers create state
  source records.

Both now require ``require_manager_or_admin`` (Broken Access Control, OWASP
A01). These tests prove:

- anonymous callers get 401,
- authenticated non-manager/non-admin roles get 403, and
- managers/admins can still reach both endpoints.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from api.main import app as fastapi_app


def _token(role: str) -> TokenData:
    return TokenData(sub=f"{role}@example.com", user_id="test-user-id", role=role)


def _override_current_user(role: str) -> None:
    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(role)


@pytest.fixture(autouse=True)
def clear_auth_override():
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/compliance/states/sync/CA"),
        ("post", "/api/compliance/states/sources"),
    ],
)
async def test_write_endpoints_require_authentication(
    async_client: AsyncClient, method: str, path: str
) -> None:
    """Anonymous requests must be rejected with 401, not 422/200."""
    response = await getattr(async_client, method)(path)
    assert response.status_code == 401, f"{path} -> {response.status_code}: {response.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["viewer", "member", "owner", "auditor"])
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/compliance/states/sync/CA"),
        ("post", "/api/compliance/states/sources"),
    ],
)
async def test_write_endpoints_reject_non_manager_roles(
    async_client: AsyncClient, method: str, path: str, role: str
) -> None:
    """Authenticated users without manager/admin role must get 403."""
    _override_current_user(role)
    response = await getattr(async_client, method)(path)
    assert response.status_code == 403, f"{path} as {role} -> {response.status_code}: {response.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["manager", "admin"])
async def test_manager_and_admin_can_trigger_state_sync(
    async_client: AsyncClient, role: str
) -> None:
    _override_current_user(role)
    with patch(
        "app.routers.state_compliance.sync_state_credentials",
        new=AsyncMock(return_value={"state_code": "CA", "records_synced": 0}),
    ):
        response = await async_client.post("/api/compliance/states/sync/CA")
    assert response.status_code == 200, response.text
    assert response.json()["state_code"] == "CA"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["manager", "admin"])
async def test_manager_and_admin_can_create_state_source(
    async_client: AsyncClient, role: str
) -> None:
    _override_current_user(role)
    code = uuid.uuid4().hex[:2].upper()
    response = await async_client.post(
        "/api/compliance/states/sources",
        params={"state_code": code, "state_name": f"Test-{code}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state_code"] == code
