"""Security tests for pipeline webhook authentication and authorization.

Covers CRITICAL-1: the pipeline trigger and sync-inspection endpoints in
``app/routers/webhooks.py`` previously accepted anonymous requests. These
tests assert that:

- every pipeline endpoint rejects unauthenticated callers (401),
- trigger endpoints reject authenticated non-manager/non-admin roles (403),
- managers/admins can still reach the trigger endpoints, and
- authenticated viewers can read sync logs and data-quality results.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from api.main import app as fastapi_app


TRIGGER_ENDPOINTS = [
    ("post", "/api/pipeline/osha/sync"),
    ("post", "/api/pipeline/state-creds/CA/sync"),
    ("post", "/api/pipeline/data-quality/run"),
    ("post", "/api/pipeline/analytics/refresh"),
]

READ_ENDPOINTS = [
    ("get", "/api/pipeline/sync-runs"),
    ("get", "/api/pipeline/data-quality/results"),
]

ALL_ENDPOINTS = TRIGGER_ENDPOINTS + READ_ENDPOINTS


def _token(role: str) -> TokenData:
    return TokenData(sub=f"{role}@example.com", user_id="test-user-id", role=role)


def _override_current_user(role: str) -> None:
    fastapi_app.dependency_overrides[get_current_user] = lambda: _token(role)


@pytest.fixture(autouse=True)
def clear_auth_override():
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def _fake_sync_run() -> MagicMock:
    run = MagicMock()
    run.id = "00000000-0000-0000-0000-000000000001"
    run.status = "completed"
    run.records_extracted = 1
    run.records_inserted = 1
    run.records_updated = 0
    run.records_failed = 0
    run.records_matched = 1
    return run


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ALL_ENDPOINTS)
async def test_pipeline_endpoints_require_authentication(
    async_client: AsyncClient, method: str, path: str
) -> None:
    """Anonymous requests must be rejected with 401."""
    response = await getattr(async_client, method)(path)
    assert response.status_code == 401, f"{path} -> {response.status_code}: {response.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", TRIGGER_ENDPOINTS)
@pytest.mark.parametrize("role", ["viewer", "owner", "auditor"])
async def test_trigger_endpoints_reject_non_manager_roles(
    async_client: AsyncClient, method: str, path: str, role: str
) -> None:
    """Authenticated users without manager/admin role must get 403."""
    _override_current_user(role)
    response = await getattr(async_client, method)(path)
    assert response.status_code == 403, f"{path} as {role} -> {response.status_code}: {response.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["manager", "admin"])
async def test_manager_and_admin_can_trigger_osha_sync(
    async_client: AsyncClient, role: str
) -> None:
    _override_current_user(role)
    with patch(
        "app.routers.webhooks.run_osha_sync",
        new=AsyncMock(return_value=_fake_sync_run()),
    ):
        response = await async_client.post("/api/pipeline/osha/sync")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_admin_can_trigger_state_credential_sync(async_client: AsyncClient) -> None:
    _override_current_user("admin")
    with patch(
        "app.routers.webhooks.run_state_credential_sync",
        new=AsyncMock(return_value=_fake_sync_run()),
    ):
        response = await async_client.post("/api/pipeline/state-creds/CA/sync")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_manager_can_trigger_data_quality_check(async_client: AsyncClient) -> None:
    _override_current_user("manager")
    with patch(
        "app.routers.webhooks.validate_pipeline_health",
        new=AsyncMock(return_value=[{"check": "ok"}]),
    ):
        response = await async_client.post("/api/pipeline/data-quality/run")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_admin_can_refresh_analytics(async_client: AsyncClient) -> None:
    _override_current_user("admin")
    with patch(
        "app.routers.webhooks.refresh_analytics_views",
        new=AsyncMock(return_value=None),
    ):
        response = await async_client.post("/api/pipeline/analytics/refresh")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", READ_ENDPOINTS)
async def test_authenticated_viewer_can_read_pipeline_status(
    async_client: AsyncClient, method: str, path: str
) -> None:
    _override_current_user("viewer")
    response = await getattr(async_client, method)(path)
    assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text}"
