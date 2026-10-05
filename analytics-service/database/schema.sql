-- Prequal Analytics Service — Database Schema
-- Created for: MID-588 — Phase 1: Extract Analytics Service from Monolith (per ADR-001 / MID-514)
-- Owner: analytics-service (database-per-service, shared-nothing)
--
-- Event schema is compatible with the monolith's analytics_events table and the
-- 07_feature_adoption_and_system_health.sql schema (MID-88).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. Analytics Events (migrated from monolith; service-owned)
-- ---------------------------------------------------------------------------
CREATE TABLE analytics_events (
    id VARCHAR(36) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(64),
    organization_id VARCHAR(64),
    event_metadata JSONB,
    source_service VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_events_type_created ON analytics_events(event_type, created_at);
CREATE INDEX idx_analytics_events_org_created ON analytics_events(organization_id, created_at);
CREATE INDEX idx_analytics_events_user_created ON analytics_events(user_id, created_at);
CREATE INDEX idx_analytics_events_created ON analytics_events(created_at DESC);

-- ---------------------------------------------------------------------------
-- 2. Feature Usage Events (from MID-88 schema)
-- ---------------------------------------------------------------------------
CREATE TABLE feature_usage_events (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(64),
    feature_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feature_events_feature_created ON feature_usage_events(feature_name, created_at);
CREATE INDEX idx_feature_events_user_created ON feature_usage_events(user_id, created_at);
CREATE INDEX idx_feature_events_created ON feature_usage_events(created_at DESC);

-- ---------------------------------------------------------------------------
-- 3. System Health Metrics (from MID-88 schema)
-- ---------------------------------------------------------------------------
CREATE TABLE system_health_metrics (
    id VARCHAR(36) PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_health_metrics_service_recorded ON system_health_metrics(service_name, recorded_at);
CREATE INDEX idx_health_metrics_metric_recorded ON system_health_metrics(service_name, metric_name, recorded_at);
CREATE INDEX idx_health_metrics_recorded ON system_health_metrics(recorded_at DESC);

-- ---------------------------------------------------------------------------
-- 4. Dashboard Configurations (service data ownership)
-- ---------------------------------------------------------------------------
CREATE TABLE dashboard_configs (
    id SERIAL PRIMARY KEY,
    organization_id VARCHAR(64),
    name VARCHAR(255) NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    created_by VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_dashboard_configs_org ON dashboard_configs(organization_id);

-- ---------------------------------------------------------------------------
-- 5. Aggregated Metrics (materialized views)
-- ---------------------------------------------------------------------------
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

CREATE UNIQUE INDEX idx_mv_feature_adoption_feature_date ON mv_feature_adoption_summary(feature_name, event_date);
CREATE INDEX idx_mv_feature_adoption_date ON mv_feature_adoption_summary(event_date DESC);

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

CREATE UNIQUE INDEX idx_mv_system_health_service_metric ON mv_system_health_summary(service_name, metric_name);

-- ---------------------------------------------------------------------------
-- 6. Data Quality Monitoring (MID-626)
-- ---------------------------------------------------------------------------
-- Internal alert records only (no external notification delivery).
-- Archive tables are insert-only; retention never deletes source rows.

CREATE TABLE IF NOT EXISTS data_quality_alerts (
    id VARCHAR(36) PRIMARY KEY,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    source_table VARCHAR(100),
    message VARCHAR(1000) NOT NULL,
    threshold_value FLOAT,
    actual_value FLOAT,
    is_acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_alerts_created ON data_quality_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_dq_alerts_type ON data_quality_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_dq_alerts_severity ON data_quality_alerts(severity);

CREATE TABLE IF NOT EXISTS analytics_events_archive (
    id VARCHAR(36) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(64),
    organization_id VARCHAR(64),
    event_metadata JSONB,
    source_service VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE,
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_usage_events_archive (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(64),
    feature_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
