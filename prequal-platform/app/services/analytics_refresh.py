"""Scheduled analytics refresh pipeline.

Runs after the main ETL pipeline to keep dashboard materialized views fresh.
Can be triggered via the data pipeline scheduler or run ad-hoc.

Owner: Data Engineer
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.analytics_pipeline import refresh_all_analytics_views

logger = logging.getLogger(__name__)

JOB_TYPE_ANALYTICS_REFRESH = "analytics_refresh"


async def run_analytics_refresh(
    *,
    triggered_by: str = "schedule",
    stats: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Refresh all analytics materialized views.

    Typically called at the end of the daily ETL pipeline (data_pipeline.run_full_pipeline).
    Returns a summary of what was refreshed.
    """
    from uuid import uuid4

    from app.models.compliance import SyncRunLog

    summary: dict[str, Any] = {
        "status": "completed",
        "views_refreshed": [],
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    try:
        db = AsyncSessionLocal()
        logger.info("Starting analytics refresh pipeline ...")

        # Open a run log entry for traceability
        run = SyncRunLog(
            id=uuid4(),
            job_name="analytics_refresh",
            job_type=JOB_TYPE_ANALYTICS_REFRESH,
            status="running",
            triggered_by=triggered_by,
            started_at=datetime.now(),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        summary["started_at"] = run.started_at.isoformat()

        # Refresh all analytics views
        try:
            await refresh_all_analytics_views(db)
            summary["views_refreshed"] = [
                "mv_compliance_summary",
                "mv_compliance_trends",
                "mv_certification_status",
                "mv_project_compliance",
                "mv_recent_alerts",
            ]
        except Exception as exc:
            logger.exception("Analytics view refresh failed")
            summary["error"] = str(exc)
            run.status = "failed"
            run.error_message = str(exc)[:4096]
            run.completed_at = datetime.now()
            await db.commit()
            return summary

        # Update run log to completed
        run.status = "completed"
        run.completed_at = datetime.now()
        await db.commit()
        summary["completed_at"] = run.completed_at.isoformat()
        logger.info("Analytics refresh pipeline completed successfully.")

    except Exception as exc:
        logger.exception("Analytics refresh pipeline failed")
        summary["error"] = str(exc)
    finally:
        await db.close()

    return summary
