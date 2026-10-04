"""pytest fixtures for the Prequal alerting test suite.

Provides async database session and test client fixtures.
"""

import os

import uuid

# PostgreSQL parity mode (MID-628): when TEST_DATABASE_URL points at a real
# PostgreSQL instance, the whole suite runs against it with the real Alembic
# migrations (no SQLite shims). Default remains a file-based SQLite with a
# unique path per test session so parallel or overlapping runs do not collide.
_test_db_path = os.path.join(os.path.dirname(__file__), "..", f"test_prequal_{uuid.uuid4().hex}.db")
_pg_test_url = os.environ.get("TEST_DATABASE_URL", "")
_use_postgres = _pg_test_url.startswith("postgresql")
if _use_postgres:
    os.environ["DATABASE_URL"] = _pg_test_url
else:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"
# Ensure the auth module can import during tests even without an ambient secret.
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long-here")

import pytest_asyncio  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PGUUID  # noqa: E402

from api.main import app as fastapi_app  # noqa: E402
from app.database import AsyncSessionLocal, Base, engine  # noqa: E402

# Import models so Base.metadata includes all tables
import app.models.compliance  # noqa: F401,E402


@compiles(PGUUID, "sqlite")
def _compile_pg_uuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID columns as CHAR(32) under SQLite.

    SQLite would otherwise give a bare ``UUID`` column NUMERIC affinity and
    coerce all-digit hex UUID strings (e.g. ``00000000-...-0001``) into
    integers/floats, which then fail to hydrate back into UUID objects.
    """
    return "CHAR(32)"


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create an async engine and initialize all tables."""
    if _use_postgres:
        # PostgreSQL parity mode: apply the real Alembic migrations so
        # materialized views and Alembic-only tables exist exactly as in
        # production. SQLite shims are not used in this mode.
        _run_alembic_migrations("head")
    else:
        # Clean up any stale test DB from a previous run
        if os.path.exists(_test_db_path):
            try:
                os.remove(_test_db_path)
            except PermissionError:
                pass  # Windows may hold the file; create_all below is idempotent
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Analytics materialized views are PostgreSQL-only; create regular
            # views in SQLite so pipeline tests can execute.
            await _create_analytics_views_sqlite(conn)
            # Data quality monitoring tables are Alembic-only; create them for
            # test compatibility when running under SQLite.
            await _create_data_quality_monitoring_tables_sqlite(conn)
    yield engine
    if _use_postgres:
        # Best-effort teardown of the disposable test database
        try:
            _run_alembic_migrations("base")
        except Exception:  # noqa: BLE001 - teardown must not fail the suite
            pass
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if os.path.exists(_test_db_path):
            try:
                os.remove(_test_db_path)
            except PermissionError:
                pass  # Windows may hold the file; let temp cleanup handle it
    await engine.dispose()


def _run_alembic_migrations(revision: str) -> None:
    """Run Alembic migrations against the PostgreSQL test database.

    Alembic requires a sync driver, so the asyncpg URL from TEST_DATABASE_URL
    is rewritten to psycopg2 (present in requirements.txt). alembic.ini's
    ``script_location = %(here)s/alembic`` resolves the migrations directory.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", _pg_test_url.replace("+asyncpg", "+psycopg2"))
    command.upgrade(cfg, revision)


async def _create_data_quality_monitoring_tables_sqlite(conn):
    """Create data quality monitoring tables for SQLite test database.

    These tables are defined in Alembic migration 014 and are not part
    of Base.metadata (they are created via raw SQL in the migration).
    For test compatibility under SQLite, create simplified SQLite versions.
    """
    from sqlalchemy import text

    # data_quality_alerts
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS data_quality_alerts (
            id TEXT PRIMARY KEY,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            source_table TEXT,
            source_job TEXT,
            message TEXT NOT NULL,
            threshold_value REAL,
            actual_value REAL,
            is_acknowledged INTEGER NOT NULL DEFAULT 0,
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    # pipeline_performance_logs
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS pipeline_performance_logs (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            job_name TEXT NOT NULL,
            job_type TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms INTEGER,
            records_in INTEGER DEFAULT 0,
            records_out INTEGER DEFAULT 0,
            cache_hits INTEGER DEFAULT 0,
            cache_misses INTEGER DEFAULT 0,
            api_requests INTEGER DEFAULT 0,
            api_errors INTEGER DEFAULT 0,
            avg_api_latency_ms INTEGER,
            max_api_latency_ms INTEGER,
            error_message TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    # archived_sync_run_logs
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS archived_sync_run_logs (
            id TEXT PRIMARY KEY,
            job_name TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT,
            triggered_by TEXT,
            started_at TEXT,
            completed_at TEXT,
            records_processed INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            error_message TEXT,
            run_metadata TEXT,
            archived_at TEXT DEFAULT CURRENT_TIMESTAMP,
            archive_reason TEXT DEFAULT 'retention'
        )
        """
    ))

    # archived_data_quality_results
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS archived_data_quality_results (
            id TEXT PRIMARY KEY,
            check_id TEXT NOT NULL,
            sync_run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            records_checked INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            failure_rate REAL,
            execution_time_ms INTEGER,
            sample_failures TEXT,
            executed_at TEXT,
            archived_at TEXT DEFAULT CURRENT_TIMESTAMP,
            archive_reason TEXT DEFAULT 'retention'
        )
        """
    ))

    # data_quality_field_metrics (migration 027, MID-605)
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS data_quality_field_metrics (
            id TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            total_rows INTEGER NOT NULL DEFAULT 0,
            null_count INTEGER NOT NULL DEFAULT 0,
            null_rate REAL,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            duplicate_rate REAL
        )
        """
    ))

    # data_quality_schema_snapshots (migration 027, MID-605)
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS data_quality_schema_snapshots (
            id TEXT PRIMARY KEY,
            table_name TEXT NOT NULL,
            columns_json TEXT NOT NULL,
            captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    # mv_sync_health_dashboard view for SQLite test compatibility
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_sync_health_dashboard AS
        SELECT
            job_name,
            job_type,
            COUNT(*) AS total_runs,
            COUNT(*) FILTER (WHERE status = 'completed') AS successful_runs,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs,
            COUNT(*) FILTER (WHERE status = 'partial') AS partial_runs,
            SUM(records_processed) AS total_records_processed,
            SUM(records_inserted) AS total_records_inserted,
            SUM(records_updated) AS total_records_updated,
            SUM(records_failed) AS total_records_failed,
            CASE WHEN SUM(records_processed) > 0 THEN
                ROUND(CAST(SUM(records_failed) AS REAL) / SUM(records_processed), 4)
            ELSE 0 END AS error_rate,
            AVG(records_processed) AS avg_records_per_run,
            AVG(
                (julianday(completed_at) - julianday(started_at)) * 86400
            ) AS avg_run_duration_seconds,
            MAX(started_at) AS last_run_at,
            datetime('now') AS computed_at
        FROM sync_run_logs
        WHERE started_at >= date('now', '-30 days')
        GROUP BY job_name, job_type
        """
    ))

    # mv_match_accuracy view for SQLite test compatibility
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_match_accuracy AS
        SELECT
            'violations' AS source_table,
            COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS matched_count,
            COUNT(*) FILTER (WHERE subcontractor_id IS NULL) AS unmatched_count,
            COUNT(*) AS total_count,
            CASE WHEN COUNT(*) > 0 THEN
                ROUND(CAST(COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS REAL) / COUNT(*), 4)
            ELSE 0 END AS match_rate,
            datetime('now') AS computed_at
        FROM violations
        WHERE is_osha_violation = 1
        UNION ALL
        SELECT
            'state_credential_records' AS source_table,
            COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS matched_count,
            COUNT(*) FILTER (WHERE subcontractor_id IS NULL) AS unmatched_count,
            COUNT(*) AS total_count,
            CASE WHEN COUNT(*) > 0 THEN
                ROUND(CAST(COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS REAL) / COUNT(*), 4)
            ELSE 0 END AS match_rate,
            datetime('now') AS computed_at
        FROM state_credential_records
        """
    ))

    # mv_data_quality_summary view for SQLite test compatibility
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_data_quality_summary AS
        SELECT
            dqc.id AS check_id,
            dqc.check_name,
            dqc.table_name,
            dqc.column_name,
            dqc.check_type,
            dqc.severity,
            dqc.is_active,
            COUNT(dqr.id) AS total_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'passed') AS passed_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'failed') AS failed_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'warning') AS warning_runs,
            AVG(dqr.failure_rate) AS avg_failure_rate,
            MAX(dqr.executed_at) AS last_executed_at,
            datetime('now') AS computed_at
        FROM data_quality_checks dqc
        LEFT JOIN data_quality_results dqr ON dqr.check_id = dqc.id
        GROUP BY dqc.id, dqc.check_name, dqc.table_name, dqc.column_name, dqc.check_type, dqc.severity, dqc.is_active
        """
    ))

    # mv_pipeline_performance_summary view for SQLite test compatibility
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_pipeline_performance_summary AS
        SELECT
            job_name,
            job_type,
            stage_name,
            COUNT(*) AS total_runs,
            AVG(duration_ms) AS avg_duration_ms,
            MIN(duration_ms) AS min_duration_ms,
            MAX(duration_ms) AS max_duration_ms,
            AVG(records_in) AS avg_records_in,
            AVG(api_requests) AS avg_api_requests,
            AVG(avg_api_latency_ms) AS avg_api_latency_ms,
            MAX(max_api_latency_ms) AS max_api_latency_ms,
            AVG(cache_hits) AS avg_cache_hits,
            AVG(cache_misses) AS avg_cache_misses,
            CASE WHEN SUM(cache_hits + cache_misses) > 0 THEN
                ROUND(CAST(SUM(cache_hits) AS REAL) / SUM(cache_hits + cache_misses), 4)
            ELSE 0 END AS cache_hit_rate,
            datetime('now') AS computed_at
        FROM pipeline_performance_logs
        WHERE started_at >= date('now', '-30 days')
        GROUP BY job_name, job_type, stage_name
        """
    ))

    # mv_subcontractor_compliance_trends view for SQLite
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_subcontractor_compliance_trends AS
        SELECT
            date('now', '-90 days') AS trend_date,
            (SELECT COUNT(DISTINCT id) FROM subcontractors) AS total_subcontractors,
            (SELECT COUNT(DISTINCT id) FROM subcontractors WHERE status = 'active') AS active_subcontractors,
            (SELECT COUNT(DISTINCT s.id) FROM subcontractors s
             WHERE s.status = 'active'
             AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
             AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
            ) AS compliant_subcontractors,
            CASE WHEN (SELECT COUNT(*) FROM subcontractors WHERE status = 'active') > 0 THEN
                ROUND(CAST((SELECT COUNT(DISTINCT s.id) FROM subcontractors s
                 WHERE s.status = 'active'
                 AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
                 AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
                ) AS REAL) / (SELECT COUNT(*) FROM subcontractors WHERE status = 'active'), 2) * 100
            ELSE 0 END AS compliance_rate,
            (SELECT COUNT(*) FROM certifications c WHERE c.status = 'valid'
             AND c.expiration_date >= date('now') AND c.expiration_date <= date('now', '+30 days')) AS expiring_soon_30d,
            (SELECT COUNT(*) FROM violations WHERE status = 'open') AS subcontractors_with_violations,
            (SELECT COALESCE(SUM(penalty_amount), 0) FROM violations WHERE status = 'open') AS total_open_penalties,
            datetime('now') AS computed_at
        """
    ))

    # mv_certification_expiration_trends view for SQLite
    await conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS mv_certification_expiration_trends (
            trend_date TEXT PRIMARY KEY,
            valid_certs INTEGER,
            expired_certs INTEGER,
            expiring_7d INTEGER,
            expiring_30d INTEGER,
            expiring_60d INTEGER,
            computed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))


async def _create_analytics_views_sqlite(conn):
    """Create analytics views for SQLite test database.

    PostgreSQL uses materialized views driven by Alembic migration 010.
    SQLite does not support materialized views, so we create regular views
    with the same column layout for test compatibility.
    """
    from sqlalchemy import text
    # mv_feature_adoption_summary
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_feature_adoption_summary AS
        SELECT
            'feature_a' AS feature_name,
            date('now', '-1 days') AS event_date,
            0 AS total_events,
            0 AS unique_users,
            0 AS view_count,
            0 AS action_count,
            0 AS export_count,
            datetime('now') AS computed_at
        FROM users LIMIT 1
        """
    ))
    # mv_system_health_summary
    await conn.execute(text(
        """
        CREATE VIEW IF NOT EXISTS mv_system_health_summary AS
        SELECT
            'service_1' AS service_name,
            'metric_a' AS metric_name,
            'count' AS metric_unit,
            0 AS avg_value,
            0 AS min_value,
            0 AS max_value,
            0 AS p95_value,
            0 AS total_count,
            datetime('now') AS computed_at
        FROM users LIMIT 1
        """
    ))
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


@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limiter():
    """Reset the app rate-limit storage so cross-suite runs don't hit 429.

    The limiter state lives in a module-global MemoryStorage instance keyed by
    client IP; without a per-test reset, suites that issue >20 requests/min
    accumulate hits and fail with spurious 429s.
    """
    try:
        from app.middleware.rate_limit import _rate_storage  # noqa: WPS433

        _rate_storage._strategy.storage.reset()
    except Exception:  # noqa: BLE001 - test isolation must not fail the suite
        pass
    yield
