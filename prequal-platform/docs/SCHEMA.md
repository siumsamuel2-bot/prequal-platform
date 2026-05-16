# Prequal Compliance Platform — Database Schema Documentation

## Overview

PostgreSQL schema for subcontractor compliance tracking. Designed for FastAPI with SQLAlchemy 2.0.

## Entity Relationships

```
subcontractors
  ├── certifications (1:N)
  ├── violations (1:N)
  └── project_subcontractors (N:M via)

projects
  └── project_subcontractors (N:M via)

alert_preferences / alert_notifications / certification_renewals
  └── certifications (N:1)

osha_inspections  ←  violations (reference only, no FK)
osha_api_logs    ←  osha_data_freshness (FK)
```

## Core Tables

### subcontractors
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | |
| company_name | VARCHAR(255) | NOT NULL | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | |
| license_number | VARCHAR(100) | | |
| license_expiration | DATE | | |
| status | VARCHAR(50) | DEFAULT 'active' | |
| ... | | | Full field list in 001 migration |

### projects
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| project_name | VARCHAR(255) | NOT NULL | |
| project_number | VARCHAR(100) | UNIQUE | |
| status | VARCHAR(50) | DEFAULT 'planning' | |

### certifications
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| subcontractor_id | UUID | FK → subcontractors.id, ON DELETE CASCADE | |
| certification_type | VARCHAR(100) | NOT NULL | e.g. OSHA 30 |
| expiration_date | DATE | NOT NULL | |
| status | VARCHAR(50) | DEFAULT 'valid' | |
| verification_status | VARCHAR(50) | DEFAULT 'unverified' | |

### violations
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| subcontractor_id | UUID | FK → subcontractors.id, ON DELETE CASCADE | |
| violation_type | VARCHAR(100) | NOT NULL | |
| issued_date | DATE | NOT NULL | |
| is_osha_violation | BOOLEAN | DEFAULT TRUE | Flag for OSHA-sourced violations |
| osha_violation_id | VARCHAR(100) | | OSHA-specific identifier |
| inspection_number | VARCHAR(100) | | Links to osha_inspections |
| standard_cited | VARCHAR(100) | | OSHA standard number |
| gravity_score | NUMERIC(5,2) | | OSHA severity metric |
| probability_score | NUMERIC(5,2) | | OSHA likelihood metric |
| risk_category | VARCHAR(50) | | ‘high’, ‘serious’, etc. |

### project_subcontractors (junction)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, CASCADE | |
| subcontractor_id | UUID | FK → subcontractors.id, CASCADE | |
| role | VARCHAR(100) | | |
| UNIQUE(project_id, subcontractor_id) | | | |

## Expiration & Alert Tables

### alert_preferences
- user_id, certification_types[], advance_notice_days, alert_methods[], is_active

### alert_notifications
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | |
| certification_id | UUID | FK → certifications.id, CASCADE | |
| alert_type | VARCHAR(50) | NOT NULL | e.g. `expiration_30d` |
| scheduled_for | TIMESTAMP WITH TZ | NOT NULL | Date alert was generated |
| sent_at | TIMESTAMP WITH TZ | | Reserved for external notification delivery |
| status | VARCHAR(50) | DEFAULT 'pending' | `pending`, `acknowledged`, `sent`, `failed` |
| acknowledged_at | TIMESTAMP WITH TZ | | When alert was acknowledged |
| days_until_expiration | INTEGER | | Denormalized for quick querying |
| method | VARCHAR(50) | | `in_app` (no external delivery yet) |
| recipient | VARCHAR(255) | | Target recipient |
| subject | VARCHAR(255) | | Alert subject line |
| body | TEXT | | Full alert message |
| retry_count | INTEGER | DEFAULT 0 | Delivery retry attempts |
| max_retries | INTEGER | DEFAULT 3 | Maximum retry attempts |
| error_message | TEXT | | Error on delivery failure |
| created_at | TIMESTAMP WITH TZ | DEFAULT CURRENT_TIMESTAMP | |
| updated_at | TIMESTAMP WITH TZ | DEFAULT CURRENT_TIMESTAMP | |

### certification_renewals
- certification_id FK, requested_by, status, reviewed_by, new_expiration_date

## OSHA Integration Tables

### osha_inspections
- inspection_number (UNIQUE), activity_number, inspection_date, type, site info, penalties

### osha_api_logs
- request_type, request_parameters (JSON), response_status, response_body (JSON), error_message

### osha_data_freshness
- data_type, last_updated, next_scheduled_update, update_frequency, status, last_run_log_id FK

## Views

### compliance_status_by_subcontractor
Aggregated compliance status: valid/expired certs, open/resolved OSHA violations, total penalties, earliest cert expiration.

### osha_violation_trends
Monthly rollup of OSHA violations by subcontractor with penalty totals and gravity averages.

### expiring_certifications
Filter for certs expiring within 90 days that are not revoked.

### recent_violations
Violations issued in the last 60 days, ordered by issued_date DESC.

## Indexes

All tables have `idx_<table>_<column>` indexes on primary foreign keys and commonly filtered columns. See migration `001_initial_schema.py` for full listing.

## Constraints Summary

- All tables use UUID primary keys with `uuid-ossp` extension
- Foreign keys enforce CASCADE delete where appropriate
- Subcontractor email is UNIQUE
- Project project_number is UNIQUE
- Inspection inspection_number is UNIQUE
- Junction table ensures unique (project, subcontractor) pairs

## Migration

Managed by Alembic. Run:
```bash
alembic upgrade head
```

## Seed Data

Run after migrations:
```bash
python scripts/seed_data.py
```

Populates 4 subcontractors, 2 projects, 4 certifications, 2 violations, and 4 project assignments with real-world data shapes.
