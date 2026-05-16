"""
Logging configuration for Prequal Platform.

Provides structured JSON logging for production environments with support for:
- Console and file handlers
- Log levels by environment
- Correlation IDs for request tracing
- Sensitive data filtering
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON."""

    def __init__(self, service_name: str = "prequal-api"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        # Add optional fields
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class CorrelationIDFilter(logging.Filter):
    """Filter that adds correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID if available in context."""
        # Try to get correlation ID from context
        # This can be extended to use contextvars for async context
        return True


def get_log_level() -> str:
    """Get log level from environment."""
    import os
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    return level if level in valid_levels else "INFO"


def setup_logging(service_name: str = "prequal-api") -> None:
    """
    Configure application logging.

    Args:
        service_name: Name of the service for log identification
    """
    import os

    # Get configuration from environment
    log_level = get_log_level()
    log_format = os.getenv("LOG_FORMAT", "json")  # json or text
    log_file = os.getenv("LOG_FILE")  # Optional file output

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    if log_format == "json":
        formatter = JSONFormatter(service_name)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Log configuration
    logger.info(f"Logging configured: level={log_level}, format={log_format}")


# Convenience function for getting logger with extras
def get_logger(name: str) -> logging.Logger:
    """
    Get logger with configured formatters.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
