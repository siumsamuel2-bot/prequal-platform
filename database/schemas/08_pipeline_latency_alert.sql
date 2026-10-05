-- Pipeline 95th Percentile Latency Alert (MID-150)
-- Purpose: Create a data-quality alert that fires when the 95th-percentile
-- pipeline latency (duration_ms) over the last 24 hours exceeds 6 minutes (360000ms).
-- Dependencies: 05_data_quality_monitoring.sql (alert rules + pipeline_performance tables)

-- ================================================================
-- 1. Alert Rule
-- ================================================================

INSERT INTO data_quality_alert_rules (
    id,
    rule_name,
    rule_type,
    source_name,
    condition_operator,
    condition_value,
    severity,
    notification_channels,
    is_active,
    cooldown_minutes,
    created_at,
    updated_at
)
SELECT 
    gen_random_uuid(),
    'pipeline_latency_95th_percentile',
    'performance',
    'external_compliance_pipeline',
    '>',              -- condition_operator: current p95 > threshold
    '360000',         -- condition_value: 6 minutes in milliseconds
    'warning',        -- severity: warning
    ARRAY['email', 'slack'],
    TRUE,
    60,               -- cooldown_minutes: 1 hour
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM data_quality_alert_rules
    WHERE rule_name = 'pipeline_latency_95th_percentile'
);

-- ================================================================
-- 2. Helper Function: Evaluate 95th Percentile Latency
-- ================================================================

CREATE OR REPLACE FUNCTION check_latency_95th_percentile(
    p_pipeline_name VARCHAR DEFAULT 'external_compliance_pipeline'
)
RETURNS TABLE (
    should_fire BOOLEAN,
    current_p95_ms NUMERIC,
    alert_message TEXT
) AS $$
DECLARE
    v_p95_ms NUMERIC;
    v_threshold_ms NUMERIC := 360000;
BEGIN
    -- Compute 95th percentile for the last 24 hours
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) INTO v_p95_ms
    FROM pipeline_performance
    WHERE pipeline_name = p_pipeline_name
      AND run_start_at > CURRENT_TIMESTAMP - INTERVAL '24 hours';

    IF v_p95_ms IS NULL THEN
        RETURN QUERY SELECT FALSE, v_p95_ms, 'No performance data found in the last 24 hours for pipeline ' || p_pipeline_name;
    ELSIF v_p95_ms > v_threshold_ms THEN
        RETURN QUERY SELECT TRUE, v_p95_ms, '95th percentile latency (' || v_p95_ms || ' ms) exceeds threshold (' || v_threshold_ms || ' ms) for pipeline ' || p_pipeline_name;
    ELSE
        RETURN QUERY SELECT FALSE, v_p95_ms, '95th percentile latency (' || v_p95_ms || ' ms) within threshold (' || v_threshold_ms || ' ms) for pipeline ' || p_pipeline_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 3. Helper Function: Insert an Alert Log Entry from the 95th Percentile Check
-- ================================================================

CREATE OR REPLACE FUNCTION raise_latency_alert(
    p_pipeline_name VARCHAR DEFAULT 'external_compliance_pipeline'
)
RETURNS TABLE (alert_log_id UUID, severity VARCHAR, message TEXT) AS $$
DECLARE
    v_rule_id UUID;
    v_should_fire BOOLEAN;
    v_p95_ms NUMERIC;
    v_message TEXT;
    v_log_id UUID;
BEGIN
    -- Find the latency alert rule
    SELECT id INTO v_rule_id
    FROM data_quality_alert_rules
    WHERE rule_name = 'pipeline_latency_95th_percentile'
    AND is_active = TRUE;

    IF v_rule_id IS NULL THEN
        RETURN;
    END IF;

    -- Check the 95th percentile
    SELECT c.should_fire, c.current_p95_ms, c.alert_message
    INTO v_should_fire, v_p95_ms, v_message
    FROM check_latency_95th_percentile(p_pipeline_name) c;

    IF v_should_fire THEN
        INSERT INTO data_quality_alert_log (rule_id, alert_status, severity, alert_message, context)
        VALUES (
            v_rule_id,
            'pending',
            'warning',
            v_message,
            jsonb_build_object('pipeline', p_pipeline_name, 'p95_latency_ms', v_p95_ms)
        )
        RETURNING id INTO v_log_id;
        RETURN QUERY SELECT v_log_id, 'warning'::VARCHAR, v_message::TEXT;
    ELSE
        RETURN;
    END IF;
END;
$$ LANGUAGE plpgsql;
