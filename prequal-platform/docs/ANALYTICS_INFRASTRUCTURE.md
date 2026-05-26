# Analytics Infrastructure

**Owner**: Data Engineer  
**Date**: 2026-05-26  
**Related Ticket**: [MID-58](/MID/issues/MID-58)

## Overview

The analytics infrastructure provides performant, materialized-view-backed endpoints for the Dashboard & Compliance Metrics page. All aggregation happens at the database layer (PostgreSQL materialized views), and the FastAPI router is a thin translation layer between HTTP and SQL.

## Architecture

```
PostgreSQL (materialized views)
        |
        v
app/services/analytics_pipeline.py  (data aggregation)
        |
        v
app/routers/analytics.py           (HTTP router)
        |
        v
    Dashboard UI
```

## Materialized Views

| View | Endpoint | Description |
|------|----------|-------------|
| `mv_compliance_summary` | `GET /api/analytics/compliance/summary` | Single-row dashboard summary |
| `mv_compliance_trends` | `GET /api/analytics/compliance/trends` | Daily trend data for charts |
| `mv_certification_status` | `GET /api/analytics/compliance/export` | CSV/JSON export of certifications |
| `mv_project_compliance` | `GET /api/analytics/projects` | Per-project compliance summary |
| `mv_recent_alerts` | `GET /api/analytics/alerts/recent` | Recent alert log entries |

## Endpoints

### GET /api/analytics/compliance/summary
Returns a single-row summary of compliance metrics:
- total / active / suspended / blacklisted subcontractors
- compliance rate (%)
- expiring soon (30d, 60d)
- open violations (total, OSHA-specific)
- total penalties
- certification counts (valid, expired, pending)

### GET /api/analytics/compliance/trends
Query params: `days=30|60|90` (default: 30)
Returns a list of daily data points for the compliance trend chart.

### GET /api/analytics/compliance/export
Query params: `format=csv|json`, `expiration_bucket`, `limit`, `offset`
Exports certification status rows as CSV or JSON.

### GET /api/analytics/alerts/recent
Query params: `status`, `limit`, `offset`
Returns recent alert notifications enriched with certification and subcontractor data.

### GET /api/analytics/projects
Query params: `limit`, `offset`
Returns per-project compliance summaries.

## Data Pipeline Refresh

Run the refresh job after daily ETL:

```python
from app.services.analytics_refresh import run_analytics_refresh
import asyncio

summary = asyncio.run(run_analytics_refresh(triggered_by="schedule"))
```

This refreshes all materialized views concurrently (using `REFRESH MATERIALIZED VIEW CONCURRENTLY` where unique indexes exist).

## Indexing & Performance

Each materialized view has at least one unique index to support `CONCURRENTLY` refreshes:
- `mv_compliance_summary`: `idx_mv_compliance_summary_computed` (computed_at)
- `mv_compliance_trends`: `idx_mv_compliance_trends_date` (trend_date)
- `mv_certification_status`: `idx_mv_cert_status_cert_id` (certification_id) + expiration_bucket, subcontractor_id
- `mv_project_compliance`: `idx_mv_project_compliance_project` (project_id)
- `mv_recent_alerts`: `idx_mv_recent_alerts_alert_id` (alert_id) + created_at DESC, status

## Tests

- `tests/test_analytics_pipeline.py` — unit tests for data aggregation logic
- `tests/test_analytics_router.py` — integration tests for HTTP endpoints
- `scripts/validate_analytics_views.py` — stand-alone validation script for MV presence and structure

## Notes

- Never delete data from tables — use status flags (`expired`, `revoked`, etc.) per our data retention rules.
- Views are refreshed via the `analytics_refresh` pipeline job, not on every request.
- The CSV export endpoint returns an empty file with headers if no rows match the filter.
