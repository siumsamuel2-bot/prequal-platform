# Data Model Design: Subcontractor Compliance Tracking

**Owner**: Data Engineer  
**Date**: 2026-05-05  
**Related Tickets**: [MID-12](/MID/issues/MID-12) (Design), [MID-14](/MID/issues/MID-14) (Implementation)  
**Status**: Complete — design rationale documented; implementation in `database/schemas/`

## 1. Design Principles

- **Data Integrity First**: Foreign keys, unique constraints, and `NOT NULL` checks enforced at the database level.
- **Audit-Everywhere**: `created_at` and `updated_at` on every table; triggers auto-update `updated_at`.
- **Soft Deletion / Status States**: Never delete production data. Use status fields (`active`, `inactive`, `suspended`, `blacklisted`) to archive or flag entities.
- **Scalable Identification**: UUID primary keys prevent enumeration and support distributed data ingestion (e.g., OSHA API imports).
- **Extensibility**: PostGIS enabled for future geospatial compliance mapping.

## 2. Entity-Relationship Model

### Core Entities

| Entity | Table | Description |
|--------|-------|-------------|
| **Subcontractor** | `subcontractors` | Master data for subcontractor companies |
| **Project** | `projects` | Construction projects managed by the general contractor |
| **Certification** | `certifications` | Licenses, OSHA training, safety certs held by subcontractors |
| **Violation** | `violations` | OSHA citations, insurance lapses, licensing issues |
| **ProjectAssignment** | `project_subcontractors` | Many-to-many link between projects and subcontractors |

### Supporting Entities

| Entity | Table | Description |
|--------|-------|-------------|
| **AlertPreference** | `alert_preferences` | Per-user notification rules for expiring certifications |
| **AlertNotification** | `alert_notifications` | Individual alert records with send status |
| **CertificationRenewal** | `certification_renewals` | Renewal workflow tracking |
| **OSHAInspection** | `osha_inspections` | Metadata for OSHA inspections |
| **OSHAAPILog** | `osha_api_logs` | Request/response logging for OSHA data ingestion |
| **OSHADataFreshness** | `osha_data_freshness` | Pipeline health and data freshness tracking |

### Relationships

```text
subcontractors (1) ──< (N) certifications
subcontractors (1) ──< (N) violations
projects (1) ──< (N) project_subcontractors >── (1) subcontractors
subcontractors (1) ──< (N) alert_preferences
subcontractors (1) ──< (N) certification_renewals
certifications (1) ──< (N) alert_notifications
certifications (1) ──< (N) certification_renewals
violations (N) >── (1) osha_inspections (via inspection_number)
```

- **CASCADE DELETE**: Child tables (`certifications`, `violations`, `project_subcontractors`) cascade on subcontractor deletion to maintain referential integrity.
- **SET NULL**: `violations.project_id` uses `ON DELETE SET NULL` to preserve the violation audit trail even if a project is archived.

## 3. Field Semantics & Validation

### `subcontractors.status`
- `active` — Fully qualified, can be assigned to projects
- `inactive` — No longer bidding/working, historical data preserved
- `suspended` — Temporarily ineligible (e.g., insurance lapse)
- `blacklisted` — Permanently disqualified (e.g., repeated safety violations)

### `certifications.status`
- `valid` — Current and verified
- `expired` — Past expiration date, requires renewal
- `revoked` — Fraudulently obtained or manually revoked
- `pending_verification` — Document uploaded, not yet verified

### `violations.status`
- `open` — Unresolved violation
- `under_review` — Being disputed or investigated
- `resolved` — Corrective action verified
- `appealed` — Under formal appeal process

## 4. Data Ingestion Pipeline Design (OSHA)

### Architecture
```
+-------------+      +------------------+      +------------------+
| OSHA API    | ---> | Ingestion Worker | ---> | prequal DB       |
| (external)  |      | (Python/ETL)     |      | (PostgreSQL)     |
+-------------+      +------------------+      +------------------+
                            |
                            v
                     +------------------+
                     | osha_api_logs    |
                     | osha_data_       |
                     |   freshness      |
                     +------------------+
```

### Pipeline Stages
1. **Extract**: Query OSHA API (inspections, violations, establishments) with pagination.
2. **Validate**: Check for duplicates (by `osha_violation_id` / `inspection_number`), schema conformance, and required fields.
3. **Transform**: Map OSHA JSON fields to normalized schema (e.g., `gravity_score`, `penalty_amount`).
4. **Load**: Upsert into `violations`, `osha_inspections`. Log every batch in `osha_api_logs`.
5. **Monitor**: Update `osha_data_freshness` with last-success timestamp and next-scheduled run.

### Error Handling
- Partial failures logged in `osha_api_logs.error_message`
- Retry with exponential backoff up to `max_retries`
- Stale data flagged in `osha_data_freshness.status`

## 5. Analytics Requirements

### Compliance Reporting Views

| View | Purpose |
|------|---------|
| `compliance_status_by_subcontractor` | Dashboard summary: valid/expired certs, open/resolved violations, total penalties per sub |
| `osha_violation_trends` | Monthly trend analysis: violation count, penalties, gravity scores |
| `expiring_certifications` | Near-term expiration alerts (≤ 90 days) for proactive renewal |
| `recent_violations` | Violations issued in last 60 days for latest activity feeds |

### Key Metrics
- **Compliance Score**: `(valid_certs / total_certs) * (1 - open_violations_weight)`
- **Risk Rating**: Derived from `gravity_score`, `probability_score`, and violation history
- **Days to Expiration**: Calculated field for certification urgency sorting

## 6. Indexing Strategy

- **B-tree indexes** on all foreign keys, status fields, and expiration dates for fast filtering.
- **Composite unique** on `(project_id, subcontractor_id)` to prevent duplicate assignments.
- **Full-text** support can be added later on `violations.description` for search.

## 7. Security & Privacy

- **Never delete** production data — archive via status changes.
- **Audit trail** — `osha_api_logs` retains full request/response history.
- **PII handling** — Subcontractor emails/phones stored in `subcontractors`; access controlled at application layer.

---

## Deliverables Checklist
- [x] Entity-relationship model documented
- [x] Relationships, constraints, and cascade rules specified
- [x] Data ingestion pipeline for OSHA designed
- [x] Analytics requirements and views defined
- [x] Implementation exists: `database/schemas/01_core_tables.sql`, `02_expiration_tracking.sql`, `03_osha_integration.sql`
- [x] Seed data available: `database/seeds/seed_data.sql`
- [x] Validation tests: `database/tests/validate_schema.sql`, `database/validate_schema.sql`
