# Data Quality Monitoring & Analytics Pipeline (MID-72)

## Overview
This document describes the data quality monitoring and analytics pipeline implemented for the Prequal subcontractor compliance platform. The pipeline tracks sync health, data quality metrics, match rates, alerts, and pipeline performance.

## Schema Files

| File | Purpose |
|------|---------|
| `01_core_tables.sql` | Base tables (subcontractors, projects, certifications, etc.) |
| `02_expiration_tracking.sql` | Certification expiration and renewal tracking |
| `03_osha_integration.sql` | OSHA data sync and inspection records |
| `04_state_credentials.sql` | State-level credential verification |
| `05_data_quality_monitoring.sql` | Data quality, alerts, performance, and analytics |

## Tables in `05_data_quality_monitoring.sql`

### 1. `sync_health`
Tracks the health of external data source syncs.

| Column | Type | Description |
|--------|------|-------------|
| `source_name` | VARCHAR(100) | e.g. 'osha_api', 'tx_credentials' |
| `source_type` | VARCHAR(50) | 'api', 'ftp', 'sftp' |
| `health_status` | VARCHAR(50) | healthy, degraded, failed, unknown |
| `consecutive_failures` | INTEGER | Rolling counter of consecutive failed syncs |
| `last_successful_sync_at` | TIMESTAMPTZ | Timestamp of last successful sync |
| `expected_next_sync_at` | TIMESTAMPTZ | Scheduled next sync time |

**Indexes:** `idx_sync_health_source` (unique), `idx_sync_health_status`, `idx_sync_health_last_successful`

### 2. `data_quality_checks`
Defines quality rules that can be evaluated against the database.

| Column | Type | Description |
|--------|------|-------------|
| `check_name` | VARCHAR(255) | Human-readable check name |
| `check_type` | VARCHAR(100) | uniqueness, completeness, freshness, format, referential |
| `table_name` | VARCHAR(100) | Target table for the check |
| `check_query` | TEXT | SQL that returns a result to evaluate |
| `expected_result` | VARCHAR(50) | Expected result for a pass |
| `alert_threshold` | DECIMAL(5,4) | Threshold for triggering alerts |
| `priority` | VARCHAR(20) | critical, high, medium, low |

**Indexes:** `idx_dq_checks_table`, `idx_dq_checks_type`, `idx_dq_checks_active`

### 3. `data_quality_results`
Stores the output of each quality check run.

| Column | Type | Description |
|--------|------|-------------|
| `check_id` | UUID | FK to `data_quality_checks` |
| `status` | VARCHAR(50) | pass, fail, warning, error |
| `actual_result` | TEXT | The actual result from the check |
| `record_count` | INTEGER | Total records evaluated |
| `failed_record_count` | INTEGER | Number of failing records |
| `details` | JSONB | Additional detail about failures |

**Indexes:** `idx_dq_results_check_id`, `idx_dq_results_run_at`, `idx_dq_results_status`

### 4. `match_rate_tracking`
Tracks how well external data matches internal records.

| Column | Type | Description |
|--------|------|-------------|
| `source_name` | VARCHAR(100) | External source name |
| `match_date` | DATE | Date of the match run |
| `source_records_total` | INTEGER | Total records from source |
| `matched_records` | INTEGER | Records successfully matched |
| `unmatched_records` | INTEGER | Records that could not be matched |
| `fuzzy_matched_records` | INTEGER | Records matched via fuzzy logic |
| `match_rate_percent` | DECIMAL(5,2) | Auto-computed: matched / total * 100 |
| `fuzzy_match_percent` | DECIMAL(5,2) | Auto-computed: fuzzy / unmatched * 100 |

**Trigger:** `match_rate_auto_compute` calculates `match_rate_percent` and `fuzzy_match_percent`
**Unique Index:** `idx_match_rate_source_date` (source_name, match_date)

### 5. `data_quality_alert_rules`
Defines alerting thresholds for data quality degradation.

| Column | Type | Description |
|--------|------|-------------|
| `rule_name` | VARCHAR(255) | Human-readable rule name |
| `rule_type` | VARCHAR(100) | sync_fail, match_rate_drop, quality_fail, stale_data, performance |
| `condition_operator` | VARCHAR(20) | <, >, <=, >=, =, !=, contains |
| `condition_value` | TEXT | Value to compare against |
| `severity` | VARCHAR(20) | info, warning, critical, emergency |
| `notification_channels` | TEXT[] | email, sms, slack, in_app |
| `cooldown_minutes` | INTEGER | Minimum time between repeat alerts |

**Indexes:** `idx_alert_rules_type`, `idx_alert_rules_active`, `idx_alert_rules_source`

### 6. `data_quality_alert_log`
Persistent record of triggered alerts.

| Column | Type | Description |
|--------|------|-------------|
| `rule_id` | UUID | FK to alert rule |
| `alert_status` | VARCHAR(50) | pending, acknowledged, resolved, escalated, dismissed |
| `triggered_at` | TIMESTAMPTZ | When the alert fired |
| `acknowledged_at` | TIMESTAMPTZ | When someone acknowledged it |
| `severity` | VARCHAR(20) | Derived from rule at trigger time |
| `context` | JSONB | Snapshot of conditions when triggered |

**Indexes:** `idx_alert_log_rule_id`, `idx_alert_log_status`, `idx_alert_log_triggered_at`, `idx_alert_log_severity`

### 7. `pipeline_performance`
Captures per-pipeline execution metrics.

| Column | Type | Description |
|--------|------|-------------|
| `pipeline_name` | VARCHAR(255) | e.g. 'osha_daily_sync' |
| `run_start_at` / `run_end_at` | TIMESTAMPTZ | Execution window |
| `duration_ms` | INTEGER | Auto-computed from timestamps |
| `records_processed` / `inserted` / `updated` / `failed` | INTEGER | Row counts |
| `cache_hits` / `cache_misses` | INTEGER | Cache statistics |
| `cache_hit_rate_percent` | DECIMAL(5,2) | Auto-computed |
| `api_calls_made` / `total_api_latency_ms` | INTEGER | API metrics |
| `avg_api_latency_ms` | DECIMAL(10,2) | Auto-computed |
| `status` | VARCHAR(50) | running, completed, partial, failed |

**Trigger:** `pipeline_perf_auto_compute` calculates duration, cache hit rate, and avg API latency
**Indexes:** `idx_perf_pipeline`, `idx_perf_run_start`, `idx_perf_status`

### 8. `api_latency_tracking`
Per-endpoint API latency monitoring.

| Column | Type | Description |
|--------|------|-------------|
| `endpoint` | VARCHAR(500) | Full URL |
| `method` | VARCHAR(10) | HTTP method |
| `latency_ms` | INTEGER | Response time in ms |
| `status_code` | INTEGER | HTTP status code |
| `is_cache_hit` | BOOLEAN | Whether result came from cache |
| `pipeline_name` | VARCHAR(255) | Associated pipeline |

**Indexes:** `idx_api_latency_endpoint`, `idx_api_latency_request_at`, `idx_api_latency_pipeline`

### 9. `data_retention_policies`
Configures automatic archival of stale data.

| Column | Type | Description |
|--------|------|-------------|
| `policy_name` | VARCHAR(255) | Human-readable name |
| `table_name` | VARCHAR(100) | Target table |
| `retention_days` | INTEGER | How long to keep data active |
| `archival_after_days` | INTEGER | When to move to archive |
| `action` | VARCHAR(50) | archive, flag, partition |
| `is_active` | BOOLEAN | Whether policy is enabled |
| `records_archived` | INTEGER | Running counter of archived rows |

**Indexes:** `idx_retention_table`, `idx_retention_active`

### 10. `archived_records`
Stores snapshots of archived data.

| Column | Type | Description |
|--------|------|-------------|
| `source_table` | VARCHAR(100) | Original table name |
| `source_record_id` | UUID | Original record ID |
| `archived_at` | TIMESTAMPTZ | When archived |
| `archive_reason` | VARCHAR(255) | Why it was archived |
| `original_data` | JSONB | Full snapshot of the row |
| `restored_at` | TIMESTAMPTZ | If ever restored |

**Indexes:** `idx_archived_source` (source_table, source_record_id), `idx_archived_at`

## Materialized Views

| View | Purpose |
|------|---------|
| `mv_sync_health_dashboard` | Flattened sync health + last run status |
| `mv_data_quality_summary` | Pass/warning/fail counts per table |
| `mv_match_rate_trends` | Weekly aggregated match rate trends |
| `mv_pipeline_performance_summary` | Daily pipeline performance aggregates |

**Refresh function:** `refresh_analytics_views()` refreshes all concurrently.

## Helper Functions

| Function | Purpose |
|----------|---------|
| `evaluate_check_status(p_check_id, p_actual_result, p_failed_record_count)` | Evaluate a DQ check result against its threshold |
| `evaluate_alert_rule(p_rule_id)` | Determine if an alert rule should fire |
| `is_alert_in_cooldown(p_rule_id, p_cooldown_minutes)` | Check if alert is within cooldown period |
| `check_sync_health(p_source_name)` | Get overall health + score for a source |
| `apply_retention_policy(p_policy_id)` | Flag-based archival (never deletes) |

## Triggers

| Trigger | Table | Purpose |
|---------|-------|---------|
| `match_rate_auto_compute` | `match_rate_tracking` | Computes match/fuzzy percentages |
| `pipeline_perf_auto_compute` | `pipeline_performance` | Computes duration, cache rate, avg latency |
| `update_sync_health_updated_at` | `sync_health` | Auto-updates `updated_at` |
| `update_dq_checks_updated_at` | `data_quality_checks` | Auto-updates `updated_at` |
| `update_dq_alert_rules_updated_at` | `data_quality_alert_rules` | Auto-updates `updated_at` |
| `update_retention_policies_updated_at` | `data_retention_policies` | Auto-updates `updated_at` |

## Seed Data

The `seed_data.sql` file contains realistic test data including:

- **10 subcontractors** with varying compliance profiles (active, suspended, inactive, blacklisted, null optional fields)
- **6 projects** across different statuses (active, planning, completed, on hold, cancelled)
- **12 certifications** at various lifecycle stages (valid, expired, revoked, pending verification)
- **10 project-subcontractor assignments** with mixed status
- **7 violations** of different types (safety, insurance, licensing)
- **3 OSHA inspections** tied to violations
- **5 alert preferences** and **3 alert notifications**
- **2 certification renewals** (one pending, one rejected)
- **5 sync run logs** (completed, failed, partial)
- **4 sync health records** (healthy, degraded, unknown)
- **8 data quality checks** covering uniqueness, completeness, freshness, format, referential integrity
- **8 data quality results** (7 pass, 1 warning)
- **6 match rate tracking rows** across 3 sources over 2 days
- **5 alert rules** for sync failures, match rate drops, quality failures, stale data, and performance
- **3 alert log entries** (acknowledged, resolved, pending)
- **4 pipeline performance records** (completed, failed, partial)
- **5 API latency tracking entries**
- **4 data retention policies** (archive after 30-365 days, flag after 180 days)
- **1 archived record sample**

## Testing

Run `database/tests/validate_data_quality_schema.sql` against the database after applying the schema and seed data. Tests verify:

1. All 10 tables exist
2. Row counts > 0 after seeding
3. `match_rate_auto_compute` trigger calculates correctly (85.00% / 33.33%)
4. `pipeline_perf_auto_compute` trigger calculates duration, cache rate, and avg latency
5. Sync health indexes are present
6. All 4 materialized views exist
7. Unique constraint on `match_rate_tracking(source_name, match_date)`
8. Alert rule structure is correct
9. No retention policy uses `delete` action (only archive/flag)
10. Alert log entries reference valid alert rules

## Next Steps / Maintenance

- Schedule `refresh_analytics_views()` periodically (e.g. via pg_cron or application cron)
- Wire alert rules into notification delivery (email/Slack/SMS)
- Add monitoring dashboard queries against materialized views
- Consider partitioning `pipeline_performance` and `api_latency_tracking` by date once volume grows
- Review retention policies before production deployment
