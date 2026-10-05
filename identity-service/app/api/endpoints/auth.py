"""
Authentication endpoints with secure session management.
Implements short expiry (15 minutes) and token rotation on each request.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time

from app.database import get_db
from app.models.models import User, UserSession
from app.schemas.schemas import UserLogin, UserSessionResponse, SessionRotationRequest, SessionRotationResponse
from app.services.security import (
    verify_password,
    generate_session_token,
    generate_rotation_token,
    is_token_expired,
    store_session_in_redis,
    get_session_from_redis,
    delete_session_from_redis,
    delete_all_user_sessions_from_redis,
)
from app.config import settings

RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300

_auth_rate_limit_store: dict = defaultdict(list)


def _check_auth_rate_limit(client_ip: str) -> tuple:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    _auth_rate_limit_store[client_ip] = [
        t for t in _auth_rate_limit_store[client_ip] if t > window_start
    ]
    if len(_auth_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_ATTEMPTS:
        return False, 0
    return True, RATE_LIMIT_MAX_ATTEMPTS - len(_auth_rate_limit_store[client_ip])


def _record_auth_attempt(client_ip: str) -> None:
    _auth_rate_limit_store[client_ip].append(time.time())


router = APIRouter()


@router.post("/login", response_model=UserSessionResponse)
async def login(user_login: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and create a new secure session."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    allowed, remaining = _check_auth_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": "300"},
        )
    _record_auth_attempt(client_ip)

    user = db.query(User).filter(User.email == user_login.email).first()
    if not user or not verify_password(user_login.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Generate tokens
    session_token = generate_session_token()
    rotation_token = generate_rotation_token()
    expires_at = datetime.utcnow() + timedelta(seconds=settings.SESSION_EXPIRY_SECONDS)

    # Create session in database
    new_session = UserSession(
        user_id=user.id,
        token=session_token,
        rotation_token=rotation_token,
        user_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=expires_at,
        is_valid=True,
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # Also store in Redis for fast lookup
    await store_session_in_redis(
        session_token,
        user.id,
        rotation_token,
        settings.SESSION_EXPIRY_SECONDS,
    )

    return new_session


@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Invalidate the current session token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.replace("Bearer ", "")

    # Find and invalidate session in database
    session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.is_valid == True
    ).first()

    if session:
        session.is_valid = False
        session.invalidated_reason = "logout"
        db.commit()

    # Also delete from Redis
    await delete_session_from_redis(token)

    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all(request: Request, db: Session = Depends(get_db)):
    """Invalidate all sessions for the current user."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.replace("Bearer ", "")

    # Find current session to get user_id
    current_session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.is_valid == True
    ).first()

    if current_session:
        # Invalidate all sessions for this user in database
        db.query(UserSession).filter(
            UserSession.user_id == current_session.user_id,
            UserSession.is_valid == True
        ).update({
            "is_valid": False,
            "invalidated_reason": "logout_all"
        })
        db.commit()

        # Also delete from Redis
        await delete_all_user_sessions_from_redis(current_session.user_id)

    return {"message": "All sessions invalidated"}


@router.post("/session/rotate", response_model=SessionRotationResponse)
async def rotate_session_token(
    rotation_request: SessionRotationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Rotate session token for continued access.
    Requires both current_token and rotation_token for security.
    """
    current_token = rotation_request.current_token
    provided_rotation_token = rotation_request.rotation_token

    session = db.query(UserSession).filter(
        UserSession.token == current_token,
        UserSession.is_valid == True
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    if session.rotation_token != provided_rotation_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid rotation token",
        )

    if is_token_expired(session.expires_at):
        session.is_valid = False
        session.invalidated_reason = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    # Delete old session from Redis
    await delete_session_from_redis(current_token)

    new_token = generate_session_token()
    new_rotation_token = generate_rotation_token()
    new_expires_at = datetime.utcnow() + timedelta(seconds=settings.SESSION_EXPIRY_SECONDS)

    session.token = new_token
    session.rotation_token = new_rotation_token
    session.expires_at = new_expires_at
    session.last_used_at = datetime.utcnow()

    db.commit()
    db.refresh(session)

    # Store new session in Redis
    await store_session_in_redis(
        new_token,
        session.user_id,
        new_rotation_token,
        settings.SESSION_EXPIRY_SECONDS,
    )

    return {
        "token": new_token,
        "rotation_token": new_rotation_token,
        "expires_at": new_expires_at,
    }