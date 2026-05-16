from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from enum import Enum


class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    NO_DATA = "no_data"


class VirusScanStatus(str, Enum):
    NOT_SCANNED = "not_scanned"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


class CredentialUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subcontractor_id: UUID
    certification_id: Optional[UUID] = None
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    status: UploadStatus
    extraction_status: ExtractionStatus
    virus_scan_status: VirusScanStatus
    created_at: datetime
    updated_at: datetime


class CredentialUploadWithExtraction(CredentialUploadResponse):
    extracted_cert_type: Optional[str] = None
    extracted_cert_number: Optional[str] = None
    extracted_issue_date: Optional[str] = None
    extracted_expiration_date: Optional[str] = None
    extracted_issuing_authority: Optional[str] = None
    ocr_raw_text: Optional[str] = None


class CredentialUploadStatusResponse(BaseModel):
    upload_id: UUID
    status: UploadStatus
    message: str
    certification_id: Optional[UUID] = None


class ExtractedCredentialData(BaseModel):
    cert_type: Optional[str] = None
    cert_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    confidence: float = 0.0
    raw_text: Optional[str] = None


class FileValidationResult(BaseModel):
    is_valid: bool
    error: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/tiff",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


def validate_file_content_type(mime_type: str) -> bool:
    return mime_type.lower() in ALLOWED_MIME_TYPES


def validate_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES