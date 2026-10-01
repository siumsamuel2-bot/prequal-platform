"""Add MFA fields to users table

Revision ID: 018_add_mfa
Revises: 017_encrypt_client_data
Create Date: 2026-06-09

Adds columns for multi-factor authentication:
- mfa_secret: TOTP secret (encrypted)
- mfa_enabled: Whether MFA is active
- mfa_method: MFA method (totp, sms, etc.)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '018_add_mfa'
down_revision: Union[str, None] = '017_encrypt_client_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('mfa_secret', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'users',
        sa.Column('mfa_method', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'mfa_method')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret')