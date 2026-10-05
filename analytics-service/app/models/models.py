import uuid

from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, Index
from sqlalchemy.sql import func

from app.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    organization_id = Column(String(64), nullable=True, index=True)
    event_metadata = Column("event_metadata", JSON, default=dict)
    source_service = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FeatureUsageEvent(Base):
    __tablename__ = "feature_usage_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=True)
    feature_name = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_metadata = Column("event_metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


Index("idx_feature_events_feature_created", FeatureUsageEvent.feature_name, FeatureUsageEvent.created_at)
Index("idx_feature_events_user_created", FeatureUsageEvent.user_id, FeatureUsageEvent.created_at)


class SystemHealthMetric(Base):
    __tablename__ = "system_health_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_name = Column(String(100), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50), nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


Index("idx_health_metrics_service_recorded", SystemHealthMetric.service_name, SystemHealthMetric.recorded_at)
Index("idx_health_metrics_metric_recorded", SystemHealthMetric.service_name, SystemHealthMetric.metric_name, SystemHealthMetric.recorded_at)


class DashboardConfig(Base):
    __tablename__ = "dashboard_configs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(64), index=True)
    name = Column(String(255), nullable=False)
    config = Column(JSON, default=dict)
    created_by = Column(String(64), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ---------------------------------------------------------------------------
# Data Quality Monitoring (MID-626)
# ---------------------------------------------------------------------------
# Alerts are internal records only (no external notification delivery).
# Archive tables are insert-only; retention never deletes source rows.


class DataQualityAlert(Base):
    __tablename__ = "data_quality_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    source_table = Column(String(100), nullable=True, index=True)
    message = Column(String(1000), nullable=False)
    threshold_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    is_acknowledged = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AnalyticsEventArchive(Base):
    __tablename__ = "analytics_events_archive"

    id = Column(String(36), primary_key=True)
    event_type = Column(String(50), nullable=False)
    user_id = Column(String(64), nullable=True)
    organization_id = Column(String(64), nullable=True)
    event_metadata = Column("event_metadata", JSON, nullable=True)
    source_service = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now())


class FeatureUsageEventArchive(Base):
    __tablename__ = "feature_usage_events_archive"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), nullable=True)
    feature_name = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_metadata = Column("event_metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now())
