-- ================================================================
-- Production Migration Script
-- Schema: 06_production_migration.sql
-- Purpose: Bridge SQL schema (01-05) with Alembic migrations and
--          prepare production-ready database state.
-- Dependencies: 01_core_tables, 02_expiration_tracking,
--               03_osha_integration, 04_state_credentials,
--               05_data_quality_monitoring
-- Author: Data Engineer
-- ================================================================

-- ================================================================
-- 1. COLUMN ALIGNMENT: Ensure SQL schema matches Alembic models
-- ================================================================

-- Users table (required by compliance.py models and foreign keys)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_id ON users(id);

-- Organizations table (required by compliance.py models)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_id ON organizations(id);

-- Teams table (required by compliance.py models)
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    org_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_teams_org_id ON teams(org_id);
CREATE INDEX idx_teams_id ON teams(id);

-- Uploaded credentials table (referenced by compliance.py models)
CREATE TABLE IF NOT EXISTS uploaded_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subcontractor_id UUID REFERENCES subcontractors(id) ON DELETE CASCADE,
    credential_type VARCHAR(100) NOT NULL,
    file_url TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_uploaded_credentials_subcontractor_id ON uploaded_credentials(subcontractor_id);

-- Stub for notification_delivery_logs if the alembic migration hasn't run
CREATE TABLE IF NOT EXISTS notification_delivery_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_notification_id UUID REFERENCES alert_notifications(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notification_delivery_logs_alert_notification_id ON notification_delivery_logs(alert_notification_id);

-- ================================================================
-- 2. ADD PRODUCTION CONSTRAINTS NOT IN SQL SCHEMA
-- ================================================================

-- Foreign key from certifications.verified_by -> users.id
ALTER TABLE certifications
    ADD CONSTRAINT fk_certifications_verified_by_users
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL
    NOT VALID;

-- Foreign key from alert_preferences.user_id -> users.id
ALTER TABLE alert_preferences
    ADD CONSTRAINT fk_alert_preferences_user_id_users
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    NOT VALID;

-- Foreign key from certification_renewals.requested_by -> users.id
ALTER TABLE certification_renewals
    ADD CONSTRAINT fk_certification_renewals_requested_by_users
    FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE CASCADE
    NOT VALID;

-- Foreign key from certification_renewals.reviewed_by -> users.id
ALTER TABLE certification_renewals
    ADD CONSTRAINT fk_certification_renewals_reviewed_by_users
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
    NOT VALID;

-- ================================================================
-- 3. ALIGN subcontractors WITH ENCRYPTED COLUMNS (MID-75)
-- ================================================================
-- These columns are added by alembic 015/016, but we include them
-- here for environments applying SQL schema directly.
-- NOTE: Alembic takes precedence for managed environments.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_ein'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_ein VARCHAR(500);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_contact_first_name'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_contact_first_name VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_contact_last_name'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_contact_last_name VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_email'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_email VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_phone'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_phone VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_address_line1'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_address_line1 VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_address_line2'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_address_line2 VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_city'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_city VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_state'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_state VARCHAR(700);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'subcontractors' AND column_name = 'encrypted_zip_code'
    ) THEN
        ALTER TABLE subcontractors ADD COLUMN encrypted_zip_code VARCHAR(700);
    END IF;
END $$;

-- ================================================================
-- 4. PRODUCTION-PERFORMANCE INDEX FOR COMPLIANCE LOOKUPS
-- ================================================================
-- Composite indexes for the most common query patterns

-- Fast compliance status lookup by subcontractor + cert status + expiration
CREATE INDEX IF NOT EXISTS idx_certifications_subcontractor_status_expiration
    ON certifications(subcontractor_id, status, expiration_date);

-- Fast violation lookup by subcontractor + status + issued_date
CREATE INDEX IF NOT EXISTS idx_violations_subcontractor_status_issued_date
    ON violations(subcontractor_id, status, issued_date);

-- Fast compliance report: active subcontractors with open violations
CREATE INDEX IF NOT EXISTS idx_subcontractors_status_id
    ON subcontractors(status, id);

-- Fast lookup for compliance dashboard
CREATE INDEX IF NOT EXISTS idx_violations_status_is_osha
    ON violations(status, is_osha_violation) WHERE is_osha_violation = TRUE;

-- ================================================================
-- 5. DATA QUALITY CHECKS: PRODUCTION HARDENING
-- ================================================================
-- Add additional data quality checks that seed data already validates

INSERT INTO data_quality_checks (id, check_name, check_type, table_name, column_name, description, check_query, expected_result, alert_threshold, is_active, priority, created_at, updated_at)
VALUES
    ('dqc-0001-0001-0001-000000000009', 'subcontractors_ein_not_null', 'completeness', 'subcontractors', 'ein', 'EIN should not be null for production records', 'SELECT COUNT(*) FROM subcontractors WHERE ein IS NULL OR TRIM(ein) = ''''', '0', 1.0, FALSE, 'medium', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000010', 'certifications_subcontractor_exists', 'referential', 'certifications', 'subcontractor_id', 'All certifications must reference valid subcontractors', 'SELECT COUNT(*) FROM certifications c LEFT JOIN subcontractors s ON c.subcontractor_id = s.id WHERE s.id IS NULL', '0', 1.0, TRUE, 'critical', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000011', 'violations_subcontractor_exists', 'referential', 'violations', 'subcontractor_id', 'All violations must reference valid subcontractors', 'SELECT COUNT(*) FROM violations v LEFT JOIN subcontractors s ON v.subcontractor_id = s.id WHERE s.id IS NULL', '0', 1.0, TRUE, 'critical', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000012', 'projects_status_valid', 'format', 'projects', 'status', 'Project status must be within allowed values', 'SELECT COUNT(*) FROM projects WHERE status NOT IN (''planning'', ''active'', ''on_hold'', ''completed'', ''cancelled'')', '0', 1.0, TRUE, 'high', NOW(), NOW());

-- ================================================================
-- 6. SYNC HEALTH BASELINE FOR PRODUCTION
-- ================================================================

INSERT INTO sync_health (id, source_name, source_type, sync_run_log_id, health_status, last_successful_sync_at, last_failed_sync_at, last_failure_reason, sync_frequency, expected_next_sync_at, consecutive_failures, consecutive_successes, average_records_processed, average_processing_time_ms, created_at, updated_at)
VALUES
    ('11111111-5555-5555-5555-111111111555', 'production_init', 'manual', NULL, 'healthy', NOW(), NULL, NULL, 'once', NULL, 0, 1, 0, 0, NOW(), NOW());

-- ================================================================
-- 7. COMMENTS AND DOCUMENTATION
-- ================================================================

COMMENT ON TABLE subcontractors IS 'Core entity: subcontractor companies with compliance tracking. Encrypted columns added by MID-75 (Alembic 015/016).';
COMMENT ON TABLE certifications IS 'Certifications held by subcontractors, with expiration tracking and verification status.';
COMMENT ON TABLE violations IS 'Compliance violations (OSHA and other) linked to subcontractors and optionally projects.';
COMMENT ON TABLE projects IS 'Construction projects that subcontractors are assigned to.';
COMMENT ON TABLE project_subcontractors IS 'Many-to-many link between projects and subcontractors, with role and insurance/bond dates.';
COMMENT ON TABLE state_credential_records IS 'External state licensing board data, synced and matched to subcontractors.';
COMMENT ON TABLE sync_run_logs IS 'Pipeline execution audit log for all data integrations.';
COMMENT ON TABLE data_quality_checks IS 'Configurable data quality rules evaluated against production tables.';

