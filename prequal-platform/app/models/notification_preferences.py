"""
Notification Preferences Data Schema

Per-user and per-subcontractor notification preferences.
Controls what alerts get sent, how, and when.

Owner: Data Engineer
Last updated: 2026-05-14
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Text, DateTime, Integer, Boolean, 
    ForeignKey, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class NotificationPreferences(Base):
    """
    Per-user and per-subcontractor notification preferences.
    
    A user can have preferences for their own account, or for
    subcontractors they manage. The user_id is the owner of
    the preference record, and subcontractor_id is the target
    (if null, the preference applies to the user themselves).
    """
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who owns this preference
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Which subcontractor this applies to (null = user themselves)
    subcontractor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("subcontractors.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # What to notify about
    notify_on_cert_expiration: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_cert_expiration_days: Mapped[List[int]] = mapped_column(
        JSON, 
        default=[30, 14, 7]
    )  # e.g. [30, 14, 7]
    
    notify_on_violation: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_renewal_request: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_renewal_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # How to notify
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Which email address to use (null = user's primary email)
    custom_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Phone for SMS (null = use user's phone)
    custom_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Digest settings
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    digest_frequency: Mapped[str] = mapped_column(String(50), default="daily")  # daily, weekly, monthly
    digest_day_of_week: Mapped[Optional[int]] = mapped_column(Integer)  # 0=Monday for weekly
    digest_hour: Mapped[int] = mapped_column(Integer, default=9)  # 0-23
    
    # Quiet hours
    quiet_hours_start: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    quiet_hours_end: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    quiet_hours_timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    
    # Language
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    # Opt-out
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    unsubscribed_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    # Rate limit per-user
    max_emails_per_hour: Mapped[int] = mapped_column(Integer, default=10)
    max_emails_per_day: Mapped[int] = mapped_column(Integer, default=50)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_notification_preferences_user_id", "user_id"),
        Index("idx_notification_preferences_subcontractor_id", "subcontractor_id"),
        Index("idx_notification_preferences_unsubscribed", "unsubscribed_at"),
    )
