"""
Notification Delivery Log Data Schema

Tracks every email delivery attempt with full audit trail.
Used by: email notification service, analytics, compliance reporting.

Owner: Data Engineer
Last updated: 2026-05-14
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Text, DateTime, Integer, Boolean, 
    ForeignKey, Index, Enum as SQLAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class DeliveryStatus(str):
    """Delivery status pipeline values."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class NotificationDeliveryLog(Base):
    """
    Tracks every email delivery attempt with full audit trail.
    
    One row per delivery attempt. If an email is retried, each retry
    creates a new row with its own status and timestamps.
    """
    __tablename__ = "notification_delivery_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to the alert that triggered this delivery
    alert_notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("alert_notifications.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Who this notification is for
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    recipient_subcontractor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("subcontractors.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # What was sent
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True
    )
    email_subject: Mapped[Optional[str]] = mapped_column(String(500))
    email_body_html: Mapped[Optional[str]] = mapped_column(Text)
    email_body_text: Mapped[Optional[str]] = mapped_column(Text)
    
    # Delivery tracking
    status: Mapped[str] = mapped_column(String(50), default=DeliveryStatus.PENDING, nullable=False)
    
    # Provider info
    provider: Mapped[str] = mapped_column(String(100), default="smtp")  # smtp, sendgrid, postmark, etc.
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # external provider message ID
    
    # Timestamps
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Retry tracking
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    bounce_reason: Mapped[Optional[str]] = mapped_column(Text)
    bounce_code: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Rate limiting / throttling
    rate_limit_bucket: Mapped[Optional[str]] = mapped_column(String(100))  # e.g. "smtp:recipient_domain"
    rate_limit_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    delivery_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_notification_delivery_logs_status", "status"),
        Index("idx_notification_delivery_logs_alert_notification_id", "alert_notification_id"),
        Index("idx_notification_delivery_logs_recipient_email", "recipient_email"),
        Index("idx_notification_delivery_logs_created_at", "created_at"),
        Index("idx_notification_delivery_logs_provider", "provider"),
        Index("idx_notification_delivery_logs_queued_at", "queued_at"),
    )
