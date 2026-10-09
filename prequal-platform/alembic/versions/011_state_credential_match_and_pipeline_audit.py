"""011: Add subcontractor matching and pipeline audit columns for external compliance data.

Migration ID: 011
Description:
- Adds subcontractor_id FK to state_credential_records for explicit matching.
- Adds data validation and deduplication columns to violations and state_credential_records.
- Adds pipeline error notification tracking table.
- Adds data source tracking columns for audit trail.

Owner: Data Engineer
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "011_state_cred_pipeline_audit"
down_revision = "010_analytics_materialized_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. state_credential_records: add explicit subcontractor_id FK
    # ------------------------------------------------------------------
    op.add_column(
        "state_credential_records",
        sa.Column("subcontractor_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_state_credential_subcontractor_id",
        "state_credential_records",
        ["subcontractor_id"],
    )
    op.create_foreign_key(
        "fk_state_credential_subcontractor",
        "state_credential_records",
        "subcontractors",
        ["subcontractor_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 2. violations: add data validation / dedup columns
    # ------------------------------------------------------------------
    op.add_column(
        "violations",
        sa.Column("source_system", sa.String(50), nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("source_record_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("match_confidence", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("match_method", sa.String(50), nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("raw_payload", JSON, nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "violations",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "idx_violations_source_system_record",
        "violations",
        ["source_system", "source_record_id"],
    )
    op.create_index(
        "idx_violations_is_duplicate",
        "violations",
        ["is_duplicate"],
    )

    # ------------------------------------------------------------------
    # 3. state_credential_records: add data validation / dedup columns
    # ------------------------------------------------------------------
    op.add_column(
        "state_credential_records",
        sa.Column("source_system", sa.String(50), nullable=True),
    )
    op.add_column(
        "state_credential_records",
        sa.Column("match_confidence", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "state_credential_records",
        sa.Column("match_method", sa.String(50), nullable=True),
    )
    op.add_column(
        "state_credential_records",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "idx_state_credential_source_system",
        "state_credential_records",
        ["source_system"],
    )
    op.create_index(
        "idx_state_credential_is_duplicate",
        "state_credential_records",
        ["is_duplicate"],
    )

    # ------------------------------------------------------------------
    # 4. sync_run_logs: add error notification columns
    # ------------------------------------------------------------------
    op.add_column(
        "sync_run_logs",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sync_run_logs",
        sa.Column("notification_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "sync_run_logs",
        sa.Column("notification_recipient", sa.String(255), nullable=True),
    )

    # ------------------------------------------------------------------
    # 5. pipeline_error_notifications table
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_error_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("sync_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_details", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_pipeline_notifications_job_name",
        "pipeline_error_notifications",
        ["job_name"],
    )
    op.create_index(
        "idx_pipeline_notifications_status",
        "pipeline_error_notifications",
        ["status"],
    )
    op.create_index(
        "idx_pipeline_notifications_created_at",
        "pipeline_error_notifications",
        ["created_at"],
    )


def downgrade() -> None:
    # Drop pipeline_error_notifications
    op.drop_table("pipeline_error_notifications")

    # Revert sync_run_logs columns
    op.drop_column("sync_run_logs", "notified_at")
    op.drop_column("sync_run_logs", "notification_status")
    op.drop_column("sync_run_logs", "notification_recipient")

    # Revert state_credential_records columns
    op.drop_column("state_credential_records", "is_duplicate")
    op.drop_column("state_credential_records", "match_method")
    op.drop_column("state_credential_records", "match_confidence")
    op.drop_column("state_credential_records", "source_system")
    op.drop_column("state_credential_records", "subcontractor_id")

    # Revert violations columns
    op.drop_column("violations", "is_duplicate")
    op.drop_column("violations", "last_synced_at")
    op.drop_column("violations", "raw_payload")
    op.drop_column("violations", "match_method")
    op.drop_column("violations", "match_confidence")
    op.drop_column("violations", "source_record_id")
    op.drop_column("violations", "source_system")
