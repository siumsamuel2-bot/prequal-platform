"""Analytics ingestion endpoints (stream publishing + consumer drain)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import IngestConsumeResponse, IngestEventBatchRequest, TrackFeatureRequest, TrackHealthRequest
from app.services.ingestion import AnalyticsIngestionService, IngestionConsumer
from app.services.service_auth import UserContext, get_user_context, require_service_auth

router = APIRouter()


@router.post("/ingestion/events")
def ingest_events(
    batch: IngestEventBatchRequest,
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Ingest a batch of analytics events via the event pipeline.

    Events are published to the Redis stream when available, otherwise written
    directly to the analytics database. Internal callers use service auth.
    """
    service = AnalyticsIngestionService(db)
    result = service.ingest_event_batch([e.model_dump() for e in batch.events])
    return result


@router.post("/ingestion/consume", response_model=IngestConsumeResponse)
def consume_events(
    max_count: int = Query(default=100, ge=1, le=10000),
    _: None = Depends(require_service_auth),
):
    """Drain the analytics events stream into the database (service callers only)."""
    consumer = IngestionConsumer()
    ingested = consumer.consume(max_count=max_count)
    return IngestConsumeResponse(ingested=ingested)


@router.post("/track-feature")
def track_feature(
    request: TrackFeatureRequest,
    context: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
):
    """Track a feature usage event."""
    service = AnalyticsIngestionService(db)
    event_id = service.track_feature_event(
        request.feature_name,
        request.event_type,
        user_id=context.user_id,
        organization_id=context.organization_id,
        metadata=request.metadata,
    )
    return {"status": "tracked", "event_id": event_id}


@router.post("/track-health")
def track_health(
    request: TrackHealthRequest,
    _: None = Depends(require_service_auth),
    db: Session = Depends(get_db),
):
    """Track a system health metric (service callers only)."""
    service = AnalyticsIngestionService(db)
    metric_id = service.track_system_health_metric(
        request.service_name,
        request.metric_name,
        request.metric_value,
        request.metric_unit,
    )
    return {"status": "tracked", "metric_id": metric_id}
