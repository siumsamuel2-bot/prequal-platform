"""Add subscriptions table for billing

Revision ID: 019_add_subscriptions_table
Revises: 018_add_mfa
Create Date: 2026-06-09

Creates the subscriptions table referenced by billing.py
but never created via Alembic. Coordinates with MID-81
production data migration.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision: str = '019_add_subscriptions_table'
down_revision: Union[str, None] = '018_add_mfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('org_id', pg.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('plan', sa.String(50), server_default='starter'),
        sa.Column('status', sa.String(50), server_default='inactive'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_index('idx_subscriptions_org_id', 'subscriptions', ['org_id'])
    op.create_index('idx_subscriptions_stripe_id', 'subscriptions', ['stripe_subscription_id'])


def downgrade() -> None:
    op.drop_index('idx_subscriptions_stripe_id', table_name='subscriptions')
    op.drop_index('idx_subscriptions_org_id', table_name='subscriptions')
    op.drop_table('subscriptions')
