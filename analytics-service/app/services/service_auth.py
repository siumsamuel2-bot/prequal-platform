"""Service-to-service authentication and user context propagation.

Follows the security patterns established in MID-544/545/546/547:
- Internal callers (API gateway, monolith, other services) authenticate with a
  shared service API key via the `X-Service-Api-Key` header (constant-time compare).
- User context is propagated from the gateway via trusted `X-User-Id`,
  `X-User-Role`, and `X-Organization-Id` headers, which are only honored when
  the request carries a valid service API key.

Fail-closed: if SERVICE_API_KEY is not configured, service-authenticated
requests are rejected.
"""

import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

SERVICE_API_KEY_HEADER = "X-Service-Api-Key"
USER_ID_HEADER = "X-User-Id"
USER_ROLE_HEADER = "X-User-Role"
ORGANIZATION_ID_HEADER = "X-Organization-Id"


@dataclass
class UserContext:
    user_id: Optional[str]
    user_role: Optional[str]
    organization_id: Optional[str]
    via_service_key: bool


def require_service_auth(
    request: Request,
    x_service_api_key: Optional[str] = Header(default=None, alias=SERVICE_API_KEY_HEADER),
) -> None:
    """Validate the service API key. Raises 401 when missing/invalid or unconfigured."""
    expected = settings.SERVICE_API_KEY
    if not expected:
        logger.error("SERVICE_API_KEY is not configured; rejecting service-authenticated request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication is not configured",
        )
    if not x_service_api_key or not secrets.compare_digest(x_service_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
        )


def get_user_context(
    request: Request,
    x_user_id: Optional[str] = Header(default=None, alias=USER_ID_HEADER),
    x_user_role: Optional[str] = Header(default=None, alias=USER_ROLE_HEADER),
    x_organization_id: Optional[str] = Header(default=None, alias=ORGANIZATION_ID_HEADER),
) -> UserContext:
    """Build user context from trusted headers.

    Trusted headers are only honored when the request is service-authenticated
    (the gateway/monolith sets them after validating the user session).
    """
    via_service_key = bool(
        request.headers.get(SERVICE_API_KEY_HEADER)
        and settings.SERVICE_API_KEY
        and secrets.compare_digest(request.headers.get(SERVICE_API_KEY_HEADER, ""), settings.SERVICE_API_KEY)
    )
    if via_service_key:
        return UserContext(
            user_id=x_user_id,
            user_role=x_user_role,
            organization_id=x_organization_id,
            via_service_key=True,
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing service authentication for user context propagation",
    )


def require_admin_context(context: UserContext) -> UserContext:
    """Ensure the propagated user context has admin role."""
    if not context.via_service_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service authentication",
        )
    if context.user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return context
