"""
Data access audit middleware.

Records a structured audit entry for every data-access API operation
(reads and writes on customer data) into:
- The ELK pipeline (JSON logs via app.services.audit_logging)
- The data_access_audit_logs table (durable, queryable record)

Auth-focused operations under /api/auth/* are excluded here; the auth
router already records them via security_service.log_auth_event into
the audit_logs table.

Usage:
    from app.middleware.audit import setup_audit_logging

    app = FastAPI()
    setup_audit_logging(app)

Owner: Senior Engineer
Ticket: MID-313
"""

import logging
import os
import re
from typing import Optional, Tuple

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.correlation_id import get_correlation_id
from app.services.audit_logging import default_audit_service

logger = logging.getLogger("prequal.audit_middleware")

EXCLUDED_PATHS = {
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}
EXCLUDED_PREFIXES = (
    "/api/health",
    "/api/auth/",
)
PASS_THROUGH_METHODS = {"OPTIONS", "HEAD"}

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _extract_user_id(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    secret = os.environ.get("SECRET_KEY")
    if not token or not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("user_id")
    return str(user_id) if user_id else None


def _parse_resource(path: str) -> Tuple[str, Optional[str]]:
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] == "api":
        parts = parts[1:]
    if not parts:
        return "unknown", None
    resource_type = parts[0]
    resource_id = None
    if len(parts) > 1 and (_UUID_RE.match(parts[1]) or parts[1].isdigit()):
        resource_id = parts[1]
    return resource_type, resource_id


class DataAccessAuditMiddleware(BaseHTTPMiddleware):
    """Audit every data-access API request (ELK + data_access_audit_logs)."""

    def __init__(self, app, audit_service=default_audit_service):
        super().__init__(app)
        self.audit_service = audit_service

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            request.method.upper() in PASS_THROUGH_METHODS
            or path in EXCLUDED_PATHS
            or path.startswith(EXCLUDED_PREFIXES)
        ):
            return await call_next(request)

        user_id = _extract_user_id(request)
        request_id = get_correlation_id()

        self.audit_service.set_context(request_id=request_id, user_id=user_id)

        operation = request.method.upper()
        resource_type, resource_id = _parse_resource(path)

        status_code = 500
        error_message = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            try:
                self.audit_service.log(
                    operation_type=operation,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    request_id=request_id,
                    status="success" if status_code < 400 else "failure",
                    error_message=error_message,
                )
            except Exception:
                logger.exception(
                    "Failed to record data access audit entry for %s %s",
                    request.method, path,
                )


def setup_audit_logging(app):
    """Attach the data access audit middleware to the application."""
    app.add_middleware(DataAccessAuditMiddleware)
    logger.info("Data access audit middleware configured")
