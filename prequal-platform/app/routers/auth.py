import os
import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.auth import User, Team, TeamMember, Organization
from app.models.compliance import Project, Subcontractor
from app.schemas.compliance import (
    Token, TokenData, UserCreate, UserResponse, RegisterRequest, LoginRequest,
    UserWithTeams
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

SECRET_KEY = os.getenv("SECRET_KEY", "54EC409A2CC6B37C639C332264284D9A89CC5546B2022CA3A910178A3A202C53")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        role: str = payload.get("role", "viewer")
        if email is None:
            raise credentials_exception
        token_data = TokenData(sub=email, user_id=user_id)
        token_data.role = role
        token_data.team_id = payload.get("team_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
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


def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    pass


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


@router.post("/register", response_model=Token)
async def register(register_request: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
        role="admin"
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
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": str(team.id)}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(login_request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, login_request.username, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.first()
    team_id = str(membership.team.id) if membership else None
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.first()
    team_id = str(membership.team.id) if membership else None
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        user_id = payload.get("user_id")
        user = await get_user_by_id(db, UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .order_by(TeamMember.joined_at)
    )
    membership = result.first()
    team_id = str(membership.team.id) if membership else None
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role, "team_id": team_id}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserWithTeams)
async def read_users_me(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, current_user.sub)
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
    
    teams = []
    for m in memberships:
        teams.append({
            "id": str(m.team.id),
            "name": m.team.name,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None
        })
    
    return UserWithTeams(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        teams=teams
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_admin(current_user)
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/teams", response_model=dict)
async def create_team(
    name: str,
    description: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_manager_or_admin(current_user)
    team = Team(
        name=name,
        description=description,
        owner_id=UUID(current_user.user_id)
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    membership = TeamMember(
        team_id=team.id,
        user_id=UUID(current_user.user_id),
        role="owner"
    )
    db.add(membership)
    await db.commit()
    
    return {"id": str(team.id), "name": team.name, "description": team.description}


@router.get("/teams", response_model=list[dict])
async def list_user_teams(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == UUID(current_user.user_id))
    )
    memberships = result.scalars().all()
    return [
        {
            "id": str(m.team.id),
            "name": m.team.name,
            "description": m.team.description,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None
        }
        for m in memberships
    ]


@router.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: UUID,
    email: str,
    role: str = "member",
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_manager_or_admin(current_user)
    
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == UUID(current_user.user_id)
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized to add members")
    
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a team member")
    
    new_member = TeamMember(
        team_id=team_id,
        user_id=user.id,
        role=role
    )
    db.add(new_member)
    await db.commit()
    
    return {"message": f"Added {email} to team with role {role}"}


@router.get("/teams/{team_id}/projects", response_model=list[dict])
async def list_team_projects(
    team_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == UUID(current_user.user_id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a team member")
    
    projects_result = await db.execute(
        select(Project).where(Project.team_id == team_id)
    )
    projects = projects_result.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "project_name": p.project_name,
            "status": p.status
        }
        for p in projects
    ]


@router.post("/password-reset-request", response_model=MessageResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, request.email)
    if not user:
        return MessageResponse(message="If the email exists, a password reset link has been sent")
    
    reset_token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    
    user.password_reset_token = reset_token
    user.password_reset_expires = expires
    await db.commit()
    
    reset_url = f"https://prequal.example.com/reset-password?token={reset_token}"
    logger.info(f"Password reset requested for {request.email}. Reset link: {reset_url}")
    
    return MessageResponse(message="If the email exists, a password reset link has been sent")


class OrganizationCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: Optional[datetime] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


@router.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    slug = org_data.slug or org_data.name.lower().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    existing_org = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing_org.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization slug already exists")

    organization = Organization(name=org_data.name, slug=slug)
    db.add(organization)
    await db.commit()
    await db.refresh(organization)

    user = await get_user_by_id(db, UUID(current_user.user_id))
    if user:
        user.org_id = organization.id
        await db.commit()

    return OrganizationResponse(
        id=str(organization.id),
        name=organization.name,
        slug=organization.slug,
        created_at=organization.created_at
    )


@router.get("/organizations/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, UUID(current_user.user_id))
    if not user or not user.org_id:
        raise HTTPException(status_code=404, detail="No organization found")

    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        created_at=org.created_at
    )


@router.patch("/organizations/me", response_model=OrganizationResponse)
async def update_my_organization(
    org_data: OrganizationUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, UUID(current_user.user_id))
    if not user or not user.org_id:
        raise HTTPException(status_code=404, detail="No organization found")

    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org_data.name is not None:
        org.name = org_data.name
    if org_data.slug is not None:
        existing = await db.execute(select(Organization).where(Organization.slug == org_data.slug, Organization.id != org.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Organization slug already exists")
        org.slug = org_data.slug

    await db.commit()
    await db.refresh(org)

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        created_at=org.created_at
    )


@router.get("/onboarding/status", response_model=dict)
async def get_onboarding_status(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, UUID(current_user.user_id))
    has_org = user and user.org_id is not None

    result = await db.execute(select(Project).where(Project.owner_id == user.id))
    has_project = result.scalar_one_or_none() is not None

    from app.models.compliance import Subcontractor
    result = await db.execute(select(Subcontractor).limit(1))
    has_subcontractor = result.scalar_one_or_none() is not None

    return {
        "has_organization": has_org,
        "has_project": has_project,
        "has_subcontractor": has_subcontractor,
        "step": 1 if not has_org else 2 if not has_project else 3 if not has_subcontractor else 0
    }


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.password_reset_token == request.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    user.hashed_password = get_password_hash(request.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()
    
    return MessageResponse(message="Password has been reset successfully")