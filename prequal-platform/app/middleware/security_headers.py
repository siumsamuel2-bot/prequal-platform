"""Security headers middleware for the Prequal Platform API.

Adds response headers to mitigate common web vulnerabilities:
- X-Content-Type-Options: nosniff - Prevents MIME-type sniffing
- X-Frame-Options: DENY - Prevents clickjacking attacks
- X-XSS-Protection: 1; mode=block - Enables XSS filter in older browsers
- Content-Security-Policy: default-src 'self' - Restricts resource loading
- Strict-Transport-Security - Forces HTTPS for future visits (MID-690)
- Referrer-Policy - Limits referer leakage to cross-origin targets (MID-690)
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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response