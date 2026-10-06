"""Data Pipeline module (legacy wrapper).

This module now re-exports the canonical implementation from
``external_compliance_pipeline`` to preserve backward compatibility.
All new code should import directly from ``external_compliance_pipeline``.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SyncRunLog

from app.services.external_compliance_pipeline import (  # noqa: F401
    run_osha_sync,
    validate_pipeline_health,
    refresh_analytics_views,
    run_full_pipeline,
    record_pipeline_metric,
    get_pipeline_health_summary,
    MatchResult,
    PipelineRun,
    match_subcontractor,
    normalize_company_name,
    parse_date,
    parse_decimal,
    map_status,
)

__all__ = [
    "run_osha_sync",
    "run_state_credential_sync",
    "run_state_credential_sync_legacy",
    "validate_pipeline_health",
    "refresh_analytics_views",
    "run_full_pipeline",
    "record_pipeline_metric",
    "get_pipeline_health_summary",
    "MatchResult",
    "PipelineRun",
    "match_subcontractor",
    "normalize_company_name",
    "parse_date",
    "parse_decimal",
    "map_status",
    "_open_run",
    "_close_run",
    "run_data_quality_checks",
    "_load_state_credential_record",
]


# ---------------------------------------------------------------------------
# Sync Run Log helpers
# ---------------------------------------------------------------------------


async def _open_run(
    db: AsyncSession,
    job_name: str,
    job_type: str,
    triggered_by: str = "schedule",
) -> SyncRunLog:
    """Create a new sync run log entry with status 'running'."""
    run = SyncRunLog(
        job_name=job_name,
        job_type=job_type,
        status="running",
        triggered_by=triggered_by,
        started_at=datetime.now(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _close_run(
    db: AsyncSession,
    run: SyncRunLog,
    status: str,
    stats: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    error_message: Optional[str] = None,
) -> SyncRunLog:
    """Update a sync run log entry with final status and stats."""
    run.status = status
    run.completed_at = datetime.now()
    if error:
        error_message = error
    if error_message:
        run.error_message = error_message
    if stats:
        run.records_processed = stats.get("records_processed", 0)
        run.records_inserted = stats.get("records_inserted", 0)
        run.records_updated = stats.get("records_updated", 0)
        run.records_failed = stats.get("records_failed", 0)
    await db.commit()
    await db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Data Quality Checks
# ---------------------------------------------------------------------------


async def run_data_quality_checks(
    *, triggered_by: str = "schedule", db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """Run all active data quality checks and return a summary."""
    from sqlalchemy import select as sa_select, text as sa_text
    from app.models.compliance import DataQualityCheck

    if db is None:
        from app.database import AsyncSessionLocal

        db = AsyncSessionLocal()

    result = await db.execute(sa_select(DataQualityCheck).where(DataQualityCheck.is_active == True))
    active_checks = result.scalars().all()
    total_rules = len(active_checks)

    passed = 0
    failed = 0
    errors = 0

    for check in active_checks:
        try:
            # Execute the check query against the DB
            if check.check_query:
                q = sa_text(check.check_query)
                row = await db.execute(q)
                rows = row.fetchall()
                # Check query should return 0 rows for pass (no violations), rows for fail (violations found)
                # If it returns a single numeric value, 0 = pass, non-zero = fail
                if rows:
                    # Check if it's a single-column single-row result with a numeric value
                    if len(rows) == 1 and len(rows[0]) == 1:
                        val = rows[0][0]
                        if val == 0 or val is False or val == "0" or val == "false":
                            passed += 1
                        else:
                            failed += 1
                    else:
                        # Multiple rows or columns = violations found
                        failed += 1
                else:
                    # No rows = no violations = pass
                    passed += 1
            else:
                passed += 1
        except Exception:
            failed += 1

    errors = total_rules - passed - failed

    return {
        "total_rules": total_rules,
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# State Credential Record helpers
# ---------------------------------------------------------------------------


async def _load_state_credential_record(
    db: AsyncSession, rec: dict
) -> dict:
    """Upsert a state credential record and return {success, existing, id}."""
    state_code = rec.get("state_code", "")
    cred_num = rec.get("credential_number", "")
    cred_type = rec.get("credential_type", "")

    result = await db.execute(
        text(
            "SELECT id FROM state_credential_records WHERE state_code = :st "
            "AND credential_number = :num AND credential_type = :ctype"
        ),
        {"st": state_code, "num": cred_num, "ctype": cred_type},
    )
    existing_row = result.scalar_one_or_none()

    if existing_row:
        # Update existing record
        await db.execute(
            text(
                """UPDATE state_credential_records SET
                    issuing_state = :issuing_state,
                    holder_name = :holder_name,
                    holder_address = :holder_address,
                    holder_city = :holder_city,
                    holder_state = :holder_state,
                    holder_zip = :holder_zip,
                    issue_date = :issue_date,
                    expiration_date = :expiration_date,
                    status = :status,
                    external_source_id = :external_source_id,
                    external_source_url = :external_source_url,
                    last_synced_at = :last_synced_at,
                    sync_version = sync_version + 1,
                    raw_data = :raw_data,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {
                "id": str(existing_row),
                "issuing_state": state_code,
                "holder_name": rec.get("holder_name", ""),
                "holder_address": rec.get("holder_address"),
                "holder_city": rec.get("holder_city"),
                "holder_state": rec.get("holder_state"),
                "holder_zip": rec.get("holder_zip"),
                "issue_date": rec.get("issue_date"),
                "expiration_date": rec.get("expiration_date"),
                "status": rec.get("status", "active"),
                "external_source_id": rec.get("external_source_id"),
                "external_source_url": rec.get("external_source_url"),
                "last_synced_at": datetime.now(),
                "raw_data": json.dumps(rec, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)),
            },
        )
        await db.commit()
        return {"success": True, "existing": True, "id": existing_row}

    # Insert new record — keep str for sqlite binding, return as UUID for API
    import uuid as _uuid_mod

    new_id = str(_uuid_mod.uuid4())
    new_uuid = _uuid_mod.UUID(new_id)

    await db.execute(
        text(
            """INSERT INTO state_credential_records
            (id, state_code, credential_number, credential_type, issuing_state,
            holder_name, holder_address, holder_city, holder_state, holder_zip,
            issue_date, expiration_date, status, external_source_id,
            external_source_url, last_synced_at, sync_version, raw_data,
            created_at, updated_at)
            VALUES
            (:id, :state_code, :credential_number, :credential_type, :issuing_state,
            :holder_name, :holder_address, :holder_city, :holder_state, :holder_zip,
            :issue_date, :expiration_date, :status, :external_source_id,
            :external_source_url, :last_synced_at, :sync_version, :raw_data,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {
            "id": new_id,
            "state_code": state_code,
            "credential_number": cred_num,
            "credential_type": cred_type,
            "issuing_state": state_code,
            "holder_name": rec.get("holder_name", ""),
            "holder_address": rec.get("holder_address"),
            "holder_city": rec.get("holder_city"),
            "holder_state": rec.get("holder_state"),
            "holder_zip": rec.get("holder_zip"),
            "issue_date": rec.get("issue_date"),
            "expiration_date": rec.get("expiration_date"),
            "status": rec.get("status", "active"),
            "external_source_id": rec.get("external_source_id"),
            "external_source_url": rec.get("external_source_url"),
            "last_synced_at": datetime.now(),
            "sync_version": 1,
            "raw_data": json.dumps(rec, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)),
        },
    )
    await db.commit()
    return {"success": True, "existing": False, "id": new_uuid}


# ---------------------------------------------------------------------------
# Legacy wrapper for run_state_credential_sync (backward compatibility with tests)
# ---------------------------------------------------------------------------


async def run_state_credential_sync_legacy(
    state_code: str,
    *,
    triggered_by: str = "schedule",
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Legacy wrapper for run_state_credential_sync.
    
    Provides the old API expected by tests:
    - Accepts state_code as positional argument
    - Creates own DB session if not provided
    - Returns dict summary instead of PipelineRun object
    """
    from app.services.external_compliance_pipeline import run_state_credential_sync as _run_sync
    from app.database import AsyncSessionLocal
    
    if db is None:
        db = AsyncSessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        run = await _run_sync(db=db, state_code=state_code, triggered_by=triggered_by)
        # Treat "skipped" as graceful noop (not an error)
        error = run.error_message if run.status not in ("skipped", "completed") else None
        return {
            "error": error,
            "records_processed": run.records_extracted,
            "records_inserted": run.records_inserted if hasattr(run, 'records_inserted') else 0,
            "records_updated": run.records_updated if hasattr(run, 'records_updated') else 0,
            "records_failed": run.records_failed,
            "status": run.status,
        }
    finally:
        if close_db:
            await db.close()


# Use legacy wrapper as the public API for backward compatibility
run_state_credential_sync = run_state_credential_sync_legacy
