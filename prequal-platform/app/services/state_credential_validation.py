"""State credential validation rules.

Validates raw state credential records before they are written to the
database.  Keeps data-quality checks in one place so both the ETL pipeline
and the service layer use the same logic.

Owner: Data Engineer
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Optional


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


class StateCredentialValidationError(ValueError):
    """Raised when a state credential record fails data-quality checks."""
    pass


def validate_state_credential_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean a raw state-credential record.

    Returns the cleaned record dict.  Raises StateCredentialValidationError
    on any rule violation.
    """
    # ---- required fields ---------------------------------------------------
    state_code = _clean_state_code(rec.get("state_code"))
    if not state_code:
        raise StateCredentialValidationError(
            f"Invalid or missing state_code: {rec.get('state_code')!r}"
        )

    cred_num = _clean_str(rec.get("credential_number") or rec.get("number"))
    if not cred_num:
        raise StateCredentialValidationError("Missing required field: credential_number")

    cred_type = _clean_str(rec.get("credential_type") or rec.get("type"))
    if not cred_type:
        raise StateCredentialValidationError("Missing required field: credential_type")

    # ---- status ------------------------------------------------------------
    status = _clean_str(rec.get("status", "active")).lower()
    allowed_statuses = {"active", "expired", "revoked", "suspended"}
    if status not in allowed_statuses:
        raise StateCredentialValidationError(
            f"Invalid status '{rec.get('status')}' for credential {cred_num}"
        )

    # ---- dates --------------------------------------------------------------
    issue_date = _parse_optional_date(rec.get("issue_date"))
    expiration_date = _parse_optional_date(rec.get("expiration_date"))

    if issue_date and expiration_date and expiration_date < issue_date:
        raise StateCredentialValidationError(
            f"expiration_date ({expiration_date}) < issue_date ({issue_date}) "
            f"for credential {cred_num}"
        )

    return {
        **rec,
        "state_code": state_code,
        "credential_number": cred_num,
        "credential_type": cred_type,
        "status": status,
        "issue_date": issue_date,
        "expiration_date": expiration_date,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_state_code(value: Any) -> Optional[str]:
    if not value:
        return None
    cleaned = str(value).strip().upper()
    if len(cleaned) == 2 and cleaned.isalpha() and cleaned.isascii():
        return cleaned
    return None


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_optional_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    parsed = _parse_date(value)
    if parsed is None:
        raise StateCredentialValidationError(f"Invalid date value: {value!r}")
    return parsed
