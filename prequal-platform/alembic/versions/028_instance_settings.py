"""028: Instance Settings singleton table

Migration ID: 028 (MID-314)
Description:
- Creates the `instance_settings` table: a singleton key-value store for
  platform-wide runtime settings, keyed by `singleton_key`. This resolves the
  failing query `SELECT ... FROM instance_settings WHERE singleton_key = 'default'`
  which errored because the table did not exist in any prior migration.
- Seeds the required `default` row so the settings query always finds a
  well-formed record on a freshly migrated database.
- Idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING) so it is safe to apply
  to databases where the table or row may already exist.

Owner: Data Engineer
"""

from alembic import op

revision: str = "028_instance_settings"
down_revision: str = "027_data_quality_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # instance_settings — singleton platform settings store
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instance_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            singleton_key VARCHAR(64) NOT NULL,
            settings_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Enforce the singleton contract: at most one row per singleton_key
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_instance_settings_singleton_key
        ON instance_settings (singleton_key)
        """
    )
    # Seed the required default row (never overwrites an existing row)
    op.execute(
        """
        INSERT INTO instance_settings (singleton_key, settings_json)
        VALUES ('default', '{}')
        ON CONFLICT (singleton_key) DO NOTHING
        """
    )


def downgrade() -> None:
    # Per data-retention policy we never silently drop data; archive instead.
    # The downgrade creates an archive copy before dropping the table.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS archived_instance_settings (
            id UUID,
            singleton_key VARCHAR(64),
            settings_json TEXT,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE,
            archived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        INSERT INTO archived_instance_settings
            (id, singleton_key, settings_json, created_at, updated_at)
        SELECT id, singleton_key, settings_json, created_at, updated_at
        FROM instance_settings
        """
    )
    op.execute("DROP TABLE IF EXISTS instance_settings CASCADE")
