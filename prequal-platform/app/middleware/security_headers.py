"""Security headers middleware for the Prequal Platform API.

Adds response headers to mitigate common web vulnerabilities:
- X-Content-Type-Options: nosniff - Prevents MIME-type sniffing
- X-Frame-Options: DENY - Prevents clickjacking attacks
- X-XSS-Protection: 1; mode=block - Enables XSS filter in older browsers
- Content-Security-Policy: default-src 'self' - Restricts resource loading
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response