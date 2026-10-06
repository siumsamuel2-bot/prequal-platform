import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


MAX_SESSION_ROTATIONS = 200


class UserSession(Base):
    """Server-side session tracking for secure token rotation and invalidation.

    Each active access token corresponds to a single server-side session record.
    - On login: a new session is created with the access token JTI.
    - On each request: the session is validated (active, not expired) and rotated (new JTI, updated last_seen).
    - On logout: the session is marked inactive.
    - On password change: all sessions for the user are marked inactive.
    """
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_from_jti: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rotation_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_user_sessions_user_id", "user_id"),
        Index("idx_user_sessions_jti", "jti", unique=True),
        Index("idx_user_sessions_active_user_id", "user_id", "active"),
        Index("idx_user_sessions_expires_at", "expires_at"),
    )
