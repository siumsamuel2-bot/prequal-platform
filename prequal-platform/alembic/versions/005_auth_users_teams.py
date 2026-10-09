"""Add users, teams, and team_members tables

Revision ID: 005_auth_users_teams
Revises: 004_data_pipeline_sync
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005_auth_users_teams'
down_revision = '004_data_pipeline_sync'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])

    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_teams_owner_id', 'teams', ['owner_id'])

    op.create_table(
        'team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_team_members_team_id', 'team_members', ['team_id'])
    op.create_index('idx_team_members_user_id', 'team_members', ['user_id'])
    op.create_index('uq_team_member', 'team_members', ['team_id', 'user_id'], unique=True)

    op.add_column('projects', sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True))
    op.create_index('idx_projects_team_id', 'projects', ['team_id'])


def downgrade() -> None:
    op.drop_index('idx_projects_team_id', table_name='projects')
    op.drop_column('projects', 'team_id')
    op.drop_index('uq_team_member', table_name='team_members')
    op.drop_index('idx_team_members_user_id', table_name='team_members')
    op.drop_index('idx_team_members_team_id', table_name='team_members')
    op.drop_table('team_members')
    op.drop_index('idx_teams_owner_id', table_name='teams')
    op.drop_table('teams')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')