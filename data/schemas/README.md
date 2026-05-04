# Database Schema: Prequal Subcontractor Compliance Platform

## Overview
PostgreSQL schema designed for tracking subcontractor certifications, projects, compliance violations, and OSHA integration. Aligns with FastAPI + PostgreSQL architecture for mid-market general contractors ($10M-$50M revenue).

## Schema Components

### Core Tables (`01_core_tables.sql`)
- **`subcontractors`**: Contractor master data (company, contact, licensing)
- **`projects`**: Project metadata (location, timeline, budget)
- **`certifications`**: Subcontractor certifications (OSHA, safety training)
- **`violations`**: Compliance violations with OSHA-specific fields
- **`project_subcontractors`**: Many-to-many relationship between projects and subcontractors

### Expiration Tracking (`02_expiration_tracking.sql`)
- **`alert_preferences`**: User notification settings
- **`alert_notifications`**: Scheduled/triggered alerts (email, SMS, in-app)
- **`certification_renewals`**: Renewal request workflow

### OSHA Integration (`03_osha_integration.sql`)
- **`osha_inspections`**: OSHA inspection metadata
- **`osha_api_logs`**: API ingestion audit trail
- **`osha_data_freshness`**: Data staleness tracking
- **Analytics Views**: Pre-built compliance reporting

## Key Features
- UUIDv4 identifiers for globally unique IDs
- `ON DELETE CASCADE` for relational integrity
- Indexes on foreign keys, expiration dates, and status fields
- `created_at`/`updated_at` auditing on all tables
- PostGIS extension (unused, staged for future location-based reporting)

## Implementation Notes
1. **Data Integrity**: `NOT NULL` constraints on business-critical fields (e.g., `certifications.expiration_date`)
2. **Extensibility**: String-based types (`certification_types`, `violation_types`) avoid enum lock-in
3. **Denormalization**: `violations` retains `subcontractor_id` for simpler queries

## Sample Seed Data Requirements
Collaborate with API team to seed:
- 5 contractors (mix of compliant/non-compliant)
- 3 projects with 2-4 subcontractor assignments
- 3 certifications per contractor (OSHA 10/30, First Aid)
- 2-3 violations per high-risk contractor

## Related Issues
- [MID-14: Contingency: Database Schema Design](/MID/issues/MID-14)
- [MID-6: Core Architecture and Data Modeling](/MID/issues/MID-6)