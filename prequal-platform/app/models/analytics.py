import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AnalyticsEventType(str, Enum):
    PAGE_VIEW = "page_view"
    FEATURE_USAGE = "feature_usage"
    ONBOARDING_STEP = "onboarding_step"
    CERTIFICATION_UPLOAD = "certification_upload"
    COMPLIANCE_ALERT_VIEW = "compliance_alert_view"
    SUBCONTRACTOR_ADD = "subcontractor_add"
    SUBCONTRACTOR_EDIT = "subcontractor_edit"
    SUBCONTRACTOR_DELETE = "subcontractor_delete"
    LOGIN = "login"
    LOGOUT = "logout"
    SEARCH = "search"
    EXPORT = "export"
    FEEDBACK_SUBMIT = "feedback_submit"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    event_name = Column(String(100), nullable=False)
    event_data = Column(JSON, nullable=True)
    
    page_url = Column(String(500), nullable=True)
    referrer_url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    duration_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AnalyticsEvent {self.event_type}:{self.event_name} at {self.created_at}>"


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    feedback_type = Column(String(50), nullable=False)
    rating = Column(Integer, nullable=True)
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    
    extra_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<UserFeedback {self.feedback_type} from user {self.user_id}>"