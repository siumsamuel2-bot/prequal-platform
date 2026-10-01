import os
import logging
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.models.security import AuditLog, FailedLoginAttempt, AccountLockout
from app.models.auth import User
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
FAILED_ATTEMPT_WINDOW_HOURS = 1
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 100

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(client_id: str, max_requests: int = RATE_LIMIT_MAX_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS) -> Tuple[bool, int]:
    now = time.time()
    window_start = now - window_seconds
    _rate_limit_store[client_id] = [t for t in _rate_limit_store[client_id] if t > window_start]
    _rate_limit_store[client_id].append(now)
    remaining = max(0, max_requests - len(_rate_limit_store[client_id]))
    return len(_rate_limit_store[client_id]) <= max_requests, remaining


def is_account_locked(email: str) -> Tuple[bool, Optional[datetime]]:
    return False, None


async def record_failed_login(db: AsyncSession, email: str, ip_address: Optional[str] = None) -> None:
    attempt = FailedLoginAttempt(email=email, ip_address=ip_address)
    db.add(attempt)
    await db.commit()
    logger.warning(f"Failed login attempt for {email} from {ip_address}")


async def check_account_lockout(db: AsyncSession, email: str) -> Optional[AccountLockout]:
    result = await db.execute(select(AccountLockout).where(AccountLockout.email == email.lower()))
    lockout = result.scalar_one_or_none()
    if lockout and lockout.locked_until > datetime.utcnow():
        return lockout
    if lockout and lockout.locked_until <= datetime.utcnow():
        await db.delete(lockout)
        await db.commit()
    return None


async def create_account_lockout(db: AsyncSession, email: str, reason: str) -> AccountLockout:
    result = await db.execute(select(AccountLockout).where(AccountLockout.email == email.lower()))
    existing = result.scalar_one_or_none()
    if existing:
        existing.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        existing.reason = reason
        await db.commit()
        return existing
    lockout = AccountLockout(
        email=email.lower(),
        locked_until=datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES),
        reason=reason
    )
    db.add(lockout)
    await db.commit()
    return lockout


async def clear_failed_login_attempts(email: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FailedLoginAttempt).where(FailedLoginAttempt.email == email.lower()))
        await db.commit()


async def audit_log(
    db: AsyncSession,
    action: str,
    resource: str,
    user_id: Optional[uuid.UUID] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    details: Optional[str] = None
) -> AuditLog:
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        details=details
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry


async def log_auth_event(
    db: AsyncSession,
    action: str,
    email: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    details: Optional[str] = None
) -> AuditLog:
    return await audit_log(
        db=db,
        action=action,
        resource="authentication",
        user_id=user_id,
        resource_id=email,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        details=details
    )


async def log_data_access(
    db: AsyncSession,
    action: str,
    resource: str,
    resource_id: str,
    user_id: uuid.UUID,
    ip_address: Optional[str] = None,
    details: Optional[str] = None
) -> AuditLog:
    return await audit_log(
        db=db,
        action=action,
        resource=resource,
        resource_id=resource_id,
        user_id=user_id,
        ip_address=ip_address,
        details=details
    )