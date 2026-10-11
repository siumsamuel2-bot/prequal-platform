"""Integration tests for the alert delivery + summary paths (MID-676).

Complements ``test_alerts_integration.py`` (which covers ``scan_expirations``)
by exercising the remaining ``app.services.alert_service`` surface against a
real (SQLite/PostgreSQL-parity) session:

- ``get_alert_summary`` platform-wide and team-scoped
- ``_get_users_to_notify_for_subcontractor`` opt-in / opt-out behaviour
- ``_send_alert_to_user`` email, SMS fallback, and no-channel paths
- ``deliver_pending_alerts`` end-to-end marking of sent / failed / skipped
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

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


def _today_at_min() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


@pytest_asyncio.fixture
async def alert_env(db_engine):
    """Seed one team/user/project/subcontractor/cert chain for delivery tests."""
    async with AsyncSessionLocal() as session:
        suffix = uuid4().hex[:8]

        team = Team(name=f"Compliance Team {suffix}", owner_id=uuid4())
        session.add(team)
        await session.flush()

        user = User(
            email=f"manager-{suffix}@example.com",
            name="Compliance Manager",
            hashed_password="x",
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))

        sub = Subcontractor(
            company_name=f"Acme {suffix}",
            email=f"acme-{suffix}@example.com",
            status="active",
            team_id=team.id,
        )
        session.add(sub)
        await session.flush()

        proj = Project(
            project_name=f"Downtown Tower {suffix}",
            project_number=f"DT-{suffix}",
            status="active",
            team_id=team.id,
        )
        session.add(proj)
        await session.flush()

        session.add(
            ProjectSubcontractor(
                project_id=proj.id,
                subcontractor_id=sub.id,
                role="Concrete",
                status="active",
            )
        )

        cert = Certification(
            subcontractor_id=sub.id,
            certification_type="OSHA 30",
            certification_number=f"CERT-{suffix}",
            issuing_authority="OSHA",
            issue_date=date.today() - timedelta(days=300),
            expiration_date=date.today() + timedelta(days=30),
            status="valid",
            verification_status="verified",
        )
        session.add(cert)
        await session.flush()

        await session.begin_nested()

        session.team = team  # type: ignore[attr-defined]
        session.user = user  # type: ignore[attr-defined]
        session.sub = sub  # type: ignore[attr-defined]
        session.proj = proj  # type: ignore[attr-defined]
        session.cert = cert  # type: ignore[attr-defined]

        yield session

        await session.rollback()
        await session.close()


def _make_alert(cert: Certification, **overrides) -> AlertNotification:
    fields = dict(
        certification_id=cert.id,
        alert_type="expiration_30d",
        scheduled_for=_today_at_min(),
        status="pending",
        method="in_app",
        recipient=str(cert.subcontractor_id),
        subject="Certification expires in 30 days",
        body="OSHA 30 expires soon.",
        retry_count=0,
        max_retries=3,
        days_until_expiration=30,
    )
    fields.update(overrides)
    return AlertNotification(**fields)


class TestGetAlertSummary:
    """get_alert_summary counts and team scoping."""

    @pytest.mark.asyncio
    async def test_team_scoped_counts(self, alert_env):
        session = alert_env
        session.add(_make_alert(session.cert, status="pending", scheduled_for=_today_at_min() + timedelta(days=1)))
        session.add(_make_alert(session.cert, status="acknowledged", scheduled_for=_today_at_min() + timedelta(days=2)))

        expired = Certification(
            subcontractor_id=session.sub.id,
            certification_type="Expired Cert",
            certification_number=f"EXP-{uuid4().hex[:6]}",
            issue_date=date.today() - timedelta(days=400),
            expiration_date=date.today() - timedelta(days=3),
            status="expired",
            verification_status="verified",
        )
        session.add(expired)
        await session.commit()

        summary = await alert_service.get_alert_summary(session, days=30, team_id=session.team.id)
        assert summary["pending_alerts"] == 1
        assert summary["acknowledged_alerts"] == 1
        assert summary["expired_certifications"] == 1
        assert summary["lookback_days"] == 30

    @pytest.mark.asyncio
    async def test_platform_wide_includes_team_rows(self, alert_env):
        session = alert_env
        session.add(_make_alert(session.cert, status="pending", scheduled_for=_today_at_min() + timedelta(days=1)))
        await session.commit()

        summary = await alert_service.get_alert_summary(session, days=30)
        assert summary["pending_alerts"] >= 1
        assert summary["lookback_days"] == 30


class TestUsersToNotify:
    """_get_users_to_notify_for_subcontractor preference handling."""

    @pytest.mark.asyncio
    async def test_includes_team_member_without_prefs(self, alert_env):
        session = alert_env
        users = await alert_service._get_users_to_notify_for_subcontractor(session, session.sub.id)
        assert session.user.id in {u.id for u, _ in users}

    @pytest.mark.asyncio
    async def test_opt_out_excludes_user(self, alert_env):
        session = alert_env
        session.add(
            NotificationPreferences(
                user_id=session.user.id,
                subcontractor_id=session.sub.id,
                notify_on_cert_expiration=False,
            )
        )
        await session.commit()

        users = await alert_service._get_users_to_notify_for_subcontractor(session, session.sub.id)
        assert session.user.id not in {u.id for u, _ in users}

    @pytest.mark.asyncio
    async def test_inactive_user_excluded(self, alert_env):
        session = alert_env
        session.user.is_active = False
        await session.commit()

        users = await alert_service._get_users_to_notify_for_subcontractor(session, session.sub.id)
        assert session.user.id not in {u.id for u, _ in users}


class TestSendAlertToUser:
    """_send_alert_to_user channel selection."""

    @pytest.mark.asyncio
    async def test_email_success(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert)
        calls: list[str] = []

        async def fake_send(recipient, subject, body, method):
            calls.append(method)
            return NotificationResult(success=True, message_id="m-1")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        sent, method = await alert_service._send_alert_to_user(session, alert, session.user, None)
        assert sent is True
        assert method == "email"
        assert calls == ["email"]

    @pytest.mark.asyncio
    async def test_email_failure_falls_back_to_sms(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert)
        prefs = NotificationPreferences(
            user_id=session.user.id,
            subcontractor_id=session.sub.id,
            email_enabled=True,
            sms_enabled=True,
            custom_phone="+15550001111",
        )
        calls: list[str] = []

        async def fake_send(recipient, subject, body, method):
            calls.append(method)
            return NotificationResult(success=(method == "sms"), error=None if method == "sms" else "smtp down")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        sent, method = await alert_service._send_alert_to_user(session, alert, session.user, prefs)
        assert sent is True
        assert method == "sms"
        assert calls == ["email", "sms"]

    @pytest.mark.asyncio
    async def test_sms_enabled_without_phone_is_not_sent(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert)
        prefs = NotificationPreferences(
            user_id=session.user.id,
            subcontractor_id=session.sub.id,
            email_enabled=False,
            sms_enabled=True,
            custom_phone=None,
        )

        async def fake_send(recipient, subject, body, method):
            raise AssertionError("no channel should be attempted without a phone")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        sent, method = await alert_service._send_alert_to_user(session, alert, session.user, prefs)
        assert sent is False
        assert method == "none"

    @pytest.mark.asyncio
    async def test_email_and_sms_failure_is_not_sent(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert)
        prefs = NotificationPreferences(
            user_id=session.user.id,
            subcontractor_id=session.sub.id,
            email_enabled=True,
            sms_enabled=True,
            custom_phone="+15550003333",
        )

        async def fake_send(recipient, subject, body, method):
            return NotificationResult(success=False, error="provider down")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        sent, method = await alert_service._send_alert_to_user(session, alert, session.user, prefs)
        assert sent is False
        assert method == "none"

    @pytest.mark.asyncio
    async def test_all_channels_disabled(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert)
        prefs = NotificationPreferences(
            user_id=session.user.id,
            subcontractor_id=session.sub.id,
            email_enabled=False,
            sms_enabled=False,
        )

        async def fake_send(recipient, subject, body, method):
            raise AssertionError("no channel enabled")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        sent, method = await alert_service._send_alert_to_user(session, alert, session.user, prefs)
        assert sent is False
        assert method == "none"


class TestDeliverPendingAlerts:
    """deliver_pending_alerts end-to-end status transitions."""

    @pytest.mark.asyncio
    async def test_success_marks_alert_sent(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert, scheduled_for=_today_at_min())
        session.add(alert)
        await session.commit()

        async def fake_send(recipient, subject, body, method):
            return NotificationResult(success=True, message_id="m-2")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        summary = await alert_service.deliver_pending_alerts(session)
        await session.refresh(alert)

        assert alert.status == "sent"
        assert alert.sent_at is not None
        assert summary["sent_email"] >= 1
        assert summary["by_alert_type"]["expiration_30d"]["sent"] >= 1

    @pytest.mark.asyncio
    async def test_failure_marks_alert_failed(self, alert_env, monkeypatch):
        session = alert_env
        alert = _make_alert(session.cert, scheduled_for=_today_at_min())
        session.add(alert)
        await session.commit()

        async def fake_send(recipient, subject, body, method):
            return NotificationResult(success=False, error="provider down")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        summary = await alert_service.deliver_pending_alerts(session)
        await session.refresh(alert)

        assert alert.status == "failed"
        assert alert.error_message
        assert summary["failed"] >= 1

    @pytest.mark.asyncio
    async def test_no_recipients_is_skipped(self, alert_env):
        session = alert_env
        session.user.is_active = False
        alert = _make_alert(session.cert, scheduled_for=_today_at_min())
        session.add(alert)
        await session.commit()

        summary = await alert_service.deliver_pending_alerts(session)
        await session.refresh(alert)

        assert summary["skipped_no_recipients"] >= 1
        assert alert.status == "pending"

    @pytest.mark.asyncio
    async def test_sms_delivery_is_counted(self, alert_env, monkeypatch):
        session = alert_env
        session.add(
            NotificationPreferences(
                user_id=session.user.id,
                subcontractor_id=session.sub.id,
                email_enabled=False,
                sms_enabled=True,
                custom_phone="+15550004444",
            )
        )
        alert = _make_alert(session.cert, scheduled_for=_today_at_min())
        session.add(alert)
        await session.commit()

        async def fake_send(recipient, subject, body, method):
            return NotificationResult(success=True, message_id="m-sms")

        monkeypatch.setattr(alert_service, "send_notification", fake_send)

        summary = await alert_service.deliver_pending_alerts(session)
        await session.refresh(alert)

        assert alert.status == "sent"
        assert summary["sent_sms"] >= 1


class TestScanWarningWindow:
    """scan_expirations covers the 7-day warning window."""

    @pytest.mark.asyncio
    async def test_seven_day_window_creates_alert(self, alert_env):
        session = alert_env
        cert_7 = Certification(
            subcontractor_id=session.sub.id,
            certification_type="First Aid",
            certification_number=f"AID-{uuid4().hex[:6]}",
            issuing_authority="Red Cross",
            issue_date=date.today() - timedelta(days=358),
            expiration_date=date.today() + timedelta(days=7),
            status="valid",
            verification_status="verified",
        )
        session.add(cert_7)
        await session.commit()

        summary = await alert_service.scan_expirations(session)
        assert summary["warnings_7"] >= 1
