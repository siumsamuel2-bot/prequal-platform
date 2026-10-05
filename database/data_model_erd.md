# Prequal Database - Entity Relationship Diagram

**Database:** PostgreSQL 15+  
**Purpose:** Production-ready data model for subcontractor compliance tracking  
**Last Updated:** 2026-06-10  
**Ticket:** [MID-81](/MID/issues/MID-81)

---

## Entities and Relationships

```
+---------------------------------------+
| users                                 |
+---------------------------------------+
| id (PK)                               |
| email (UQ)                            |
| hashed_password                       |
| first_name                            |
| last_name                             |
| is_active                             |
| is_superuser                          |
| created_at                            |
| updated_at                            |
+---------------------------------------+
        |
        | 1:N (verified_by)
        v
+---------------------------------------+       +---------------------------------------+
| organizations                         |       | teams                                 |
+---------------------------------------+       +---------------------------------------+
| id (PK)                               |       | id (PK)                               |
| name                                  |       | name                                  |
| slug (UQ)                             |       | org_id (FK -> organizations.id)       |
| created_at                            |       | created_at                            |
| updated_at                            |       | updated_at                            |
+---------------------------------------+       +---------------------------------------+
        ^                                                 ^
        |                                                 |
        |  N:1 (org_id)                                   | N:1 (org_id)
        v                                                 v
+---------------------------------------+       +---------------------------------------+
| subcontractors                        |       | projects                              |
+---------------------------------------+       +---------------------------------------+
| id (PK)                               |       | id (PK)                               |
| company_name                          |       | project_name                          |
| contact_first_name                    |       | project_number (UQ)                   |
| contact_last_name                     |       | description                             |
| email (UQ)                            |       | client_name                             |
| phone                                 |       | client_contact                        |
| address_line1                         |       | start_date                            |
| address_line2                         |       | estimated_end_date                    |
| city                                  |       | actual_end_date                       |
| state                                 |       | address_line1                         |
| zip_code                              |       | ...                                   |
| ein                                   |       | status                                |
| encrypted_ein                         |       | budget                                |
| encrypted_contact_first_name          |       | created_at                            |
| encrypted_contact_last_name           |       | updated_at                            |
| ... (10 encrypted PII cols)           |       +---------------------------------------+
| license_number                        |                |
| license_state                         |                |
| license_expiration                    |                v
| status                                |       +---------------------------------------+
| org_id (FK)                           |       | project_subcontractors                |
| created_at                            |       +---------------------------------------+
| updated_at                            |       | id (PK)                               |
+---------------------------------------+       | project_id (FK -> projects.id)        |
        ^   ^                                   | subcontractor_id (FK -> subcontractors)|
        |   |                                   | role                                  |
        |   |                                   | start_date                            |
        |   |                                   | end_date                              |
        |   |                                   | status                                |
        |   |                                   | insurance_expiration                  |
        |   |                                   | bonds_expiration                      |
        |   |                                   | created_at                            |
        |   |                                   | updated_at                            |
        |   |                                   +---------------------------------------+
        |   |
        |   +--------------------------------+
        |                                    |
        v                                    v
+-----------------------------------+  +-----------------------------------+
| certifications                    |  | violations                        |
+-----------------------------------+  +-----------------------------------+
| id (PK)                           |  | id (PK)                           |
| subcontractor_id (FK)             |  | subcontractor_id (FK)             |
| certification_type                |  | project_id (FK, nullable)         |
| certification_number              |  | violation_type                    |
| issuing_authority                   |  | violation_code                    |
| issue_date                        |  | description                       |
| expiration_date                     |  | issued_by                         |
| status                            |  | issued_date                       |
| document_url                      |  | effective_date                    |
| verification_status               |  | resolution_date                   |
| verified_at                       |  | status                            |
| verified_by (FK -> users.id)      |  | penalty_amount                    |
| notes                             |  | is_criminal                       |
| created_at                        |  | is_osha_violation                 |
| updated_at                        |  | osha_violation_id                 |
+-----------------------------------+  | citation_number                   |
        |                              | inspection_number                 |
        | 1:1 FK                       | standard_cited                    |
        v                              | initial_penalty                   |
+-----------------------------------+  | final_penalty                     |
| alert_notifications               |  | gravity_score                     |
+-----------------------------------+  | probability_score                 |
| id (PK)                           |  | risk_category                     |
| certification_id (FK)               |  | site_city                         |
| alert_type                        |  | site_state                        |
| scheduled_for                     |  | naics_code                        |
| sent_at                           |  | created_at                        |
| status                            |  | updated_at                        |
| method                            |  +-----------------------------------+
| recipient                         |
| subject                           |
| body                              |
| retry_count                       |
| max_retries                       |
| created_at                        |
| updated_at                        |
+-----------------------------------+
```

## Data Quality & Monitoring Tables

```
+---------------------------+   +---------------------------+   +---------------------------+
| sync_health               |   | sync_run_logs             |   | data_quality_checks       |
+---------------------------+   +---------------------------+   +---------------------------+
| id (PK)                   |   | id (PK)                   |   | id (PK)                   |
| source_name               |   | job_name                  |   | check_name (UQ)           |
| source_type               |   | job_type                  |   | check_type                |
| sync_run_log_id (FK)      |   | status                    |   | table_name                |
| health_status             |   | triggered_by              |   | column_name               |
| last_successful_sync_at   |   | started_at                |   | description                 |
| last_failed_sync_at       |   | completed_at              |   | check_query                 |
| ...                       |   | records_processed         |   | expected_result             |
+---------------------------+   | ...                       |   | alert_threshold           |
                                +---------------------------+   | is_active                   |
                                |                               | priority                    |
+---------------------------+   v                               | created_at                  |
| match_rate_tracking       |   +---------------------------+   | updated_at                  |
+---------------------------+   | pipeline_performance      |   +---------------------------+
| id (PK)                   |   +---------------------------+
| source_name               |   | id (PK)                   |
| match_date                |   | pipeline_name             |
| source_records_total      |   | run_id                    |
| matched_records           |   | run_start_at              |
| unmatched_records         |   | run_end_at                |
| match_rate_percent        |   | duration_ms               |
| fuzzy_match_percent       |   | records_processed         |
| match_confidence_avg      |   | ...                       |
+---------------------------+   +---------------------------+
```

## State & External Data Tables

```
+---------------------------------------+   +---------------------------------------+
| state_credential_records              |   | external_data_freshness               |
+---------------------------------------+   +---------------------------------------+
| id (PK)                               |   | id (PK)                               |
| state_code                            |   | source_name (UQ with source_type)     |
| credential_number                     |   | source_type                           |
| credential_type                       |   | last_updated                          |
| issuing_state                         |   | next_scheduled_update                 |
| holder_name                           |   | update_frequency                      |
| ...                                   |   | status                                |
| subcontractor_id (FK, nullable)       |   | last_run_log_id (FK)                  |
| last_synced_at                        |   | error_count                           |
| raw_data (JSONB)                      |   | created_at                            |
| created_at                            |   | updated_at                            |
| updated_at                            |   +---------------------------------------+
+---------------------------------------+
```

## Relationships Summary

| Parent Table         | Child Table             | Relationship    | On Delete  |
|----------------------|-------------------------|-----------------|------------|
| users                | certifications          | 1:N (verified_by) | SET NULL   |
| users                | alert_preferences       | 1:N (user_id)     | CASCADE    |
| subcontractors       | certifications          | 1:N               | CASCADE    |
| subcontractors       | violations              | 1:N               | CASCADE    |
| subcontractors       | project_subcontractors  | 1:N               | CASCADE    |
| projects             | project_subcontractors  | 1:N               | CASCADE    |
| projects             | violations (project_id) | 1:N               | SET NULL   |
| certifications       | alert_notifications     | 1:N               | CASCADE    |
| certifications       | certification_renewals    | 1:N               | CASCADE    |
| organizations        | subcontractors          | 1:N (org_id)      | SET NULL   |
| organizations        | projects                | 1:N (org_id)      | SET NULL   |
| sync_run_logs        | sync_health             | 1:1 (FK)          | SET NULL   |
| sync_run_logs        | external_data_freshness   | 1:1 (FK)          | SET NULL   |

## Indexes for Production Query Performance

| Index Name                                      | Columns                                    | Purpose                                 |
|-------------------------------------------------|-------------------------------------------|-----------------------------------------|
| idx_subcontractors_status                       | status                                    | Filter active/inactive subs             |
| idx_subcontractors_license_expiration            | license_expiration                        | Compliance dashboard expiry alerts        |
| idx_certifications_subcontractor_id             | subcontractor_id                          | Sub compliance detail lookup            |
| idx_certifications_expiration_date              | expiration_date                           | Expiration report generation            |
| idx_violations_subcontractor_id                 | subcontractor_id                          | Sub violation history lookup            |
| idx_violations_status                           | status                                    | Open violation filtering              |
| idx_certifications_subcontractor_status_expiration | subcontractor_id, status, expiration_date | Composite: compliance lookup          |
| idx_violations_subcontractor_status_issued_date  | subcontractor_id, status, issued_date     | Composite: violation history            |
| idx_violations_status_is_osha                   | status, is_osha_violation WHERE is_osha   | OSHA-only queries                       |

## Data Model Design Notes

1. **Encrypted Columns (MID-75)**: Subcontractor PII is stored in both plaintext (legacy) and `encrypted_*` variants for migration. Production queries should read encrypted columns via the application layer.

2. **Archive, Never Delete**: Records older than retention policies are *flagged* and copied to `archived_records`, never removed from source tables.

3. **Sync Health Baseline**: Every external data source (OSHA API, state credentials) has a corresponding `sync_health` row for monitoring.

4. **State Credentials**: Raw state board data is stored in `state_credential_records` with a soft link to internal `subcontractors` via `subcontractor_id` (nullable until matching is complete).