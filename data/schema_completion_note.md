# PostgreSQL Schema Design: Subcontractor Compliance Tracking

**Tasks Completed**: Consolidated MID-12 (Data Model Design) and MID-14 (Contingency Schema) requirements into a unified PostgreSQL schema.

## Schema Overview

### New Tables
- **`compliance_requirements`**: MID-12 compliance standards (e.g., OSHA, insurance)
- **`insurance_policies`**: MID-12 insurance tracking
- **`subcontractor_compliance`**: Junction table linking subcontractors to requirements
- **`compliance_checks`**: MID-14 audit trail for compliance validations

### Extended Tables
- **`subcontractors`**: Added `mid_12_compliant` and `mid_14_compliant` flags
- **`certifications`**: Added `mid_requirement_number` for MID-12/MID-14 mapping
- **`violations`**: Added `mid_14_violation` flags and corrective action fields

## Key Features
- **Normalized design** with relationships and constraints
- **Sample seed data** for compliance scenarios (OSHA, insurance, violations)
- **Indexing strategy** for performance optimization
- **SQL queries** for common operations (compliance status, expired items)
- **Migration scripts** and FastAPI integration patterns

## Deliverables
- [Schema definition](data/schema.sql) (SQL/DDL)
- [Seed data](data/seed_compliance.sql) for testing
- [Queries](data/queries.sql) for common operations
- [FastAPI models](app/models/compliance.py) (Pydantic)

**Status**: Deprecated. See `database/README.md` for the authoritative schema. This note preserved for historical context only.