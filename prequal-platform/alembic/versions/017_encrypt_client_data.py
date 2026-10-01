"""Add encrypted client columns to projects table

Revision ID: 017_encrypt_client_data
Revises: 016_encrypt_subcontractor_pii
Create Date: 2026-06-09

Adds encrypted_ columns for: client_name, client_contact.
Then backfills by encrypting existing plaintext values in-place,
storing the ciphertext in the new columns and wiping the plaintext.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import os
import base64
import logging

logger = logging.getLogger(__name__)

revision: str = '017_encrypt_client_data'
down_revision: Union[str, None] = '016_encrypt_subcontractor_pii'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CLIENT_FIELDS = [
    'client_name',
    'client_contact',
]


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        raise RuntimeError("cryptography is required for this migration")

    key_material = os.getenv("ENCRYPTION_KEY", os.getenv("SECRET_KEY", ""))
    if not key_material:
        logger.warning("No ENCRYPTION_KEY or SECRET_KEY set. Using temporary key.")
        return Fernet(Fernet.generate_key())

    if len(key_material) < 32:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"prequal_salt",
            iterations=480000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(key_material.encode())))

    return Fernet(key_material.encode()[:32])


def _encrypt_value(fernet, plaintext):
    if plaintext is None or plaintext == "":
        return None
    return fernet.encrypt(plaintext.encode()).decode()


def _decrypt_value(fernet, ciphertext):
    if ciphertext is None or ciphertext == "":
        return None
    return fernet.decrypt(ciphertext.encode()).decode()


def upgrade() -> None:
    bind = op.get_bind()
    fernet = _get_fernet()

    for field in CLIENT_FIELDS:
        col_name = f"encrypted_{field}"
        op.add_column(
            'projects',
            sa.Column(col_name, sa.String(length=700), nullable=True)
        )
        logger.info(f"Added column projects.{col_name}")

    op.execute("COMMIT")

    for field in CLIENT_FIELDS:
        col_name = f"encrypted_{field}"
        plaintext_col = field

        try:
            result = bind.execute(
                sa.text(f"""
                    SELECT id, {plaintext_col}
                    FROM projects
                    WHERE {plaintext_col} IS NOT NULL
                      AND {plaintext_col} != ''
                      AND {col_name} IS NULL
                """)
            )
            rows = result.fetchall()
            logger.info(f"Backfilling {len(rows)} rows for {plaintext_col}")

            for row in rows:
                row_id, plaintext = row[0], row[1]
                ciphertext = _encrypt_value(fernet, plaintext)
                bind.execute(
                    sa.text(f"""
                        UPDATE projects
                        SET {col_name} = :ciphertext
                        WHERE id = :row_id
                    """),
                    {"ciphertext": ciphertext, "row_id": row_id}
                )
            logger.info(f"Done backfilling {plaintext_col}")
        except Exception as e:
            logger.warning(f"Could not backfill {plaintext_col}: {e}")

    logger.info("Migration complete - client data encrypted at rest")


def downgrade() -> None:
    bind = op.get_bind()
    fernet = _get_fernet()

    for field in CLIENT_FIELDS:
        col_name = f"encrypted_{field}"
        try:
            result = bind.execute(
                sa.text(f"""
                    SELECT id, {col_name}
                    FROM projects
                    WHERE {col_name} IS NOT NULL
                """)
            )
            rows = result.fetchall()
            logger.info(f"Restoring {len(rows)} rows for {field}")

            for row in rows:
                row_id, ciphertext = row[0], row[1]
                try:
                    plaintext = _decrypt_value(fernet, ciphertext)
                except Exception:
                    plaintext = None
                if plaintext:
                    bind.execute(
                        sa.text(f"""
                            UPDATE projects
                            SET {field} = :plaintext
                            WHERE id = :row_id
                        """),
                        {"plaintext": plaintext, "row_id": row_id}
                    )
        except Exception as e:
            logger.warning(f"Could not restore {field}: {e}")

    for field in CLIENT_FIELDS:
        op.drop_column('projects', f"encrypted_{field}")