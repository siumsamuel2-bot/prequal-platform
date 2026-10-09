"""Sprint 2: Add Organizations, org FKs, AlertConfig, AlertLog

Revision ID: 008_sprint2_auth_alerts_subcontractors
Revises: 007_password_reset
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008_sprint2_orgs_alerts'
down_revision = '007_password_reset'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. Organizations table
    # =====================================================================
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_organizations_slug', 'organizations', ['slug'], unique=True)

    # =====================================================================
    # 2. Add org_id FK to users (nullable for existing rows)
    # =====================================================================
    op.add_column(
        'users',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('idx_users_org_id', 'users', ['org_id'])

    # =====================================================================
    # 3. Add org_id FK to projects (nullable for existing rows)
    # =====================================================================
    op.add_column(
        'projects',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('idx_projects_org_id', 'projects', ['org_id'])

    # =====================================================================
    # 4. Add org_id FK to subcontractors (nullable for existing rows)
    # =====================================================================
    op.add_column(
        'subcontractors',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('idx_subcontractors_org_id', 'subcontractors', ['org_id'])

    # =====================================================================
    # 5. OrganizationMembership table (formal many-to-many)
    #    Extends team_members pattern; supports multiple orgs per user
    # =====================================================================
    op.create_table(
        'organization_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_org_memberships_user_id', 'organization_memberships', ['user_id'])
    op.create_index('idx_org_memberships_org_id', 'organization_memberships', ['org_id'])
    op.create_index('uq_org_membership', 'organization_memberships', ['user_id', 'org_id'], unique=True)

    # =====================================================================
    # 6. AlertConfig table (notification & alert configuration per user/org)
    #    Complements AlertPreference which tracks user-level preferences.
    # =====================================================================
    op.create_table(
        'alert_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('lead_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_alert_configs_user_id', 'alert_configs', ['user_id'])
    op.create_index('idx_alert_configs_org_id', 'alert_configs', ['org_id'])

    # =====================================================================
    # 7. AlertLog table (audit trail for sent/failed alerts)
    #    Bridges alert_notifications and notification_delivery_logs
    # =====================================================================
    op.create_table(
        'alert_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_configs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subcontractor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subcontractors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('certification_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('certifications.id', ondelete='SET NULL'), nullable=True),
        sa.Column('channel', sa.String(50), nullable=False),  # email, sms, in_app
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),  # pending, sent, failed, bounced
        sa.Column('recipient', sa.String(255), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_alert_logs_alert_config_id', 'alert_logs', ['alert_config_id'])
    op.create_index('idx_alert_logs_subcontractor_id', 'alert_logs', ['subcontractor_id'])
    op.create_index('idx_alert_logs_certification_id', 'alert_logs', ['certification_id'])
    op.create_index('idx_alert_logs_status', 'alert_logs', ['status'])
    op.create_index('idx_alert_logs_sent_at', 'alert_logs', ['sent_at'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('idx_alert_logs_sent_at', table_name='alert_logs')
    op.drop_index('idx_alert_logs_status', table_name='alert_logs')
    op.drop_index('idx_alert_logs_certification_id', table_name='alert_logs')
    op.drop_index('idx_alert_logs_subcontractor_id', table_name='alert_logs')
    op.drop_index('idx_alert_logs_alert_config_id', table_name='alert_logs')
    op.drop_table('alert_logs')

    op.drop_index('idx_alert_configs_org_id', table_name='alert_configs')
    op.drop_index('idx_alert_configs_user_id', table_name='alert_configs')
    op.drop_table('alert_configs')

    op.drop_index('uq_org_membership', table_name='organization_memberships')
    op.drop_index('idx_org_memberships_org_id', table_name='organization_memberships')
    op.drop_index('idx_org_memberships_user_id', table_name='organization_memberships')
    op.drop_table('organization_memberships')

    op.drop_index('idx_subcontractors_org_id', table_name='subcontractors')
    op.drop_column('subcontractors', 'org_id')

    op.drop_index('idx_projects_org_id', table_name='projects')
    op.drop_column('projects', 'org_id')

    op.drop_index('idx_users_org_id', table_name='users')
    op.drop_column('users', 'org_id')

    op.drop_index('idx_organizations_slug', table_name='organizations')
    op.drop_table('organizations')
