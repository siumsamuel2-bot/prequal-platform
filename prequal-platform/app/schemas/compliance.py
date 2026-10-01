import re
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, computed_field
from enum import Enum


class SubcontractorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class CertificationStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_VERIFICATION = "pending_verification"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"


class ViolationStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    APPEALED = "appealed"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AlertType(str, Enum):
    EXPIRATION_APPROACHING = "expiration_approaching"
    EXPIRED = "expired"
    VIOLATION_ISSUED = "violation_issued"
    RENEWAL_APPROVED = "renewal_approved"
    RENEWAL_REJECTED = "renewal_rejected"


class AlertMethod(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class RenewalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class AlertNotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ACKNOWLEDGED = "acknowledged"


class AssignmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class CertificationBase(BaseModel):
    certification_type: str
    certification_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: date
    document_url: Optional[str] = None
    notes: Optional[str] = None


class CertificationCreate(CertificationBase):
    subcontractor_id: UUID


class SubcontractorCertificationCreate(CertificationBase):
    """Create a certification nested under a subcontractor.

    The subcontractor comes from the path parameter, so the body does not
    carry ``subcontractor_id``.
    """
    pass


class CertificationUpdate(BaseModel):
    certification_type: Optional[str] = None
    certification_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    status: Optional[CertificationStatus] = None
    document_url: Optional[str] = None
    verification_status: Optional[VerificationStatus] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[UUID] = None
    notes: Optional[str] = None


class CertificationResponse(CertificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subcontractor_id: UUID
    status: CertificationStatus
    verification_status: VerificationStatus
    verified_at: Optional[datetime] = None
    verified_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_expired(self) -> bool:
        return self.expiration_date < date.today()

    @computed_field
    @property
    def days_until_expiration(self) -> int:
        return (self.expiration_date - date.today()).days


class CertificationWithSubcontractor(CertificationResponse):
    subcontractor_company_name: Optional[str] = None


class ViolationBase(BaseModel):
    violation_type: str
    violation_code: Optional[str] = None
    description: str
    issued_by: Optional[str] = None
    issued_date: date
    effective_date: Optional[date] = None
    resolution_date: Optional[date] = None
    penalty_amount: Optional[float] = None
    is_criminal: bool = False
    notes: Optional[str] = None


class ViolationCreate(ViolationBase):
    subcontractor_id: UUID
    project_id: Optional[UUID] = None


class ViolationUpdate(BaseModel):
    violation_type: Optional[str] = None
    violation_code: Optional[str] = None
    description: Optional[str] = None
    issued_by: Optional[str] = None
    issued_date: Optional[date] = None
    effective_date: Optional[date] = None
    resolution_date: Optional[date] = None
    status: Optional[ViolationStatus] = None
    penalty_amount: Optional[float] = None
    is_criminal: Optional[bool] = None
    notes: Optional[str] = None


class ViolationResponse(ViolationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subcontractor_id: UUID
    project_id: Optional[UUID] = None
    status: ViolationStatus
    created_at: datetime
    updated_at: datetime


class ViolationWithSubcontractor(ViolationResponse):
    subcontractor_company_name: Optional[str] = None


class SubcontractorBase(BaseModel):
    company_name: str
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "USA"
    ein: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_expiration: Optional[date] = None


class SubcontractorCreate(SubcontractorBase):
    pass


class SubcontractorUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    ein: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_expiration: Optional[date] = None
    status: Optional[SubcontractorStatus] = None


class SubcontractorResponse(SubcontractorBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: SubcontractorStatus
    created_at: datetime
    updated_at: datetime


class SubcontractorWithDetails(SubcontractorResponse):
    certifications: List[CertificationResponse] = []
    violations: List[ViolationResponse] = []
    active_projects_count: int = 0
    compliance_score: Optional[float] = None


class ProjectBase(BaseModel):
    project_name: str
    project_number: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    start_date: Optional[date] = None
    estimated_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "USA"
    budget: Optional[float] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    project_number: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    start_date: Optional[date] = None
    estimated_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    status: Optional[ProjectStatus] = None
    budget: Optional[float] = None


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectWithSubcontractors(ProjectResponse):
    subcontractors: List[dict] = []


class ProjectSubcontractorBase(BaseModel):
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    insurance_expiration: Optional[date] = None
    bonds_expiration: Optional[date] = None


class ProjectSubcontractorCreate(ProjectSubcontractorBase):
    project_id: UUID
    subcontractor_id: UUID


class ProjectSubcontractorUpdate(BaseModel):
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[AssignmentStatus] = None
    insurance_expiration: Optional[date] = None
    bonds_expiration: Optional[date] = None


class ProjectSubcontractorResponse(ProjectSubcontractorBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    subcontractor_id: UUID
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime


class AlertPreferenceBase(BaseModel):
    certification_types: Optional[List[str]] = None
    advance_notice_days: int = 30
    alert_methods: List[AlertMethod] = ["email"]
    is_active: bool = True


class AlertPreferenceCreate(AlertPreferenceBase):
    user_id: UUID


class AlertPreferenceUpdate(BaseModel):
    certification_types: Optional[List[str]] = None
    advance_notice_days: Optional[int] = None
    alert_methods: Optional[List[AlertMethod]] = None
    is_active: Optional[bool] = None


class AlertPreferenceResponse(AlertPreferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class AlertNotificationBase(BaseModel):
    alert_type: AlertType
    scheduled_for: datetime
    method: Optional[AlertMethod] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class AlertNotificationCreate(AlertNotificationBase):
    certification_id: UUID


class AlertNotificationUpdate(BaseModel):
    status: Optional[AlertNotificationStatus] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class AlertNotificationResponse(AlertNotificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    certification_id: UUID
    sent_at: Optional[datetime] = None
    status: AlertNotificationStatus
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    days_until_expiration: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AlertWithContextResponse(AlertNotificationResponse):
    """Enriched alert response including contractor and project context."""
    contractor_name: Optional[str] = None
    project_ids: List[str] = []


class CertificationRenewalBase(BaseModel):
    notes: Optional[str] = None
    new_expiration_date: Optional[date] = None


class CertificationRenewalCreate(CertificationRenewalBase):
    certification_id: UUID


class CertificationRenewalUpdate(BaseModel):
    status: Optional[RenewalStatus] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None
    new_expiration_date: Optional[date] = None


class CertificationRenewalResponse(CertificationRenewalBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    certification_id: UUID
    requested_by: UUID
    requested_at: datetime
    status: RenewalStatus
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ComplianceStatusResponse(BaseModel):
    subcontractor_id: UUID
    company_name: str
    state: Optional[str] = None
    compliance_score: float
    status: str
    active_certifications: int
    expiring_certifications: int
    expired_certifications: int
    open_violations: int
    resolved_violations: int


class DashboardSummary(BaseModel):
    total_subcontractors: int
    active_subcontractors: int
    compliance_rate: float
    total_projects: int
    active_projects: int
    expiring_this_month: int
    open_violations: int
    recent_alerts: List[AlertNotificationResponse] = []


# ---------------------------------------------------------------------------
# Analytics Dashboard Schemas
# Added: 2026-05-26 (Data Engineer)
# Purpose: response shapes for analytics materialized view endpoints
# ---------------------------------------------------------------------------

class ComplianceSummaryResponse(BaseModel):
    total_subcontractors: int
    active_subcontractors: int
    suspended_subcontractors: int
    blacklisted_subcontractors: int
    compliant_subcontractors: int
    compliance_rate: float
    expiring_soon_30d: int
    expiring_soon_60d: int
    open_violations: int
    open_osha_violations: int
    total_open_penalties: float
    valid_certifications: int
    expired_certifications: int
    pending_verification_certs: int
    computed_at: Optional[str] = None


class ComplianceTrendPoint(BaseModel):
    date: Optional[str] = None
    active_subcontractors: int
    valid_certifications: int
    expired_certifications: int
    open_violations: int
    open_osha_violations: int
    compliance_percentage: float
    computed_at: Optional[str] = None


class CertificationExportRow(BaseModel):
    subcontractor_id: str
    company_name: str
    email: str
    subcontractor_status: str
    certification_id: str
    certification_type: str
    certification_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    certification_status: str
    verification_status: str
    expiration_bucket: Optional[str] = None
    days_until_expiration: Optional[int] = None
    verified_at: Optional[str] = None
    created_at: Optional[str] = None
    computed_at: Optional[str] = None


class ProjectComplianceSummary(BaseModel):
    project_id: str
    project_name: str
    project_number: Optional[str] = None
    project_status: str
    total_subcontractors: int
    active_subcontractors: int
    suspended_subcontractors: int
    compliant_subcontractors: int
    compliance_rate: float
    open_violations: int
    open_osha_violations: int
    total_open_penalties: float
    expiring_soon_subcontractors: int
    computed_at: Optional[str] = None


class RecentAlert(BaseModel):
    alert_id: str
    certification_id: str
    alert_type: str
    scheduled_for: Optional[str] = None
    sent_at: Optional[str] = None
    status: str
    method: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    acknowledged_at: Optional[str] = None
    days_until_expiration: Optional[int] = None
    created_at: Optional[str] = None
    certification_type: str
    expiration_date: Optional[str] = None
    subcontractor_id: str
    subcontractor_name: str
    subcontractor_email: str
    computed_at: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    sub: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = "viewer"
    team_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserWithTeams(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    teams: List[dict] = []


class TeamResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    role: str
    joined_at: Optional[datetime] = None


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Email Notification Delivery Schemas
# Added: 2026-05-14 (Data Engineer)
# Purpose: Pydantic schemas for email templates, notification preferences,
#          and delivery logs
# ---------------------------------------------------------------------------

class DeliveryStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class EmailTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: str = "alert"
    alert_type: Optional[str] = None
    subject_template: str
    html_body_template: str
    text_body_template: Optional[str] = None
    template_variables: List[str] = []
    language: str = "en"
    is_active: bool = True
    is_default: bool = False


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[str] = None
    alert_type: Optional[str] = None
    subject_template: Optional[str] = None
    html_body_template: Optional[str] = None
    text_body_template: Optional[str] = None
    template_variables: Optional[List[str]] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class EmailTemplateResponse(EmailTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class NotificationPreferencesBase(BaseModel):
    notify_on_cert_expiration: bool = True
    notify_on_cert_expiration_days: List[int] = [30, 14, 7]
    notify_on_violation: bool = True
    notify_on_renewal_request: bool = True
    notify_on_renewal_approved: bool = False
    email_enabled: bool = True
    sms_enabled: bool = False
    in_app_enabled: bool = True
    custom_email: Optional[EmailStr] = None
    custom_phone: Optional[str] = None
    digest_enabled: bool = False
    digest_frequency: str = "daily"
    digest_day_of_week: Optional[int] = None
    digest_hour: int = 9
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    quiet_hours_timezone: str = "UTC"
    language: str = "en"
    max_emails_per_hour: int = 10
    max_emails_per_day: int = 50


class NotificationPreferencesCreate(NotificationPreferencesBase):
    user_id: UUID
    subcontractor_id: Optional[UUID] = None


class NotificationPreferencesUpdate(BaseModel):
    notify_on_cert_expiration: Optional[bool] = None
    notify_on_cert_expiration_days: Optional[List[int]] = None
    notify_on_violation: Optional[bool] = None
    notify_on_renewal_request: Optional[bool] = None
    notify_on_renewal_approved: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    custom_email: Optional[EmailStr] = None
    custom_phone: Optional[str] = None
    digest_enabled: Optional[bool] = None
    digest_frequency: Optional[str] = None
    digest_day_of_week: Optional[int] = None
    digest_hour: Optional[int] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    quiet_hours_timezone: Optional[str] = None
    language: Optional[str] = None
    max_emails_per_hour: Optional[int] = None
    max_emails_per_day: Optional[int] = None


class NotificationPreferencesResponse(NotificationPreferencesBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    subcontractor_id: Optional[UUID] = None
    unsubscribed_at: Optional[datetime] = None
    unsubscribed_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryLogBase(BaseModel):
    recipient_email: EmailStr
    status: DeliveryStatus = DeliveryStatus.PENDING
    provider: str = "smtp"
    attempt_number: int = 1
    max_attempts: int = 3


class NotificationDeliveryLogCreate(NotificationDeliveryLogBase):
    alert_notification_id: UUID
    template_id: Optional[UUID] = None


class NotificationDeliveryLogUpdate(BaseModel):
    status: Optional[DeliveryStatus] = None
    provider_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    rate_limit_bucket: Optional[str] = None
    rate_limit_window_start: Optional[datetime] = None


class NotificationDeliveryLogResponse(NotificationDeliveryLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_notification_id: UUID
    recipient_user_id: Optional[UUID] = None
    recipient_subcontractor_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    email_subject: Optional[str] = None
    email_body_html: Optional[str] = None
    email_body_text: Optional[str] = None
    provider_message_id: Optional[str] = None
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    bounce_reason: Optional[str] = None
    bounce_code: Optional[str] = None
    rate_limit_bucket: Optional[str] = None
    rate_limit_window_start: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime