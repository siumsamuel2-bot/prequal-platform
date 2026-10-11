"""Delivery-path coverage for app/services/alert_service.py (MID-676).

Covers ``deliver_pending_alerts``, ``_get_users_to_notify_for_subcontractor``
and ``_send_alert_to_user`` end-to-end against the test database, with the
notification transport stubbed so no network is touched.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.auth import Team, TeamMember, User
from app.models.compliance import (
    AlertNotification,
    Certification,
    NotificationPreferences,
    Project,
    ProjectSubcontractor,
    Subcontractor,
)
from app.services import alert_service
from app.services.notification_service import NotificationResult


async def _seed_deliverable(
    session,
    *,
    email_enabled: bool = True,
    sms_enabled: bool = False,
    phone: str | None = None,
):
    """Seed user/team/sub/project/cert/pending-alert wired for delivery."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"notify-{suffix}@example.com",
        name="Notify User",
        hashed_password="x",
        role="member",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    team = Team(name=f"Team {suffix}", owner_id=user.id)
    session.add(team)
    await session.flush()
    session.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))

    sub = Subcontractor(
        company_name="Deliver Co",
        email=f"deliver-{suffix}@example.com",
        status="active",
        team_id=team.id,
    )
    proj = Project(
        project_name="Deliver Project",
        project_number=f"DP-{suffix}",
        status="active",
        team_id=team.id,
    )
    session.add_all([sub, proj])
    await session.flush()

    session.add(
        ProjectSubcontractor(
            project_id=proj.id, subcontractor_id=sub.id, status="active"
        )
    )
    cert = Certification(
        subcontractor_id=sub.id,
        certification_type="OSHA 10",
        certification_number=f"DC-{suffix}",
        expiration_date=date.today() + timedelta(days=7),
        status="valid",
        verification_status="verified",
    )
    session.add(cert)
    await session.flush()

    session.add(
        NotificationPreferences(
            user_id=user.id,
            subcontractor_id=sub.id,
            notify_on_cert_expiration=True,
            email_enabled=email_enabled,
            sms_enabled=sms_enabled,
            custom_phone=phone,
        )
    )
    alert = AlertNotification(
        certification_id=cert.id,
        alert_type="expiration_7d",
        scheduled_for=datetime.now(),
        status="pending",
        method="in_app",
        recipient=str(sub.id),
        subject="Cert expiring",
        body="Cert expires in 7 days.",
        retry_count=0,
        max_retries=3,
        days_until_expiration=7,
    )
    session.add(alert)
    await session.commit()
    return user, sub, alert


@pytest.mark.asyncio
async def test_get_users_to_notify_returns_team_member(db_engine):
    async with AsyncSessionLocal() as session:
        user, sub, _alert = await _seed_deliverable(session)
        pairs = await alert_service._get_users_to_notify_for_subcontractor(session, sub.id)
        assert any(u.id == user.id for u, _prefs in pairs)


@pytest.mark.asyncio
async def test_deliver_marks_sent_on_email_success(db_engine, monkeypatch):
    calls: list[tuple[str, str]] = []

    async def _fake_send(recipient, subject, body, method):
        calls.append((recipient, method))
        return NotificationResult(success=True, message_id="msg-1")

    monkeypatch.setattr(alert_service, "send_notification", _fake_send)

    async with AsyncSessionLocal() as session:
        _user, _sub, alert = await _seed_deliverable(session)
        alert_id = alert.id

    async with AsyncSessionLocal() as session:
        summary = await alert_service.deliver_pending_alerts(session)

    assert summary["sent_email"] >= 1
    assert ("email" in [method for _recipient, method in calls])

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AlertNotification).where(AlertNotification.id == alert_id)
            )
        ).scalar_one()
        assert row.status == "sent"
        assert row.sent_at is not None


@pytest.mark.asyncio
async def test_deliver_marks_failed_on_send_error(db_engine, monkeypatch):
    async def _fake_send(recipient, subject, body, method):
        return NotificationResult(success=False, error="smtp down")

    monkeypatch.setattr(alert_service, "send_notification", _fake_send)

    async with AsyncSessionLocal() as session:
        _user, _sub, alert = await _seed_deliverable(session)
        alert_id = alert.id

    async with AsyncSessionLocal() as session:
        summary = await alert_service.deliver_pending_alerts(session)

    assert summary["failed"] >= 1
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AlertNotification).where(AlertNotification.id == alert_id)
            )
        ).scalar_one()
        assert row.status == "failed"
        assert row.error_message


@pytest.mark.asyncio
async def test_deliver_uses_sms_when_email_disabled(db_engine, monkeypatch):
    calls: list[str] = []

    async def _fake_send(recipient, subject, body, method):
        calls.append(method)
        return NotificationResult(success=True, message_id="msg-sms")

    monkeypatch.setattr(alert_service, "send_notification", _fake_send)

    async with AsyncSessionLocal() as session:
        _user, _sub, alert = await _seed_deliverable(
            session, email_enabled=False, sms_enabled=True, phone="+15551234567"
        )
        alert_id = alert.id

    async with AsyncSessionLocal() as session:
        summary = await alert_service.deliver_pending_alerts(session)

    assert summary["sent_sms"] >= 1
    assert "sms" in calls
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AlertNotification).where(AlertNotification.id == alert_id)
            )
        ).scalar_one()
        assert row.status == "sent"


@pytest.mark.asyncio
async def test_send_alert_to_user_email_default_when_no_prefs(db_engine, monkeypatch):
    async def _fake_send(recipient, subject, body, method):
        return NotificationResult(success=True, message_id="m")

    monkeypatch.setattr(alert_service, "send_notification", _fake_send)

    async with AsyncSessionLocal() as session:
        user, _sub, alert = await _seed_deliverable(session)
        sent, method = await alert_service._send_alert_to_user(session, alert, user, None)

    assert sent is True
    assert method == "email"
