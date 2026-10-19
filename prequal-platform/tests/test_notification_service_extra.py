"""Coverage for app/services/notification_service.py (MID-676).

Exercises the transport branches (SendGrid / Twilio) and the templated
convenience senders. The vendor SDKs are injected as fake modules so no network
or optional dependency is required.
"""
from __future__ import annotations

import sys
import types

import pytest

from app.services import notification_service as notify


def _fake_sendgrid(monkeypatch, response):
    """Install a fake ``sendgrid`` package and return the client class used."""
    sendgrid = types.ModuleType("sendgrid")
    helpers = types.ModuleType("sendgrid.helpers")
    mail = types.ModuleType("sendgrid.helpers.mail")

    def _Mail(**kwargs):
        return kwargs

    class _Client:
        last = None

        def __init__(self, api_key):
            self.api_key = api_key
            self.sent = []
            _Client.last = self

        def send(self, message):
            self.sent.append(message)
            return response

    mail.Mail = _Mail
    sendgrid.SendGridAPIClient = _Client
    sendgrid.helpers = helpers
    helpers.mail = mail
    monkeypatch.setitem(sys.modules, "sendgrid", sendgrid)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers", helpers)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers.mail", mail)
    return _Client


def _fake_twilio(monkeypatch, *, sid="SM123", error=None):
    twilio = types.ModuleType("twilio")
    rest = types.ModuleType("twilio.rest")

    class _Messages:
        def create(self, **kwargs):
            _Messages.last_kwargs = kwargs
            if error is not None:
                raise error
            return types.SimpleNamespace(sid=sid)

    class _Client:
        def __init__(self, account_sid, auth_token):
            self.account_sid = account_sid
            self.auth_token = auth_token
            self.messages = _Messages()

    rest.Client = _Client
    twilio.rest = rest
    monkeypatch.setitem(sys.modules, "twilio", twilio)
    monkeypatch.setitem(sys.modules, "twilio.rest", rest)
    return _Client


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_debug_when_unconfigured(monkeypatch):
    monkeypatch.setattr(notify, "SENDGRID_API_KEY", None)
    result = await notify.send_email("a@example.com", "Hi", "Body")
    assert result.success is True
    assert result.message_id.startswith("debug-")


@pytest.mark.asyncio
async def test_send_email_sendgrid_success(monkeypatch):
    monkeypatch.setattr(notify, "SENDGRID_API_KEY", "SG.test")
    response = types.SimpleNamespace(status_code=202, headers={"X-Message-Id": "abc"})
    _fake_sendgrid(monkeypatch, response)

    result = await notify.send_email(
        "a@example.com", "Hi", "Body", html_body="<p>Body</p>"
    )

    assert result.success is True
    assert result.message_id == "abc"


@pytest.mark.asyncio
async def test_send_email_sendgrid_error_status(monkeypatch):
    monkeypatch.setattr(notify, "SENDGRID_API_KEY", "SG.test")
    response = types.SimpleNamespace(status_code=400, headers={})
    _fake_sendgrid(monkeypatch, response)

    result = await notify.send_email("a@example.com", "Hi", "Body")

    assert result.success is False
    assert result.error == "HTTP 400"


@pytest.mark.asyncio
async def test_send_email_sendgrid_raises(monkeypatch):
    monkeypatch.setattr(notify, "SENDGRID_API_KEY", "SG.test")

    class _BoomClient:
        def __init__(self, api_key):
            raise RuntimeError("smtp down")

    sendgrid = types.ModuleType("sendgrid")
    helpers = types.ModuleType("sendgrid.helpers")
    mail = types.ModuleType("sendgrid.helpers.mail")
    mail.Mail = lambda **kwargs: kwargs
    sendgrid.SendGridAPIClient = _BoomClient
    sendgrid.helpers = helpers
    helpers.mail = mail
    monkeypatch.setitem(sys.modules, "sendgrid", sendgrid)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers", helpers)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers.mail", mail)

    result = await notify.send_email("a@example.com", "Hi", "Body")

    assert result.success is False
    assert "smtp down" in result.error


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_sms_debug_when_unconfigured(monkeypatch):
    monkeypatch.setattr(notify, "TWILIO_ACCOUNT_SID", None)
    monkeypatch.setattr(notify, "TWILIO_AUTH_TOKEN", None)
    result = await notify.send_sms("+15551234567", "hello")
    assert result.success is True
    assert result.message_id.startswith("debug-")


@pytest.mark.asyncio
async def test_send_sms_twilio_success(monkeypatch):
    monkeypatch.setattr(notify, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(notify, "TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setattr(notify, "TWILIO_PHONE_NUMBER", "+15550000000")
    _fake_twilio(monkeypatch, sid="SM999")

    result = await notify.send_sms("+15551234567", "hello")

    assert result.success is True
    assert result.message_id == "SM999"


@pytest.mark.asyncio
async def test_send_sms_twilio_raises(monkeypatch):
    monkeypatch.setattr(notify, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(notify, "TWILIO_AUTH_TOKEN", "tok")
    _fake_twilio(monkeypatch, error=RuntimeError("twilio down"))

    result = await notify.send_sms("+15551234567", "hello")

    assert result.success is False
    assert "twilio down" in result.error


# ---------------------------------------------------------------------------
# Routing + templated senders
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_notification_routes_to_sms(monkeypatch):
    calls = []

    async def _fake_sms(recipient, body):
        calls.append(("sms", recipient, body))
        return notify.NotificationResult(success=True, message_id="s")

    monkeypatch.setattr(notify, "send_sms", _fake_sms)
    result = await notify.send_notification("+1555", "subj", "body", method="sms")
    assert result.success is True
    assert calls == [("sms", "+1555", "body")]


@pytest.mark.asyncio
async def test_send_notification_routes_to_email(monkeypatch):
    calls = []

    async def _fake_email(recipient, subject, body, html_body=None):
        calls.append((recipient, subject, body, html_body))
        return notify.NotificationResult(success=True, message_id="e")

    monkeypatch.setattr(notify, "send_email", _fake_email)
    result = await notify.send_notification(
        "a@example.com", "subj", "body", method="email", html_body="<p>x</p>"
    )
    assert result.success is True
    assert calls == [("a@example.com", "subj", "body", "<p>x</p>")]


@pytest.mark.asyncio
async def test_send_welcome_email_substitutes_app_url(monkeypatch):
    captured = {}

    async def _fake_email(to_email, subject, body, html_body=None):
        captured.update(
            to=to_email, subject=subject, body=body, html=html_body
        )
        return notify.NotificationResult(success=True, message_id="w")

    monkeypatch.setattr(notify, "send_email", _fake_email)
    result = await notify.send_welcome_email("new@example.com", app_url="https://app.test")

    assert result.success is True
    assert captured["subject"] == notify.WELCOME_EMAIL_SUBJECT
    assert "https://app.test/setup" in captured["html"]
    assert "{app_url}" not in captured["html"]


@pytest.mark.asyncio
async def test_send_setup_complete_email_substitutes_app_url(monkeypatch):
    captured = {}

    async def _fake_email(to_email, subject, body, html_body=None):
        captured.update(to=to_email, subject=subject, html=html_body)
        return notify.NotificationResult(success=True, message_id="s")

    monkeypatch.setattr(notify, "send_email", _fake_email)
    result = await notify.send_setup_complete_email(
        "owner@example.com", app_url="https://app.test"
    )

    assert result.success is True
    assert captured["subject"] == notify.SETUP_COMPLETE_EMAIL_SUBJECT
    assert "https://app.test/dashboard" in captured["html"]


@pytest.mark.asyncio
async def test_send_first_alert_email_formats_fields(monkeypatch):
    captured = {}

    async def _fake_email(to_email, subject, body, html_body=None):
        captured.update(to=to_email, subject=subject, body=body, html=html_body)
        return notify.NotificationResult(success=True, message_id="a")

    monkeypatch.setattr(notify, "send_email", _fake_email)
    result = await notify.send_first_alert_email(
        "pm@example.com",
        subcontractor_name="Acme Builders",
        certification_type="OSHA 30",
        expiration_date="2026-01-01",
        days_until_expiration=7,
        subcontractor_id="sub-1",
        app_url="https://app.test",
    )

    assert result.success is True
    assert captured["subject"] == notify.FIRST_ALERT_EMAIL_SUBJECT
    assert "Acme Builders" in captured["body"]
    assert "OSHA 30" in captured["body"]
    assert "https://app.test/subcontractors/sub-1" in captured["html"]
