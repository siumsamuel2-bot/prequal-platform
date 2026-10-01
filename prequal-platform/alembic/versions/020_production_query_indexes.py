"""Add production query performance indexes

Revision ID: 020_production_query_indexes
Revises: 019_add_subscriptions_table
Create Date: 2026-06-09

Adds composite indexes for common production query patterns
identified during MID-81 schema audit. These patterns include
org-scoped listings, certification expiration dashboards,
OSHA compliance checks, and alert processing queues.

Owner: Data Engineer
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '020_production_query_indexes'
down_revision: Union[str, None] = '019_add_subscriptions_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. subcontractors: org-scoped active listing
    # ------------------------------------------------------------------
    op.create_index(
        'idx_subcontractors_org_status',
        'subcontractors',
        ['org_id', 'status']
    )
    # subcontractors: license expiration by state
    op.create_index(
        'idx_subcontractors_license_state_exp',
        'subcontractors',
        ['license_state', 'license_expiration']
    )
    # subcontractors: city-state for geo dashboards
    op.drop_index('idx_subcontractors_city_state', table_name='subcontractors')
    op.create_index(
        'idx_subcontractors_state_city',
        'subcontractors',
        ['state', 'city']
    )

    # ------------------------------------------------------------------
    # 2. projects: org-scoped active project dashboard
    # ------------------------------------------------------------------
    op.create_index(
        'idx_projects_org_status_start',
        'projects',
        ['org_id', 'status', 'start_date']
    )

    # ------------------------------------------------------------------
    # 3. certifications: expiration dashboard
    # ------------------------------------------------------------------
    op.create_index(
        'idx_certifications_sub_exp_status',
        'certifications',
        ['subcontractor_id', 'expiration_date', 'status']
    )

    # ------------------------------------------------------------------
    # 4. violations: OSHA compliance checks
    # ------------------------------------------------------------------
    op.create_index(
        'idx_violations_sub_is_osha_status',
        'violations',
        ['subcontractor_id', 'is_osha_violation', 'status']
    )

    # ------------------------------------------------------------------
    # 5. alert_notifications: pending alert processing queue
    # ------------------------------------------------------------------
    op.create_index(
        'idx_alert_notifications_status_scheduled',
        'alert_notifications',
        ['status', 'scheduled_for']
    )

    # ------------------------------------------------------------------
    # 6. users: org user management
    # ------------------------------------------------------------------
    op.create_index(
        'idx_users_org_active_role',
        'users',
        ['org_id', 'is_active', 'role']
    )

    # ------------------------------------------------------------------
    # 7. sync_run_logs: job history filtering
    # ------------------------------------------------------------------
    op.create_index(
        'idx_sync_run_logs_job_started',
        'sync_run_logs',
        ['job_name', 'started_at']
    )

    # ------------------------------------------------------------------
    # 8. notification_delivery_logs: pending delivery queue
    # ------------------------------------------------------------------
    op.create_index(
        'idx_notification_delivery_status_created',
        'notification_delivery_logs',
        ['status', 'created_at']
    )

    # ------------------------------------------------------------------
    # 9. state_credential_records: subcontractor credential lookup
    # ------------------------------------------------------------------
    op.create_index(
        'idx_state_credential_sub_type',
        'state_credential_records',
        ['subcontractor_id', 'credential_type']
    )

    # ------------------------------------------------------------------
    # 10. project_subcontractors: active assignment lookups
    # ------------------------------------------------------------------
    op.create_index(
        'idx_project_subcontractors_status_proj',
        'project_subcontractors',
        ['status', 'project_id']
    )
    op.create_index(
        'idx_project_subcontractors_status_sub',
        'project_subcontractors',
        ['status', 'subcontractor_id']
    )


def downgrade() -> None:
    # Reverse order
    op.drop_index('idx_project_subcontractors_status_sub', table_name='project_subcontractors')
    op.drop_index('idx_project_subcontractors_status_proj', table_name='project_subcontractors')
    op.drop_index('idx_state_credential_sub_type', table_name='state_credential_records')
    op.drop_index('idx_notification_delivery_status_created', table_name='notification_delivery_logs')
    op.drop_index('idx_sync_run_logs_job_started', table_name='sync_run_logs')
    op.drop_index('idx_users_org_active_role', table_name='users')
    op.drop_index('idx_alert_notifications_status_scheduled', table_name='alert_notifications')
    op.drop_index('idx_violations_sub_is_osha_status', table_name='violations')
    op.drop_index('idx_certifications_sub_exp_status', table_name='certifications')
    op.drop_index('idx_projects_org_status_start', table_name='projects')
    op.drop_index('idx_subcontractors_state_city', table_name='subcontractors')
    op.create_index('idx_subcontractors_city_state', 'subcontractors', ['city', 'state'])
    op.drop_index('idx_subcontractors_license_state_exp', table_name='subcontractors')
    op.drop_index('idx_subcontractors_org_status', table_name='subcontractors')
