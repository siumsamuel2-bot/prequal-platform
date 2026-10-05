"""Data quality monitoring endpoints for the analytics service (MID-626).

Endpoints:
- GET  /analytics/quality/health  — run all checks without persisting (read-only)
- GET  /analytics/quality/alerts   — recent persisted data-quality alerts
- POST /analytics/quality/run-checks — run checks, persist alerts, archive old rows
- POST /analytics/quality/archive  — apply retention/archival policy

Writes and scheduled actions require service auth; health/metrics reads also
require service auth (fail-closed; see service_auth).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import data_quality
from app.services.service_auth import require_service_auth

router = APIRouter()


@router.get("/quality/health")
def quality_health(
    sla_hours: int = Query(default=24, ge=1, le=720),
    _: None = Depends(require_service_auth),
    db: Session = Depends(get_db),
):
    """Run all data-quality checks (no persistence). Read-only health probe."""
    return data_quality.run_data_quality_check(db, persist=False)


@router.get("/quality/alerts")
def quality_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Depends(require_service_auth),
    db: Session = Depends(get_db),
):
    """List recent persisted data-quality alerts (internal records only)."""
    return {"alerts": data_quality.list_recent_quality_alerts(db, limit=limit)}


@router.post("/quality/run-checks")
def quality_run_checks(
    _: None = Depends(require_service_auth),
    db: Session = Depends(get_db),
):
    """Run all checks and persist any triggered alerts.

    Intended to be invoked by the service scheduler or the monolith's
    daily data-quality job. Never deletes data.
    """
    return data_quality.run_data_quality_check(db, persist=True)


@router.post("/quality/archive")
def quality_archive(
    retention_days: int = Query(default=90, ge=7, le=3650),
    _: None = Depends(require_service_auth),
    db: Session = Depends(get_db),
):
    """Apply the retention policy: archive rows older than retention_days.

    Insert-only into archive tables; source rows are never deleted.
    """
    return {
        "analytics_events": data_quality.archive_old_analytics_events(db, retention_days),
        "feature_usage_events": data_quality.archive_old_feature_events(db, retention_days),
    }
