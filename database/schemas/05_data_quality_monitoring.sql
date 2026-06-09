-- Data Quality Monitoring & Analytics Pipeline
-- Schema: 05_data_quality_monitoring.sql
-- Purpose: Track sync health, data quality, match rates, and pipeline performance
-- Dependencies: 01_core_tables, 02_expiration_tracking, 03_osha_integration, 04_state_credentials

-- ================================================================
-- 1. SYNC HEALTH TRACKING
-- ================================================================

CREATE TABLE sync_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(100) NOT NULL,                     -- e.g., 'osha_api', 'tx_credentials'
    source_type VARCHAR(50) NOT NULL,                      -- 'api', 'ftp', 'sftp'
    sync_run_log_id UUID REFERENCES sync_run_logs(id) ON DELETE SET NULL,
    health_status VARCHAR(50) DEFAULT 'healthy',          -- healthy, degraded, failed, unknown
    last_successful_sync_at TIMESTAMP WITH TIME ZONE,
    last_failed_sync_at TIMESTAMP WITH TIME ZONE,
    last_failure_reason TEXT,
    sync_frequency VARCHAR(50) DEFAULT 'daily',
    expected_next_sync_at TIMESTAMP WITH TIME ZONE,
    consecutive_failures INTEGER DEFAULT 0,
    consecutive_successes INTEGER DEFAULT 0,
    average_records_processed INTEGER DEFAULT 0,
    average_processing_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_sync_health_source ON sync_health(source_name, source_type);
CREATE INDEX idx_sync_health_status ON sync_health(health_status);
CREATE INDEX idx_sync_health_last_successful ON sync_health(last_successful_sync_at);

-- ================================================================
-- 2. DATA QUALITY CHECKS & METRICS
-- ================================================================

CREATE TABLE data_quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_name VARCHAR(255) NOT NULL,                      -- e.g., 'subcontractors_email_unique'
    check_type VARCHAR(100) NOT NULL,                    -- uniqueness, completeness, freshness, format, referential
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100),
    description TEXT,
    check_query TEXT NOT NULL,                             -- SQL that evaluates to pass/fail or numeric score
    expected_result VARCHAR(50),                         -- 'null', 'empty', 'gt_0', etc.
    alert_threshold DECIMAL(5,4),                        -- When to alert (e.g., 0.95 for 95% pass rate)
    is_active BOOLEAN DEFAULT TRUE,
    priority VARCHAR(20) DEFAULT 'medium',                 -- critical, high, medium, low
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dq_checks_table ON data_quality_checks(table_name);
CREATE INDEX idx_dq_checks_type ON data_quality_checks(check_type);
CREATE INDEX idx_dq_checks_active ON data_quality_checks(is_active);

CREATE TABLE data_quality_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_id UUID NOT NULL REFERENCES data_quality_checks(id) ON DELETE CASCADE,
    run_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,                           -- pass, fail, warning, error
    actual_result TEXT,                                    -- The actual result of the check
    record_count INTEGER,
    failed_record_count INTEGER,
    details JSONB,                                          -- Detailed info about failures
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dq_results_check_id ON data_quality_results(check_id);
CREATE INDEX idx_dq_results_run_at ON data_quality_results(run_at);
CREATE INDEX idx_dq_results_status ON data_quality_results(status);

-- ================================================================
-- 3. MATCH RATE TRACKING (External Data → Internal Records)
-- ================================================================

CREATE TABLE match_rate_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(100) NOT NULL,
    match_date DATE NOT NULL DEFAULT CURRENT_DATE,
    source_records_total INTEGER DEFAULT 0,
    source_records_new INTEGER DEFAULT 0,
    source_records_updated INTEGER DEFAULT 0,
    matched_records INTEGER DEFAULT 0,
    unmatched_records INTEGER DEFAULT 0,
    fuzzy_matched_records INTEGER DEFAULT 0,
    match_rate_percent DECIMAL(5,2),                     -- matched / total * 100
    fuzzy_match_percent DECIMAL(5,2),                    -- fuzzy_matched / unmatched * 100
    match_confidence_avg DECIMAL(5,2),                   -- 0.00 to 1.00
    reprocess_needed BOOLEAN DEFAULT FALSE,
    match_method VARCHAR(50) DEFAULT 'exact',              -- exact, fuzzy, composite
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_match_rate_source_date ON match_rate_tracking(source_name, match_date);
CREATE INDEX idx_match_rate_source ON match_rate_tracking(source_name);
CREATE INDEX idx_match_rate_date ON match_rate_tracking(match_date);

-- Auto-compute match rate via trigger
CREATE OR REPLACE FUNCTION compute_match_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.source_records_total > 0 THEN
        NEW.match_rate_percent := (NEW.matched_records::DECIMAL / NEW.source_records_total::DECIMAL * 100)::DECIMAL(5,2);
        IF NEW.unmatched_records > 0 THEN
            NEW.fuzzy_match_percent := (NEW.fuzzy_matched_records::DECIMAL / NEW.unmatched_records::DECIMAL * 100)::DECIMAL(5,2);
        ELSE
            NEW.fuzzy_match_percent := 0;
        END IF;
    ELSE
        NEW.match_rate_percent := 0;
        NEW.fuzzy_match_percent := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER match_rate_auto_compute
    BEFORE INSERT OR UPDATE ON match_rate_tracking
    FOR EACH ROW
    EXECUTE FUNCTION compute_match_rate();

-- ================================================================
-- 4. ALERT RULES & PERSISTENT ALERT LOG
-- ================================================================

CREATE TABLE data_quality_alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(100) NOT NULL,                     -- sync_fail, match_rate_drop, quality_fail, stale_data, performance
    source_name VARCHAR(100),
    check_id UUID REFERENCES data_quality_checks(id) ON DELETE SET NULL,
    condition_operator VARCHAR(20),                        -- '<', '>', '<=', '>=', '=', '!=' or 'contains'
    condition_value TEXT,
    severity VARCHAR(20) DEFAULT 'warning',              -- info, warning, critical, emergency
    notification_channels TEXT[] DEFAULT '{email}',    -- email, sms, slack, in_app
    recipients TEXT[],                                     -- list of contact identifiers
    is_active BOOLEAN DEFAULT TRUE,
    cooldown_minutes INTEGER DEFAULT 60,                 -- Prevent alert spam
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_rules_type ON data_quality_alert_rules(rule_type);
CREATE INDEX idx_alert_rules_active ON data_quality_alert_rules(is_active);
CREATE INDEX idx_alert_rules_source ON data_quality_alert_rules(source_name);

CREATE TABLE data_quality_alert_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id UUID NOT NULL REFERENCES data_quality_alert_rules(id) ON DELETE CASCADE,
    alert_status VARCHAR(50) DEFAULT 'pending',          -- pending, acknowledged, resolved, escalated, dismissed
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by UUID,
    resolved_at TIMESTAMP WITH TIME ZONE,
    severity VARCHAR(20),
    alert_message TEXT,
    context JSONB,                                        -- snapshot of conditions when triggered
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_log_rule_id ON data_quality_alert_log(rule_id);
CREATE INDEX idx_alert_log_status ON data_quality_alert_log(alert_status);
CREATE INDEX idx_alert_log_triggered_at ON data_quality_alert_log(triggered_at);
CREATE INDEX idx_alert_log_severity ON data_quality_alert_log(severity);

-- ================================================================
-- 5. PERFORMANCE MONITORING
-- ================================================================

CREATE TABLE pipeline_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_name VARCHAR(255) NOT NULL,                 -- e.g., 'osha_daily_sync'
    run_id UUID,                                          -- If linked to a sync_run_logs entry
    run_start_at TIMESTAMP WITH TIME ZONE,
    run_end_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    cpu_time_ms INTEGER,
    memory_peak_mb INTEGER,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    cache_hit_rate_percent DECIMAL(5,2),
    api_calls_made INTEGER DEFAULT 0,
    total_api_latency_ms INTEGER DEFAULT 0,
    avg_api_latency_ms DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'running',              -- running, completed, partial, failed
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_perf_pipeline ON pipeline_performance(pipeline_name);
CREATE INDEX idx_perf_run_start ON pipeline_performance(run_start_at);
CREATE INDEX idx_perf_status ON pipeline_performance(status);

-- Auto-compute cache hit rate and duration
CREATE OR REPLACE FUNCTION compute_pipeline_metrics()
RETURNS TRIGGER AS $$
DECLARE
    v_cache_total INTEGER;
BEGIN
    -- Compute duration if both timestamps are present
    IF NEW.run_start_at IS NOT NULL AND NEW.run_end_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.run_end_at - NEW.run_start_at)) * 1000;
    END IF;

    -- Compute cache hit rate
    IF NEW.cache_hits IS NOT NULL AND NEW.cache_misses IS NOT NULL THEN
        v_cache_total := NEW.cache_hits + NEW.cache_misses;
        IF v_cache_total > 0 THEN
            NEW.cache_hit_rate_percent := (NEW.cache_hits::DECIMAL / v_cache_total::DECIMAL * 100)::DECIMAL(5,2);
        ELSE
            NEW.cache_hit_rate_percent := 0;
        END IF;
    END IF;

    -- Compute average API latency
    IF NEW.api_calls_made > 0 AND NEW.total_api_latency_ms IS NOT NULL THEN
        NEW.avg_api_latency_ms := NEW.total_api_latency_ms::DECIMAL / NEW.api_calls_made::DECIMAL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pipeline_perf_auto_compute
    BEFORE INSERT OR UPDATE ON pipeline_performance
    FOR EACH ROW
    EXECUTE FUNCTION compute_pipeline_metrics();

CREATE TABLE api_latency_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,                           -- GET, POST, etc.
    request_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER NOT NULL,
    status_code INTEGER,
    response_size_bytes INTEGER,
    is_cache_hit BOOLEAN DEFAULT FALSE,
    pipeline_name VARCHAR(255),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_latency_endpoint ON api_latency_tracking(endpoint);
CREATE INDEX idx_api_latency_request_at ON api_latency_tracking(request_at);
CREATE INDEX idx_api_latency_pipeline ON api_latency_tracking(pipeline_name);

-- ================================================================
-- 6. DATA RETENTION & ARCHIVAL TRACKING (Flag-based; never delete)
-- ================================================================

CREATE TABLE data_retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    retention_days INTEGER NOT NULL,
    archival_after_days INTEGER,                          -- When to move to archive table
    action VARCHAR(50) DEFAULT 'archive',               -- archive, flag, partition
    is_active BOOLEAN DEFAULT TRUE,
    last_applied_at TIMESTAMP WITH TIME ZONE,
    records_archived INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_retention_table ON data_retention_policies(table_name);
CREATE INDEX idx_retention_active ON data_retention_policies(is_active);

CREATE TABLE archived_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_table VARCHAR(100) NOT NULL,
    source_record_id UUID NOT NULL,
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(255),
    retention_policy_id UUID REFERENCES data_retention_policies(id) ON DELETE SET NULL,
    original_data JSONB NOT NULL,                         -- Full snapshot
    restored_at TIMESTAMP WITH TIME ZONE,               -- If ever restored
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_archived_source ON archived_records(source_table, source_record_id);
CREATE INDEX idx_archived_at ON archived_records(archived_at);

-- ================================================================
-- 7. MATERIALIZED VIEWS FOR ANALYTICS
-- ================================================================

-- Daily sync health dashboard
CREATE MATERIALIZED VIEW mv_sync_health_dashboard AS
SELECT
    sh.source_name,
    sh.source_type,
    sh.health_status,
    sh.last_successful_sync_at,
    sh.last_failed_sync_at,
    sh.consecutive_failures,
    sh.consecutive_successes,
    srl.records_processed AS last_run_records,
    srl.status AS last_run_status,
    srl.completed_at AS last_run_completed_at,
    CASE
        WHEN sh.consecutive_failures >= 3 THEN 'critical'
        WHEN sh.consecutive_failures >= 1 THEN 'warning'
        WHEN sh.last_successful_sync_at IS NULL THEN 'unknown'
        ELSE 'healthy'
    END AS overall_health,
    CURRENT_TIMESTAMP AS refreshed_at
FROM sync_health sh
LEFT JOIN sync_run_logs srl ON sh.sync_run_log_id = srl.id;

-- Data quality summary by table
CREATE MATERIALIZED VIEW mv_data_quality_summary AS
SELECT
    dqc.table_name,
    COUNT(DISTINCT dqc.id) AS total_checks,
    COUNT(DISTINCT CASE WHEN dqr.status = 'pass' THEN dqc.id END) AS passing_checks,
    COUNT(DISTINCT CASE WHEN dqr.status = 'fail' THEN dqc.id END) AS failing_checks,
    COUNT(DISTINCT CASE WHEN dqr.status = 'warning' THEN dqc.id END) AS warning_checks,
    MAX(dqr.run_at) AS last_check_run_at,
    CURRENT_TIMESTAMP AS refreshed_at
FROM data_quality_checks dqc
LEFT JOIN data_quality_results dqr ON dqc.id = dqr.check_id
    AND dqr.run_at = (SELECT MAX(run_at) FROM data_quality_results WHERE check_id = dqc.id)
WHERE dqc.is_active = TRUE
GROUP BY dqc.table_name;

-- Match rate trends over time
CREATE MATERIALIZED VIEW mv_match_rate_trends AS
SELECT
    source_name,
    DATE_TRUNC('week', match_date) AS period,
    AVG(match_rate_percent) AS avg_match_rate,
    MIN(match_rate_percent) AS min_match_rate,
    MAX(match_rate_percent) AS max_match_rate,
    SUM(source_records_total) AS total_records,
    SUM(matched_records) AS total_matched,
    COUNT(*) AS sync_count,
    CURRENT_TIMESTAMP AS refreshed_at
FROM match_rate_tracking
GROUP BY source_name, DATE_TRUNC('week', match_date);

-- Pipeline performance summary
CREATE MATERIALIZED VIEW mv_pipeline_performance_summary AS
SELECT
    pipeline_name,
    DATE_TRUNC('day', run_start_at) AS run_date,
    COUNT(*) AS run_count,
    AVG(duration_ms) AS avg_duration_ms,
    MIN(duration_ms) AS min_duration_ms,
    MAX(duration_ms) AS max_duration_ms,
    SUM(records_processed) AS total_records_processed,
    SUM(records_failed) AS total_records_failed,
    AVG(cache_hit_rate_percent) AS avg_cache_hit_rate,
    AVG(avg_api_latency_ms) AS avg_api_latency_ms,
    CURRENT_TIMESTAMP AS refreshed_at
FROM pipeline_performance
GROUP BY pipeline_name, DATE_TRUNC('day', run_start_at);

-- Maintenance: refresh all materialized views (run periodically)
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sync_health_dashboard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_data_quality_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_match_rate_trends;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pipeline_performance_summary;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 8. UPDATED_AT TRIGGERS (if update_updated_at_column exists)
-- ================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        EXECUTE 'CREATE TRIGGER update_sync_health_updated_at BEFORE UPDATE ON sync_health FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()';
        EXECUTE 'CREATE TRIGGER update_dq_checks_updated_at BEFORE UPDATE ON data_quality_checks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()';
        EXECUTE 'CREATE TRIGGER update_dq_alert_rules_updated_at BEFORE UPDATE ON data_quality_alert_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()';
        EXECUTE 'CREATE TRIGGER update_retention_policies_updated_at BEFORE UPDATE ON data_retention_policies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()';
    END IF;
END $$;

-- ================================================================
-- 9. HELPER FUNCTIONS FOR ALERT EVALUATION
-- ================================================================

-- Evaluate a data quality check result against its alert threshold
-- Returns: 'pass', 'warning', or 'fail'
CREATE OR REPLACE FUNCTION evaluate_check_status(
    p_check_id UUID,
    p_actual_result TEXT,
    p_failed_record_count INTEGER DEFAULT NULL
)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_alert_threshold DECIMAL(5,4);
    v_expected_result TEXT;
    v_result NUMERIC;
BEGIN
    SELECT alert_threshold, expected_result
    INTO v_alert_threshold, v_expected_result
    FROM data_quality_checks
    WHERE id = p_check_id;

    -- Direct comparison for simple expected results
    IF v_expected_result IS NOT NULL AND p_actual_result = v_expected_result THEN
        RETURN 'pass';
    END IF;

    -- Numeric threshold comparison (for percentage-based checks)
    IF v_alert_threshold IS NOT NULL THEN
        BEGIN
            v_result := p_actual_result::NUMERIC;
            IF v_result >= v_alert_threshold * 100 THEN
                RETURN 'pass';
            ELSIF v_result >= (v_alert_threshold - 0.05) * 100 THEN
                RETURN 'warning';
            ELSE
                RETURN 'fail';
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- Non-numeric result, default to check against expected
            IF p_actual_result = v_expected_result THEN
                RETURN 'pass';
            ELSE
                RETURN 'fail';
            END IF;
        END IF;
    END IF;

    RETURN 'pass';
END;
$$ LANGUAGE plpgsql;

-- Evaluate an alert rule and determine if it should fire
CREATE OR REPLACE FUNCTION evaluate_alert_rule(
    p_rule_id UUID
)
RETURNS TABLE (should_fire BOOLEAN, rule_severity VARCHAR(20), alert_context JSONB) AS $$
DECLARE
    v_rule RECORD;
    v_current_value TEXT;
    v_condition_met BOOLEAN := FALSE;
    v_context JSONB;
BEGIN
    SELECT * INTO v_rule FROM data_quality_alert_rules WHERE id = p_rule_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR(20), NULL::JSONB;
        RETURN;
    END IF;

    -- Build context based on rule type
    CASE v_rule.rule_type
        WHEN 'sync_fail' THEN
            SELECT INTO v_current_value consecutive_failures::TEXT
            FROM sync_health
            WHERE source_name = v_rule.source_name;

            v_context := jsonb_build_object(
                'source', v_rule.source_name,
                'consecutive_failures', v_current_value::INT
            );

        WHEN 'match_rate_drop' THEN
            SELECT INTO v_current_value match_rate_percent::TEXT
            FROM match_rate_tracking
            WHERE source_name = v_rule.source_name
            ORDER BY match_date DESC LIMIT 1;

            v_context := jsonb_build_object(
                'source', v_rule.source_name,
                'current_match_rate', v_current_value::NUMERIC
            );

        WHEN 'quality_fail' THEN
            SELECT INTO v_current_value status
            FROM data_quality_results
            WHERE check_id = v_rule.check_id
            ORDER BY run_at DESC LIMIT 1;

            v_context := jsonb_build_object(
                'check_id', v_rule.check_id,
                'latest_result', v_current_value
            );

        WHEN 'stale_data' THEN
            SELECT INTO v_current_value EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_successful_sync_at))::TEXT
            FROM sync_health
            WHERE source_name = v_rule.source_name;

            v_context := jsonb_build_object(
                'source', v_rule.source_name,
                'seconds_stale', v_current_value::NUMERIC
            );

        WHEN 'performance' THEN
            SELECT INTO v_current_value duration_ms::TEXT
            FROM pipeline_performance
            WHERE pipeline_name = v_rule.source_name
            ORDER BY run_start_at DESC LIMIT 1;

            v_context := jsonb_build_object(
                'pipeline', v_rule.source_name,
                'last_duration_ms', v_current_value::NUMERIC
            );
    END CASE;

    -- Evaluate condition
    IF v_current_value IS NULL THEN
        RETURN QUERY SELECT FALSE, v_rule.severity, v_context;
        RETURN;
    END IF;

    -- Simple operator evaluation (covers most numeric cases)
    EXECUTE format(
        'SELECT $1 %s $2',
        v_rule.condition_operator
    ) INTO v_condition_met USING v_current_value::NUMERIC, v_rule.condition_value::NUMERIC;

    RETURN QUERY SELECT v_condition_met, v_rule.severity, v_context;
END;
$$ LANGUAGE plpgsql;

-- Check if an alert is in cooldown period
CREATE OR REPLACE FUNCTION is_alert_in_cooldown(
    p_rule_id UUID,
    p_cooldown_minutes INTEGER DEFAULT 60
)
RETURNS BOOLEAN AS $$
DECLARE
    v_last_triggered TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT last_triggered_at INTO v_last_triggered
    FROM data_quality_alert_rules
    WHERE id = p_rule_id;

    IF v_last_triggered IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN (CURRENT_TIMESTAMP - v_last_triggered) < (p_cooldown_minutes || ' minutes')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- Check sync health and return status
CREATE OR REPLACE FUNCTION check_sync_health(
    p_source_name VARCHAR(100)
)
RETURNS TABLE (source_name VARCHAR(100), overall_status VARCHAR(50), health_score NUMERIC, details JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sh.source_name::VARCHAR(100),
        CASE
            WHEN sh.consecutive_failures >= 3 THEN 'critical'::VARCHAR(50)
            WHEN sh.consecutive_failures >= 1 THEN 'warning'::VARCHAR(50)
            WHEN sh.last_successful_sync_at IS NULL THEN 'unknown'::VARCHAR(50)
            ELSE 'healthy'::VARCHAR(50)
        END,
        CASE
            WHEN sh.consecutive_failures >= 3 THEN 0.0
            WHEN sh.consecutive_failures >= 1 THEN 50.0
            WHEN sh.last_successful_sync_at IS NULL THEN NULL
            ELSE 100.0
        END::NUMERIC,
        jsonb_build_object(
            'last_successful_sync', sh.last_successful_sync_at,
            'last_failed_sync', sh.last_failed_sync_at,
            'consecutive_failures', sh.consecutive_failures,
            'expected_next_sync', sh.expected_next_sync_at
        )::JSONB
    FROM sync_health sh
    WHERE sh.source_name = p_source_name
      OR p_source_name IS NULL
    ORDER BY sh.source_name;
END;
$$ LANGUAGE plpgsql;

-- Apply data retention policy (flag-based, never delete)
CREATE OR REPLACE FUNCTION apply_retention_policy(
    p_policy_id UUID
)
RETURNS TABLE (records_archived BIGINT, log_message TEXT) AS $$
DECLARE
    v_policy RECORD;
    v_cutoff_date TIMESTAMP WITH TIME ZONE;
    v_archived_count BIGINT;
BEGIN
    SELECT * INTO v_policy FROM data_retention_policies WHERE id = p_policy_id;

    IF NOT FOUND OR NOT v_policy.is_active THEN
        RETURN QUERY SELECT 0::BIGINT, 'Policy not found or inactive'::TEXT;
        RETURN;
    END IF;

    -- Calculate cutoff date based on retention policy
    v_cutoff_date := CURRENT_TIMESTAMP - (v_policy.retention_days || ' days')::INTERVAL;

    -- Archive records older than retention period
    -- This is a flag-based operation, not a delete
    EXECUTE format(
        'INSERT INTO archived_records (source_table, source_record_id, archived_at, archive_reason, retention_policy_id, original_data)
         SELECT %L, id, CURRENT_TIMESTAMP, %L, %L, to_jsonb(t.*)
         FROM %I t
         WHERE t.created_at < %L
         AND NOT EXISTS (
             SELECT 1 FROM archived_records ar
             WHERE ar.source_table = %L AND ar.source_record_id = t.id
         )',
        v_policy.table_name,
        'Data retention policy: ' || v_policy.policy_name || ' (' || v_policy.retention_days || ' days)',
        p_policy_id,
        v_policy.table_name,
        v_cutoff_date,
        v_policy.table_name
    );

    GET DIAGNOSTICS v_archived_count = ROW_COUNT;

    -- Update policy tracking
    UPDATE data_retention_policies
    SET last_applied_at = CURRENT_TIMESTAMP,
        records_archived = records_archived + v_archived_count
    WHERE id = p_policy_id;

    RETURN QUERY SELECT v_archived_count,
        'Archived ' || v_archived_count || ' records from ' || v_policy.table_name || ' (policy: ' || v_policy.policy_name || ')'::TEXT;
END;
$$ LANGUAGE plpgsql;
