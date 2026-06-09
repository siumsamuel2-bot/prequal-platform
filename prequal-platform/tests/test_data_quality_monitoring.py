"""Tests for the data quality monitoring service.

Covers health checks, alerting thresholds, archival logic, and performance logging.
Owner: Data Engineer
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.data_quality_monitoring import (
    run_data_quality_health_check,
    get_sync_health,
    get_match_accuracy,
    get_error_rates,
    check_stale_data,
    evaluate_thresholds,
    archive_old_sync_logs,
    archive_old_data_quality_results,
    log_pipeline_performance,
    refresh_data_quality_views,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(db_engine):
    """Yield a database session with data-quality tables present."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# 1. Health Checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_sync_health_returns_structure(db: AsyncSession):
    result = await get_sync_health(db, days=7)
    assert "period_days" in result
    assert "jobs" in result
    assert isinstance(result["jobs"], list)


@pytest.mark.asyncio
async def test_get_match_accuracy_returns_sources(db: AsyncSession):
    result = await get_match_accuracy(db)
    assert "sources" in result
    for source in result["sources"]:
        assert "source_table" in source
        assert "total_count" in source
        assert "matched_count" in source
        assert "unmatched_count" in source
        assert "match_rate" in source
        assert 0.0 <= source["match_rate"] <= 1.0


@pytest.mark.asyncio
async def test_get_error_rates_returns_structure(db: AsyncSession):
    result = await get_error_rates(db, days=7)
    assert "period_days" in result
    assert "jobs" in result
    for job in result["jobs"]:
        assert "job_name" in job
        assert "error_rate" in job
        assert 0.0 <= job["error_rate"] <= 1.0


@pytest.mark.asyncio
async def test_check_stale_data_returns_structure(db: AsyncSession):
    result = await check_stale_data(db)
    assert "stale_osha_sources" in result
    assert "stale_state_credentials" in result
    assert "total_stale_osha" in result
    assert "total_stale_state" in result
    assert isinstance(result["total_stale_osha"], int)
    assert isinstance(result["total_stale_state"], int)


@pytest.mark.asyncio
async def test_run_data_quality_health_check(db: AsyncSession):
    result = await run_data_quality_health_check(db)
    assert "checked_at" in result
    assert "metrics" in result
    assert "alerts_triggered" in result
    assert "sync_health" in result["metrics"]
    assert "match_accuracy" in result["metrics"]
    assert "error_rates" in result["metrics"]
    assert "stale_data" in result["metrics"]


# ---------------------------------------------------------------------------
# 2. Alerting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_thresholds_with_good_metrics(db: AsyncSession):
    metrics = {
        "match_accuracy": {
            "sources": [
                {"source_table": "violations", "match_rate": 0.95},
                {"source_table": "state_credential_records", "match_rate": 0.92},
            ]
        },
        "error_rates": {
            "jobs": [
                {"job_name": "osha_daily_sync", "error_rate": 0.01},
            ]
        },
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {
            "period_days": 7,
            "jobs": [
                {"job_name": "osha_daily_sync", "failed_runs": 0},
            ],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_match_rate_alert(db: AsyncSession):
    metrics = {
        "match_accuracy": {
            "sources": [
                {"source_table": "violations", "match_rate": 0.70},
            ]
        },
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
    }
    alerts = await evaluate_thresholds(db, metrics)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "match_rate_drop"
    assert alerts[0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_error_rate_alert(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {
            "jobs": [
                {"job_name": "osha_daily_sync", "error_rate": 0.10},
            ]
        },
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
    }
    alerts = await evaluate_thresholds(db, metrics)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "error_rate_spike"
    assert alerts[0]["severity"] == "error"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_stale_data_alert(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 2, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
    }
    alerts = await evaluate_thresholds(db, metrics)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "stale_data"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_sync_failure_alert(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {
            "period_days": 7,
            "jobs": [
                {"job_name": "osha_daily_sync", "failed_runs": 5},
            ],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "sync_failure"


# ---------------------------------------------------------------------------
# 3. Data Retention / Archival
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_old_sync_logs_returns_counts(db: AsyncSession):
    result = await archive_old_sync_logs(db, retention_days=90)
    assert "archived" in result
    assert "deleted" not in result  # non-destructive archival per retention policy
    assert isinstance(result["archived"], int)


@pytest.mark.asyncio
async def test_archive_old_data_quality_results_returns_counts(db: AsyncSession):
    result = await archive_old_data_quality_results(db, retention_days=90)
    assert "archived" in result
    assert "deleted" not in result  # non-destructive archival per retention policy
    assert isinstance(result["archived"], int)


# ---------------------------------------------------------------------------
# 4. Performance Monitoring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_pipeline_performance(db: AsyncSession):
    await log_pipeline_performance(
        db,
        run_id=str(uuid4()),
        job_name="test_job",
        job_type="test",
        stage_name="extract",
        stage_order=1,
        started_at=datetime.now(),
        completed_at=datetime.now() + timedelta(seconds=2),
        records_in=100,
        records_out=95,
        cache_hits=10,
        cache_misses=2,
        api_requests=5,
        api_errors=0,
        avg_api_latency_ms=120,
        max_api_latency_ms=250,
    )
    # Verify by querying the table directly
    result = await db.execute(
        text("SELECT COUNT(*) FROM pipeline_performance_logs WHERE job_name = 'test_job'")
    )
    count = result.scalar()
    assert count >= 1


# ---------------------------------------------------------------------------
# 5. View Refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_data_quality_views(db: AsyncSession):
    # Should not raise; we can't easily verify contents without running the migration
    await refresh_data_quality_views(db)
