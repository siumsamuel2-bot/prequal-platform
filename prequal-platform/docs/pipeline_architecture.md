# External Compliance Data Pipeline Architecture

**Owner:** Data Engineer  
**Last Updated:** 2026-06-05  
**Scope:** OSHA Violation Database + State Credential Database integration for Prequal

---

## Overview

The external compliance data pipeline fetches violation and credential data from public APIs, matches records to internal subcontractor profiles, and stores them with full audit trails and data quality monitoring.

---

## Components

### 1. Data Sources

| Source | API | Rate Limit | Auth |
|--------|-----|------------|------|
| OSHA Whistleblower | `https://www.whistleblower.gov/api/cases` | 1 req/sec | Optional API key |
| State Credential Boards | Configured per state (`STATE_API_URL_{CODE}`) | Varies | `STATE_API_KEY_{CODE}` |

### 2. Clients

| File | Purpose |
|------|---------|
| `app/services/osha_client.py` | Async OSHA API client with rate limiting |
| `app/services/state_credential_client.py` | Generic async state credential client |

### 3. Pipeline

| File | Purpose |
|------|---------|
| `app/services/external_compliance_pipeline.py` | Core ETL: extract, transform, match, upsert, log |
| `scripts/run_daily_sync.py` | Daily scheduled runner with error notifications |
| `app/scheduled.py` | APScheduler job definitions |

### 4. Data Quality & Matching

| File | Purpose |
|------|---------|
| `app/services/compliance_matching.py` | Fuzzy matching, duplicate detection, match validation |

### 5. Schemas

| File | Purpose |
|------|---------|
| `app/models/compliance.py` | SQLAlchemy ORM models |
| `alembic/versions/001_initial_schema.py` | Core tables + OSHA columns |
| `alembic/versions/004_data_pipeline_sync.py` | Sync logs, data quality, state credentials, analytics views |
| `alembic/versions/011_state_credential_match_and_pipeline_audit.py` | Matching FKs, dedup columns, error notifications |

---

## Data Flow

```
┌──────────────────────┐
│   OSHA API           │
│   (whistleblower.gov)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│  OSHAClient          │────▶│  StateCredentialClient│
│  (rate-limited)      │     │  (per-state config)   │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           ▼                            ▼
┌──────────────────────────────────────────────────┐
│  external_compliance_pipeline.py                 │
│  ├─ Extract cases/credentials                    │
│  ├─ Deduplicate (compliance_matching.py)         │
│  ├─ Match to subcontractors (EIN → License → Name)│
│  ├─ Upsert to violations / state_credential_records│
│  └─ Log to sync_run_logs, osha_api_logs           │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  Data Quality Validation                         │
│  ├─ validate_pipeline_health()                   │
│  ├─ validate_matching_accuracy()                 │
│  └─ validate_deduplication()                     │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  Analytics Refresh                                 │
│  ├─ mv_compliance_summary                          │
│  ├─ mv_violation_trends                           │
│  ├─ mv_certification_status                       │
│  └─ mv_project_compliance                         │
└──────────────────────────────────────────────────┘
```

---

## Matching Strategy

### Priority (highest first)

1. **EIN Exact Match** — `subcontractors.ein = external.ein`
2. **License Exact Match** — `subcontractors.license_number + license_state`
3. **Name Fuzzy Match** — Normalized name comparison

### Confidence Scores

| Method | Score | Notes |
|--------|-------|-------|
| EIN | 1.00 | Exact match, highest confidence |
| License | 0.95 | Exact match within state |
| Name | 0.80 | After suffix normalization (LLC, Inc, etc.) |

---

## Deduplication Strategy

Duplicate detection runs before upsert:

- **OSHA violations:** Same `osha_violation_id` or same `(ein, issued_date)`
- **State credentials:** Same `(state_code, credential_number, credential_type)`
- **Fuzzy name + date** for edge cases where IDs differ

Duplicates are flagged with `is_duplicate = TRUE` and `duplicate_info` JSON.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| API rate limit exceeded | Backoff + retry with semaphore |
| API returns 4xx/5xx | Log to `osha_api_logs`, increment `records_failed` |
| Data format change | Graceful parse failure, log specific field error |
| Match failure | Record stored with `subcontractor_id = NULL`; flagged for review |
| Sync failure | `sync_run_logs.status = 'failed'` + `pipeline_error_notifications` entry |

---

## Scheduled Jobs

| Job | Cron | File |
|-----|------|------|
| OSHA daily sync | `0 2 * * *` | `app/scheduled.py` |
| State credential sync | `0 3 * * *` | `app/scheduled.py` |
| Data quality checks | `0 4 * * *` | `app/scheduled.py` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres@localhost:5432/compliance` | PostgreSQL connection |
| `OSHA_API_URL` | `https://www.whistleblower.gov/api/cases` | OSHA API base URL |
| `OSHA_API_KEY` | `""` | Optional OSHA API key |
| `OSHA_RATE_LIMIT` | `1.0` | Requests per second |
| `OSHA_MAX_PAGES` | `10` | Max pagination pages |
| `STATE_API_URL_{CODE}` | — | State credential API URL |
| `STATE_API_KEY_{CODE}` | — | State credential API key |
| `STATE_MAX_PAGES` | `5` | Max pagination per state |
| `STATE_SYNC_STATES` | `CA,TX` | Comma-separated state codes (FL opt-in) |
| `NOTIFY_EMAIL` | — | Failure alert email |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Testing

Run all pipeline tests:

```bash
cd prequal-platform
pytest tests/test_external_compliance_pipeline.py -v
pytest tests/test_osha_pipeline.py -v
pytest tests/test_compliance_matching.py -v
pytest tests/test_state_credential_client.py -v
```

---

## Monitoring

Key health checks (from `validate_pipeline_health()`):

- `unmatched_osha_violations` — Should trend toward 0
- `unmatched_state_credentials` — Should trend toward 0
- `stale_running_jobs` — Should always be 0
- `failed_jobs_last_7d` — Should be 0

---

## Future Work

- Add retry queue for failed API requests
- Implement webhook-based real-time updates
- Add manual match review UI

---

## MID-613 Optimization Changelog (2026-10-03)

Changes delivered in `app/services/external_compliance_pipeline.py`:

1. **OSHA pre-load validation gate (`validate_osha_case_record`)** — previously only
   state credentials had a validation gate; OSHA records flowed unvalidated into
   `violations`. Invalid records (missing/oversized `osha_violation_id`, no company
   name or EIN identity signal, unparseable dates, negative/non-numeric penalty or
   gravity) are now rejected, counted in `records_failed`, and never written.
2. **In-batch OSHA deduplication** — paginated OSHA results can repeat the same case
   across pages. The sync now dedupes by `osha_violation_id` before any DB
   round-trip (last occurrence wins), eliminating redundant SELECT+upsert calls and
   reporting the dropped count in run logs.
3. **`MATCH_THRESHOLD` enforcement** — the threshold constant was defined (0.75) but
   never applied. Matches below the threshold (e.g. weak name-only matches) are now
   discarded with an explanatory log line instead of being persisted to
   `subcontractor_id`, for both OSHA and state credential paths.
4. **`get_pipeline_health_summary` SQL fix** — `INTERVAL ':days days'` was a quoted
   literal so the parameter never bound and the query always failed on PostgreSQL.
   Now uses `make_interval(days => :days)`.
5. **`check_batch_health` dialect fix + latency alerting** — rewrote the SQLite-only
   `julianday()`/`datetime('now')` query as a portable row fetch with duration and
   throughput computed in Python. `BATCH_LATENCY_MAX_MS` (previously dead config)
   now raises `batch_latency_high` (severity=error) alerts alongside the existing
   `batch_throughput_low` (severity=warning) alerts.

### Maintenance procedures

- **Daily:** Data quality check (`run_daily_data_quality_check`) refreshes materialized
  views and archives sync logs > 90 days (archive-only, never deletes source rows).
- **Weekly:** Review `data_quality_alerts` for unacknowledged `error` severity alerts;
  check `batch_latency_high` signals against `BATCH_LATENCY_MAX_MS` tuning.
- **On alert `match_rate_drop`:** investigate unmatched records
  (`violations.subcontractor_id IS NULL` / `state_credential_records.subcontractor_id IS NULL`)
  before raising `MATCH_THRESHOLD`; the default 0.75 admits name-normalized matches.
- **On schema changes:** `detect_schema_drift` snapshots key tables per run; baseline
  drift on migration deploys is expected and alerts once per table.
