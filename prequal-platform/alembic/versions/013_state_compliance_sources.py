"""Add state compliance sources table

Revision ID: 013_state_compliance_sources
Revises: 012_security_audit_lockout
Create Date: 2026-06-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '013_state_compliance_sources'
down_revision: Union[str, None] = '012_security_audit_lockout'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'state_compliance_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('state_code', sa.String(length=2), nullable=False),
        sa.Column('state_name', sa.String(length=100), nullable=False),
        sa.Column('api_url', sa.String(length=500), nullable=True),
        sa.Column('api_key_env_var', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='license_board'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_synced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_state_sources_state_code', 'state_compliance_sources', ['state_code'], unique=True)
    op.create_index('idx_state_sources_active', 'state_compliance_sources', ['is_active'])


def downgrade() -> None:
    op.drop_index('idx_state_sources_active', table_name='state_compliance_sources')
    op.drop_index('idx_state_sources_state_code', table_name='state_compliance_sources')
    op.drop_table('state_compliance_sources')