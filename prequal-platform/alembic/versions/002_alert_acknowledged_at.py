"""Add acknowledged_at to alert_notifications.

Migration ID: 002
Description: Adds acknowledged_at column to alert_notifications table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_notifications",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "idx_alert_notifications_acknowledged_at",
        "alert_notifications",
        ["acknowledged_at"]
    )
    # Also add a days_until_expiration denormalized column for quick alerting lookups
    op.add_column(
        "alert_notifications",
        sa.Column("days_until_expiration", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_index("idx_alert_notifications_acknowledged_at", table_name="alert_notifications")
    op.drop_column("alert_notifications", "acknowledged_at")
    op.drop_column("alert_notifications", "days_until_expiration")
