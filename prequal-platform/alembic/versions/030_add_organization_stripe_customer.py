"""030: Add stripe_customer_id to organizations

Migration ID: 030 (MID-656)
Description:
- Adds `stripe_customer_id` VARCHAR(255) NULL to `organizations` plus the
  supporting index that `app/models/auth.py` declares.
- `app/models/auth.py` (``Organization.stripe_customer_id``) and
  `app/routers/billing.py` both reference this column, but no earlier revision
  ever added it. The SQLite test path created it implicitly via
  ``Base.metadata.create_all``, so the drift was masked; on PostgreSQL every
  ``organizations`` INSERT failed with
  ``UndefinedColumn: column "stripe_customer_id" of relation "organizations"
  does not exist``.
- Idempotent: guards on ``IF NOT EXISTS`` so it is safe on databases where the
  column/index already exist (create_all-seeded or previously-migrated DBs).

Owner: Senior Engineer
"""

from typing import Union

from alembic import op

revision: str = "030_org_stripe_customer"
down_revision: Union[str, tuple] = "029_session_rotation_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer
        ON organizations (stripe_customer_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_organizations_stripe_customer")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS stripe_customer_id")
