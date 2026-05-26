# Analytics Schema Documentation

## Overview
This document describes the analytics materialized views and aggregation pipeline built for the Dashboard & Compliance Metrics (MID-58). These views power the backend API endpoints consumed by the frontend dashboard.

## Materialized Views

### 1. mv_compliance_summary
**Purpose:** Dashboard card-level metrics (top-line KPIs).
**Used by:** `GET /api/compliance/summary`
**Refresh:** Daily after ETL pipeline completes.

| Column | Type | Description |
|--------|------|-------------|
| total_subcontractors | int | Count of all subcontractors |
| active_subcontractors | int | Count of status='active' subcontractors |
| suspended_subcontractors | int | Count of status='suspended' subcontractors |
| blacklisted_subcontractors | int | Count of status='blacklisted' subcontractors |
| compliant_subcontractors | int | Subs with >=1 valid cert AND no open violations |
| expiring_soon_30d | int | Subs with certs expiring within 30 days |
| expiring_soon_60d | int | Subs with certs expiring within 60 days |
| open_violations | int | Total open violations (all types) |
| open_osha_violations | int | Open violations where is_osha_violation = TRUE |
| total_open_penalties | decimal | Sum of penalties for open violations |
| valid_certifications | int | Count of status='valid' certs |
| expired_certifications | int | Count of status='expired' certs |
| pending_verification_certs | int | Count of pending_verification certs |
| computed_at | timestamp | When the view was last refreshed |

### 2. mv_compliance_trends
**Purpose:** Daily compliance trend data for chart rendering.
**Used by:** `GET /api/compliance/trends?days=N`
**Refresh:** Daily after ETL pipeline completes.

| Column | Type | Description |
|--------|------|-------------|
| trend_date | date | Date of the data point |
| active_subcontractors | int | Active subs on that day |
| valid_certifications | int | Valid certs on that day |
| expired_certifications | int | Expired certs on that day |
| open_violations | int | Open violations on that day |
| open_osha_violations | int | OSHA open violations on that day |
| compliance_percentage | float | % compliant subcontractors |
| computed_at | timestamp | When the view was last refreshed |

### 3. mv_certification_status
**Purpose:** Detailed certification status with expiration bucket classification.
**Used by:** `GET /api/compliance/export`
**Refresh:** Daily after ETL pipeline completes.

**Expiration Buckets:**
- `critical` — expires within 7 days
- `warning` — expires within 30 days
- `attention` — expires within 60 days
- `valid` — expires after 60 days
- `expired` — already expired

### 4. mv_project_compliance
**Purpose:** Per-project compliance rollup.
**Used by:** `GET /api/compliance/summary` (by project)
**Refresh:** Daily after ETL pipeline completes.

### 5. mv_recent_alerts
**Purpose:** Recent alert notifications with full context.
**Used by:** `GET /api/alerts/recent`
**Refresh:** Daily after ETL pipeline completes.

## Data Pipeline Integration

The analytics refresh is triggered at the end of the full ETL pipeline:

```python
from app.services.analytics_refresh import run_analytics_refresh

# After OSHA sync + data quality checks
await run_analytics_refresh(triggered_by="schedule")
```

## Performance

All materialized views have unique indexes to support `REFRESH MATERIALIZED VIEW CONCURRENTLY`:
- `mv_compliance_summary`: `idx_mv_compliance_summary_computed` (computed_at)
- `mv_compliance_trends`: `idx_mv_compliance_trends_date` (trend_date)
- `mv_certification_status`: `idx_mv_cert_status_cert_id` (certification_id)
- `mv_project_compliance`: `idx_mv_project_compliance_project` (project_id)
- `mv_recent_alerts`: `idx_mv_recent_alerts_alert_id` (alert_id)

## Data Validity

Views reflect the state of data as of the last refresh. The `computed_at` column in each view provides a freshness timestamp. Refresh frequency is daily (scheduled). For more frequent refreshes, consider event-based refresh triggers on INSERT/UPDATE operations for specific tables.
