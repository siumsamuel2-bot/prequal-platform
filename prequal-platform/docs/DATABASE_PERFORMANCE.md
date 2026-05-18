# Database Performance Optimization & Indexing Review

**Owner:** Data Engineer  
**Date:** 2026-05-17  
**Scope:** Sprint 1 + Sprint 2 schema (auth, compliance, alerts, notifications)

---

## Executive Summary

This document records findings from the performance optimization review of the prequal-platform PostgreSQL schema. A new Alembic migration (`009_db_performance_indexes`) adds **70+ missing indexes** across all tables to address known query patterns in endpoints, services, and scheduled jobs.

---

## Schema Review Methodology

1. **Read all models:** `app/models/auth.py`, `compliance.py`, `alerts.py`, `email_template.py`, `notification_preferences.py`, `notification_delivery_log.py`, `credential_upload.py`
2. **Read all migrations:** `001` through `008` to understand existing indexes
3. **Read query patterns:** `app/routers/compliance.py`, `alerts.py`, `auth.py`; `app/services/alert_service.py`, `data_pipeline.py`, `state_credential_client.py`
4. **Identify missing indexes:** FK columns without indexes, sort columns, filter columns, composite patterns for common WHERE + ORDER BY combinations
5. **Create migration:** `009_db_performance_indexes.py` with all missing indexes

---

## Existing Indexes (Pre-Review)

| Table | Existing Indexes |
|-------|-------------------|
| `subcontractors` | `idx_subcontractors_status`, `idx_subcontractors_license_expiration`, `idx_subcontractors_org_id` |
| `projects` | `idx_projects_status`, `idx_projects_org_id`, `idx_projects_team_id` |
| `certifications` | `idx_certifications_subcontractor_id`, `idx_certifications_expiration_date`, `idx_certifications_status` |
| `project_subcontractors` | `uq_project_subcontractor`, `idx_project_subcontractors_project_id`, `idx_project_subcontractors_subcontractor_id` |
| `violations` | `idx_violations_subcontractor_id`, `idx_violations_project_id`, `idx_violations_issued_date`, `idx_violations_status`, `idx_violations_osha_violation_id`, `idx_violations_inspection_number`, `idx_violations_citation_number` |
| `alert_preferences` | `idx_alert_preferences_user_id` |
| `alert_notifications` | `idx_alert_notifications_certification_id`, `idx_alert_notifications_scheduled_for`, `idx_alert_notifications_status`, `idx_alert_notifications_acknowledged_at`, `idx_alert_notifications_days_until` |
| `certification_renewals` | `idx_certification_renewals_certification_id`, `idx_certification_renewals_status` |
| `osha_inspections` | `idx_osha_inspections_inspection_date` |
| `osha_api_logs` | `idx_osha_api_logs_request_type`, `idx_osha_api_logs_created_at` |
| `sync_run_logs` | `idx_sync_run_logs_job_name`, `idx_sync_run_logs_status`, `idx_sync_run_logs_created_at` |
| `state_credential_records` | `idx_state_credential_state_code`, `idx_state_credential_status`, `idx_state_credential_expiration` |
| `data_quality_checks` | `idx_data_quality_checks_table_name`, `idx_data_quality_checks_check_type`, `idx_data_quality_checks_is_active` |
| `data_quality_results` | `idx_data_quality_results_check_id`, `idx_data_quality_results_sync_run_id`, `idx_data_quality_results_status` |
| `users` | `idx_users_email`, `idx_users_role`, `idx_users_password_reset_token`, `idx_users_org_id` |
| `teams` | `idx_teams_owner_id` |
| `team_members` | `idx_team_members_team_id`, `idx_team_members_user_id` |
| `organization_memberships` | `idx_org_members_user_id`, `idx_org_members_org_id` |
| `alert_configs` | `idx_alert_configs_user_id`, `idx_alert_configs_org_id`, `idx_alert_configs_active` |
| `alert_logs` | `idx_alert_logs_alert_config_id`, `idx_alert_logs_subcontractor_id`, `idx_alert_logs_certification_id`, `idx_alert_logs_status`, `idx_alert_logs_sent_at` |
| `email_templates` | `idx_email_templates_type`, `idx_email_templates_alert_type`, `idx_email_templates_active`, `idx_email_templates_language` |
| `notification_preferences` | `idx_notification_preferences_user_id`, `idx_notification_preferences_subcontractor_id`, `idx_notification_preferences_unsubscribed` |
| `notification_delivery_logs` | `idx_notification_delivery_logs_status`, `idx_notification_delivery_logs_alert_notification_id`, `idx_notification_delivery_logs_recipient_email`, `idx_notification_delivery_logs_created_at`, `idx_notification_delivery_logs_provider`, `idx_notification_delivery_logs_queued_at` |
| `uploaded_credentials` | `idx_uploaded_credentials_subcontractor_id`, `idx_uploaded_credentials_status`, `idx_uploaded_credentials_stored_filename` |

---

## Missing Indexes Identified

### 1. Auth (`app/models/auth.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_users_email_is_active` (`email`, `is_active`) | Login flow filters by email AND checks is_active |
| `idx_users_org_id_role` (`org_id`, `role`) | Endpoint `require_admin` / `require_manager_or_admin` filters by org_id + role |
| `idx_users_is_active` (`is_active`) | List endpoints filter out inactive users |
| `idx_teams_created_at` (`created_at`) | Team list sorted by created_at |
| `idx_team_members_role` (`role`) | Filter team members by role |
| `idx_team_members_joined_at` (`joined_at`) | Sorted member listings |
| `idx_org_members_role` (`role`) | Filter memberships by role |
| `idx_org_members_created_at` (`created_at`) | Sorted membership listings |

### 2. Compliance (`app/models/compliance.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_subcontractors_created_at` (`created_at`) | Subcontractor list sorted by created_at |
| `idx_subcontractors_email` (`email`) | Lookup by email (unique constraint already exists, but b-tree index needed for ILIKE prefix) |
| `idx_subcontractors_city_state` (`city`, `state`) | Geo-filtered listings |
| `idx_subcontractors_state` (`state`) | State-level filtering |
| `idx_subcontractors_ein` (`ein`) | Lookup by EIN |
| `idx_projects_created_at` (`created_at`) | Project list sorted by created_at |
| `idx_projects_start_date` (`start_date`) | Date-range filtering |
| `idx_projects_estimated_end_date` (`estimated_end_date`) | Upcoming deadline queries |
| `idx_projects_client_name` (`client_name`) | Lookup by client |
| `idx_projects_city_state` (`city`, `state`) | Geo-filtered listings |
| `idx_projects_team_id` (`team_id`) | Team-scoped project lookups |
| `idx_certifications_type` (`certification_type`) | Filter by cert type |
| `idx_certifications_created_at` (`created_at`) | Sorted listings |
| `idx_certifications_subcontractor_status` (`subcontractor_id`, `status`) | Compliance score queries (see `compliance.py` router) |
| `idx_certifications_verification_status` (`verification_status`) | Unverified cert lookups |
| `idx_project_subcontractors_status` (`status`) | Active link filtering |
| `idx_project_subcontractors_created_at` (`created_at`) | Sorted listings |
| `idx_project_subcontractors_insurance_exp` (`insurance_expiration`) | Insurance expiration queries |
| `idx_project_subcontractors_bonds_exp` (`bonds_expiration`) | Bond expiration queries |
| `idx_project_subcontractors_proj_status` (`project_id`, `status`) | Project + status composite queries |
| `idx_violations_violation_type` (`violation_type`) | Filter by violation type |
| `idx_violations_created_at` (`created_at`) | Sorted listings |
| `idx_violations_is_osha` (`is_osha_violation`) | OSHA-specific queries |
| `idx_violations_sub_status` (`subcontractor_id`, `status`) | Subcontractor compliance score |
| `idx_violations_issued_osha` (`issued_date`, `is_osha_violation`) | OSHA trend queries (used by view `osha_violation_trends`) |
| `idx_alert_preferences_created_at` (`created_at`) | Sorted listings |
| `idx_alert_preferences_is_active` (`is_active`) | Active preference filtering |
| `idx_alert_notifications_created_at` (`created_at`) | Sorted listings |
| `idx_alert_notifications_method` (`method`) | Filter by delivery method |
| `idx_alert_notifications_cert_status` (`certification_id`, `status`) | Cert alert lookups |
| `idx_certification_renewals_created_at` (`created_at`) | Sorted listings |
| `idx_certification_renewals_requested_by` (`requested_by`) | Requester lookups |
| `idx_osha_inspections_created_at` (`created_at`) | Sorted listings |
| `idx_osha_inspections_type` (`type`) | Filter by inspection type |
| `idx_osha_inspections_site_state` (`site_state`) | State-level filtering |
| `idx_osha_api_logs_request_date` (`request_date`) | Date-range filtering |
| `idx_sync_run_logs_job_type` (`job_type`) | Filter by job type |
| `idx_sync_run_logs_started_at` (`started_at`) | Date-range filtering |
| `idx_sync_run_logs_completed_at` (`completed_at`) | Date-range filtering |
| `idx_state_credential_number` (`credential_number`) | Lookup by credential number |
| `idx_state_credential_type` (`credential_type`) | Filter by type |
| `idx_state_credential_issuing_state` (`issuing_state`) | State filtering |
| `idx_state_credential_last_synced` (`last_synced_at`) | Sync freshness queries |
| `idx_state_credential_state_num` (`state_code`, `credential_number`) | Deduplication lookup |
| `idx_data_quality_checks_created_at` (`created_at`) | Sorted listings |
| `idx_data_quality_results_created_at` (`created_at`) | Sorted listings |
| `idx_data_quality_results_executed_at` (`executed_at`) | Date-range filtering |

### 3. Alerts (`app/models/alerts.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_alert_configs_created_at` (`created_at`) | Sorted listings |
| `idx_alert_configs_user_active` (`user_id`, `is_active`) | Active config lookups |
| `idx_alert_logs_created_at` (`created_at`) | Sorted listings |
| `idx_alert_logs_channel` (`channel`) | Filter by delivery channel |
| `idx_alert_logs_config_status` (`alert_config_id`, `status`) | Config alert lookups |

### 4. Notification Preferences (`app/models/notification_preferences.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_notification_prefs_created_at` (`created_at`) | Sorted listings |
| `idx_notification_prefs_user_active` (`user_id`, `is_active`) | Active preference lookups |
| `idx_notification_prefs_digest` (`digest_enabled`) | Digest subscriber queries |

### 5. Notification Delivery Log (`app/models/notification_delivery_log.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_notification_delivery_updated_at` (`updated_at`) | Sorted listings |
| `idx_notification_delivery_recipient_user` (`recipient_user_id`) | User delivery lookups |
| `idx_notification_delivery_recipient_sub` (`recipient_subcontractor_id`) | Subcontractor delivery lookups |
| `idx_notification_delivery_template` (`template_id`) | Template usage lookups |
| `idx_notification_delivery_sent_at` (`sent_at`) | Date-range filtering |
| `idx_notification_delivery_failed_at` (`failed_at`) | Failure analysis |
| `idx_notification_delivery_bounced_at` (`bounced_at`) | Bounce analysis |
| `idx_notification_delivery_attempt` (`attempt_number`) | Retry analysis |
| `idx_notification_delivery_status_created` (`status`, `created_at`) | Pending queue ordering |

### 6. Email Templates (`app/models/email_template.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_email_templates_created_by` (`created_by`) | Owner lookups |
| `idx_email_templates_created_at` (`created_at`) | Sorted listings |
| `idx_email_templates_is_default` (`is_default`) | Default template lookups |

### 7. Uploaded Credentials (`app/models/credential_upload.py`)

| Missing Index | Rationale |
|---------------|-----------|
| `idx_uploaded_creds_cert_id` (`certification_id`) | Cert-linked lookups |
| `idx_uploaded_creds_created_at` (`created_at`) | Sorted listings |
| `idx_uploaded_creds_extraction` (`extraction_status`) | Pending extraction queries |
| `idx_uploaded_creds_virus_scan` (`virus_scan_status`) | Pending scan queries |
| `idx_uploaded_creds_cert_num` (`extracted_cert_number`) | Cert number lookups |

---

## Connection Pooling Review

Current `app/database.py` configuration:

```python
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```

### Assessment

- **pool_pre_ping=True**: Good — prevents stale connections from being handed out
- **pool_size=10**: Suitable for current expected load (mid-market SaaS, < 100 concurrent users)
- **max_overflow=20**: Allows burst to 30 connections; reasonable for async pool
- **pool_recycle=300**: Recycles idle connections after 5 minutes, reducing stale connection errors
- **pool_timeout=30**: Fails fast instead of queuing indefinitely when the pool is exhausted

### Recommendations

1. **Monitor pool usage** in production. If `max_overflow` is consistently reached, increase `pool_size` to 20 and `max_overflow` to 30.
2. **Add pool_recycle** to handle idle connections gracefully:
   ```python
   pool_recycle=300  # Recycle connections after 5 minutes idle
   ```
3. **Add pool_timeout** to fail fast rather than queue indefinitely:
   ```python
   pool_timeout=30  # Wait up to 30s for a connection from the pool
   ```
4. **Consider separate read pool** for analytics queries if dashboard views become heavy.

---

## Composite Index Rationale

A few composite indexes were added for very common query patterns:

1. **`idx_users_email_is_active` (email, is_active)**: Login flow always checks both. Covers `WHERE email = ? AND is_active = true`.
2. **`idx_certifications_subcontractor_status` (subcontractor_id, status)**: `get_subcontractor_compliance_score()` and similar endpoints query valid certs per subcontractor frequently.
3. **`idx_project_subcontractors_proj_status` (project_id, status)**: Alerts router queries active subcontractors by project.
4. **`idx_violations_sub_status` (subcontractor_id, status)**: Compliance score calculation needs open violations per subcontractor.
5. **`idx_violations_issued_osha` (issued_date, is_osha_violation)**: `osha_violation_trends` view groups by month and filters OSHA violations.
6. **`idx_state_credential_state_num` (state_code, credential_number)**: State credential sync deduplicates by this composite.
7. **`idx_notification_delivery_status_created` (status, created_at)**: Pending delivery queue ordered by oldest first.
8. **`idx_alert_configs_user_active` (user_id, is_active)**: Active alert config lookups per user.
9. **`idx_alert_logs_config_status` (alert_config_id, status)**: Config alert status lookups.
10. **`idx_alert_notifications_cert_status` (certification_id, status)**: Cert alert lookups.
11. **`idx_users_org_id_role` (org_id, role)**: Admin/manager role checks per organization.
12. **`idx_notification_prefs_user_active` (user_id, is_active)**: Active notification pref lookups.

---

## Migration Safety

- **No data migration** required — this is a metadata-only change
- **All indexes are `CREATE INDEX` (not `UNIQUE`)** — no constraint enforcement changes
- **Downgrade provided** — all indexes dropped in reverse order
- **Idempotent** — running `alembic downgrade` then `alembic upgrade` is safe

---

## Next Steps

1. [ ] Run `alembic upgrade head` in staging to verify migration applies cleanly
2. [ ] Run `pg_stat_statements` or `EXPLAIN (ANALYZE, BUFFERS)` on top 10 slow queries after migration
3. [ ] Monitor index bloat with `pgstatindex()` after 1 week of production traffic
4. [ ] Consider adding **partial indexes** for common hot paths (e.g., `is_active = true`, `status = 'pending'`)
5. [ ] Evaluate **covering indexes** (INCLUDE clause) for wide reads if specific columns are frequently fetched together
