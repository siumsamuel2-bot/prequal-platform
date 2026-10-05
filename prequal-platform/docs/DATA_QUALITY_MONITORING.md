# Data Quality Monitoring & Alerting (MID-605)

Owner: Data Engineer

Comprehensive data quality monitoring for the subcontractor compliance data
pipeline (OSHA violations, state credential databases, subcontractor records).
Built on top of MID-434 (audit logging) and MID-269 (retry-with-backoff).

## Components

All logic lives in `app/services/data_quality_monitoring.py` and runs:

- **Scheduled**: daily via `app/scheduled.py` job `daily_data_quality_checks`
  (after `validate_pipeline_health`)
- **Manual**: `POST /api/pipeline/data-quality/run` (manager/admin)
- **Batch**: `python scripts/run_daily_sync.py` includes the data quality step

### Collected metrics (every run)

| Metric key (API/result) | Function | Description |
|---|---|---|
| `sync_health` | `get_sync_health(db, days)` | Runs, successes, failures, record counts, avg duration, last run per job (window: days) |
| `match_accuracy` | `get_match_accuracy(db)` | Matched/unmatched rates for OSHA violations and state credential records |
| `error_rates` | `get_error_rates(db, days)` | records_failed / records_processed per job |
| `stale_data` | `check_stale_data(db)` | Stale OSHA sources (>24h) and state credentials not synced in 7d |
| `field_quality` | `get_field_quality_metrics(db, persist=True)` | Null/duplicate rates for critical fields; snapshot persisted to `data_quality_field_metrics`; null-rate spikes vs previous snapshot |
| `schema_drift` | `detect_schema_drift(db, persist=True)` | Added/removed columns vs previous snapshot per monitored table |
| `volume_anomalies` | `detect_volume_anomalies(db)` | Latest completed run records vs avg of up to 10 previous completed runs; flags drops > `row_count_drop_pct` (50%) |
| `freshness` | `check_freshness_sla(db)` | Time since last successful sync per job vs `stale_hours_max` SLA (24h) |
| `source_health` | `get_source_health(db, days)` | Per-source rollup: `healthy` / `degraded` / `down` |

Critical fields monitored for null/duplicate rates (`FIELD_QUALITY_SPECS`):
`subcontractors.ein` (counts empty `encrypted_ein` as null),
`subcontractors.license_number`, `certifications.certification_number`
(+ duplicates), `certifications.expiration_date`,
`state_credential_records.credential_number` (+ duplicates),
`state_credential_records.expiration_date`, `violations.citation_number`.

Tables monitored for schema drift (`SCHEMA_DRIFT_TABLES`): `subcontractors`,
`certifications`, `violations`, `state_credential_records`, `sync_run_logs`,
`osha_data_freshness`.

### Alert rules (persisted to `data_quality_alerts`)

| alert_type | Condition | Severity |
|---|---|---|
| `match_rate_drop` | match_rate < 85% | warning |
| `error_rate_spike` | error_rate > 5% | error |
| `stale_data` | any stale OSHA source | warning |
| `sync_failure` | failed runs > 2 in 7d window | error |
| `high_null_rate` | field null_rate > 10% | warning (>20%: error) |
| `high_duplicate_rate` | duplicate_rate > 1% | warning |
| `null_rate_spike` | null_rate jump >= 10pp vs previous snapshot | error |
| `row_count_drop` | latest run records drop > 50% vs recent avg | error |
| `freshness_sla_breach` | last successful sync older than 24h | warning (>48h or never: error) |
| `schema_change` | columns added/removed vs previous snapshot | warning |

Alerts are written to `data_quality_alerts` (migration 014). Every alert also
emits a data-access audit event (MID-434, `operation_type=DATA_QUALITY_ALERT`,
`compliance_tag=data_quality`) so quality events join the audit trail.

### Source health status

`get_source_health()` rolls freshness + error rate + failures into
`healthy` / `degraded` / `down`:

- **down**: no successful run ever, or last success older than 2× SLA
- **degraded**: SLA breached, error rate above threshold, or any failed run
- **healthy**: otherwise

## New tables (migration 027)

- `data_quality_field_metrics` — per-run snapshots of field null/duplicate
  rates; enables 7d/30d trend series and spike detection
- `data_quality_schema_snapshots` — per-table column snapshots (JSON) used
  for drift detection

Both follow the non-destructive retention policy: rows are archived/flagged,
never deleted. SQLite test equivalents are created in `tests/conftest.py`.

## API endpoints (`/api/pipeline`)

| Endpoint | Auth | Description |
|---|---|---|
| `POST /data-quality/run` | manager/admin | Run full monitoring suite, persist alerts |
| `GET /data-quality/results` | user | Rule-based check results (existing) |
| `GET /data-quality/metrics?days=7` | user | Read-only full metrics snapshot (dashboard-ready JSON for Grafana/MID-142) |
| `GET /data-quality/health?days=7` | user | Per-source health rollup (`overall` + `sources[]`) |
| `GET /data-quality/alerts?acknowledged=false&severity=error&days=30` | user | Alert history |
| `POST /data-quality/alerts/{id}/acknowledge` | manager/admin | Acknowledge an alert |
| `GET /data-quality/trends?days=30` | user | Daily sync run aggregates + field-quality time series |

`GET` endpoints are read-only: they never persist snapshots or trigger alerts
(`persist=False`, no threshold evaluation).

## Dashboard data structure

`GET /data-quality/metrics` returns:

```json
{
  "generated_at": "2026-10-03T02:30:00",
  "sync_health": {"period_days": 7, "jobs": [...]},
  "match_accuracy": {"sources": [...]},
  "error_rates": {"period_days": 7, "jobs": [...]},
  "stale_data": {"stale_osha_sources": [...], "stale_state_credentials": [...]},
  "field_quality": {"captured_at": "...", "fields": [...], "spikes": [...]},
  "schema_drift": {"drift_detected": false, "tables": [...]},
  "volume_anomalies": {"anomalies": [...], "jobs": [...]},
  "freshness": {"sla_hours": 24, "sources": [...], "total_breached": 0},
  "source_health": {"overall": "healthy", "sources": [...]}
}
```

Grafana (MID-142) can poll the JSON endpoints directly (JSON API / Infinity
datasource) or DevOps can scrape from centralized logs — every alert is also
emitted to the audit log stream.

## Tests

`tests/test_data_quality_monitoring.py` (30 tests): health checks, threshold
evaluation for every alert type, retention/archival, performance logging,
field metrics + snapshots, schema drift baseline/stability, volume anomalies
(>50% drop detection, stable-job no-alert), freshness SLA breach, source
health rollup, and read-only snapshot shape.

Run: `venv\Scripts\python.exe -m pytest tests/test_data_quality_monitoring.py`
