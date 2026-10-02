"""Analytics reporting endpoints (feature adoption, health, reports, pilot engagement, anomalies)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.anomaly_detection import UsageAnomalyDetector
from app.services.ingestion import AnalyticsIngestionService
from app.services.org_directory import get_organization_name
from app.services.reporting import (
    WeeklyReport,
    get_daily_active_users,
    get_feature_adoption_summary,
    get_pilot_engagement_metrics,
    get_system_health_summary,
)
from app.services.service_auth import UserContext, get_user_context, require_admin_context

router = APIRouter()


@router.get("/feature-adoption")
def feature_adoption(
    feature_name: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Get feature adoption summary for the dashboard."""
    require_admin_context(context)
    return get_feature_adoption_summary(db, feature_name=feature_name, days=days)


@router.get("/daily-active-users")
def daily_active_users(
    days: int = Query(default=30, ge=1, le=365),
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Return daily active user counts."""
    require_admin_context(context)
    return get_daily_active_users(db, days=days)


@router.get("/system-health")
def system_health(
    hours: int = Query(default=24, ge=1, le=720),
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Get system health summary for the given period."""
    require_admin_context(context)
    return get_system_health_summary(db, hours=hours)


@router.get("/weekly-report")
def weekly_report(
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Generate and return the weekly analytics report."""
    require_admin_context(context)
    return WeeklyReport(db).generate()


@router.get("/anomalies")
def anomalies(
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Run all anomaly detection checks and return flagged items."""
    require_admin_context(context)
    detector = UsageAnomalyDetector(db)
    anomaly_list = detector.run_all_checks()
    return {
        "anomalies": [
            {
                "type": a.anomaly_type,
                "severity": a.severity,
                "feature": a.feature,
                "message": a.message,
                "detected_at": a.detected_at.isoformat(),
                "metric_value": a.metric_value,
                "expected_range": a.expected_range,
            }
            for a in anomaly_list
        ],
        "total": len(anomaly_list),
    }


@router.get("/pilot-engagement")
def pilot_engagement(
    days: int = Query(default=30, ge=1, le=365),
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Get aggregated pilot customer engagement metrics for internal monitoring."""
    require_admin_context(context)
    return get_pilot_engagement_metrics(db, days=days, org_directory=get_organization_name)
