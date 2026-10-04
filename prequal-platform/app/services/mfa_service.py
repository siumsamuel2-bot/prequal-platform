"""Multi-factor authentication helpers (TOTP + backup codes).

Provides the building blocks used by the auth router for:
- Generating TOTP secrets and otpauth provisioning URIs / QR codes
- Verifying time-based one-time passwords
- Generating and verifying single-use backup codes

Owners: Backend Engineer (MID-307 / MID-315)
"""

import base64
import io
import os
import secrets
from typing import List, Optional, Tuple

import pyotp

from app.services.password_policy import hash_password, verify_password

MFA_ISSUER = os.getenv("MFA_ISSUER", "Prequal")
MFA_METHOD_TOTP = "totp"
BACKUP_CODE_COUNT = int(os.getenv("MFA_BACKUP_CODE_COUNT", "10"))
TOTP_VALID_WINDOW = int(os.getenv("MFA_TOTP_VALID_WINDOW", "1"))


def generate_totp_secret() -> str:
    """Return a new base32-encoded TOTP secret."""
    return pyotp.random_base32()


def build_otpauth_uri(secret: str, account_name: str, issuer: Optional[str] = None) -> str:
    """Build the ``otpauth://`` provisioning URI for authenticator apps."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name=issuer or MFA_ISSUER,
    )


def build_qr_data_uri(otpauth_uri: str) -> str:
    """Render ``otpauth_uri`` as a PNG data URI when possible.

    Falls back to returning the raw ``otpauth://`` URI when the optional
    ``qrcode`` dependency is unavailable so callers never fail on it.
    """
    try:
        import qrcode  # type: ignore

        image = qrcode.make(otpauth_uri)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return otpauth_uri


def normalize_totp_token(token: Optional[str]) -> str:
    if not token:
        return ""
    return token.strip().replace(" ", "").replace("-", "")


def verify_totp(secret: Optional[str], token: Optional[str], valid_window: Optional[int] = None) -> bool:
    """Verify a TOTP token against ``secret`` allowing clock drift."""
    if not secret or not token:
        return False
    cleaned = normalize_totp_token(token)
    if not cleaned.isdigit():
        return False
    try:
        return pyotp.TOTP(secret).verify(
            cleaned,
            valid_window=valid_window if valid_window is not None else TOTP_VALID_WINDOW,
        )
    except Exception:
        return False


def generate_backup_codes(count: Optional[int] = None) -> List[str]:
    """Generate a fresh batch of human-friendly single-use backup codes."""
    total = count or BACKUP_CODE_COUNT
    codes: List[str] = []
    while len(codes) < total:
        candidate = secrets.token_hex(5).upper()  # 10 hex characters
        if candidate not in codes:
            codes.append(candidate)
    return codes


def hash_backup_codes(codes: List[str]) -> List[str]:
    """Hash backup codes for storage so the plaintext is never persisted."""
    return [hash_password(code) for code in codes]


def verify_and_consume_backup_code(
    token: Optional[str],
    hashed_codes: Optional[List[str]],
) -> Tuple[bool, Optional[List[str]]]:
    """Verify a backup code and return the remaining (not yet used) hashes.

    Returns ``(matched, remaining_hashes)``. When ``matched`` is False the
    remaining hashes are unchanged.
    """
    if not token or not hashed_codes:
        return False, hashed_codes
    candidate = normalize_totp_token(token).upper()
    for index, hashed in enumerate(hashed_codes):
        if verify_password(candidate, hashed):
            remaining = hashed_codes[:index] + hashed_codes[index + 1:]
            return True, remaining
    return False, hashed_codes
