"""Verify and unblock stale sync runs.

This script checks for sync runs that are stuck in 'running' status
(typically due to runtime adapter issues) and marks them as failed
so the pipeline can proceed.

Usage:
    python scripts/clear_stale_runs.py [--dry-run]

Environment:
    DATABASE_URL    PostgreSQL connection string
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import AsyncSessionLocal
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STALE_RUN_TIMEOUT_HOURS = int(os.getenv("STALE_RUN_TIMEOUT_HOURS", "2"))


async def clear_stale_runs(dry_run: bool = True) -> dict:
    """Find and clear stale sync runs.

    Args:
        dry_run: If True, only report what would be done without making changes.

    Returns:
        Summary of stale runs found and cleared.
    """
    result = {
        "dry_run": dry_run,
        "stale_run_timeout_hours": STALE_RUN_TIMEOUT_HOURS,
        "stale_runs_found": 0,
        "stale_runs_cleared": 0,
        "errors": [],
    }

    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=STALE_RUN_TIMEOUT_HOURS)

        query = text(
            """
            SELECT id, job_name, job_type, started_at, status
            FROM sync_run_logs
            WHERE status = 'running' AND started_at < :cutoff
            """
        )
        stale_runs = await db.execute(query, {"cutoff": cutoff})
        rows = stale_runs.fetchall()

        result["stale_runs_found"] = len(rows)

        if not rows:
            logger.info("No stale sync runs found")
            return result

        logger.info("Found %d stale sync runs", len(rows))
        for row in rows:
            logger.info(
                "  - Run %s: job=%s type=%s started=%s status=%s",
                row.id, row.job_name, row.job_type, row.started_at, row.status
            )

        if dry_run:
            logger.info("[DRY RUN] Would clear %d stale runs", len(rows))
            return result

        update_query = text(
            """
            UPDATE sync_run_logs
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error_message = 'Automatically cleared: run exceeded :timeout_hours-hour timeout and appeared to be stuck.'
            WHERE status = 'running' AND started_at < :cutoff
            RETURNING id
            """
        )
        update_result = await db.execute(
            update_query,
            {"cutoff": cutoff, "timeout_hours": STALE_RUN_TIMEOUT_HOURS}
        )
        cleared = update_result.fetchall()
        result["stale_runs_cleared"] = len(cleared)

        await db.commit()
        logger.info("Cleared %d stale sync runs", len(cleared))

    return result


async def check_adapter_health() -> dict:
    """Verify the state scraper adapters are configured and can be instantiated.

    Returns:
        Health status of each configured scraper.
    """
    from app.services.state_scrapers.factory import list_supported_states, get_scraper

    result = {
        "supported_states": list_supported_states(),
        "scrapers": {},
    }

    for state_code in result["supported_states"]:
        scraper = get_scraper(state_code)
        result["scrapers"][state_code] = {
            "configured": scraper is not None,
            "class": type(scraper).__name__ if scraper else None,
        }

    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clear stale sync runs and verify adapter health")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Only report what would be done (default: True)")
    parser.add_argument("--execute", action="store_false", dest="dry_run",
                        help="Actually clear stale runs (default: dry-run mode)")
    parser.add_argument("--check-adapters", action="store_true",
                        help="Check adapter health status")
    args = parser.parse_args()

    if args.check_adapters:
        health = await check_adapter_health()
        print("Adapter Health:")
        print(f"  Supported states: {health['supported_states']}")
        for state, info in health["scrapers"].items():
            print(f"  {state}: configured={info['configured']} class={info['class']}")

    if args.dry_run:
        print("Running in DRY-RUN mode. Use --execute to actually clear runs.")

    result = await clear_stale_runs(dry_run=args.dry_run)
    print(f"\nResult: {result['stale_runs_found']} stale runs found, "
          f"{result['stale_runs_cleared']} cleared")


if __name__ == "__main__":
    asyncio.run(main())