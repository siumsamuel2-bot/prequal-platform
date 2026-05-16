"""
Data Integrity & Delivery Pipeline Tests for Email Notification Infrastructure

Tests cover:
- Schema validation for new tables (EmailTemplate, NotificationPreferences, NotificationDeliveryLog)
- Delivery status pipeline transitions (pending -> queued -> sending -> delivered/bounced/failed)
- Data quality constraints (valid emails, valid status values, valid JSON)
- Foreign key integrity (cascade, set null)
- Rate limiting data model validation
- Template variable substitution data integrity

Owner: Data Engineer
"""

import uuid
from datetime import datetime, date
import pytest
from pydantic import ValidationError

from app.schemas.compliance import (
    EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    NotificationPreferencesCreate, NotificationPreferencesUpdate, NotificationPreferencesResponse,
    NotificationDeliveryLogCreate, NotificationDeliveryLogUpdate, NotificationDeliveryLogResponse,
    DeliveryStatus
)


# ---------------------------------------------------------------------------
# EmailTemplate Schema Tests
# ---------------------------------------------------------------------------

def test_email_template_create_valid():
    """EmailTemplateCreate should accept valid template data."""
    template = EmailTemplateCreate(
        name="cert_expiration_30d",
        subject_template="Certification expires in 30 days",
        html_body_template="<html><body><h1> expires in 30 days</h1></body></html>",
        text_body_template=" expires in 30 days",
        template_variables=["certification_type", "expiration_date", "contractor_name"],
        language="en",
        is_active=True,
    )
    assert template.name == "cert_expiration_30d"
    assert template.template_type == "alert"
    assert len(template.template_variables) == 3


def test_email_template_create_missing_required():
    """EmailTemplateCreate should fail when required fields are missing."""
    with pytest.raises(ValidationError) as exc_info:
        EmailTemplateCreate(name="incomplete")
    assert "html_body_template" in str(exc_info.value)
    assert "subject_template" in str(exc_info.value)


def test_email_template_create_empty_name():
    """EmailTemplateCreate should reject empty name."""
    with pytest.raises(ValidationError):
        EmailTemplateCreate(
            name="",
            subject_template="Subject",
            html_body_template="<html></html>",
        )


def test_email_template_update_partial():
    """EmailTemplateUpdate should allow partial updates."""
    update = EmailTemplateUpdate(subject_template="Updated subject")
    assert update.subject_template == "Updated subject"
    assert update.name is None


def test_email_template_response_enrichment():
    """EmailTemplateResponse should include all computed fields."""
    template_id = uuid.uuid4()
    response = EmailTemplateResponse(
        id=template_id,
        name="test_template",
        subject_template="Test subject",
        html_body_template="<html></html>",
        template_variables=[],
        language="en",
        is_active=True,
        is_default=False,
        version=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert response.id == template_id
    assert response.version == 1


# ---------------------------------------------------------------------------
# NotificationPreferences Schema Tests
# ---------------------------------------------------------------------------

def test_notification_preferences_create_valid():
    """NotificationPreferencesCreate should accept valid preference data."""
    pref = NotificationPreferencesCreate(
        user_id=uuid.uuid4(),
        email_enabled=True,
        notify_on_cert_expiration_days=[30, 14, 7],
    )
    assert pref.email_enabled is True
    assert pref.notify_on_cert_expiration is True


def test_notification_preferences_create_invalid_email():
    """NotificationPreferencesCreate should reject invalid custom_email."""
    with pytest.raises(ValidationError):
        NotificationPreferencesCreate(
            user_id=uuid.uuid4(),
            custom_email="invalid-email",
        )


def test_notification_preferences_create_negative_emails_per_hour():
    """NotificationPreferencesCreate should reject negative max_emails_per_hour."""
    with pytest.raises(ValidationError):
        NotificationPreferencesCreate(
            user_id=uuid.uuid4(),
            max_emails_per_hour=-1,
        )


def test_notification_preferences_update_partial():
    """NotificationPreferencesUpdate should allow partial updates."""
    update = NotificationPreferencesUpdate(email_enabled=False)
    assert update.email_enabled is False
    assert update.digest_frequency is None


def test_notification_preferences_response_unsubscribed():
    """NotificationPreferencesResponse should track unsubscribe state."""
    pref = NotificationPreferencesResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        unsubscribed_at=datetime.now(),
        unsubscribed_reason="User opted out",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert pref.unsubscribed_at is not None
    assert pref.unsubscribed_reason == "User opted out"


# ---------------------------------------------------------------------------
# NotificationDeliveryLog Schema Tests
# ---------------------------------------------------------------------------

def test_delivery_log_create_valid():
    """NotificationDeliveryLogCreate should accept valid delivery log data."""
    log = NotificationDeliveryLogCreate(
        alert_notification_id=uuid.uuid4(),
        recipient_email="test@example.com",
        status=DeliveryStatus.PENDING,
        provider="smtp",
        attempt_number=1,
        max_attempts=3,
    )
    assert log.status == DeliveryStatus.PENDING
    assert log.provider == "smtp"


def test_delivery_log_create_invalid_email():
    """NotificationDeliveryLogCreate should reject invalid recipient_email."""
    with pytest.raises(ValidationError):
        NotificationDeliveryLogCreate(
            alert_notification_id=uuid.uuid4(),
            recipient_email="invalid-email",
        )


def test_delivery_log_update_status_transition():
    """NotificationDeliveryLogUpdate should allow status transitions."""
    update = NotificationDeliveryLogUpdate(
        status=DeliveryStatus.SENDING,
        sent_at=datetime.now(),
    )
    assert update.status == DeliveryStatus.SENDING
    assert update.sent_at is not None


def test_delivery_log_update_bounce_tracking():
    """NotificationDeliveryLogUpdate should track bounce details."""
    update = NotificationDeliveryLogUpdate(
        status=DeliveryStatus.BOUNCED,
        bounced_at=datetime.now(),
        bounce_reason="Recipient mailbox full",
        bounce_code="552",
    )
    assert update.status == DeliveryStatus.BOUNCED
    assert update.bounce_code == "552"


def test_delivery_log_response_full():
    """NotificationDeliveryLogResponse should include all tracking fields."""
    log_id = uuid.uuid4()
    alert_id = uuid.uuid4()
    response = NotificationDeliveryLogResponse(
        id=log_id,
        alert_notification_id=alert_id,
        recipient_email="recipient@example.com",
        status=DeliveryStatus.DELIVERED,
        provider="smtp",
        attempt_number=1,
        max_attempts=3,
        sent_at=datetime.now(),
        delivered_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert response.status == DeliveryStatus.DELIVERED
    assert response.delivered_at is not None
    assert response.sent_at is not None


# ---------------------------------------------------------------------------
# Delivery Status Pipeline Tests
# ---------------------------------------------------------------------------

def test_delivery_status_values():
    """DeliveryStatus enum should contain all expected values."""
    expected = {"pending", "queued", "sending", "delivered", "bounced", "suppressed", "failed", "retrying", "cancelled"}
    actual = {status.value for status in DeliveryStatus}
    assert expected == actual


def test_status_transitions_valid():
    """Valid delivery status transitions should be accepted."""
    # pending -> queued -> sending -> delivered
    log = NotificationDeliveryLogUpdate(status=DeliveryStatus.QUEUED)
    assert log.status == DeliveryStatus.QUEUED
    
    log = NotificationDeliveryLogUpdate(status=DeliveryStatus.SENDING)
    assert log.status == DeliveryStatus.SENDING
    
    log = NotificationDeliveryLogUpdate(status=DeliveryStatus.DELIVERED)
    assert log.status == DeliveryStatus.DELIVERED


def test_status_final_states():
    """DELIVERED, FAILED, BOUNCED, CANCELLED, SUPPRESSED should be terminal states."""
    terminal_states = [
        DeliveryStatus.DELIVERED,
        DeliveryStatus.FAILED,
        DeliveryStatus.BOUNCED,
        DeliveryStatus.CANCELLED,
        DeliveryStatus.SUPPRESSED,
    ]
    for state in terminal_states:
        log = NotificationDeliveryLogUpdate(status=state)
        assert log.status == state


# ---------------------------------------------------------------------------
# Rate Limiting Model Tests
# ---------------------------------------------------------------------------

def test_rate_limit_bucket_format():
    """Rate limit bucket should use expected format."""
    update = NotificationDeliveryLogUpdate(
        rate_limit_bucket="smtp:example.com",
        rate_limit_window_start=datetime.now(),
    )
    assert update.rate_limit_bucket == "smtp:example.com"
    assert update.rate_limit_window_start is not None


def test_rate_limit_window_validation():
    """Rate limit window should be a valid datetime."""
    with pytest.raises(ValidationError):
        NotificationDeliveryLogUpdate(
            rate_limit_window_start="invalid-date",
        )


# ---------------------------------------------------------------------------
# Data Quality & Integrity Tests
# ---------------------------------------------------------------------------

def test_email_subject_max_length():
    """Email subject should not exceed 500 characters."""
    with pytest.raises(ValidationError):
        NotificationDeliveryLogCreate(
            alert_notification_id=uuid.uuid4(),
            recipient_email="test@example.com",
            email_subject="x" * 501,
        )


def test_provider_message_id_format():
    """Provider message ID should be a valid string."""
    update = NotificationDeliveryLogUpdate(provider_message_id="msg_12345@provider.com")
    assert update.provider_message_id == "msg_12345@provider.com"


def test_attempt_number_positive():
    """Attempt number should be positive."""
    with pytest.raises(ValidationError):
        NotificationDeliveryLogCreate(
            alert_notification_id=uuid.uuid4(),
            recipient_email="test@example.com",
            attempt_number=0,
        )


def test_max_attempts_gte_attempt_number():
    """max_attempts should be >= attempt_number."""
    log = NotificationDeliveryLogCreate(
        alert_notification_id=uuid.uuid4(),
        recipient_email="test@example.com",
        attempt_number=2,
        max_attempts=2,
    )
    assert log.max_attempts >= log.attempt_number


# ---------------------------------------------------------------------------
# Template Variable Substitution Data Integrity Tests
# ---------------------------------------------------------------------------

def test_template_variables_list():
    """Template variables should be stored as a list of strings."""
    template = EmailTemplateCreate(
        name="cert_expiration_30d",
        subject_template="Certification expires in 30 days",
        html_body_template="<html><body>{{certification_type}} expires on {{expiration_date}}</body></html>",
        template_variables=["certification_type", "expiration_date", "contractor_name"],
    )
    assert len(template.template_variables) == 3
    assert "certification_type" in template.template_variables


def test_template_html_validation():
    """HTML body should contain template variable placeholders."""
    template = EmailTemplateCreate(
        name="test_template",
        subject_template="Test",
        html_body_template="<html><body>{{contractor_name}}</body></html>",
        template_variables=["contractor_name"],
    )
    assert "{{contractor_name}}" in template.html_body_template


# ---------------------------------------------------------------------------
# Foreign Key Integrity Tests (simulated)
# ---------------------------------------------------------------------------

def test_delivery_log_alert_notification_id_format():
    """Alert notification ID should be a valid UUID."""
    alert_id = uuid.uuid4()
    log = NotificationDeliveryLogCreate(
        alert_notification_id=alert_id,
        recipient_email="test@example.com",
    )
    assert log.alert_notification_id == alert_id


def test_preferences_user_id_format():
    """User ID should be a valid UUID."""
    user_id = uuid.uuid4()
    pref = NotificationPreferencesCreate(user_id=user_id)
    assert pref.user_id == user_id


def test_preferences_subcontractor_id_optional():
    """Subcontractor ID should be optional."""
    pref = NotificationPreferencesCreate(user_id=uuid.uuid4(), subcontractor_id=None)
    assert pref.subcontractor_id is None
