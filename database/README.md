# Prequal Database Schema

## Overview
This directory contains the PostgreSQL schema definitions, seed data, and validation scripts for the Prequal Subcontractor Compliance Platform.

## Directory Structure
- `schemas/` - Core database schema definitions, ordered by application sequence
- `seeds/` - Realistic seed data for development and testing
- `tests/` - Schema validation and integrity tests
- `validate_schema.sql` - Comprehensive constraint validation script
- `README.md` - This file

## Schema Files

### 01_core_tables.sql
Creates the foundational tables for the compliance platform:
- **subcontractors** - Subcontractor master data
- **projects** - Project information
- **certifications** - Subcontractor certificates and licenses
- **project_subcontractors** - Many-to-many assignment table
- **violations** - OSHA and other compliance violations

### 02_expiration_tracking.sql
Extends the core schema with expiration management capabilities:
- **alert_preferences** - Per-user notification settings for expiring certs
- **alert_notifications** - Individual alert records with tracking
- **certification_renewals** - Renewal workflow management

### 03_osha_integration.sql
OSHA data feed integration, analytics, and reporting extensions:
- **osha_inspections** - OSHA inspection metadata
- **osha_api_logs** - API request/response logging
- **osha_data_freshness** - Data pipeline health tracking
- **Analytics views**: `compliance_status_by_subcontractor`, `osha_violation_trends`, `expiring_certifications`, `recent_violations`

### 04_state_credentials.sql
State credential database integration for external compliance data:
- **state_credential_records** - Raw state licensing board data
- **sync_run_logs** - Pipeline execution audit log
- **external_data_freshness** - Data source health tracking

### 05_data_quality_monitoring.sql
Data quality monitoring, analytics, and pipeline performance tracking:
- **sync_health** - Sync health dashboard data
- **data_quality_checks** - Configurable data quality rules
- **data_quality_results** - Check execution results
- **match_rate_tracking** - External data match rate metrics
- **data_quality_alert_rules** / **data_quality_alert_log** - Alert system
- **pipeline_performance** / **api_latency_tracking** - Performance monitoring
- **data_retention_policies** / **archived_records** - Retention and archival
- **Materialized views**: `mv_sync_health_dashboard`, `mv_data_quality_summary`, `mv_match_rate_trends`, `mv_pipeline_performance_summary`

### 06_production_migration.sql
Production migration script bridging SQL schema with Alembic models:
- Creates stub tables required by `compliance.py` models (users, organizations, teams, uploaded_credentials, notification_delivery_logs)
- Adds production FK constraints (verified_by, user_id, requested_by, reviewed_by)
- Aligns `subcontractors` with encrypted columns from MID-75
- Creates production-performance composite indexes for compliance lookups
- Seeds production data quality checks and sync health baseline
- Adds table comments for documentation

## Seed Data

### seeds/seed_data.sql
Original comprehensive seed data covering:
- Happy path (fully compliant subcontractors)
- Expiring certifications (triggers expiration workflow)
- Expired certifications (grace period, renewal needed)
- Revoked certifications (fraud detection, compliance failure)
- OSHA violations (open, resolved, contested)
- Insurance lapses (business interruption risk)
- Suspended and blacklisted subcontractors
- Edge cases (NULL optional fields, missing EIN, special characters)

### seeds/seed_production.sql
Production-specific supplemental data (MID-81):
- User baseline (admin, data engineer)
- Additional subcontractors with edge cases (multi-state, long names, blacklisted)
- Additional certifications (expiring soon, pending verification)
- Additional violations (serious, multi-state)
- Additional project with subcontractor assignments
- State credential record seeds (TX, CA, NY)
- Sync health baseline

## Running the Schema

```bash
# 1. Create database
createdb prequal_compliance

# 2. Apply schema in order
psql -d prequal_compliance -f schemas/01_core_tables.sql
psql -d prequal_compliance -f schemas/02_expiration_tracking.sql
psql -d prequal_compliance -f schemas/03_osha_integration.sql
psql -d prequal_compliance -f schemas/04_state_credentials.sql
psql -d prequal_compliance -f schemas/05_data_quality_monitoring.sql
psql -d prequal_compliance -f schemas/06_production_migration.sql

# 3. Seed data
psql -d prequal_compliance -f seeds/seed_data.sql
psql -d prequal_compliance -f seeds/seed_production.sql

# 4. Validate constraints and data integrity
psql -d prequal_compliance -f tests/validate_schema.sql
psql -d prequal_compliance -f tests/validate_data_quality_schema.sql
psql -d prequal_compliance -f validate_schema.sql
```

## Validation Results
The validation scripts test:
1. Table existence (all 20+ tables)
2. Primary key constraints
3. Foreign key relationships and cascade behavior
4. Unique constraints (email, project_number, assignments)
5. Not-null constraints
6. Status enum validation
7. Data integrity of seed data
8. Trigger functionality (`updated_at` auto-update)
9. Index presence and performance readiness
10. Analytics view correctness
11. Data quality auto-compute triggers (match rate, pipeline performance)
12. Materialized view refresh functions

## Key Design Decisions
- **UUIDs for primary keys** - Enables safe distributed data ingestion and prevents enumeration attacks
- **ON DELETE CASCADE** for child tables (certifications, violations) to maintain referential integrity
- **ON DELETE SET NULL** for violations.project_id to preserve violation audit trail when projects are archived
- **Never delete** - Archive or flag data instead (see `archived_records`, `data_retention_policies`)
- **status** fields use VARCHAR with application-level enums (CHECK constraints can be added per-deployment)
- **updated_at triggers** on all major tables for audit trail
- **PostGIS** enabled for future geospatial compliance mapping
- **Encrypted columns** for PII (MID-75) - `encrypted_ein`, `encrypted_contact_first_name`, etc.
