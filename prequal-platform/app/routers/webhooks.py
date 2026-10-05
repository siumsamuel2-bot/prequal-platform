"""Webhook listener for state credential database updates.

Provides an endpoint that external state credential databases can POST to
when a credential status changes, allowing real-time or near real-time
synchronization into our platform.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance import SyncRunLog, DataQualityResult
from app.routers.auth import (
    get_current_user,
    require_manager_or_admin,
    TokenData,
)
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
    current_user: TokenData = Depends(get_current_user),
    _: None = Depends(require_manager_or_admin),
):
    """Manually trigger the OSHA data sync run (manager or admin only)."""
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
    current_user: TokenData = Depends(get_current_user),
    _: None = Depends(require_manager_or_admin),
):
    """Manually trigger a state credential database sync (manager or admin only)."""
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
    current_user: TokenData = Depends(get_current_user),
    _: None = Depends(require_manager_or_admin),
):
    """Manually trigger a full data quality check run (manager or admin only).

    Runs pipeline health validation plus the MID-605 monitoring suite
    (field quality, schema drift, volume anomalies, freshness SLA) and
    persists any threshold-breach alerts.
    """
    from app.services.data_quality_monitoring import run_data_quality_health_check

    checks = await validate_pipeline_health(db)
    monitoring = await run_data_quality_health_check(db)
    return {
        "checks": checks,
        "monitoring": monitoring,
        "alerts_triggered": len(monitoring.get("alerts_triggered", [])),
        "status": "completed",
    }


@router.post("/analytics/refresh")
async def refresh_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
    _: None = Depends(require_manager_or_admin),
):
    """Manually refresh all analytics materialized views (manager or admin only)."""
    await refresh_analytics_views(db)
    return {"message": "Analytics views refreshed successfully"}


@router.get("/sync-runs")
async def list_sync_runs(
    job_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """List recent sync run logs (authenticated users only)."""
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
    current_user: TokenData = Depends(get_current_user),
):
    """List data quality check results (authenticated users only)."""
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


# ---------------------------------------------------------------------------
# Data Quality Monitoring & Observability (MID-605)
# ---------------------------------------------------------------------------

@router.get("/data-quality/metrics")
async def get_data_quality_metrics(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Full read-only data quality metrics snapshot for observability.

    Returns sync health, match accuracy, error rates, stale data, field-level
    null/duplicate rates, schema drift status, volume anomalies, freshness
    SLA status, and per-source health. Consumable by Grafana (MID-142) via
    the JSON data source. Does not persist snapshots or trigger alerts.
    """
    from app.services.data_quality_monitoring import collect_data_quality_metrics

    return await collect_data_quality_metrics(db, days=days)


@router.get("/data-quality/health")
async def get_data_quality_health(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Per-source health status (healthy/degraded/down) plus overall rollup."""
    from app.services.data_quality_monitoring import get_source_health

    return await get_source_health(db, days=days)


@router.get("/data-quality/alerts")
async def list_data_quality_alerts(
    acknowledged: Optional[bool] = None,
    severity: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """List data quality alerts (most recent first)."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    conditions = ["created_at >= :cutoff"]
    params: dict = {"cutoff": cutoff, "limit": limit}
    if acknowledged is not None:
        conditions.append("is_acknowledged = :acknowledged")
        params["acknowledged"] = acknowledged
    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity

    result = await db.execute(
        sql_text(
            f"""
            SELECT id, alert_type, severity, source_table, source_job, message,
                   threshold_value, actual_value, is_acknowledged, acknowledged_at,
                   acknowledged_by, created_at
            FROM data_quality_alerts
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        params,
    )
    return [
        {
            "id": str(r["id"]),
            "alert_type": r["alert_type"],
            "severity": r["severity"],
            "source_table": r["source_table"],
            "source_job": r["source_job"],
            "message": r["message"],
            "threshold_value": float(r["threshold_value"]) if r["threshold_value"] is not None else None,
            "actual_value": float(r["actual_value"]) if r["actual_value"] is not None else None,
            "is_acknowledged": bool(r["is_acknowledged"]),
            "acknowledged_at": str(r["acknowledged_at"]) if r["acknowledged_at"] else None,
            "acknowledged_by": r["acknowledged_by"],
            "created_at": str(r["created_at"]),
        }
        for r in result.mappings().all()
    ]


@router.post("/data-quality/alerts/{alert_id}/acknowledge")
async def acknowledge_data_quality_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
    _: None = Depends(require_manager_or_admin),
):
    """Acknowledge a data quality alert (manager or admin only)."""
    result = await db.execute(
        sql_text(
            """
            UPDATE data_quality_alerts
            SET is_acknowledged = :ack,
                acknowledged_at = :ack_at,
                acknowledged_by = :ack_by
            WHERE id = :alert_id
            """
        ),
        {
            "ack": True,
            "ack_at": datetime.utcnow(),
            "ack_by": getattr(current_user, "email", None) or str(getattr(current_user, "user_id", "unknown")),
            "alert_id": alert_id,
        },
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"id": alert_id, "acknowledged": True}


@router.get("/data-quality/trends")
async def get_data_quality_trends(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Historical trend data for dashboards.

    - daily_sync_runs: per-day run counts, successes, failures, records
      processed (from sync_run_logs; 7d or 30d windows)
    - field_quality: per-field null/duplicate rate series (from
      data_quality_field_metrics snapshots)
    """
    from app.services.data_quality_monitoring import get_field_quality_trends

    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        sql_text(
            """
            SELECT job_name, status, started_at, completed_at,
                   records_processed, records_failed
            FROM sync_run_logs
            WHERE started_at >= :cutoff
            ORDER BY started_at
            """
        ),
        {"cutoff": cutoff},
    )

    daily: dict = {}
    for r in result.mappings().all():
        started = r["started_at"]
        day = str(started)[:10] if started is not None else "unknown"
        bucket = daily.setdefault(
            day,
            {
                "date": day,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "records_processed": 0,
                "records_failed": 0,
            },
        )
        bucket["total_runs"] += 1
        if r["status"] == "completed":
            bucket["successful_runs"] += 1
        elif r["status"] == "failed":
            bucket["failed_runs"] += 1
        bucket["records_processed"] += int(r["records_processed"] or 0)
        bucket["records_failed"] += int(r["records_failed"] or 0)

    return {
        "period_days": days,
        "daily_sync_runs": [daily[k] for k in sorted(daily)],
        "field_quality": await get_field_quality_trends(db, days=days),
    }
