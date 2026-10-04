"""Password policy enforcement for the Prequal platform.

Centralises the rules used across registration, password change and password
reset so the policy cannot drift between entry points:

- Minimum length and character complexity
- Rejection of commonly breached passwords
- Password history (prevent reuse of the last N passwords)
- Password expiration

Owners: Backend Engineer (MID-307 / MID-317)
"""

import os
import re
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

import bcrypt

# ---------------------------------------------------------------------------
# Policy configuration (overridable via environment)
# ---------------------------------------------------------------------------
MIN_PASSWORD_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
PASSWORD_HISTORY_SIZE = int(os.getenv("PASSWORD_HISTORY_SIZE", "5"))
PASSWORD_MAX_AGE_DAYS = int(os.getenv("PASSWORD_MAX_AGE_DAYS", "90"))

# bcrypt hashes only the first 72 bytes of the input.
_BCRYPT_MAX_BYTES = 72

# Character classes required by the complexity rule.
_REQUIRED_CLASSES = (
    (re.compile(r"[A-Z]"), "an uppercase letter"),
    (re.compile(r"[a-z]"), "a lowercase letter"),
    (re.compile(r"\d"), "a digit"),
    (re.compile(r"[^A-Za-z0-9]"), "a special character"),
)

# A compact set of the most frequently breached passwords. Checks are
# case-insensitive. Production deployments can extend this list without a code
# change by pointing ``PASSWORD_DENYLIST_FILE`` at one password per line.
COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "123456",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty",
        "qwerty123",
        "abc123",
        "letmein",
        "monkey",
        "dragon",
        "iloveyou",
        "admin",
        "admin123",
        "welcome",
        "welcome1",
        "login",
        "master",
        "sunshine",
        "princess",
        "football",
        "baseball",
        "superman",
        "trustno1",
        "changeme",
        "p@ssw0rd",
        "p@ssword1",
        "qazwsx",
        "zaq12wsx",
        "1q2w3e4r",
        "company123",
        "prequal",
        "prequal123",
    }
)


def _load_denylist_file() -> frozenset:
    path = os.getenv("PASSWORD_DENYLIST_FILE")
    if not path or not os.path.exists(path):
        return frozenset()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            entries = {
                line.strip().lower()
                for line in handle
                if line.strip() and not line.startswith("#")
            }
        return frozenset(entries)
    except OSError:
        return frozenset()


_DENYLIST_FILE_PASSWORDS = _load_denylist_file()


def is_common_password(password: str) -> bool:
    """Return True when ``password`` appears on the breached-password denylist."""
    if not password:
        return False
    candidate = password.strip().lower()
    return candidate in COMMON_PASSWORDS or candidate in _DENYLIST_FILE_PASSWORDS


def validate_password_strength(password: str) -> List[str]:
    """Return a list of human-readable policy violations for ``password``.

    An empty list means the password satisfies the policy.
    """
    errors: List[str] = []
    if password is None:
        return ["Password is required"]

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    for pattern, description in _REQUIRED_CLASSES:
        if not pattern.search(password):
            errors.append(f"Password must contain {description}")

    if is_common_password(password):
        errors.append("Password is too common and has appeared in data breaches")

    return errors


def validate_password(password: str) -> None:
    """Raise ``ValueError`` if ``password`` violates the policy."""
    errors = validate_password_strength(password)
    if errors:
        raise ValueError("; ".join(errors))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Safely verify a password against a bcrypt hash."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()
    ).decode("utf-8")


def _hash_candidates(
    current_hash: Optional[str],
    history: Optional[Iterable[str]],
) -> List[str]:
    candidates: List[str] = []
    if history:
        if isinstance(history, (list, tuple)):
            candidates.extend(str(item) for item in history if item)
        elif isinstance(history, str):
            candidates.append(history)
    if current_hash:
        candidates.append(current_hash)
    return candidates


def is_password_reused(
    new_password: str,
    current_hash: Optional[str],
    history: Optional[Iterable[str]],
) -> bool:
    """Return True when ``new_password`` matches the current or a historic hash."""
    for candidate in _hash_candidates(current_hash, history):
        if verify_password(new_password, candidate):
            return True
    return False


def append_to_password_history(
    current_hash: Optional[str],
    history: Optional[Iterable[str]],
    max_items: Optional[int] = None,
) -> List[str]:
    """Return a trimmed history list including ``current_hash`` as the newest entry."""
    limit = max_items or PASSWORD_HISTORY_SIZE
    items = [str(item) for item in history if item] if history else []
    if current_hash:
        items.append(current_hash)
    # Keep only the most recent N hashes.
    return items[-limit:]


def is_password_expired(
    password_changed_at: Optional[datetime],
    max_age_days: Optional[int] = None,
) -> bool:
    """Return True when a password is older than the maximum allowed age.

    ``None`` is treated as "unknown age" and is not considered expired, so
    legacy accounts without a timestamp are not locked out unintentionally.
    """
    if password_changed_at is None:
        return False
    moment = password_changed_at
    if moment.tzinfo is not None:
        moment = moment.replace(tzinfo=None)
    max_age = max_age_days if max_age_days is not None else PASSWORD_MAX_AGE_DAYS
    return moment < (datetime.utcnow() - timedelta(days=max_age))
