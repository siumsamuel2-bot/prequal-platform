"""014: Data Quality Monitoring & Analytics Pipeline

Migration ID: 014
Description:
- Adds data quality monitoring tables and views (014a)
- Adds data retention and archival support (014b)
- Adds pipeline performance monitoring (014c)
- Adds analytics views for subcontractor compliance trends (014d)

Owner: Data Engineer
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "014_data_quality_monitoring"
down_revision = "013_state_compliance_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ====================================================================
    # 014a: Data Quality Monitoring Schema Additions
    # ====================================================================

    # sync_health_daily — daily rollup of sync job health metrics
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_health_daily (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            date DATE NOT NULL UNIQUE,
            job_name VARCHAR(100) NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            runs_total INT NOT NULL DEFAULT 0,
            runs_successful INT NOT NULL DEFAULT 0,
            runs_failed INT NOT NULL DEFAULT 0,
            records_processed INT NOT NULL DEFAULT 0,
            records_inserted INT NOT NULL DEFAULT 0,
            records_updated INT NOT NULL DEFAULT 0,
            records_failed INT NOT NULL DEFAULT 0,
            avg_match_rate NUMERIC(5,4),
            avg_error_rate NUMERIC(5,4),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.create_index("idx_sync_health_daily_date", "sync_health_daily", ["date"])
    op.create_index("idx_sync_health_daily_job_name", "sync_health_daily", ["job_name"])

    # data_quality_alerts — threshold-based alerts for data quality degradation
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS data_quality_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            alert_type VARCHAR(50) NOT NULL,  -- sync_failure, match_rate_drop, error_rate_spike, stale_data
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',  -- warning, error, critical
            source_table VARCHAR(100),
            source_job VARCHAR(100),
            message TEXT NOT NULL,
            threshold_value NUMERIC(10,4),
            actual_value NUMERIC(10,4),
            is_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
            acknowledged_at TIMESTAMP WITH TIME ZONE,
            acknowledged_by VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.create_index("idx_data_quality_alerts_type", "data_quality_alerts", ["alert_type"])
    op.create_index("idx_data_quality_alerts_severity", "data_quality_alerts", ["severity"])
    op.create_index("idx_data_quality_alerts_created", "data_quality_alerts", ["created_at"])
    op.create_index("idx_data_quality_alerts_acknowledged", "data_quality_alerts", ["is_acknowledged"])

    # Materialized view: mv_sync_health_dashboard
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sync_health_dashboard AS
        SELECT
            srl.job_name,
            srl.job_type,
            COUNT(*) AS total_runs,
            COUNT(*) FILTER (WHERE srl.status = 'completed') AS successful_runs,
            COUNT(*) FILTER (WHERE srl.status = 'failed') AS failed_runs,
            COUNT(*) FILTER (WHERE srl.status = 'partial') AS partial_runs,
            SUM(srl.records_processed) AS total_records_processed,
            SUM(srl.records_inserted) AS total_records_inserted,
            SUM(srl.records_updated) AS total_records_updated,
            SUM(srl.records_failed) AS total_records_failed,
            CASE
                WHEN SUM(srl.records_processed) > 0 THEN
                    ROUND(SUM(srl.records_failed)::NUMERIC / SUM(srl.records_processed)::NUMERIC, 4)
                ELSE 0
            END AS error_rate,
            AVG(srl.records_processed) AS avg_records_per_run,
            AVG(EXTRACT(EPOCH FROM (srl.completed_at - srl.started_at))) AS avg_run_duration_seconds,
            MAX(srl.started_at) AS last_run_at,
            CURRENT_TIMESTAMP AS computed_at
        FROM sync_run_logs srl
        WHERE srl.started_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY srl.job_name, srl.job_type;
        """
    )
    op.create_index("idx_mv_sync_health_job", "mv_sync_health_dashboard", ["job_name"])
    op.create_index("idx_mv_sync_health_computed", "mv_sync_health_dashboard", ["computed_at"])

    # Materialized view: mv_match_accuracy
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_match_accuracy AS
        SELECT
            'violations' AS source_table,
            COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS matched_count,
            COUNT(*) FILTER (WHERE subcontractor_id IS NULL) AS unmatched_count,
            COUNT(*) AS total_count,
            CASE
                WHEN COUNT(*) > 0 THEN
                    ROUND(COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC, 4)
                ELSE 0
            END AS match_rate,
            CURRENT_TIMESTAMP AS computed_at
        FROM violations
        WHERE is_osha_violation = TRUE
        UNION ALL
        SELECT
            'state_credential_records' AS source_table,
            COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL) AS matched_count,
            COUNT(*) FILTER (WHERE subcontractor_id IS NULL) AS unmatched_count,
            COUNT(*) AS total_count,
            CASE
                WHEN COUNT(*) > 0 THEN
                    ROUND(COUNT(*) FILTER (WHERE subcontractor_id IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC, 4)
                ELSE 0
            END AS match_rate,
            CURRENT_TIMESTAMP AS computed_at
        FROM state_credential_records;
        """
    )
    op.create_index("idx_mv_match_accuracy_table", "mv_match_accuracy", ["source_table"])

    # ====================================================================
    # 014b: Data Retention and Archival Policy
    # ====================================================================

    # archived_sync_run_logs — archival target for old sync_run_logs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS archived_sync_run_logs (
            id UUID PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            status VARCHAR(50),
            triggered_by VARCHAR(50),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            records_processed INT DEFAULT 0,
            records_inserted INT DEFAULT 0,
            records_updated INT DEFAULT 0,
            records_failed INT DEFAULT 0,
            error_message TEXT,
            run_metadata JSON,
            archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            archive_reason VARCHAR(50) DEFAULT 'retention'
        )
        """
    )
    op.create_index("idx_archived_sync_job_name", "archived_sync_run_logs", ["job_name"])
    op.create_index("idx_archived_sync_archived_at", "archived_sync_run_logs", ["archived_at"])

    # archived_data_quality_results — archival target for old data_quality_results
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS archived_data_quality_results (
            id UUID PRIMARY KEY,
            check_id UUID NOT NULL,
            sync_run_id UUID NOT NULL,
            status VARCHAR(20) NOT NULL,
            records_checked INT DEFAULT 0,
            records_failed INT DEFAULT 0,
            failure_rate NUMERIC(5,4),
            execution_time_ms INT,
            sample_failures JSON,
            executed_at TIMESTAMP WITH TIME ZONE,
            archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            archive_reason VARCHAR(50) DEFAULT 'retention'
        )
        """
    )
    op.create_index("idx_archived_dqr_archived_at", "archived_data_quality_results", ["archived_at"])

    # ====================================================================
    # 014c: Pipeline Performance Monitoring
    # ====================================================================

    # pipeline_performance_logs — per-run performance metrics
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_performance_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL,
            job_name VARCHAR(100) NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            stage_name VARCHAR(100) NOT NULL,
            stage_order INT NOT NULL DEFAULT 0,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            duration_ms INT,
            records_in INT DEFAULT 0,
            records_out INT DEFAULT 0,
            cache_hits INT DEFAULT 0,
            cache_misses INT DEFAULT 0,
            api_requests INT DEFAULT 0,
            api_errors INT DEFAULT 0,
            avg_api_latency_ms INT,
            max_api_latency_ms INT,
            error_message TEXT,
            metadata JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.create_index("idx_ppl_run_id", "pipeline_performance_logs", ["run_id"])
    op.create_index("idx_ppl_job_name", "pipeline_performance_logs", ["job_name"])
    op.create_index("idx_ppl_stage_name", "pipeline_performance_logs", ["stage_name"])
    op.create_index("idx_ppl_created_at", "pipeline_performance_logs", ["created_at"])

    # Materialized view: mv_pipeline_performance_summary
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_pipeline_performance_summary AS
        SELECT
            job_name,
            job_type,
            stage_name,
            COUNT(*) AS total_runs,
            AVG(duration_ms) AS avg_duration_ms,
            MIN(duration_ms) AS min_duration_ms,
            MAX(duration_ms) AS max_duration_ms,
            AVG(records_in) AS avg_records_in,
            avg(api_requests) AS avg_api_requests,
            AVG(avg_api_latency_ms) AS avg_api_latency_ms,
            MAX(max_api_latency_ms) AS max_api_latency_ms,
            AVG(cache_hits) AS avg_cache_hits,
            AVG(cache_misses) AS avg_cache_misses,
            CASE
                WHEN SUM(cache_hits + cache_misses) > 0 THEN
                    ROUND(SUM(cache_hits)::NUMERIC / SUM(cache_hits + cache_misses)::NUMERIC, 4)
                ELSE 0
            END AS cache_hit_rate,
            CURRENT_TIMESTAMP AS computed_at
        FROM pipeline_performance_logs
        WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY job_name, job_type, stage_name;
        """
    )
    op.create_index("idx_mv_ppl_summary_job", "mv_pipeline_performance_summary", ["job_name"])
    op.create_index("idx_mv_ppl_summary_stage", "mv_pipeline_performance_summary", ["stage_name"])

    # ====================================================================
    # 014d: Analytics Views for Subcontractor Compliance Trends
    # ====================================================================

    # Materialized view: mv_subcontractor_compliance_trends
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_subcontractor_compliance_trends AS
        WITH daily_stats AS (
            SELECT
                generate_series::date AS trend_date,
                COUNT(DISTINCT s.id) AS total_subcontractors,
                COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.id END) AS active_subcontractors,
                COUNT(DISTINCT CASE
                    WHEN s.status = 'active'
                        AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid' AND c.expiration_date >= generate_series)
                        AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open' AND (v.resolution_date IS NULL OR v.resolution_date > generate_series))
                    THEN s.id END) AS compliant_subcontractors,
                COUNT(DISTINCT CASE
                    WHEN s.status = 'active'
                        AND EXISTS (SELECT 1 FROM certifications c WHERE c.subcontractor_id = s.id AND c.status = 'valid' AND c.expiration_date BETWEEN generate_series AND generate_series + INTERVAL '30 days')
                    THEN s.id END) AS expiring_soon_30d,
                COUNT(DISTINCT CASE
                    WHEN s.status = 'active'
                        AND EXISTS (SELECT 1 FROM violations v WHERE v.subcontractor_id = s.id AND v.status = 'open' AND v.issued_date <= generate_series)
                    THEN s.id END) AS subcontractors_with_violations,
                COALESCE(SUM(CASE WHEN v.status = 'open' AND v.issued_date <= generate_series THEN v.penalty_amount ELSE 0 END), 0) AS total_open_penalties
            FROM generate_series(CURRENT_DATE - INTERVAL '90 days', CURRENT_DATE, INTERVAL '1 day') AS generate_series
            LEFT JOIN subcontractors s ON s.created_at <= generate_series
            LEFT JOIN violations v ON v.subcontractor_id = s.id
            GROUP BY generate_series
        )
        SELECT
            trend_date,
            total_subcontractors,
            active_subcontractors,
            compliant_subcontractors,
            CASE
                WHEN active_subcontractors > 0 THEN
                    ROUND((compliant_subcontractors::NUMERIC / active_subcontractors::NUMERIC) * 100, 2)
                ELSE 0
            END AS compliance_rate,
            expiring_soon_30d,
            subcontractors_with_violations,
            total_open_penalties,
            CURRENT_TIMESTAMP AS computed_at
        FROM daily_stats
        ORDER BY trend_date;
        """
    )
    op.create_index("idx_mv_subcomptrend_date", "mv_subcontractor_compliance_trends", ["trend_date"])

    # Materialized view: mv_certification_expiration_trends
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_certification_expiration_trends AS
        WITH daily AS (
            SELECT
                generate_series::date AS trend_date,
                COUNT(DISTINCT CASE WHEN c.status = 'valid' AND c.expiration_date >= generate_series THEN c.id END) AS valid_certs,
                COUNT(DISTINCT CASE WHEN c.expiration_date < generate_series THEN c.id END) AS expired_certs,
                COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN generate_series AND generate_series + INTERVAL '7 days' THEN c.id END) AS expiring_7d,
                COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN generate_series AND generate_series + INTERVAL '30 days' THEN c.id END) AS expiring_30d,
                COUNT(DISTINCT CASE WHEN c.expiration_date BETWEEN generate_series AND generate_series + INTERVAL '60 days' THEN c.id END) AS expiring_60d
            FROM generate_series(CURRENT_DATE - INTERVAL '90 days', CURRENT_DATE + INTERVAL '60 days', INTERVAL '1 day') AS generate_series
            LEFT JOIN certifications c ON c.created_at <= generate_series
            GROUP BY generate_series
        )
        SELECT
            trend_date,
            valid_certs,
            expired_certs,
            expiring_7d,
            expiring_30d,
            expiring_60d,
            CURRENT_TIMESTAMP AS computed_at
        FROM daily
        ORDER BY trend_date;
        """
    )
    op.create_index("idx_mv_certexptrend_date", "mv_certification_expiration_trends", ["trend_date"])

    # Materialized view: mv_data_quality_summary
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_data_quality_summary AS
        SELECT
            dqc.id AS check_id,
            dqc.check_name,
            dqc.table_name,
            dqc.column_name,
            dqc.check_type,
            dqc.severity,
            dqc.is_active,
            COUNT(dqr.id) AS total_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'passed') AS passed_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'failed') AS failed_runs,
            COUNT(*) FILTER (WHERE dqr.status = 'warning') AS warning_runs,
            AVG(dqr.failure_rate) AS avg_failure_rate,
            MAX(dqr.executed_at) AS last_executed_at,
            CURRENT_TIMESTAMP AS computed_at
        FROM data_quality_checks dqc
        LEFT JOIN data_quality_results dqr ON dqr.check_id = dqc.id
        GROUP BY dqc.id, dqc.check_name, dqc.table_name, dqc.column_name, dqc.check_type, dqc.severity, dqc.is_active;
        """
    )
    op.create_index("idx_mv_dq_summary_check", "mv_data_quality_summary", ["check_id"])


def downgrade() -> None:
    # Reverse order of creation
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_data_quality_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_certification_expiration_trends CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_subcontractor_compliance_trends CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pipeline_performance_summary CASCADE")
    op.execute("DROP TABLE IF EXISTS pipeline_performance_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS archived_data_quality_results CASCADE")
    op.execute("DROP TABLE IF EXISTS archived_sync_run_logs CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_match_accuracy CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sync_health_dashboard CASCADE")
    op.execute("DROP TABLE IF EXISTS data_quality_alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS sync_health_daily CASCADE")