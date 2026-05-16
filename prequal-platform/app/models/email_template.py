"""
Email Template Data Schema

Stores email templates for notification delivery.
Supports variable substitution and multi-language.

Owner: Data Engineer
Last updated: 2026-05-14
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, DateTime, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class EmailTemplate(Base):
    """
    Email templates for notification delivery.
    
    Templates support variable substitution via {{variable_name}} syntax.
    Variables are documented in the template_variables column.
    """
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Template identification
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Template type and purpose
    template_type: Mapped[str] = mapped_column(String(50), nullable=False, default="alert")  # alert, digest, welcome, etc.
    alert_type: Mapped[Optional[str]] = mapped_column(String(50))  # e.g. "expiration_30d", "violation", etc.
    
    # Template content
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    html_body_template: Mapped[str] = mapped_column(Text, nullable=False)
    text_body_template: Mapped[Optional[str]] = mapped_column(Text)
    
    # Variable documentation
    # e.g. ["contractor_name", "certification_type", "expiration_date", "days_until_expiration"]
    template_variables: Mapped[list] = mapped_column(JSON, default=list)
    
    # Language
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Ownership
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_email_templates_type", "template_type"),
        Index("idx_email_templates_alert_type", "alert_type"),
        Index("idx_email_templates_active", "is_active"),
        Index("idx_email_templates_language", "language"),
    )
