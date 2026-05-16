"""Certification Expiration Monitoring & Alerting Service.

Provides:
- Daily certification expiration scan (auto-flags expired, generates alerts at 30/14/7 days)
- Manual scan trigger via REST endpoint
- Alert summary and project/contractor-scoped retrieval

All writes go through the existing compliance models for consistency.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.compliance import Certification, Subcontractor, AlertNotification, ProjectSubcontractor
from app.schemas.compliance import CertificationStatus

# Warning windows in days (sorted descending: 30, 14, 7)
WARNING_WINDOWS = [30, 14, 7]


# ---------------------------------------------------------------------------
# Internal helper: create a deduplicated expiration alert
# ---------------------------------------------------------------------------

async def _create_expiration_alert(
    db: AsyncSession,
    certification: Certification,
    days_until: int,
) -> Optional[AlertNotification]:
    """Create an expiration alert if one doesn't already exist for today."""
    scheduled_for = datetime.combine(date.today(), datetime.min.time())

    # Deduplication: one alert per cert / days-until / day
    existing = await db.execute(
        select(AlertNotification).where(
            and_(
                AlertNotification.certification_id == certification.id,
                AlertNotification.days_until_expiration == days_until,
                func.date(AlertNotification.scheduled_for) == date.today(),
            )
        )
    )
    if existing.scalar_one_or_none():
        return None

    # Resolve active project for the subcontractor (first found)
    proj_result = await db.execute(
        select(ProjectSubcontractor.project_id)
        .where(
            and_(
                ProjectSubcontractor.subcontractor_id == certification.subcontractor_id,
                ProjectSubcontractor.status == "active",
            )
        )
    )
    project_ids = proj_result.scalars().all()

    # Resolve contractor name
    sub_result = await db.execute(
        select(Subcontractor.company_name)
        .where(Subcontractor.id == certification.subcontractor_id)
    )
    company_name = sub_result.scalar() or "Unknown"

    subject = f"Certification expires in {days_until} days" if days_until > 0 else "Certification has expired"
    body = (
        f"{certification.certification_type} for {company_name} "
        f"expires on {certification.expiration_date.isoformat()} "
        f"({days_until} days from today)."
    )

    alert = AlertNotification(
        certification_id=certification.id,
        alert_type=f"expiration_{days_until}d" if days_until > 0 else "expired",
        scheduled_for=scheduled_for,
        status="pending",
        method="in_app",
        recipient=str(certification.subcontractor_id),
        subject=subject,
        body=body,
        retry_count=0,
        max_retries=3,
        days_until_expiration=days_until if days_until > 0 else 0,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# Daily expiration scan
# ---------------------------------------------------------------------------

async def scan_expirations(db: AsyncSession) -> dict[str, Any]:
    """Daily scan: flag expired certs, generate alerts at warning windows."""
    today = date.today()
    summary = {
        "alerts_created": 0,
        "certifications_expired": 0,
        "warnings_30": 0,
        "warnings_14": 0,
        "warnings_7": 0,
    }

    # 1. Flag expired certifications
    expired_result = await db.execute(
        select(Certification).where(
            and_(
                Certification.expiration_date < today,
                Certification.status != CertificationStatus.EXPIRED.value,
            )
        )
    )
    for cert in expired_result.scalars().all():
        cert.status = CertificationStatus.EXPIRED.value  # type: ignore[assignment]
        summary["certifications_expired"] += 1

    await db.commit()

    # 2. Generate alerts at warning windows
    for window in WARNING_WINDOWS:
        target_date = today + timedelta(days=window)
        result = await db.execute(
            select(Certification, Subcontractor.company_name)
            .join(Subcontractor, Certification.subcontractor_id == Subcontractor.id)
            .where(
                and_(
                    Certification.expiration_date == target_date,
                    Certification.status == CertificationStatus.VALID.value,
                )
            )
        )
        for cert, _company_name in result.all():
            alert = await _create_expiration_alert(db, cert, window)
            if alert:
                summary["alerts_created"] += 1
                if window == 30:
                    summary["warnings_30"] += 1
                elif window == 14:
                    summary["warnings_14"] += 1
                elif window == 7:
                    summary["warnings_7"] += 1

    return summary


# ---------------------------------------------------------------------------
# Alert summary helper
# ---------------------------------------------------------------------------

async def get_alert_summary(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Return a summary of alert counts for the given lookback period."""
    today = date.today()
    future = today + timedelta(days=days)

    pending_count = (await db.execute(
        select(func.count(AlertNotification.id)).where(
            AlertNotification.scheduled_for >= today,
            AlertNotification.scheduled_for <= future,
            AlertNotification.status == "pending",
        )
    )).scalar() or 0

    ack_count = (await db.execute(
        select(func.count(AlertNotification.id)).where(
            AlertNotification.scheduled_for >= today,
            AlertNotification.scheduled_for <= future,
            AlertNotification.status == "acknowledged",
        )
    )).scalar() or 0

    expired_count = (await db.execute(
        select(func.count(Certification.id)).where(
            Certification.status == "expired"
        )
    )).scalar() or 0

    return {
        "pending_alerts": pending_count,
        "acknowledged_alerts": ack_count,
        "expired_certifications": expired_count,
        "lookback_days": days,
    }
