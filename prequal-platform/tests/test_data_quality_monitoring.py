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
    get_field_quality_metrics,
    get_field_quality_trends,
    detect_schema_drift,
    detect_volume_anomalies,
    check_freshness_sla,
    get_source_health,
    collect_data_quality_metrics,
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


# ---------------------------------------------------------------------------
# 6. Field-Level Quality Metrics (MID-605)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_field_quality_metrics_structure(db: AsyncSession):
    result = await get_field_quality_metrics(db, persist=False)
    assert "captured_at" in result
    assert "fields" in result
    assert "spikes" in result
    spec_labels = {(s["table_name"], s["column_name"]) for s in result["fields"]}
    # All configured critical fields are reported
    assert ("subcontractors", "ein") in spec_labels
    assert ("certifications", "certification_number") in spec_labels
    assert ("certifications", "expiration_date") in spec_labels
    assert ("state_credential_records", "credential_number") in spec_labels
    for f in result["fields"]:
        assert 0.0 <= f["null_rate"] <= 1.0
        assert 0.0 <= f["duplicate_rate"] <= 1.0


@pytest.mark.asyncio
async def test_get_field_quality_metrics_detects_nulls_and_persists(db: AsyncSession):
    # Seed a subcontractor with and without EIN
    await db.execute(
        text(
            """
            INSERT INTO subcontractors (id, company_name, email, country, ein, status, created_at, updated_at)
            VALUES (:id1, 'Null EIN Sub', 'nullein@example.com', 'USA', NULL, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"id1": str(uuid4())},
    )
    await db.commit()

    result = await get_field_quality_metrics(db, persist=True)
    ein_field = next(
        f for f in result["fields"]
        if f["table_name"] == "subcontractors" and f["column_name"] == "ein"
    )
    assert ein_field["null_count"] >= 1
    assert ein_field["null_rate"] > 0

    # Snapshot row was persisted for trend history
    count = (
        await db.execute(
            text("SELECT COUNT(*) FROM data_quality_field_metrics WHERE table_name='subcontractors' AND column_name='ein'")
        )
    ).scalar()
    assert count >= 1


@pytest.mark.asyncio
async def test_get_field_quality_trends(db: AsyncSession):
    await get_field_quality_metrics(db, persist=True)
    trends = await get_field_quality_trends(db, days=30)
    assert trends["period_days"] == 30
    assert isinstance(trends["series"], list)
    assert len(trends["series"]) >= 1
    assert "points" in trends["series"][0]


# ---------------------------------------------------------------------------
# 7. Schema Drift Detection (MID-605)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_schema_drift_baseline_then_stable(db: AsyncSession):
    # First call creates/updates snapshots (may be a baseline or a no-drift
    # comparison against an earlier snapshot from this test session)
    first = await detect_schema_drift(db, persist=True)
    assert len(first["tables"]) >= 1
    assert any(t["table_name"] == "subcontractors" for t in first["tables"])

    # Second run compares against the baseline; schema unchanged -> no drift
    second = await detect_schema_drift(db, persist=True)
    assert second["drift_detected"] is False
    assert all(
        t["added_columns"] == [] and t["removed_columns"] == [] for t in second["tables"]
    )


@pytest.mark.asyncio
async def test_schema_snapshots_persisted(db: AsyncSession):
    await detect_schema_drift(db, persist=True)
    count = (
        await db.execute(
            text("SELECT COUNT(*) FROM data_quality_schema_snapshots WHERE table_name='certifications'")
        )
    ).scalar()
    assert count >= 1


# ---------------------------------------------------------------------------
# 8. Volume Anomaly Detection & Freshness SLA (MID-605)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_volume_anomalies_flags_row_count_drop(db: AsyncSession):
    job = "anomaly_test_job"
    # Three historical runs around 1000 records, then a sudden drop to 100
    for i, records in enumerate([1000, 1050, 980]):
        await db.execute(
            text(
                """
                INSERT INTO sync_run_logs
                (id, job_name, job_type, status, triggered_by, started_at, completed_at,
                 records_processed, records_inserted, records_updated, records_failed,
                 created_at, updated_at)
                VALUES (:id, :job, 'test', 'completed', 'test',
                        :ts, :ts, :recs, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(uuid4()),
                "job": job,
                "ts": datetime.utcnow() - timedelta(hours=48 - i * 24),
                "recs": records,
            },
        )
    await db.execute(
        text(
            """
            INSERT INTO sync_run_logs
            (id, job_name, job_type, status, triggered_by, started_at, completed_at,
             records_processed, records_inserted, records_updated, records_failed,
             created_at, updated_at)
            VALUES (:id, :job, 'test', 'completed', 'test',
                    :ts, :ts, :recs, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {
            "id": str(uuid4()),
            "job": job,
            "ts": datetime.utcnow(),
            "recs": 100,  # >50% drop vs ~1010 baseline
        },
    )
    await db.commit()

    result = await detect_volume_anomalies(db)
    anomaly = next((a for a in result["anomalies"] if a["job_name"] == job), None)
    assert anomaly is not None
    assert anomaly["latest_records"] == 100
    assert anomaly["drop_pct"] > 0.50


@pytest.mark.asyncio
async def test_detect_volume_anomalies_stable_job_no_alerts(db: AsyncSession):
    job = "stable_test_job"
    for i, records in enumerate([500, 510, 495, 505]):
        await db.execute(
            text(
                """
                INSERT INTO sync_run_logs
                (id, job_name, job_type, status, triggered_by, started_at, completed_at,
                 records_processed, records_inserted, records_updated, records_failed,
                 created_at, updated_at)
                VALUES (:id, :job, 'test', 'completed', 'test',
                        :ts, :ts, :recs, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(uuid4()),
                "job": job,
                "ts": datetime.utcnow() - timedelta(hours=72 - i * 24),
                "recs": records,
            },
        )
    await db.commit()

    result = await detect_volume_anomalies(db)
    assert all(a["job_name"] != job for a in result["anomalies"])


@pytest.mark.asyncio
async def test_check_freshness_sla_breach(db: AsyncSession):
    job = "stale_test_job"
    # Last successful run 48h ago -> breaches the 24h SLA
    await db.execute(
        text(
            """
            INSERT INTO sync_run_logs
            (id, job_name, job_type, status, triggered_by, started_at, completed_at,
             records_processed, records_inserted, records_updated, records_failed,
             created_at, updated_at)
            VALUES (:id, :job, 'test', 'completed', 'test',
                    :ts, :ts, 10, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"id": str(uuid4()), "job": job, "ts": datetime.utcnow() - timedelta(hours=48)},
    )
    await db.commit()

    result = await check_freshness_sla(db, sla_hours=24)
    source = next((s for s in result["sources"] if s["job_name"] == job), None)
    assert source is not None
    assert source["breached"] is True
    assert source["age_hours"] >= 48


@pytest.mark.asyncio
async def test_get_source_health_structure(db: AsyncSession):
    result = await get_source_health(db, days=7)
    assert result["overall"] in ("healthy", "degraded", "down")
    for source in result["sources"]:
        assert source["status"] in ("healthy", "degraded", "down")
        assert "source" in source
        assert "error_rate" in source


@pytest.mark.asyncio
async def test_collect_data_quality_metrics_readonly_snapshot(db: AsyncSession):
    snapshot = await collect_data_quality_metrics(db, days=7)
    for key in (
        "generated_at",
        "sync_health",
        "match_accuracy",
        "error_rates",
        "stale_data",
        "field_quality",
        "schema_drift",
        "volume_anomalies",
        "freshness",
        "source_health",
    ):
        assert key in snapshot, f"missing key: {key}"


# ---------------------------------------------------------------------------
# 9. Extended Threshold Evaluation (MID-605)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_high_null_rate(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
        "field_quality": {
            "fields": [
                {
                    "table_name": "subcontractors",
                    "column_name": "ein",
                    "total_rows": 100,
                    "null_count": 25,
                    "null_rate": 0.25,
                    "duplicate_count": 0,
                    "duplicate_rate": 0.0,
                }
            ],
            "spikes": [],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    null_alerts = [a for a in alerts if a["alert_type"] == "high_null_rate"]
    assert len(null_alerts) == 1
    assert null_alerts[0]["source_table"] == "subcontractors"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_null_rate_spike(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
        "field_quality": {
            "fields": [],
            "spikes": [
                {
                    "table_name": "certifications",
                    "column_name": "certification_number",
                    "previous_null_rate": 0.02,
                    "current_null_rate": 0.30,
                }
            ],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    spike_alerts = [a for a in alerts if a["alert_type"] == "null_rate_spike"]
    assert len(spike_alerts) == 1
    assert spike_alerts[0]["severity"] == "error"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_row_count_drop(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
        "volume_anomalies": {
            "anomalies": [
                {
                    "job_name": "osha_daily_sync",
                    "latest_records": 100,
                    "baseline_avg_records": 1000,
                    "drop_pct": 0.90,
                }
            ]
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    drop_alerts = [a for a in alerts if a["alert_type"] == "row_count_drop"]
    assert len(drop_alerts) == 1
    assert drop_alerts[0]["source_job"] == "osha_daily_sync"


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_freshness_sla_breach(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
        "freshness": {
            "sla_hours": 24,
            "sources": [
                {
                    "job_name": "osha_daily_sync",
                    "last_successful_sync": None,
                    "age_hours": 30.0,
                    "breached": True,
                }
            ],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    sla_alerts = [a for a in alerts if a["alert_type"] == "freshness_sla_breach"]
    assert len(sla_alerts) == 1


@pytest.mark.asyncio
async def test_evaluate_thresholds_triggers_schema_change(db: AsyncSession):
    metrics = {
        "match_accuracy": {"sources": []},
        "error_rates": {"jobs": []},
        "stale_data": {"total_stale_osha": 0, "total_stale_state": 0},
        "sync_health": {"period_days": 7, "jobs": []},
        "schema_drift": {
            "drift_detected": True,
            "tables": [
                {
                    "table_name": "violations",
                    "column_count": 30,
                    "added_columns": ["new_col"],
                    "removed_columns": [],
                    "baseline": False,
                }
            ],
        },
    }
    alerts = await evaluate_thresholds(db, metrics)
    schema_alerts = [a for a in alerts if a["alert_type"] == "schema_change"]
    assert len(schema_alerts) == 1
    assert schema_alerts[0]["source_table"] == "violations"


@pytest.mark.asyncio
async def test_run_data_quality_health_check_includes_mid605_metrics(db: AsyncSession):
    result = await run_data_quality_health_check(db)
    for key in (
        "field_quality",
        "schema_drift",
        "volume_anomalies",
        "freshness",
    ):
        assert key in result["metrics"], f"missing metric: {key}"
