# Database Performance Review

## Sprint 1 + Sprint 2 Indexing Audit

### Summary
- **Total Existing Indexes (before this migration)**: ~50+ across all tables
- **Migration 009 Adds**: 78 new indexes
- **Tables Covered**: 20 tables across auth, compliance, alerts, and notification models

### Connection Pooling Review

**Current Configuration (app/database.py)**:
```python
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "300")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
)
```

**Environment Variables Added (2026-05-18)**:
| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | 10 | Permanent connections in pool |
| `DB_MAX_OVERFLOW` | 20 | Extra connections for burst traffic |
| `DB_POOL_RECYCLE` | 300 | Max connection age in seconds before recycle |
| `DB_POOL_TIMEOUT` | 30 | Max seconds to wait for a connection |

**Assessment**:
- `pool_size=10` is reasonable for a single-worker FastAPI app, but since the app runs with Uvicorn workers, each worker creates its own pool.
- If running 4 workers, that's up to 40 permanent connections.
- `max_overflow=20` allows burst handling but can exhaust PostgreSQL `max_connections` if too many workers spawn.
- Environment variables allow adjusting pool tuning per environment without code changes.

**Recommendations**:
1. `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` are now environment variables (done)
2. In production, set `DB_POOL_RECYCLE=180` to avoid stale connections in long-running containers
3. In production, consider reducing `DB_MAX_OVERFLOW=10` to limit connection spikes during traffic bursts
4. Monitor `pg_stat_activity` to confirm actual pool utilization

### New Indexes Added (Migration 009)

#### Auth Tables (users, teams, team_members, organization_memberships)
| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| users | idx_users_email_is_active | email, is_active | Login + active check |
| users | idx_users_org_id_role | org_id, role | Org-scoped role filtering |
| users | idx_users_is_active | is_active | Exclude inactive accounts |
| teams | idx_teams_created_at | created_at | Sorted listings |
| team_members | idx_team_members_role | role | Role-based filtering |
| team_members | idx_team_members_joined_at | joined_at | Sorted listings |
| organization_memberships | idx_org_members_role | role | Role filtering |
| organization_memberships | idx_org_members_created_at | created_at | Sorted listings |

#### Compliance Tables
| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| subcontractors | idx_subcontractors_created_at | created_at | Sorted listings |
| subcontractors | idx_subcontractors_email | email | Email lookup |
| subcontractors | idx_subcontractors_city_state | city, state | Geo-filtered listings |
| subcontractors | idx_subcontractors_state | state | State-level filtering |
| subcontractors | idx_subcontractors_ein | ein | EIN lookup |
| projects | idx_projects_created_at | created_at | Sorted listings |
| projects | idx_projects_start_date | start_date | Date-range filtering |
| projects | idx_projects_estimated_end_date | estimated_end_date | Deadline queries |
| projects | idx_projects_client_name | client_name | Client lookup |
| projects | idx_projects_city_state | city, state | Geo-filtered listings |
| projects | idx_projects_team_id | team_id | Team-scoped lookups |
| certifications | idx_certifications_type | certification_type | Type filtering |
| certifications | idx_certifications_created_at | created_at | Sorted listings |
| certifications | idx_certifications_subcontractor_status | subcontractor_id, status | Compliance checks |
| certifications | idx_certifications_verification_status | verification_status | Unverified cert lookups |
| project_subcontractors | idx_project_subcontractors_status | status | Active-link filtering |
| project_subcontractors | idx_project_subcontractors_created_at | created_at | Sorted listings |
| project_subcontractors | idx_project_subcontractors_insurance_exp | insurance_expiration | Upcoming expiration queries |
| project_subcontractors | idx_project_subcontractors_bonds_exp | bonds_expiration | Upcoming expiration queries |
| project_subcontractors | idx_project_subcontractors_proj_status | project_id, status | Project + status queries |
| violations | idx_violations_violation_type | violation_type | Type filtering |
| violations | idx_violations_created_at | created_at | Sorted listings |
| violations | idx_violations_is_osha | is_osha_violation | OSHA-specific queries |
| violations | idx_violations_sub_status | subcontractor_id, status | Compliance lookups |
| violations | idx_violations_issued_osha | issued_date, is_osha_violation | Trend analysis |
| alert_preferences | idx_alert_preferences_created_at | created_at | Sorted listings |
| alert_preferences | idx_alert_preferences_is_active | is_active | Active-preference queries |
| alert_notifications | idx_alert_notifications_created_at | created_at | Sorted listings |
| alert_notifications | idx_alert_notifications_method | method | Method filtering |
| alert_notifications | idx_alert_notifications_cert_status | certification_id, status | Cert alert lookups |
| certification_renewals | idx_certification_renewals_created_at | created_at | Sorted listings |
| certification_renewals | idx_certification_renewals_requested_by | requested_by | Requester lookups |
| osha_inspections | idx_osha_inspections_created_at | created_at | Sorted listings |
| osha_inspections | idx_osha_inspections_type | type | Type filtering |
| osha_inspections | idx_osha_inspections_site_state | site_state | State-level filtering |
| osha_api_logs | idx_osha_api_logs_request_date | request_date | Date-range filtering |
| sync_run_logs | idx_sync_run_logs_job_type | job_type | Type filtering |
| sync_run_logs | idx_sync_run_logs_started_at | started_at | Date-range filtering |
| sync_run_logs | idx_sync_run_logs_completed_at | completed_at | Date-range filtering |
| state_credential_records | idx_state_credential_number | credential_number | Lookup |
| state_credential_records | idx_state_credential_type | credential_type | Type filtering |
| state_credential_records | idx_state_credential_issuing_state | issuing_state | State filtering |
| state_credential_records | idx_state_credential_last_synced | last_synced_at | Sync freshness queries |
| state_credential_records | idx_state_credential_state_num | state_code, credential_number | Deduplication lookups |
| data_quality_checks | idx_data_quality_checks_created_at | created_at | Sorted listings |
| data_quality_results | idx_data_quality_results_created_at | created_at | Sorted listings |
| data_quality_results | idx_data_quality_results_executed_at | executed_at | Date-range filtering |

#### Alert Tables (Sprint 2)
| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| alert_configs | idx_alert_configs_created_at | created_at | Sorted listings |
| alert_configs | idx_alert_configs_user_active | user_id, is_active | Active config lookups |
| alert_logs | idx_alert_logs_created_at | created_at | Sorted listings |
| alert_logs | idx_alert_logs_channel | channel | Channel filtering |
| alert_logs | idx_alert_logs_config_status | alert_config_id, status | Config alert lookups |

#### Notification & Email Tables
| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| notification_preferences | idx_notification_prefs_created_at | created_at | Sorted listings |
| notification_preferences | idx_notification_prefs_user_active | user_id, is_active | Active preference lookups |
| notification_preferences | idx_notification_prefs_digest | digest_enabled | Digest subscriber queries |
| notification_delivery_logs | idx_notification_delivery_updated_at | updated_at | Sorted listings |
| notification_delivery_logs | idx_notification_delivery_recipient_user | recipient_user_id | User delivery lookups |
| notification_delivery_logs | idx_notification_delivery_recipient_sub | recipient_subcontractor_id | Subcontractor lookups |
| notification_delivery_logs | idx_notification_delivery_template | template_id | Template usage lookups |
| notification_delivery_logs | idx_notification_delivery_sent_at | sent_at | Date-range filtering |
| notification_delivery_logs | idx_notification_delivery_failed_at | failed_at | Failure analysis |
| notification_delivery_logs | idx_notification_delivery_bounced_at | bounced_at | Bounce analysis |
| notification_delivery_logs | idx_notification_delivery_attempt | attempt_number | Retry analysis |
| notification_delivery_logs | idx_notification_delivery_status_created | status, created_at | Pending queue ordering |
| email_templates | idx_email_templates_created_by | created_by | Owner lookups |
| email_templates | idx_email_templates_created_at | created_at | Sorted listings |
| email_templates | idx_email_templates_is_default | is_default | Default template lookups |

#### Credential Upload Tables
| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| uploaded_credentials | idx_uploaded_creds_cert_id | certification_id | Cert-linked lookups |
| uploaded_credentials | idx_uploaded_creds_created_at | created_at | Sorted listings |
| uploaded_credentials | idx_uploaded_creds_extraction | extraction_status | Pending extraction queries |
| uploaded_credentials | idx_uploaded_creds_virus_scan | virus_scan_status | Pending scan queries |
| uploaded_credentials | idx_uploaded_creds_cert_num | extracted_cert_number | Cert number lookups |

### Query Optimization Recommendations

1. **Expiration Queries (Certifications, Insurance, Bonds)**
   - All expiration date columns now have indexes
   - Use `expiration_date >= NOW() AND expiration_date <= NOW() + INTERVAL '30 days'` for upcoming alerts
   - Consider BRIN index on expiration_date if data is append-only and time-ordered

2. **Compliance Dashboard Queries**
   - The composite `idx_certifications_subcontractor_status` speeds up compliance check queries
   - The composite `idx_violations_sub_status` speeds up violation status lookups
   - Consider a materialized view for compliance dashboard (already exists: `mv_compliance_summary`)

3. **OSHA ETL Pipeline**
   - `idx_violations_issued_osha` supports trend analysis queries
   - `idx_violations_osha_violation_id` supports upsert deduplication
   - The data pipeline does raw SQL upserts; the indexes will help UPDATE WHERE lookups

4. **Notification Delivery Pipeline**
   - `idx_notification_delivery_status_created` optimizes the pending queue worker
   - `idx_notification_delivery_recipient_user` optimizes per-user delivery history
   - The `attempt_number` index supports retry analysis and backpressure monitoring

5. **State Credential Sync**
   - The composite `idx_state_credential_state_num` is critical for deduplication during sync
   - `idx_state_credential_last_synced` supports sync freshness queries

### Index Maintenance Notes
- All new indexes are B-tree (default) — appropriate for equality and range lookups
- Monitor index bloat periodically: `SELECT * FROM pg_stat_user_indexes;`
- Consider REINDEX after large data pipeline runs if bloat becomes significant
- For analytics queries (rarely used), consider `pg_stat_statements` to confirm index usage

### Files Changed
- `alembic/versions/009_db_performance_indexes.py` — new migration with 78 indexes and full downgrade
- `app/database.py` — connection pool settings now read from environment variables (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT`)
