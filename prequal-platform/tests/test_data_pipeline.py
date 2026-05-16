"""Tests for the data pipeline service (sync_run_logs, data quality, analytics views).

Tests run against a temporary file-based SQLite database via the
database fixture in conftest.py so that sessions created inside the
data-pipeline code (which call ``AsyncSessionLocal()``) share the same
backend with the test.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select as sa_select, text as sa_text
from app.models.compliance import (
    DataQualityCheck,
    DataQualityResult,
    SyncRunLog,
    StateCredentialRecord,
)
from app.services import data_pipeline as dp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_quality_checks(db) -> None:
    """Insert a few known data-quality checks into the DB."""
    from datetime import datetime as _dt
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
    checks = [
        DataQualityCheck(
            id=uuid4(),
            check_name=f"no_bad_emails_{suffix}",
            table_name="subcontractors",
            column_name="email",
            check_type="custom",
            check_query="SELECT 0",  # always pass
            severity="warning",
            is_active=True,
            description="Stub check that always passes.",
            created_at=_dt.now(),
            updated_at=_dt.now(),
        ),
        DataQualityCheck(
            id=uuid4(),
            check_name=f"always_fails_{suffix}",
            table_name="subcontractors",
            column_name="email",
            check_type="custom",
            check_query="SELECT 1",  # always fail
            severity="error",
            is_active=True,
            description="Stub check that always fails.",
            created_at=_dt.now(),
            updated_at=_dt.now(),
        ),
        DataQualityCheck(
            id=uuid4(),
            check_name=f"inactive_check_{suffix}",
            table_name="subcontractors",
            column_name="email",
            check_type="custom",
            check_query="SELECT 1",
            severity="error",
            is_active=False,
            description="Should be ignored.",
            created_at=_dt.now(),
            updated_at=_dt.now(),
        ),
    ]
    for c in checks:
        db.add(c)
    await db.commit()


# ---------------------------------------------------------------------------
# 1. Sync Run Log helpers
# ---------------------------------------------------------------------------

class TestSyncRunLogHelpers:
    @pytest.mark.asyncio
    async def test_open_run_creates_running_row(self, db_session):
        run = await dp._open_run(db_session, "test_job", "osha_daily_sync")
        await db_session.refresh(run)
        assert run.status == "running"
        assert run.job_name == "test_job"
        assert run.job_type == "osha_daily_sync"
        assert isinstance(run.id, UUID)

    @pytest.mark.asyncio
    async def test_close_run_updates_stats(self, db_session):
        run = await dp._open_run(db_session, "test_job", "osha_daily_sync")
        run = await dp._close_run(
            db_session,
            run,
            status="completed",
            stats={
                "records_processed": 10,
                "records_inserted": 5,
                "records_updated": 3,
                "records_failed": 2,
            },
        )
        assert run.status == "completed"
        assert run.records_processed == 10
        assert run.records_inserted == 5
        assert run.records_updated == 3
        assert run.records_failed == 2
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_close_run_with_error(self, db_session):
        run = await dp._open_run(db_session, "test_job", "osha_daily_sync")
        run = await dp._close_run(db_session, run, status="failed", error="Boom")
        assert "Boom" in (run.error_message or "")
        assert run.status == "failed"


# ---------------------------------------------------------------------------
# 2. Data Quality Checks Pipeline
# ---------------------------------------------------------------------------

class TestDataQualityChecks:
    @pytest.mark.asyncio
    async def test_run_data_quality_checks_produces_results(self, db_session):
        await _seed_quality_checks(db_session)
        # Seed a sync_run_log so the data quality pipeline can reference it
        run = await dp._open_run(db_session, "dq_test", "data_quality_check", triggered_by="test")
        db_session.expire(run)
        db_session.expunge(run)
        summary = await dp.run_data_quality_checks(triggered_by="test")
        assert summary["total_rules"] == 2  # only active ones
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["errors"] == 0
        assert "error" not in summary

    @pytest.mark.asyncio
    async def test_run_data_quality_respects_inactive(self, db_session):
        await _seed_quality_checks(db_session)
        summary = await dp.run_data_quality_checks(triggered_by="test")
        assert summary["total_rules"] == 2
        assert summary["passed"] + summary["failed"] + summary["errors"] == 2

    @pytest.mark.asyncio
    async def test_run_data_quality_no_rules(self, db_session):
        summary = await dp.run_data_quality_checks(triggered_by="test")
        assert summary["total_rules"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == 0


# ---------------------------------------------------------------------------
# 3. State Credential Sync Pipeline
# ---------------------------------------------------------------------------

class TestStateCredentialSync:
    @pytest.mark.asyncio
    async def test_run_state_credential_sync_without_env_is_noop(self, db_session):
        """When no STATE_API_URL_* env var is set, the sync noop gracefully."""
        os.environ.pop("STATE_API_URL_OH", None)
        summary = await dp.run_state_credential_sync("OH", triggered_by="test")
        assert summary.get("error") is None
        assert summary["records_processed"] == 0

    @pytest.mark.asyncio
    async def test_load_state_credential_record_insert(self, db_session):
        rec = {
            "state_code": "OH",
            "credential_number": "HVAC-12345",
            "credential_type": "HVAC",
            "issuing_state": "OH",
            "holder_name": "Acme Heating",
            "status": "active",
            "expiration_date": date(2026, 12, 31),
        }
        result = await dp._load_state_credential_record(db_session, rec)
        assert result["success"] is True
        assert result["existing"] is False
        assert isinstance(result["id"], UUID)

        # Verify in DB
        row = (
            await db_session.execute(
                sa_select(StateCredentialRecord)
            )
        ).scalar_one()
        assert row.credential_number == "HVAC-12345"
        assert row.status == "active"

    @pytest.mark.asyncio
    async def test_load_state_credential_record_update(self, db_session):
        from uuid import uuid4 as _uuid4

        # Seed existing row
        existing = StateCredentialRecord(
            id=_uuid4(),
            state_code="OH",
            credential_number="ELEC-99999",
            credential_type="Electrical",
            issuing_state="OH",
            holder_name="Old Name",
            status="active",
        )
        db_session.add(existing)
        await db_session.commit()

        rec = {
            "state_code": "OH",
            "credential_number": "ELEC-99999",
            "credential_type": "Electrical",
            "holder_name": "New Name",
            "status": "active",
        }
        result = await dp._load_state_credential_record(db_session, rec)
        assert result["success"] is True
        assert result["existing"] is True

        await db_session.refresh(existing)
        assert existing.holder_name == "New Name"


# ---------------------------------------------------------------------------
# 4. Analytics View Refresh (best-effort in SQLite)
# ---------------------------------------------------------------------------

class TestAnalyticsViews:
    @pytest.mark.asyncio
    async def test_refresh_views_does_not_crash(self, db_session):
        """SQLite does not support MATERIALIZED VIEW, but ensure the call
        does not silently swallow other errors."""
        import sqlalchemy as sa

        # If SQLite, we expect an operational error for materialized views.
        try:
            await dp.refresh_analytics_views(db_session)
        except sa.exc.OperationalError as exc:
            assert "materialized" in str(exc).lower() or "refresh" in str(exc).lower()
            pytest.skip("SQLite does not support MATERIALIZED VIEW. Expected.")
