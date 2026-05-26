"""Analytics REST endpoints for the Dashboard & Compliance Metrics.

Provides endpoints backed by materialized views for consistent, performant
aggregations. These endpoints power the frontend Dashboard page.

Endpoints:
    GET /api/analytics/compliance/summary    — single-row compliance summary
    GET /api/analytics/compliance/trends      — daily compliance trend data
    GET /api/analytics/compliance/export      — CSV export of certifications
    GET /api/analytics/alerts/recent          — recent alert log entries
    GET /api/analytics/projects               — per-project compliance summary

Owner: Data Engineer
"""
from __future__ import annotations

import csv
import io
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.compliance import (
    ComplianceSummaryResponse,
    ComplianceTrendPoint,
    CertificationExportRow,
    ProjectComplianceSummary,
    RecentAlert,
)
from app.routers.auth import get_current_user, TokenData
from app.services.analytics_pipeline import (
    get_compliance_summary,
    get_compliance_trends,
    get_certification_export_rows,
    get_certification_export_count,
    get_recent_alerts,
    get_recent_alerts_count,
    get_all_project_compliance,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# GET /api/analytics/compliance/summary
# ---------------------------------------------------------------------------

@router.get("/compliance/summary", response_model=ComplianceSummaryResponse)
async def compliance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """Return a single-row compliance summary backed by mv_compliance_summary."""
    data = await get_compliance_summary(db)
    return ComplianceSummaryResponse(**data)


# ---------------------------------------------------------------------------
# GET /api/analytics/compliance/trends?days=30|60|90
# ---------------------------------------------------------------------------

@router.get("/compliance/trends", response_model=list[ComplianceTrendPoint])
async def compliance_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return daily compliance trend points for the last ``days`` days."""
    data = await get_compliance_trends(db, days=days)
    return [ComplianceTrendPoint(**row).model_dump() for row in data]


# ---------------------------------------------------------------------------
# GET /api/analytics/compliance/export?format=csv
# ---------------------------------------------------------------------------

@router.get("/compliance/export")
async def compliance_export(
    format: str = Query("csv", pattern="^(csv|json)$"),
    expiration_bucket: Optional[str] = None,
    limit: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Export certification status rows (CSV or JSON)."""
    try:
        rows = await get_certification_export_rows(
            db,
            expiration_bucket=expiration_bucket,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if format == "json":
        return rows

    # CSV path
    if not rows:
        # Return an empty CSV with headers only
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CertificationExportRow.model_fields.keys())
        writer.writeheader()
        return StreamingResponse(
            io.BytesIO(buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=compliance_export.csv"},
        )

    # Build CSV from rows
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_export.csv"},
    )


# ---------------------------------------------------------------------------
# GET /api/analytics/alerts/recent
# ---------------------------------------------------------------------------

@router.get("/alerts/recent", response_model=list[RecentAlert])
async def alerts_recent(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return recent alert log entries backed by mv_recent_alerts."""
    data = await get_recent_alerts(db, status=status, limit=limit, offset=offset)
    return [RecentAlert(**row).model_dump() for row in data]


# ---------------------------------------------------------------------------
# GET /api/analytics/projects
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=list[ProjectComplianceSummary])
async def projects_compliance(
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return per-project compliance summaries backed by mv_project_compliance."""
    data = await get_all_project_compliance(db, limit=limit, offset=offset)
    return [ProjectComplianceSummary(**row).model_dump() for row in data]
