from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    organization_id: Optional[int] = None
    role: str = "user"


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    organization_id: Optional[int] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    organization_id: Optional[int]
    role: str
    is_active: bool
    created_at: datetime
    last_password_change: Optional[datetime]

    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserSessionResponse(BaseModel):
    id: int
    user_id: int
    token: str
    expires_at: datetime
    created_at: datetime
    is_valid: bool

    class Config:
        from_attributes = True


class SessionRotationRequest(BaseModel):
    current_token: str
    rotation_token: str


class SessionRotationResponse(BaseModel):
    token: str
    rotation_token: str
    expires_at: datetime