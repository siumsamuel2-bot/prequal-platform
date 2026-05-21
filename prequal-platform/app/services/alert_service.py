"""Certification Expiration Monitoring & Alerting Service.

Provides:
- Daily certification expiration scan (auto-flags expired, generates alerts at 30/14/7 days)
- Manual scan trigger via REST endpoint
- Alert summary and project/contractor-scoped retrieval
- Alert delivery processor (sends email/SMS for pending alerts)

All writes go through the existing compliance models for consistency.
"""

from __future__ import annotations

import uuid
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance import (
    Certification, Subcontractor, AlertNotification, ProjectSubcontractor, Project,
    NotificationPreferences
)
from app.models.auth import User, TeamMember
from app.schemas.compliance import CertificationStatus
from app.services.notification_service import send_notification, NotificationResult
from app.logging_config import get_logger

logger = get_logger(__name__)

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


async def _get_users_to_notify_for_subcontractor(
    db: AsyncSession,
    subcontractor_id: uuid.UUID
) -> list[tuple[User, NotificationPreferences]]:
    """Find users who should be notified about a subcontractor's cert expirations.
    
    Returns list of (User, NotificationPreferences) tuples for users who have
    opted in to notifications for this subcontractor.
    """
    result = await db.execute(
        select(
            User,
            NotificationPreferences
        )
        .join(TeamMember, User.id == TeamMember.user_id)
        .join(Project, TeamMember.team_id == Project.team_id)
        .join(ProjectSubcontractor, Project.id == ProjectSubcontractor.project_id)
        .outerjoin(
            NotificationPreferences,
            and_(
                NotificationPreferences.user_id == User.id,
                NotificationPreferences.subcontractor_id == subcontractor_id
            )
        )
        .where(
            and_(
                ProjectSubcontractor.subcontractor_id == subcontractor_id,
                ProjectSubcontractor.status == "active",
                User.is_active == True,
                or_(
                    NotificationPreferences.notify_on_cert_expiration == True,
                    NotificationPreferences.id.is_(None)
                )
            )
        )
        .distinct()
    )
    return list(result.all())


async def _send_alert_to_user(
    db: AsyncSession,
    alert: AlertNotification,
    user: User,
    prefs: Optional[NotificationPreferences]
) -> tuple[bool, str]:
    """Send an alert to a specific user based on their preferences.
    
    Returns (success, method_used).
    """
    email_enabled = prefs.email_enabled if prefs and prefs.email_enabled is not None else True
    sms_enabled = prefs.sms_enabled if prefs and prefs.sms_enabled else False
    
    sent = False
    method_used = "none"
    
    if email_enabled:
        email_result = await send_notification(
            recipient=user.email,
            subject=alert.subject or "Certification Alert",
            body=alert.body or "",
            method="email"
        )
        if email_result.success:
            sent = True
            method_used = "email"
            logger.info(
                f"Email alert sent to {user.email} for alert {alert.id}, "
                f"message_id={email_result.message_id}"
            )
        else:
            logger.error(
                f"Failed to send email alert to {user.email} for alert {alert.id}: "
                f"{email_result.error}"
            )
    
    if not sent and sms_enabled:
        phone = prefs.custom_phone if prefs and prefs.custom_phone else None
        if phone:
            sms_result = await send_notification(
                recipient=phone,
                subject=alert.subject or "",
                body=alert.body or "",
                method="sms"
            )
            if sms_result.success:
                sent = True
                method_used = "sms"
                logger.info(
                    f"SMS alert sent to {phone} for alert {alert.id}, "
                    f"message_id={sms_result.message_id}"
                )
            else:
                logger.error(
                    f"Failed to send SMS alert to {phone} for alert {alert.id}: "
                    f"{sms_result.error}"
                )
    
    return sent, method_used


async def deliver_pending_alerts(db: AsyncSession) -> dict[str, Any]:
    """Process and deliver all pending alerts scheduled for today.
    
    This function:
    1. Finds pending alerts scheduled for today
    2. For each alert, identifies users to notify based on project/team membership
    3. Respects user notification preferences
    4. Sends email/SMS notifications
    5. Updates alert status based on delivery success
    
    Returns a summary dict of delivery results.
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    summary = {
        "total_processed": 0,
        "sent_email": 0,
        "sent_sms": 0,
        "failed": 0,
        "skipped_no_recipients": 0,
        "by_alert_type": {},
    }
    
    result = await db.execute(
        select(AlertNotification)
        .where(
            and_(
                AlertNotification.status == "pending",
                AlertNotification.scheduled_for >= today_start,
                AlertNotification.scheduled_for <= today_end,
            )
        )
        .options(selectinload(AlertNotification.certification))
    )
    pending_alerts = result.scalars().all()
    
    logger.info(f"Found {len(pending_alerts)} pending alerts to deliver")
    
    for alert in pending_alerts:
        summary["total_processed"] += 1
        
        alert_type = alert.alert_type or "unknown"
        if alert_type not in summary["by_alert_type"]:
            summary["by_alert_type"][alert_type] = {"processed": 0, "sent": 0, "failed": 0}
        summary["by_alert_type"][alert_type]["processed"] += 1
        
        certification = alert.certification
        if not certification:
            logger.warning(f"Alert {alert.id} has no certification, skipping")
            summary["skipped_no_recipients"] += 1
            continue
        
        subcontractor_id = certification.subcontractor_id
        users_to_notify = await _get_users_to_notify_for_subcontractor(db, subcontractor_id)
        
        if not users_to_notify:
            logger.info(f"No users to notify for alert {alert.id} (subcontractor {subcontractor_id})")
            summary["skipped_no_recipients"] += 1
            continue
        
        alert_sent = False
        for user, prefs in users_to_notify:
            success, method = await _send_alert_to_user(db, alert, user, prefs)
            if success:
                alert_sent = True
                if method == "email":
                    summary["sent_email"] += 1
                elif method == "sms":
                    summary["sent_sms"] += 1
        
        if alert_sent:
            alert.status = "sent"
            alert.sent_at = datetime.utcnow()
            summary["by_alert_type"][alert_type]["sent"] += 1
        else:
            alert.status = "failed"
            alert.error_message = "Failed to deliver to all recipients"
            summary["failed"] += 1
            summary["by_alert_type"][alert_type]["failed"] += 1
        
        await db.commit()
    
    logger.info(
        f"Alert delivery complete: processed={summary['total_processed']}, "
        f"email={summary['sent_email']}, sms={summary['sent_sms']}, "
        f"failed={summary['failed']}, skipped={summary['skipped_no_recipients']}"
    )
    
    return summary
