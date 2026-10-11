"""Customer-care feedback persistence (MID-666).

Backs the ``feedback_submissions`` table used by the post-launch support loop
(MID-664). Submissions are always org-scoped: ``org_id`` is resolved server-side
from the caller's authenticated identity, never trusted from the client.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class FeedbackSubmission(Base):
    __tablename__ = "feedback_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Submitter; nullable only for out-of-band submissions (e.g. contact form).
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    surface: Mapped[str] = mapped_column(String(100), nullable=False)
    page_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    linked_issue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    disposition_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "idx_feedback_org_status_created",
            "org_id",
            "status",
            "created_at",
        ),
        Index("idx_feedback_org_type", "org_id", "type"),
    )
