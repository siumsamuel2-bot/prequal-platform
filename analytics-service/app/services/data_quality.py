"""Data quality monitoring for the analytics service database (MID-626).

Complements the monolith's data_quality_monitoring.py (MID-605), which covers
compliance tables. This module watches the analytics service's own tables:
analytics_events, feature_usage_events, system_health_metrics.

Checks:
- Freshness: per-source last-event age vs SLA hours (default 24h)
- Field quality: null rates for organization_id / user_id / event_type /
  feature_name (static threshold, default 10%)
- Volume anomalies: today's event count vs trailing 7-day average
  (drop > 50% is anomalous)
- Retention: rows older than retention_days (default 90) are archived
  (insert-only archive tables; source rows are NEVER deleted).

Alerts are persisted to data_quality_alerts in this service's database —
internal records only, no external delivery (per MID-626 constraints).

Owner: Data Engineer
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.models import (
    AnalyticsEvent,
    FeatureUsageEvent,
    DataQualityAlert,
    AnalyticsEventArchive,
    FeatureUsageEventArchive,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "freshness_hours_max": 24,
    "null_rate_max": 0.10,
    "volume_drop_pct": 0.50,
    "retention_days": 90,
}


# ---------------------------------------------------------------------------
# Freshness: last event per source vs SLA
# ---------------------------------------------------------------------------

def check_freshness(
    db: Session, sla_hours: Optional[int] = None
) -> Dict[str, Any]:
    """Check per-source event freshness against the SLA."""
    sla = sla_hours if sla_hours is not None else DEFAULT_THRESHOLDS["freshness_hours_max"]
    now = datetime.utcnow()

    rows = (
        db.query(
            AnalyticsEvent.source_service,
            func.max(AnalyticsEvent.created_at).label("last_event"),
        )
        .group_by(AnalyticsEvent.source_service)
        .all()
    )
    sources: List[Dict[str, Any]] = []
    for r in rows:
        last = r.last_event.replace(tzinfo=None) if r.last_event else None
        age_hours = round((now - last).total_seconds() / 3600, 2) if last else None
        sources.append(
            {
                "source_service": r.source_service or "unknown",
                "last_event_at": last.isoformat() if last else None,
                "age_hours": age_hours,
                "breached": last is None or (age_hours is not None and age_hours > sla),
            }
        )

    return {
        "sla_hours": sla,
        "sources": sources,
        "total_breached": sum(1 for s in sources if s["breached"]),
    }


# ---------------------------------------------------------------------------
# Field quality: null rates on critical columns
# ---------------------------------------------------------------------------

FIELD_SPECS = [
    {"table_cls": AnalyticsEvent, "column": "event_type"},
    {"table_cls": AnalyticsEvent, "column": "organization_id"},
    {"table_cls": AnalyticsEvent, "column": "user_id"},
    {"table_cls": FeatureUsageEvent, "column": "feature_name"},
    {"table_cls": FeatureUsageEvent, "column": "event_type"},
    {"table_cls": FeatureUsageEvent, "column": "user_id"},
]


def check_field_quality(db: Session) -> Dict[str, Any]:
    """Compute null rates for critical analytics columns."""
    fields: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    for spec in FIELD_SPECS:
        table_cls = spec["table_cls"]
        col = getattr(table_cls, spec["column"])
        total = db.query(func.count(table_cls.id)).scalar() or 0
        null_count = (
            db.query(func.count(table_cls.id)).filter(col.is_(None)).scalar() or 0
        )
        null_rate = round(null_count / total, 4) if total else 0.0
        label = f"{table_cls.__tablename__}.{spec['column']}"
        fields.append(
            {
                "table": table_cls.__tablename__,
                "column": spec["column"],
                "total_rows": total,
                "null_count": null_count,
                "null_rate": null_rate,
            }
        )
        if null_rate > DEFAULT_THRESHOLDS["null_rate_max"]:
            alerts.append(
                {
                    "alert_type": "high_null_rate",
                    "severity": "warning" if null_rate <= 2 * DEFAULT_THRESHOLDS["null_rate_max"] else "error",
                    "source_table": table_cls.__tablename__,
                    "message": (
                        f"Null rate for {label} above threshold: {null_rate:.2%} "
                        f"({null_count}/{total} rows; threshold {DEFAULT_THRESHOLDS['null_rate_max']:.2%})"
                    ),
                    "threshold_value": DEFAULT_THRESHOLDS["null_rate_max"],
                    "actual_value": null_rate,
                }
            )
    return {"fields": fields, "alerts": alerts}


# ---------------------------------------------------------------------------
# Volume anomalies: today's count vs trailing 7-day average
# ---------------------------------------------------------------------------

def check_volume_anomalies(db: Session) -> Dict[str, Any]:
    """Detect sudden daily-volume drops in feature_usage_events."""
    drop_pct = DEFAULT_THRESHOLDS["volume_drop_pct"]
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    history_start = today_start - timedelta(days=7)

    today_count = (
        db.query(func.count(FeatureUsageEvent.id))
        .filter(FeatureUsageEvent.created_at >= today_start)
        .scalar()
    ) or 0

    history = (
        db.query(
            func.date(FeatureUsageEvent.created_at).label("day"),
            func.count(FeatureUsageEvent.id).label("cnt"),
        )
        .filter(
            FeatureUsageEvent.created_at >= history_start,
            FeatureUsageEvent.created_at < today_start,
        )
        .group_by(func.date(FeatureUsageEvent.created_at))
        .all()
    )
    avg_per_day = (
        sum(r.cnt for r in history) / len(history) if history else None
    )

    anomalous = (
        avg_per_day is not None
        and avg_per_day > 0
        and today_count < avg_per_day * (1 - drop_pct)
    )
    result: Dict[str, Any] = {
        "drop_pct_threshold": drop_pct,
        "today_count": today_count,
        "baseline_avg_per_day": round(avg_per_day, 2) if avg_per_day is not None else None,
        "anomalous": anomalous,
    }
    if anomalous:
        drop = 1 - (today_count / avg_per_day)
        result["alert"] = {
            "alert_type": "volume_drop",
            "severity": "error",
            "source_table": "feature_usage_events",
            "message": (
                f"Today's event count {today_count} is {drop:.2%} below the "
                f"7-day average of {avg_per_day:.2f} (threshold {drop_pct:.0%})"
            ),
            "threshold_value": drop_pct,
            "actual_value": round(drop, 4),
        }
    return result


# ---------------------------------------------------------------------------
# Alert persistence (internal records only)
# ---------------------------------------------------------------------------

def persist_alerts(db: Session, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Persist alerts to data_quality_alerts. Returns persisted rows (dicts)."""
    persisted: List[Dict[str, Any]] = []
    for a in alerts:
        row = DataQualityAlert(
            id=str(uuid.uuid4()),
            alert_type=a["alert_type"],
            severity=a["severity"],
            source_table=a.get("source_table"),
            message=a["message"],
            threshold_value=a.get("threshold_value"),
            actual_value=a.get("actual_value"),
        )
        db.add(row)
        persisted.append(
            {
                "id": row.id,
                "alert_type": row.alert_type,
                "severity": row.severity,
                "source_table": row.source_table,
                "message": row.message,
            }
        )
    db.commit()
    logger.info("Persisted %d data quality alert(s)", len(persisted))
    return persisted


def run_data_quality_check(db: Session, persist: bool = True) -> Dict[str, Any]:
    """Run all analytics data quality checks; optionally persist alerts."""
    freshness = check_freshness(db)
    field_quality = check_field_quality(db)
    volume = check_volume_anomalies(db)

    alerts: List[Dict[str, Any]] = list(field_quality["alerts"])
    for src in freshness["sources"]:
        if src["breached"]:
            sla = freshness["sla_hours"]
            age = src["age_hours"]
            alerts.append(
                {
                    "alert_type": "freshness_sla_breach",
                    "severity": "error" if (age is None or age > 2 * sla) else "warning",
                    "source_table": "analytics_events",
                    "message": (
                        f"Freshness SLA breach for source {src['source_service']}: "
                        f"last event "
                        + (f"{age:.1f}h ago" if age is not None else "never")
                        + f" (SLA {sla}h)"
                    ),
                    "threshold_value": sla,
                    "actual_value": age,
                }
            )
    if volume.get("alert"):
        alerts.append(volume["alert"])

    result: Dict[str, Any] = {
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "freshness": freshness,
        "field_quality": {k: v for k, v in field_quality.items() if k != "alerts"},
        "volume": {k: v for k, v in volume.items() if k != "alert"},
        "alerts": alerts,
    }
    if persist and alerts:
        result["persisted_alerts"] = persist_alerts(db, alerts)
    return result


# ---------------------------------------------------------------------------
# Retention: archival (never deletes)
# ---------------------------------------------------------------------------

def archive_old_analytics_events(
    db: Session, retention_days: Optional[int] = None
) -> Dict[str, int]:
    """Archive analytics_events older than retention_days.

    Insert-only into analytics_events_archive; source rows are never deleted.
    Returns the count of newly archived rows.
    """
    days = retention_days if retention_days is not None else DEFAULT_THRESHOLDS["retention_days"]
    cutoff = datetime.utcnow() - timedelta(days=days)
    sql = text(
        """
        INSERT INTO analytics_events_archive
            (id, event_type, user_id, organization_id, event_metadata,
             source_service, created_at)
        SELECT e.id, e.event_type, e.user_id, e.organization_id,
               e.event_metadata, e.source_service, e.created_at
        FROM analytics_events e
        WHERE e.created_at < :cutoff
        AND NOT EXISTS (
            SELECT 1 FROM analytics_events_archive a WHERE a.id = e.id
        )
        """
    )
    result = db.execute(sql, {"cutoff": cutoff})
    db.commit()
    return {"archived": result.rowcount}


def archive_old_feature_events(
    db: Session, retention_days: Optional[int] = None
) -> Dict[str, int]:
    """Archive feature_usage_events older than retention_days (never delete source)."""
    days = retention_days if retention_days is not None else DEFAULT_THRESHOLDS["retention_days"]
    cutoff = datetime.utcnow() - timedelta(days=days)
    sql = text(
        """
        INSERT INTO feature_usage_events_archive
            (id, user_id, feature_name, event_type, event_metadata, created_at)
        SELECT f.id, f.user_id, f.feature_name, f.event_type,
               f.event_metadata, f.created_at
        FROM feature_usage_events f
        WHERE f.created_at < :cutoff
        AND NOT EXISTS (
            SELECT 1 FROM feature_usage_events_archive a WHERE a.id = f.id
        )
        """
    )
    result = db.execute(sql, {"cutoff": cutoff})
    db.commit()
    return {"archived": result.rowcount}


def list_recent_quality_alerts(db: Session, limit: int = 50) -> List[Dict[str, Any]]:
    """List recent persisted data-quality alerts, newest first."""
    rows = (
        db.query(DataQualityAlert)
        .order_by(DataQualityAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "alert_type": r.alert_type,
            "severity": r.severity,
            "source_table": r.source_table,
            "message": r.message,
            "threshold_value": r.threshold_value,
            "actual_value": r.actual_value,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
