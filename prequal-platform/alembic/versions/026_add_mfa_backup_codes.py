"""Add mfa_backup_codes to users table

Revision ID: 026_add_mfa_backup_codes
Revises: 025_add_subcontractor_team_id
Create Date: 2026-10-03

Stores bcrypt hashes of single-use MFA recovery (backup) codes. The plaintext
codes are shown to the user exactly once at enrolment time.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '026_add_mfa_backup_codes'
down_revision: Union[str, None] = '025_add_subcontractor_team_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('mfa_backup_codes', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'mfa_backup_codes')
