"""Analytics reporting service.

Generates feature adoption, system health, and pilot engagement reports.
Queries are written against the analytics service's own database using
SQLAlchemy expressions with Python-computed cutoffs for portability.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import func, distinct, case
from sqlalchemy.orm import Session

from app.models.models import AnalyticsEvent, FeatureUsageEvent, SystemHealthMetric
from app.services.ingestion import FEATURE_NAMES

logger = logging.getLogger(__name__)


def get_daily_active_users(db: Session, days: int = 30) -> List[Dict[str, Any]]:
    """Return daily active user counts for the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(FeatureUsageEvent.created_at).label("day"),
            func.count(distinct(FeatureUsageEvent.user_id)).label("active_users"),
        )
        .filter(FeatureUsageEvent.created_at >= cutoff)
        .group_by(func.date(FeatureUsageEvent.created_at))
        .order_by(func.date(FeatureUsageEvent.created_at).desc())
        .all()
    )
    return [{"day": str(row.day), "active_users": row.active_users} for row in rows]


def get_feature_adoption_summary(
    db: Session,
    feature_name: Optional[str] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Get feature adoption summary for dashboard display."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = db.query(
        FeatureUsageEvent.feature_name,
        FeatureUsageEvent.event_type,
        func.count(FeatureUsageEvent.id).label("event_count"),
        func.count(distinct(FeatureUsageEvent.user_id)).label("unique_users"),
    ).filter(FeatureUsageEvent.created_at >= cutoff)
    if feature_name:
        query = query.filter(FeatureUsageEvent.feature_name == feature_name)
    rows = query.group_by(FeatureUsageEvent.feature_name, FeatureUsageEvent.event_type).order_by(
        FeatureUsageEvent.feature_name, func.count(FeatureUsageEvent.id).desc()
    ).all()
    return [
        {
            "feature_name": row.feature_name,
            "event_type": row.event_type,
            "event_count": row.event_count,
            "unique_users": row.unique_users,
        }
        for row in rows
    ]


def get_system_health_summary(
    db: Session,
    hours: int = 24,
) -> List[Dict[str, Any]]:
    """Get system health summary for the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(
            SystemHealthMetric.service_name,
            SystemHealthMetric.metric_name,
            SystemHealthMetric.metric_unit,
            func.avg(SystemHealthMetric.metric_value).label("avg_value"),
            func.min(SystemHealthMetric.metric_value).label("min_value"),
            func.max(SystemHealthMetric.metric_value).label("max_value"),
            func.count(SystemHealthMetric.id).label("total_count"),
        )
        .filter(SystemHealthMetric.recorded_at >= cutoff)
        .group_by(SystemHealthMetric.service_name, SystemHealthMetric.metric_name, SystemHealthMetric.metric_unit)
        .order_by(SystemHealthMetric.service_name, SystemHealthMetric.metric_name)
        .all()
    )
    return [
        {
            "service_name": row.service_name,
            "metric_name": row.metric_name,
            "metric_unit": row.metric_unit,
            "avg_value": round(row.avg_value, 2) if row.avg_value is not None else None,
            "min_value": row.min_value,
            "max_value": row.max_value,
            "total_count": row.total_count,
        }
        for row in rows
    ]


class WeeklyReport:
    """Generates a weekly feature adoption and system health report."""

    def __init__(self, db: Session):
        self.db = db

    def generate(self) -> Dict[str, Any]:
        """Generate a complete weekly report with adoption metrics, health status, and anomaly flags."""
        report = {
            "period": "weekly",
            "generated_at": datetime.utcnow().isoformat(),
            "feature_adoption": self._feature_adoption_section(),
            "system_health": self._system_health_section(),
            "alerts": [],
        }
        for feature in FEATURE_NAMES:
            feature_data = [f for f in report["feature_adoption"] if f["feature_name"] == feature]
            if not feature_data:
                report["alerts"].append({
                    "type": "zero_usage",
                    "feature": feature,
                    "message": f"No usage events recorded for {feature} in the past 7 days. Potential churn signal.",
                })
        return report

    def _feature_adoption_section(self) -> List[Dict[str, Any]]:
        return get_feature_adoption_summary(self.db, days=7)

    def _system_health_section(self) -> List[Dict[str, Any]]:
        return get_system_health_summary(self.db, hours=24 * 7)


def get_pilot_engagement_metrics(
    db: Session,
    days: int = 30,
    org_directory=None,
) -> Dict[str, Any]:
    """Compute pilot customer engagement metrics from the analytics event store.

    `org_directory` is an optional callable mapping organization ids to names
    (cross-service lookup). When unavailable, organization names are omitted
    and ids are returned instead.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)

    total_orgs = db.query(func.count(distinct(AnalyticsEvent.organization_id))).filter(
        AnalyticsEvent.organization_id.isnot(None)
    ).scalar() or 0

    active_org_rows = (
        db.query(AnalyticsEvent.organization_id)
        .filter(AnalyticsEvent.created_at >= cutoff, AnalyticsEvent.organization_id.isnot(None))
        .distinct()
        .all()
    )
    active_org_ids = [row[0] for row in active_org_rows]
    active_orgs = len(active_org_ids)

    active_user_events = (
        db.query(func.count(distinct(AnalyticsEvent.user_id)))
        .filter(AnalyticsEvent.created_at >= cutoff, AnalyticsEvent.user_id.isnot(None))
        .scalar() or 0
    )

    total_events = db.query(func.count(AnalyticsEvent.id)).filter(AnalyticsEvent.created_at >= cutoff).scalar() or 0
    avg_events = total_events / active_orgs if active_orgs > 0 else 0

    onboarding_events = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_type == "onboarding_completion",
        AnalyticsEvent.created_at >= cutoff,
    ).scalar() or 0
    onboarding_completion_rate = (onboarding_events / active_orgs * 100) if active_orgs > 0 else 0

    adoption_rows = (
        db.query(
            AnalyticsEvent.organization_id,
            func.count(AnalyticsEvent.id).label("count"),
        )
        .filter(AnalyticsEvent.created_at >= cutoff, AnalyticsEvent.organization_id.isnot(None))
        .group_by(AnalyticsEvent.organization_id)
        .all()
    )
    adoption_by_org: Dict[str, int] = {}
    for row in adoption_rows:
        org_key = str(row[0]) if row[0] else "unknown"
        adoption_by_org[org_key] = adoption_by_org.get(org_key, 0) + row[1]

    recent_rows = (
        db.query(
            AnalyticsEvent.organization_id,
            func.max(AnalyticsEvent.created_at).label("last_activity"),
        )
        .filter(AnalyticsEvent.created_at >= cutoff, AnalyticsEvent.organization_id.isnot(None))
        .group_by(AnalyticsEvent.organization_id)
        .order_by(func.max(AnalyticsEvent.created_at).desc())
        .limit(10)
        .all()
    )

    recently_active_orgs: List[Dict[str, Any]] = []
    for org_id, last_activity in recent_rows:
        entry: Dict[str, Any] = {
            "organization_id": org_id,
            "organization_name": None,
            "last_activity": last_activity.isoformat() if last_activity else None,
        }
        if org_directory:
            entry["organization_name"] = org_directory(str(org_id))
        recently_active_orgs.append(entry)

    trends: List[Dict[str, Any]] = []
    for i in range(min(days, 7)):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_orgs = (
            db.query(func.count(distinct(AnalyticsEvent.organization_id)))
            .filter(
                AnalyticsEvent.created_at >= day_start,
                AnalyticsEvent.created_at < day_end,
                AnalyticsEvent.organization_id.isnot(None),
            )
            .scalar() or 0
        )
        day_events = (
            db.query(func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.created_at >= day_start, AnalyticsEvent.created_at < day_end)
            .scalar() or 0
        )
        trends.append({
            "date": day.strftime("%Y-%m-%d"),
            "active_organizations": day_orgs,
            "total_events": day_events,
        })
    trends.reverse()

    return {
        "total_organizations": total_orgs,
        "active_organizations_30d": active_orgs,
        "total_users": None,
        "active_users_30d": active_user_events,
        "avg_events_per_org": round(avg_events, 2),
        "onboarding_completion_rate": round(onboarding_completion_rate, 2),
        "feature_adoption_by_org": adoption_by_org,
        "recently_active_orgs": recently_active_orgs,
        "engagement_trends": trends,
    }
