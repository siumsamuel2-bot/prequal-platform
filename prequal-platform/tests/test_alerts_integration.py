"""Integration tests for the alerting service and endpoints.

Runs against the test SQLite database seeded with real subcontractors,
certifications, projects, and alert notifications.
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.compliance import (
    Subcontractor, Certification, Project, ProjectSubcontractor
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_db() -> AsyncSession:
    """Create a fresh seeded DB session for a single test."""
    async with AsyncSessionLocal() as session:
        # Create subcontractor
        sub = Subcontractor(
            company_name="Acme Construction",
            email="acme@example.com",
            phone="555-0100",
            address_line1="123 Main St",
            city="Austin",
            state="TX",
            zip_code="78701",
            status="active",
        )
        session.add(sub)
        await session.flush()

        # Create a project
        proj = Project(
            project_name="Downtown Tower",
            project_number="DT-2026",
            client_name="Big Client Corp",
            start_date=date.today() - timedelta(days=30),
            status="active",
        )
        session.add(proj)
        await session.flush()

        # Link subcontractor to project
        ps = ProjectSubcontractor(
            project_id=proj.id,
            subcontractor_id=sub.id,
            role="Concrete",
            status="active",
        )
        session.add(ps)
        await session.flush()

        # Create a valid certification expiring in 30 days
        cert_30 = Certification(
            subcontractor_id=sub.id,
            certification_type="OSHA 30",
            certification_number="CERT-30",
            issuing_authority="OSHA",
            issue_date=date.today() - timedelta(days=335),
            expiration_date=date.today() + timedelta(days=30),
            status="valid",
            verification_status="verified",
        )
        session.add(cert_30)

        # Create a valid certification expiring in 14 days
        cert_14 = Certification(
            subcontractor_id=sub.id,
            certification_type="First Aid",
            certification_number="CERT-14",
            issuing_authority="Red Cross",
            issue_date=date.today() - timedelta(days=351),
            expiration_date=date.today() + timedelta(days=14),
            status="valid",
            verification_status="verified",
        )
        session.add(cert_14)

        # Create an already-expired certification
        cert_expired = Certification(
            subcontractor_id=sub.id,
            certification_type="Expired Cert",
            certification_number="CERT-EX",
            issuing_authority="Old Authority",
            issue_date=date.today() - timedelta(days=400),
            expiration_date=date.today() - timedelta(days=5),
            status="valid",
            verification_status="verified",
        )
        session.add(cert_expired)

        await session.commit()

        # Attach for test access
        session._sub = sub  # type: ignore[attr-defined]
        session._proj = proj  # type: ignore[attr-defined]
        session._cert_30 = cert_30  # type: ignore[attr-defined]
        session._cert_14 = cert_14  # type: ignore[attr-defined]
        session._cert_exp = cert_expired  # type: ignore[attr-defined]

        yield session

        await session.rollback()
        await session.close()


# ---------------------------------------------------------------------------
# Service-level integration
# ---------------------------------------------------------------------------

class TestAlertServiceIntegration:
    """Test scan_expirations end-to-end with real DB records."""

    @pytest.mark.asyncio
    async def test_scan_flags_expired_certs(self, seeded_db):
        """scan_expirations should mark past-date certs as expired."""
        from app.services.alert_service import scan_expirations
        summary = await scan_expirations(seeded_db)
        assert summary["certifications_expired"] >= 1

    @pytest.mark.asyncio
    async def test_scan_creates_alerts_at_warning_windows(self, seeded_db):
        """scan_expirations should create 30-day and 14-day alerts."""
        from app.services.alert_service import scan_expirations
        summary = await scan_expirations(seeded_db)
        assert summary["alerts_created"] >= 2
        assert summary["warnings_30"] >= 1
        assert summary["warnings_14"] >= 1

    @pytest.mark.asyncio
    async def test_scan_deduplicates_same_day(self, seeded_db):
        """Running scan twice on the same day should not create duplicates."""
        from app.services.alert_service import scan_expirations
        first = await scan_expirations(seeded_db)
        second = await scan_expirations(seeded_db)
        assert second["alerts_created"] == 0
        assert second["certifications_expired"] == 0


# ---------------------------------------------------------------------------
# Endpoint-level integration (uses HTTP client)
# ---------------------------------------------------------------------------

@pytest.fixture
def override_auth():
    """Override get_current_user for endpoint tests."""
    from app.routers import alerts as alerts_router_mod
    from app.routers.auth import TokenData
    from api.main import app

    original_dep = app.dependency_overrides.get(alerts_router_mod.get_current_user)
    app.dependency_overrides[alerts_router_mod.get_current_user] = lambda: TokenData(sub="test", user_id=str(uuid4()))
    yield
    if original_dep is not None:
        app.dependency_overrides[alerts_router_mod.get_current_user] = original_dep
    else:
        app.dependency_overrides.pop(alerts_router_mod.get_current_user, None)


class TestAlertEndpointsIntegration:
    """Test alert REST endpoints via the async HTTP test client."""

    @pytest.mark.asyncio
    async def test_scan_endpoint_triggers_and_returns_summary(self, async_client, override_auth):
        """POST /api/alerts/scan should return a summary with counts."""
        resp = await async_client.post("/api/alerts/scan")
        assert resp.status_code == 202
        body = resp.json()
        assert "message" in body
        assert "summary" in body
        assert "alerts_created" in body["summary"]
        assert "certifications_expired" in body["summary"]
