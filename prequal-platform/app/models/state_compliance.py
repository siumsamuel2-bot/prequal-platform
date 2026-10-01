import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class StateComplianceSource(Base):
    __tablename__ = "state_compliance_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    state_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key_env_var: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[str] = mapped_column(String(50), default="license_board")
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_state_sources_state_code", "state_code", unique=True),
        Index("idx_state_sources_active", "is_active"),
    )