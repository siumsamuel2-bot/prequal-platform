# MID-253: Subcontractor Compliance Database Data Model

## Overview

This document defines the comprehensive data model for Prequal's subcontractor compliance platform. The design supports mid-market general contractors in tracking subcontractor certifications, credentials, violations, and overall compliance status across projects.

## Core Entities

### 1. Organizations
The root entity representing a general contractor firm using the platform.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(255) | NOT NULL | Organization legal name |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

### 2. Subcontractors
Subcontractor companies being tracked for compliance.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| organization_id | UUID | FK → organizations | Owning organization |
| company_name | VARCHAR(255) | NOT NULL | Legal business name |
| contact_first_name | VARCHAR(100) | | Primary contact first name |
| contact_last_name | VARCHAR(100) | | Primary contact last name |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Primary email address |
| phone | VARCHAR(20) | | Primary phone |
| address_line1 | VARCHAR(255) | | Street address |
| address_line2 | VARCHAR(255) | | Suite/unit |
| city | VARCHAR(100) | | City |
| state | VARCHAR(50) | | State/province |
| zip_code | VARCHAR(20) | | Postal code |
| country | VARCHAR(100) | DEFAULT 'USA' | Country |
| ein | VARCHAR(20) | | Employer ID (encrypted) |
| license_number | VARCHAR(100) | | State contractor license |
| license_state | VARCHAR(50) | | License state |
| license_expiration | DATE | | License expiry |
| status | VARCHAR(50) | DEFAULT 'active' | active, inactive, suspended, blacklisted |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Indexes:** `idx_subcontractors_status`, `idx_subcontractors_license_expiration`, `idx_subcontractors_organization_id`

### 3. Certifications
Compliance certifications held by subcontractors (OSHA, safety training, etc.).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| subcontractor_id | UUID | FK → subcontractors, NOT NULL | Parent subcontractor |
| certification_type | VARCHAR(100) | NOT NULL | e.g., OSHA 10, OSHA 30, First Aid |
| certification_number | VARCHAR(100) | | Cert number from issuer |
| issuing_authority | VARCHAR(255) | | Who issued the cert |
| issue_date | DATE | | Date issued |
| expiration_date | DATE | NOT NULL | Must have expiration |
| status | VARCHAR(50) | DEFAULT 'valid' | valid, expired, revoked, pending_verification |
| document_url | TEXT | | URL to stored document |
| verification_status | VARCHAR(50) | DEFAULT 'unverified' | unverified, verified, failed |
| verified_at | TIMESTAMPTZ | | When verified |
| verified_by | UUID | | User who verified |
| notes | TEXT | | Additional notes |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Indexes:** `idx_certifications_subcontractor_id`, `idx_certifications_expiration_date`, `idx_certifications_status`

### 4. Projects
Construction projects the general contractor is managing.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| project_name | VARCHAR(255) | NOT NULL | Project display name |
| project_number | VARCHAR(100) | UNIQUE | Internal project code |
| description | TEXT | | Project description |
| client_name | VARCHAR(255) | | End client |
| client_contact | VARCHAR(255) | | Client contact info |
| start_date | DATE | | Planned/start date |
| estimated_end_date | DATE | | Estimated completion |
| actual_end_date | DATE | | Actual completion |
| address_line1 | VARCHAR(255) | | Project site address |
| address_line2 | VARCHAR(255) | | Suite/unit |
| city | VARCHAR(100) | | City |
| state | VARCHAR(50) | | State |
| zip_code | VARCHAR(20) | | Postal code |
| country | VARCHAR(100) | DEFAULT 'USA' | Country |
| status | VARCHAR(50) | DEFAULT 'planning' | planning, active, on_hold, completed, cancelled |
| budget | DECIMAL(15,2) | | Project budget |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Indexes:** `idx_projects_status`

### 5. Project_Subcontractors
Many-to-many assignment of subcontractors to projects.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| project_id | UUID | FK → projects, NOT NULL | Assigned project |
| subcontractor_id | UUID | FK → subcontractors, NOT NULL | Assigned subcontractor |
| role | VARCHAR(100) | | Trade/role on project |
| start_date | DATE | | When added to project |
| end_date | DATE | | When removed/completed |
| status | VARCHAR(50) | DEFAULT 'active' | active, completed, terminated |
| insurance_expiration | DATE | | Insurance expiry for this project |
| bonds_expiration | DATE | | Bond expiry for this project |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Constraint:** UNIQUE(project_id, subcontractor_id)

**Indexes:** `idx_project_subcontractors_project_id`, `idx_project_subcontractors_subcontractor_id`

### 6. Violations
Compliance violations (OSHA, licensing, insurance, etc.).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| subcontractor_id | UUID | FK → subcontractors, NOT NULL | Violated company |
| project_id | UUID | FK → projects, SET NULL | Related project |
| violation_type | VARCHAR(100) | NOT NULL | safety, licensing, insurance, etc. |
| violation_code | VARCHAR(50) | | Specific code (OSHA, etc.) |
| description | TEXT | NOT NULL | Violation description |
| issued_by | VARCHAR(255) | | Agency/authority |
| issued_date | DATE | NOT NULL | Date issued |
| effective_date | DATE | | When effective |
| resolution_date | DATE | | When resolved |
| status | VARCHAR(50) | DEFAULT 'open' | open, under_review, resolved, appealed |
| penalty_amount | DECIMAL(10,2) | | Fine amount |
| is_criminal | BOOLEAN | DEFAULT FALSE | Criminal violation |
| notes | TEXT | | Additional context |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**OSHA-Extended Fields (via ALTER):**
- osha_violation_id, citation_number, standard_cited
- initial_penalty, final_penalty, abatement_date, date_corrected
- contest_status, inspection_number, activity_number
- site_city, site_state, site_zip_code, site_address
- naics_code, inspection_type, owner_type
- gravity_score, probability_score, risk_category
- is_osha_violation (BOOLEAN DEFAULT TRUE)

**Indexes:** `idx_violations_subcontractor_id`, `idx_violations_project_id`, `idx_violations_issued_date`, `idx_violations_status`

### 7. State_Credential_Records
External state licensing board data fetched via API.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| state_code | VARCHAR(2) | NOT NULL | State abbreviation |
| credential_number | VARCHAR(100) | NOT NULL | License number from state |
| credential_type | VARCHAR(100) | NOT NULL | e.g., General Contractor |
| issuing_state | VARCHAR(100) | NOT NULL | Full state name |
| holder_name | VARCHAR(255) | | Name on credential |
| holder_address | TEXT | | Full address |
| holder_city | VARCHAR(100) | | City |
| holder_state | VARCHAR(50) | | State |
| holder_zip | VARCHAR(20) | | ZIP code |
| issue_date | DATE | | Date issued |
| expiration_date | DATE | | Expiration date |
| status | VARCHAR(50) | DEFAULT 'active' | active, expired, revoked, suspended |
| external_source_id | VARCHAR(255) | | ID in state's system |
| external_source_url | TEXT | | Link to state record |
| last_synced_at | TIMESTAMPTZ | Auto-update | Last API sync |
| sync_version | INTEGER | DEFAULT 1 | Increments on update |
| raw_data | JSONB | | Full raw API response |
| subcontractor_id | UUID | FK → subcontractors, SET NULL | Matched internal record |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Constraint:** UNIQUE(state_code, credential_number, credential_type)

**Indexes:** `idx_state_credential_state_code`, `idx_state_credential_subcontractor_id`, `idx_state_credential_status`, `idx_state_credential_expiration`

### 8. OSHA_Inspections
OSHA inspection records linked to violations.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| inspection_number | VARCHAR(100) | UNIQUE, NOT NULL | OSHA inspection ID |
| activity_number | VARCHAR(100) | | Activity number |
| inspection_date | DATE | NOT NULL | When inspected |
| completion_date | DATE | | When completed |
| type | VARCHAR(100) | NOT NULL | Complaint, Referral, Fatality, etc. |
| scope | VARCHAR(100) | | Partial, Full |
| site_city | VARCHAR(100) | | Site city |
| site_state | VARCHAR(50) | | Site state |
| site_zip_code | VARCHAR(20) | | Site ZIP |
| site_address | TEXT | | Full address |
| naics_code | VARCHAR(20) | | NAICS industry code |
| reported_by | VARCHAR(255) | | Who reported |
| owner_type | VARCHAR(50) | | Construction type |
| safety_man_hour | INTEGER | | Inspection hours |
| health_man_hour | INTEGER | | Health inspection hours |
| total_penalty | DECIMAL(10,2) | | Total penalty assessed |
| abatement_completed | DATE | | Abatement date |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

## Compliance-Specific Entities

### 9. Alert_Preferences
User preferences for certification expiration alerts.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | NOT NULL | User reference |
| certification_types | TEXT[] | | Types to monitor (NULL = all) |
| advance_notice_days | INTEGER | DEFAULT 30 | Days before expiry to alert |
| alert_methods | TEXT[] | DEFAULT '{email}' | email, sms, in_app |
| is_active | BOOLEAN | DEFAULT TRUE | Enable/disable |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

### 10. Alert_Notifications
Scheduled/ sent expiration alerts.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| certification_id | UUID | FK → certifications, NOT NULL | Related cert |
| alert_type | VARCHAR(50) | NOT NULL | expiration_approaching, expired |
| scheduled_for | TIMESTAMPTZ | NOT NULL | When to send |
| sent_at | TIMESTAMPTZ | | When actually sent |
| status | VARCHAR(50) | DEFAULT 'pending' | pending, sent, failed, cancelled |
| method | VARCHAR(50) | | email, sms, in_app |
| recipient | VARCHAR(255) | | Email or phone |
| subject | VARCHAR(255) | | Email subject |
| body | TEXT | | Message body |
| retry_count | INTEGER | DEFAULT 0 | Retry attempts |
| max_retries | INTEGER | DEFAULT 3 | Max retries |
| error_message | TEXT | | Last error |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

### 11. Certification_Renewals
Renewal request workflow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| certification_id | UUID | FK → certifications, NOT NULL | Cert to renew |
| requested_by | UUID | NOT NULL | User requestor |
| requested_at | TIMESTAMPTZ | DEFAULT NOW() | Request time |
| status | VARCHAR(50) | DEFAULT 'pending' | pending, approved, rejected, completed |
| reviewed_by | UUID | | Reviewer user |
| reviewed_at | TIMESTAMPTZ | | Review time |
| notes | TEXT | | Review notes |
| new_expiration_date | DATE | | Approved new date |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

## Sync & Data Pipeline Entities

### 12. Sync_Run_Logs
Audit log for data sync pipelines.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| job_name | VARCHAR(255) | NOT NULL, INDEX | e.g., osha_daily_sync |
| job_type | VARCHAR(100) | NOT NULL | osha_sync, state_credential_sync |
| status | VARCHAR(50) | DEFAULT 'running' | running, completed, partial, failed, skipped |
| triggered_by | VARCHAR(100) | DEFAULT 'schedule' | schedule, manual, webhook |
| started_at | TIMESTAMPTZ | DEFAULT NOW() | Job start |
| completed_at | TIMESTAMPTZ | | Job end |
| records_processed | INTEGER | DEFAULT 0 | Total processed |
| records_inserted | INTEGER | DEFAULT 0 | New records |
| records_updated | INTEGER | DEFAULT 0 | Modified records |
| records_failed | INTEGER | DEFAULT 0 | Failed records |
| records_matched | INTEGER | DEFAULT 0 | Matched to subs |
| error_message | TEXT | | Error details |
| run_metadata | JSONB | | Additional structured info |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Indexes:** `idx_sync_run_logs_job_name`, `idx_sync_run_logs_status`, `idx_sync_run_logs_started_at`

### 13. External_Data_Freshness
Health tracking for external data sources.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| source_name | VARCHAR(100) | NOT NULL | osha, tx_credentials, etc. |
| source_type | VARCHAR(50) | NOT NULL | api, ftp, sftp |
| last_updated | TIMESTAMPTZ | | Last successful sync |
| next_scheduled_update | TIMESTAMPTZ | | Next expected sync |
| update_frequency | VARCHAR(50) | DEFAULT 'daily' | hourly, daily, weekly |
| status | VARCHAR(50) | DEFAULT 'current' | current, stale, failed_update |
| last_run_log_id | UUID | FK → sync_run_logs | Reference to last run |
| error_count | INTEGER | DEFAULT 0 | Consecutive failures |
| last_error_message | TEXT | | Last error |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMPTZ | Auto-update | Last modification |

**Constraint:** UNIQUE(source_name, source_type)

## Relationships

```
organizations
├── users (1:M)
├── subcontractors (1:M)
│   ├── certifications (1:M)
│   ├── violations (1:M)
│   ├── state_credential_records (1:M) [via subcontractor_id]
│   └── project_subcontractors (1:M)
├── projects (1:M)
│   └── project_subcontractors (1:M)
├── certifications (1:M)
│   └── alert_notifications (1:M)
│   └── certification_renewals (1:M)
└── feedback (1:M)

subcontractors
├── certifications (1:M)
├── violations (1:M)
├── project_subcontractors (1:M)
└── state_credential_records (1:M) [matched external records]

projects
└── project_subcontractors (1:M)
└── violations (1:M) [optional]

osha_inspections (standalone)
└── violations (1:M) [via inspection_number]

sync_run_logs (standalone)
└── external_data_freshness (1:1) [via last_run_log_id]
```

## Key Indexes Summary

| Table | Index | Purpose |
|-------|-------|---------|
| subcontractors | idx_subcontractors_status | Filter by status |
| subcontractors | idx_subcontractors_license_expiration | Expiration alerts |
| subcontractors | idx_subcontractors_organization_id | Org filtering |
| certifications | idx_certifications_subcontractor_id | Sub doc lookup |
| certifications | idx_certifications_expiration_date | Expiration queries |
| certifications | idx_certifications_status | Status filtering |
| project_subcontractors | idx_project_subcontractors_project_id | Project subs |
| project_subcontractors | idx_project_subcontractors_subcontractor_id | Sub projects |
| violations | idx_violations_subcontractor_id | Sub violations |
| violations | idx_violations_project_id | Project violations |
| violations | idx_violations_issued_date | Date range queries |
| violations | idx_violations_status | Status filtering |
| state_credential_records | idx_state_credential_state_code | State filtering |
| state_credential_records | idx_state_credential_subcontractor_id | Matched subs |
| state_credential_records | idx_state_credential_expiration | Expiration |
| state_credential_records | idx_state_credential_holder_name | Full-text search |

## Security & Compliance Considerations

### PII Encryption
- `subcontractors.ein` — Encrypted at rest (AES-256)
- `subcontractors.contact_first_name/last_name` — Consider encryption for sensitive deployments
- All PHI should be treated per applicable regulations

### Data Retention
- Use `archived_records` table with JSONB snapshot for long-term retention
- Flag-based archival (no hard deletes) to maintain audit trail
- Retention policies configurable per table

### Audit Trail
- All tables include `created_at` and `updated_at` timestamps
- `updated_at` automatically maintained via triggers
- Sensitive operations logged in sync_run_logs

## Implementation Notes

### Migration Priority
1. Core tables (01_core_tables.sql) — Foundational
2. Expiration tracking (02_expiration_tracking.sql) — Alert system
3. OSHA integration (03_osha_integration.sql) — Compliance data
4. State credentials (04_state_credentials.sql) — External data
5. Data quality monitoring (05_data_quality_monitoring.sql) — Operational excellence

### SQLAlchemy Model Alignment
The current `backend/app/models/models.py` uses integer PKs and simpler structures. Full implementation requires:
1. Migrate to UUID primary keys
2. Add all OSHA-extended violation fields
3. Implement state_credential_records model
4. Add sync_run_logs and external_data_freshness

### Materialized Views
- `compliance_status_by_subcontractor` — Pre-computed compliance scores
- `osha_violation_trends` — Monthly violation analytics
- `expiring_certifications` — 90-day expiration list
- `recent_violations` — Last 60 days violations

Refresh strategy: Daily via `refresh_analytics_views()` function.

## Summary

This data model supports:
- Multi-tenant organization structure
- Full subcontractor profiles with contact info and licensing
- Certification lifecycle management with expiration tracking
- Project assignment and tracking
- OSHA and state credential integration
- Violation tracking with full OSHA attributes
- Alert and notification workflow
- Data quality monitoring and pipeline health tracking

The design prioritizes query performance (composite indexes), data integrity (foreign keys with appropriate delete actions), and compliance (audit trails, encryption ready).