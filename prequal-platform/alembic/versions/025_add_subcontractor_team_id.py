"""Add team_id to subcontractors table for multi-tenant isolation

Revision ID: 025_add_subcontractor_team_id
Revises: 024_data_access_audit_logging
Create Date: 2026-07-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '025_add_subcontractor_team_id'
down_revision: Union[str, None] = '024_data_access_audit_logging'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subcontractors',
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index(
        'idx_subcontractors_team_id',
        'subcontractors',
        ['team_id'],
        unique=False
    )
    op.create_foreign_key(
        'fk_subcontractors_team_id',
        'subcontractors',
        'teams',
        ['team_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_subcontractors_team_id', 'subcontractors', type_='foreignkey')
    op.drop_index('idx_subcontractors_team_id', table_name='subcontractors')
    op.drop_column('subcontractors', 'team_id')