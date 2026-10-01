"""Add password_history to users table

Revision ID: 021_add_password_history
Revises: 020_password_changed_at
Create Date: 2026-06-09

Adds password_history column for storing previous password hashes
to prevent password reuse within the last 5 passwords.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '021_add_password_history'
down_revision: Union[str, None] = '020_password_changed_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_history', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'password_history')