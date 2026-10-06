import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base

if TYPE_CHECKING:
    from app.models.compliance import Certification, Subcontractor


class UploadedCredential(Base):
    __tablename__ = "uploaded_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcontractor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=False)
    certification_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("certifications.id", ondelete="SET NULL"), nullable=True)
    
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="pending")
    extraction_status: Mapped[str] = mapped_column(String(50), default="pending")
    
    extracted_cert_type: Mapped[Optional[str]] = mapped_column(String(100))
    extracted_cert_number: Mapped[Optional[str]] = mapped_column(String(100))
    extracted_issue_date: Mapped[Optional[str]] = mapped_column(String(50))
    extracted_expiration_date: Mapped[Optional[str]] = mapped_column(String(50))
    extracted_issuing_authority: Mapped[Optional[str]] = mapped_column(String(255))
    
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text)
    virus_scan_status: Mapped[str] = mapped_column(String(50), default="not_scanned")
    virus_scan_result: Mapped[Optional[str]] = mapped_column(Text)
    
    upload_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subcontractor: Mapped["Subcontractor"] = relationship("Subcontractor", back_populates="uploaded_credentials")
    certification: Mapped[Optional["Certification"]] = relationship("Certification")

    __table_args__ = (
        Index("idx_uploaded_credentials_subcontractor_id", "subcontractor_id"),
        Index("idx_uploaded_credentials_status", "status"),
        Index("idx_uploaded_credentials_stored_filename", "stored_filename"),
    )