"""Add encrypted_ein column to subcontractors table

Revision ID: 015_encrypt_subcontractor_ein
Revises: 014_data_quality_monitoring
Create Date: 2026-06-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '015_encrypt_subcontractor_ein'
down_revision: Union[str, None] = '014_data_quality_monitoring'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subcontractors',
        sa.Column('encrypted_ein', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('subcontractors', 'encrypted_ein')