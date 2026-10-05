-- ================================================================
-- Data Quality Monitoring Schema Validation Tests
-- For: 05_data_quality_monitoring.sql
-- Run AFTER applying schema and seed data
-- ================================================================

-- =============================================================================
-- TEST 1: Data Quality Table Existence
-- =============================================================================
SELECT 'TEST 1 - DQ Table Existence' AS test;
DO $$
BEGIN
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sync_health');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_quality_checks');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_quality_results');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'match_rate_tracking');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_quality_alert_rules');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_quality_alert_log');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pipeline_performance');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_latency_tracking');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_retention_policies');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_records');
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 2: Row Count Sanity Checks (post-seed)
-- =============================================================================
SELECT 'TEST 2 - DQ Row Count Sanity' AS test;
SELECT
    (SELECT COUNT(*) FROM sync_health) AS sync_health_count,
    (SELECT COUNT(*) FROM data_quality_checks) AS dq_checks_count,
    (SELECT COUNT(*) FROM data_quality_results) AS dq_results_count,
    (SELECT COUNT(*) FROM match_rate_tracking) AS match_rate_count,
    (SELECT COUNT(*) FROM data_quality_alert_rules) AS alert_rules_count,
    (SELECT COUNT(*) FROM data_quality_alert_log) AS alert_log_count,
    (SELECT COUNT(*) FROM pipeline_performance) AS pipeline_perf_count,
    (SELECT COUNT(*) FROM api_latency_tracking) AS api_latency_count,
    (SELECT COUNT(*) FROM data_retention_policies) AS retention_policies_count,
    (SELECT COUNT(*) FROM archived_records) AS archived_records_count;
-- Expected after seed: all counts > 0


-- =============================================================================
-- TEST 3: Trigger - Match Rate Auto-Compute
-- =============================================================================
SELECT 'TEST 3 - Match Rate Auto-Compute Trigger' AS test;
DO $$
DECLARE
    test_id UUID := gen_random_uuid();
    computed_rate DECIMAL;
    computed_fuzzy DECIMAL;
BEGIN
    INSERT INTO match_rate_tracking (id, source_name, match_date, source_records_total, matched_records, unmatched_records, fuzzy_matched_records)
    VALUES (test_id, 'test_source', CURRENT_DATE, 100, 85, 15, 5);

    SELECT match_rate_percent, fuzzy_match_percent
    INTO computed_rate, computed_fuzzy
    FROM match_rate_tracking
    WHERE id = test_id;

    ASSERT computed_rate = 85.00, 'Match rate should be 85.00';
    ASSERT computed_fuzzy = 33.33, 'Fuzzy match rate should be 33.33';

    -- Clean up
    DELETE FROM match_rate_tracking WHERE id = test_id;
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 4: Trigger - Pipeline Performance Auto-Compute
-- =============================================================================
SELECT 'TEST 4 - Pipeline Performance Auto-Compute Trigger' AS test;
DO $$
DECLARE
    test_id UUID := gen_random_uuid();
    computed_duration INTEGER;
    computed_cache_rate DECIMAL;
    computed_avg_latency DECIMAL;
BEGIN
    INSERT INTO pipeline_performance (id, pipeline_name, run_start_at, run_end_at, cache_hits, cache_misses, api_calls_made, total_api_latency_ms)
    VALUES (test_id, 'test_pipeline', '2026-06-08 01:00:00-05', '2026-06-08 01:05:30-05', 100, 25, 10, 25000);

    SELECT duration_ms, cache_hit_rate_percent, avg_api_latency_ms
    INTO computed_duration, computed_cache_rate, computed_avg_latency
    FROM pipeline_performance
    WHERE id = test_id;

    ASSERT computed_duration >= 330000 AND computed_duration <= 330000, 'Duration should be 330000 ms';
    ASSERT computed_cache_rate = 80.00, 'Cache hit rate should be 80.00';
    ASSERT computed_avg_latency = 2500.00, 'Average API latency should be 2500.00';

    -- Clean up
    DELETE FROM pipeline_performance WHERE id = test_id;
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 5: Sync Health Indexes
-- =============================================================================
SELECT 'TEST 5 - Sync Health Indexes' AS test;
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'sync_health'
  AND indexname IN ('idx_sync_health_source', 'idx_sync_health_status', 'idx_sync_health_last_successful');


-- =============================================================================
-- TEST 6: Materialized View Existence
-- =============================================================================
SELECT 'TEST 6 - Materialized View Existence' AS test;
DO $$
BEGIN
    ASSERT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_sync_health_dashboard');
    ASSERT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_data_quality_summary');
    ASSERT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_match_rate_trends');
    ASSERT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_pipeline_performance_summary');
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 7: Unique Constraint - Match Rate Source + Date
-- =============================================================================
SELECT 'TEST 7 - Match Rate Unique Constraint' AS test;
DO $$
BEGIN
    -- Attempt duplicate insert (should fail if UNIQUE index works)
    INSERT INTO match_rate_tracking (id, source_name, match_date, source_records_total, matched_records, unmatched_records, fuzzy_matched_records)
    VALUES (gen_random_uuid(), 'test_duplicate', '2026-06-08', 100, 90, 10, 0);

    -- Second insert with same source and date should raise duplicate key violation
    BEGIN
        INSERT INTO match_rate_tracking (id, source_name, match_date, source_records_total, matched_records, unmatched_records, fuzzy_matched_records)
        VALUES (gen_random_uuid(), 'test_duplicate', '2026-06-08', 100, 90, 10, 0);
        RAISE EXCEPTION 'Expected unique violation but insert succeeded';
    EXCEPTION WHEN unique_violation THEN
        -- Expected; do nothing
        NULL;
    END;

    -- Clean up
    DELETE FROM match_rate_tracking WHERE source_name = 'test_duplicate';
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 8: Alert Rule Cooldown and Trigger
-- =============================================================================
SELECT 'TEST 8 - Alert Rule Structure' AS test;
SELECT rule_name, rule_type, severity, is_active, cooldown_minutes
FROM data_quality_alert_rules
WHERE is_active = TRUE
ORDER BY rule_name;


-- =============================================================================
-- TEST 9: Retention Policy - No Delete Action Allowed
-- =============================================================================
SELECT 'TEST 9 - Retention Policy Safety' AS test;
DO $$
BEGIN
    -- Verify no retention policy uses 'delete' action
    ASSERT NOT EXISTS (
        SELECT 1 FROM data_retention_policies WHERE action = 'delete'
    ), 'Retention policies must NOT use delete action (archive or flag only)';
END $$;
SELECT 'PASSED' AS result;


-- =============================================================================
-- TEST 10: Referential Integrity - Alert Log to Alert Rules
-- =============================================================================
SELECT 'TEST 10 - Referential Integrity' AS test;
DO $$
BEGIN
    -- All alert log entries must reference valid rules
    ASSERT NOT EXISTS (
        SELECT 1 FROM data_quality_alert_log dal
        LEFT JOIN data_quality_alert_rules dr ON dal.rule_id = dr.id
        WHERE dr.id IS NULL
    ), 'All alert log entries must reference valid alert rules';
END $$;
SELECT 'PASSED' AS result;
