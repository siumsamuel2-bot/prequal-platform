"""
Correlation ID middleware for request tracing across services.

Generates unique request IDs and propagates them through:
- Request context (via contextvars)
- Response headers (X-Request-ID)
- Log records (via logging Filter)
- Async task contexts (for background tasks)

Usage:
    from app.middleware.correlation_id import setup_correlation_id
    
    app = FastAPI()
    setup_correlation_id(app)
"""

import uuid
import logging
from contextvars import ContextVar
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

logger = logging.getLogger(__name__)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id.get()


def set_correlation_id(request_id: str) -> None:
    """Set the correlation ID in the current context."""
    correlation_id.set(request_id)


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation_id to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = correlation_id.get()
        if request_id:
            record.request_id = request_id
        return True


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates/extracts correlation IDs and stores in context."""

    async def dispatch(self, request: Request, call_next):
        existing_id = request.headers.get("X-Request-ID")
        request_id = existing_id if existing_id else str(uuid.uuid4())

        token = correlation_id.set(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            correlation_id.reset(token)


def setup_correlation_id(app):
    """Configure correlation ID handling on the FastAPI application.

    This sets up:
    - CorrelationIDMiddleware for request ID generation/propagation
    - Logging filter to add correlation_id to all log records

    The filter is attached to the root logger's HANDLERS, not just the root
    logger: logger-level filters do not apply to records propagated from
    descendant loggers (which is how all app loggers emit), while handler-level
    filters apply to every record that passes through the handler.
    """
    correlation_filter = CorrelationIDFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(correlation_filter)
    for handler in root_logger.handlers:
        handler.addFilter(correlation_filter)

    app.add_middleware(CorrelationIDMiddleware)

    logger.info("Correlation ID middleware configured")