-- Schema Validation Tests for Prequal Subcontractor Compliance Platform
-- Run this after applying schema files and seed data.
-- All tests should pass (return rows matching expected patterns).
-- Failures indicate schema or constraint issues that must be resolved.

-- =============================================================================
-- TEST 1: Core Table Existence
-- =============================================================================
SELECT 'TEST 1 - Core Table Existence' AS test;
DO $$
BEGIN
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'subcontractors');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'projects');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'certifications');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'project_subcontractors');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'violations');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alert_preferences');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alert_notifications');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'certification_renewals');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'osha_inspections');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'osha_api_logs');
    ASSERT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'osha_data_freshness');
END $$;
SELECT 'PASSED' AS result;

-- =============================================================================
-- TEST 2: Row Count Sanity Checks (post-seed)
-- =============================================================================
SELECT 'TEST 2 - Row Count Sanity' AS test;
SELECT
    (SELECT COUNT(*) FROM subcontractors) AS subcontractors_count,
    (SELECT COUNT(*) FROM projects) AS projects_count,
    (SELECT COUNT(*) FROM certifications) AS certifications_count;
-- Expected after seed: subcontractors >= 8, projects >= 3, certifications >= 11

-- =============================================================================
-- TEST 3: Primary Key Constraints
-- =============================================================================
SELECT 'TEST 3 - Primary Key Constraints' AS test;
-- Each core table must have a unique primary key (id)
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_name IN ('subcontractors', 'projects', 'certifications', 'violations')
  AND column_name = 'id'
  AND is_nullable = 'NO';

-- =============================================================================
-- TEST 4: Not-Null Constraints
-- =============================================================================
SELECT 'TEST 4 - Not-Null Constraints' AS test;
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE table_name IN ('subcontractors', 'projects', 'certifications')
  AND column_name IN ('company_name', 'email', 'subcontractor_id', 'certification_type', 'expiration_date', 'violation_type', 'description')
  AND is_nullable = 'NO';

-- =============================================================================
-- TEST 5: Foreign Key Constraints (Parent Tables)
-- =============================================================================
SELECT 'TEST 5 - Foreign Key Constraints' AS test;
SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('certifications', 'violations', 'project_subcontractors', 'alert_notifications', 'certification_renewals')
ORDER BY tc.table_name, kcu.column_name;

-- =============================================================================
-- TEST 6: Email Uniqueness
-- =============================================================================
SELECT 'TEST 6 - Email Uniqueness' AS test;
SELECT CASE WHEN COUNT(email) = COUNT(DISTINCT email) THEN 'PASSED' ELSE 'FAILED - Duplicate emails found' END
FROM subcontractors;

-- =============================================================================
-- TEST 7: Status Enum Validation (recommended domain/enum)
-- =============================================================================
SELECT 'TEST 7 - Status Enum Values' AS test;
SELECT DISTINCT status FROM subcontractors WHERE status NOT IN ('active', 'inactive', 'suspended', 'blacklisted');
SELECT DISTINCT status FROM projects WHERE status NOT IN ('planning', 'active', 'on_hold', 'completed', 'cancelled');
SELECT DISTINCT status FROM certifications WHERE status NOT IN ('valid', 'expired', 'revoked', 'pending_verification');
SELECT DISTINCT status FROM violations WHERE status NOT IN ('open', 'under_review', 'resolved', 'appealed');
SELECT DISTINCT status FROM alert_notifications WHERE status NOT IN ('pending', 'sent', 'failed', 'cancelled');
SELECT DISTINCT status FROM certification_renewals WHERE status NOT IN ('pending', 'approved', 'rejected', 'completed');

-- =============================================================================
-- TEST 8: Cascading Delete / ON DELETE CASCADE
-- =============================================================================
SELECT 'TEST 8 - Cascade Delete Test' AS test;
DO $$
DECLARE
    test_sub_id UUID := gen_random_uuid();
    test_cert_id UUID := gen_random_uuid();
BEGIN
    INSERT INTO subcontractors (id, company_name, email, status) VALUES (test_sub_id, 'DeleteTest Sub', 'cascadetest@example.com', 'active');
    INSERT INTO certifications (id, subcontractor_id, certification_type, expiration_date, status)
    VALUES (test_cert_id, test_sub_id, 'Cascade Test Cert', '2027-01-01', 'valid');

    -- Verify certification exists
    ASSERT EXISTS (SELECT 1 FROM certifications WHERE id = test_cert_id);

    -- Delete subcontractor, expect certification gone
    DELETE FROM subcontractors WHERE id = test_sub_id;
    ASSERT NOT EXISTS (SELECT 1 FROM certifications WHERE id = test_cert_id);
END $$;
SELECT 'PASSED' AS result;

-- =============================================================================
-- TEST 9: Trigger - updated_at timestamp
-- =============================================================================
SELECT 'TEST 9 - updated_at Trigger Test' AS test;
DO $$
DECLARE
    original_ts TIMESTAMP WITH TIME ZONE;
    updated_ts TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Create a test sub and record its initial updated_at
    INSERT INTO subcontractors (id, company_name, email, status)
    VALUES ('00000000-0000-0000-0000-000000000099', 'TriggerTest Sub', 'triggertest@example.com', 'active');

    SELECT updated_at INTO original_ts FROM subcontractors WHERE id = '00000000-0000-0000-0000-000000000099';

    -- Wait briefly and update
    PERFORM pg_sleep(0.1);
    UPDATE subcontractors SET phone = '555-1111' WHERE id = '00000000-0000-0000-0000-000000000099';

    SELECT updated_at INTO updated_ts FROM subcontractors WHERE id = '00000000-0000-0000-0000-000000000099';

    ASSERT updated_ts > original_ts;
END $$;
SELECT 'PASSED' AS result;

-- =============================================================================
-- TEST 10: Index Existence (Performance)
-- =============================================================================
SELECT 'TEST 10 - Index Existence' AS test;
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('subcontractors', 'projects', 'certifications', 'violations')
  AND indexname LIKE 'idx_%';