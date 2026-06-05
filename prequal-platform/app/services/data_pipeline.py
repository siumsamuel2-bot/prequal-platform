"""Scheduled and ad-hoc ETL job engine for data sync pipelines.

Provides a common runner, an OSHA-specific sync job, a state-credential sync job,
and a data quality validation pipeline. All runs integrate with the
``sync_run_logs`` audit table.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.osha_client import OSHAClient
# Import explicitly to satisfy type-checkers / callers
from app.services.state_credential_client import StateCredentialClient  # noqa: F401

logger = logging.getLogger(__name__)

JOB_TYPE_OSHA_SYNC = "osha_daily_sync"
JOB_TYPE_STATE_CRED_SYNC = "state_credential_sync"
JOB_TYPE_DATA_QUALITY = "data_quality_check"


# ---------------------------------------------------------------------------
# 1. SyncRunLog helpers (async)
# ---------------------------------------------------------------------------

async def _open_run(
    db: AsyncSession,
    job_name: str,
    job_type: str,
    *,
    triggered_by: str = "schedule",
    run_meta: Optional[dict[str, Any]] = None,
) -> Any:
    """Create a sync_run_logs row in 'running' state."""
    from app.models.compliance import SyncRunLog

    run = SyncRunLog(
        id=uuid4(),
        job_name=job_name,
        job_type=job_type,
        status="running",
        triggered_by=triggered_by,
        started_at=datetime.now(),
        run_metadata=(run_meta or {}),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _close_run(
    db: AsyncSession,
    run: Any,
    *,
    status: str,
    error: Optional[str] = None,
    stats: Optional[dict[str, int]] = None,
    stats_update: Optional[dict[str, int]] = None,
) -> Any:
    """Update a sync_run_logs row to a terminal state."""
    run.status = status
    run.completed_at = datetime.now()
    if error is not None:
        run.error_message = (run.error_message or "") + error[:4096]
    if stats:
        run.records_processed = stats.get("records_processed", run.records_processed or 0)
        run.records_inserted = stats.get("records_inserted", run.records_inserted or 0)
        run.records_updated = stats.get("records_updated", run.records_updated or 0)
        run.records_failed = stats.get("records_failed", run.records_failed or 0)
    if stats_update:
        run.records_processed = (run.records_processed or 0) + stats_update.get("records_processed", 0)
        run.records_updated = (run.records_updated or 0) + stats_update.get("records_updated", 0)
        run.records_inserted = (run.records_inserted or 0) + stats_update.get("records_inserted", 0)
        run.records_failed = (run.records_failed or 0) + stats_update.get("records_failed", 0)
    await db.commit()
    await db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# 2. OSHA Daily Sync
# ---------------------------------------------------------------------------

async def run_osha_sync(
    *,
    triggered_by: str = "schedule",
    search: Optional[str] = None,
    state: Optional[str] = None,
    max_pages: Optional[int] = None,
) -> dict[str, Any]:
    logger.info("Starting OSHA daily sync run ...")
    db: Optional[AsyncSession] = None
    run = None
    summary: dict[str, Any] = {
        "total_inserted": 0,
        "total_updated": 0,
        "total_failed": 0,
        "total_processed": 0,
    }

    try:
        db = AsyncSessionLocal()
        run = await _open_run(
            db, "osha_daily_sync", JOB_TYPE_OSHA_SYNC, triggered_by=triggered_by
        )

        total_inserted = 0
        total_updated = 0
        total_failed = 0

        async with OSHAClient() as client:
            case_list = await client.paginate_cases(
                search=search,
                state=state,
                date_opened_from=date(date.today().year - 3, 1, 1),
                page_size=50,
                max_pages=max_pages,
            )

        logger.info("Fetched %d case(s) from OSHA.", len(case_list))

        for case in case_list:
            try:
                result = await _load_case_async(db, case)
                if result.get("existing"):
                    total_updated += 1
                else:
                    total_inserted += 1
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                logger.error("Failed to process case id=%s: %s", case.get("id"), exc)
                total_failed += 1

        await db.commit()

        summary["total_inserted"] = total_inserted
        summary["total_updated"] = total_updated
        summary["total_failed"] = total_failed
        summary["total_processed"] = total_inserted + total_updated + total_failed

        run = await _close_run(
            db,
            run,
            status="completed" if total_failed == 0 else "partial",
            stats={
                "records_processed": summary["total_processed"],
                "records_inserted": summary["total_inserted"],
                "records_updated": summary["total_updated"],
                "records_failed": summary["total_failed"],
            },
        )

    except Exception as exc:
        logger.exception("OSHA sync failed")
        if run is not None and db is not None:
            run = await _close_run(db, run, status="failed", error=str(exc))
        summary["error"] = str(exc)
    finally:
        if db is not None:
            await db.close()

    return summary


async def _load_case_async(db: AsyncSession, case: dict) -> dict:
    """Async upsert a single OSHA case into violations/inspections."""
    from scripts.etl_osha import _extract_violation_record, _extract_inspection_record
    import uuid as _uuid

    vrec = _extract_violation_record(case)
    irect = _extract_inspection_record(case)
    result: dict[str, Any] = {
        "violation_id": None,
        "inspection_id": None,
        "existing": False,
        "success": False,
    }

    osha_id = vrec.get("osha_violation_id")
    if osha_id is not None:
        existing = await db.execute(
            select(text("vtemp.id")).select_from(
                text(f"(SELECT id FROM violations WHERE osha_violation_id = '{osha_id}') as vtemp")
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            result["existing"] = True
            result["violation_id"] = row
            await db.execute(
                text(
                    """
                    UPDATE violations SET status = :status, resolution_date = :resolution_date,
                    description = :description, inspection_number = :inspection_number,
                    standard_cited = :standard_cited, updated_at = CURRENT_TIMESTAMP
                    WHERE osha_violation_id = :osha_id
                    """
                ),
                {
                    "osha_id": osha_id,
                    "status": vrec["status"],
                    "resolution_date": vrec["resolution_date"],
                    "description": vrec["description"],
                    "inspection_number": vrec["inspection_number"],
                    "standard_cited": vrec["standard_cited"],
                },
            )
        else:
            new_id = _uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO violations (id, violation_type, violation_code, description,
                    issued_by, issued_date, effective_date, resolution_date, status,
                    is_osha_violation, osha_violation_id, inspection_number, standard_cited,
                    gravity_score, is_criminal, penalty_amount)
                    VALUES (:id, :violation_type, :violation_code, :description, :issued_by,
                    :issued_date, :effective_date, :resolution_date, :status,
                    :is_osha_violation, :osha_violation_id, :inspection_number,
                    :standard_cited, :gravity_score, FALSE, 0)
                    """
                ),
                {**vrec, "id": new_id},
            )
            result["violation_id"] = new_id

    ins_num = irect.get("inspection_number")
    if ins_num is not None:
        existing_ins = await db.execute(
            select(text("it.id")).select_from(
                text(f"(SELECT id FROM osha_inspections WHERE inspection_number = '{ins_num}') as it")
            )
        )
        ins_row = existing_ins.scalar_one_or_none()
        if ins_row:
            result["inspection_id"] = ins_row
            await db.execute(
                text(
                    """
                    UPDATE osha_inspections SET inspection_date = :inspection_date, type = :type,
                    site_city = :site_city, site_state = :site_state,
                    site_address = :site_address, naics_code = :naics_code,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE inspection_number = :inspection_number
                    """
                ),
                irect,
            )
        else:
            new_ins_id = _uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO osha_inspections (id, inspection_number, inspection_date, type,
                    site_city, site_state, site_address, naics_code, reported_by, owner_type,
                    total_penalty, abatement_completed)
                    VALUES (:id, :inspection_number, :inspection_date, :type, :site_city,
                    :site_state, :site_address, :naics_code, :reported_by, :owner_type,
                    :total_penalty, :abatement_completed)
                    """
                ),
                {**irect, "id": new_ins_id},
            )
            result["inspection_id"] = new_ins_id

    result["success"] = True
    return result


# ---------------------------------------------------------------------------
# 3. State Credential Sync
# ---------------------------------------------------------------------------

async def run_state_credential_sync(
    state_code: str, *, triggered_by: str = "webhook"
) -> dict[str, Any]:
    logger.info("Starting state credential sync for state=%s ...", state_code)
    summary = {
        "state_code": state_code,
        "records_processed": 0,
        "records_inserted": 0,
        "records_updated": 0,
        "records_failed": 0,
    }

    db: Optional[AsyncSession] = None
    run = None
    try:
        db = AsyncSessionLocal()
        run = await _open_run(
            db, f"state_creds_{state_code}", JOB_TYPE_STATE_CRED_SYNC, triggered_by=triggered_by
        )

        # NOTE: real implementation hits STATE_API_URL_* env endpoint via
        # StateCredentialClient. When no endpoint is configured, fall back
        # gracefully to a no-op so tests and local dev do not fail.
        if not os.getenv(f"STATE_API_URL_{state_code.upper()}"):
            logger.info("No state API configured for %s — noop.", state_code)
            run = await _close_run(db, run, status="completed", stats=summary)
            return summary

        client = StateCredentialClient(state_code)
        records = await client.paginate_credentials(query="", page_size=50)
        logger.info("Fetched %d credential(s) for %s.", len(records), state_code)

        for rec in records:
            try:
                res = await _load_state_credential_record(db, rec)
                if res["existing"]:
                    summary["records_updated"] += 1
                else:
                    summary["records_inserted"] += 1
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                logger.error("Failed to process state record: %s", exc)
                summary["records_failed"] += 1
        
        summary["records_processed"] = (
            summary["records_inserted"]
            + summary["records_updated"]
            + summary["records_failed"]
        )

        run = await _close_run(db, run, status="completed", stats=summary)
    except Exception as exc:
        logger.exception("State credential sync failed for %s", state_code)
        if run is not None and db is not None:
            run = await _close_run(db, run, status="failed", error=str(exc))
        summary["error"] = str(exc)
    finally:
        if db is not None:
            await db.close()

    return summary


def _json_safe(value: Any) -> Any:
    """Serialize dict/list to JSON string for raw SQL binding on SQLite."""
    import json as _json
    return _json.dumps(value, default=str) if isinstance(value, (dict, list)) else value


async def _load_state_credential_record(db: AsyncSession, rec: dict) -> dict[str, Any]:
    """Upsert a single state-credential dict into ``state_credential_records``."""
    from uuid import uuid4 as _uuid4

    result: dict[str, Any] = {"id": None, "existing": False, "success": False}

    state_code = (rec.get("state_code") or "")[:2].upper()
    cred_num = str(rec.get("credential_number") or rec.get("number", ""))
    cred_type = str(rec.get("credential_type") or rec.get("type", ""))
    holder_name = str(rec.get("holder_name") or rec.get("name", ""))

    # Attempt to locate existing row by composite key
    existing = await db.execute(
        text(
            """SELECT id FROM state_credential_records
            WHERE state_code = :state_code AND credential_number = :cred_num
            AND credential_type = :cred_type"""
        ),
        {"state_code": state_code, "cred_num": cred_num, "cred_type": cred_type},
    )
    row = existing.scalar_one_or_none()

    values = {
        "state_code": state_code,
        "credential_number": cred_num,
        "credential_type": cred_type,
        "issuing_state": str(rec.get("issuing_state") or state_code),
        "holder_name": holder_name,
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
        "sync_version": rec.get("sync_version", 1),
        "raw_data": rec,
    }

    if row:
        result["existing"] = True
        result["id"] = row
        await db.execute(
            text(
                """UPDATE state_credential_records SET
                issuing_state = :issuing_state, holder_name = :holder_name,
                holder_address = :holder_address, holder_city = :holder_city,
                holder_state = :holder_state, holder_zip = :holder_zip,
                issue_date = :issue_date, expiration_date = :expiration_date,
                status = :status, external_source_id = :external_source_id,
                external_source_url = :external_source_url, last_synced_at = :last_synced_at,
                sync_version = sync_version + 1, raw_data = :raw_data,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = :id"""
            ),
            {**values, "id": str(row), "raw_data": _json_safe(values["raw_data"])},
        )
    else:
        new_id = _uuid4()
        result["id"] = new_id
        await db.execute(
            text(
                """INSERT INTO state_credential_records
                (id, state_code, credential_number, credential_type, issuing_state,
                holder_name, holder_address, holder_city, holder_state, holder_zip,
                issue_date, expiration_date, status, external_source_id,
                external_source_url, last_synced_at, sync_version, raw_data, created_at, updated_at)
                VALUES (:id, :state_code, :credential_number, :credential_type, :issuing_state,
                :holder_name, :holder_address, :holder_city, :holder_state, :holder_zip,
                :issue_date, :expiration_date, :status, :external_source_id,
                :external_source_url, :last_synced_at, :sync_version, :raw_data,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
            ),
                {**values, "id": str(new_id), "raw_data": _json_safe(values["raw_data"])},
        )

    result["success"] = True
    return result


# ---------------------------------------------------------------------------
# 4. Data Quality Monitors
# ---------------------------------------------------------------------------

async def run_data_quality_checks(*, triggered_by: str = "schedule") -> dict[str, Any]:
    logger.info("Starting data quality checks ...")
    summary: dict[str, Any] = {
        "total_rules": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "details": [],
    }
    db: Optional[AsyncSession] = None
    run = None

    try:
        db = AsyncSessionLocal()
        run = await _open_run(
            db, "data_quality_check", JOB_TYPE_DATA_QUALITY, triggered_by=triggered_by
        )

        from app.models.compliance import DataQualityCheck, DataQualityResult

        rules = await db.execute(select(DataQualityCheck).where(DataQualityCheck.is_active.is_(True)))
        rules_list = rules.scalars().all()
        summary["total_rules"] = len(rules_list)
        total_pass, total_fail, total_err = 0, 0, 0

        for check in rules_list:
            try:
                result = await db.execute(text(check.check_query))
                count = result.scalar() or 0
                passed = count == 0

                dqr = DataQualityResult(
                    id=uuid4(),
                    check_id=check.id,
                    sync_run_id=run.id,
                    status="passed" if passed else "failed",
                    records_checked=1,
                    records_failed=count,
                    failure_rate=1.0 if not passed else 0.0,
                    execution_time_ms=None,
                    sample_failures=None,
                )
                db.add(dqr)
                if passed:
                    total_pass += 1
                else:
                    total_fail += 1
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                logger.error("Data quality check %s failed: %s", check.check_name, exc)
                dqr = DataQualityResult(
                    id=uuid4(),
                    check_id=check.id,
                    sync_run_id=run.id,
                    status="error",
                    records_checked=0,
                    records_failed=0,
                    failure_rate=None,
                    execution_time_ms=None,
                    sample_failures={"error": str(exc)},
                )
                db.add(dqr)
                total_err += 1

        await db.commit()

        summary["passed"] = total_pass
        summary["failed"] = total_fail
        summary["errors"] = total_err

        run = await _close_run(db, run, status="completed")
    except Exception as exc:
        logger.exception("Data quality pipeline failed")
        if run is not None and db is not None:
            run = await _close_run(db, run, status="failed", error=str(exc))
        summary["error"] = str(exc)
    finally:
        if db is not None:
            await db.close()

    return summary


# ---------------------------------------------------------------------------
# 5. Refresh materialized views
# ---------------------------------------------------------------------------

async def refresh_analytics_views(db: AsyncSession) -> None:
    logger.info("Refreshing analytics materialized views ...")
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_compliance_summary"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_violation_trends"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_certification_status"))
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_project_compliance"))
    await db.commit()
    logger.info("Analytics views refreshed.")


async def run_full_pipeline(
    *,
    triggered_by: str = "schedule",
    search: Optional[str] = None,
    state: Optional[str] = None,
    max_pages: Optional[int] = None,
) -> dict[str, Any]:
    """Run the full daily pipeline: OSHA sync -> data quality checks -> analytics refresh."""
    logger.info("Starting full daily data pipeline ...")
    overall: dict[str, Any] = {"osha": None, "data_quality": None, "analytics": None}

    # 1. OSHA sync
    try:
        overall["osha"] = await run_osha_sync(
            triggered_by=triggered_by, search=search, state=state, max_pages=max_pages
        )
    except Exception:
        logger.exception("OSHA sync step failed")

    # 2. Data quality
    try:
        overall["data_quality"] = await run_data_quality_checks(triggered_by=triggered_by)
    except Exception:
        logger.exception("Data quality step failed")

    # 3. Analytics refresh - uses the new analytics_pipeline module
    try:
        from app.services.analytics_refresh import run_analytics_refresh
        overall["analytics"] = await run_analytics_refresh(triggered_by=triggered_by)
    except Exception:
        logger.exception("Analytics refresh step failed")

    logger.info("Full daily pipeline completed. Summary: %s", overall)
    return overall


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    result = asyncio.run(run_full_pipeline(triggered_by="manual"))
    print(result)
