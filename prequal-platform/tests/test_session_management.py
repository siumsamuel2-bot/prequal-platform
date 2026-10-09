"""Tests for secure server-side session management (MID-316).

Covers:
- Session creation with secure metadata (IP, user agent, expiry)
- Short expiry enforcement
- Rotation on each authenticated request
- Revocation on logout / password change
- Middleware (get_current_user) enforcing expiry and rotation
- Max rotation limit enforcement

These tests exercise the session layer directly so they do not depend on
password hashing backends.
"""
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.auth import User
from app.routers.auth import create_access_token, get_current_user
from app.models.session import MAX_SESSION_ROTATIONS
from app.services.session_manager import (
    SESSION_EXPIRE_MINUTES,
    create_session,
    get_session_by_jti,
    rotate_session,
    revoke_all_user_sessions,
    revoke_session,
    validate_session,
)


async def _make_user(db_session) -> User:
    user = User(
        email=f"session-{uuid.uuid4().hex}@example.com",
        name="Session Tester",
        hashed_password="not-used-in-these-tests",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _token_for(user: User, jti: str, password_changed_at=None) -> str:
    return create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role},
        password_changed_at=password_changed_at,
        jti=jti,
    )


@pytest.mark.asyncio
async def test_create_session_tracks_secure_metadata(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())

    session = await create_session(
        db_session, user.id, jti, ip_address="203.0.113.5", user_agent="pytest-agent"
    )

    assert session.jti == jti
    assert session.active is True
    assert session.ip_address == "203.0.113.5"
    assert session.user_agent == "pytest-agent"
    lifetime_minutes = (session.expires_at - session.created_at).total_seconds() / 60
    assert SESSION_EXPIRE_MINUTES - 1 <= lifetime_minutes <= SESSION_EXPIRE_MINUTES + 1


@pytest.mark.asyncio
async def test_validate_rejects_and_inactivates_expired_session(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())
    await create_session(db_session, user.id, jti, expires_minutes=-1)

    assert await validate_session(db_session, jti) is None

    stored = await get_session_by_jti(db_session, jti)
    assert stored is not None
    assert stored.active is False
    assert stored.revoked_at is not None


@pytest.mark.asyncio
async def test_rotate_session_issues_new_jti_and_invalidates_old(db_session):
    user = await _make_user(db_session)
    old_jti = str(uuid.uuid4())
    session = await create_session(db_session, user.id, old_jti)

    new_jti = str(uuid.uuid4())
    rotated = await rotate_session(db_session, session, new_jti)

    assert rotated.jti == new_jti
    assert rotated.rotated_from_jti == old_jti
    assert rotated.active is True
    assert await validate_session(db_session, new_jti) is not None
    assert await validate_session(db_session, old_jti) is None


@pytest.mark.asyncio
async def test_revoke_session(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())
    await create_session(db_session, user.id, jti)

    assert await revoke_session(db_session, jti) is True
    assert await validate_session(db_session, jti) is None
    assert await revoke_session(db_session, "does-not-exist") is False


@pytest.mark.asyncio
async def test_revoke_all_user_sessions_invalidates_every_session(db_session):
    user = await _make_user(db_session)
    first = str(uuid.uuid4())
    second = str(uuid.uuid4())
    await create_session(db_session, user.id, first)
    await create_session(db_session, user.id, second)

    revoked = await revoke_all_user_sessions(db_session, user.id)

    assert revoked == 2
    assert await validate_session(db_session, first) is None
    assert await validate_session(db_session, second) is None


@pytest.mark.asyncio
async def test_get_current_user_requires_active_session_and_rotates(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())
    token = _token_for(user, jti)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401

    await create_session(db_session, user.id, jti)

    token_data = await get_current_user(token=token, db=db_session)
    assert token_data.user_id == str(user.id)
    assert token_data.jti is not None
    assert token_data.jti != jti

    previous = await get_session_by_jti(db_session, jti)
    assert previous is None
    rotated = await get_session_by_jti(db_session, token_data.jti)
    assert rotated is not None and rotated.active is True

    with pytest.raises(HTTPException) as reused_exc:
        await get_current_user(token=token, db=db_session)
    assert reused_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_session(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())
    await create_session(db_session, user.id, jti, expires_minutes=-1)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=_token_for(user, jti), db=db_session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_token_after_password_change(db_session):
    user = await _make_user(db_session)
    original_change = datetime(2020, 1, 1, 12, 0, 0)
    jti = str(uuid.uuid4())
    token = _token_for(user, jti, password_changed_at=original_change)
    await create_session(db_session, user.id, jti)

    user.password_changed_at = datetime.utcnow()
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401
    assert "password change" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_rotate_session_max_limit(db_session):
    user = await _make_user(db_session)
    jti = str(uuid.uuid4())
    session = await create_session(db_session, user.id, jti)

    # Rotate until reaching the max limit (200)
    for _ in range(MAX_SESSION_ROTATIONS):
        new_jti = str(uuid.uuid4())
        await rotate_session(db_session, session, new_jti)

    # The session should now be inactive after exceeding max rotations
    assert await validate_session(db_session, jti) is None

    # Attempting to validate the last jti should raise 401
    from fastapi import HTTPException
    from starlette.status import HTTP_401_UNAUTHORIZED
    with pytest.raises(HTTPException) as exc_info:
        await rotate_session(db_session, session, str(uuid.uuid4()))
    assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED
    assert "maximum rotation limit" in exc_info.value.detail
