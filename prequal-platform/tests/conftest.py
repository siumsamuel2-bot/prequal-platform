"""pytest fixtures for the Prequal alerting test suite.

Provides async database session and test client fixtures.
"""

import os

# Use a file-based SQLite so that multiple AsyncSession connections share
# the same database. In-memory SQLite creates a fresh DB per connection.
_test_db_path = os.path.join(os.path.dirname(__file__), "..", "test_prequal.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"

import pytest_asyncio  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from api.main import app as fastapi_app  # noqa: E402
from app.database import AsyncSessionLocal, Base, engine  # noqa: E402

# Import models so Base.metadata includes all tables
import app.models.compliance  # noqa: F401,E402


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create an async engine and initialize all tables."""
    # Clean up any stale test DB from a previous run
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Analytics materialized views are PostgreSQL-only; create regular
        # views in SQLite so pipeline tests can execute.
        await _create_analytics_views_sqlite(conn)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists(_test_db_path):
        try:
            os.remove(_test_db_path)
        except PermissionError:
            pass  # Windows may hold the file; let temp cleanup handle it


async def _create_analytics_views_sqlite(conn):
    """Create analytics views for SQLite test database.

    PostgreSQL uses materialized views driven by Alembic migration 010.
    SQLite does not support materialized views, so we create regular views
    with the same column layout for test compatibility.
    """
    from sqlalchemy import text
    # mv_compliance_summary
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_compliance_summary AS
        SELECT
            COUNT(DISTINCT s.id) AS total_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.id END) AS active_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'suspended' THEN s.id END) AS suspended_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'blacklisted' THEN s.id END) AS blacklisted_subcontractors,
            COUNT(DISTINCT CASE
                WHEN s.status = 'active'
                    AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
                    AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
                THEN s.id END) AS compliant_subcontractors,
            COUNT(DISTINCT CASE
                WHEN EXISTS (SELECT 1 FROM certifications c
                    WHERE c.subcontractor_id = s.id
                    AND c.status = 'valid'
                    AND c.expiration_date <= date('now', '+30 days')
                    AND c.expiration_date >= date('now'))
                THEN s.id END) AS expiring_soon_30d,
            COUNT(DISTINCT CASE
                WHEN EXISTS (SELECT 1 FROM certifications c
                    WHERE c.subcontractor_id = s.id
                    AND c.status = 'valid'
                    AND c.expiration_date <= date('now', '+60 days')
                    AND c.expiration_date >= date('now'))
                THEN s.id END) AS expiring_soon_60d,
            (SELECT COUNT(*) FROM violations WHERE status = 'open') AS open_violations,
            (SELECT COUNT(*) FROM violations WHERE status = 'open' AND is_osha_violation = 1) AS open_osha_violations,
            COALESCE((SELECT SUM(penalty_amount) FROM violations WHERE status = 'open'), 0) AS total_open_penalties,
            (SELECT COUNT(*) FROM certifications WHERE status = 'valid') AS valid_certifications,
            (SELECT COUNT(*) FROM certifications WHERE status = 'expired') AS expired_certifications,
            (SELECT COUNT(*) FROM certifications WHERE status = 'pending_verification') AS pending_verification_certs,
            datetime('now') AS computed_at
        FROM subcontractors s;
        """
    ))

    # mv_compliance_trends
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_compliance_trends AS
        SELECT
            date('now', '-365 days') AS trend_date,
            (SELECT COUNT(DISTINCT s.id) FROM subcontractors s WHERE s.status != 'inactive') AS active_subcontractors,
            (SELECT COUNT(DISTINCT c.id) FROM certifications c WHERE c.status = 'valid') AS valid_certifications,
            (SELECT COUNT(DISTINCT c.id) FROM certifications c WHERE c.status = 'expired') AS expired_certifications,
            (SELECT COUNT(DISTINCT v.id) FROM violations v WHERE v.status = 'open') AS open_violations,
            (SELECT COUNT(DISTINCT v.id) FROM violations v WHERE v.status = 'open' AND v.is_osha_violation = 1) AS open_osha_violations,
            0.0 AS compliance_percentage,
            datetime('now') AS computed_at;
        """
    ))

    # mv_certification_status
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_certification_status AS
        SELECT
            s.id AS subcontractor_id,
            s.company_name,
            s.email,
            s.status AS subcontractor_status,
            c.id AS certification_id,
            c.certification_type,
            c.certification_number,
            c.issue_date,
            c.expiration_date,
            c.status AS certification_status,
            c.verification_status,
            CASE
                WHEN c.expiration_date < date('now') THEN 'expired'
                WHEN c.expiration_date <= date('now', '+7 days') THEN 'critical'
                WHEN c.expiration_date <= date('now', '+30 days') THEN 'warning'
                WHEN c.expiration_date <= date('now', '+60 days') THEN 'attention'
                ELSE 'valid'
            END AS expiration_bucket,
            julianday(date('now')) - julianday(c.expiration_date) AS days_until_expiration,
            c.verified_at,
            c.created_at,
            datetime('now') AS computed_at
        FROM subcontractors s
        JOIN certifications c ON c.subcontractor_id = s.id
        WHERE s.status = 'active'
        ORDER BY c.expiration_date ASC;
        """
    ))

    # mv_project_compliance
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_project_compliance AS
        SELECT
            p.id AS project_id,
            p.project_name,
            p.project_number,
            p.status AS project_status,
            p.start_date,
            p.estimated_end_date,
            COUNT(DISTINCT ps.subcontractor_id) AS total_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'active' THEN ps.subcontractor_id END) AS active_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'suspended' THEN ps.subcontractor_id END) AS suspended_subcontractors,
            COUNT(DISTINCT CASE
                WHEN s.status = 'active'
                    AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
                    AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
                THEN s.id END) AS compliant_subcontractors,
            COUNT(DISTINCT CASE WHEN v.status = 'open' THEN v.id END) AS open_violations,
            COUNT(DISTINCT CASE WHEN v.status = 'open' AND v.is_osha_violation = 1 THEN v.id END) AS open_osha_violations,
            SUM(CASE WHEN v.status = 'open' THEN v.penalty_amount ELSE 0 END) AS total_open_penalties,
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1 FROM certifications c
                WHERE c.subcontractor_id = s.id
                AND c.status = 'valid'
                AND c.expiration_date <= date('now', '+30 days')
                AND c.expiration_date >= date('now')
            ) THEN s.id END) AS expiring_soon_subcontractors,
            datetime('now') AS computed_at
        FROM projects p
        LEFT JOIN project_subcontractors ps ON ps.project_id = p.id AND ps.status = 'active'
        LEFT JOIN subcontractors s ON s.id = ps.subcontractor_id
        LEFT JOIN violations v ON v.project_id = p.id
        GROUP BY p.id, p.project_name, p.project_number, p.status, p.start_date, p.estimated_end_date
        ORDER BY p.created_at DESC;
        """
    ))

    # mv_recent_alerts
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_recent_alerts AS
        SELECT
            an.id AS alert_id,
            an.certification_id,
            an.alert_type,
            an.scheduled_for,
            an.sent_at,
            an.status,
            an.method,
            an.recipient,
            an.subject,
            an.acknowledged_at,
            an.days_until_expiration,
            an.created_at,
            c.certification_type,
            c.expiration_date,
            s.id AS subcontractor_id,
            s.company_name AS subcontractor_name,
            s.email AS subcontractor_email,
            datetime('now') AS computed_at
        FROM alert_notifications an
        JOIN certifications c ON c.id = an.certification_id
        JOIN subcontractors s ON s.id = c.subcontractor_id
        WHERE an.created_at >= date('now', '-90 days')
        ORDER BY an.created_at DESC;
        """
    ))


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a fresh async session for each test."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture
async def async_client(db_engine):
    """Async HTTP test client for FastAPI."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
