"""Session management service for secure token handling with short expiry and rotation.

This module provides functions for:
- Creating and validating server-side sessions
- Session token rotation on each request
- Session invalidation on logout and password change
- Secure session metadata tracking (IP, user agent, timestamps)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import UserSession

logger = logging.getLogger(__name__)

# Short-lived access sessions (mirrors ACCESS_TOKEN_EXPIRE_MINUTES used for JWTs).
SESSION_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# Cap stored user agent length to the column size to avoid DB errors.
_MAX_USER_AGENT_LEN = 500


def _utcnow() -> datetime:
    """Naive UTC timestamp, consistent across SQLite and PostgreSQL backends."""
    return datetime.utcnow()


def _as_naive(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize a possibly timezone-aware datetime to naive UTC for comparison."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _truncate(value: Optional[str], length: int) -> Optional[str]:
    if value is None:
        return None
    return value[:length]


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    jti: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    expires_minutes: Optional[int] = None,
) -> UserSession:
    """Create a new server-side session bound to an access token JTI.

    Args:
        db: Database session
        user_id: User UUID
        jti: Token ID (JTI) from the access token
        ip_address: Client IP address
        user_agent: Client user agent string
        expires_minutes: Optional override for the session lifetime

    Returns:
        The created UserSession object
    """
    now = _utcnow()
    session = UserSession(
        user_id=user_id,
        jti=jti,
        ip_address=_truncate(ip_address, 45),
        user_agent=_truncate(user_agent, _MAX_USER_AGENT_LEN),
        active=True,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=expires_minutes or SESSION_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.debug("Created session %s for user %s", jti, user_id)
    return session


async def get_session_by_jti(db: AsyncSession, jti: str) -> Optional[UserSession]:
    """Fetch a session record by its current JTI (active or not)."""
    if not jti:
        return None
    result = await db.execute(select(UserSession).where(UserSession.jti == jti))
    return result.scalar_one_or_none()


async def validate_session(db: AsyncSession, jti: str) -> Optional[UserSession]:
    """Return the active, unexpired session for ``jti`` or ``None``.

    Expired sessions are marked inactive so they can no longer be used.
    """
    session = await get_session_by_jti(db, jti)
    if session is None:
        return None
    if not session.active:
        return None
    if _as_naive(session.expires_at) is not None and _as_naive(session.expires_at) <= _utcnow():
        session.active = False
        session.revoked_at = _utcnow()
        await db.commit()
        logger.info("Expired session %s marked inactive", jti)
        return None
    return session


async def rotate_session(
    db: AsyncSession,
    session: UserSession,
    new_jti: str,
    expires_minutes: Optional[int] = None,
) -> UserSession:
    """Rotate an existing session to a new JTI.

    The previous JTI is retained in ``rotated_from_jti`` for audit purposes.
    """
    session.rotated_from_jti = session.jti
    session.jti = new_jti
    session.last_seen_at = _utcnow()
    session.expires_at = _utcnow() + timedelta(
        minutes=expires_minutes or SESSION_EXPIRE_MINUTES
    )
    await db.commit()
    await db.refresh(session)
    logger.debug("Rotated session to new jti %s", new_jti)
    return session


async def revoke_session(db: AsyncSession, jti: str) -> bool:
    """Revoke a single session by JTI. Returns True if a session was found."""
    session = await get_session_by_jti(db, jti)
    if session is None:
        return False
    if session.active:
        session.active = False
        session.revoked_at = _utcnow()
        await db.commit()
        logger.info("Revoked session %s", jti)
    return True


async def revoke_all_user_sessions(db: AsyncSession, user_id: UUID) -> int:
    """Revoke every active session for a user (e.g. on logout or password change).

    Returns the number of sessions that were revoked.
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.active.is_(True),
        )
    )
    sessions = result.scalars().all()
    now = _utcnow()
    for session in sessions:
        session.active = False
        session.revoked_at = now
    if sessions:
        await db.commit()
        logger.info("Revoked %d session(s) for user %s", len(sessions), user_id)
    return len(sessions)


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Mark all expired active sessions inactive. Returns the number cleaned up."""
    result = await db.execute(select(UserSession).where(UserSession.active.is_(True)))
    sessions = result.scalars().all()
    now = _utcnow()
    cleaned = 0
    for session in sessions:
        expires_at = _as_naive(session.expires_at)
        if expires_at is not None and expires_at <= now:
            session.active = False
            session.revoked_at = now
            cleaned += 1
    if cleaned:
        await db.commit()
        logger.info("Cleaned up %d expired session(s)", cleaned)
    return cleaned
