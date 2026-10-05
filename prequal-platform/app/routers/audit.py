"""
Audit log query API.

Exposes the data_access_audit_logs table for compliance review:
GET /api/audit-logs (admin only) with filters for user, operation,
resource, org, status, and time range.

Owner: Senior Engineer
Ticket: MID-313
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance import DataAccessAuditLog
from app.routers.auth import get_current_user, TokenData
from app.services.security_service import log_data_access

router = APIRouter(prefix="/api", tags=["audit"])


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    operation_type: str
    resource_type: str
    resource_id: Optional[str] = None
    org_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    record_count: Optional[int] = None
    change_summary: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    compliance_tag: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditLogQueryResponse(BaseModel):
    items: List[AuditLogEntry]
    total: int
    skip: int
    limit: int


@router.get("/audit-logs", response_model=AuditLogQueryResponse)
async def query_audit_logs(
    request: Request = None,
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by acting user"),
    operation_type: Optional[str] = Query(None, description="GET/POST/PUT/PATCH/DELETE/EXPORT/..."),
    resource_type: Optional[str] = Query(None, description="Resource type, e.g. subcontractors"),
    resource_id: Optional[str] = Query(None, description="Specific resource identifier"),
    org_id: Optional[uuid.UUID] = Query(None, description="Filter by organization"),
    audit_status: Optional[str] = Query(None, alias="status", description="success or failure"),
    start_date: Optional[datetime] = Query(None, description="ISO timestamp, inclusive"),
    end_date: Optional[datetime] = Query(None, description="ISO timestamp, inclusive"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    query = select(DataAccessAuditLog)
    if user_id is not None:
        query = query.where(DataAccessAuditLog.user_id == user_id)
    if operation_type:
        query = query.where(func.upper(DataAccessAuditLog.operation_type) == operation_type.upper())
    if resource_type:
        query = query.where(func.lower(DataAccessAuditLog.resource_type) == resource_type.lower())
    if resource_id:
        query = query.where(DataAccessAuditLog.resource_id == resource_id)
    if org_id is not None:
        query = query.where(DataAccessAuditLog.org_id == org_id)
    if audit_status:
        query = query.where(func.lower(DataAccessAuditLog.status) == audit_status.lower())
    if start_date is not None:
        query = query.where(DataAccessAuditLog.created_at >= start_date)
    if end_date is not None:
        query = query.where(DataAccessAuditLog.created_at <= end_date)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = (
        query
        .order_by(DataAccessAuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    if request:
        client_ip = request.client.host if request.client else None
        await log_data_access(
            db=db,
            action="list",
            resource="audit_logs",
            resource_id="all",
            user_id=uuid.UUID(current_user.user_id),
            ip_address=client_ip,
            details=f"Queried audit logs (returned {len(entries)} of {total})"
        )

    return AuditLogQueryResponse(
        items=[AuditLogEntry.model_validate(e, from_attributes=True) for e in entries],
        total=total,
        skip=skip,
        limit=limit,
    )
