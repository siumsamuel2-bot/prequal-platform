"""Endpoint-level coverage for app/routers/alerts.py (MID-676).

These exercise the alert REST endpoints end-to-end through the ASGI test client
against the real (SQLite or PostgreSQL-parity) test database. They complement:

- ``test_alerts.py`` - schema/contract assertions only.
- ``test_alerts_integration.py`` - scan service + POST /scan.
- ``test_alerts_tenant_isolation.py`` - tenant scoping via mocked sessions.

Regression covered here: ``alert_service`` writes per-window ``alert_type``
values (``expiration_30d`` / ``14d`` / ``7d``). Before the ``AlertType`` enum
included them, every scan-generated alert made
``GET /api/alerts`` (and ``/by-contractor``, ``/by-project``, acknowledge)
raise a Pydantic ``ResponseValidationError`` -> HTTP 500.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio

from api.main import app
from app.database import AsyncSessionLocal
from app.models.compliance import (
    AlertNotification,
    Certification,
    Project,
    ProjectSubcontractor,
    Subcontractor,
)
from app.routers import alerts as alerts_module
from app.routers.auth import TokenData


@pytest.fixture
def auth_override():
    """Install an overridable ``get_current_user`` for endpoint tests."""

    def _set(role: str = "admin", user_id: str | None = None) -> str:
        uid = user_id or str(uuid.uuid4())
        app.dependency_overrides[alerts_module.get_current_user] = lambda: TokenData(
            sub="tester", user_id=uid, role=role
        )
        return uid

    yield _set
    app.dependency_overrides.pop(alerts_module.get_current_user, None)


@pytest_asyncio.fixture
async def seeded_alert(db_engine):
    """Seed a subcontractor/project/cert/alert with an emitted alert_type."""
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:8]
        sub = Subcontractor(
            company_name="Alertco Builders",
            email=f"alertco-{suffix}@example.com",
            status="active",
        )
        proj = Project(
            project_name="Alert Tower",
            project_number=f"AT-{suffix}",
            status="active",
            start_date=date.today() - timedelta(days=10),
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
            certification_type="OSHA 30",
            certification_number=f"CERT-{suffix}",
            issuing_authority="OSHA",
            issue_date=date.today() - timedelta(days=335),
            expiration_date=date.today() + timedelta(days=30),
            status="valid",
            verification_status="verified",
        )
        session.add(cert)
        await session.flush()

        alert = AlertNotification(
            certification_id=cert.id,
            alert_type="expiration_30d",
            scheduled_for=datetime.now(),
            status="pending",
            method="in_app",
            recipient=str(sub.id),
            subject="Certification expires in 30 days",
            body="OSHA 30 expires in 30 days.",
            retry_count=0,
            max_retries=3,
            days_until_expiration=30,
        )
        session.add(alert)
        await session.commit()

        return {
            "sub": str(sub.id),
            "proj": str(proj.id),
            "cert": str(cert.id),
            "alert": str(alert.id),
        }


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_admin_lists_scan_generated_alert(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        resp = await async_client.get("/api/alerts")
        assert resp.status_code == 200, resp.text
        ids = [row["id"] for row in resp.json()]
        assert seeded_alert["alert"] in ids

    @pytest.mark.asyncio
    async def test_filters_by_status_type_and_days(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        for query in (
            "status_filter=pending",
            "alert_type=expiration_30d",
            "days_until=30",
        ):
            resp = await async_client.get(f"/api/alerts?{query}")
            assert resp.status_code == 200, f"{query}: {resp.text}"
            assert seeded_alert["alert"] in [row["id"] for row in resp.json()]

    @pytest.mark.asyncio
    async def test_viewer_without_team_sees_nothing(self, async_client, auth_override, seeded_alert):
        auth_override(role="viewer")
        resp = await async_client.get("/api/alerts")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAlertsByContractor:
    @pytest.mark.asyncio
    async def test_enriched_response(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        resp = await async_client.get(f"/api/alerts/by-contractor/{seeded_alert['sub']}")
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        row = next(r for r in rows if r["id"] == seeded_alert["alert"])
        assert row["contractor_name"] == "Alertco Builders"
        assert seeded_alert["proj"] in row["project_ids"]

    @pytest.mark.asyncio
    async def test_contractor_without_certs_returns_empty(self, async_client, auth_override, db_engine):
        auth_override(role="admin")
        async with AsyncSessionLocal() as session:
            sub = Subcontractor(
                company_name="No Certs LLC",
                email=f"nocerts-{uuid.uuid4().hex[:8]}@example.com",
                status="active",
            )
            session.add(sub)
            await session.commit()
            sub_id = str(sub.id)
        resp = await async_client.get(f"/api/alerts/by-contractor/{sub_id}")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_viewer_cross_team_contractor_404(self, async_client, auth_override, seeded_alert):
        auth_override(role="viewer")
        resp = await async_client.get(f"/api/alerts/by-contractor/{seeded_alert['sub']}")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAlertsByProject:
    @pytest.mark.asyncio
    async def test_enriched_response(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        resp = await async_client.get(f"/api/alerts/by-project/{seeded_alert['proj']}")
        assert resp.status_code == 200, resp.text
        assert seeded_alert["alert"] in [row["id"] for row in resp.json()]

    @pytest.mark.asyncio
    async def test_project_without_subcontractors_returns_empty(self, async_client, auth_override, db_engine):
        auth_override(role="admin")
        async with AsyncSessionLocal() as session:
            proj = Project(
                project_name="Empty Project",
                project_number=f"EP-{uuid.uuid4().hex[:8]}",
                status="active",
            )
            session.add(proj)
            await session.commit()
            proj_id = str(proj.id)
        resp = await async_client.get(f"/api/alerts/by-project/{proj_id}")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAcknowledgeAlert:
    @pytest.mark.asyncio
    async def test_acknowledge_then_conflict(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        first = await async_client.patch(f"/api/alerts/{seeded_alert['alert']}/acknowledge")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "acknowledged"
        assert first.json()["acknowledged_at"] is not None

        second = await async_client.patch(f"/api/alerts/{seeded_alert['alert']}/acknowledge")
        assert second.status_code == 400

    @pytest.mark.asyncio
    async def test_unknown_alert_404(self, async_client, auth_override, db_engine):
        auth_override(role="admin")
        resp = await async_client.patch(f"/api/alerts/{uuid.uuid4()}/acknowledge")
        assert resp.status_code == 404


class TestSummaryAndDelivery:
    @pytest.mark.asyncio
    async def test_summary_admin(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        resp = await async_client.get("/api/alerts/summary?days=30")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) >= {
            "pending_alerts",
            "acknowledged_alerts",
            "expired_certifications",
            "lookback_days",
        }

    @pytest.mark.asyncio
    async def test_summary_viewer_without_team_is_zeroed(self, async_client, auth_override, seeded_alert):
        auth_override(role="viewer")
        resp = await async_client.get("/api/alerts/summary")
        assert resp.status_code == 200
        assert resp.json()["pending_alerts"] == 0

    @pytest.mark.asyncio
    async def test_deliver_endpoint_returns_summary(self, async_client, auth_override, seeded_alert):
        auth_override(role="admin")
        resp = await async_client.post("/api/alerts/deliver")
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["message"] == "Alert delivery completed"
        assert "total_processed" in body["summary"]


class TestAlertPreferences:
    @pytest.mark.asyncio
    async def test_get_creates_defaults(self, async_client, auth_override, db_engine):
        uid = auth_override(role="admin")
        resp = await async_client.get("/api/alerts/preferences")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"] == uid
        assert body["advance_notice_days"] == 30
        assert body["alert_methods"] == ["email"]

    @pytest.mark.asyncio
    async def test_post_creates_then_updates(self, async_client, auth_override, db_engine):
        uid = auth_override(role="admin")
        payload = {
            "user_id": uid,
            "advance_notice_days": 15,
            "alert_methods": ["email", "sms"],
            "is_active": True,
        }
        created = await async_client.post("/api/alerts/preferences", json=payload)
        assert created.status_code == 200, created.text
        assert created.json()["advance_notice_days"] == 15

        payload["advance_notice_days"] = 7
        updated = await async_client.post("/api/alerts/preferences", json=payload)
        assert updated.status_code == 200, updated.text
        assert updated.json()["advance_notice_days"] == 7


class TestNotificationPreferences:
    @pytest.mark.asyncio
    async def test_get_defaults_when_unset(self, async_client, auth_override, db_engine):
        auth_override(role="admin")
        resp = await async_client.get("/api/alerts/notification-preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email_enabled"] is True
        assert body["notify_on_cert_expiration_days"] == [30, 14, 7]

    @pytest.mark.asyncio
    async def test_put_creates_then_updates(self, async_client, auth_override, db_engine):
        # Use the conftest sentinel admin identity (00000000-...-0001, backed by
        # a real users row in PG mode): notification_preferences.user_id has a
        # real FK to users and PG enforces it, unlike SQLite (MID-726).
        auth_override(role="admin", user_id="00000000-0000-0000-0000-000000000001")
        created = await async_client.put(
            "/api/alerts/notification-preferences",
            json={"email_enabled": False, "sms_enabled": True, "max_emails_per_day": 5},
        )
        assert created.status_code == 200, created.text
        assert created.json()["email_enabled"] is False

        updated = await async_client.put(
            "/api/alerts/notification-preferences",
            json={"digest_enabled": True, "digest_frequency": "weekly"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["digest_enabled"] is True
