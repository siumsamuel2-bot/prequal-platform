"""Add email notification delivery tables

Revision ID: 006_email_notification_delivery
Revises: 005_auth_users_teams
Create Date: 2026-05-14

Tables added:
- email_templates: stores email templates for notification delivery
- notification_preferences: per-user and per-subcontractor notification preferences
- notification_delivery_logs: tracks every email delivery attempt with full audit trail

Owner: Data Engineer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_email_notification_delivery'
down_revision = '005_auth_users_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # email_templates
    op.create_table(
        'email_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_type', sa.String(50), nullable=False, server_default='alert'),
        sa.Column('alert_type', sa.String(50), nullable=True),
        sa.Column('subject_template', sa.String(500), nullable=False),
        sa.Column('html_body_template', sa.Text(), nullable=False),
        sa.Column('text_body_template', sa.Text(), nullable=True),
        sa.Column('template_variables', postgresql.JSON(), nullable=True, server_default='[]'),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('idx_email_templates_type', 'email_templates', ['template_type'])
    op.create_index('idx_email_templates_alert_type', 'email_templates', ['alert_type'])
    op.create_index('idx_email_templates_active', 'email_templates', ['is_active'])
    op.create_index('idx_email_templates_language', 'email_templates', ['language'])

    # notification_preferences
    op.create_table(
        'notification_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subcontractor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subcontractors.id', ondelete='CASCADE'), nullable=True),
        sa.Column('notify_on_cert_expiration', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_cert_expiration_days', postgresql.JSON(), server_default='[30, 14, 7]'),
        sa.Column('notify_on_violation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_renewal_request', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_renewal_approved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('in_app_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('custom_email', sa.String(255), nullable=True),
        sa.Column('custom_phone', sa.String(20), nullable=True),
        sa.Column('digest_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('digest_frequency', sa.String(50), server_default='daily'),
        sa.Column('digest_day_of_week', sa.Integer(), nullable=True),
        sa.Column('digest_hour', sa.Integer(), server_default='9'),
        sa.Column('quiet_hours_start', sa.Integer(), nullable=True),
        sa.Column('quiet_hours_end', sa.Integer(), nullable=True),
        sa.Column('quiet_hours_timezone', sa.String(50), server_default='UTC'),
        sa.Column('language', sa.String(10), server_default='en'),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribed_reason', sa.Text(), nullable=True),
        sa.Column('max_emails_per_hour', sa.Integer(), server_default='10'),
        sa.Column('max_emails_per_day', sa.Integer(), server_default='50'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('idx_notification_preferences_user_id', 'notification_preferences', ['user_id'])
    op.create_index('idx_notification_preferences_subcontractor_id', 'notification_preferences', ['subcontractor_id'])
    op.create_index('idx_notification_preferences_unsubscribed', 'notification_preferences', ['unsubscribed_at'])

    # notification_delivery_logs
    op.create_table(
        'notification_delivery_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_notification_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_notifications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_email', sa.String(255), nullable=False),
        sa.Column('recipient_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recipient_subcontractor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subcontractors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('email_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email_subject', sa.String(500), nullable=True),
        sa.Column('email_body_html', sa.Text(), nullable=True),
        sa.Column('email_body_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('provider', sa.String(100), server_default='smtp'),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bounced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_number', sa.Integer(), server_default='1'),
        sa.Column('max_attempts', sa.Integer(), server_default='3'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('bounce_reason', sa.Text(), nullable=True),
        sa.Column('bounce_code', sa.String(50), nullable=True),
        sa.Column('rate_limit_bucket', sa.String(100), nullable=True),
        sa.Column('rate_limit_window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('delivery_metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('idx_notification_delivery_logs_status', 'notification_delivery_logs', ['status'])
    op.create_index('idx_notification_delivery_logs_alert_notification_id', 'notification_delivery_logs', ['alert_notification_id'])
    op.create_index('idx_notification_delivery_logs_recipient_email', 'notification_delivery_logs', ['recipient_email'])
    op.create_index('idx_notification_delivery_logs_created_at', 'notification_delivery_logs', ['created_at'])
    op.create_index('idx_notification_delivery_logs_provider', 'notification_delivery_logs', ['provider'])
    op.create_index('idx_notification_delivery_logs_queued_at', 'notification_delivery_logs', ['queued_at'])
    op.create_index('idx_notification_delivery_logs_provider_message_id', 'notification_delivery_logs', ['provider_message_id'])


def downgrade() -> None:
    op.drop_index('idx_notification_delivery_logs_provider_message_id', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_queued_at', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_provider', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_created_at', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_recipient_email', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_alert_notification_id', table_name='notification_delivery_logs')
    op.drop_index('idx_notification_delivery_logs_status', table_name='notification_delivery_logs')
    op.drop_table('notification_delivery_logs')

    op.drop_index('idx_notification_preferences_unsubscribed', table_name='notification_preferences')
    op.drop_index('idx_notification_preferences_subcontractor_id', table_name='notification_preferences')
    op.drop_index('idx_notification_preferences_user_id', table_name='notification_preferences')
    op.drop_table('notification_preferences')

    op.drop_index('idx_email_templates_language', table_name='email_templates')
    op.drop_index('idx_email_templates_active', table_name='email_templates')
    op.drop_index('idx_email_templates_alert_type', table_name='email_templates')
    op.drop_index('idx_email_templates_type', table_name='email_templates')
    op.drop_table('email_templates')
