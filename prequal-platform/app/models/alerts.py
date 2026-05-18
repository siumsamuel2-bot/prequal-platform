import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class AlertConfig(Base):
    """
    Sprint 2: Centralized alert configuration per user/org.
    Complements AlertPreference which stores granular user-level preferences.
    """
    __tablename__ = "alert_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    alert_logs: Mapped[List["AlertLog"]] = relationship(
        "AlertLog", back_populates="alert_config", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_alert_configs_user_id", "user_id"),
        Index("idx_alert_configs_org_id", "org_id"),
        Index("idx_alert_configs_active", "is_active"),
    )


class AlertLog(Base):
    """
    Sprint 2: Audit trail for every alert that is sent, failed, or bounced.
    Bridges alert_notifications and notification_delivery_logs.
    """
    __tablename__ = "alert_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    subcontractor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subcontractors.id", ondelete="SET NULL"),
        nullable=True,
    )
    certification_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # email, sms, in_app
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, sent, failed, bounced
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    alert_config: Mapped["AlertConfig"] = relationship("AlertConfig", back_populates="alert_logs")

    __table_args__ = (
        Index("idx_alert_logs_alert_config_id", "alert_config_id"),
        Index("idx_alert_logs_subcontractor_id", "subcontractor_id"),
        Index("idx_alert_logs_certification_id", "certification_id"),
        Index("idx_alert_logs_status", "status"),
        Index("idx_alert_logs_sent_at", "sent_at"),
    )
