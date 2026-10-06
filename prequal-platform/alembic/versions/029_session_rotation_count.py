"""029: Add rotation_count to user_sessions

Migration ID: 029 (MID-641 / MID-640)
Description:
- Adds `rotation_count` INTEGER NOT NULL DEFAULT 0 to `user_sessions`.
  The column is required by the secure token-rotation logic in
  `app/models/session.py` (`MAX_SESSION_ROTATIONS = 200`) and by the
  session-management tests; without it, queries referencing
  `rotation_count` fail on PostgreSQL.
- Idempotent: guards on information_schema so it is safe on databases
  where the column already exists.

Owner: Data Engineer
"""

from typing import Union

from alembic import op

revision: str = "029_session_rotation_count"
# Merge the dangling 020_production_query_indexes branch (off 019) with the
# main chain so `alembic upgrade head` resolves to a single head again.
down_revision: Union[str, tuple] = ("028_instance_settings", "020_production_query_indexes")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_sessions
        ADD COLUMN IF NOT EXISTS rotation_count INTEGER NOT NULL DEFAULT 0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_sessions
        DROP COLUMN IF EXISTS rotation_count
        """
    )
