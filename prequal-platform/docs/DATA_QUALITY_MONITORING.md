# Data Quality Monitoring & Analytics Pipeline

**Owner**: Data Engineer  
**Date**: 2026-06-08  
**Related Ticket**: [MID-72](/MID/issues/MID-72)

## Overview

This document describes the data quality monitoring, alerting, analytics,
retention, and performance monitoring infrastructure added to the Prequal
platform. It builds on top of the existing external compliance data pipeline
(MID-64) to provide production-grade observability.

---

## What Was Built

### 1. Data Quality Monitoring Views & Tables

#### `sync_health_daily`
Daily rollup table for sync job health metrics. Populated by the
`run_daily_data_quality_check()` entry point.

#### `data_quality_alerts`
Threshold-based alert table for data quality degradation events.
Configured types: `sync_failure`, `match_rate_drop`, `error_rate_spike`,
`stale_data`.

#### Materialized Views
| View | Purpose |
|------|---------|
| `mv_sync_health_dashboard` | 30-day sync job health summary (runs, error rates, duration) |
| `mv_match_accuracy` | Match accuracy for violations + state_credential_records |
| `mv_data_quality_summary` | Per-check rollup of data_quality_results |

### 2. Alerting Pipeline

The `data_quality_monitoring.py` service evaluates metrics against thresholds:

| Metric | Threshold | Alert Type | Severity |
|--------|-----------|------------|----------|
| Match rate | < 85% | `match_rate_drop` | `warning` |
| Error rate | > 5% | `error_rate_spike` | `error` |
| Stale OSHA data | > 0 | `stale_data` | `warning` |
| Failed jobs | > 2 in period | `sync_failure` | `error` |

Alerts are persisted to `data_quality_alerts` with `is_acknowledged`
set to `FALSE`. A future UI or notification layer can consume unacknowledged
alerts.

### 3. Analytics Views for Compliance Trends

| View | Purpose |
|------|---------|
| `mv_subcontractor_compliance_trends` | Daily compliance rate, violations, penalties |
| `mv_certification_expiration_trends` | Daily cert buckets (valid, expired, expiring) |

### 4. Data Retention & Archival Policy

- `sync_run_logs` and `data_quality_results` older than **90 days** are
  copied to `archived_sync_run_logs` / `archived_data_quality_results`.
- Original records are **never deleted** from source tables per our data
  retention policy.  Source-table soft-delete support can be added via a
  future schema migration if row count growth becomes a concern.
- Run via `scripts/run_data_quality_archival.py`.
- The archival script is idempotent (uses `NOT EXISTS` to skip already-archived
  records) and safe to rerun.

### 5. Pipeline Performance Monitoring

The `pipeline_performance_logs` table captures per-stage metrics:
- `duration_ms`
- `records_in` / `records_out`
- `cache_hits` / `cache_misses`
- `api_requests` / `api_errors`
- `avg_api_latency_ms` / `max_api_latency_ms`

The `mv_pipeline_performance_summary` view rolls these up by job + stage.

---

## Files Added / Modified

| File | Action |
|------|--------|
| `alembic/versions/014_data_quality_monitoring.py` | New migration (tables + views) |
| `app/services/data_quality_monitoring.py` | New service module |
| `tests/test_data_quality_monitoring.py` | Test suite |
| `scripts/run_data_quality_archival.py` | Archival runner script |
| `docs/DATA_QUALITY_MONITORING.md` | This document |

---

## Integration with Existing Infrastructure

The data quality refresh is designed to run **after** the daily ETL pipeline
completes (02:00–04:00 UTC). The scheduled job in `app/scheduled.py` should be
updated to call `run_daily_data_quality_check()` after the existing
data-quality checker finishes.

Example scheduler addition:
```python
from app.services.data_quality_monitoring import run_daily_data_quality_check

async def _run_data_quality_full():
    # existing data quality checks ...
    # then:
    await run_daily_data_quality_check()
```

---

## Testing

Run the test suite:
```bash
cd prequal-platform
pytest tests/test_data_quality_monitoring.py -v
```

Tests cover:
- Health check structure and metric ranges
- Alert threshold evaluation (positive and negative cases)
- Archival return counts
- Performance log insertion
- View refresh idempotence

---

## Notes

- All threshold values are configurable via `DEFAULT_THRESHOLDS` in
  `data_quality_monitoring.py`.
- Never delete data without archiving first.
- Materialized views require `REFRESH MATERIALIZED VIEW` after significant
  data changes.
