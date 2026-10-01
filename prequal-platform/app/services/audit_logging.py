# Data Access Audit Logging Service
# Provides structured audit logging for read/write operations on customer data.
# Designed to emit JSON logs consumable by ELK stack.
# Owner: Data Engineer
# Ticket: MID-434

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from contextvars import ContextVar

# Context variables for correlation across async boundaries
_ctx_request_id: ContextVar[Optional[str]] = ContextVar("audit_request_id", default=None)
_ctx_user_id: ContextVar[Optional[str]] = ContextVar("audit_user_id", default=None)
_ctx_org_id: ContextVar[Optional[str]] = ContextVar("audit_org_id", default=None)
_ctx_session_id: ContextVar[Optional[str]] = ContextVar("audit_session_id", default=None)

logger = logging.getLogger("prequal.data_access_audit")


@dataclass
class DataAccessAuditEvent:
    operation_type: str
    resource_type: str
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    query_filter: Optional[str] = None
    fields_accessed: Optional[str] = None
    record_count: Optional[int] = None
    change_summary: Optional[str] = None
    before_values: Optional[Dict[str, Any]] = None
    after_values: Optional[Dict[str, Any]] = None
    status: str = "success"
    error_message: Optional[str] = None
    compliance_tag: Optional[str] = None
    retention_days: int = 2555
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.request_id:
            self.request_id = _ctx_request_id.get()
        if not self.user_id:
            self.user_id = _ctx_user_id.get()
        if not self.org_id:
            self.org_id = _ctx_org_id.get()
        if not self.session_id:
            self.session_id = _ctx_session_id.get()

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def validate(self) -> bool:
        return bool(self.operation_type and self.resource_type)


class AuditLoggingService:
    VALID_OPERATIONS = {
        "POST", "GET", "PUT", "DELETE", "PATCH",
        "BULK_READ", "BULK_WRITE", "EXPORT", "IMPORT"
    }

    def __init__(self, enable_elk: bool = True, enable_db: bool = True):
        self.enable_elk = enable_elk
        self.enable_db = enable_db

    @staticmethod
    def set_context(request_id=None, user_id=None, org_id=None, session_id=None):
        if request_id:
            _ctx_request_id.set(request_id)
        if user_id:
            _ctx_user_id.set(user_id)
        if org_id:
            _ctx_org_id.set(org_id)
        if session_id:
            _ctx_session_id.set(session_id)

    @staticmethod
    def clear_context():
        _ctx_request_id.set(None)
        _ctx_user_id.set(None)
        _ctx_org_id.set(None)
        _ctx_session_id.set(None)

    def log(self, operation_type, resource_type, resource_id=None,
            user_id=None, org_id=None, ip_address=None, user_agent=None,
            request_id=None, session_id=None, query_filter=None,
            fields_accessed=None, record_count=None, change_summary=None,
            before_values=None, after_values=None, status="success",
            error_message=None, compliance_tag=None, retention_days=2555):
        event = DataAccessAuditEvent(
            operation_type=operation_type.upper(),
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id or _ctx_user_id.get(),
            org_id=org_id or _ctx_org_id.get(),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id or _ctx_request_id.get(),
            session_id=session_id or _ctx_session_id.get(),
            query_filter=query_filter,
            fields_accessed=fields_accessed,
            record_count=record_count,
            change_summary=change_summary,
            before_values=before_values,
            after_values=after_values,
            status=status.lower(),
            error_message=error_message,
            compliance_tag=compliance_tag,
            retention_days=retention_days,
        )
        if event.operation_type not in self.VALID_OPERATIONS:
            raise ValueError(
                "Invalid operation_type: {event.operation_type}. "
                "Must be one of {self.VALID_OPERATIONS}"
            )
        if self.enable_elk:
            self._emit_to_elk(event)
        if self.enable_db:
            self._emit_to_db(event)
        return event

    def _emit_to_elk(self, event):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "data_access_audit",
            **event.to_dict(),
            "version": "1.0",
            "service": "prequal-api",
        }
        logger.info(json.dumps(log_entry))

    def _emit_to_db(self, event):
        pass


default_audit_service = AuditLoggingService()


def log_data_access(operation_type, resource_type, **kwargs):
    return default_audit_service.log(operation_type, resource_type, **kwargs)
