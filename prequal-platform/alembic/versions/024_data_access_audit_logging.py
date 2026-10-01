"""Add data access audit logging table for compliance

Revision ID: 024_data_access_audit_logging
Revises: 023_add_user_sessions
Create Date: 2026-06-30

Owner: Data Engineer
Description:
    Adds a dedicated data_access_audit_logs table to capture all read/write
    operations on customer data for compliance and security traceability.
    Complements the existing audit_logs table (auth-focused) with a
    domain-specific schema optimized for data access analytics.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '024_data_access_audit_logging'
down_revision: Union[str, None] = '023_add_user_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # data_access_audit_logs table
    # ------------------------------------------------------------------
    op.create_table(
        'data_access_audit_logs',
        # Primary key
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),

        # Who performed the action
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),

        # What action was performed (POST / GET / PUT / DELETE / PATCH / BULK_READ / BULK_WRITE / EXPORT / IMPORT)
        sa.Column('operation_type', sa.String(length=20), nullable=False),

        # What resource was accessed (table or entity name)
        sa.Column('resource_type', sa.String(length=100), nullable=False),

        # Specific resource identifier (row PK, comma-separated for bulk)
        sa.Column('resource_id', sa.String(length=500), nullable=True),

        # Organization scope (for multi-tenant isolation in queries)
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Request context
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),

        # Query and data payload metadata
        sa.Column('query_filter', sa.Text(), nullable=True),
        sa.Column('fields_accessed', sa.Text(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),

        # Change tracking for writes
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('before_values', postgresql.JSON, nullable=True),
        sa.Column('after_values', postgresql.JSON, nullable=True),

        # Outcome
        sa.Column('status', sa.String(length=20), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Compliance / retention
        sa.Column('compliance_tag', sa.String(length=100), nullable=True),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),

        # Foreign key to users (optional — system/API actions may have null user_id)
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='SET NULL'),
    )

    # Indexes for compliance query patterns
    op.create_index('idx_data_access_audit_user_id', 'data_access_audit_logs', ['user_id'])
    op.create_index('idx_data_access_audit_org_id', 'data_access_audit_logs', ['org_id'])
    op.create_index('idx_data_access_audit_operation', 'data_access_audit_logs', ['operation_type'])
    op.create_index('idx_data_access_audit_resource', 'data_access_audit_logs', ['resource_type'])
    op.create_index('idx_data_access_audit_resource_id', 'data_access_audit_logs', ['resource_id'])
    op.create_index('idx_data_access_audit_created_at', 'data_access_audit_logs', ['created_at'])
    op.create_index('idx_data_access_audit_status', 'data_access_audit_logs', ['status'])
    op.create_index('idx_data_access_audit_compliance_tag', 'data_access_audit_logs', ['compliance_tag'])

    # Composite indexes for common query patterns
    op.create_index('idx_data_access_audit_user_op', 'data_access_audit_logs',
                    ['user_id', 'operation_type'])
    op.create_index('idx_data_access_audit_resource_created',
                    'data_access_audit_logs', ['resource_type', 'created_at'])
    op.create_index('idx_data_access_audit_org_created',
                    'data_access_audit_logs', ['org_id', 'created_at'])
    op.create_index('idx_data_access_audit_compliance_created',
                    'data_access_audit_logs', ['compliance_tag', 'created_at'])


def downgrade() -> None:
    op.drop_table('data_access_audit_logs')
