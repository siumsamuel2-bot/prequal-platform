"""Add password reset fields to users

Revision ID: 007_password_reset
Revises: 006_email_notification_delivery
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '007_password_reset'
down_revision = '006_email_notification_delivery'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True))
    op.create_index('idx_users_password_reset_token', 'users', ['password_reset_token'])


def downgrade() -> None:
    op.drop_index('idx_users_password_reset_token', table_name='users')
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')