-- Feature Adoption & System Health Analytics Schema
-- Created for: MID-88 — Usage Analytics Pipeline (Feature Adoption & System Health Tracking)
-- Owner: Data Engineer

-- ---------------------------------------------------------------------------
-- 1. Raw Events Table for Feature Adoption
-- ---------------------------------------------------------------------------
CREATE TABLE feature_usage_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,                                              -- optional, references users(id) if available
    feature_name VARCHAR(100) NOT NULL,                      -- e.g., 'compliance_dashboard', 'certification_upload'
    event_type VARCHAR(50) NOT NULL,                         -- 'view', 'action', 'export'
    event_metadata JSONB,                                      -- flexible context (page, button, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feature_events_feature_created ON feature_usage_events(feature_name, created_at);
CREATE INDEX idx_feature_events_user_created ON feature_usage_events(user_id, created_at);
CREATE INDEX idx_feature_events_created ON feature_usage_events(created_at DESC);

-- ---------------------------------------------------------------------------
-- 2. Raw Metrics Table for System Health
-- ---------------------------------------------------------------------------
CREATE TABLE system_health_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,                      -- 'api', 'database', 'worker'
    metric_name VARCHAR(100) NOT NULL,                       -- 'response_time_ms', 'error_count', 'active_connections'
    metric_value FLOAT NOT NULL,
    metric_unit VARCHAR(50),                                 -- 'ms', 'count', 'percent'
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_health_metrics_service_recorded ON system_health_metrics(service_name, recorded_at);
CREATE INDEX idx_health_metrics_metric_recorded ON system_health_metrics(service_name, metric_name, recorded_at);
CREATE INDEX idx_health_metrics_recorded ON system_health_metrics(recorded_at DESC);

-- ---------------------------------------------------------------------------
-- 3. Feature Adoption Materialized View (daily aggregation)
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

-- ---------------------------------------------------------------------------
-- 4. System Health Materialized View (24h aggregation)
-- ---------------------------------------------------------------------------
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
