#!/usr/bin/env python3
"""Run data quality archival process.

Intended to be scheduled daily after the data quality checks complete.
Copies old sync_run_logs and data_quality_results to their archive tables.
Records are NEVER deleted from source tables per the retention policy.

Usage:
    python scripts/run_data_quality_archival.py [--retention-days 90]

Owner: Data Engineer
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, "..")

from app.database import AsyncSessionLocal
from app.services.data_quality_monitoring import (
    archive_old_sync_logs,
    archive_old_data_quality_results,
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data Quality Archival (Non-Destructive)")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=90,
        help="Number of days to retain before copying to archive (default: 90)",
    )
    return parser.parse_args()


async def run_archival(retention_days: int) -> None:
    db = AsyncSessionLocal()
    try:
        logger.info("Starting data quality archival (retention=%s days)", retention_days)

        sync_result = await archive_old_sync_logs(db, retention_days=retention_days)
        logger.info("Archived sync_run_logs: %s", sync_result)

        dqr_result = await archive_old_data_quality_results(db, retention_days=retention_days)
        logger.info("Archived data_quality_results: %s", dqr_result)

        logger.info("Data quality archival complete. Source records are never deleted.")
    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    asyncio.run(run_archival(args.retention_days))
