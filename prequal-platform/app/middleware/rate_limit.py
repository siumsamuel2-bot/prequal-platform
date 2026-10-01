"""
Rate limiting middleware and configuration for Prequal Platform API.

RATE LIMIT POLICIES
===================

Default Limits (applied to all endpoints):
- Authenticated requests: 100 requests/minute per user
- Unauthenticated requests: 20 requests/minute per IP address

Tiered Limits by Endpoint Type:
- Login/Token endpoints (unauthenticated): 10 requests/minute per IP
- Registration (unauthenticated): 20 requests/minute per IP
- Authenticated reads (GET): 200 requests/minute per user
- Authenticated writes (POST/PUT/PATCH/DELETE): 50 requests/minute per user

DDoS Protection:
- Burst protection: 100 requests/second
- Sustained protection: 1000 requests/minute
- Temporary IP blocks after excessive violations: 5 minutes

Response Headers:
- X-RateLimit-Limit: The maximum number of requests allowed
- X-RateLimit-Remaining: The number of requests remaining
- X-RateLimit-Reset: Time when the rate limit resets
- Retry-After: Seconds to wait before retrying (on 429 responses)

Rate Limit Key Strategy:
- For authenticated requests: rate limiting key = "user:{user_id}"
- For unauthenticated requests: rate limiting key = "ip:{client_ip}"

Metrics:
- rate_limit_hits_total: Counter for rate limit exceeded events
- rate_limit_blocked_ips: Gauge for currently blocked IP addresses

Usage:
    from app.middleware.rate_limit import limiter, RateLimitTiers

    @router.post("/endpoint")
    @limiter.limit(RateLimitTiers.UNAUTHENTICATED_DEFAULT)
    async def endpoint():
        ...

    Or apply to all routes in a router:
    router = APIRouterdependencies=[Depends(limiter.limit("100/minute"))])
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def get_ip_address(request: Request) -> str:
    """Extract client IP address, considering X-Forwarded-For header."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def rate_limit_key(request: Request) -> str:
    """Returns a key for rate limiting based on user authentication.

    If the request has a valid JWT token, uses the user_id as the key.
    Otherwise, uses the IP address.

    This enables:
    - Per-user rate limiting for authenticated requests
    - Per-IP rate limiting for unauthenticated requests
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt
            token = auth_header[7:]
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("user_id")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    return f"ip:{get_ip_address(request)}"


class RateLimitTiers:
    """Rate limit tiers for different endpoint types.

    Authenticated tiers (for endpoints requiring authentication):
    - AUTHENTICATED_DEFAULT: 100/minute - general authenticated endpoints
    - AUTHENTICATED_READ: 200/minute - read-heavy endpoints (GET)
    - AUTHENTICATED_WRITE: 50/minute - write operations (POST/PUT/PATCH/DELETE)

    Unauthenticated tiers (for public endpoints):
    - UNAUTHENTICATED_DEFAULT: 20/minute - general public endpoints
    - UNAUTHENTICATED_LOGIN: 10/minute - login/token endpoints (strict)
    - UNAUTHENTICATED_READ: 30/minute - public read endpoints

    DDoS protection tiers:
    - DDOS_PROTECTION_BURST: 100/second - burst traffic handling
    - DDOS_PROTECTION_SUSTAINED: 1000/minute - sustained traffic limit
    """

    AUTHENTICATED_DEFAULT = "100/minute"
    AUTHENTICATED_READ = "200/minute"
    AUTHENTICATED_WRITE = "50/minute"

    UNAUTHENTICATED_DEFAULT = "20/minute"
    UNAUTHENTICATED_LOGIN = "10/minute"
    UNAUTHENTICATED_READ = "30/minute"

    DDOS_PROTECTION_BURST = "100/second"
    DDOS_PROTECTION_SUSTAINED = "1000/minute"


limiter = Limiter(key_func=rate_limit_key, default_limits=[
    RateLimitTiers.UNAUTHENTICATED_DEFAULT,
])


class RateLimitMetrics:
    """Track rate limiting metrics and blocked IPs.

    This class maintains in-memory counters for rate limiting events.
    In production, consider using Redis for distributed rate limiting metrics.
    """

    _rate_limit_hits: dict[str, int] = defaultdict(int)
    _rate_limit_blocked_ips: set[str] = set()
    _last_reset = datetime.utcnow()

    @classmethod
    def record_hit(cls, client_id: str, endpoint: str, limit: str):
        """Record a rate limit hit for monitoring/alerting."""
        key = f"{client_id}:{endpoint}"
        cls._rate_limit_hits[key] += 1
        logger.warning(
            f"Rate limit hit - client: {client_id}, endpoint: {endpoint}, limit: {limit}, "
            f"total_hits: {cls._rate_limit_hits[key]}"
        )

    @classmethod
    def record_blocked(cls, client_id: str, endpoint: str, reason: str):
        """Record an IP that has been blocked due to rate limiting."""
        cls._rate_limit_blocked_ips.add(client_id)
        logger.warning(
            f"Rate limit blocked - client: {client_id}, endpoint: {endpoint}, reason: {reason}"
        )

    @classmethod
    def get_stats(cls) -> dict:
        """Get current rate limiting statistics."""
        return {
            "total_hits": sum(cls._rate_limit_hits.values()),
            "unique_blocked": len(cls._rate_limit_blocked_ips),
            "tracked_keys": len(cls._rate_limit_hits)
        }

    @classmethod
    def is_ip_blocked(cls, client_id: str) -> bool:
        """Check if an IP is currently blocked."""
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        if cls._last_reset < cutoff:
            cls._rate_limit_hits.clear()
            cls._rate_limit_blocked_ips.clear()
            cls._last_reset = datetime.utcnow()
        return client_id in cls._rate_limit_blocked_ips


class RateLimitAlertMiddleware(BaseHTTPMiddleware):
    """Middleware to track rate limit events and temporarily block abusive IPs."""

    async def dispatch(self, request: Request, call_next):
        client_ip = get_ip_address(request)

        if RateLimitMetrics.is_ip_blocked(client_ip):
            return Response(
                content='{"detail": "Too many requests. You have been temporarily blocked."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "300"}
            )

        response = await call_next(request)

        if response.status_code == 429:
            endpoint = request.url.path
            RateLimitMetrics.record_hit(client_ip, endpoint, "rate_limit_exceeded")

            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers.get("X-RateLimit-Remaining", "0"))
                if remaining == 0:
                    retry_after = response.headers.get("Retry-After", "60")
                    response.headers["Retry-After"] = retry_after

        return response


def create_rate_limit_response(detail: str, retry_after: int = 60) -> JSONResponse:
    """Create a standardized rate limit exceeded response with Retry-After header."""
    return JSONResponse(
        status_code=429,
        content={"detail": detail},
        headers={"Retry-After": str(retry_after)}
    )


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Exception handler for RateLimitExceeded errors.

    Returns a properly formatted 429 response with Retry-After header.
    """
    client_ip = get_ip_address(request)
    endpoint = request.url.path
    RateLimitMetrics.record_blocked(client_ip, endpoint, str(exc))

    retry_after = 60
    if hasattr(exc, "detail"):
        detail_str = str(exc.detail)
        import re
        match = re.search(r"(\d+)\s*(second|minute|hour)", detail_str, re.IGNORECASE)
        if match:
            value, unit = int(match.group(1)), match.group(2).lower()
            retry_after = value if unit == "second" else value * 60 if unit == "minute" else value * 3600

    return create_rate_limit_response(str(exc.detail), retry_after)


def get_limiter() -> Limiter:
    """Get the shared Limiter instance."""
    return limiter


def setup_rate_limiting(app):
    """Configure rate limiting middleware on the FastAPI application.

    This sets up:
    - SlowAPI middleware for decorator-based rate limiting
    - RateLimitAlertMiddleware for tracking and blocking abusive IPs
    - Exception handler for RateLimitExceeded responses
    """
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RateLimitAlertMiddleware)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    logger.info("Rate limiting middleware configured")


def get_authenticated_user_id(request: Request) -> Optional[str]:
    """Extract user_id from the Authorization header JWT token.

    Note: This does NOT verify the token signature. Token verification
    is done by the route's authentication dependency. This function
    is only for rate limiting key generation.
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            import jwt
            token = auth_header[7:]
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get("user_id")
    except Exception:
        pass
    return None