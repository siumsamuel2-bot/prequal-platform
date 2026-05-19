"""Alerting REST endpoints for certification expiration monitoring.

Provides endpoints to:
- List all alerts with filtering and pagination
- Get alerts by contractor (subcontractor)
- Get alerts by project
- Acknowledge an alert
- Trigger a manual expiration scan
- Manage alert preferences
"""

from datetime import date, timedelta, datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.compliance import (
    AlertNotification, Certification, Subcontractor,
    ProjectSubcontractor, Project, AlertPreference, NotificationPreferences
)
from app.schemas.compliance import (
    AlertNotificationResponse, AlertNotificationStatus,
    AlertNotificationUpdate, AlertNotificationCreate, AlertWithContextResponse,
    AlertPreferenceCreate, AlertPreferenceResponse
)
from app.services.alert_service import scan_expirations, get_alert_summary
from app.routers.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# -----------------------------------------------------------------------
# Internal helper for building enriched alert responses
# -----------------------------------------------------------------------

async def _enrich_alert_row(
    db: AsyncSession,
    alert: AlertNotification
) -> dict:
    """Enrich an AlertNotification with contractor and project context."""
    # Get certification details
    cert_result = await db.execute(
        select(Certification)
        .where(Certification.id == alert.certification_id)
    )
    cert = cert_result.scalar_one_or_none()

    contractor_name = None
    project_ids = []

    if cert:
        sub_result = await db.execute(
            select(Subcontractor.company_name)
            .where(Subcontractor.id == cert.subcontractor_id)
        )
        row = sub_result.first()
        contractor_name = row[0] if row else None

        proj_result = await db.execute(
            select(ProjectSubcontractor.project_id)
            .where(
                ProjectSubcontractor.subcontractor_id == cert.subcontractor_id,
                ProjectSubcontractor.status == "active"
            )
        )
        project_ids = [row[0] for row in proj_result.all()]

    return {
        "id": str(alert.id),
        "certification_id": str(alert.certification_id),
        "alert_type": alert.alert_type,
        "scheduled_for": alert.scheduled_for,
        "sent_at": alert.sent_at,
        "status": alert.status,
        "method": alert.method,
        "recipient": alert.recipient,
        "subject": alert.subject,
        "body": alert.body,
        "retry_count": alert.retry_count,
        "max_retries": alert.max_retries,
        "error_message": alert.error_message,
        "acknowledged_at": alert.acknowledged_at,
        "days_until_expiration": alert.days_until_expiration,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
        "contractor_name": contractor_name,
        "project_ids": [str(pid) for pid in project_ids] if project_ids else []
    }


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.get("", response_model=List[AlertNotificationResponse])
async def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[AlertNotificationStatus] = None,
    alert_type: Optional[str] = None,
    days_until: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """List all alerts with optional filtering."""
    query = select(AlertNotification).order_by(desc(AlertNotification.scheduled_for))

    if status_filter:
        query = query.where(AlertNotification.status == status_filter.value)
    if alert_type:
        query = query.where(AlertNotification.alert_type == alert_type)
    if days_until is not None:
        query = query.where(AlertNotification.days_until_expiration == days_until)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return alerts


@router.get("/by-contractor/{contractor_id}", response_model=List[AlertWithContextResponse])
async def get_alerts_by_contractor(
    contractor_id: UUID,
    status_filter: Optional[AlertNotificationStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get alerts for a specific contractor (subcontractor)."""
    # First find all certifications for this contractor
    cert_result = await db.execute(
        select(Certification.id).where(Certification.subcontractor_id == contractor_id)
    )
    cert_ids = [row[0] for row in cert_result.all()]

    if not cert_ids:
        return []

    query = (
        select(AlertNotification)
        .where(AlertNotification.certification_id.in_(cert_ids))
        .order_by(desc(AlertNotification.scheduled_for))
    )

    if status_filter:
        query = query.where(AlertNotification.status == status_filter.value)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return [await _enrich_alert_row(db, alert) for alert in alerts]


@router.get("/by-project/{project_id}", response_model=List[AlertWithContextResponse])
async def get_alerts_by_project(
    project_id: UUID,
    status_filter: Optional[AlertNotificationStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get alerts for a specific project."""
    # Find all subcontractors on this project
    ps_result = await db.execute(
        select(ProjectSubcontractor.subcontractor_id)
        .where(
            ProjectSubcontractor.project_id == project_id,
            ProjectSubcontractor.status == "active"
        )
    )
    subcontractor_ids = [row[0] for row in ps_result.all()]

    if not subcontractor_ids:
        return []

    # Find all certs for these subcontractors
    cert_result = await db.execute(
        select(Certification.id)
        .where(Certification.subcontractor_id.in_(subcontractor_ids))
    )
    cert_ids = [row[0] for row in cert_result.all()]

    if not cert_ids:
        return []

    query = (
        select(AlertNotification)
        .where(AlertNotification.certification_id.in_(cert_ids))
        .order_by(desc(AlertNotification.scheduled_for))
    )

    if status_filter:
        query = query.where(AlertNotification.status == status_filter.value)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return [await _enrich_alert_row(db, alert) for alert in alerts]


@router.patch("/{alert_id}/acknowledge", response_model=AlertNotificationResponse)
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Acknowledge an alert, marking it as resolved."""
    result = await db.execute(
        select(AlertNotification).where(AlertNotification.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    if alert.status == "acknowledged":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert already acknowledged"
        )

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now()

    await db.commit()
    await db.refresh(alert)

    return alert


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Trigger a manual expiration scan (for testing / admin use)."""
    summary = await scan_expirations(db)
    return {
        "message": "Expiration scan completed",
        "summary": summary
    }


@router.get("/summary")
async def get_alerts_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get a summary of alert counts for a time window."""
    summary = await get_alert_summary(db, days=days)
    return summary


@router.get("/preferences", response_model=AlertPreferenceResponse)
async def get_alert_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get alert preferences for the current user."""
    result = await db.execute(
        select(AlertPreference).where(AlertPreference.user_id == UUID(current_user.user_id))
    )
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        prefs = AlertPreference(
            user_id=UUID(current_user.user_id),
            certification_types=None,
            advance_notice_days=30,
            alert_methods=["email"],
            is_active=True
        )
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    
    return prefs


@router.post("/preferences", response_model=AlertPreferenceResponse)
async def update_alert_preferences(
    prefs: AlertPreferenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Create or update alert preferences for the current user."""
    result = await db.execute(
        select(AlertPreference).where(AlertPreference.user_id == UUID(current_user.user_id))
    )
    db_prefs = result.scalar_one_or_none()
    
    if db_prefs:
        db_prefs.certification_types = prefs.certification_types
        db_prefs.advance_notice_days = prefs.advance_notice_days
        db_prefs.alert_methods = prefs.alert_methods
        db_prefs.is_active = prefs.is_active
    else:
        db_prefs = AlertPreference(
            user_id=UUID(current_user.user_id),
            certification_types=prefs.certification_types,
            advance_notice_days=prefs.advance_notice_days,
            alert_methods=prefs.alert_methods,
            is_active=prefs.is_active
        )
        db.add(db_prefs)
    
    await db.commit()
    await db.refresh(db_prefs)
    return db_prefs


@router.get("/notification-preferences", response_model=dict)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get full notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == UUID(current_user.user_id)
        )
    )
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        return {
            "notify_on_cert_expiration": True,
            "notify_on_cert_expiration_days": [30, 14, 7],
            "notify_on_violation": True,
            "email_enabled": True,
            "sms_enabled": False
        }
    
    return {
        "notify_on_cert_expiration": prefs.notify_on_cert_expiration,
        "notify_on_cert_expiration_days": prefs.notify_on_cert_expiration_days,
        "notify_on_violation": prefs.notify_on_violation,
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "digest_enabled": prefs.digest_enabled,
        "digest_frequency": prefs.digest_frequency
    }
