"""Add password_changed_at to users table

Revision ID: 020_password_changed_at
Revises: 019_add_subscriptions_table
Create Date: 2026-06-09

Adds password_changed_at column for session invalidation on password change.
When a user changes their password, all existing tokens become invalid.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '020_password_changed_at'
down_revision: Union[str, None] = '019_add_subscriptions_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('NOW()'))
    )


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')