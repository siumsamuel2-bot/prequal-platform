"""Data Quality Monitoring Service

Provides data quality checks, alerting, and health monitoring for the
compliance data pipeline. Integrates with the existing pipeline to track
sync health, match accuracy, error rates, and trigger alerts when quality
thresholds are breached.

- Thresholds: match rate < 85%, error rate > 5%, stale data > 0, failed jobs > 2
- Archival: non-destructive (copies to archive tables, never deletes source)
- Daily entry point: run_daily_data_quality_check()

Owner: Data Engineer
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration / thresholds
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "match_rate_min": 0.85,
    "error_rate_max": 0.05,
    "stale_hours_max": 25,
    "failed_jobs_max": 2,
    "unmatched_osha_max": 50,
    "unmatched_state_max": 50,
}


# ---------------------------------------------------------------------------
# 1. Health Checks
# ---------------------------------------------------------------------------

async def run_data_quality_health_check(db: AsyncSession) -> Dict[str, Any]:
    """Run a comprehensive data quality health check.
    
    Returns a dict with all quality metrics and any triggered alerts.
    """
    results: Dict[str, Any] = {
        "checked_at": datetime.now().isoformat(),
        "metrics": {},
        "alerts_triggered": [],
    }

    # Sync health metrics
    sync_health = await get_sync_health(db, days=7)
    results["metrics"]["sync_health"] = sync_health

    # Match accuracy
    match_accuracy = await get_match_accuracy(db)
    results["metrics"]["match_accuracy"] = match_accuracy

    # Error rates
    error_rates = await get_error_rates(db, days=7)
    results["metrics"]["error_rates"] = error_rates

    # Stale data
    stale_data = await check_stale_data(db)
    results["metrics"]["stale_data"] = stale_data

    # Trigger alerts based on thresholds
    alerts = await evaluate_thresholds(db, results["metrics"])
    results["alerts_triggered"] = alerts

    return results


async def get_sync_health(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    """Return sync job health summary for the last N days."""
    # Portable query without dialect-specific FILTER / EXTRACT.
    # We aggregate counts and sums, then compute success/failure counts in Python.
    result = await db.execute(
        text(
            """
            SELECT
                job_name,
                job_type,
                COUNT(*) AS total_runs,
                SUM(records_processed) AS total_records_processed,
                SUM(records_inserted) AS total_records_inserted,
                SUM(records_updated) AS total_records_updated,
                SUM(records_failed) AS total_records_failed,
                AVG(
                    (julianday(completed_at) - julianday(started_at)) * 86400
                ) AS avg_duration_seconds,
                MAX(started_at) AS last_run_at
            FROM sync_run_logs
            WHERE started_at >= date('now', '-' || :days || ' days')
            GROUP BY job_name, job_type
            """
        ),
        {"days": days},
    )
    rows = result.mappings().all()

    job_names = [(r["job_name"], r["job_type"]) for r in rows]
    status_counts: Dict[str, Dict[str, int]] = {}
    if job_names:
        # Batch fetch status counts
        placeholders = ", ".join([f"(:jn{i}, :jt{i})" for i in range(len(job_names))])
        params = {}
        for i, (jn, jt) in enumerate(job_names):
            params[f"jn{i}"] = jn
            params[f"jt{i}"] = jt
        status_result = await db.execute(
            text(
                f"""
                SELECT
                    job_name,
                    job_type,
                    status,
                    COUNT(*) AS cnt
                FROM sync_run_logs
                WHERE started_at >= date('now', '-' || :days || ' days')
                AND (job_name, job_type) IN ({placeholders})
                GROUP BY job_name, job_type, status
                """
            ),
            {**params, "days": days},
        )
        for row in status_result.mappings().all():
            key = (row["job_name"], row["job_type"])
            if key not in status_counts:
                status_counts[key] = {}
            status_counts[key][row["status"]] = row["cnt"]

    return {
        "period_days": days,
        "jobs": [
            {
                "job_name": r["job_name"],
                "job_type": r["job_type"],
                "total_runs": r["total_runs"],
                "successful_runs": status_counts.get((r["job_name"], r["job_type"]), {}).get("completed", 0),
                "failed_runs": status_counts.get((r["job_name"], r["job_type"]), {}).get("failed", 0),
                "partial_runs": status_counts.get((r["job_name"], r["job_type"]), {}).get("partial", 0),
                "total_records_processed": r["total_records_processed"] or 0,
                "total_records_inserted": r["total_records_inserted"] or 0,
                "total_records_updated": r["total_records_updated"] or 0,
                "total_records_failed": r["total_records_failed"] or 0,
                "avg_duration_seconds": round(float(r["avg_duration_seconds"] or 0), 2),
                "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
            }
            for r in rows
        ],
    }


async def get_match_accuracy(db: AsyncSession) -> Dict[str, Any]:
    """Return match accuracy metrics for violations and state credentials."""
    # Portable query avoiding FILTER and ::NUMERIC casts.
    result = await db.execute(
        text(
            """
            SELECT
                'violations' AS source_table,
                COUNT(*) AS total_count,
                SUM(CASE WHEN subcontractor_id IS NOT NULL THEN 1 ELSE 0 END) AS matched_count,
                SUM(CASE WHEN subcontractor_id IS NULL THEN 1 ELSE 0 END) AS unmatched_count,
                CASE
                    WHEN COUNT(*) > 0 THEN
                        ROUND(CAST(SUM(CASE WHEN subcontractor_id IS NOT NULL THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4)
                    ELSE 0
                END AS match_rate
            FROM violations
            WHERE is_osha_violation = 1
            UNION ALL
            SELECT
                'state_credential_records' AS source_table,
                COUNT(*) AS total_count,
                SUM(CASE WHEN holder_name IS NOT NULL THEN 1 ELSE 0 END) AS matched_count,
                SUM(CASE WHEN holder_name IS NULL THEN 1 ELSE 0 END) AS unmatched_count,
                CASE
                    WHEN COUNT(*) > 0 THEN
                        ROUND(CAST(SUM(CASE WHEN holder_name IS NOT NULL THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4)
                    ELSE 0
                END AS match_rate
            FROM state_credential_records
            """
        )
    )
    rows = result.mappings().all()
    return {
        "sources": [
            {
                "source_table": r["source_table"],
                "total_count": r["total_count"],
                "matched_count": r["matched_count"],
                "unmatched_count": r["unmatched_count"],
                "match_rate": float(r["match_rate"]),
            }
            for r in rows
        ]
    }


async def get_error_rates(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    """Calculate error rates from sync_run_logs over the last N days."""
    # Portable query avoiding ::NUMERIC casts.
    result = await db.execute(
        text(
            """
            SELECT
                job_name,
                SUM(records_processed) AS total_processed,
                SUM(records_failed) AS total_failed,
                CASE
                    WHEN SUM(records_processed) > 0 THEN
                        ROUND(CAST(SUM(records_failed) AS REAL) / CAST(SUM(records_processed) AS REAL), 4)
                    ELSE 0
                END AS error_rate
            FROM sync_run_logs
            WHERE started_at >= date('now', '-' || :days || ' days')
            GROUP BY job_name
            """
        ),
        {"days": days},
    )
    rows = result.mappings().all()
    return {
        "period_days": days,
        "jobs": [
            {
                "job_name": r["job_name"],
                "total_processed": r["total_processed"] or 0,
                "total_failed": r["total_failed"] or 0,
                "error_rate": float(r["error_rate"]),
            }
            for r in rows
        ],
    }


async def check_stale_data(db: AsyncSession) -> Dict[str, Any]:
    """Check for stale data in key tables."""
    # OSHA data freshness
    result = await db.execute(
        text(
            """
            SELECT data_type, last_updated, next_scheduled_update, status
            FROM osha_data_freshness
            WHERE last_updated < datetime('now', '-25 hours')
            OR status != 'current'
            """
        )
    )
    stale_osha = [dict(r) for r in result.mappings().all()]

    # State credential records not synced in 7 days
    result = await db.execute(
        text(
            """
            SELECT state_code, COUNT(*) AS stale_count
            FROM state_credential_records
            WHERE last_synced_at < datetime('now', '-7 days')
            GROUP BY state_code
            """
        )
    )
    stale_state = [dict(r) for r in result.mappings().all()]

    return {
        "stale_osha_sources": stale_osha,
        "stale_state_credentials": stale_state,
        "total_stale_osha": len(stale_osha),
        "total_stale_state": sum(s["stale_count"] for s in stale_state),
    }


# ---------------------------------------------------------------------------
# 2. Alerting
# ---------------------------------------------------------------------------

async def evaluate_thresholds(db: AsyncSession, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate metrics against configured thresholds and create alerts."""
    alerts: List[Dict[str, Any]] = []
    thresholds = DEFAULT_THRESHOLDS

    # Check match rate
    match_sources = metrics.get("match_accuracy", {}).get("sources", [])
    for source in match_sources:
        if source["match_rate"] < thresholds["match_rate_min"]:
            alert = {
                "alert_type": "match_rate_drop",
                "severity": "warning",
                "source_table": source["source_table"],
                "message": (
                    f"Match rate for {source['source_table']} dropped below threshold: "
                    f"{source['match_rate']:.2%} (threshold: {thresholds['match_rate_min']:.2%})"
                ),
                "threshold_value": thresholds["match_rate_min"],
                "actual_value": source["match_rate"],
            }
            alerts.append(alert)
            await _persist_alert(db, alert)

    # Check error rates
    error_jobs = metrics.get("error_rates", {}).get("jobs", [])
    for job in error_jobs:
        if job["error_rate"] > thresholds["error_rate_max"]:
            alert = {
                "alert_type": "error_rate_spike",
                "severity": "error",
                "source_job": job["job_name"],
                "message": (
                    f"Error rate for {job['job_name']} exceeded threshold: "
                    f"{job['error_rate']:.2%} (threshold: {thresholds['error_rate_max']:.2%})"
                ),
                "threshold_value": thresholds["error_rate_max"],
                "actual_value": job["error_rate"],
            }
            alerts.append(alert)
            await _persist_alert(db, alert)

    # Check stale data
    stale_data = metrics.get("stale_data", {})
    if stale_data.get("total_stale_osha", 0) > 0:
        alert = {
            "alert_type": "stale_data",
            "severity": "warning",
            "source_table": "osha_data_freshness",
            "message": (
                f"OSHA data is stale: {stale_data['total_stale_osha']} sources outdated"
            ),
        }
        alerts.append(alert)
        await _persist_alert(db, alert)

    # Check failed jobs
    sync_health = metrics.get("sync_health", {}).get("jobs", [])
    for job in sync_health:
        if job["failed_runs"] > thresholds["failed_jobs_max"]:
            alert = {
                "alert_type": "sync_failure",
                "severity": "error",
                "source_job": job["job_name"],
                "message": (
                    f"Job {job['job_name']} has {job['failed_runs']} failed runs "
                    f"in the last {metrics['sync_health']['period_days']} days"
                ),
                "threshold_value": thresholds["failed_jobs_max"],
                "actual_value": job["failed_runs"],
            }
            alerts.append(alert)
            await _persist_alert(db, alert)

    return alerts


async def _persist_alert(db: AsyncSession, alert: Dict[str, Any]) -> None:
    """Persist a data quality alert to the database."""
    await db.execute(
        text(
            """
            INSERT INTO data_quality_alerts
            (id, alert_type, severity, source_table, source_job, message,
             threshold_value, actual_value, created_at)
            VALUES
            (:id, :alert_type, :severity, :source_table, :source_job, :message,
             :threshold_value, :actual_value, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(uuid4()),
            "alert_type": alert.get("alert_type"),
            "severity": alert.get("severity"),
            "source_table": alert.get("source_table"),
            "source_job": alert.get("source_job"),
            "message": alert.get("message"),
            "threshold_value": alert.get("threshold_value"),
            "actual_value": alert.get("actual_value"),
        },
    )
    await db.commit()


# ---------------------------------------------------------------------------
# 3. Data Retention / Archival
# ---------------------------------------------------------------------------

async def archive_old_sync_logs(db: AsyncSession, retention_days: int = 90) -> Dict[str, int]:
    """Archive sync_run_logs older than retention_days.

    Copies qualifying records to archived_sync_run_logs.  Per data retention
    policy, records are NEVER deleted from the source table — they are flagged
    by the existence of their copy in the archive table.  Source-table soft-
    delete support (e.g. an archived_at flag) should be added via a future
    schema migration if row count growth becomes a concern.

    Returns a dict with the count of newly archived records.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO archived_sync_run_logs
            (id, job_name, job_type, status, triggered_by, started_at, completed_at,
             records_processed, records_inserted, records_updated, records_failed,
             error_message, run_metadata, archived_at, archive_reason)
            SELECT
                id, job_name, job_type, status, triggered_by, started_at, completed_at,
                records_processed, records_inserted, records_updated, records_failed,
                error_message, run_metadata, CURRENT_TIMESTAMP, 'retention'
            FROM sync_run_logs
            WHERE started_at < date('now', '-' || :days || ' days')
            AND NOT EXISTS (
                SELECT 1 FROM archived_sync_run_logs a WHERE a.id = sync_run_logs.id
            )
            """
        ),
        {"days": retention_days},
    )
    archived_count = result.rowcount
    await db.commit()
    return {"archived": archived_count}


async def archive_old_data_quality_results(db: AsyncSession, retention_days: int = 90) -> Dict[str, int]:
    """Archive data_quality_results older than retention_days.

    Copies qualifying records to archived_data_quality_results.  Per data
    retention policy, records are NEVER deleted from the source table.
    Source-table soft-delete support should be added via a future schema
    migration if row count growth becomes a concern.

    Returns a dict with the count of newly archived records.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO archived_data_quality_results
            (id, check_id, sync_run_id, status, records_checked, records_failed,
             failure_rate, execution_time_ms, sample_failures, executed_at,
             archived_at, archive_reason)
            SELECT
                id, check_id, sync_run_id, status, records_checked, records_failed,
                failure_rate, execution_time_ms, sample_failures, executed_at,
                CURRENT_TIMESTAMP, 'retention'
            FROM data_quality_results
            WHERE executed_at < date('now', '-' || :days || ' days')
            AND NOT EXISTS (
                SELECT 1 FROM archived_data_quality_results a WHERE a.id = data_quality_results.id
            )
            """
        ),
        {"days": retention_days},
    )
    archived_count = result.rowcount
    await db.commit()
    return {"archived": archived_count}


# ---------------------------------------------------------------------------
# 4. Performance Monitoring
# ---------------------------------------------------------------------------

async def log_pipeline_performance(
    db: AsyncSession,
    *,
    run_id: str,
    job_name: str,
    job_type: str,
    stage_name: str,
    stage_order: int = 0,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    records_in: int = 0,
    records_out: int = 0,
    cache_hits: int = 0,
    cache_misses: int = 0,
    api_requests: int = 0,
    api_errors: int = 0,
    avg_api_latency_ms: Optional[int] = None,
    max_api_latency_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a pipeline performance record."""
    if started_at and completed_at:
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    else:
        duration_ms = None

    await db.execute(
        text(
            """
            INSERT INTO pipeline_performance_logs
            (id, run_id, job_name, job_type, stage_name, stage_order, started_at,
             completed_at, duration_ms, records_in, records_out, cache_hits,
             cache_misses, api_requests, api_errors, avg_api_latency_ms,
             max_api_latency_ms, error_message, metadata, created_at)
            VALUES
            (:id, :run_id, :job_name, :job_type, :stage_name, :stage_order,
             :started_at, :completed_at, :duration_ms, :records_in, :records_out,
             :cache_hits, :cache_misses, :api_requests, :api_errors,
             :avg_api_latency_ms, :max_api_latency_ms, :error_message,
             :metadata, CURRENT_TIMESTAMP)
            """
        ),
        {
            "id": str(uuid4()),
            "run_id": run_id,
            "job_name": job_name,
            "job_type": job_type,
            "stage_name": stage_name,
            "stage_order": stage_order,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "records_in": records_in,
            "records_out": records_out,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "api_requests": api_requests,
            "api_errors": api_errors,
            "avg_api_latency_ms": avg_api_latency_ms,
            "max_api_latency_ms": max_api_latency_ms,
            "error_message": error_message,
            "metadata": metadata,
        },
    )
    await db.commit()


# ---------------------------------------------------------------------------
# 5. Analytics Refresh Extensions
# ---------------------------------------------------------------------------

async def refresh_data_quality_views(db: AsyncSession) -> None:
    """Refresh all data-quality-related materialized views.

    On PostgreSQL: issues REFRESH MATERIALIZED VIEW CONCURRENTLY.
    On SQLite (no materialized views): silently skip and return.
    """
    from sqlalchemy.dialects.sqlite.base import SQLiteDialect  # type: ignore[import-untyped]

    dialect = db.bind.dialect if db.bind else None
    if isinstance(dialect, SQLiteDialect):
        logger.info("SQLite detected; skipping MATERIALIZED VIEW refresh (views are regular views).")
        return

    views = [
        "mv_sync_health_dashboard",
        "mv_match_accuracy",
        "mv_pipeline_performance_summary",
        "mv_subcontractor_compliance_trends",
        "mv_certification_expiration_trends",
        "mv_data_quality_summary",
    ]
    for view in views:
        try:
            await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            logger.info("Refreshed materialized view: %s", view)
        except Exception:
            logger.warning("Failed to refresh %s concurrently, trying non-concurrent", view)
            await db.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
            logger.info("Refreshed materialized view: %s", view)


# ---------------------------------------------------------------------------
# 6. Scheduled Entry Point
# ---------------------------------------------------------------------------

async def run_daily_data_quality_check() -> Dict[str, Any]:
    """Run the full data quality check suite (intended for daily scheduler)."""
    db = AsyncSessionLocal()
    try:
        # Run health check
        results = await run_data_quality_health_check(db)

        # Refresh materialized views
        await refresh_data_quality_views(db)

        # Archive old data
        archive_sync = await archive_old_sync_logs(db)
        archive_dqr = await archive_old_data_quality_results(db)
        results["archived"] = {
            "sync_logs": archive_sync,
            "data_quality_results": archive_dqr,
        }

        logger.info("Daily data quality check complete: %s alerts triggered", len(results["alerts_triggered"]))
        return results
    finally:
        await db.close()