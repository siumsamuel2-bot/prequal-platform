"""Webhook listener for state credential database updates.

Provides an endpoint that external state credential databases can POST to
when a credential status changes, allowing real-time or near real-time
synchronization into our platform.
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance import SyncRunLog, DataQualityResult
from app.services.external_compliance_pipeline import (
    run_osha_sync,
    run_state_credential_sync,
    validate_pipeline_health,
    refresh_analytics_views,
)

router = APIRouter(prefix="/api/pipeline", tags=["data_pipeline"])


@router.post("/osha/sync")
async def trigger_osha_sync_route(
    search: Optional[str] = None,
    state: Optional[str] = None,
    max_pages: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger the OSHA data sync run."""
    run = await run_osha_sync(
        db=db, triggered_by="manual", search=search, state=state, max_pages=max_pages
    )
    return {
        "run_id": str(run.id),
        "status": run.status,
        "extracted": run.records_extracted,
        "inserted": run.records_inserted,
        "updated": run.records_updated,
        "failed": run.records_failed,
        "matched": run.records_matched,
    }


@router.post("/state-creds/{state_code}/sync")
async def trigger_state_credential_sync(
    state_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a state credential database sync."""
    run = await run_state_credential_sync(
        db=db, state_code=state_code, triggered_by="manual"
    )
    return {
        "run_id": str(run.id),
        "status": run.status,
        "extracted": run.records_extracted,
        "inserted": run.records_inserted,
        "updated": run.records_updated,
        "failed": run.records_failed,
        "matched": run.records_matched,
    }


@router.post("/data-quality/run")
async def trigger_data_quality_check(
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a data quality check run."""
    checks = await validate_pipeline_health(db)
    return {
        "checks": checks,
        "status": "completed",
    }


@router.post("/analytics/refresh")
async def refresh_analytics(
    db: AsyncSession = Depends(get_db),
):
    """Manually refresh all analytics materialized views."""
    await refresh_analytics_views(db)
    return {"message": "Analytics views refreshed successfully"}


@router.get("/sync-runs")
async def list_sync_runs(
    job_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List recent sync run logs."""
    query = select(SyncRunLog).order_by(SyncRunLog.created_at.desc())
    if job_name:
        query = query.where(SyncRunLog.job_name == job_name)
    if status:
        query = query.where(SyncRunLog.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "job_name": r.job_name,
            "job_type": r.job_type,
            "status": r.status,
            "triggered_by": r.triggered_by,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "records_processed": r.records_processed,
            "records_inserted": r.records_inserted,
            "records_updated": r.records_updated,
            "records_failed": r.records_failed,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/data-quality/results")
async def list_data_quality_results(
    check_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List data quality check results."""
    query = select(DataQualityResult).order_by(DataQualityResult.executed_at.desc())
    if check_id:
        query = query.where(DataQualityResult.check_id == check_id)
    if status:
        query = query.where(DataQualityResult.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "check_id": str(r.check_id),
            "sync_run_id": str(r.sync_run_id),
            "status": r.status,
            "records_checked": r.records_checked,
            "records_failed": r.records_failed,
            "failure_rate": float(r.failure_rate) if r.failure_rate is not None else None,
            "execution_time_ms": r.execution_time_ms,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        }
        for r in rows
    ]
