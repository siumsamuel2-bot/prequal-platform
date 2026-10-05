"""
User management endpoints for identity-service.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.models import User, Organization
from app.schemas.schemas import UserCreate, UserUpdate, UserResponse, OrganizationCreate, OrganizationResponse
from app.services.security import hash_password

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_create: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_create.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if organization exists
    if user_create.organization_id:
        org = db.query(Organization).filter(Organization.id == user_create.organization_id).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found",
            )

    hashed_password = hash_password(user_create.password)
    new_user = User(
        email=user_create.email,
        hashed_password=hashed_password,
        full_name=user_create.full_name,
        organization_id=user_create.organization_id,
        role=user_create.role,
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    organization_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List users with optional filters."""
    query = db.query(User)

    if organization_id is not None:
        query = query.filter(User.organization_id == organization_id)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """Update a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check email uniqueness if changing
    if user_update.email and user_update.email != user.email:
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check organization exists if changing
    if user_update.organization_id:
        org = db.query(Organization).filter(Organization.id == user_update.organization_id).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found",
            )

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    db.delete(user)
    db.commit()


@router.post("/organizations/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(org_create: OrganizationCreate, db: Session = Depends(get_db)):
    """Create a new organization."""
    org = Organization(name=org_create.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations/", response_model=List[OrganizationResponse])
def list_organizations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List organizations."""
    orgs = db.query(Organization).offset(skip).limit(limit).all()
    return orgs


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
def get_organization(org_id: int, db: Session = Depends(get_db)):
    """Get an organization by ID."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org