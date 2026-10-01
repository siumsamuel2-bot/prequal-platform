"""Analytics pipeline for Dashboard & Compliance Metrics.

Provides data-layer aggregation queries behind the Dashboard API.
All queries read from materialized views or pre-computed aggregates
for predictable performance.

Owner: Data Engineer
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _to_iso(value: Any) -> Optional[str]:
    """Convert a datetime/date object (or string) to ISO format string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Refresh helpers for materialized views
# ---------------------------------------------------------------------------

async def refresh_all_analytics_views(db: AsyncSession, *, concurrently: bool = True) -> None:
    """Refresh all dashboard materialized views.

    Call this after the daily ETL pipeline completes.
    """
    views = [
        "mv_compliance_summary",
        "mv_compliance_trends",
        "mv_certification_status",
        "mv_project_compliance",
        "mv_recent_alerts",
    ]
    for view in views:
        await _refresh_view(db, view, concurrently=concurrently)


async def _refresh_view(db: AsyncSession, view_name: str, *, concurrently: bool = True) -> None:
    if concurrently:
        await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
    else:
        await db.execute(text(f"REFRESH MATERIALIZED VIEW {view_name}"))
    logger.info("Refreshed materialized view: %s", view_name)


# ---------------------------------------------------------------------------
# Compliance Summary (GET /api/compliance/summary)
# ---------------------------------------------------------------------------

async def get_compliance_summary(db: AsyncSession) -> dict[str, Any]:
    """Return single-row compliance summary for the dashboard card view."""
    result = await db.execute(text("SELECT * FROM mv_compliance_summary LIMIT 1"))
    row = result.mappings().first()
    if not row:
        return {}
    return {
        "total_subcontractors": row["total_subcontractors"],
        "active_subcontractors": row["active_subcontractors"],
        "suspended_subcontractors": row["suspended_subcontractors"],
        "blacklisted_subcontractors": row["blacklisted_subcontractors"],
        "compliant_subcontractors": row["compliant_subcontractors"],
        "compliance_rate": _safe_rate(row["compliant_subcontractors"], row["active_subcontractors"]),
        "expiring_soon_30d": row["expiring_soon_30d"],
        "expiring_soon_60d": row["expiring_soon_60d"],
        "open_violations": row["open_violations"],
        "open_osha_violations": row["open_osha_violations"],
        "total_open_penalties": float(row["total_open_penalties"] or 0),
        "valid_certifications": row["valid_certifications"],
        "expired_certifications": row["expired_certifications"],
        "pending_verification_certs": row["pending_verification_certs"],
        "computed_at": _to_iso(row["computed_at"]),
    }


# ---------------------------------------------------------------------------
# Compliance Trends (GET /api/compliance/trends?days=30/60/90)
# ---------------------------------------------------------------------------

async def get_compliance_trends(db: AsyncSession, days: int = 90) -> list[dict[str, Any]]:
    """Return daily compliance trend points for the last ``days`` days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).date()
    result = await db.execute(
        text(
            """
            SELECT trend_date, active_subcontractors, valid_certifications,
                   expired_certifications, open_violations, open_osha_violations,
                   compliance_percentage, computed_at
            FROM mv_compliance_trends
            WHERE trend_date >= :cutoff
            ORDER BY trend_date ASC
            """
        ),
        {"cutoff": cutoff},
    )
    rows = result.mappings().all()
    trends = []
    for row in rows:
        trends.append(
            {
                "date": _to_iso(row["trend_date"]),
                "active_subcontractors": row["active_subcontractors"],
                "valid_certifications": row["valid_certifications"],
                "expired_certifications": row["expired_certifications"],
                "open_violations": row["open_violations"],
                "open_osha_violations": row["open_osha_violations"],
                "compliance_percentage": round(float(row["compliance_percentage"] or 0), 2),
                "computed_at": _to_iso(row["computed_at"]),
            }
        )
    return trends


# ---------------------------------------------------------------------------
# Certification Status for Export (GET /api/compliance/export)
# ---------------------------------------------------------------------------

async def get_certification_export_rows(
    db: AsyncSession,
    *,
    expiration_bucket: Optional[str] = None,
    subcontractor_id: Optional[str] = None,
    limit: int = 5000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return paginated rows for CSV export."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    filters = ["1=1"]

    if expiration_bucket:
        filters.append("expiration_bucket = :bucket")
        params["bucket"] = expiration_bucket
    if subcontractor_id:
        filters.append("subcontractor_id = :sub_id")
        params["sub_id"] = subcontractor_id

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(
            f"""
            SELECT
                subcontractor_id,
                company_name,
                email,
                subcontractor_status,
                certification_id,
                certification_type,
                certification_number,
                issue_date,
                expiration_date,
                certification_status,
                verification_status,
                expiration_bucket,
                days_until_expiration,
                verified_at,
                created_at,
                computed_at
            FROM mv_certification_status
            WHERE {where_clause}
            ORDER BY expiration_date ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return [
        {
            "subcontractor_id": str(r["subcontractor_id"]),
            "company_name": r["company_name"],
            "email": r["email"],
            "subcontractor_status": r["subcontractor_status"],
            "certification_id": str(r["certification_id"]),
            "certification_type": r["certification_type"],
            "certification_number": r["certification_number"],
            "issue_date": _to_iso(r["issue_date"]),
            "expiration_date": _to_iso(r["expiration_date"]),
            "certification_status": r["certification_status"],
            "verification_status": r["verification_status"],
            "expiration_bucket": r["expiration_bucket"],
            "days_until_expiration": r["days_until_expiration"],
            "verified_at": _to_iso(r["verified_at"]),
            "created_at": _to_iso(r["created_at"]),
            "computed_at": _to_iso(r["computed_at"]),
        }
        for r in rows
    ]


async def get_certification_export_count(
    db: AsyncSession,
    *,
    expiration_bucket: Optional[str] = None,
    subcontractor_id: Optional[str] = None,
) -> int:
    """Return total count for pagination headers."""
    params: dict[str, Any] = {}
    filters = ["1=1"]

    if expiration_bucket:
        filters.append("expiration_bucket = :bucket")
        params["bucket"] = expiration_bucket
    if subcontractor_id:
        filters.append("subcontractor_id = :sub_id")
        params["sub_id"] = subcontractor_id

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(f"SELECT COUNT(*) FROM mv_certification_status WHERE {where_clause}"),
        params,
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Recent Alerts (GET /api/alerts/recent)
# ---------------------------------------------------------------------------

async def get_recent_alerts(
    db: AsyncSession,
    *,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return recent alert notifications for the dashboard."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    filters = ["1=1"]

    if status:
        filters.append("status = :status")
        params["status"] = status

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(
            f"""
            SELECT
                alert_id,
                certification_id,
                alert_type,
                scheduled_for,
                sent_at,
                status,
                method,
                recipient,
                subject,
                acknowledged_at,
                days_until_expiration,
                created_at,
                certification_type,
                expiration_date,
                subcontractor_id,
                subcontractor_name,
                subcontractor_email,
                computed_at
            FROM mv_recent_alerts
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return [
        {
            "alert_id": str(r["alert_id"]),
            "certification_id": str(r["certification_id"]),
            "alert_type": r["alert_type"],
            "scheduled_for": _to_iso(r["scheduled_for"]),
            "sent_at": _to_iso(r["sent_at"]),
            "status": r["status"],
            "method": r["method"],
            "recipient": r["recipient"],
            "subject": r["subject"],
            "acknowledged_at": _to_iso(r["acknowledged_at"]),
            "days_until_expiration": r["days_until_expiration"],
            "created_at": _to_iso(r["created_at"]),
            "certification_type": r["certification_type"],
            "expiration_date": _to_iso(r["expiration_date"]),
            "subcontractor_id": str(r["subcontractor_id"]),
            "subcontractor_name": r["subcontractor_name"],
            "subcontractor_email": r["subcontractor_email"],
            "computed_at": _to_iso(r["computed_at"]),
        }
        for r in rows
    ]


async def get_recent_alerts_count(
    db: AsyncSession,
    *,
    status: Optional[str] = None,
) -> int:
    """Return total count for pagination headers."""
    params: dict[str, Any] = {}
    filters = ["1=1"]

    if status:
        filters.append("status = :status")
        params["status"] = status

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(f"SELECT COUNT(*) FROM mv_recent_alerts WHERE {where_clause}"),
        params,
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Project-level Compliance (GET /api/compliance/summary by project)
# ---------------------------------------------------------------------------

async def get_project_compliance_by_id(
    db: AsyncSession,
    project_id: str,
) -> Optional[dict[str, Any]]:
    """Return compliance summary for a specific project."""
    result = await db.execute(
        text(
            """
            SELECT *
            FROM mv_project_compliance
            WHERE project_id = :project_id
            LIMIT 1
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    total_subcontractors = row["total_subcontractors"] or 0
    compliant_subcontractors = row["compliant_subcontractors"] or 0
    return {
        "project_id": str(row["project_id"]),
        "project_name": row["project_name"],
        "project_number": row["project_number"],
        "project_status": row["project_status"],
        "start_date": _to_iso(row["start_date"]),
        "estimated_end_date": _to_iso(row["estimated_end_date"]),
        "total_subcontractors": total_subcontractors,
        "active_subcontractors": row["active_subcontractors"],
        "suspended_subcontractors": row["suspended_subcontractors"],
        "compliant_subcontractors": compliant_subcontractors,
        "compliance_rate": _safe_rate(compliant_subcontractors, total_subcontractors),
        "open_violations": row["open_violations"],
        "open_osha_violations": row["open_osha_violations"],
        "total_open_penalties": float(row["total_open_penalties"] or 0),
        "expiring_soon_subcontractors": row["expiring_soon_subcontractors"],
        "computed_at": _to_iso(row["computed_at"]),
    }


async def get_all_project_compliance(db: AsyncSession, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
    """Return compliance summary for all active projects."""
    result = await db.execute(
        text(
            """
            SELECT *
            FROM mv_project_compliance
            ORDER BY computed_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    )
    rows = result.mappings().all()
    projects = []
    for row in rows:
        total_subcontractors = row["total_subcontractors"] or 0
        compliant_subcontractors = row["compliant_subcontractors"] or 0
        projects.append(
            {
                "project_id": str(row["project_id"]),
                "project_name": row["project_name"],
                "project_number": row["project_number"],
                "project_status": row["project_status"],
                "total_subcontractors": total_subcontractors,
                "active_subcontractors": row["active_subcontractors"],
                "compliant_subcontractors": compliant_subcontractors,
                "compliance_rate": _safe_rate(compliant_subcontractors, total_subcontractors),
                "open_violations": row["open_violations"],
                "open_osha_violations": row["open_osha_violations"],
                "total_open_penalties": float(row["total_open_penalties"] or 0),
                "expiring_soon_subcontractors": row["expiring_soon_subcontractors"],
                "computed_at": _to_iso(row["computed_at"]),
            }
        )
    return projects


# ---------------------------------------------------------------------------
# Feature Adoption (GET /api/analytics/feature-adoption)
# ---------------------------------------------------------------------------

async def get_feature_adoption_summary(
    db: AsyncSession,
    *,
    feature_name: Optional[str] = None,
    days: int = 90,
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return daily feature adoption aggregates from mv_feature_adoption_summary."""
    params: dict[str, Any] = {"limit": limit, "offset": offset, "days": days}
    filters = ["event_date >= CURRENT_DATE - INTERVAL ':days days'"]

    if feature_name:
        filters.append("feature_name = :feature_name")
        params["feature_name"] = feature_name

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(
            f"""
            SELECT
                feature_name,
                event_date,
                total_events,
                unique_users,
                view_count,
                action_count,
                export_count,
                computed_at
            FROM mv_feature_adoption_summary
            WHERE {where_clause}
            ORDER BY event_date DESC, total_events DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return [
        {
            "feature_name": row["feature_name"],
            "event_date": _to_iso(row["event_date"]),
            "total_events": row["total_events"],
            "unique_users": row["unique_users"],
            "view_count": row["view_count"],
            "action_count": row["action_count"],
            "export_count": row["export_count"],
            "computed_at": _to_iso(row["computed_at"]),
        }
        for row in rows
    ]


async def get_feature_adoption_summary_count(
    db: AsyncSession,
    *,
    feature_name: Optional[str] = None,
    days: int = 90,
) -> int:
    """Return total count of feature adoption rows for pagination."""
    params: dict[str, Any] = {"days": days}
    filters = ["event_date >= CURRENT_DATE - INTERVAL ':days days'"]

    if feature_name:
        filters.append("feature_name = :feature_name")
        params["feature_name"] = feature_name

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(f"SELECT COUNT(*) FROM mv_feature_adoption_summary WHERE {where_clause}"),
        params,
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# System Health (GET /api/analytics/system-health)
# ---------------------------------------------------------------------------

async def get_system_health_summary(
    db: AsyncSession,
    *,
    service_name: Optional[str] = None,
    metric_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return system health aggregates from mv_system_health_summary."""
    params: dict[str, Any] = {}
    filters = ["1=1"]

    if service_name:
        filters.append("service_name = :service_name")
        params["service_name"] = service_name
    if metric_name:
        filters.append("metric_name = :metric_name")
        params["metric_name"] = metric_name

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(
            f"""
            SELECT
                service_name,
                metric_name,
                metric_unit,
                avg_value,
                min_value,
                max_value,
                p95_value,
                total_count,
                computed_at
            FROM mv_system_health_summary
            WHERE {where_clause}
            ORDER BY service_name, metric_name
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return [
        {
            "service_name": row["service_name"],
            "metric_name": row["metric_name"],
            "metric_unit": row["metric_unit"],
            "avg_value": round(float(row["avg_value"] or 0), 4),
            "min_value": round(float(row["min_value"] or 0), 4),
            "max_value": round(float(row["max_value"] or 0), 4),
            "p95_value": round(float(row["p95_value"] or 0), 4),
            "total_count": row["total_count"],
            "computed_at": _to_iso(row["computed_at"]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator and denominator > 0:
        return round((numerator / denominator) * 100, 2)
    return 0.0
