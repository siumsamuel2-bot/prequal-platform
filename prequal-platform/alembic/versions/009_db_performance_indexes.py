"""Database Performance Optimization & Indexing Review

Revision ID: 009_db_performance_indexes
Revises: 008_sprint2_auth_alerts_subcontractors
Create Date: 2026-05-17

Data Engineer review of Sprint 1 + Sprint 2 schema.
Adds missing indexes for FKs, lookup columns, sort columns, and common query patterns.

Owner: Data Engineer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '009_db_performance_indexes'
down_revision = '008_sprint2_orgs_alerts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. auth.py models
    # =====================================================================

    # users: add composite index for common login lookups (email + is_active)
    _safe_create_index('idx_users_email_is_active', 'users', ['email', 'is_active'])
    # users: add org_id + role composite for org-scoped admin/staff lookups
    _safe_create_index('idx_users_org_id_role', 'users', ['org_id', 'role'])
    # users: add is_active for filtering inactive accounts
    _safe_create_index('idx_users_is_active', 'users', ['is_active'])

    # teams: add created_at for sorted listings
    _safe_create_index('idx_teams_created_at', 'teams', ['created_at'])

    # team_members: add role for filtering by role
    _safe_create_index('idx_team_members_role', 'team_members', ['role'])
    # team_members: add joined_at for sorted listings
    _safe_create_index('idx_team_members_joined_at', 'team_members', ['joined_at'])

    # organization_memberships: add role for filtering
    _safe_create_index('idx_org_members_role', 'organization_memberships', ['role'])
    # organization_memberships: add created_at for sorted listings
    _safe_create_index('idx_org_members_created_at', 'organization_memberships', ['created_at'])

    # =====================================================================
    # 2. compliance.py models
    # =====================================================================

    # subcontractors: add created_at for sorted listings
    _safe_create_index('idx_subcontractors_created_at', 'subcontractors', ['created_at'])
    # subcontractors: add email for lookup by email
    _safe_create_index('idx_subcontractors_email', 'subcontractors', ['email'])
    # subcontractors: add city + state for geo-filtered listings
    _safe_create_index('idx_subcontractors_city_state', 'subcontractors', ['city', 'state'])
    # subcontractors: add state for state-level filtering
    _safe_create_index('idx_subcontractors_state', 'subcontractors', ['state'])
    # subcontractors: add ein for lookup by ein
    _safe_create_index('idx_subcontractors_ein', 'subcontractors', ['ein'])

    # projects: add created_at for sorted listings
    _safe_create_index('idx_projects_created_at', 'projects', ['created_at'])
    # projects: add start_date for date-range filtering
    _safe_create_index('idx_projects_start_date', 'projects', ['start_date'])
    # projects: add estimated_end_date for upcoming deadline queries
    _safe_create_index('idx_projects_estimated_end_date', 'projects', ['estimated_end_date'])
    # projects: add client_name for lookup by client
    _safe_create_index('idx_projects_client_name', 'projects', ['client_name'])
    # projects: add city + state for geo-filtered listings
    _safe_create_index('idx_projects_city_state', 'projects', ['city', 'state'])
    # idx_projects_team_id already created in 005_auth_users_teams.py

    # certifications: add certification_type for type filtering
    _safe_create_index('idx_certifications_type', 'certifications', ['certification_type'])
    # certifications: add created_at for sorted listings
    _safe_create_index('idx_certifications_created_at', 'certifications', ['created_at'])
    # certifications: add subcontractor_id + status composite for compliance checks
    _safe_create_index('idx_certifications_subcontractor_status', 'certifications', ['subcontractor_id', 'status'])
    # certifications: add verification_status for unverified cert lookups
    _safe_create_index('idx_certifications_verification_status', 'certifications', ['verification_status'])

    # project_subcontractors: add status for active-link filtering
    _safe_create_index('idx_project_subcontractors_status', 'project_subcontractors', ['status'])
    # project_subcontractors: add created_at for sorted listings
    _safe_create_index('idx_project_subcontractors_created_at', 'project_subcontractors', ['created_at'])
    # project_subcontractors: add insurance_expiration for upcoming expiration queries
    _safe_create_index('idx_project_subcontractors_insurance_exp', 'project_subcontractors', ['insurance_expiration'])
    # project_subcontractors: add bonds_expiration for upcoming expiration queries
    _safe_create_index('idx_project_subcontractors_bonds_exp', 'project_subcontractors', ['bonds_expiration'])
    # project_subcontractors: add composite for project + status queries
    _safe_create_index('idx_project_subcontractors_proj_status', 'project_subcontractors', ['project_id', 'status'])

    # violations: add violation_type for type filtering
    _safe_create_index('idx_violations_violation_type', 'violations', ['violation_type'])
    # violations: add created_at for sorted listings
    _safe_create_index('idx_violations_created_at', 'violations', ['created_at'])
    # violations: add is_osha_violation for OSHA-specific queries
    _safe_create_index('idx_violations_is_osha', 'violations', ['is_osha_violation'])
    # violations: add subcontractor_id + status composite
    _safe_create_index('idx_violations_sub_status', 'violations', ['subcontractor_id', 'status'])
    # violations: add issued_date + is_osha_violation composite for trend queries
    _safe_create_index('idx_violations_issued_osha', 'violations', ['issued_date', 'is_osha_violation'])

    # alert_preferences: add created_at for sorted listings
    _safe_create_index('idx_alert_preferences_created_at', 'alert_preferences', ['created_at'])
    # alert_preferences: add is_active for active-preference queries
    _safe_create_index('idx_alert_preferences_is_active', 'alert_preferences', ['is_active'])

    # alert_notifications: add created_at for sorted listings
    _safe_create_index('idx_alert_notifications_created_at', 'alert_notifications', ['created_at'])
    # alert_notifications: add method for method filtering
    _safe_create_index('idx_alert_notifications_method', 'alert_notifications', ['method'])
    # alert_notifications: add certification_id + status composite for cert alert lookups
    _safe_create_index('idx_alert_notifications_cert_status', 'alert_notifications', ['certification_id', 'status'])

    # certification_renewals: add created_at for sorted listings
    _safe_create_index('idx_certification_renewals_created_at', 'certification_renewals', ['created_at'])
    # certification_renewals: add requested_by for requester lookups
    _safe_create_index('idx_certification_renewals_requested_by', 'certification_renewals', ['requested_by'])

    # osha_inspections: add created_at for sorted listings
    _safe_create_index('idx_osha_inspections_created_at', 'osha_inspections', ['created_at'])
    # osha_inspections: add type for type filtering
    _safe_create_index('idx_osha_inspections_type', 'osha_inspections', ['type'])
    # osha_inspections: add site_state for state-level filtering
    _safe_create_index('idx_osha_inspections_site_state', 'osha_inspections', ['site_state'])

    # osha_api_logs: add request_date for date-range filtering
    _safe_create_index('idx_osha_api_logs_request_date', 'osha_api_logs', ['request_date'])

    # sync_run_logs: add job_type for type filtering
    _safe_create_index('idx_sync_run_logs_job_type', 'sync_run_logs', ['job_type'])
    # sync_run_logs: add completed_at for date-range filtering (idx_sync_run_logs_started_at already in 004)
    _safe_create_index('idx_sync_run_logs_completed_at', 'sync_run_logs', ['completed_at'])

    # state_credential_records: add credential_number for lookup
    _safe_create_index('idx_state_credential_number', 'state_credential_records', ['credential_number'])
    # state_credential_records: add credential_type for type filtering
    _safe_create_index('idx_state_credential_type', 'state_credential_records', ['credential_type'])
    # state_credential_records: add issuing_state for state filtering
    _safe_create_index('idx_state_credential_issuing_state', 'state_credential_records', ['issuing_state'])
    # state_credential_records: add last_synced_at for sync freshness queries
    _safe_create_index('idx_state_credential_last_synced', 'state_credential_records', ['last_synced_at'])
    # state_credential_records: add composite state + credential number for deduplication lookups
    _safe_create_index('idx_state_credential_state_num', 'state_credential_records', ['state_code', 'credential_number'])

    # data_quality_checks: add created_at for sorted listings
    _safe_create_index('idx_data_quality_checks_created_at', 'data_quality_checks', ['created_at'])

    # data_quality_results: add created_at for sorted listings
    _safe_create_index('idx_data_quality_results_created_at', 'data_quality_results', ['created_at'])
    # idx_data_quality_results_executed_at already created in 004_data_pipeline_sync.py

    # =====================================================================
    # 3. alerts.py models
    # =====================================================================

    # alert_configs: add created_at for sorted listings
    _safe_create_index('idx_alert_configs_created_at', 'alert_configs', ['created_at'])
    # alert_configs: add user_id + is_active composite for active config lookups
    _safe_create_index('idx_alert_configs_user_active', 'alert_configs', ['user_id', 'is_active'])

    # alert_logs: add created_at for sorted listings
    _safe_create_index('idx_alert_logs_created_at', 'alert_logs', ['created_at'])
    # alert_logs: add channel for channel filtering
    _safe_create_index('idx_alert_logs_channel', 'alert_logs', ['channel'])
    # alert_logs: add alert_config_id + status composite for config alert lookups
    _safe_create_index('idx_alert_logs_config_status', 'alert_logs', ['alert_config_id', 'status'])

    # =====================================================================
    # 4. notification_preferences.py models
    # =====================================================================

    # notification_preferences: add created_at for sorted listings
    _safe_create_index('idx_notification_prefs_created_at', 'notification_preferences', ['created_at'])
    # notification_preferences: add user_id + is_active composite
    _safe_create_index('idx_notification_prefs_user_active', 'notification_preferences', ['user_id', 'is_active'])
    # notification_preferences: add digest_enabled for digest subscriber queries
    _safe_create_index('idx_notification_prefs_digest', 'notification_preferences', ['digest_enabled'])

    # =====================================================================
    # 5. notification_delivery_log.py models (in compliance.py)
    # =====================================================================

    # notification_delivery_logs: add updated_at for sorted listings
    _safe_create_index('idx_notification_delivery_updated_at', 'notification_delivery_logs', ['updated_at'])
    # notification_delivery_logs: add recipient_user_id for user delivery lookups
    _safe_create_index('idx_notification_delivery_recipient_user', 'notification_delivery_logs', ['recipient_user_id'])
    # notification_delivery_logs: add recipient_subcontractor_id for subcontractor lookups
    _safe_create_index('idx_notification_delivery_recipient_sub', 'notification_delivery_logs', ['recipient_subcontractor_id'])
    # notification_delivery_logs: add template_id for template usage lookups
    _safe_create_index('idx_notification_delivery_template', 'notification_delivery_logs', ['template_id'])
    # notification_delivery_logs: add sent_at for date-range filtering
    _safe_create_index('idx_notification_delivery_sent_at', 'notification_delivery_logs', ['sent_at'])
    # notification_delivery_logs: add failed_at for failure analysis queries
    _safe_create_index('idx_notification_delivery_failed_at', 'notification_delivery_logs', ['failed_at'])
    # notification_delivery_logs: add bounced_at for bounce analysis queries
    _safe_create_index('idx_notification_delivery_bounced_at', 'notification_delivery_logs', ['bounced_at'])
    # notification_delivery_logs: add attempt_number for retry analysis
    _safe_create_index('idx_notification_delivery_attempt', 'notification_delivery_logs', ['attempt_number'])
    # notification_delivery_logs: composite status + created_at for pending queue ordering
    _safe_create_index('idx_notification_delivery_status_created', 'notification_delivery_logs', ['status', 'created_at'])

    # =====================================================================
    # 6. email_template.py models
    # =====================================================================

    # email_templates: add created_by for owner lookups
    _safe_create_index('idx_email_templates_created_by', 'email_templates', ['created_by'])
    # email_templates: add created_at for sorted listings
    _safe_create_index('idx_email_templates_created_at', 'email_templates', ['created_at'])
    # email_templates: add is_default for default template lookups
    _safe_create_index('idx_email_templates_is_default', 'email_templates', ['is_default'])

    # =====================================================================
    # 7. credential_upload.py models
    # =====================================================================

    # uploaded_credentials: add certification_id for cert-linked lookups
    _safe_create_index('idx_uploaded_creds_cert_id', 'uploaded_credentials', ['certification_id'])
    # uploaded_credentials: add created_at for sorted listings
    _safe_create_index('idx_uploaded_creds_created_at', 'uploaded_credentials', ['created_at'])
    # uploaded_credentials: add extraction_status for pending extraction queries
    _safe_create_index('idx_uploaded_creds_extraction', 'uploaded_credentials', ['extraction_status'])
    # uploaded_credentials: add virus_scan_status for pending scan queries
    _safe_create_index('idx_uploaded_creds_virus_scan', 'uploaded_credentials', ['virus_scan_status'])
    # uploaded_credentials: add extracted_cert_number for cert number lookups
    _safe_create_index('idx_uploaded_creds_cert_num', 'uploaded_credentials', ['extracted_cert_number'])




def _safe_create_index(name, table_name, columns, **kw):
    """Create an index only if the table and all its columns exist.

    Guards against drift between this performance-index migration and the
    schema actually produced by earlier migrations (PostgreSQL parity mode).
    Missing objects are skipped; valid indexes are still created.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table_name):
        return
    present = {c["name"] for c in insp.get_columns(table_name)}
    if all(col in present for col in columns):
        op.create_index(name, table_name, columns, **kw)
def downgrade() -> None:
    # Drop all indexes added in this migration in reverse order:

    # 7. credential_upload
    op.drop_index('idx_uploaded_creds_cert_num', table_name='uploaded_credentials')
    op.drop_index('idx_uploaded_creds_virus_scan', table_name='uploaded_credentials')
    op.drop_index('idx_uploaded_creds_extraction', table_name='uploaded_credentials')
    op.drop_index('idx_uploaded_creds_created_at', table_name='uploaded_credentials')
    op.drop_index('idx_uploaded_creds_cert_id', table_name='uploaded_credentials')

    # 6. email_template
    op.drop_index('idx_email_templates_is_default', table_name='email_templates')
    op.drop_index('idx_email_templates_created_at', table_name='email_templates')
    op.drop_index('idx_email_templates_created_by', table_name='email_templates')

    # 5. notification_delivery_log
    op.drop_index('idx_notification_delivery_status_created', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_attempt', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_bounced_at', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_failed_at', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_sent_at', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_template', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_recipient_sub', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_recipient_user', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_updated_at', table_name='notification_delivery_logs')

    # 4. notification_preferences
    op.drop_index('idx_notification_prefs_digest', table_name='notification_preferences')
    op.drop_index('idx_notification_prefs_user_active', table_name='notification_preferences')
    op.drop_index('idx_notification_prefs_created_at', table_name='notification_preferences')

    # 3. alerts
    op.drop_index('idx_alert_logs_config_status', table_name='alert_logs')
    op.drop_index('idx_alert_logs_channel', table_name='alert_logs')
    op.drop_index('idx_alert_logs_created_at', table_name='alert_logs')
    op.drop_index('idx_alert_configs_user_active', table_name='alert_configs')
    op.drop_index('idx_alert_configs_created_at', table_name='alert_configs')

    # 2. compliance
    # idx_data_quality_results_executed_at is in 004_data_pipeline_sync.py, do not drop here
    op.drop_index('idx_data_quality_results_created_at', table_name='data_quality_results')
    op.drop_index('idx_data_quality_checks_created_at', table_name='data_quality_checks')
    op.drop_index('idx_state_credential_state_num', table_name='state_credential_records')
    op.drop_index('idx_state_credential_last_synced', table_name='state_credential_records')
    op.drop_index('idx_state_credential_issuing_state', table_name='state_credential_records')
    op.drop_index('idx_state_credential_type', table_name='state_credential_records')
    op.drop_index('idx_state_credential_number', table_name='state_credential_records')
    op.drop_index('idx_sync_run_logs_completed_at', table_name='sync_run_logs')
    # idx_sync_run_logs_started_at belongs to 004, do not drop here
    op.drop_index('idx_sync_run_logs_job_type', table_name='sync_run_logs')
    op.drop_index('idx_osha_api_logs_request_date', table_name='osha_api_logs')
    op.drop_index('idx_osha_inspections_site_state', table_name='osha_inspections')
    op.drop_index('idx_osha_inspections_type', table_name='osha_inspections')
    op.drop_index('idx_osha_inspections_created_at', table_name='osha_inspections')
    op.drop_index('idx_certification_renewals_requested_by', table_name='certification_renewals')
    op.drop_index('idx_certification_renewals_created_at', table_name='certification_renewals')
    op.drop_index('idx_alert_notifications_cert_status', table_name='alert_notifications')
    op.drop_index('idx_alert_notifications_method', table_name='alert_notifications')
    op.drop_index('idx_alert_notifications_created_at', table_name='alert_notifications')
    op.drop_index('idx_alert_preferences_is_active', table_name='alert_preferences')
    op.drop_index('idx_alert_preferences_created_at', table_name='alert_preferences')
    op.drop_index('idx_violations_issued_osha', table_name='violations')
    op.drop_index('idx_violations_sub_status', table_name='violations')
    op.drop_index('idx_violations_is_osha', table_name='violations')
    op.drop_index('idx_violations_created_at', table_name='violations')
    op.drop_index('idx_violations_violation_type', table_name='violations')
    op.drop_index('idx_project_subcontractors_proj_status', table_name='project_subcontractors')
    op.drop_index('idx_project_subcontractors_bonds_exp', table_name='project_subcontractors')
    op.drop_index('idx_project_subcontractors_insurance_exp', table_name='project_subcontractors')
    op.drop_index('idx_project_subcontractors_created_at', table_name='project_subcontractors')
    op.drop_index('idx_project_subcontractors_status', table_name='project_subcontractors')
    op.drop_index('idx_certifications_verification_status', table_name='certifications')
    op.drop_index('idx_certifications_subcontractor_status', table_name='certifications')
    op.drop_index('idx_certifications_created_at', table_name='certifications')
    op.drop_index('idx_certifications_type', table_name='certifications')
    # idx_projects_team_id belongs to 005, do not drop here
    op.drop_index('idx_projects_city_state', table_name='projects')
    op.drop_index('idx_projects_client_name', table_name='projects')
    op.drop_index('idx_projects_estimated_end_date', table_name='projects')
    op.drop_index('idx_projects_start_date', table_name='projects')
    op.drop_index('idx_projects_created_at', table_name='projects')
    op.drop_index('idx_subcontractors_ein', table_name='subcontractors')
    op.drop_index('idx_subcontractors_state', table_name='subcontractors')
    op.drop_index('idx_subcontractors_city_state', table_name='subcontractors')
    op.drop_index('idx_subcontractors_email', table_name='subcontractors')
    op.drop_index('idx_subcontractors_created_at', table_name='subcontractors')

    # 1. auth
    op.drop_index('idx_org_members_created_at', table_name='organization_memberships')
    op.drop_index('idx_org_members_role', table_name='organization_memberships')
    op.drop_index('idx_team_members_joined_at', table_name='team_members')
    op.drop_index('idx_team_members_role', table_name='team_members')
    op.drop_index('idx_teams_created_at', table_name='teams')
    op.drop_index('idx_users_is_active', table_name='users')
    op.drop_index('idx_users_org_id_role', table_name='users')
    op.drop_index('idx_users_email_is_active', table_name='users')
