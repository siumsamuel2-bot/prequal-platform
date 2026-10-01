"""Daily External Compliance Sync Runner

Runs the full external compliance data pipeline (OSHA + state credentials)
on a scheduled basis with error tracking and notification.

Usage:
    python scripts/run_daily_sync.py [--notify devops@example.com]

Environment:
    DATABASE_URL                PostgreSQL connection string
    OSHA_MAX_PAGES              Max OSHA pagination pages (default 10)
    STATE_MAX_PAGES             Max state pagination pages (default 5)
    STATE_SYNC_STATES           Comma-separated state codes (default CA,TX)
    NOTIFY_EMAIL                Email address for failure alerts
    LOG_LEVEL                   Logging level (default INFO)

This script is designed to be invoked by the APScheduler in app/scheduled.py
or by a DevOps-managed cron job / systemd timer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Ensure imports work when run from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import AsyncSessionLocal
from app.services.external_compliance_pipeline import (
    run_osha_sync,
    run_state_credential_sync,
    validate_pipeline_health,
    refresh_analytics_views,
    get_pipeline_health_summary,
    PipelineRun,
)

logger = logging.getLogger(__name__)

DEFAULT_NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")
STATE_SYNC_STATES = os.getenv("STATE_SYNC_STATES", "CA,TX")


async def _notify_failure(
    *,
    job_name: str,
    job_type: str,
    error_message: str,
    run_metadata: Dict[str, Any],
    db_session=None,
) -> None:
    """Log a pipeline error notification. If email is configured, queue it."""
    recipient = DEFAULT_NOTIFY_EMAIL
    severity = "critical" if "failed" in str(run_metadata.get("status", "")).lower() else "warning"

    notification = {
        "id": str(uuid.uuid4()),
        "job_name": job_name,
        "job_type": job_type,
        "severity": severity,
        "message": error_message[:4096],
        "recipient": recipient,
        "status": "pending",
        "error_details": json.dumps(run_metadata),
        "created_at": datetime.now().isoformat(),
    }

    if db_session is not None:
        from sqlalchemy import text
        await db_session.execute(
            text(
                """INSERT INTO pipeline_error_notifications
                (id, job_name, job_type, severity, message, recipient, status, error_details, created_at)
                VALUES (:id, :job_name, :job_type, :severity, :message, :recipient, :status, :error_details, :created_at)
                """
            ),
            notification,
        )
        await db_session.commit()

    if recipient:
        logger.warning(
            "Pipeline failure notification queued for %s: %s — %s",
            recipient, job_name, error_message,
        )
    else:
        logger.warning(
            "No NOTIFY_EMAIL configured; pipeline failure logged locally only. "
            "Job: %s — Error: %s", job_name, error_message,
        )


async def run_daily_sync(
    *,
    notify_email: Optional[str] = None,
    state_codes: Optional[List[str]] = None,
    max_osha_pages: int = 20,
    max_state_pages: int = 10,
) -> Dict[str, Any]:
    """Run the full daily external compliance sync pipeline.

    Steps:
        1. OSHA violation sync
        2. State credential sync (for each configured state)
        3. Data quality validation
        4. Analytics view refresh
        5. Error notification if any step fails
    """
    results: Dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "osha": None,
        "state_credentials": [],
        "data_quality": None,
        "analytics_refresh": None,
        "status": "running",
    }
    all_success = True

    async with AsyncSessionLocal() as db:
        # ------------------------------------------------------------------
        # 1. OSHA Sync
        # ------------------------------------------------------------------
        try:
            osha_run = await run_osha_sync(
                db=db,
                max_pages=max_osha_pages,
                triggered_by="schedule",
            )
            results["osha"] = {
                "run_id": str(osha_run.id),
                "status": osha_run.status,
                "extracted": osha_run.records_extracted,
                "inserted": osha_run.records_inserted,
                "updated": osha_run.records_updated,
                "failed": osha_run.records_failed,
                "matched": osha_run.records_matched,
            }
            if osha_run.status not in ("completed", "partial"):
                all_success = False
                await _notify_failure(
                    job_name="osha_daily_sync",
                    job_type="osha_sync",
                    error_message=osha_run.error_message or "OSHA sync returned non-success status",
                    run_metadata=results["osha"],
                    db_session=db,
                )
        except Exception as exc:
            logger.exception("OSHA sync step failed")
            all_success = False
            results["osha"] = {"status": "failed", "error": str(exc)}
            await _notify_failure(
                job_name="osha_daily_sync",
                job_type="osha_sync",
                error_message=str(exc),
                run_metadata=results["osha"],
                db_session=db,
            )

        # ------------------------------------------------------------------
        # 2. State Credential Sync
        # ------------------------------------------------------------------
        if not state_codes:
            state_codes = [s.strip().upper() for s in STATE_SYNC_STATES.split(",") if s.strip()]

        for sc in state_codes:
            try:
                sc_run = await run_state_credential_sync(
                    db=db, state_code=sc, triggered_by="schedule"
                )
                sc_result = {
                    "state": sc,
                    "run_id": str(sc_run.id),
                    "status": sc_run.status,
                    "extracted": sc_run.records_extracted,
                    "inserted": sc_run.records_inserted,
                    "updated": sc_run.records_updated,
                    "failed": sc_run.records_failed,
                    "matched": sc_run.records_matched,
                }
                results["state_credentials"].append(sc_result)
                if sc_run.status not in ("completed", "partial", "skipped"):
                    all_success = False
                    await _notify_failure(
                        job_name=f"state_creds_{sc}",
                        job_type="state_credential_sync",
                        error_message=sc_run.error_message or f"State {sc} sync failed",
                        run_metadata=sc_result,
                        db_session=db,
                    )
            except Exception as exc:
                logger.exception("State credential sync failed for %s", sc)
                all_success = False
                sc_result = {"state": sc, "status": "failed", "error": str(exc)}
                results["state_credentials"].append(sc_result)
                await _notify_failure(
                    job_name=f"state_creds_{sc}",
                    job_type="state_credential_sync",
                    error_message=str(exc),
                    run_metadata=sc_result,
                    db_session=db,
                )

        # ------------------------------------------------------------------
        # 3. Data Quality Validation
        # ------------------------------------------------------------------
        try:
            checks = await validate_pipeline_health(db)
            results["data_quality"] = checks
            logger.info("Data quality checks: %s", checks)
        except Exception as exc:
            logger.exception("Data quality checks failed")
            all_success = False
            results["data_quality"] = {"status": "failed", "error": str(exc)}
            await _notify_failure(
                job_name="data_quality_checks",
                job_type="validation",
                error_message=str(exc),
                run_metadata=results["data_quality"],
                db_session=db,
            )

        # ------------------------------------------------------------------
        # 4. Analytics View Refresh
        # ------------------------------------------------------------------
        try:
            await refresh_analytics_views(db)
            results["analytics_refresh"] = {"status": "completed"}
            logger.info("Analytics views refreshed successfully")
        except Exception as exc:
            logger.exception("Analytics view refresh failed")
            all_success = False
            results["analytics_refresh"] = {"status": "failed", "error": str(exc)}
            await _notify_failure(
                job_name="analytics_refresh",
                job_type="analytics",
                error_message=str(exc),
                run_metadata=results["analytics_refresh"],
                db_session=db,
            )

    # ------------------------------------------------------------------
    # 5. Pipeline Health Summary
    # ------------------------------------------------------------------
    try:
        results["pipeline_health"] = await get_pipeline_health_summary(db)
    except Exception as exc:
        logger.exception("Pipeline health summary failed")
        results["pipeline_health"] = {"status": "failed", "error": str(exc)}

    results["completed_at"] = datetime.now().isoformat()
    results["status"] = "completed" if all_success else "partial" if any(
        r.get("status") not in ("failed",) for r in [results.get("osha", {})] + results.get("state_credentials", [])
    ) else "failed"

    logger.info("Daily sync complete: %s", results["status"])
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily External Compliance Sync Runner")
    parser.add_argument("--notify", default=DEFAULT_NOTIFY_EMAIL, help="Email for failure alerts")
    parser.add_argument("--states", default=STATE_SYNC_STATES, help="Comma-separated state codes")
    parser.add_argument("--max-osha-pages", type=int, default=20, help="Max OSHA pagination pages")
    parser.add_argument("--max-state-pages", type=int, default=10, help="Max state pagination pages")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    state_codes = [s.strip().upper() for s in args.states.split(",") if s.strip()]

    result = asyncio.run(
        run_daily_sync(
            notify_email=args.notify or None,
            state_codes=state_codes,
            max_osha_pages=args.max_osha_pages,
            max_state_pages=args.max_state_pages,
        )
    )
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
