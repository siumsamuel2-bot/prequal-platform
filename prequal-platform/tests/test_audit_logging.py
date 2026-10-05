"""Tests for data access audit logging (MID-313).

Covers:
- AuditLoggingService event creation, validation, and context handling
- _emit_to_db persistence to data_access_audit_logs
- DataAccessAuditMiddleware recording of API data-access operations
- GET /api/audit-logs queryable compliance endpoint (admin only)

Owner: Senior Engineer
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app as fastapi_app
from app.database import AsyncSessionLocal
from app.models.compliance import DataAccessAuditLog
from app.services.audit_logging import (
    AuditLoggingService,
    DataAccessAuditEvent,
    _pending_persist_tasks,
    default_audit_service,
)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_event_defaults_fill_timestamp_and_context():
    AuditLoggingService.set_context(
        request_id="req-123",
        user_id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-000000000002",
    )
    try:
        event = DataAccessAuditEvent(
            operation_type="GET",
            resource_type="subcontractors",
        )
        assert event.created_at.endswith("Z")
        assert event.request_id == "req-123"
        assert event.user_id == "00000000-0000-0000-0000-000000000001"
        assert event.org_id == "00000000-0000-0000-0000-000000000002"
        assert event.validate() is True
    finally:
        AuditLoggingService.clear_context()


def test_log_rejects_invalid_operation_type():
    service = AuditLoggingService(enable_elk=False, enable_db=False)
    with pytest.raises(ValueError):
        service.log(operation_type="TELEPORT", resource_type="subcontractors")


def test_log_normalizes_operation_and_status():
    service = AuditLoggingService(enable_elk=False, enable_db=False)
    event = service.log(
        operation_type="get",
        resource_type="subcontractors",
        status="SUCCESS",
    )
    assert event.operation_type == "GET"
    assert event.status == "success"


def test_log_data_access_helper_uses_default_service():
    event = default_audit_service.log(
        operation_type="GET",
        resource_type="certifications",
    )
    assert event.operation_type == "GET"
    assert event.resource_type == "certifications"
    AuditLoggingService.clear_context()


async def test_emit_to_db_persists_audit_record(db_session: AsyncSession):
    user_id = str(uuid.uuid4())
    svc = AuditLoggingService(enable_elk=False, enable_db=True)
    event = svc.log(
        operation_type="POST",
        resource_type="subcontractors",
        resource_id="123",
        user_id=user_id,
        status="success",
    )
    # Allow the fire-and-forget persist task to run
    for _ in range(5):
        await asyncio.sleep(0)
        if not _pending_persist_tasks:
            break
    await asyncio.sleep(0.05)

    result = await db_session.execute(
        select(DataAccessAuditLog).where(
            DataAccessAuditLog.operation_type == "POST",
            DataAccessAuditLog.resource_type == "subcontractors",
        )
    )
    record = result.scalars().first()
    assert record is not None
    assert str(record.user_id) == user_id
    assert record.resource_id == "123"
    assert record.status == "success"
    assert record.retention_until is not None


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------

def _mock_admin_user():
    from app.schemas.compliance import TokenData
    return TokenData(
        sub="audit-admin@example.com",
        user_id="00000000-0000-0000-0000-000000000001",
        role="admin",
    )


def _mock_viewer_user():
    from app.schemas.compliance import TokenData
    return TokenData(
        sub="audit-viewer@example.com",
        user_id="00000000-0000-0000-0000-000000000002",
        role="viewer",
    )


@pytest_asyncio.fixture(autouse=True)
async def override_auth():
    from app.routers.auth import get_current_user
    fastapi_app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


async def _flush_audit_tasks():
    for _ in range(5):
        await asyncio.sleep(0)
        if not _pending_persist_tasks:
            break
    await asyncio.sleep(0.05)


async def _count_audit_entries(db_session: AsyncSession, **filters) -> int:
    query = select(DataAccessAuditLog)
    for col, value in filters.items():
        query = query.where(getattr(DataAccessAuditLog, col) == value)
    result = await db_session.execute(query)
    return len(result.scalars().all())


async def test_middleware_records_read_operation(async_client: AsyncClient, db_session: AsyncSession):
    response = await async_client.get("/api/subcontractors")
    assert response.status_code in (200, 401, 403)
    await _flush_audit_tasks()
    count = await _count_audit_entries(
        db_session, operation_type="GET", resource_type="subcontractors"
    )
    assert count >= 1


async def test_middleware_records_resource_id_from_path(async_client: AsyncClient, db_session: AsyncSession):
    missing_id = str(uuid.uuid4())
    await async_client.get(f"/api/subcontractors/{missing_id}")
    await _flush_audit_tasks()
    result = await db_session.execute(
        select(DataAccessAuditLog).where(
            DataAccessAuditLog.resource_id == missing_id
        )
    )
    record = result.scalars().first()
    assert record is not None
    assert record.operation_type == "GET"
    # A 404 outcome must be recorded as failure
    assert record.status == "failure"


async def test_middleware_excludes_auth_paths(async_client: AsyncClient, db_session: AsyncSession):
    before = await _count_audit_entries(db_session, resource_type="auth")
    await async_client.post("/api/auth/token", data={"username": "x", "password": "y"})
    await _flush_audit_tasks()
    after = await _count_audit_entries(db_session, resource_type="auth")
    assert after == before


async def test_middleware_excludes_health(async_client: AsyncClient, db_session: AsyncSession):
    before = await _count_audit_entries(db_session, resource_type="health")
    await async_client.get("/api/health")
    await async_client.get("/health")
    await _flush_audit_tasks()
    after = await _count_audit_entries(db_session, resource_type="health")
    assert after == before


async def test_middleware_sets_correlation_context(async_client: AsyncClient, db_session: AsyncSession):
    response = await async_client.get(
        "/api/subcontractors", headers={"X-Request-ID": "corr-audit-42"}
    )
    assert response.headers.get("X-Request-ID") == "corr-audit-42"
    await _flush_audit_tasks()
    result = await db_session.execute(
        select(DataAccessAuditLog).where(
            DataAccessAuditLog.request_id == "corr-audit-42"
        )
    )
    record = result.scalars().first()
    assert record is not None


# ---------------------------------------------------------------------------
# Query endpoint tests
# ---------------------------------------------------------------------------

async def test_query_audit_logs_admin_allowed(async_client: AsyncClient, db_session: AsyncSession):
    # Seed one entry directly
    db_session.add(DataAccessAuditLog(
        operation_type="EXPORT",
        resource_type="compliance",
        resource_id="report-1",
        status="success",
    ))
    await db_session.commit()

    response = await async_client.get("/api/audit-logs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(
        item["operation_type"] == "EXPORT" and item["resource_id"] == "report-1"
        for item in body["items"]
    )


async def test_query_audit_logs_filters(async_client: AsyncClient, db_session: AsyncSession):
    db_session.add(DataAccessAuditLog(
        operation_type="DELETE",
        resource_type="violations",
        resource_id="v-999",
        status="success",
    ))
    await db_session.commit()

    response = await async_client.get(
        "/api/audit-logs",
        params={"operation_type": "delete", "resource_type": "Violations"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(item["operation_type"] == "DELETE" for item in body["items"])


async def test_query_audit_logs_requires_admin(async_client: AsyncClient):
    from app.routers.auth import get_current_user
    fastapi_app.dependency_overrides[get_current_user] = _mock_viewer_user
    try:
        response = await async_client.get("/api/audit-logs")
        assert response.status_code == 403
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
        fastapi_app.dependency_overrides[get_current_user] = _mock_admin_user
