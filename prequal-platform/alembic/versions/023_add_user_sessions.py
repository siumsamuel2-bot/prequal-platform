"""Add user_sessions table for secure session management

Revision ID: 023_add_user_sessions
Revises: 022_feature_adoption_and_system_health
Create Date: 2026-06-26

Security Engineer: Adds server-side session tracking with short expiry
and rotation on each request.

Owner: Security Engineer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '023_add_user_sessions'
down_revision = '022_feature_adoption_and_system_health'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('jti', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('rotated_from_jti', sa.String(255), nullable=True, index=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Index('idx_user_sessions_user_id', 'user_id'),
        sa.Index('idx_user_sessions_jti', 'jti', unique=True),
        sa.Index('idx_user_sessions_active_user_id', 'user_id', 'active'),
        sa.Index('idx_user_sessions_expires_at', 'expires_at'),
    )


def downgrade():
    op.drop_table('user_sessions')
