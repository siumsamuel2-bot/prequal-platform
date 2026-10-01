"""Feature Adoption & System Health Analytics Schema

Revision ID: 022_feature_adoption_and_system_health
Revises: 021_add_password_history
Create Date: 2026-06-15

Data Engineer: Adds tables and materialized views for usage analytics
(feature adoption) and system health tracking.

Owner: Data Engineer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '022_feature_adoption_and_system_health'
down_revision = '021_add_password_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. feature_usage_events — raw events table
    # =====================================================================
    op.create_table(
        'feature_usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feature_name', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('event_metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Index('idx_feature_events_feature_created', 'feature_name', 'created_at'),
        sa.Index('idx_feature_events_user_created', 'user_id', 'created_at'),
    )

    # =====================================================================
    # 2. system_health_metrics — raw metrics table
    # =====================================================================
    op.create_table(
        'system_health_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('service_name', sa.String(100), nullable=False, index=True),
        sa.Column('metric_name', sa.String(100), nullable=False, index=True),
        sa.Column('metric_value', sa.Float, nullable=False),
        sa.Column('metric_unit', sa.String(50), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Index('idx_health_metrics_service_recorded', 'service_name', 'recorded_at'),
        sa.Index('idx_health_metrics_metric_recorded', 'service_name', 'metric_name', 'recorded_at'),
    )

    # =====================================================================
    # 3. mv_feature_adoption_summary — daily adoption aggregation
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_feature_adoption_summary AS
        SELECT
            feature_name,
            DATE(created_at) AS event_date,
            COUNT(*) AS total_events,
            COUNT(DISTINCT user_id) AS unique_users,
            COUNT(DISTINCT CASE WHEN event_type = 'view' THEN id END) AS view_count,
            COUNT(DISTINCT CASE WHEN event_type = 'action' THEN id END) AS action_count,
            COUNT(DISTINCT CASE WHEN event_type = 'export' THEN id END) AS export_count,
            CURRENT_TIMESTAMP AS computed_at
        FROM feature_usage_events
        WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY feature_name, DATE(created_at)
        ORDER BY event_date DESC, total_events DESC;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_feature_adoption_feature_date
        ON mv_feature_adoption_summary(feature_name, event_date);
    """)

    op.execute("""
        CREATE INDEX idx_mv_feature_adoption_date
        ON mv_feature_adoption_summary(event_date DESC);
    """)

    # =====================================================================
    # 4. mv_system_health_summary — health metrics aggregation (last 24h)
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_system_health_summary AS
        SELECT
            service_name,
            metric_name,
            metric_unit,
            AVG(metric_value) AS avg_value,
            MIN(metric_value) AS min_value,
            MAX(metric_value) AS max_value,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY metric_value) AS p95_value,
            COUNT(*) AS total_count,
            CURRENT_TIMESTAMP AS computed_at
        FROM system_health_metrics
        WHERE recorded_at >= CURRENT_DATE - INTERVAL '1 day'
        GROUP BY service_name, metric_name, metric_unit
        ORDER BY service_name, metric_name;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_system_health_service_metric
        ON mv_system_health_summary(service_name, metric_name);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_system_health_summary CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_adoption_summary CASCADE;")
    op.drop_table('system_health_metrics')
    op.drop_table('feature_usage_events')
