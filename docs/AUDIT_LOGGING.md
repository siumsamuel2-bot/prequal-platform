# Database Audit Logging

## Overview

Structured audit logging for all read/write operations on customer data.
Complements the existing auth-focused `audit_logs` with domain-specific
tables optimized for data access analytics and compliance.

Owner: Data Engineer  
Ticket: [MID-434](/MID/issues/MID-434)  

## Components

### 1. data_access_audit_logs table

New table added via migration `024_data_access_audit_logging.py`.

**Schema:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Actor (nullable for system/API actions) |
| operation_type | VARCHAR(20) | POST, GET, PUT, DELETE, PATCH, BULK_READ, BULK_WRITE, EXPORT, IMPORT |
| resource_type | VARCHAR(100) | Table/entity name (e.g., subcontractors) |
| resource_id | VARCHAR(500) | Specific row PK or comma-separated for bulk |
| org_id | UUID | Organization scope for multi-tenant queries |
| ip_address | VARCHAR(45) | Client IP |
| user_agent | VARCHAR(500) | Client user agent |
| request_id | VARCHAR(255) | Correlation ID |
| session_id | VARCHAR(255) | Session correlation |
| query_filter | TEXT | Query filter applied |
| fields_accessed | TEXT | Fields included in read |
| record_count | INTEGER | Number of records touched |
| change_summary | TEXT | Human-readable change summary |
| before_values | JSON | Snapshot before write |
| after_values | JSON | Snapshot after write |
| status | VARCHAR(20) | success or error |
| error_message | TEXT | Error detail if applicable |
| compliance_tag | VARCHAR(100) | e.g., gdpr, hipaa |
| retention_until | TIMESTAMPTZ | Retention boundary |
| created_at | TIMESTAMPTZ | Event timestamp |

**Indexes:**
Per-column and composite indexes for common compliance query patterns:
- User + operation, resource + created, org + created, compliance_tag + created.

### 2. SQLAlchemy Model

**File:** `prequal-platform/app/models/compliance.py`  
**Class:** `DataAccessAuditLog`

Registered in `app/models/__init__.py`.

### 3. Audit Logging Service

**File:** `prequal-platform/app/services/audit_logging.py`

Provides:
- `DataAccessAuditEvent` dataclass
- `AuditLoggingService` with `log()` method
- `log_data_access()` convenience function
- Context var propagation for request/user/org/session IDs

**Usage example:**
```python
from app.services.audit_logging import log_data_access
log_data_access(
    operation_type="GET",
    resource_type="subcontractors",
    resource_id=str(subcontractor_id),
    record_count=1,
    compliance_tag="gdpr",
)
```

### 4. Compliance Views

Planned views (to be applied after migration):
- `v_compliance_data_access_summary` — daily rollup by operation/resource/status
- `v_compliance_user_access_history` — per-user access for GDPR/SAR queries
- `v_compliance_failed_access_attempts` — failed/error access for security review
- `v_compliance_sensitive_data_access` — flag exports and bulk reads on PII

## Data Pipeline / ELK

The service emits structured JSON logs via `logging.getLogger("prequal.data_access_audit")`.
Configure your log shipper to forward these to ELK for centralized search and alerting.

## Migration

Run the Alembic migration to create the table:
```bash
alembic upgrade 024_data_access_audit_logging
```

## Related Issues

- [MID-434: Implement audit logging for data access](/MID/issues/MID-434)
- Migration complements existing `012_security_audit_lockout` (auth-focused `audit_logs`).

## Repository Schema Artifact (added 2026-10-02)

`database/schemas/09_audit_logging.sql` now contains the full DDL for the
`audit_logs` audit-trail table used by the root `backend/` service:
insert-only enforcement (BEFORE UPDATE/DELETE triggers), compliance query
indexes, and analytics views (`audit_resource_access`,
`audit_user_activity_daily`, `audit_high_risk_events`,
`audit_elk_export_backlog`).

The root `backend/` service also gained:
- `backend/app/services/audit_elk_exporter.py` — incremental bulk shipper to
  Elasticsearch with watermarks and NDJSON spool fallback (durable when ELK is
  down; idempotent doc IDs; env-configured via `ELASTICSEARCH_URL`,
  `ELASTICSEARCH_API_KEY`, `AUDIT_EXPORT_INDEX`, `AUDIT_EXPORT_SPOOL_DIR`).
- `backend/app/api/endpoints/audit.py` — compliance read API
  (`GET /api/v1/compliance/audit-logs`, `/audit-logs/high-risk`), restricted
  to admin/compliance/auditor roles.
- `AuditContextMiddleware` + `register_event_listeners()` wired into
  `backend/app/main.py`.

Verification: `backend/tests/test_audit_logging.py` 9/9 pass;
`prequal-platform/tests/test_audit_logging.py` 13/13 pass.
