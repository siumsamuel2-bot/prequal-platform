"""Scheduled background jobs for the Prequal alerting and data pipeline system.

Provides APScheduler-based recurring tasks that run independently of the
FastAPI request/response cycle.  This module is designed to be imported by
a small long-running process (or a separate container) managed by DevOps.

Tasks:
- Daily certification expiration scan (default: 01:00 UTC)
- Daily alert delivery (default: 01:30 UTC)
- Daily OSHA sync (default: 02:00 UTC)
- Daily state credential sync (default: 03:00 UTC)
- Daily data quality checks (default: 04:00 UTC)
"""

import os
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from app.database import AsyncSessionLocal
from app.services.alert_service import scan_expirations, deliver_pending_alerts
from app.logging_config import get_logger

logger = get_logger(__name__)

# Alert schedule
SCAN_HOUR = int(os.getenv("ALERT_SCAN_HOUR", "1"))
SCAN_MINUTE = int(os.getenv("ALERT_SCAN_MINUTE", "0"))
DELIVERY_HOUR = int(os.getenv("ALERT_DELIVERY_HOUR", "1"))
DELIVERY_MINUTE = int(os.getenv("ALERT_DELIVERY_MINUTE", "30"))

# Data Pipeline Sync Schedule
OSHA_SYNC_HOUR = int(os.getenv("OSHA_SYNC_HOUR", "2"))
OSHA_SYNC_MINUTE = int(os.getenv("OSHA_SYNC_MINUTE", "0"))
STATE_SYNC_HOUR = int(os.getenv("STATE_SYNC_HOUR", "3"))
STATE_SYNC_MINUTE = int(os.getenv("STATE_SYNC_MINUTE", "0"))
DATA_QUALITY_HOUR = int(os.getenv("DATA_QUALITY_HOUR", "4"))
DATA_QUALITY_MINUTE = int(os.getenv("DATA_QUALITY_MINUTE", "0"))


async def _run_daily_scan() -> None:
    """Execute the expiration scan inside an async DB session."""
    async with AsyncSessionLocal() as db:
        try:
            summary = await scan_expirations(db)
            logger.info(
                "Daily expiration scan complete: "
                f"alerts_created={summary.get('alerts_created')}, "
                f"expired={summary.get('certifications_expired')}, "
                f"w30={summary.get('warnings_30')}, "
                f"w14={summary.get('warnings_14')}, "
                f"w7={summary.get('warnings_7')}."
            )
        except Exception as exc:
            logger.exception("Daily expiration scan failed: %s", exc)


async def _run_daily_delivery() -> None:
    """Execute the alert delivery inside an async DB session."""
    async with AsyncSessionLocal() as db:
        try:
            summary = await deliver_pending_alerts(db)
            logger.info(
                "Daily alert delivery complete: "
                f"processed={summary.get('total_processed')}, "
                f"email={summary.get('sent_email')}, "
                f"sms={summary.get('sent_sms')}, "
                f"failed={summary.get('failed')}"
            )
        except Exception as exc:
            logger.exception("Daily alert delivery failed: %s", exc)


async def _run_osha_sync() -> None:
    """Execute the OSHA daily data sync."""
    try:
        from app.services.external_compliance_pipeline import run_osha_sync
        async with AsyncSessionLocal() as db:
            run = await run_osha_sync(db=db, triggered_by="schedule")
            logger.info(
                "OSHA daily sync complete: "
                f"status={run.status} "
                f"inserted={run.records_inserted} "
                f"updated={run.records_updated} "
                f"failed={run.records_failed}"
            )
    except Exception as exc:
        logger.exception("OSHA daily sync failed: %s", exc)


async def _run_state_credential_sync() -> None:
    """Execute state credential sync for all configured states."""
    try:
        from app.services.external_compliance_pipeline import run_state_credential_sync
        from app.services.state_scrapers.factory import list_supported_states
        states_env = os.getenv("STATE_SYNC_STATES", "CA,TX")
        env_states = [s.strip().upper() for s in states_env.split(",") if s.strip()]
        scraper_states = list_supported_states()
        states = list(dict.fromkeys(env_states + scraper_states))
        for state in states:
            try:
                async with AsyncSessionLocal() as db:
                    run = await run_state_credential_sync(db=db, state_code=state, triggered_by="schedule")
                    logger.info(
                        "State credential sync for %s complete: "
                        f"status={run.status} "
                        f"inserted={run.records_inserted} "
                        f"updated={run.records_updated} "
                        f"failed={run.records_failed}",
                        state,
                    )
            except Exception as exc:
                logger.exception("State credential sync failed for %s: %s", state, exc)
    except Exception as exc:
        logger.exception("State credential sync orchestration failed: %s", exc)


async def _run_data_quality_checks() -> None:
    """Execute data quality validation checks."""
    try:
        from app.services.external_compliance_pipeline import validate_pipeline_health
        async with AsyncSessionLocal() as db:
            checks = await validate_pipeline_health(db)
            logger.info(
                "Data quality checks complete: "
                f"unmatched_osha={checks.get('unmatched_osha_violations')}, "
                f"unmatched_state_creds={checks.get('unmatched_state_credentials')}, "
                f"stale_runs_cleaned={checks.get('stale_runs_cleaned')}, "
                f"stale_running_jobs={checks.get('stale_running_jobs')}, "
                f"failed_jobs_7d={checks.get('failed_jobs_last_7d')}")
    except Exception as exc:
        logger.exception("Data quality checks failed: %s", exc)


def schedule_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all recurring jobs with the provided scheduler."""
    # Alert jobs
    scheduler.add_job(
        _run_daily_scan,
        CronTrigger(hour=SCAN_HOUR, minute=SCAN_MINUTE),
        id="daily_expiration_scan",
        name="Daily certification expiration scan",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily_expiration_scan at %02d:%02d UTC",
        SCAN_HOUR, SCAN_MINUTE,
    )

    scheduler.add_job(
        _run_daily_delivery,
        CronTrigger(hour=DELIVERY_HOUR, minute=DELIVERY_MINUTE),
        id="daily_alert_delivery",
        name="Daily alert delivery (email/SMS)",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily_alert_delivery at %02d:%02d UTC",
        DELIVERY_HOUR, DELIVERY_MINUTE,
    )

    # Data pipeline jobs
    scheduler.add_job(
        _run_osha_sync,
        CronTrigger(hour=OSHA_SYNC_HOUR, minute=OSHA_SYNC_MINUTE),
        id="daily_osha_sync",
        name="Daily OSHA violation data sync",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily_osha_sync at %02d:%02d UTC",
        OSHA_SYNC_HOUR, OSHA_SYNC_MINUTE,
    )

    scheduler.add_job(
        _run_state_credential_sync,
        CronTrigger(hour=STATE_SYNC_HOUR, minute=STATE_SYNC_MINUTE),
        id="daily_state_credential_sync",
        name="Daily state credential verification sync",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily_state_credential_sync at %02d:%02d UTC",
        STATE_SYNC_HOUR, STATE_SYNC_MINUTE,
    )

    scheduler.add_job(
        _run_data_quality_checks,
        CronTrigger(hour=DATA_QUALITY_HOUR, minute=DATA_QUALITY_MINUTE),
        id="daily_data_quality_checks",
        name="Daily data quality and integrity checks",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily_data_quality_checks at %02d:%02d UTC",
        DATA_QUALITY_HOUR, DATA_QUALITY_MINUTE,
    )


# ---------------------------------------------------------------------------
# Entry-point for running the scheduler as a standalone process
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = AsyncIOScheduler()
    schedule_jobs(scheduler)
    scheduler.start()
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
