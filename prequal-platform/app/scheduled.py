"""Scheduled background jobs for the Prequal alerting system.

Provides APScheduler-based recurring tasks that run independently of the
FastAPI request/response cycle.  This module is designed to be imported by
a small long-running process (or a separate container) managed by DevOps.

Example usage (run by DevOps via entrypoint script or container CMD):
    python -m app.scheduled

Tasks:
- Daily certification expiration scan (default: 01:00 UTC)
- Daily alert delivery (default: 01:30 UTC)
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

SCAN_HOUR = int(os.getenv("ALERT_SCAN_HOUR", "1"))
SCAN_MINUTE = int(os.getenv("ALERT_SCAN_MINUTE", "0"))
DELIVERY_HOUR = int(os.getenv("ALERT_DELIVERY_HOUR", "1"))
DELIVERY_MINUTE = int(os.getenv("ALERT_DELIVERY_MINUTE", "30"))


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
                f"w7={summary.get('warnings_7')}"
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


def schedule_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all recurring jobs with the provided scheduler."""
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
