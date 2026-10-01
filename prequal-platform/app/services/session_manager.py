"""Session management service for secure token handling with short expiry and rotation.

This module provides functions for:
- Creating and validating server-side sessions
- Session token rotation on each request
- Session invalidation on logout and password change
- Secure session metadata tracking (IP, user agent, timestamps)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, status, Request
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import UserSession

logger = logging.getLogger(__name__)

# Configuration (these should ideally come from config/settings)
ACCESS_TOKEN_EXPIRE_MINUTES = 15


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    jti: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> UserSession:
    """Create a new server-side session for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        jti: Token ID (JTI) from the access token
        ip_address: Client IP address
        user_agent: Client user agent string
        
    Returns:
        The created UserSession object
    """
    expires_at = datetime.utcnow() + timedelta
