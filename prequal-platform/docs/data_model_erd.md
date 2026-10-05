# Prequal Compliance Platform - Data Model ERD

**Generated:** 2026-06-09
**Author:** Data Engineer (MID-81)
**Database:** PostgreSQL 15+
**Migration Chain:** 001 → 020

---

## Entity Relationship Diagram (Text)

```
+-----------------------------------+       +-----------------------------------+
|  organizations                    |       |  users                             |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |<----->|  id (PK)                           |
|  name                             |       |  email (UQ)                        |
|  slug (UQ)                        |       |  name                              |
|  stripe_customer_id                 |       |  hashed_password                   |
|  created_at                       |       |  role                              |
|  updated_at                       |       |  is_active                         |
+-----------------------------------+       |  org_id (FK)                       |
       ^   ^                                |  mfa_secret                        |
       |   |                                |  mfa_enabled                       |
       |   |                                |  created_at                        |
       |   |                                +-----------------------------------+
       |   |
       |   +--------------------------------+
       |                                    |
       v                                    v
+-----------------------------------+  +-----------------------------------+
|  teams                            |  |  organization_memberships         |
+-----------------------------------+  +-----------------------------------+
|  id (PK)                          |  |  id (PK)                          |
|  name                             |  |  user_id (FK)                     |
|  description                      |  |  org_id (FK)                     |
|  owner_id (FK -> users)            |  |  role                             |
|  created_at                       |  |  created_at                       |
|  updated_at                       |  +-----------------------------------+
+-----------------------------------+         v   v
       ^                                      |   |
       |                                      |   v
       |                           +-----------------------------------+
       |                           |  team_members                     |
       |                           +-----------------------------------+
       |                           |  id (PK)                          |
       +---------------------------|  team_id (FK)                     |
                                   |  user_id (FK)                     |
                                   |  role                             |
                                   |  joined_at                        |
                                   +-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  subcontractors                   |       |  projects                          |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |       |  id (PK)                           |
|  company_name                     |       |  project_name                      |
|  contact_first_name               |       |  project_number (UQ)               |
|  contact_last_name                |       |  description                       |
|  email (UQ)                       |       |  client_name                       |
|  phone                            |       |  client_contact                    |
|  address_line1                    |       |  encrypted_client_name             |
|  address_line2                    |       |  encrypted_client_contact            |
|  city                             |       |  start_date                        |
|  state                            |       |  estimated_end_date                |
|  zip_code                         |       |  actual_end_date                     |
|  country                          |       |  status                             |
|  ein                              |       |  budget                             |
|  encrypted_ein                    |       |  org_id (FK)                       |
|  encrypted_contact_first_name     |       |  team_id (FK)                      |
|  encrypted_contact_last_name      |       |  created_at                         |
|  encrypted_email                  |       |  updated_at                         |
|  encrypted_phone                  |       +-----------------------------------+
|  encrypted_address_line1          |                |
|  encrypted_address_line2          |                |
|  encrypted_city                   |                v
|  encrypted_state                  |       +-----------------------------------+
|  encrypted_zip_code               |       |  project_subcontractors            |
|  license_number                   |       +-----------------------------------+
|  license_state                    |       |  id (PK)                           |
|  license_expiration               |       |  project_id (FK)                   |
|  status                           |       |  subcontractor_id (FK)             |
|  org_id (FK)                      |       |  role                              |
|  created_at                       |       |  start_date                        |
|  updated_at                       |       |  end_date                          |
+-----------------------------------+       |  status                            |
       ^   ^                                |  insurance_expiration              |
       |   |                                |  bonds_expiration                  |
       |   |                                |  created_at                        |
       |   |                                +-----------------------------------+
       |   |
       |   +--------------------------------+
       |                                    |
       v                                    v
+-----------------------------------+  +-----------------------------------+
|  certifications                    |  |  violations                        |
+-----------------------------------+  +-----------------------------------+
|  id (PK)                          |  |  id (PK)                           |
|  subcontractor_id (FK)            |  |  subcontractor_id (FK)             |
|  certification_type               |  |  project_id (FK)                   |
|  certification_number             |  |  violation_type                    |
|  issuing_authority                |  |  violation_code                    |
|  issue_date                       |  |  description                       |
|  expiration_date                    |  |  issued_by                         |
|  status                           |  |  issued_date                       |
|  document_url                     |  |  effective_date                    |
|  verification_status              |  |  resolution_date                   |
|  verified_at                      |  |  status                            |
|  verified_by                      |  |  penalty_amount                    |
|  notes                            |  |  is_criminal                       |
|  created_at                       |  |  is_osha_violation                 |
|  updated_at                       |  |  osha_violation_id                 |
+-----------------------------------+  |  citation_number                   |
       |                                |  inspection_number                 |
       |                                |  standard_cited                    |
       |                                |  initial_penalty                   |
       |                                |  final_penalty                     |
       |                                |  gravity_score                     |
       |                                |  probability_score                 |
       |                                |  risk_category                     |
       |                                |  site_city                         |
       |                                |  site_state                        |
       |                                |  naics_code                        |
       |                                |  created_at                        |
       |                                |  updated_at                        |
       |                                +-----------------------------------+
       v
+-----------------------------------+
|  alert_notifications               |
+-----------------------------------+
|  id (PK)                          |
|  certification_id (FK)              |
|  alert_type                       |
|  scheduled_for                    |
|  sent_at                          |
|  status                           |
|  method                           |
|  recipient                        |
|  subject                          |
|  body                             |
|  retry_count                      |
|  max_retries                      |
|  error_message                    |
|  acknowledged_at                  |
|  days_until_expiration              |
|  created_at                       |
|  updated_at                       |
+-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  osha_inspections                 |       |  state_credential_records          |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |       |  id (PK)                           |
|  inspection_number (UQ)           |       |  state_code                        |
|  activity_number                  |       |  credential_number               |
|  inspection_date                    |       |  credential_type                   |
|  completion_date                  |       |  issuing_state                     |
|  type                             |       |  holder_name                       |
|  scope                            |       |  holder_address                    |
|  site_city                        |       |  holder_city                       |
|  site_state                       |       |  holder_state                      |
|  site_zip_code                    |       |  holder_zip                        |
|  site_address                     |       |  issue_date                        |
|  naics_code                       |       |  expiration_date                   |
|  reported_by                      |       |  status                            |
|  owner_type                       |       |  external_source_id                |
|  safety_man_hour                  |       |  external_source_url               |
|  health_man_hour                  |       |  last_synced_at                    |
|  total_penalty                    |       |  sync_version                      |
|  abatement_completed              |       |  raw_data                          |
|  created_at                       |       |  subcontractor_id (FK)             |
|  updated_at                       |       |  source_system                     |
+-----------------------------------+       |  match_confidence                  |
                                     |       |  is_duplicate                      |
                                     |       |  created_at                        |
                                     |       |  updated_at                        |
+-----------------------------------+       +-----------------------------------+
|  osha_api_logs                     |
+-----------------------------------+
|  id (PK)                          |
|  request_type                       |
|  request_parameters                 |
|  request_date                       |
|  response_status                    |
|  response_body                      |
|  records_processed                  |
|  records_failed                     |
|  error_message                      |
|  created_at                         |
+-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  email_templates                   |      |  notification_preferences          |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |       |  id (PK)                           |
|  name (UQ)                        |       |  user_id (FK)                      |
|  description                      |       |  subcontractor_id (FK)             |
|  template_type                    |       |  notify_on_cert_expiration         |
|  alert_type                       |       |  notify_on_cert_expiration_days    |
|  subject_template                 |       |  notify_on_violation               |
|  html_body_template               |       |  notify_on_renewal_request         |
|  text_body_template               |       |  email_enabled                     |
|  template_variables               |       |  sms_enabled                       |
|  language                         |       |  in_app_enabled                    |
|  is_active                        |       |  custom_email                      |
|  is_default                       |       |  custom_phone                      |
|  version                          |       |  digest_enabled                    |
|  created_by (FK)                  |       |  digest_frequency                  |
|  created_at                       |       |  created_at                        |
|  updated_at                       |       |  updated_at                        |
+-----------------------------------+       +-----------------------------------+

+-----------------------------------+
|  notification_delivery_logs        |
+-----------------------------------+
|  id (PK)                           |
|  alert_notification_id (FK)        |
|  recipient_email                     |
|  recipient_user_id (FK)            |
|  recipient_subcontractor_id (FK)   |
|  template_id (FK)                  |
|  status                            |
|  provider                          |
|  queued_at                         |
|  sent_at                           |
|  delivered_at                      |
|  failed_at                         |
|  attempt_number                      |
|  max_attempts                      |
|  error_message                     |
|  created_at                        |
+-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  data_quality_checks               |      |  data_quality_results              |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |       |  id (PK)                           |
|  check_name (UQ)                  |       |  check_id (FK)                     |
|  table_name                       |       |  sync_run_id (FK)                  |
|  column_name                        |       |  status                            |
|  check_type                       |       |  records_checked                   |
|  check_query                      |       |  records_failed                    |
|  expected_threshold                 |       |  failure_rate                      |
|  severity                           |       |  execution_time_ms                 |
|  is_active                          |       |  sample_failures                   |
|  description                        |       |  executed_at                       |
|  created_at                         |       |  created_at                        |
|  updated_at                         |       +-----------------------------------+
+-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  sync_run_logs                     |      |  subscriptions                     |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                          |       |  id (PK)                           |
|  job_name                         |       |  org_id (FK)                       |
|  job_type                         |       |  stripe_subscription_id            |
|  status                           |       |  plan                              |
|  triggered_by                     |       |  status                            |
|  started_at                       |       |  current_period_start                |
|  completed_at                     |       |  current_period_end                |
|  records_processed                |       |  canceled_at                       |
|  records_inserted                 |       |  created_at                        |
|  records_updated                  |       |  updated_at                        |
|  records_failed                   |       +-----------------------------------+
|  error_message                    |
|  run_metadata                     |
|  created_at                         |
|  updated_at                         |
+-----------------------------------+

+-----------------------------------+
|  audit_logs                        |
+-----------------------------------+
|  id (PK)                           |
|  user_id (FK)                      |
|  action                            |
|  resource                          |
|  resource_id                       |
|  ip_address                        |
|  user_agent                        |
|  status                            |
|  details                           |
|  created_at                        |
+-----------------------------------+

+-----------------------------------+       +-----------------------------------+
|  failed_login_attempts             |      |  account_lockouts                  |
+-----------------------------------+       +-----------------------------------+
|  id (PK)                           |      |  email (PK)                        |
|  email                               |      |  locked_until                      |
|  ip_address                          |      |  reason                            |
|  attempted_at                        |      |  created_at                        |
+-----------------------------------+       +-----------------------------------+

+-----------------------------------+
|  state_compliance_sources          |
+-----------------------------------+
|  id (PK)                           |
|  state_code (UQ)                   |
|  state_name                        |
|  api_url                           |
|  api_key_env_var                     |
|  is_active                           |
|  priority                            |
|  source_type                         |
|  last_sync_at                        |
|  records_synced                      |
|  created_at                          |
|  updated_at                          |
+-----------------------------------+
```

---

## Migration Order & Coordination

### Encryption Work (MID-75) - COMPLETE
The encryption migration chain is finished and must run **before** any production data is loaded.

| Migration | Runs After | Purpose |
|-----------|-----------|---------|
| 015 | 014 | Adds `encrypted_ein` to subcontractors |
| 016 | 015 | Adds 9 encrypted PII columns to subcontractors + backfills |
| 017 | 016 | Adds 2 encrypted client columns to projects + backfills |
| 018 | 017 | Adds MFA fields to users |
| **019** | **018** | **Creates subscriptions table (MID-81)** |
| **020** | **019** | **Adds production composite indexes (MID-81)** |

### Seed Execution Order
1. Run all Alembic migrations: `alembic upgrade head`
2. Execute production seed: `python scripts/seed_production_baseline.py`
3. Validate: `pytest tests/validate_production_schema.py -v`

### Production-Ready Checklist
- [x] Schema audit complete
- [x] Encryption migrations complete (MID-75)
- [x] Subscriptions table migration created (019)
- [x] Production seed script with encrypted columns
- [x] Composite indexes for query performance (020)
- [x] Validation tests for referential integrity
- [x] ERD documentation
