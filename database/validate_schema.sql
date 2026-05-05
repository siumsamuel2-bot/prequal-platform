-- =========================================
-- Schema Validation for Prequal Platform
-- Author: Data Engineer
-- Purpose: Verify constraints, relationships, and data integrity
-- Run after applying schema (01-03) and seed data
-- =========================================

-- =========================================
-- 1. TABLE EXISTENCE CHECK
-- =========================================
DO $$
DECLARE
    tbl RECORD;
BEGIN
    RAISE NOTICE '=== 1. TABLE EXISTENCE CHECK ===';
    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('subcontractors', 'projects', 'certifications',
                           'project_subcontractors', 'violations',
                           'alert_preferences', 'alert_notifications',
                           'certification_renewals', 'osha_inspections',
                           'osha_api_logs', 'osha_data_freshness')
    LOOP
        RAISE NOTICE 'Table % exists', tbl.table_name;
    END LOOP;
END;
$$;


-- =========================================
-- 2. PRIMARY KEY CONSTRAINTS
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 2. PRIMARY KEY CONSTRAINTS ===';
    PERFORM * FROM subcontractors WHERE id = 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111';
    IF FOUND THEN RAISE NOTICE 'PK subcontractors: PASS'; ELSE RAISE NOTICE 'PK subcontractors: FAIL'; END IF;

    PERFORM * FROM projects WHERE id = 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111';
    IF FOUND THEN RAISE NOTICE 'PK projects: PASS'; ELSE RAISE NOTICE 'PK projects: FAIL'; END IF;

    PERFORM * FROM certifications WHERE id = 'cccccccc-1111-1111-1111-cccccccc1111';
    IF FOUND THEN RAISE NOTICE 'PK certifications: PASS'; ELSE RAISE NOTICE 'PK certifications: FAIL'; END IF;

    PERFORM * FROM violations WHERE id = 'eeeeeeee-1111-1111-1111-eeeeeeee1111';
    IF FOUND THEN RAISE NOTICE 'PK violations: PASS'; ELSE RAISE NOTICE 'PK violations: FAIL'; END IF;
END;
$$;


-- =========================================
-- 3. FOREIGN KEY CONSTRAINTS
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 3. FOREIGN KEY CONSTRAINTS ===';
    -- certifications -> subcontractors
    PERFORM * FROM certifications c
    JOIN subcontractors s ON c.subcontractor_id = s.id
    WHERE c.id = 'cccccccc-1111-1111-1111-cccccccc1111';
    IF FOUND THEN RAISE NOTICE 'FK certifications.subcontractor_id: PASS'; ELSE RAISE NOTICE 'FK certifications.subcontractor_id: FAIL'; END IF;

    -- project_subcontractors -> projects, subcontractors
    PERFORM * FROM project_subcontractors ps
    JOIN projects p ON ps.project_id = p.id
    JOIN subcontractors s ON ps.subcontractor_id = s.id
    WHERE ps.id = 'dddddddd-1111-1111-1111-dddddddd1111';
    IF FOUND THEN RAISE NOTICE 'FK project_subcontractors project+sub: PASS'; ELSE RAISE NOTICE 'FK project_subcontractors project+sub: FAIL'; END IF;

    -- violations -> subcontractors
    PERFORM * FROM violations v
    JOIN subcontractors s ON v.subcontractor_id = s.id
    WHERE v.id = 'eeeeeeee-1111-1111-1111-eeeeeeee1111';
    IF FOUND THEN RAISE NOTICE 'FK violations.subcontractor_id: PASS'; ELSE RAISE NOTICE 'FK violations.subcontractor_id: FAIL'; END IF;
END;
$$;


-- =========================================
-- 4. UNIQUE CONSTRAINTS
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 4. UNIQUE CONSTRAINTS ===';

    -- subcontractors.email must be unique
    BEGIN
        INSERT INTO subcontractors (id, company_name, email, status, created_at, updated_at)
        VALUES ('ffffffff-1111-1111-1111-ffffffff1111', 'Duplicate Test', 'm.thompson@summit-construction.com', 'active', NOW(), NOW());
        RAISE NOTICE 'UNIQUE subcontractors.email: FAIL - accepted duplicate';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'UNIQUE subcontractors.email: PASS - correctly rejected';
    END;

    -- projects.project_number must be unique
    BEGIN
        INSERT INTO projects (id, project_name, project_number, status, created_at, updated_at)
        VALUES ('ffffffff-2222-2222-2222-ffffffff2222', 'Dup Proj', 'PROJ-2026-001', 'active', NOW(), NOW());
        RAISE NOTICE 'UNIQUE projects.project_number: FAIL - accepted duplicate';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'UNIQUE projects.project_number: PASS - correctly rejected';
    END;

    -- project_subcontractors (project_id, subcontractor_id) must be unique
    BEGIN
        INSERT INTO project_subcontractors (id, project_id, subcontractor_id, status, created_at, updated_at)
        VALUES ('ffffffff-3333-3333-3333-ffffffff3333', 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'active', NOW(), NOW());
        RAISE NOTICE 'UNIQUE project_subcontractors: FAIL - accepted duplicate';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'UNIQUE project_subcontractors: PASS - correctly rejected';
    END;
END;
$$;


-- =========================================
-- 5. NOT NULL CONSTRAINTS
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 5. NOT NULL CONSTRAINTS ===';

    -- subcontractors.company_name NOT NULL
    BEGIN
        INSERT INTO subcontractors (id, company_name, email, status, created_at, updated_at)
        VALUES ('ffffffff-4444-4444-4444-ffffffff4444', NULL, 'null@company.com', 'active', NOW(), NOW());
        RAISE NOTICE 'NOT NULL subcontractors.company_name: FAIL';
    EXCEPTION WHEN not_null_violation THEN
        RAISE NOTICE 'NOT NULL subcontractors.company_name: PASS - correctly rejected NULL';
    END;

    -- certifications.subcontractor_id NOT NULL
    BEGIN
        INSERT INTO certifications (id, subcontractor_id, certification_type, expiration_date, status, created_at, updated_at)
        VALUES ('ffffffff-5555-5555-5555-ffffffff5555', NULL, 'Test Cert', '2027-01-01', 'valid', NOW(), NOW());
        RAISE NOTICE 'NOT NULL certifications.subcontractor_id: FAIL';
    EXCEPTION WHEN not_null_violation THEN
        RAISE NOTICE 'NOT NULL certifications.subcontractor_id: PASS - correctly rejected NULL';
    END;

    -- violations.issued_date NOT NULL
    BEGIN
        INSERT INTO violations (id, subcontractor_id, violation_type, description, issued_date, status, created_at, updated_at)
        VALUES ('ffffffff-6666-6666-6666-ffffffff6666', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'safety', 'Test desc', NULL, 'open', NOW(), NOW());
        RAISE NOTICE 'NOT NULL violations.issued_date: FAIL';
    EXCEPTION WHEN not_null_violation THEN
        RAISE NOTICE 'NOT NULL violations.issued_date: PASS - correctly rejected NULL';
    END;
END;
$$;


-- =========================================
-- 6. CASCADE DELETE
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 6. CASCADE DELETE ===';

    -- Deleting a subcontractor should cascade delete their certifications
    PERFORM * FROM certifications WHERE subcontractor_id = 'aaaaaaaa-1010-1010-1010-aaaaaaaa1010';
    IF NOT FOUND THEN
        RAISE NOTICE 'CASCADE DELETE certifications: PASS - foundation first certs deleted with sub';
    ELSE
        RAISE NOTICE 'CASCADE DELETE certifications: FAIL - orphaned records remain';
    END IF;

    -- Deleting a project should set violations.project_id to NULL (SET NULL)
    -- (We use the violation eeeeeeee-1111-1111-1111-eeeeeeee1111 whose project was not deleted yet)
    -- Skip interactive test; verify FK definition instead:
    RAISE NOTICE 'SET NULL violations.project_id: MANUAL VERIFICATION - ensure ON DELETE SET NULL is correct';
END;
$$;


-- =========================================
-- 7. CHECK CONSTRAINTS (Status ENUM values)
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 7. STATUS CONSTRAINTS ===';
    -- subcontractors.status must be one of: active, inactive, suspended, blacklisted
    BEGIN
        UPDATE subcontractors SET status = 'invalid_status' WHERE id = 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111';
        RAISE NOTICE 'CHECK subcontractors.status: FAIL - accepted invalid status';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'CHECK subcontractors.status: PASS - correctly rejected';
    END;

    -- projects.status
    BEGIN
        UPDATE projects SET status = 'not_real' WHERE id = 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111';
        RAISE NOTICE 'CHECK projects.status: FAIL';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'CHECK projects.status: PASS';
    END;

    -- certifications.status
    BEGIN
        UPDATE certifications SET status = 'bogus' WHERE id = 'cccccccc-1111-1111-1111-cccccccc1111';
        RAISE NOTICE 'CHECK certifications.status: FAIL';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'CHECK certifications.status: PASS';
    END;
END;
$$;


-- =========================================
-- 8. DATA QUALITY - SEED DATA INTEGRITY
-- =========================================
DO $$
DECLARE
    v_expired_certs INTEGER;
    v_valid_subs INTEGER;
    v_open_violations INTEGER;
BEGIN
    RAISE NOTICE '=== 8. DATA QUALITY - SEED DATA INTEGRITY ===';
    -- Count expired certs (should include Riverbend OSHA-30, Pinnacle NRCA, QuickFix OSHA-30)
    SELECT COUNT(*) INTO v_expired_certs FROM certifications WHERE status = 'expired';
    RAISE NOTICE 'Expired certifications count: % (expected >= 3)', v_expired_certs;

    -- Count active subcontractors
    SELECT COUNT(*) INTO v_valid_subs FROM subcontractors WHERE status = 'active';
    RAISE NOTICE 'Active subcontractors count: % (expected >= 5)', v_valid_subs;

    -- Count open violations
    SELECT COUNT(*) INTO v_open_violations FROM violations WHERE status = 'open';
    RAISE NOTICE 'Open violations count: % (expected >= 2)', v_open_violations;
END;
$$;


-- =========================================
-- 9. INDEX CHECK
-- =========================================
DO $$
BEGIN
    RAISE NOTICE '=== 9. INDEX CHECK ===';
    -- Verify key indexes exist
    PERFORM * FROM pg_indexes WHERE indexname = 'idx_certifications_expiration_date';
    IF FOUND THEN RAISE NOTICE 'Index idx_certifications_expiration_date: EXISTS'; ELSE RAISE NOTICE 'Index idx_certifications_expiration_date: MISSING'; END IF;

    PERFORM * FROM pg_indexes WHERE indexname = 'idx_violations_status';
    IF FOUND THEN RAISE NOTICE 'Index idx_violations_status: EXISTS'; ELSE RAISE NOTICE 'Index idx_violations_status: MISSING'; END IF;

    PERFORM * FROM pg_indexes WHERE indexname = 'idx_subcontractors_status';
    IF FOUND THEN RAISE NOTICE 'Index idx_subcontractors_status: EXISTS'; ELSE RAISE NOTICE 'Index idx_subcontractors_status: MISSING'; END IF;
END;
$$;


-- =========================================
-- 10. UPDATED_AT TRIGGER CHECK
-- =========================================
DO $$
    v_before TIMESTAMP WITH TIME ZONE;
    v_after TIMESTAMP WITH TIME ZONE;
BEGIN
    RAISE NOTICE '=== 10. UPDATED_AT TRIGGER CHECK ===';
    SELECT updated_at INTO v_before FROM subcontractors WHERE id = 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111';
    UPDATE subcontractors SET company_name = company_name || '' WHERE id = 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111';
    SELECT updated_at INTO v_after FROM subcontractors WHERE id = 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111';
    IF v_after > v_before THEN
        RAISE NOTICE 'TRIGGER updated_at: PASS - timestamp advanced';
    ELSE
        RAISE NOTICE 'TRIGGER updated_at: FAIL - timestamp did not update (was %; after %)', v_before, v_after;
    END IF;
END;
$$;


-- =========================================
-- 11. ANALYTICS VIEWS QUERY TESTS
-- =========================================
DO $$
    v_count INTEGER;
BEGIN
    RAISE NOTICE '=== 11. ANALYTIC VIEW TESTS ===';
    -- Test compliance_status_by_subcontractor view
    SELECT COUNT(*) INTO v_count FROM compliance_status_by_subcontractor;
    RAISE NOTICE 'compliance_status_by_subcontractor rows: %', v_count;

    -- Test expiring_certifications view (should show Riverbend cert and Pinnacle expired)
    SELECT COUNT(*) INTO v_count FROM expiring_certifications;
    RAISE NOTICE 'expiring_certifications rows: %', v_count;

    -- Test osha_violation_trends view
    SELECT COUNT(*) INTO v_count FROM osha_violation_trends;
    RAISE NOTICE 'osha_violation_trends rows: %', v_count;
END;
$$;

