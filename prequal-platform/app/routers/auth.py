import os
import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import jwt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
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
from app.middleware.rate_limit import limiter, RateLimitTiers
from app.services.notification_service import send_welcome_email, send_setup_complete_email

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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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


class LogoutResponse(BaseModel):
    message: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, password_changed_at: Optional[datetime] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES, hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "type": "access"})
    if password_changed_at:
        to_encode["password_changed_at"] = password_changed_at.isoformat() if isinstance(password_changed_at, datetime) else password_changed_at
    to_encode = _add_security_claims(to_encode)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _add_security_claims(to_encode: dict) -> dict:
    from uuid import uuid4
    now = datetime.utcnow()
    jti = str(uuid4())
    to_encode["iat"] = now
    to_encode["nbf"] = now
    to_encode["jti"] = jti
    return to_encode


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
    jti = str(uuid.uuid4())
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
    db: AsyncSession = Depends(get_db)
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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        role: str = payload.get("role", "viewer")
        token_password_changed_at = payload.get("password_changed_at")
        if email is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=email, user_id=user_id)
        token_data.role = role
        token_data.team_id = payload.get("team_id")
        user = await get_user_by_id(db, UUID(user_id))
        if user:
            token_data.name = user.name
            token_data.email = user.email
            if user.password_changed_at:
                token_ts = datetime.fromisoformat(token_password_changed_at.replace("Z", "+00:00")) if token_password_changed_at else None
                user_pw_ts = user.password_changed_at.replace(tzinfo=None) if user.password_changed_at.tzinfo else user.password_changed_at
                if token_ts and token_ts < user_pw_ts:
                    raise password_changed_exception
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
@limiter.limit(RateLimitTiers.UNAUTHENTICATED_DEFAULT)
async def register(request: Request, register_request: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
        password_changed_at=datetime.utcnow()
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
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": str(team.id)},
        password_changed_at=user.password_changed_at
    )
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
@limiter.limit(RateLimitTiers.UNAUTHENTICATED_LOGIN)
async def login(login_request: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
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
    membership = result.first()
    team_id = str(membership.team.id) if membership else None

    await log_auth_event(db, "login_success", email=user.email, user_id=user.id, ip_address=client_ip, status="success")

    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at
    )
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/token", response_model=TokenRefreshResponse)
@limiter.limit(RateLimitTiers.UNAUTHENTICATED_LOGIN)
async def login_for_access_token(
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
    membership = result.first()
    team_id = str(membership.team.id) if membership else None

    await log_auth_event(db, "token_login_success", email=user.email, user_id=user.id, ip_address=client_ip, status="success")

    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at
    )
    refresh_token, _ = await create_and_store_refresh_token(
        db, user.id, user.password_changed_at
    )
    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(refresh_token: str = Query(...), db: AsyncSession = Depends(get_db)):
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
    membership = result.first()
    team_id = str(membership.team.id) if membership else None
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id},
        password_changed_at=user.password_changed_at
    )
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
    """Logout current user by revoking their refresh tokens."""
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == UUID(current_user.user_id))
    )
    await db.commit()
    
    await log_auth_event(
        db, "logout", user_id=UUID(current_user.user_id), 
        ip_address=request.client.host if request.client else None,
        status="success"
    )
    
    return LogoutResponse(message="Successfully logged out")