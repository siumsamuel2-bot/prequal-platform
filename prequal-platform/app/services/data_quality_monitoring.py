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
    "stale_hours_max": 24,  # freshness SLA in hours (MID-605: alert if > 24h)
    "failed_jobs_max": 2,
    "unmatched_osha_max": 50,
    "unmatched_state_max": 50,
    "null_rate_max": 0.10,  # static threshold for critical-field null rates
    "duplicate_rate_max": 0.01,  # duplicate rate ceiling for key fields
    "row_count_drop_pct": 0.50,  # anomaly: row count drop > 50% vs recent avg
    "null_rate_spike_abs": 0.10,  # anomaly: null rate jump >= 10pp vs last snapshot
}

# Critical pipeline fields monitored for null/duplicate rates (MID-605).
# null_condition is a boolean SQL fragment; duplicates only checked where
# check_duplicates is true (keys that must be unique per row).
FIELD_QUALITY_SPECS = [
    {
        "table": "subcontractors",
        "column": "ein",
        "null_condition": "ein IS NULL AND (encrypted_ein IS NULL OR encrypted_ein = '')",
        "check_duplicates": False,
    },
    {
        "table": "subcontractors",
        "column": "license_number",
        "null_condition": "license_number IS NULL",
        "check_duplicates": False,
    },
    {
        "table": "certifications",
        "column": "certification_number",
        "null_condition": "certification_number IS NULL",
        "check_duplicates": True,
    },
    {
        "table": "certifications",
        "column": "expiration_date",
        "null_condition": "expiration_date IS NULL",
        "check_duplicates": False,
    },
    {
        "table": "state_credential_records",
        "column": "credential_number",
        "null_condition": "credential_number IS NULL",
        "check_duplicates": True,
    },
    {
        "table": "state_credential_records",
        "column": "expiration_date",
        "null_condition": "expiration_date IS NULL",
        "check_duplicates": False,
    },
    {
        "table": "violations",
        "column": "citation_number",
        "null_condition": "citation_number IS NULL",
        "check_duplicates": False,
    },
]

# Tables whose schemas are tracked for drift between monitoring runs.
SCHEMA_DRIFT_TABLES = [
    "subcontractors",
    "certifications",
    "violations",
    "state_credential_records",
    "sync_run_logs",
    "osha_data_freshness",
]


def _parse_dt(value: Any) -> Optional[datetime]:
    """Coerce a DB value (datetime or ISO string) to a naive UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            if fmt is None:
                dt = datetime.fromisoformat(s.split(".")[0] if "+" not in s else s)
            else:
                dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _is_sqlite(db: AsyncSession) -> bool:
    from sqlalchemy.dialects.sqlite.base import SQLiteDialect  # type: ignore[import-untyped]

    return bool(db.bind) and isinstance(db.bind.dialect, SQLiteDialect)


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

    # Field-level null/duplicate rates (persists snapshot for trend data)
    results["metrics"]["field_quality"] = await get_field_quality_metrics(db, persist=True)

    # Schema drift detection (persists snapshot)
    results["metrics"]["schema_drift"] = await detect_schema_drift(db, persist=True)

    # Volume anomaly detection (row-count drops)
    results["metrics"]["volume_anomalies"] = await detect_volume_anomalies(db)

    # Freshness SLA (last successful sync per source)
    results["metrics"]["freshness"] = await check_freshness_sla(db)

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
                "last_run_at": (lambda dt: dt.isoformat() if dt else None)(_parse_dt(r["last_run_at"])),
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
# 2. Field-Level Quality Metrics (MID-605)
# ---------------------------------------------------------------------------

async def _latest_field_metric_rates(db: AsyncSession) -> Dict[tuple, float]:
    """Return {(table, column): null_rate} from the most recent snapshot."""
    try:
        result = await db.execute(
            text(
                """
                SELECT f.table_name, f.column_name, f.null_rate
                FROM data_quality_field_metrics f
                JOIN (
                    SELECT table_name, column_name, MAX(captured_at) AS max_captured
                    FROM data_quality_field_metrics
                    GROUP BY table_name, column_name
                ) latest
                ON f.table_name = latest.table_name
                AND f.column_name = latest.column_name
                AND f.captured_at = latest.max_captured
                """
            )
        )
        return {
            (r["table_name"], r["column_name"]): float(r["null_rate"] or 0.0)
            for r in result.mappings().all()
        }
    except Exception as exc:
        logger.warning("Could not load previous field metrics (first run?): %s", exc)
        return {}


async def get_field_quality_metrics(
    db: AsyncSession, persist: bool = True
) -> Dict[str, Any]:
    """Compute null/duplicate rates for critical fields.

    Persists a snapshot row per field to data_quality_field_metrics (unless
    persist=False) and reports null-rate spikes vs the previous snapshot.
    """
    thresholds = DEFAULT_THRESHOLDS
    previous_rates = await _latest_field_metric_rates(db)

    fields: List[Dict[str, Any]] = []
    spikes: List[Dict[str, Any]] = []
    captured_at = datetime.utcnow()

    for spec in FIELD_QUALITY_SPECS:
        table = spec["table"]
        column = spec["column"]
        try:
            total_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            total = int(total_result.scalar() or 0)

            null_result = await db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {spec['null_condition']}")
            )
            null_count = int(null_result.scalar() or 0)
        except Exception as exc:
            logger.warning("Skipping field metric %s.%s: %s", table, column, exc)
            continue

        duplicate_count = 0
        if spec.get("check_duplicates") and total > 0:
            dup_result = await db.execute(
                text(
                    f"""
                    SELECT COALESCE(SUM(cnt - 1), 0) FROM (
                        SELECT COUNT(*) AS cnt
                        FROM {table}
                        WHERE {column} IS NOT NULL
                        GROUP BY {column}
                        HAVING COUNT(*) > 1
                    ) dups
                    """
                )
            )
            duplicate_count = int(dup_result.scalar() or 0)

        null_rate = round(null_count / total, 4) if total > 0 else 0.0
        duplicate_rate = round(duplicate_count / total, 4) if total > 0 else 0.0

        prev_rate = previous_rates.get((table, column))
        if prev_rate is not None and (null_rate - prev_rate) >= thresholds["null_rate_spike_abs"]:
            spikes.append(
                {
                    "table_name": table,
                    "column_name": column,
                    "previous_null_rate": prev_rate,
                    "current_null_rate": null_rate,
                }
            )

        fields.append(
            {
                "table_name": table,
                "column_name": column,
                "total_rows": total,
                "null_count": null_count,
                "null_rate": null_rate,
                "duplicate_count": duplicate_count,
                "duplicate_rate": duplicate_rate,
            }
        )

        if persist:
            await db.execute(
                text(
                    """
                    INSERT INTO data_quality_field_metrics
                    (id, captured_at, table_name, column_name, total_rows,
                     null_count, null_rate, duplicate_count, duplicate_rate)
                    VALUES
                    (:id, :captured_at, :table_name, :column_name, :total_rows,
                     :null_count, :null_rate, :duplicate_count, :duplicate_rate)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "captured_at": captured_at,
                    "table_name": table,
                    "column_name": column,
                    "total_rows": total,
                    "null_count": null_count,
                    "null_rate": null_rate,
                    "duplicate_count": duplicate_count,
                    "duplicate_rate": duplicate_rate,
                },
            )

    if persist:
        await db.commit()

    return {
        "captured_at": captured_at.isoformat(),
        "fields": fields,
        "spikes": spikes,
    }


async def get_field_quality_trends(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    """Return historical field metric snapshots for trend charts (7d/30d)."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        result = await db.execute(
            text(
                """
                SELECT table_name, column_name, captured_at, total_rows,
                       null_count, null_rate, duplicate_count, duplicate_rate
                FROM data_quality_field_metrics
                WHERE captured_at >= :cutoff
                ORDER BY table_name, column_name, captured_at
                """
            ),
            {"cutoff": cutoff},
        )
    except Exception as exc:
        logger.warning("Could not load field metric trends: %s", exc)
        return {"period_days": days, "series": []}

    series: Dict[tuple, Dict[str, Any]] = {}
    for r in result.mappings().all():
        key = (r["table_name"], r["column_name"])
        if key not in series:
            series[key] = {"table_name": key[0], "column_name": key[1], "points": []}
        captured = _parse_dt(r["captured_at"])
        series[key]["points"].append(
            {
                "captured_at": captured.isoformat() if captured else None,
                "total_rows": r["total_rows"],
                "null_rate": float(r["null_rate"] or 0.0),
                "duplicate_rate": float(r["duplicate_rate"] or 0.0),
            }
        )
    return {"period_days": days, "series": list(series.values())}


# ---------------------------------------------------------------------------
# 3. Schema Drift Detection (MID-605)
# ---------------------------------------------------------------------------

async def _get_table_columns(db: AsyncSession, table: str) -> List[str]:
    """Return the live column list for a table (dialect-portable)."""
    if table not in SCHEMA_DRIFT_TABLES:
        raise ValueError(f"Table not in schema drift whitelist: {table}")
    if _is_sqlite(db):
        result = await db.execute(text(f'PRAGMA table_info("{table}")'))
        return [r[1] for r in result.all()]
    result = await db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"table_name": table},
    )
    return [r[0] for r in result.all()]


async def detect_schema_drift(db: AsyncSession, persist: bool = True) -> Dict[str, Any]:
    """Detect schema drift for monitored pipeline tables.

    Compares live columns against the previous snapshot per table (new/removed
    columns). Persists a fresh snapshot per run when persist=True.
    """
    import json as _json

    tables: List[Dict[str, Any]] = []
    drift_detected = False

    for table in SCHEMA_DRIFT_TABLES:
        try:
            current_columns = await _get_table_columns(db, table)
        except Exception as exc:
            logger.warning("Schema drift: could not introspect %s: %s", table, exc)
            continue

        previous_columns: Optional[List[str]] = None
        try:
            prev_result = await db.execute(
                text(
                    """
                    SELECT columns_json
                    FROM data_quality_schema_snapshots
                    WHERE table_name = :table_name
                    ORDER BY captured_at DESC
                    LIMIT 1
                    """
                ),
                {"table_name": table},
            )
            prev_row = prev_result.first()
            if prev_row is not None:
                raw = prev_row[0]
                previous_columns = _json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception as exc:
            logger.warning("Schema drift: could not load snapshot for %s: %s", table, exc)

        added: List[str] = []
        removed: List[str] = []
        if previous_columns is not None:
            prev_set = set(previous_columns)
            cur_set = set(current_columns)
            added = sorted(cur_set - prev_set)
            removed = sorted(prev_set - cur_set)
            if added or removed:
                drift_detected = True

        tables.append(
            {
                "table_name": table,
                "column_count": len(current_columns),
                "added_columns": added,
                "removed_columns": removed,
                "baseline": previous_columns is None,
            }
        )

        if persist:
            await db.execute(
                text(
                    """
                    INSERT INTO data_quality_schema_snapshots
                    (id, table_name, columns_json, captured_at)
                    VALUES (:id, :table_name, :columns_json, :captured_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "table_name": table,
                    "columns_json": _json.dumps(sorted(current_columns)),
                    "captured_at": datetime.utcnow(),
                },
            )

    if persist:
        await db.commit()

    return {
        "checked_at": datetime.utcnow().isoformat(),
        "drift_detected": drift_detected,
        "tables": tables,
    }


# ---------------------------------------------------------------------------
# 4. Volume Anomaly Detection & Freshness SLA (MID-605)
# ---------------------------------------------------------------------------

async def detect_volume_anomalies(db: AsyncSession) -> Dict[str, Any]:
    """Detect sudden row-count drops per sync job.

    Compares the most recent completed run's records_processed against the
    average of up to 10 previous completed runs. A drop greater than
    row_count_drop_pct (default 50%) is flagged as an anomaly.
    """
    drop_pct = DEFAULT_THRESHOLDS["row_count_drop_pct"]
    result = await db.execute(
        text(
            """
            SELECT job_name, records_processed, completed_at
            FROM sync_run_logs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            """
        )
    )

    by_job: Dict[str, List[Dict[str, Any]]] = {}
    for r in result.mappings().all():
        by_job.setdefault(r["job_name"], []).append(
            {
                "records_processed": int(r["records_processed"] or 0),
                "completed_at": _parse_dt(r["completed_at"]),
            }
        )

    anomalies: List[Dict[str, Any]] = []
    jobs: List[Dict[str, Any]] = []
    for job_name, runs in by_job.items():
        latest = runs[0]
        history = runs[1:11]
        baseline_avg = (
            sum(r["records_processed"] for r in history) / len(history) if history else None
        )
        anomaly = None
        if (
            baseline_avg is not None
            and len(history) >= 2
            and baseline_avg > 0
            and latest["records_processed"] < baseline_avg * (1 - drop_pct)
        ):
            anomaly = {
                "job_name": job_name,
                "latest_records": latest["records_processed"],
                "baseline_avg_records": round(baseline_avg, 2),
                "drop_pct": round(1 - (latest["records_processed"] / baseline_avg), 4),
            }
            anomalies.append(anomaly)
        jobs.append(
            {
                "job_name": job_name,
                "latest_records": latest["records_processed"],
                "baseline_avg_records": round(baseline_avg, 2) if baseline_avg is not None else None,
                "anomalous": anomaly is not None,
            }
        )

    return {"drop_pct_threshold": drop_pct, "jobs": jobs, "anomalies": anomalies}


async def check_freshness_sla(
    db: AsyncSession, sla_hours: Optional[int] = None
) -> Dict[str, Any]:
    """Check data freshness SLA (default: stale_hours_max hours) per sync job.

    A source breaches the SLA when it has no successful run, or its last
    successful sync is older than sla_hours.
    """
    sla = sla_hours if sla_hours is not None else int(DEFAULT_THRESHOLDS["stale_hours_max"])
    result = await db.execute(
        text(
            """
            SELECT job_name, MAX(completed_at) AS last_success
            FROM sync_run_logs
            WHERE status = 'completed'
            GROUP BY job_name
            """
        )
    )

    now = datetime.utcnow()
    sources: List[Dict[str, Any]] = []
    for r in result.mappings().all():
        last_success = _parse_dt(r["last_success"])
        age_hours = round((now - last_success).total_seconds() / 3600, 2) if last_success else None
        breached = last_success is None or (age_hours is not None and age_hours > sla)
        sources.append(
            {
                "job_name": r["job_name"],
                "last_successful_sync": last_success.isoformat() if last_success else None,
                "age_hours": age_hours,
                "breached": breached,
            }
        )

    return {
        "sla_hours": sla,
        "sources": sources,
        "total_breached": sum(1 for s in sources if s["breached"]),
    }


async def get_source_health(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    """Per-source health status: healthy / degraded / down.

    - down:     no successful run ever, or last success older than 2x SLA
    - degraded: SLA breached, error rate above threshold, or any failed run
    - healthy:  otherwise
    """
    sync_health = await get_sync_health(db, days=days)
    error_rates = await get_error_rates(db, days=days)
    freshness = await check_freshness_sla(db)

    sla = freshness["sla_hours"]
    error_by_job = {j["job_name"]: j["error_rate"] for j in error_rates["jobs"]}
    freshness_by_job = {s["job_name"]: s for s in freshness["sources"]}

    sources: List[Dict[str, Any]] = []
    for job in sync_health["jobs"]:
        job_name = job["job_name"]
        fresh = freshness_by_job.get(job_name)
        error_rate = error_by_job.get(job_name, 0.0)
        age_hours = fresh["age_hours"] if fresh else None

        if fresh is None or age_hours is None or age_hours > 2 * sla:
            status = "down"
        elif fresh["breached"] or error_rate > DEFAULT_THRESHOLDS["error_rate_max"] or job["failed_runs"] > 0:
            status = "degraded"
        else:
            status = "healthy"

        sources.append(
            {
                "source": job_name,
                "status": status,
                "last_successful_sync": fresh["last_successful_sync"] if fresh else None,
                "age_hours": age_hours,
                "error_rate": error_rate,
                "failed_runs_7d": job["failed_runs"],
                "total_records_processed_7d": job["total_records_processed"],
            }
        )

    overall = "healthy"
    if any(s["status"] == "down" for s in sources):
        overall = "down"
    elif any(s["status"] == "degraded" for s in sources):
        overall = "degraded"

    return {"overall": overall, "sources": sources}


async def collect_data_quality_metrics(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    """Read-only metrics snapshot for API consumption (no persistence/alerts)."""
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "sync_health": await get_sync_health(db, days=days),
        "match_accuracy": await get_match_accuracy(db),
        "error_rates": await get_error_rates(db, days=days),
        "stale_data": await check_stale_data(db),
        "field_quality": await get_field_quality_metrics(db, persist=False),
        "schema_drift": await detect_schema_drift(db, persist=False),
        "volume_anomalies": await detect_volume_anomalies(db),
        "freshness": await check_freshness_sla(db),
        "source_health": await get_source_health(db, days=days),
    }


# ---------------------------------------------------------------------------
# 5. Alerting
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

    # Check field-level null rates (MID-605)
    field_quality = metrics.get("field_quality", {})
    for field in field_quality.get("fields", []):
        label = f"{field['table_name']}.{field['column_name']}"
        if field["null_rate"] > thresholds["null_rate_max"]:
            alert = {
                "alert_type": "high_null_rate",
                "severity": "warning" if field["null_rate"] <= 2 * thresholds["null_rate_max"] else "error",
                "source_table": field["table_name"],
                "message": (
                    f"Null rate for {label} above threshold: "
                    f"{field['null_rate']:.2%} ({field['null_count']}/{field['total_rows']} rows; "
                    f"threshold: {thresholds['null_rate_max']:.2%})"
                ),
                "threshold_value": thresholds["null_rate_max"],
                "actual_value": field["null_rate"],
            }
            alerts.append(alert)
            await _persist_alert(db, alert)
        if field["duplicate_rate"] > thresholds["duplicate_rate_max"]:
            alert = {
                "alert_type": "high_duplicate_rate",
                "severity": "warning",
                "source_table": field["table_name"],
                "message": (
                    f"Duplicate rate for {label} above threshold: "
                    f"{field['duplicate_rate']:.2%} ({field['duplicate_count']} duplicate rows)"
                ),
                "threshold_value": thresholds["duplicate_rate_max"],
                "actual_value": field["duplicate_rate"],
            }
            alerts.append(alert)
            await _persist_alert(db, alert)

    # Null-rate spikes vs previous snapshot (MID-605)
    for spike in field_quality.get("spikes", []):
        alert = {
            "alert_type": "null_rate_spike",
            "severity": "error",
            "source_table": spike["table_name"],
            "message": (
                f"Null rate spike for {spike['table_name']}.{spike['column_name']}: "
                f"{spike['previous_null_rate']:.2%} -> {spike['current_null_rate']:.2%}"
            ),
            "threshold_value": thresholds["null_rate_spike_abs"],
            "actual_value": spike["current_null_rate"] - spike["previous_null_rate"],
        }
        alerts.append(alert)
        await _persist_alert(db, alert)

    # Volume anomalies: sudden row-count drops > configured pct (MID-605)
    volume = metrics.get("volume_anomalies", {})
    for anomaly in volume.get("anomalies", []):
        alert = {
            "alert_type": "row_count_drop",
            "severity": "error",
            "source_job": anomaly["job_name"],
            "message": (
                f"Row count drop for {anomaly['job_name']}: "
                f"{anomaly['latest_records']} records vs baseline avg "
                f"{anomaly['baseline_avg_records']} (drop: {anomaly['drop_pct']:.2%})"
            ),
            "threshold_value": thresholds["row_count_drop_pct"],
            "actual_value": anomaly["drop_pct"],
        }
        alerts.append(alert)
        await _persist_alert(db, alert)

    # Freshness SLA breaches: > sla_hours since last successful sync (MID-605)
    freshness = metrics.get("freshness", {})
    for source in freshness.get("sources", []):
        if not source["breached"]:
            continue
        sla = freshness.get("sla_hours", thresholds["stale_hours_max"])
        age = source["age_hours"]
        alert = {
            "alert_type": "freshness_sla_breach",
            "severity": "error" if (age is None or age > 2 * sla) else "warning",
            "source_job": source["job_name"],
            "message": (
                f"Freshness SLA breach for {source['job_name']}: "
                f"last successful sync "
                + (f"{age:.1f}h ago" if age is not None else "never")
                + f" (SLA: {sla}h)"
            ),
            "threshold_value": sla,
            "actual_value": age,
        }
        alerts.append(alert)
        await _persist_alert(db, alert)

    # Schema drift: new/removed columns vs previous snapshot (MID-605)
    schema_drift = metrics.get("schema_drift", {})
    if schema_drift.get("drift_detected"):
        for table in schema_drift.get("tables", []):
            if not (table["added_columns"] or table["removed_columns"]):
                continue
            alert = {
                "alert_type": "schema_change",
                "severity": "warning",
                "source_table": table["table_name"],
                "message": (
                    f"Schema change detected on {table['table_name']}: "
                    f"added={table['added_columns'] or '[]'} "
                    f"removed={table['removed_columns'] or '[]'}"
                ),
            }
            alerts.append(alert)
            await _persist_alert(db, alert)

    return alerts


async def _persist_alert(db: AsyncSession, alert: Dict[str, Any]) -> None:
    """Persist a data quality alert to the database.

    Also emits a data-access audit event (MID-434 integration) with
    compliance_tag='data_quality' so quality events flow into the audit log.
    """
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

    # MID-605 / MID-434 integration: record data quality events in the
    # data-access audit trail. Failures here must never break the pipeline.
    try:
        from app.services.audit_logging import log_data_access

        log_data_access(
            "DATA_QUALITY_ALERT",
            "data_quality_alerts",
            resource_id=alert.get("source_table") or alert.get("source_job"),
            change_summary=(
                f"[{alert.get('severity')}] {alert.get('alert_type')}: "
                f"{alert.get('message')}"
            ),
            compliance_tag="data_quality",
        )
    except Exception as exc:
        logger.warning("Data quality audit event emission failed: %s", exc)


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