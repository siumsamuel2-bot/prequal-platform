import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Text, Date, DateTime, Boolean, Numeric, Integer, 
    ForeignKey, UniqueConstraint, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    contact_last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="USA")
    ein: Mapped[Optional[str]] = mapped_column(String(20))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    license_state: Mapped[Optional[str]] = mapped_column(String(50))
    license_expiration: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="active")
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    certifications: Mapped[List["Certification"]] = relationship("Certification", back_populates="subcontractor", cascade="all, delete-orphan")
    violations: Mapped[List["Violation"]] = relationship("Violation", back_populates="subcontractor", cascade="all, delete-orphan")
    project_assignments: Mapped[List["ProjectSubcontractor"]] = relationship("ProjectSubcontractor", back_populates="subcontractor", cascade="all, delete-orphan")
    uploaded_credentials: Mapped[List["UploadedCredential"]] = relationship("UploadedCredential", back_populates="subcontractor", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_subcontractors_status", "status"),
        Index("idx_subcontractors_license_expiration", "license_expiration"),
        Index("idx_subcontractors_org_id", "org_id"),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_contact: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    estimated_end_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_end_date: Mapped[Optional[date]] = mapped_column(Date)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="USA")
    status: Mapped[str] = mapped_column(String(50), default="planning")
    budget: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subcontractor_assignments: Mapped[List["ProjectSubcontractor"]] = relationship("ProjectSubcontractor", back_populates="project", cascade="all, delete-orphan")
    violations: Mapped[List["Violation"]] = relationship("Violation", back_populates="project")

    __table_args__ = (
        Index("idx_projects_status", "status"),
        Index("idx_projects_org_id", "org_id"),
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcontractor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=False)
    certification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    certification_number: Mapped[Optional[str]] = mapped_column(String(100))
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(255))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="valid")
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subcontractor: Mapped["Subcontractor"] = relationship("Subcontractor", back_populates="certifications")
    alert_notifications: Mapped[List["AlertNotification"]] = relationship("AlertNotification", back_populates="certification", cascade="all, delete-orphan")
    renewal_requests: Mapped[List["CertificationRenewal"]] = relationship("CertificationRenewal", back_populates="certification", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_certifications_subcontractor_id", "subcontractor_id"),
        Index("idx_certifications_expiration_date", "expiration_date"),
        Index("idx_certifications_status", "status"),
    )


class ProjectSubcontractor(Base):
    __tablename__ = "project_subcontractors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    subcontractor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="active")
    insurance_expiration: Mapped[Optional[date]] = mapped_column(Date)
    bonds_expiration: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="subcontractor_assignments")
    subcontractor: Mapped["Subcontractor"] = relationship("Subcontractor", back_populates="project_assignments")

    __table_args__ = (
        UniqueConstraint("project_id", "subcontractor_id", name="uq_project_subcontractor"),
        Index("idx_project_subcontractors_project_id", "project_id"),
        Index("idx_project_subcontractors_subcontractor_id", "subcontractor_id"),
    )


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcontractor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))
    violation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    violation_code: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by: Mapped[Optional[str]] = mapped_column(String(255))
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    resolution_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="open")
    penalty_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    is_criminal: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # OSHA-specific columns (migration 001 adds these via ALTER TABLE)
    osha_violation_id: Mapped[Optional[str]] = mapped_column(String(100))
    citation_number: Mapped[Optional[str]] = mapped_column(String(100))
    violation_description: Mapped[Optional[str]] = mapped_column(Text)
    standard_cited: Mapped[Optional[str]] = mapped_column(String(100))
    initial_penalty: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    final_penalty: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    abatement_date: Mapped[Optional[date]] = mapped_column(Date)
    date_corrected: Mapped[Optional[date]] = mapped_column(Date)
    contest_status: Mapped[Optional[str]] = mapped_column(String(50))
    inspection_number: Mapped[Optional[str]] = mapped_column(String(100))
    activity_number: Mapped[Optional[str]] = mapped_column(String(100))
    site_city: Mapped[Optional[str]] = mapped_column(String(100))
    site_state: Mapped[Optional[str]] = mapped_column(String(50))
    site_zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    site_address: Mapped[Optional[str]] = mapped_column(Text)
    naics_code: Mapped[Optional[str]] = mapped_column(String(20))
    inspection_type: Mapped[Optional[str]] = mapped_column(String(100))
    owner_type: Mapped[Optional[str]] = mapped_column(String(50))
    gravity_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    probability_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    risk_category: Mapped[Optional[str]] = mapped_column(String(50))
    is_osha_violation: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subcontractor: Mapped["Subcontractor"] = relationship("Subcontractor", back_populates="violations")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="violations")

    __table_args__ = (
        Index("idx_violations_subcontractor_id", "subcontractor_id"),
        Index("idx_violations_project_id", "project_id"),
        Index("idx_violations_issued_date", "issued_date"),
        Index("idx_violations_status", "status"),
        Index("idx_violations_osha_violation_id", "osha_violation_id"),
        Index("idx_violations_inspection_number", "inspection_number"),
        Index("idx_violations_citation_number", "citation_number"),
    )


class AlertPreference(Base):
    __tablename__ = "alert_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    certification_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    advance_notice_days: Mapped[int] = mapped_column(Integer, default=30)
    alert_methods: Mapped[List[str]] = mapped_column(JSON, default=["email"])
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_alert_preferences_user_id", "user_id"),
    )


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    method: Mapped[Optional[str]] = mapped_column(String(50))
    recipient: Mapped[Optional[str]] = mapped_column(String(255))
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    body: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    days_until_expiration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    certification: Mapped["Certification"] = relationship("Certification", back_populates="alert_notifications")

    __table_args__ = (
        Index("idx_alert_notifications_certification_id", "certification_id"),
        Index("idx_alert_notifications_scheduled_for", "scheduled_for"),
        Index("idx_alert_notifications_status", "status"),
        Index("idx_alert_notifications_acknowledged_at", "acknowledged_at"),
        Index("idx_alert_notifications_days_until", "days_until_expiration"),
    )


class CertificationRenewal(Base):
    __tablename__ = "certification_renewals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    new_expiration_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    certification: Mapped["Certification"] = relationship("Certification", back_populates="renewal_requests")

    __table_args__ = (
        Index("idx_certification_renewals_certification_id", "certification_id"),
        Index("idx_certification_renewals_status", "status"),
    )


class OSHAInspection(Base):
    __tablename__ = "osha_inspections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    activity_number: Mapped[Optional[str]] = mapped_column(String(100))
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)
    completion_date: Mapped[Optional[date]] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(String(100))
    site_city: Mapped[Optional[str]] = mapped_column(String(100))
    site_state: Mapped[Optional[str]] = mapped_column(String(50))
    site_zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    site_address: Mapped[Optional[str]] = mapped_column(Text)
    naics_code: Mapped[Optional[str]] = mapped_column(String(20))
    reported_by: Mapped[Optional[str]] = mapped_column(String(255))
    owner_type: Mapped[Optional[str]] = mapped_column(String(50))
    safety_man_hour: Mapped[Optional[int]] = mapped_column(Integer)
    health_man_hour: Mapped[Optional[int]] = mapped_column(Integer)
    total_penalty: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    abatement_completed: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_osha_inspections_inspection_date", "inspection_date"),
    )


class OSHAApiLog(Base):
    __tablename__ = "osha_api_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    request_parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    request_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    response_status: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[dict]] = mapped_column(JSON)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_osha_api_logs_request_type", "request_type"),
        Index("idx_osha_api_logs_created_at", "created_at"),
    )


class SyncRunLog(Base):
    __tablename__ = "sync_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    triggered_by: Mapped[str] = mapped_column(String(50), default="schedule")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_sync_run_logs_job_name", "job_name"),
        Index("idx_sync_run_logs_status", "status"),
        Index("idx_sync_run_logs_created_at", "created_at"),
    )


class StateCredentialRecord(Base):
    __tablename__ = "state_credential_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    credential_number: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    issuing_state: Mapped[str] = mapped_column(String(100), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    holder_address: Mapped[Optional[str]] = mapped_column(Text)
    holder_city: Mapped[Optional[str]] = mapped_column(String(100))
    holder_state: Mapped[Optional[str]] = mapped_column(String(50))
    holder_zip: Mapped[Optional[str]] = mapped_column(String(20))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="active")
    external_source_id: Mapped[Optional[str]] = mapped_column(String(255))
    external_source_url: Mapped[Optional[str]] = mapped_column(Text)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_version: Mapped[int] = mapped_column(Integer, default=1)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_state_credential_state_code", "state_code"),
        Index("idx_state_credential_status", "status"),
        Index("idx_state_credential_expiration", "expiration_date"),
    )


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_name: Mapped[Optional[str]] = mapped_column(String(100))
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    check_query: Mapped[Optional[str]] = mapped_column(Text)
    expected_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_data_quality_checks_table_name", "table_name"),
        Index("idx_data_quality_checks_check_type", "check_type"),
        Index("idx_data_quality_checks_is_active", "is_active"),
    )


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("data_quality_checks.id", ondelete="CASCADE"), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_run_logs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_checked: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    failure_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    sample_failures: Mapped[Optional[dict]] = mapped_column(JSON)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_data_quality_results_check_id", "check_id"),
        Index("idx_data_quality_results_sync_run_id", "sync_run_id"),
        Index("idx_data_quality_results_status", "status"),
    )


class OSHADataFreshness(Base):
    __tablename__ = "osha_data_freshness"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_scheduled_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    update_frequency: Mapped[str] = mapped_column(String(50), default="daily")
    status: Mapped[str] = mapped_column(String(50), default="current")
    last_run_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("osha_api_logs.id"))
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Email Notification Delivery Infrastructure
# Added: 2026-05-14 (Data Engineer)
# Purpose: Track email delivery, preferences, and templates
# ---------------------------------------------------------------------------

class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False, default="alert")
    alert_type: Mapped[Optional[str]] = mapped_column(String(50))
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    html_body_template: Mapped[str] = mapped_column(Text, nullable=False)
    text_body_template: Mapped[Optional[str]] = mapped_column(Text)
    template_variables: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_email_templates_type", "template_type"),
        Index("idx_email_templates_alert_type", "alert_type"),
        Index("idx_email_templates_active", "is_active"),
        Index("idx_email_templates_language", "language"),
    )


class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subcontractor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=True, index=True)
    notify_on_cert_expiration: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_cert_expiration_days: Mapped[Optional[list]] = mapped_column(JSON, default=[30, 14, 7])
    notify_on_violation: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_renewal_request: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_renewal_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    custom_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    digest_frequency: Mapped[str] = mapped_column(String(50), default="daily")
    digest_day_of_week: Mapped[Optional[int]] = mapped_column(Integer)
    digest_hour: Mapped[int] = mapped_column(Integer, default=9)
    quiet_hours_start: Mapped[Optional[int]] = mapped_column(Integer)
    quiet_hours_end: Mapped[Optional[int]] = mapped_column(Integer)
    quiet_hours_timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    language: Mapped[str] = mapped_column(String(10), default="en")
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    unsubscribed_reason: Mapped[Optional[str]] = mapped_column(Text)
    max_emails_per_hour: Mapped[int] = mapped_column(Integer, default=10)
    max_emails_per_day: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_notification_preferences_user_id", "user_id"),
        Index("idx_notification_preferences_subcontractor_id", "subcontractor_id"),
        Index("idx_notification_preferences_unsubscribed", "unsubscribed_at"),
    )


class NotificationDeliveryLog(Base):
    __tablename__ = "notification_delivery_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_subcontractor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id", ondelete="SET NULL"), nullable=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    email_subject: Mapped[Optional[str]] = mapped_column(String(500))
    email_body_html: Mapped[Optional[str]] = mapped_column(Text)
    email_body_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    provider: Mapped[str] = mapped_column(String(100), default="smtp")
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    bounce_reason: Mapped[Optional[str]] = mapped_column(Text)
    bounce_code: Mapped[Optional[str]] = mapped_column(String(50))
    rate_limit_bucket: Mapped[Optional[str]] = mapped_column(String(100))
    rate_limit_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
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