"""031: feedback_submissions (customer-care loop)

Migration ID: 031 (MID-666)
Description:
- Creates `feedback_submissions`, the persistence backing the post-launch
  feedback/support loop (MID-664). Rows are org-scoped: `org_id` is resolved
  server-side from the caller's authenticated identity (never client-trusted).
- Idempotent (IF NOT EXISTS) so it is safe on databases where the table or its
  indexes already exist (e.g. a create_all-seeded test database).

Owner: Backend Engineer
"""

from typing import Union

from alembic import op

revision: str = "031_feedback_submissions"
down_revision: Union[str, tuple] = "030_org_stripe_customer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_submissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            type VARCHAR(20) NOT NULL,
            surface VARCHAR(100) NOT NULL,
            page_url VARCHAR(1024),
            rating SMALLINT,
            message TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'new',
            owner_user_id UUID,
            linked_issue_id UUID,
            disposition_note TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_feedback_org_status_created
        ON feedback_submissions (org_id, status, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_feedback_org_type
        ON feedback_submissions (org_id, type)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_feedback_org_type")
    op.execute("DROP INDEX IF EXISTS idx_feedback_org_status_created")
    op.execute("DROP TABLE IF EXISTS feedback_submissions CASCADE")
