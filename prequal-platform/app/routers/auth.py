import os
import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

import bcrypt
import jwt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.auth import User, Team, TeamMember, Organization, RefreshToken
from app.models.compliance import Project, Subcontractor
from app.schemas.compliance import (
    Token, TokenData, UserCreate, UserResponse, RegisterRequest, LoginRequest,
    UserWithTeams
)
from app.services.security_service import (
    check_rate_limit, check_account_lockout, create_account_lockout,
    clear_failed_login_attempts, log_auth_event, MAX_FAILED_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES
)
from app.middleware.rate_limit import limiter, RateLimitTiers, get_tier_limit
from app.services.notification_service import send_welcome_email, send_setup_complete_email
from app.services.session_manager import (
    create_session,
    validate_session,
    rotate_session,
    revoke_session,
    revoke_all_user_sessions,
)
from app.services import password_policy
from app.services.mfa_service import (
    MFA_METHOD_TOTP,
    build_otpauth_uri,
    build_qr_data_uri,
    generate_backup_codes,
    generate_totp_secret,
    hash_backup_codes,
    verify_and_consume_backup_code,
    verify_totp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")
if len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must be at least 32 bytes for HS256 security")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "0"))
REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", "0"))
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))

_BCRYPT_MAX_BYTES = 72
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    message: str


class MFAStatusResponse(BaseModel):
    mfa_enabled: bool
    mfa_method: Optional[str] = None


class MFAEnableRequest(BaseModel):
    password: str


class MFAEnableResponse(BaseModel):
    secret: str
    otpauth_url: str


class MFAVerifyRequest(BaseModel):
    token: str


class MFAVerifyResponse(BaseModel):
    message: str
    backup_codes: List[str] = []


class MFADisableRequest(BaseModel):
    password: str
    mfa_token: str


def _bcrypt_bytes(password: str) -> bytes:
    """Encode and truncate to bcrypt's 72-byte input limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            _bcrypt_bytes(plain_password), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    password_changed_at: Optional[datetime] = None,
    jti: Optional[str] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES, hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "type": "access"})
    if password_changed_at:
        to_encode["password_changed_at"] = password_changed_at.isoformat() if isinstance(password_changed_at, datetime) else password_changed_at
    to_encode = _add_security_claims(to_encode, jti=jti)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _add_security_claims(to_encode: dict, jti: Optional[str] = None) -> dict:
    from uuid import uuid4
    now = datetime.utcnow()
    to_encode["iat"] = now
    to_encode["nbf"] = now
    to_encode["jti"] = jti or str(uuid4())
    return to_encode


def _client_metadata(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    """Extract client IP and user agent from a request for session metadata."""
    if request is None:
        return None, None
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent") if request.headers else None
    return ip_address, user_agent


async def _start_session(
    db: AsyncSession,
    request: Optional[Request],
    user: User,
    jti: str,
) -> None:
    """Persist a server-side session bound to a freshly issued access token."""
    ip_address, user_agent = _client_metadata(request)
    await create_session(
        db,
        user_id=user.id,
        jti=jti,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def _primary_team_id(db: AsyncSession, user_id) -> Optional[str]:
    """Return the user's oldest team id, or None when they have no membership."""
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user_id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.scalars().first()
    return str(membership.team.id) if membership else None


async def _issue_tokens_for_user(
    db: AsyncSession,
    request: Optional[Request],
    user: User,
) -> "TokenRefreshResponse":
    """Issue a fresh access/refresh token pair plus a server-side session."""
    team_id = await _primary_team_id(db, user.id)
    jti = str(uuid4())
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at,
        jti=jti,
    )
    await _start_session(db, request, user, jti)
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


def _ensure_password_not_expired(user: User) -> None:
    """Block authentication when the user's password has expired."""
    if password_policy.is_password_expired(user.password_changed_at):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"PASSWORD_EXPIRED:{user.id}",
        )


def create_refresh_token(data: dict, password_changed_at: Optional[datetime] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS, hours=REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "refresh"})
    if password_changed_at:
        to_encode["password_changed_at"] = password_changed_at.isoformat() if isinstance(password_changed_at, datetime) else password_changed_at
    to_encode = _add_security_claims(to_encode)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def create_and_store_refresh_token(
    db: AsyncSession,
    user_id: UUID,
    password_changed_at: Optional[datetime] = None
) -> tuple[str, str]:
    jti = str(uuid4())
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS, hours=REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
        "jti": jti,
    }
    if password_changed_at:
        to_encode["password_changed_at"] = password_changed_at.isoformat() if isinstance(password_changed_at, datetime) else password_changed_at
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    db_refresh_token = RefreshToken(
        user_id=user_id,
        jti=jti,
        expires_at=expire,
        revoked=False,
    )
    db.add(db_refresh_token)
    await db.commit()
    return token, jti


async def revoke_refresh_token(db: AsyncSession, jti: str) -> bool:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    token = result.scalar_one_or_none()
    if token and not token.revoked:
        token.revoked = True
        token.revoked_at = datetime.utcnow()
        await db.commit()
        return True
    return False


async def get_refresh_token_by_jti(db: AsyncSession, jti: str) -> Optional[RefreshToken]:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    return result.scalar_one_or_none()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    password_changed_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalidated due to password change. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    session_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session is invalid or has expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        role: str = payload.get("role", "viewer")
        jti: str = payload.get("jti")
        token_password_changed_at = payload.get("password_changed_at")
        if email is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=email, user_id=user_id)
        token_data.role = role
        token_data.team_id = payload.get("team_id")
        user = await get_user_by_id(db, UUID(user_id))
        if not user:
            raise credentials_exception
        token_data.name = user.name
        token_data.email = user.email
        if user.password_changed_at:
            token_ts = datetime.fromisoformat(token_password_changed_at.replace("Z", "+00:00")) if token_password_changed_at else None
            user_pw_ts = user.password_changed_at.replace(tzinfo=None) if user.password_changed_at.tzinfo else user.password_changed_at
            if token_ts and token_ts < user_pw_ts:
                raise password_changed_exception

        # Server-side session enforcement: the token JTI must map to an active,
        # unexpired session owned by this user.
        if not jti:
            raise session_exception
        session = await validate_session(db, jti)
        if session is None or str(session.user_id) != str(user.id):
            raise session_exception

        # Rotate the session and issue a fresh short-lived access token on every
        # request. Clients read the rotated token from the response header.
        new_jti = str(uuid4())
        new_access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": str(user.id),
                "role": user.role,
                "team_id": token_data.team_id,
            },
            password_changed_at=user.password_changed_at,
            jti=new_jti,
        )
        await rotate_session(db, session, new_jti)
        token_data.jti = new_jti
        token_data.session_id = str(session.id)
        if response is not None:
            response.headers["X-New-Access-Token"] = new_access_token
            response.headers["X-Token-Rotated"] = "true"
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    return token_data


def require_admin(current_user: TokenData = Depends(get_current_user)):
    if getattr(current_user, 'role', None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )


def require_manager_or_admin(current_user: TokenData = Depends(get_current_user)):
    if getattr(current_user, 'role', None) not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin privileges required"
        )


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


@router.post("/register", response_model=TokenRefreshResponse)
@limiter.limit(lambda: get_tier_limit("unauthenticated_register"))
async def register(request: Request, response: Response, register_request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing_user = await get_user_by_email(db, register_request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=register_request.email,
        name=register_request.name,
        hashed_password=get_password_hash(register_request.password),
        role="admin",
        password_changed_at=datetime.utcnow(),
        password_history=[],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    team = Team(
        name=f"{user.name}'s Team",
        owner_id=user.id,
        description=f"Default team for {user.name}"
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    team_member = TeamMember(
        team_id=team.id,
        user_id=user.id,
        role="owner"
    )
    db.add(team_member)
    await db.commit()
    
    jti = str(uuid4())
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": str(team.id)},
        password_changed_at=user.password_changed_at,
        jti=jti,
    )
    await _start_session(db, request, user, jti)
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )

    try:
        await send_welcome_email(user.email)
    except Exception as e:
        logger.warning(f"Failed to send welcome email to {user.email}: {e}")

    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/login", response_model=TokenRefreshResponse)
@limiter.limit(lambda: get_tier_limit("unauthenticated_login"))
async def login(login_request: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    allowed, remaining = check_rate_limit(f"login:{login_request.username}", max_requests=10, window_seconds=60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

    lockout = await check_account_lockout(db, login_request.username)
    if lockout:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts. Please try again later."
        )

    user = await authenticate_user(db, login_request.username, login_request.password)
    if not user:
        await log_auth_event(db, "login_failed", email=login_request.username, ip_address=client_ip, status="failure")
        await create_account_lockout(db, login_request.username, "Too many failed login attempts")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    await clear_failed_login_attempts(login_request.username)

    _ensure_password_not_expired(user)

    if user.mfa_enabled:
        await log_auth_event(db, "mfa_required", email=user.email, user_id=user.id, ip_address=client_ip, status="mfa_required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MFA_REQUIRED:{user.id}"
        )

    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.scalars().first()
    team_id = str(membership.team.id) if membership else None

    await log_auth_event(db, "login_success", email=user.email, user_id=user.id, ip_address=client_ip, status="success")

    jti = str(uuid4())
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at,
        jti=jti,
    )
    await _start_session(db, request, user, jti)
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/token", response_model=TokenRefreshResponse)
@limiter.limit(lambda: get_tier_limit("unauthenticated_login"))
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
    ):
    client_ip = request.client.host if request and request.client else None
    allowed, remaining = check_rate_limit(f"token:{form_data.username}", max_requests=10, window_seconds=60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

    lockout = await check_account_lockout(db, form_data.username)
    if lockout:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts."
        )

    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        await log_auth_event(db, "token_login_failed", email=form_data.username, ip_address=client_ip, status="failure")
        await create_account_lockout(db, form_data.username, "Too many failed login attempts")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await clear_failed_login_attempts(form_data.username)

    _ensure_password_not_expired(user)

    if user.mfa_enabled:
        await log_auth_event(db, "token_mfa_required", email=user.email, user_id=user.id, ip_address=client_ip, status="mfa_required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MFA_REQUIRED:{user.id}"
        )

    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.scalars().first()
    team_id = str(membership.team.id) if membership else None

    await log_auth_event(db, "token_login_success", email=user.email, user_id=user.id, ip_address=client_ip, status="success")

    jti = str(uuid4())
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at,
        jti=jti,
    )
    await _start_session(db, request, user, jti)
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    refresh_request: Optional[RefreshTokenRequest] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = None
    if refresh_request is not None and refresh_request.refresh_token:
        refresh_token = refresh_request.refresh_token
    elif request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            refresh_token = auth_header[7:].strip()

    password_changed_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalidated due to password change. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    revoked_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token has been revoked. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not refresh_token:
        raise credentials_exception
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        jti = payload.get("jti")
        if not jti:
            raise credentials_exception
        token_password_changed_at = payload.get("password_changed_at")
        user_id = payload.get("user_id")
        if not user_id:
            raise credentials_exception
        db_token = await get_refresh_token_by_jti(db, jti)
        if not db_token or db_token.revoked:
            raise revoked_exception
        user = await get_user_by_id(db, UUID(user_id))
        if not user or not user.is_active:
            raise credentials_exception
        if token_password_changed_at and user.password_changed_at:
            token_ts = datetime.fromisoformat(token_password_changed_at.replace("Z", "+00:00"))
            user_pw_ts = user.password_changed_at.replace(tzinfo=None) if user.password_changed_at.tzinfo else user.password_changed_at
            if token_ts < user_pw_ts:
                raise password_changed_exception
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    await revoke_refresh_token(db, jti)
    
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.scalars().first()
    team_id = str(membership.team.id) if membership else None
    
    access_jti = str(uuid4())
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at,
        jti=access_jti,
    )
    await _start_session(db, request, user, access_jti)
    new_refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserWithTeams)
async def get_current_user_me(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user with full details including teams."""
    user = await get_user_by_id(db, UUID(current_user.user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
    )
    memberships = result.scalars().all()
    
    teams = [
        {
            "id": str(m.team.id),
            "name": m.team.name,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None
        }
        for m in memberships
    ]
    
    return UserWithTeams(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        teams=teams
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout current user by revoking refresh tokens and server-side sessions."""
    try:
        user_uuid = UUID(str(current_user.user_id))
    except (ValueError, TypeError):
        user_uuid = None

    if user_uuid is not None:
        await revoke_all_user_sessions(db, user_uuid)
        await db.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_uuid)
        )
        await db.commit()

        await log_auth_event(
            db, "logout", user_id=user_uuid,
            ip_address=request.client.host if request.client else None,
            status="success"
        )

    return LogoutResponse(message="Successfully logged out")


@router.post("/change-password", response_model=LogoutResponse)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change the current user's password and invalidate all active sessions."""
    try:
        user_uuid = UUID(str(current_user.user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = await get_user_by_id(db, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    policy_errors = password_policy.validate_password_strength(payload.new_password)
    if policy_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(policy_errors),
        )
    if password_policy.is_password_reused(
        payload.new_password, user.hashed_password, user.password_history
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "New password must not match your current password or any of "
                f"your last {password_policy.PASSWORD_HISTORY_SIZE} passwords"
            ),
        )

    user.password_history = password_policy.append_to_password_history(
        user.hashed_password, user.password_history
    )
    user.hashed_password = get_password_hash(payload.new_password)
    user.password_changed_at = datetime.utcnow()
    await db.commit()

    revoked = await revoke_all_user_sessions(db, user.id)
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()

    await log_auth_event(
        db, "password_change", user_id=user.id,
        ip_address=request.client.host if request.client else None,
        status="success"
    )

    return LogoutResponse(
        message=f"Password changed successfully. {revoked} session(s) invalidated."
    )


# ---------------------------------------------------------------------------
# Multi-factor authentication (TOTP)
# ---------------------------------------------------------------------------

@router.get("/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return whether MFA is enabled for the current user."""
    user = await get_user_by_id(db, UUID(str(current_user.user_id)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return MFAStatusResponse(
        mfa_enabled=bool(user.mfa_enabled),
        mfa_method=user.mfa_method,
    )


@router.post("/mfa/enable", response_model=MFAEnableResponse)
async def mfa_enable(
    payload: MFAEnableRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Begin MFA enrolment by generating a TOTP secret for the current user.

    MFA is not active until the user confirms a valid code via ``/mfa/verify``.
    """
    user = await get_user_by_id(db, UUID(str(current_user.user_id)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_totp_secret()
    user.mfa_secret = secret
    user.mfa_method = MFA_METHOD_TOTP
    user.mfa_enabled = False
    await db.commit()

    otpauth_uri = build_otpauth_uri(secret, user.email)
    return MFAEnableResponse(secret=secret, otpauth_url=build_qr_data_uri(otpauth_uri))


@router.post("/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    payload: MFAVerifyRequest,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA enrolment with a TOTP code and issue backup codes."""
    user = await get_user_by_id(db, UUID(str(current_user.user_id)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup has not been started",
        )
    if not verify_totp(user.mfa_secret, payload.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    backup_codes = generate_backup_codes()
    user.mfa_backup_codes = hash_backup_codes(backup_codes)
    user.mfa_enabled = True
    user.mfa_method = MFA_METHOD_TOTP
    await db.commit()

    await log_auth_event(
        db, "mfa_enabled", email=user.email, user_id=user.id,
        ip_address=request.client.host if request.client else None,
        status="success",
    )
    return MFAVerifyResponse(
        message="MFA enabled successfully. Store your backup codes securely.",
        backup_codes=backup_codes,
    )


@router.post("/mfa/disable", response_model=LogoutResponse)
async def mfa_disable(
    payload: MFADisableRequest,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA after re-confirming the password and a valid MFA code."""
    user = await get_user_by_id(db, UUID(str(current_user.user_id)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    valid = verify_totp(user.mfa_secret, payload.mfa_token)
    if not valid:
        valid, remaining = verify_and_consume_backup_code(
            payload.mfa_token, user.mfa_backup_codes
        )
        if valid:
            user.mfa_backup_codes = remaining

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_method = None
    user.mfa_backup_codes = None
    await db.commit()

    await log_auth_event(
        db, "mfa_disabled", email=user.email, user_id=user.id,
        ip_address=request.client.host if request.client else None,
        status="success",
    )
    return LogoutResponse(message="MFA disabled successfully")


@router.post("/mfa/validate", response_model=TokenRefreshResponse)
@limiter.limit(lambda: get_tier_limit("unauthenticated_login"))
async def mfa_validate(
    request: Request,
    response: Response,
    user_id: str = Query(...),
    mfa_token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Complete an MFA-gated login by validating the second factor.

    Called after ``/login`` responds with ``MFA_REQUIRED:<user_id>``.
    """
    client_ip = request.client.host if request.client else None
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user id",
        )

    user = await get_user_by_id(db, user_uuid)
    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA request",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    valid = verify_totp(user.mfa_secret, mfa_token)
    if not valid:
        valid, remaining = verify_and_consume_backup_code(
            mfa_token, user.mfa_backup_codes
        )
        if valid:
            user.mfa_backup_codes = remaining
            await db.commit()

    if not valid:
        await log_auth_event(
            db, "mfa_validation_failed", email=user.email, user_id=user.id,
            ip_address=client_ip, status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    _ensure_password_not_expired(user)

    await log_auth_event(
        db, "mfa_validation_success", email=user.email, user_id=user.id,
        ip_address=client_ip, status="success",
    )
    return await _issue_tokens_for_user(db, request, user)