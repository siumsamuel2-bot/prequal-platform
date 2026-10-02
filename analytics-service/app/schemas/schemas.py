from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class AnalyticsEventCreate(BaseModel):
    event_type: str
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    source_service: Optional[str] = None


class AnalyticsEventResponse(BaseModel):
    id: str
    event_type: str
    user_id: Optional[str]
    organization_id: Optional[str]
    metadata: Optional[Dict[str, Any]]
    source_service: Optional[str]
    created_at: datetime


class TrackFeatureRequest(BaseModel):
    feature_name: str
    event_type: str = "action"
    metadata: Optional[Dict[str, Any]] = None


class TrackHealthRequest(BaseModel):
    service_name: str
    metric_name: str
    metric_value: float
    metric_unit: Optional[str] = None


class IngestEventBatchRequest(BaseModel):
    events: List[AnalyticsEventCreate]


class IngestConsumeResponse(BaseModel):
    ingested: int


class PilotEngagementMetrics(BaseModel):
    total_organizations: int
    active_organizations_30d: int
    total_users: Optional[int]
    active_users_30d: int
    avg_events_per_org: float
    onboarding_completion_rate: float
    feature_adoption_by_org: Dict[str, int]
    recently_active_orgs: List[Dict[str, Any]]
    engagement_trends: List[Dict[str, Any]]
