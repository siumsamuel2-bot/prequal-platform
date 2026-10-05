"""
Security utilities for password hashing, token generation, and session validation.
"""
import os
import secrets
from datetime import datetime, timezone
from passlib.context import CryptContext
import redis.asyncio as redis


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__rounds=29000,
)


def hash_password(password: str) -> str:
    """Hash a password using pbkdf2_sha256."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hashed password."""
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def generate_rotation_token() -> str:
    """Generate a short-lived rotation token for session rotation."""
    return secrets.token_urlsafe(16)


def is_token_expiry_soon(expires_at: datetime) -> bool:
    """Check if a token is about to expire (within 5 minutes)."""
    if expires_at is None:
        return True
    now = datetime.utcnow()
    if expires_at.tzinfo is not None:
        now = now.replace(tzinfo=timezone.utc)
    return (expires_at - now).total_seconds() < 300


def is_token_expired(expires_at: datetime) -> bool:
    """Check if a token has expired."""
    if expires_at is None:
        return True
    now = datetime.utcnow()
    if expires_at.tzinfo is not None:
        now = now.replace(tzinfo=timezone.utc)
    return now > expires_at


# Redis session management
_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        from app.config import settings
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def store_session_in_redis(
    session_token: str,
    user_id: int,
    rotation_token: str,
    expires_in_seconds: int = 900,
) -> None:
    """Store session data in Redis with expiration."""
    client = await get_redis_client()
    session_data = {
        "user_id": str(user_id),
        "rotation_token": rotation_token,
    }
    await client.hset(f"session:{session_token}", mapping=session_data)
    await client.expire(f"session:{session_token}", expires_in_seconds)


async def get_session_from_redis(session_token: str) -> dict | None:
    """Get session data from Redis."""
    client = await get_redis_client()
    data = await client.hgetall(f"session:{session_token}")
    return data if data else None


async def delete_session_from_redis(session_token: str) -> None:
    """Delete session from Redis."""
    client = await get_redis_client()
    await client.delete(f"session:{session_token}")


async def delete_all_user_sessions_from_redis(user_id: int) -> None:
    """Delete all sessions for a user from Redis."""
    client = await get_redis_client()
    pattern = "session:*"
    async for key in client.scan_iter(match=pattern):
        session_data = await client.hgetall(key)
        if session_data.get("user_id") == str(user_id):
            await client.delete(key)