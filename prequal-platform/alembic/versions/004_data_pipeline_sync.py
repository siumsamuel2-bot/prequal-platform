"""004: Add comprehensive data pipeline tables for sync jobs, data quality, state credentials, and analytics materialized views.

Migration ID: 004
Description: Creates tables and views for:
- Data sync job runs (sync_run_logs)
- Data quality monitoring (data_quality_checks, data_quality_results)
- State credential database sync (state_credential_records)
- Analytics materialized views for dashboard consumption
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

revision = "004_data_pipeline_sync"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. sync_run_logs — audit trail for all scheduled and triggered jobs
    # ------------------------------------------------------------------
    op.create_table(
        "sync_run_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="schedule"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("idx_sync_run_logs_job_name", "sync_run_logs", ["job_name"])
    op.create_index("idx_sync_run_logs_status", "sync_run_logs", ["status"])
    op.create_index("idx_sync_run_logs_started_at", "sync_run_logs", ["started_at"])
    op.create_index("idx_sync_run_logs_created_at", "sync_run_logs", ["created_at"])
    op.create_index("idx_sync_run_logs_triggered_by", "sync_run_logs", ["triggered_by"])

    # ------------------------------------------------------------------
    # 2. data_quality_checks — configurable validation rules
    # ------------------------------------------------------------------
    op.create_table(
        "data_quality_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("check_name", sa.String(100), nullable=False, unique=True),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("column_name", sa.String(100), nullable=True),
        sa.Column("check_type", sa.String(50), nullable=False),  # not_null, uniqueness, range, referential_integrity, freshness, custom
        sa.Column("check_query", sa.Text(), nullable=True),
        sa.Column("expected_threshold", sa.Float(), nullable=True),  # e.g., 0.95 for 95% not_null
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),  # warning, error, critical
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("idx_data_quality_checks_table_name", "data_quality_checks", ["table_name"])
    op.create_index("idx_data_quality_checks_check_type", "data_quality_checks", ["check_type"])
    op.create_index("idx_data_quality_checks_is_active", "data_quality_checks", ["is_active"])
    op.create_index("idx_data_quality_checks_severity", "data_quality_checks", ["severity"])

    # ------------------------------------------------------------------
    # 3. data_quality_results — per-run check outcomes
    # ------------------------------------------------------------------
    op.create_table(
        "data_quality_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("data_quality_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sync_run_id", UUID(as_uuid=True), sa.ForeignKey("sync_run_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),  # passed, failed, error, warning
        sa.Column("records_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_rate", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("sample_failures", sa.JSON(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_data_quality_results_check_id", "data_quality_results", ["check_id"])
    op.create_index("idx_data_quality_results_sync_run_id", "data_quality_results", ["sync_run_id"])
    op.create_index("idx_data_quality_results_status", "data_quality_results", ["status"])
    op.create_index("idx_data_quality_results_executed_at", "data_quality_results", ["executed_at"])

    # ------------------------------------------------------------------
    # 4. state_credential_records — cache of state credential DB records
    # ------------------------------------------------------------------
    op.create_table(
        "state_credential_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False, index=True),
        sa.Column("credential_number", sa.String(100), nullable=False),
        sa.Column("credential_type", sa.String(100), nullable=False),
        sa.Column("issuing_state", sa.String(100), nullable=False),
        sa.Column("holder_name", sa.String(255), nullable=False),
        sa.Column("holder_address", sa.Text(), nullable=True),
        sa.Column("holder_city", sa.String(100), nullable=True),
        sa.Column("holder_state", sa.String(50), nullable=True),
        sa.Column("holder_zip", sa.String(20), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("external_source_id", sa.String(255), nullable=True),
        sa.Column("external_source_url", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("idx_state_credential_state_code", "state_credential_records", ["state_code"])
    op.create_index("idx_state_credential_credential_number", "state_credential_records", ["credential_number"])
    op.create_index("idx_state_credential_holder_name", "state_credential_records", ["holder_name"])
    op.create_index("idx_state_credential_status", "state_credential_records", ["status"])
    op.create_index("idx_state_credential_expiration", "state_credential_records", ["expiration_date"])
    op.create_index(
        "idx_state_credential_unique",
        "state_credential_records",
        ["state_code", "credential_number", "credential_type"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 5. Seed data quality checks (built-in rules)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO data_quality_checks (id, check_name, table_name, column_name, check_type, check_query, expected_threshold, severity, is_active, description)
        VALUES 
            (gen_random_uuid(), 'osha_data_freshness', 'osha_data_freshness', 'last_updated', 'freshness', 
             'SELECT COUNT(*) FROM osha_data_freshness WHERE last_updated < NOW() - INTERVAL ''25 hours''', 
             0, 'critical', true, 'OSHA data must be updated within the last 25 hours'),
            (gen_random_uuid(), 'subcontractor_email_not_null', 'subcontractors', 'email', 'not_null', 
             'SELECT COUNT(*) FROM subcontractors WHERE email IS NULL OR email = ''''', 
             0, 'error', true, 'All subcontractors must have a valid email address'),
            (gen_random_uuid(), 'certification_expiration_valid', 'certifications', 'expiration_date', 'range', 
             'SELECT COUNT(*) FROM certifications WHERE expiration_date < issue_date', 
             0, 'error', true, 'Certification expiration date must be after issue date'),
            (gen_random_uuid(), 'violation_subcontractor_exists', 'violations', 'subcontractor_id', 'referential_integrity', 
             'SELECT COUNT(*) FROM violations v LEFT JOIN subcontractors s ON v.subcontractor_id = s.id WHERE s.id IS NULL', 
             0, 'error', true, 'All violations must reference valid subcontractors'),
            (gen_random_uuid(), 'state_credential_unique', 'state_credential_records', NULL, 'uniqueness', 
             'SELECT COUNT(*) FROM (SELECT state_code, credential_number, credential_type FROM state_credential_records GROUP BY state_code, credential_number, credential_type HAVING COUNT(*) > 1) t', 
             0, 'error', true, 'State credentials must be unique by state_code + credential_number + type')
        """
    )

    # ------------------------------------------------------------------
    # 6. Analytics views (compliance reporting)
    # ------------------------------------------------------------------

    # Materialized view: compliance_summary for fast dashboard queries
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_compliance_summary AS
        SELECT 
            s.id AS subcontractor_id,
            s.company_name,
            s.status AS subcontractor_status,
            COUNT(DISTINCT CASE WHEN c.status = 'valid' AND c.expiration_date >= CURRENT_DATE THEN c.id END) AS active_certifications,
            COUNT(DISTINCT CASE WHEN c.status = 'expired' OR c.expiration_date < CURRENT_DATE THEN c.id END) AS expired_certifications,
            COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days' THEN c.id END) AS expiring_30_days,
            COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days' THEN c.id END) AS expiring_7_days,
            COUNT(DISTINCT CASE WHEN v.status = 'open' AND v.is_osha_violation = TRUE THEN v.id END) AS open_osha_violations,
            COUNT(DISTINCT CASE WHEN v.status = 'resolved' AND v.is_osha_violation = TRUE THEN v.id END) AS resolved_osha_violations,
            COALESCE(SUM(CASE WHEN v.is_osha_violation = TRUE THEN v.penalty_amount ELSE 0 END), 0) AS total_penalties,
            MAX(c.expiration_date) AS latest_cert_expiration,
            MIN(CASE WHEN c.expiration_date >= CURRENT_DATE THEN c.expiration_date END) AS nearest_expiration
        FROM 
            subcontractors s
        LEFT JOIN 
            certifications c ON s.id = c.subcontractor_id
        LEFT JOIN 
            violations v ON s.id = v.subcontractor_id
        GROUP BY 
            s.id, s.company_name, s.status;
        """
    )
    op.create_index("idx_mv_compliance_summary_subcontractor_id", "mv_compliance_summary", ["subcontractor_id"])
    op.create_index("idx_mv_compliance_summary_status", "mv_compliance_summary", ["subcontractor_status"])

    # Materialized view: violation trends by month
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_violation_trends AS
        SELECT 
            DATE_TRUNC('month', v.issued_date) AS violation_month,
            COUNT(*) AS total_violations,
            COUNT(DISTINCT CASE WHEN v.is_osha_violation = TRUE THEN v.id END) AS osha_violations,
            COUNT(DISTINCT CASE WHEN v.status = 'open' THEN v.id END) AS open_violations,
            COUNT(DISTINCT CASE WHEN v.status = 'resolved' THEN v.id END) AS resolved_violations,
            COALESCE(SUM(v.penalty_amount), 0) AS total_penalties,
            AVG(v.gravity_score) AS avg_gravity_score,
            COUNT(DISTINCT v.subcontractor_id) AS contractors_affected
        FROM 
            violations v
        GROUP BY 
            DATE_TRUNC('month', v.issued_date);
        """
    )
    op.create_index("idx_mv_violation_trends_month", "mv_violation_trends", ["violation_month"])

    # Materialized view: certification status overview
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_certification_status AS
        SELECT 
            c.certification_type,
            COUNT(*) AS total_certs,
            COUNT(DISTINCT CASE WHEN c.status = 'valid' AND c.expiration_date >= CURRENT_DATE THEN c.id END) AS valid_certs,
            COUNT(DISTINCT CASE WHEN c.status = 'expired' OR c.expiration_date < CURRENT_DATE THEN c.id END) AS expired_certs,
            COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days' THEN c.id END) AS expiring_soon,
            AVG(CASE WHEN c.status = 'valid' THEN (c.expiration_date - CURRENT_DATE) END) AS avg_days_until_expiration,
            MIN(c.expiration_date) FILTER (WHERE c.expiration_date >= CURRENT_DATE) AS nearest_expiration
        FROM 
            certifications c
        GROUP BY 
            c.certification_type;
        """
    )
    op.create_index("idx_mv_certification_status_type", "mv_certification_status", ["certification_type"])

    # Materialized view: project compliance overview
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_project_compliance AS
        SELECT 
            p.id AS project_id,
            p.project_name,
            p.status AS project_status,
            COUNT(DISTINCT ps.subcontractor_id) AS total_subcontractors,
            COUNT(DISTINCT CASE WHEN c.status = 'valid' AND c.expiration_date >= CURRENT_DATE THEN c.subcontractor_id END) AS compliant_subcontractors,
            COUNT(DISTINCT CASE WHEN v.status = 'open' THEN v.id END) AS open_violations,
            COALESCE(SUM(v.penalty_amount), 0) AS total_penalties,
            COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days' THEN c.subcontractor_id END) AS contractors_expiring_soon
        FROM 
            projects p
        LEFT JOIN 
            project_subcontractors ps ON p.id = ps.project_id AND ps.status = 'active'
        LEFT JOIN 
            subcontractors s ON ps.subcontractor_id = s.id
        LEFT JOIN 
            certifications c ON s.id = c.subcontractor_id
        LEFT JOIN 
            violations v ON s.id = v.subcontractor_id
        GROUP BY 
            p.id, p.project_name, p.status;
        """
    )
    op.create_index("idx_mv_project_compliance_project_id", "mv_project_compliance", ["project_id"])



def downgrade() -> None:
    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_project_compliance CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_certification_status CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_violation_trends CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_compliance_summary CASCADE")

    # Drop tables
    op.execute("DROP TABLE IF EXISTS state_credential_records CASCADE")
    op.execute("DROP TABLE IF EXISTS data_quality_results CASCADE")
    op.execute("DROP TABLE IF EXISTS data_quality_checks CASCADE")
    op.execute("DROP TABLE IF EXISTS sync_run_logs CASCADE")
