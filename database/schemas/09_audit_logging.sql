-- =============================================================================
-- 09_audit_logging.sql — Audit logging for data access (MID-434)
-- Owner: Data Engineer
--
-- Provides:
--   1. audit_logs table: immutable, insert-only audit trail for all
--      read/write operations on customer data.
--   2. Insert-only enforcement via trigger (UPDATE/DELETE prohibited).
--   3. Indexes for compliance query patterns.
--   4. Compliance analytics views used by the ELK export pipeline and the
--      compliance audit API.
--
-- Schema contract mirrors backend/app/models/audit.py (AuditLog).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Core audit log table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Actor
    user_id             VARCHAR(255),
    user_email          VARCHAR(255),
    user_role           VARCHAR(50),

    -- Operation
    operation_type      VARCHAR(50)  NOT NULL,
    resource_type       VARCHAR(100) NOT NULL,
    resource_id         VARCHAR(255),

    -- Data-change snapshots (write ops only)
    old_value           JSONB,
    new_value           JSONB,

    -- Request context
    context             JSONB,
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    session_id          VARCHAR(255),
    request_id          VARCHAR(255),
    organization_id     VARCHAR(255),

    -- Compliance / ELK
    compliance_tags     TEXT[]       DEFAULT '{}',
    data_classification VARCHAR(50)  DEFAULT 'internal',
    retention_until     TIMESTAMPTZ,

    -- Timestamps
    logged_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ  DEFAULT now()
);

COMMENT ON TABLE audit_logs IS
    'Immutable audit trail of all read/write operations on customer data. '
    'Insert-only; UPDATE and DELETE are blocked by trigger. '
    'Shipped to Elasticsearch (ELK) by backend/app/services/audit_elk_exporter.py.';

-- -----------------------------------------------------------------------------
-- 2. Indexes (match SQLAlchemy model; support compliance query patterns)
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id          ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_operation_type   ON audit_logs (operation_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_resource_type    ON audit_logs (resource_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_resource_id      ON audit_logs (resource_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_organization_id  ON audit_logs (organization_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_logged_at        ON audit_logs (logged_at);
-- Composite for "who touched this resource and when"
CREATE INDEX IF NOT EXISTS idx_audit_logs_composite
    ON audit_logs (resource_type, resource_id, logged_at);
-- High-risk operation scan
CREATE INDEX IF NOT EXISTS idx_audit_logs_high_risk
    ON audit_logs (logged_at)
    WHERE operation_type IN ('DELETE', 'EXPORT');

-- -----------------------------------------------------------------------------
-- 3. Insert-only enforcement (no UPDATE / DELETE on audit trail)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_logs_block_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is insert-only: % is not permitted', TG_OP
        USING ERRCODE = 'raise_exception';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_block_mutation();

DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_block_mutation();

-- -----------------------------------------------------------------------------
-- 4. Compliance analytics views
-- -----------------------------------------------------------------------------

-- Full access trail per resource, one row per event, newest first.
CREATE OR REPLACE VIEW audit_resource_access AS
SELECT
    resource_type,
    resource_id,
    operation_type,
    user_id,
    user_email,
    organization_id,
    data_classification,
    compliance_tags,
    ip_address,
    logged_at
FROM audit_logs
ORDER BY logged_at DESC;

-- Per-user activity rollup (compliance review of who accessed what, and how much).
CREATE OR REPLACE VIEW audit_user_activity_daily AS
SELECT
    date_trunc('day', logged_at) AS day,
    user_id,
    user_email,
    operation_type,
    resource_type,
    count(*) AS event_count
FROM audit_logs
GROUP BY 1, 2, 3, 4, 5;

-- High-risk events (DELETE / EXPORT) for compliance alerting.
CREATE OR REPLACE VIEW audit_high_risk_events AS
SELECT
    id,
    logged_at,
    user_id,
    user_email,
    user_role,
    operation_type,
    resource_type,
    resource_id,
    organization_id,
    ip_address,
    context
FROM audit_logs
WHERE operation_type IN ('DELETE', 'EXPORT')
ORDER BY logged_at DESC;

-- Rows not yet shipped to ELK (exporter watermark support). The exporter
-- tracks the last shipped logged_at/id; this view shows the backlog.
CREATE OR REPLACE VIEW audit_elk_export_backlog AS
SELECT
    id,
    logged_at,
    operation_type,
    resource_type,
    resource_id,
    user_id,
    organization_id,
    data_classification,
    compliance_tags,
    old_value,
    new_value,
    context
FROM audit_logs
ORDER BY logged_at ASC, id ASC;
