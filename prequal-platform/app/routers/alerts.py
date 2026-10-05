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
    AlertPreferenceCreate, AlertPreferenceResponse,
    NotificationPreferencesUpdate, NotificationPreferencesResponse,
    RecentAlert
)
from app.services.alert_service import scan_expirations, get_alert_summary, deliver_pending_alerts
from app.services.analytics_pipeline import get_recent_alerts
from app.routers.auth import get_current_user, TokenData
from app.models.auth import TeamMember

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# -----------------------------------------------------------------------
# Tenant isolation helpers (MID-546 / HIGH-3)
# -----------------------------------------------------------------------

async def _resolve_caller_team_id(
    db: AsyncSession, current_user: TokenData
) -> Optional[UUID]:
    """Resolve the calling user's team for tenant scoping.

    Returns None for admins (unscoped access) and for non-admin users with
    no team membership — the latter case must be treated as "no access" by the
    caller, not as "unscoped". Use `_caller_can_see_all` to distinguish.

    The live `team_members` table is the source of truth; the JWT `team_id`
    claim may be stale if a user has changed teams since token issue.
    """
    if getattr(current_user, "role", "viewer") == "admin":
        return None
    user_id_str = getattr(current_user, "user_id", None)
    if not user_id_str:
        return None
    result = await db.execute(
        select(TeamMember.team_id).where(TeamMember.user_id == UUID(user_id_str))
    )
    return result.scalar_one_or_none()


def _caller_is_admin(current_user: TokenData) -> bool:
    return getattr(current_user, "role", "viewer") == "admin"


def _tenant_alert_predicate(team_id: UUID):
    """SQL predicate scoping AlertNotification rows to a single team.

    AlertNotification -> Certification -> Subcontractor (team_id).
    """
    return AlertNotification.certification_id.in_(
        select(Certification.id).where(
            Certification.subcontractor_id.in_(
                select(Subcontractor.id).where(Subcontractor.team_id == team_id)
            )
        )
    )


async def _assert_alert_in_team_scope(
    db: AsyncSession, team_id: UUID, alert: AlertNotification
) -> None:
    """Raise 404 if the alert's certificate chain is outside the caller's team.

    404 (not 403) so existence of cross-tenant alerts is not revealed.
    """
    result = await db.execute(
        select(AlertNotification.id).where(
            AlertNotification.id == alert.id,
            _tenant_alert_predicate(team_id),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )



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
    """List alerts with optional filtering.

    MID-546 (HIGH-3): tenant isolation. Non-admin users only see alerts whose
    certification chain belongs to their team. Non-admin users with no team
    membership see nothing. Admins remain unscoped.
    """
    query = select(AlertNotification).order_by(desc(AlertNotification.scheduled_for))

    if not _caller_is_admin(current_user):
        team_id = await _resolve_caller_team_id(db, current_user)
        if team_id is None:
            # Non-admin caller with no team: no accessible alerts
            return []
        query = query.where(_tenant_alert_predicate(team_id))
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
    """Get alerts for a specific contractor (subcontractor).

    MID-546 (HIGH-3): returns 404 when the contractor is outside the caller's
    team so cross-tenant enumeration is not possible.
    """
    # Tenant isolation: contractor must belong to caller's team (unless admin)
    if not _caller_is_admin(current_user):
        team_id = await _resolve_caller_team_id(db, current_user)
        if team_id is None:
            return []
        scope_result = await db.execute(
            select(Subcontractor.id).where(
                Subcontractor.id == contractor_id,
                Subcontractor.team_id == team_id,
            )
        )
        if scope_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found"
            )

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
    """Get alerts for a specific project.

    MID-546 (HIGH-3): returns 404 when the project is outside the caller's team
    so cross-tenant enumeration is not possible.
    """
    # Tenant isolation: project must belong to caller's team (unless admin)
    if not _caller_is_admin(current_user):
        team_id = await _resolve_caller_team_id(db, current_user)
        if team_id is None:
            return []
        scope_result = await db.execute(
            select(Project.id).where(
                Project.id == project_id,
                Project.team_id == team_id,
            )
        )
        if scope_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

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

    # MID-546 (HIGH-3): tenant isolation — non-admins may only acknowledge
    # alerts within their own team's certification chain.
    if not _caller_is_admin(current_user):
        team_id = await _resolve_caller_team_id(db, current_user)
        if team_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
            )
        await _assert_alert_in_team_scope(db, team_id, alert)

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


@router.post("/deliver", status_code=status.HTTP_202_ACCEPTED)
async def trigger_delivery(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Trigger delivery of all pending alerts (for testing / admin use)."""
    summary = await deliver_pending_alerts(db)
    return {
        "message": "Alert delivery completed",
        "summary": summary
    }


@router.get("/summary")
async def get_alerts_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get a summary of alert counts for a time window.

    MID-546 (HIGH-3): non-admin callers get counts scoped to their team;
    admins get the platform-wide view.
    """
    team_id = None if _caller_is_admin(current_user) else await _resolve_caller_team_id(db, current_user)
    if not _caller_is_admin(current_user) and team_id is None:
        # Non-admin caller with no team: empty, scoped summary
        return {
            "pending_alerts": 0,
            "acknowledged_alerts": 0,
            "expired_certifications": 0,
            "lookback_days": days,
        }
    summary = await get_alert_summary(db, days=days, team_id=team_id)
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


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    prefs_update: NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Create or update notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == UUID(current_user.user_id)
        )
    )
    db_prefs = result.scalar_one_or_none()
    
    if db_prefs:
        update_data = prefs_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_prefs, field, value)
    else:
        db_prefs = NotificationPreferences(
            user_id=UUID(current_user.user_id),
            notify_on_cert_expiration=prefs_update.notify_on_cert_expiration if prefs_update.notify_on_cert_expiration is not None else True,
            notify_on_cert_expiration_days=prefs_update.notify_on_cert_expiration_days if prefs_update.notify_on_cert_expiration_days is not None else [30, 14, 7],
            notify_on_violation=prefs_update.notify_on_violation if prefs_update.notify_on_violation is not None else True,
            notify_on_renewal_request=prefs_update.notify_on_renewal_request if prefs_update.notify_on_renewal_request is not None else True,
            notify_on_renewal_approved=prefs_update.notify_on_renewal_approved if prefs_update.notify_on_renewal_approved is not None else False,
            email_enabled=prefs_update.email_enabled if prefs_update.email_enabled is not None else True,
            sms_enabled=prefs_update.sms_enabled if prefs_update.sms_enabled is not None else False,
            in_app_enabled=prefs_update.in_app_enabled if prefs_update.in_app_enabled is not None else True,
            custom_email=prefs_update.custom_email,
            custom_phone=prefs_update.custom_phone,
            digest_enabled=prefs_update.digest_enabled if prefs_update.digest_enabled is not None else False,
            digest_frequency=prefs_update.digest_frequency if prefs_update.digest_frequency is not None else "daily",
            digest_day_of_week=prefs_update.digest_day_of_week,
            digest_hour=prefs_update.digest_hour if prefs_update.digest_hour is not None else 9,
            quiet_hours_start=prefs_update.quiet_hours_start,
            quiet_hours_end=prefs_update.quiet_hours_end,
            quiet_hours_timezone=prefs_update.quiet_hours_timezone if prefs_update.quiet_hours_timezone is not None else "UTC",
            language=prefs_update.language if prefs_update.language is not None else "en",
            max_emails_per_hour=prefs_update.max_emails_per_hour if prefs_update.max_emails_per_hour is not None else 10,
            max_emails_per_day=prefs_update.max_emails_per_day if prefs_update.max_emails_per_day is not None else 50,
        )
        db.add(db_prefs)
    
    await db.commit()
    await db.refresh(db_prefs)
    return db_prefs


@router.get("/recent", response_model=list[RecentAlert])
async def alerts_recent(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict]:
    """Return recent alert log entries backed by mv_recent_alerts.

    MID-546 (HIGH-3): non-admin callers are scoped to their team; admins get
    the platform-wide view.
    """
    if _caller_is_admin(current_user):
        team_id = None
    else:
        team_id = await _resolve_caller_team_id(db, current_user)
        if team_id is None:
            return []
    data = await get_recent_alerts(db, status=status, limit=limit, offset=offset, team_id=team_id)
    return [RecentAlert(**row).model_dump() for row in data]
