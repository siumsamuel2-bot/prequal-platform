# Prequal Database Schema

## Overview
This directory contains the PostgreSQL schema definitions, seed data, and validation scripts for the Prequal Subcontractor Compliance Platform.

## Directory Structure
- `schemas/` - Core database schema definitions, ordered by application sequence
- `seeds/` - Realistic seed data for development and testing
- `tests/` - Schema validation and integrity tests
- `validate_schema.sql` - Comprehensive constraint validation script

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

## Seed Data
`seeds/seed_data.sql` contains realistic compliance scenarios covering:
- Happy path (fully compliant subcontractors)
- Expiring certifications (triggers expiration workflow)
- Expired certifications (grace period, renewal needed)
- Revoked certifications (fraud detection, compliance failure)
- OSHA violations (open, resolved, contested)
- Insurance lapses (business interruption risk)
- Suspended and blacklisted subcontractors
- Edge cases (NULL optional fields, missing EIN, special characters)

## Running the Schema

```bash
# 1. Create database
createdb prequal_compliance

# 2. Apply schema in order
psql -d prequal_compliance -f schemas/01_core_tables.sql
psql -d prequal_compliance -f schemas/02_expiration_tracking.sql
psql -d prequal_compliance -f schemas/03_osha_integration.sql

# 3. Seed data
psql -d prequal_compliance -f seeds/seed_data.sql

# 4. Validate constraints and data integrity
psql -d prequal_compliance -f validate_schema.sql
```

## Validation Results
The validation script tests:
1. Table existence (all 11 tables)
2. Primary key constraints
3. Foreign key relationships and cascade behavior
4. Unique constraints (email, project_number, assignments)
5. Not-null constraints
6. Status check constraints (recommended design)
7. Data integrity of seed data
8. Trigger functionality (`updated_at` auto-update)
9. Index presence and performance readiness
10. Analytics view correctness

## Key Design Decisions
- **UUIDs for primary keys** - Enables safe distributed data ingestion and prevents enumeration attacks
- **ON DELETE CASCADE** for child tables (certifications, violations) to maintain referential integrity
- **ON DELETE SET NULL** for violations.project_id to preserve violation audit trail when projects are archived
- **status** fields use VARCHAR with application-level enums (CHECK constraints can be added per-deployment)
- **updated_at triggers** on all major tables for audit trail
- **PostGIS** enabled for future geospatial compliance mapping
