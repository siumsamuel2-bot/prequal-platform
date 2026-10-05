"""027: Data Quality Metrics History & Schema Snapshots

Migration ID: 027 (MID-605)
Description:
- data_quality_field_metrics: per-run snapshots of null/duplicate rates for
  critical fields (EIN, certification numbers, expiration dates, ...). Enables
  historical trend data (7d/30d) and null-rate spike anomaly detection.
- data_quality_schema_snapshots: per-table column snapshots used for schema
  drift detection (new/removed columns between monitoring runs).

Owner: Data Engineer
"""

from alembic import op

revision: str = "027_data_quality_metrics"
down_revision: str = "026_add_mfa_backup_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # data_quality_field_metrics — per-run field quality snapshots
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS data_quality_field_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            captured_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            table_name VARCHAR(100) NOT NULL,
            column_name VARCHAR(100) NOT NULL,
            total_rows INT NOT NULL DEFAULT 0,
            null_count INT NOT NULL DEFAULT 0,
            null_rate NUMERIC(6,4),
            duplicate_count INT NOT NULL DEFAULT 0,
            duplicate_rate NUMERIC(6,4)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dqfm_table_column ON data_quality_field_metrics (table_name, column_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dqfm_captured_at ON data_quality_field_metrics (captured_at)"
    )

    # data_quality_schema_snapshots — column snapshots for drift detection
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS data_quality_schema_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            table_name VARCHAR(100) NOT NULL,
            columns_json TEXT NOT NULL,
            captured_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dqss_table_name ON data_quality_schema_snapshots (table_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dqss_captured_at ON data_quality_schema_snapshots (captured_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS data_quality_schema_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS data_quality_field_metrics CASCADE")
