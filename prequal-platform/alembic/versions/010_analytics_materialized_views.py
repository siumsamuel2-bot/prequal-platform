"""Analytics Materialized Views for Dashboard API

Revision ID: 010_analytics_materialized_views
Revises: 009_db_performance_indexes
Create Date: 2026-05-25

Data Engineer: Analytics schema for Dashboard & Compliance Metrics.
Provides materialized views for the 4 API endpoints defined in MID-58.

Owner: Data Engineer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '010_analytics_materialized_views'
down_revision = '009_db_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. mv_compliance_summary — used by GET /api/compliance/summary
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_compliance_summary AS
        SELECT
            COUNT(DISTINCT s.id) AS total_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.id END) AS active_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'suspended' THEN s.id END) AS suspended_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'blacklisted' THEN s.id END) AS blacklisted_subcontractors,
            -- Compliant: has at least one valid cert and no open violations
            COUNT(DISTINCT CASE
                WHEN s.status = 'active'
                    AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
                    AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
                THEN s.id END) AS compliant_subcontractors,
            -- Expiring soon (within 30 days)
            COUNT(DISTINCT CASE
                WHEN EXISTS (SELECT 1 FROM certifications c
                    WHERE c.subcontractor_id = s.id
                    AND c.status = 'valid'
                    AND c.expiration_date <= CURRENT_DATE + INTERVAL '30 days'
                    AND c.expiration_date >= CURRENT_DATE)
                THEN s.id END) AS expiring_soon_30d,
            -- Expiring within 60 days
            COUNT(DISTINCT CASE
                WHEN EXISTS (SELECT 1 FROM certifications c
                    WHERE c.subcontractor_id = s.id
                    AND c.status = 'valid'
                    AND c.expiration_date <= CURRENT_DATE + INTERVAL '60 days'
                    AND c.expiration_date >= CURRENT_DATE)
                THEN s.id END) AS expiring_soon_60d,
            -- Open violations (OSHA + non-OSHA)
            (SELECT COUNT(*) FROM violations WHERE status = 'open') AS open_violations,
            -- OSHA-specific open violations
            (SELECT COUNT(*) FROM violations WHERE status = 'open' AND is_osha_violation = TRUE) AS open_osha_violations,
            -- Total penalties from open violations
            COALESCE((SELECT SUM(penalty_amount) FROM violations WHERE status = 'open'), 0) AS total_open_penalties,
            -- Certification stats
            (SELECT COUNT(*) FROM certifications WHERE status = 'valid') AS valid_certifications,
            (SELECT COUNT(*) FROM certifications WHERE status = 'expired') AS expired_certifications,
            (SELECT COUNT(*) FROM certifications WHERE status = 'pending_verification') AS pending_verification_certs,
            CURRENT_TIMESTAMP AS computed_at
        FROM subcontractors s;
    """)

    # Unique index on the single-row materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_compliance_summary_computed
        ON mv_compliance_summary(computed_at);
    """)

    # =====================================================================
    # 2. mv_compliance_trends — used by GET /api/compliance/trends
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_compliance_trends AS
        WITH daily_compliance AS (
            SELECT
                generate_series::date AS trend_date,
                -- Count of active subcontractors on that date
                COUNT(DISTINCT CASE WHEN s.created_at <= generate_series AND (s.status != 'inactive' OR s.updated_at > generate_series) THEN s.id END) AS active_subcontractors,
                -- Count of valid certs on that date
                COUNT(DISTINCT CASE WHEN c.created_at <= generate_series AND c.expiration_date >= generate_series AND c.status = 'valid' THEN c.id END) AS valid_certifications,
                -- Count of expired certs on that date (by expiration)
                COUNT(DISTINCT CASE WHEN c.created_at <= generate_series AND c.expiration_date < generate_series THEN c.id END) AS expired_certifications,
                -- Count of open violations on that date
                COUNT(DISTINCT CASE WHEN v.issued_date <= generate_series AND (v.resolution_date IS NULL OR v.resolution_date > generate_series) AND v.status = 'open' THEN v.id END) AS open_violations,
                -- OSHA open violations on that date
                COUNT(DISTINCT CASE WHEN v.issued_date <= generate_series AND (v.resolution_date IS NULL OR v.resolution_date > generate_series) AND v.status = 'open' AND v.is_osha_violation = TRUE THEN v.id END) AS open_osha_violations
            FROM generate_series(CURRENT_DATE - INTERVAL '365 days', CURRENT_DATE, INTERVAL '1 day') AS generate_series
            LEFT JOIN subcontractors s ON TRUE
            LEFT JOIN certifications c ON c.subcontractor_id = s.id
            LEFT JOIN violations v ON v.subcontractor_id = s.id
            GROUP BY generate_series
        )
        SELECT
            trend_date,
            active_subcontractors,
            valid_certifications,
            expired_certifications,
            open_violations,
            open_osha_violations,
            -- Compliant % (subcontractors with valid cert and no open violation)
            CASE
                WHEN active_subcontractors > 0 THEN
                    (COUNT(DISTINCT CASE
                        WHEN NOT EXISTS (SELECT 1 FROM violations v2 WHERE v2.subcontractor_id = s.id AND v2.status = 'open')
                            AND EXISTS (SELECT 1 FROM certifications c2 WHERE c2.subcontractor_id = s.id AND c2.status = 'valid' AND c2.expiration_date >= trend_date)
                        THEN s.id END) * 100.0 / active_subcontractors)
                ELSE 0
            END AS compliance_percentage,
            CURRENT_TIMESTAMP AS computed_at
        FROM daily_compliance
        LEFT JOIN subcontractors s ON TRUE
        GROUP BY trend_date, active_subcontractors, valid_certifications, expired_certifications, open_violations, open_osha_violations
        ORDER BY trend_date;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_compliance_trends_date
        ON mv_compliance_trends(trend_date);
    """)

    # =====================================================================
    # 3. mv_certification_status — used by GET /api/compliance/summary & export
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_certification_status AS
        SELECT
            s.id AS subcontractor_id,
            s.company_name,
            s.email,
            s.status AS subcontractor_status,
            c.id AS certification_id,
            c.certification_type,
            c.certification_number,
            c.issue_date,
            c.expiration_date,
            c.status AS certification_status,
            c.verification_status,
            CASE
                WHEN c.expiration_date < CURRENT_DATE THEN 'expired'
                WHEN c.expiration_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'critical'
                WHEN c.expiration_date <= CURRENT_DATE + INTERVAL '30 days' THEN 'warning'
                WHEN c.expiration_date <= CURRENT_DATE + INTERVAL '60 days' THEN 'attention'
                ELSE 'valid'
            END AS expiration_bucket,
            CURRENT_DATE - c.expiration_date AS days_until_expiration,
            c.verified_at,
            c.created_at,
            CURRENT_TIMESTAMP AS computed_at
        FROM subcontractors s
        JOIN certifications c ON c.subcontractor_id = s.id
        WHERE s.status = 'active'
        ORDER BY c.expiration_date ASC;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_cert_status_cert_id
        ON mv_certification_status(certification_id);
    """)

    op.execute("""
        CREATE INDEX idx_mv_cert_status_exp_bucket
        ON mv_certification_status(expiration_bucket);
    """)

    op.execute("""
        CREATE INDEX idx_mv_cert_status_sub_id
        ON mv_certification_status(subcontractor_id);
    """)

    # =====================================================================
    # 4. mv_project_compliance — used by GET /api/compliance/summary
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_project_compliance AS
        SELECT
            p.id AS project_id,
            p.project_name,
            p.project_number,
            p.status AS project_status,
            p.start_date,
            p.estimated_end_date,
            COUNT(DISTINCT ps.subcontractor_id) AS total_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'active' THEN ps.subcontractor_id END) AS active_subcontractors,
            COUNT(DISTINCT CASE WHEN s.status = 'suspended' THEN ps.subcontractor_id END) AS suspended_subcontractors,
            -- Compliant subcontractors on this project
            COUNT(DISTINCT CASE
                WHEN s.status = 'active'
                    AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid')
                    AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open')
                THEN s.id END) AS compliant_subcontractors,
            -- Open violations on this project
            COUNT(DISTINCT CASE WHEN v.status = 'open' THEN v.id END) AS open_violations,
            COUNT(DISTINCT CASE WHEN v.status = 'open' AND v.is_osha_violation = TRUE THEN v.id END) AS open_osha_violations,
            SUM(CASE WHEN v.status = 'open' THEN v.penalty_amount ELSE 0 END) AS total_open_penalties,
            -- Expiring certs within 30 days on this project
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1 FROM certifications c
                WHERE c.subcontractor_id = s.id
                AND c.status = 'valid'
                AND c.expiration_date <= CURRENT_DATE + INTERVAL '30 days'
                AND c.expiration_date >= CURRENT_DATE
            ) THEN s.id END) AS expiring_soon_subcontractors,
            CURRENT_TIMESTAMP AS computed_at
        FROM projects p
        LEFT JOIN project_subcontractors ps ON ps.project_id = p.id AND ps.status = 'active'
        LEFT JOIN subcontractors s ON s.id = ps.subcontractor_id
        LEFT JOIN violations v ON v.project_id = p.id
        GROUP BY p.id, p.project_name, p.project_number, p.status, p.start_date, p.estimated_end_date
        ORDER BY p.created_at DESC;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_project_compliance_project
        ON mv_project_compliance(project_id);
    """)

    # =====================================================================
    # 5. mv_recent_alerts — used by GET /api/alerts/recent
    # =====================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW mv_recent_alerts AS
        SELECT
            an.id AS alert_id,
            an.certification_id,
            an.alert_type,
            an.scheduled_for,
            an.sent_at,
            an.status,
            an.method,
            an.recipient,
            an.subject,
            an.acknowledged_at,
            an.days_until_expiration,
            an.created_at,
            c.certification_type,
            c.expiration_date,
            s.id AS subcontractor_id,
            s.company_name AS subcontractor_name,
            s.email AS subcontractor_email,
            CURRENT_TIMESTAMP AS computed_at
        FROM alert_notifications an
        JOIN certifications c ON c.id = an.certification_id
        JOIN subcontractors s ON s.id = c.subcontractor_id
        WHERE an.created_at >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY an.created_at DESC;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_recent_alerts_alert_id
        ON mv_recent_alerts(alert_id);
    """)

    op.execute("""
        CREATE INDEX idx_mv_recent_alerts_created
        ON mv_recent_alerts(created_at DESC);
    """)

    op.execute("""
        CREATE INDEX idx_mv_recent_alerts_status
        ON mv_recent_alerts(status);
    """)


def downgrade() -> None:
    # Drop materialized views in reverse order
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_recent_alerts CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_project_compliance CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_certification_status CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_compliance_trends CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_compliance_summary CASCADE;")
