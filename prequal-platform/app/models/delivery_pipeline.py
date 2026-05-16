"""
Email Notification Delivery Status Pipeline

Data pipeline for email delivery from alert generation to final status.
Maps the full lifecycle of an email delivery attempt.

Owner: Data Engineer
Last updated: 2026-05-14
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, ConfigDict


class DeliveryStatus(str, Enum):
    """Delivery status pipeline values.
    
    State machine:
    
    pending -> queued -> sending -> delivered
      |          |         |          |
      |          |         +----> bounced
      |          |         |
      |          +----> failed -> retrying -> (sending)
      |
      +---> cancelled / suppressed
    """
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class DeliveryPipelineState(BaseModel):
    """Represents the current state of a delivery pipeline.
    
    Used for tracking the full lifecycle of an email delivery attempt.
    """
    model_config = ConfigDict(from_attributes=True)
    
    # Identifiers
    delivery_log_id: UUID
    alert_notification_id: UUID
    recipient_email: str
    
    # Current state
    status: DeliveryStatus
    previous_status: Optional[DeliveryStatus] = None
    
    # Timestamps for each stage
    pending_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    sending_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    suppressed_at: Optional[datetime] = None
    
    # Provider info
    provider: str = "smtp"
    provider_message_id: Optional[str] = None
    
    # Retry tracking
    attempt_number: int = 1
    max_attempts: int = 3
    
    # Error tracking
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    
    # Rate limiting
    rate_limit_bucket: Optional[str] = None
    rate_limit_window_start: Optional[datetime] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
