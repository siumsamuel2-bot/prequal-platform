"""Analytics events endpoints (migrated from the monolith, MID-588)."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AnalyticsEvent, DashboardConfig
from app.schemas.schemas import AnalyticsEventCreate, AnalyticsEventResponse
from app.services.ingestion import AnalyticsIngestionService
from app.services.service_auth import UserContext, get_user_context, require_service_auth

router = APIRouter()


def _to_response(event: AnalyticsEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "user_id": event.user_id,
        "organization_id": event.organization_id,
        "metadata": event.event_metadata,
        "source_service": event.source_service,
        "created_at": event.created_at,
    }


@router.post("/events", response_model=AnalyticsEventResponse, status_code=status.HTTP_201_CREATED)
def create_analytics_event(
    event: AnalyticsEventCreate,
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Create an analytics event.

    User context is propagated from the gateway after session validation.
    Non-admin callers are pinned to their own organization.
    """
    user_id = event.user_id or context.user_id
    organization_id = event.organization_id or context.organization_id
    if context.user_role != "admin":
        organization_id = context.organization_id
    service = AnalyticsIngestionService(db)
    result = service.ingest_event(
        event_type=event.event_type,
        user_id=user_id,
        organization_id=organization_id,
        metadata=event.metadata,
        source_service=event.source_service,
    )
    if result["mode"] == "stream":
        return AnalyticsEventResponse(
            id="pending",
            event_type=event.event_type,
            user_id=user_id,
            organization_id=organization_id,
            metadata=event.metadata,
            source_service=event.source_service,
            created_at=datetime.utcnow(),
        )
    db_event = db.query(AnalyticsEvent).filter(AnalyticsEvent.id == result["event_id"]).first()
    return _to_response(db_event)


@router.get("/events", response_model=List[AnalyticsEventResponse])
def get_analytics_events(
    organization_id: Optional[str] = None,
    event_type: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """List analytics events. Non-admin callers are scoped to their organization."""
    if context.user_role != "admin":
        organization_id = context.organization_id
    query = db.query(AnalyticsEvent)
    if organization_id:
        query = query.filter(AnalyticsEvent.organization_id == organization_id)
    if event_type:
        query = query.filter(AnalyticsEvent.event_type == event_type)
    query = query.filter(AnalyticsEvent.created_at >= datetime.utcnow() - timedelta(days=days))
    events = query.order_by(AnalyticsEvent.created_at.desc()).offset(skip).limit(limit).all()
    return [_to_response(e) for e in events]


@router.get("/dashboard-configs")
def list_dashboard_configs(
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """List dashboard configurations for the caller's organization (admins see all)."""
    query = db.query(DashboardConfig)
    if context.user_role != "admin":
        query = query.filter(DashboardConfig.organization_id == context.organization_id)
    configs = query.order_by(DashboardConfig.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "organization_id": c.organization_id,
            "name": c.name,
            "config": c.config,
            "created_by": c.created_by,
            "created_at": c.created_at,
        }
        for c in configs
    ]


@router.post("/dashboard-configs", status_code=status.HTTP_201_CREATED)
def create_dashboard_config(
    name: str,
    config: Optional[dict] = None,
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Create a dashboard configuration for the caller's organization."""
    row = DashboardConfig(
        organization_id=context.organization_id,
        name=name,
        config=config or {},
        created_by=context.user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "name": row.name,
        "config": row.config,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }
