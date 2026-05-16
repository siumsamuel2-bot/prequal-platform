"""Add uploaded_credentials table for credential document storage.

Migration ID: 003
Description: Creates uploaded_credentials table for storing subcontractor 
credential document uploads with OCR extraction and virus scanning support.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploaded_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subcontractor_id", UUID(as_uuid=True), sa.ForeignKey("subcontractors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("certification_id", UUID(as_uuid=True), sa.ForeignKey("certifications.id", ondelete="SET NULL"), nullable=True),
        
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("extraction_status", sa.String(50), nullable=False, server_default="pending"),
        
        sa.Column("extracted_cert_type", sa.String(100), nullable=True),
        sa.Column("extracted_cert_number", sa.String(100), nullable=True),
        sa.Column("extracted_issue_date", sa.String(50), nullable=True),
        sa.Column("extracted_expiration_date", sa.String(50), nullable=True),
        sa.Column("extracted_issuing_authority", sa.String(255), nullable=True),
        
        sa.Column("ocr_raw_text", sa.Text(), nullable=True),
        sa.Column("virus_scan_status", sa.String(50), nullable=False, server_default="not_scanned"),
        sa.Column("virus_scan_result", sa.Text(), nullable=True),
        
        sa.Column("upload_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    op.create_index("idx_uploaded_credentials_subcontractor_id", "uploaded_credentials", ["subcontractor_id"])
    op.create_index("idx_uploaded_credentials_status", "uploaded_credentials", ["status"])
    op.create_index("idx_uploaded_credentials_stored_filename", "uploaded_credentials", ["stored_filename"])
    
    op.create_index("idx_uploaded_credentials_certification_id", "uploaded_credentials", ["certification_id"])


def downgrade() -> None:
    op.drop_index("idx_uploaded_credentials_certification_id", table_name="uploaded_credentials")
    op.drop_index("idx_uploaded_credentials_stored_filename", table_name="uploaded_credentials")
    op.drop_index("idx_uploaded_credentials_status", table_name="uploaded_credentials")
    op.drop_index("idx_uploaded_credentials_subcontractor_id", table_name="uploaded_credentials")
    op.drop_table("uploaded_credentials")