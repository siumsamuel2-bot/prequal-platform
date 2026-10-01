import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analytics import AnalyticsEvent, UserFeedback, AnalyticsEventType
from app.models.auth import User
from app.routers.auth import get_current_user, TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class AnalyticsEventCreate(BaseModel):
    event_type: str
    event_name: str
    event_data: Optional[dict] = None
    page_url: Optional[str] = None
    referrer_url: Optional[str] = None
    duration_ms: Optional[int] = None


class AnalyticsEventResponse(BaseModel):
    id: str
    event_type: str
    event_name: str
    event_data: Optional[dict] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    page_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    feedback_type: str = Field(..., description="Type: feature_request, bug_report, general, rating")
    rating: Optional[int] = Field(None, ge=1, le=5)
    subject: Optional[str] = Field(None, max_length=200)
    body: str
    extra_data: Optional[dict] = None


class FeedbackResponse(BaseModel):
    id: str
    feedback_type: str
    rating: Optional[int] = None
    subject: Optional[str] = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_events: int
    unique_users: int
    total_feedback: int
    average_rating: Optional[float] = None
    events_by_type: dict
    recent_events: List[AnalyticsEventResponse]
    events_today: int
    events_this_week: int


@router.post("/events", status_code=201)
async def track_event(
    event: AnalyticsEventCreate,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500] if request.headers.get("user-agent") else None
    
    user = None
    org_id = None
    if current_user.user_id:
        result = await db.execute(select(User).where(User.id == UUID(current_user.user_id)))
        user = result.scalar_one_or_none()
        if user:
            org_id = user.org_id

    db_event = AnalyticsEvent(
        event_type=event.event_type,
        event_name=event.event_name,
        event_data=event.event_data,
        user_id=UUID(current_user.user_id) if current_user.user_id else None,
        organization_id=org_id,
        page_url=event.page_url[:500] if event.page_url else None,
        referrer_url=event.referrer_url[:500] if event.referrer_url else None,
        user_agent=user_agent,
        ip_address=client_ip,
        duration_ms=event.duration_ms
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    
    return {"id": str(db_event.id), "status": "recorded"}


@router.get("/events", response_model=list[AnalyticsEventResponse])
async def get_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = select(AnalyticsEvent).where(AnalyticsEvent.created_at >= cutoff)
    
    if event_type:
        query = query.where(AnalyticsEvent.event_type == event_type)
    if user_id:
        query = query.where(AnalyticsEvent.user_id == UUID(user_id))
    
    query = query.order_by(desc(AnalyticsEvent.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [
        AnalyticsEventResponse(
            id=str(e.id),
            event_type=e.event_type,
            event_name=e.event_name,
            event_data=e.event_data,
            user_id=str(e.user_id) if e.user_id else None,
            organization_id=str(e.organization_id) if e.organization_id else None,
            page_url=e.page_url,
            created_at=e.created_at
        )
        for e in events
    ]


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    total_result = await db.execute(select(func.count(AnalyticsEvent.id)))
    total_events = total_result.scalar() or 0
    
    unique_users_result = await db.execute(
        select(func.count(func.distinct(AnalyticsEvent.user_id)))
    )
    unique_users = unique_users_result.scalar() or 0
    
    events_today_result = await db.execute(
        select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.created_at >= today_start)
    )
    events_today = events_today_result.scalar() or 0
    
    events_week_result = await db.execute(
        select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.created_at >= week_start)
    )
    events_this_week = events_week_result.scalar() or 0
    
    type_counts_result = await db.execute(
        select(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .group_by(AnalyticsEvent.event_type)
    )
    events_by_type = {row[0]: row[1] for row in type_counts_result.all()}
    
    recent_result = await db.execute(
        select(AnalyticsEvent)
        .order_by(desc(AnalyticsEvent.created_at))
        .limit(10)
    )
    recent_events = recent_result.scalars().all()
    
    total_feedback_result = await db.execute(select(func.count(UserFeedback.id)))
    total_feedback = total_feedback_result.scalar() or 0
    
    avg_rating_result = await db.execute(
        select(func.avg(UserFeedback.rating)).where(UserFeedback.rating.isnot(None))
    )
    average_rating = avg_rating_result.scalar()
    
    return AnalyticsSummary(
        total_events=total_events,
        unique_users=unique_users,
        total_feedback=total_feedback,
        average_rating=round(average_rating, 2) if average_rating else None,
        events_by_type=events_by_type,
        recent_events=[
            AnalyticsEventResponse(
                id=str(e.id),
                event_type=e.event_type,
                event_name=e.event_name,
                event_data=e.event_data,
                user_id=str(e.user_id) if e.user_id else None,
                organization_id=str(e.organization_id) if e.organization_id else None,
                page_url=e.page_url,
                created_at=e.created_at
            )
            for e in recent_events
        ],
        events_today=events_today,
        events_this_week=events_this_week
    )


@router.post("/feedback", status_code=201)
async def submit_feedback(
    feedback: FeedbackCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user = None
    org_id = None
    if current_user.user_id:
        result = await db.execute(select(User).where(User.id == UUID(current_user.user_id)))
        user = result.scalar_one_or_none()
        if user:
            org_id = user.org_id
    
    db_feedback = UserFeedback(
        user_id=UUID(current_user.user_id) if current_user.user_id else None,
        organization_id=org_id,
        feedback_type=feedback.feedback_type,
        rating=feedback.rating,
        subject=feedback.subject,
        body=feedback.body,
        extra_data=feedback.extra_data
    )
    db.add(db_feedback)
    await db.commit()
    await db.refresh(db_feedback)
    
    return {"id": str(db_feedback.id), "status": "submitted"}


@router.get("/feedback", response_model=list[FeedbackResponse])
async def get_feedback(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    feedback_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    query = select(UserFeedback)
    
    if feedback_type:
        query = query.where(UserFeedback.feedback_type == feedback_type)
    
    query = query.order_by(desc(UserFeedback.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    feedback_items = result.scalars().all()
    
    return [
        FeedbackResponse(
            id=str(f.id),
            feedback_type=f.feedback_type,
            rating=f.rating,
            subject=f.subject,
            body=f.body,
            created_at=f.created_at
        )
        for f in feedback_items
    ]


class FeatureAdoptionResponse(BaseModel):
    feature_name: str
    event_date: Optional[str] = None
    total_events: int
    unique_users: int
    view_count: int
    action_count: int
    export_count: int
    computed_at: Optional[str] = None


class SystemHealthResponse(BaseModel):
    service_name: str
    metric_name: str
    metric_unit: Optional[str] = None
    avg_value: float
    min_value: float
    max_value: float
    p95_value: float
    total_count: int
    computed_at: Optional[str] = None


class PerformanceMetricsResponse(BaseModel):
    requests_per_second: float
    error_rate_percent: float
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    active_db_connections: int
    max_db_connections: int
    active_requests: int
    rate_limit_hits: int
    computed_at: Optional[str] = None


class RecentlyActiveOrg(BaseModel):
    organization_id: str
    organization_name: str
    last_activity: str


class EngagementTrendPoint(BaseModel):
    date: str
    active_organizations: int
    total_events: int


class PilotEngagementResponse(BaseModel):
    total_organizations: int
    active_organizations_30d: int
    total_users: int
    active_users_30d: int
    avg_events_per_org: float
    onboarding_completion_rate: float
    feature_adoption_by_org: dict
    recently_active_orgs: list[RecentlyActiveOrg]
    engagement_trends: list[EngagementTrendPoint]


@router.get("/feature-adoption", response_model=list[FeatureAdoptionResponse])
async def get_feature_adoption(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    feature_name: Optional[str] = None,
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    from app.services.analytics_pipeline import get_feature_adoption_summary
    data = await get_feature_adoption_summary(
        db,
        feature_name=feature_name,
        days=days,
        limit=limit,
        offset=skip
    )
    return [
        FeatureAdoptionResponse(
            feature_name=row["feature_name"],
            event_date=row.get("event_date"),
            total_events=row.get("total_events", 0),
            unique_users=row.get("unique_users", 0),
            view_count=row.get("view_count", 0),
            action_count=row.get("action_count", 0),
            export_count=row.get("export_count", 0),
            computed_at=row.get("computed_at")
        )
        for row in data
    ]


@router.get("/system-health", response_model=list[SystemHealthResponse])
async def get_system_health(
    service_name: Optional[str] = None,
    metric_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    from app.services.analytics_pipeline import get_system_health_summary
    data = await get_system_health_summary(
        db,
        service_name=service_name,
        metric_name=metric_name
    )
    return [
        SystemHealthResponse(
            service_name=row["service_name"],
            metric_name=row["metric_name"],
            metric_unit=row.get("metric_unit"),
            avg_value=row.get("avg_value", 0.0),
            min_value=row.get("min_value", 0.0),
            max_value=row.get("max_value", 0.0),
            p95_value=row.get("p95_value", 0.0),
            total_count=row.get("total_count", 0),
            computed_at=row.get("computed_at")
        )
        for row in data
    ]


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    result = await db.execute(
        text("""
            SELECT
                metric_name,
                avg_value,
                p95_value
            FROM mv_system_health_summary
            WHERE service_name = 'prequal-api'
            AND metric_name IN ('requests_per_second', 'error_rate_percent', 'response_time_ms', 'db_connections_active', 'active_requests', 'rate_limit_hits')
        """)
    )
    rows = {row[0]: row[1:] for row in result.all()}

    requests_per_second = rows.get('requests_per_second', (0.0,))[0] if 'requests_per_second' in rows else 0.0
    error_rate = rows.get('error_rate_percent', (0.0,))[0] if 'error_rate_percent' in rows else 0.0
    response_time_row = rows.get('response_time_ms', (0.0, 0.0))
    p50_response = response_time_row[0] if response_time_row else 0.0
    p95_response = response_time_row[1] if response_time_row else 0.0

    db_conn_row = rows.get('db_connections_active', (0, 0))
    active_db = db_conn_row[0] if db_conn_row else 0
    max_db_result = await db.execute(text("SELECT setting FROM pg_settings WHERE name = 'max_connections'"))
    max_db = int(max_db_result.scalar() or 100)

    active_req_row = rows.get('active_requests', (0,))
    active_requests = active_req_row[0] if active_req_row else 0

    rate_limit_row = rows.get('rate_limit_hits', (0,))
    rate_limit_hits = rate_limit_row[0] if rate_limit_row else 0

    return PerformanceMetricsResponse(
        requests_per_second=round(requests_per_second, 4),
        error_rate_percent=round(error_rate, 4),
        avg_response_time_ms=round(p50_response, 2),
        p50_response_time_ms=round(p50_response, 2),
        p95_response_time_ms=round(p95_response, 2),
        p99_response_time_ms=round(p95_response * 1.5, 2),
        active_db_connections=active_db,
        max_db_connections=max_db,
        active_requests=active_requests,
        rate_limit_hits=rate_limit_hits,
        computed_at=datetime.utcnow().isoformat()
    )


@router.get("/pilot-engagement", response_model=PilotEngagementResponse)
async def get_pilot_engagement(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    from app.models.auth import Organization, User
    
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    
    total_orgs_result = await db.execute(select(func.count(Organization.id)))
    total_orgs = total_orgs_result.scalar() or 0
    
    active_orgs_result = await db.execute(
        select(func.count(func.distinct(AnalyticsEvent.organization_id)))
        .where(AnalyticsEvent.created_at >= cutoff)
        .where(AnalyticsEvent.organization_id.isnot(None))
    )
    active_orgs_30d = active_orgs_result.scalar() or 0
    
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.org_id.isnot(None))
    )
    total_users = total_users_result.scalar() or 0
    
    active_users_result = await db.execute(
        select(func.count(func.distinct(AnalyticsEvent.user_id)))
        .where(AnalyticsEvent.created_at >= cutoff)
        .where(AnalyticsEvent.user_id.isnot(None))
    )
    active_users_30d = active_users_result.scalar() or 0
    
    total_events_result = await db.execute(
        select(func.count(AnalyticsEvent.id))
        .where(AnalyticsEvent.created_at >= cutoff)
    )
    total_events_30d = total_events_result.scalar() or 0
    
    avg_events = total_events_30d / active_orgs_30d if active_orgs_30d > 0 else 0
    
    onboarding_events_result = await db.execute(
        select(func.count(AnalyticsEvent.id))
        .where(AnalyticsEvent.created_at >= cutoff)
        .where(AnalyticsEvent.event_type == 'onboarding_completion')
    )
    onboarding_events = onboarding_events_result.scalar() or 0
    onboarding_completion_rate = (onboarding_events / active_orgs_30d * 100) if active_orgs_30d > 0 else 0
    
    adoption_result = await db.execute(
        select(
            AnalyticsEvent.organization_id,
            AnalyticsEvent.event_type,
            func.count(AnalyticsEvent.id).label('count')
        )
        .where(AnalyticsEvent.created_at >= cutoff)
        .where(AnalyticsEvent.organization_id.isnot(None))
        .group_by(AnalyticsEvent.organization_id, AnalyticsEvent.event_type)
    )
    adoption_by_org: dict = {}
    for row in adoption_result.all():
        org_id = str(row[0]) if row[0] else 'unknown'
        if org_id not in adoption_by_org:
            adoption_by_org[org_id] = 0
        adoption_by_org[org_id] += row[2]
    
    recent_orgs_result = await db.execute(
        select(
            AnalyticsEvent.organization_id,
            func.max(AnalyticsEvent.created_at).label('last_activity')
        )
        .where(AnalyticsEvent.created_at >= cutoff)
        .where(AnalyticsEvent.organization_id.isnot(None))
        .group_by(AnalyticsEvent.organization_id)
        .order_by(func.max(AnalyticsEvent.created_at).desc())
        .limit(10)
    )
    recently_active_orgs = []
    for row in recent_orgs_result.all():
        org_id = row[0]
        last_activity = row[1]
        org_result = await db.execute(select(Organization.name).where(Organization.id == org_id))
        org_name = org_result.scalar_one_or_none()
        if org_name:
            recently_active_orgs.append(RecentlyActiveOrg(
                organization_id=str(org_id),
                organization_name=org_name,
                last_activity=last_activity.isoformat() if last_activity else ""
            ))
    
    trends = []
    for i in range(min(days, 7)):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_orgs_result = await db.execute(
            select(func.count(func.distinct(AnalyticsEvent.organization_id)))
            .where(AnalyticsEvent.created_at >= day_start)
            .where(AnalyticsEvent.created_at < day_end)
            .where(AnalyticsEvent.organization_id.isnot(None))
        )
        day_orgs = day_orgs_result.scalar() or 0
        
        day_events_result = await db.execute(
            select(func.count(AnalyticsEvent.id))
            .where(AnalyticsEvent.created_at >= day_start)
            .where(AnalyticsEvent.created_at < day_end)
        )
        day_events = day_events_result.scalar() or 0
        
        trends.append(EngagementTrendPoint(
            date=day.strftime("%Y-%m-%d"),
            active_organizations=day_orgs,
            total_events=day_events
        ))
    
    trends.reverse()
    
    return PilotEngagementResponse(
        total_organizations=total_orgs,
        active_organizations_30d=active_orgs_30d,
        total_users=total_users,
        active_users_30d=active_users_30d,
        avg_events_per_org=round(avg_events, 2),
        onboarding_completion_rate=round(onboarding_completion_rate, 2),
        feature_adoption_by_org=adoption_by_org,
        recently_active_orgs=recently_active_orgs,
        engagement_trends=trends
    )