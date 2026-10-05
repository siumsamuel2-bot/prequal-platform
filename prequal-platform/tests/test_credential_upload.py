import pytest
from datetime import date, datetime
from uuid import uuid4
import os
import tempfile

from app.schemas.credential_upload import (
    CredentialUploadResponse,
    CredentialUploadWithExtraction,
    CredentialUploadStatusResponse,
    ExtractedCredentialData,
    FileValidationResult,
    UploadStatus,
    ExtractionStatus,
    VirusScanStatus,
    validate_file_content_type,
    validate_file_size,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
)
from app.services.credential_service import (
    FileStorageService,
    CredentialUploadService,
    SimpleStubOCR,
    StubVirusScanner,
    PatternOCRExtractor,
)


class TestUploadStatus:
    def test_upload_status_values(self):
        assert UploadStatus.PENDING.value == "pending"
        assert UploadStatus.PROCESSING.value == "processing"
        assert UploadStatus.COMPLETED.value == "completed"
        assert UploadStatus.FAILED.value == "failed"


class TestExtractionStatus:
    def test_extraction_status_values(self):
        assert ExtractionStatus.PENDING.value == "pending"
        assert ExtractionStatus.SUCCESS.value == "success"
        assert ExtractionStatus.FAILED.value == "failed"
        assert ExtractionStatus.NO_DATA.value == "no_data"


class TestVirusScanStatus:
    def test_virus_scan_status_values(self):
        assert VirusScanStatus.NOT_SCANNED.value == "not_scanned"
        assert VirusScanStatus.CLEAN.value == "clean"
        assert VirusScanStatus.INFECTED.value == "infected"
        assert VirusScanStatus.ERROR.value == "error"


class TestFileValidation:
    def test_validate_file_content_type_valid(self):
        assert validate_file_content_type("application/pdf") == True
        assert validate_file_content_type("image/jpeg") == True
        assert validate_file_content_type("image/png") == True

    def test_validate_file_content_type_invalid(self):
        assert validate_file_content_type("application/zip") == False
        assert validate_file_content_type("text/plain") == False
        assert validate_file_content_type("application/executable") == False

    def test_validate_file_size_valid(self):
        assert validate_file_size(1000) == True
        assert validate_file_size(MAX_FILE_SIZE_BYTES - 1) == True

    def test_validate_file_size_invalid_too_large(self):
        assert validate_file_size(MAX_FILE_SIZE_BYTES + 1) == False
        assert validate_file_size(100 * 1024 * 1024) == False

    def test_validate_file_size_invalid_zero(self):
        assert validate_file_size(0) == False


class TestExtractedCredentialData:
    def test_extracted_data_defaults(self):
        data = ExtractedCredentialData()
        assert data.cert_type is None
        assert data.cert_number is None
        assert data.confidence == 0.0

    def test_extracted_data_with_values(self):
        data = ExtractedCredentialData(
            cert_type="OSHA 30",
            cert_number="OSHA-12345",
            issue_date="2024-01-15",
            expiration_date="2025-01-15",
            issuing_authority="OSHA",
            confidence=0.85,
            raw_text="OSHA 30 card...",
        )
        assert data.cert_type == "OSHA 30"
        assert data.confidence == 0.85


class TestFileValidationResult:
    def test_validation_result_valid(self):
        result = FileValidationResult(
            is_valid=True,
            mime_type="application/pdf",
            size_bytes=1024,
        )
        assert result.is_valid == True
        assert result.error is None

    def test_validation_result_invalid(self):
        result = FileValidationResult(
            is_valid=False,
            error="File too large",
        )
        assert result.is_valid == False
        assert result.error == "File too large"


class TestCredentialUploadResponse:
    def test_upload_response_from_values(self):
        upload_id = uuid4()
        sub_id = uuid4()
        now = datetime.utcnow()
        
        response = CredentialUploadResponse(
            id=upload_id,
            subcontractor_id=sub_id,
            original_filename="osha_card.pdf",
            stored_filename=f"{uuid4()}.pdf",
            file_size=1024,
            mime_type="application/pdf",
            status=UploadStatus.PENDING,
            extraction_status=ExtractionStatus.PENDING,
            virus_scan_status=VirusScanStatus.NOT_SCANNED,
            created_at=now,
            updated_at=now,
        )
        
        assert response.original_filename == "osha_card.pdf"
        assert response.status == UploadStatus.PENDING


class TestCredentialUploadWithExtraction:
    def test_upload_with_extraction(self):
        upload_id = uuid4()
        sub_id = uuid4()
        now = datetime.utcnow()
        
        response = CredentialUploadWithExtraction(
            id=upload_id,
            subcontractor_id=sub_id,
            original_filename="osha_card.pdf",
            stored_filename=f"{uuid4()}.pdf",
            file_size=1024,
            mime_type="application/pdf",
            status=UploadStatus.COMPLETED,
            extraction_status=ExtractionStatus.SUCCESS,
            virus_scan_status=VirusScanStatus.CLEAN,
            extracted_cert_type="OSHA 30",
            extracted_cert_number="OSHA-12345",
            extracted_issue_date="2024-01-15",
            extracted_expiration_date="2025-01-15",
            extracted_issuing_authority="OSHA",
            ocr_raw_text="OSHA 30 card...",
            created_at=now,
            updated_at=now,
        )
        
        assert response.extracted_cert_type == "OSHA 30"
        assert response.extraction_status == ExtractionStatus.SUCCESS


class TestCredentialUploadStatusResponse:
    def test_status_response_pending(self):
        upload_id = uuid4()
        response = CredentialUploadStatusResponse(
            upload_id=upload_id,
            status=UploadStatus.PENDING,
            message="Upload received",
        )
        assert response.status == UploadStatus.PENDING
        assert response.certification_id is None

    def test_status_response_with_cert_id(self):
        upload_id = uuid4()
        cert_id = uuid4()
        response = CredentialUploadStatusResponse(
            upload_id=upload_id,
            status=UploadStatus.COMPLETED,
            message="Processing complete",
            certification_id=cert_id,
        )
        assert response.certification_id == cert_id


class TestSimpleStubOCR:
    @pytest.mark.asyncio
    async def test_stub_ocr_returns_empty_data(self):
        ocr = SimpleStubOCR()
        result = await ocr.extract("/fake/path.pdf", "application/pdf")
        
        assert result.cert_type is None
        assert result.cert_number is None
        assert result.confidence == 0.0
        assert "[OCR_STUB]" in result.raw_text


class TestStubVirusScanner:
    @pytest.mark.asyncio
    async def test_stub_scanner_returns_clean(self):
        scanner = StubVirusScanner()
        is_clean, error = await scanner.scan("/fake/path.pdf")
        
        assert is_clean == True
        assert error is None


class TestFileStorageService:
    @pytest.mark.asyncio
    async def test_save_and_get_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorageService(upload_dir=tmpdir)
            
            content = b"test file content"
            stored_filename, file_path = await storage.save_file(content, "test.txt")
            
            assert stored_filename.endswith(".txt")
            assert os.path.exists(file_path)
            
            async with aiofiles.open(file_path, "rb") as f:
                saved_content = await f.read()
            assert saved_content == content

    @pytest.mark.asyncio
    async def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorageService(upload_dir=tmpdir)
            
            content = b"test file content"
            stored_filename, _ = await storage.save_file(content, "test.txt")
            
            result = await storage.delete_file(stored_filename)
            assert result == True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorageService(upload_dir=tmpdir)
            
            result = await storage.delete_file("nonexistent.txt")
            assert result == False


class TestCredentialUploadService:
    def test_validate_upload_valid(self):
        service = CredentialUploadService()
        
        content = b"fake pdf content" * 100
        result = service.validate_upload(content, "application/pdf")
        
        assert result.is_valid == True

    def test_validate_upload_invalid_type(self):
        service = CredentialUploadService()
        
        content = b"zip content"
        result = service.validate_upload(content, "application/zip")
        
        assert result.is_valid == False
        assert "not allowed" in result.error

    def test_validate_upload_invalid_size(self):
        service = CredentialUploadService()
        
        content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        result = service.validate_upload(content, "application/pdf")
        
        assert result.is_valid == False
        assert "exceeds maximum" in result.error

    @pytest.mark.asyncio
    async def test_process_upload_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorageService(upload_dir=tmpdir)
            service = CredentialUploadService(storage=storage)
            
            content = b"fake pdf content"
            sub_id = uuid4()
            
            stored_filename, file_path, error = await service.process_upload(
                content=content,
                original_filename="test.pdf",
                content_type="application/pdf",
                subcontractor_id=sub_id,
            )
            
            assert error is None
            assert stored_filename is not None
            assert stored_filename.endswith(".pdf")
            assert os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_process_upload_invalid_type(self):
        service = CredentialUploadService()
        
        content = b"zip content"
        sub_id = uuid4()
        
        stored_filename, file_path, error = await service.process_upload(
            content=content,
            original_filename="test.zip",
            content_type="application/zip",
            subcontractor_id=sub_id,
        )
        
        assert stored_filename is None
        assert error is not None
        assert "not allowed" in error


class TestPatternOCRExtractor:
    @pytest.mark.asyncio
    async def test_extract_cert_type_osha_10(self):
        ocr = PatternOCRExtractor()
        assert ocr._extract_cert_type("OSHA 10 Hour Construction Safety") == "OSHA_10"

    @pytest.mark.asyncio
    async def test_extract_cert_type_osha_30(self):
        ocr = PatternOCRExtractor()
        assert ocr._extract_cert_type("OSHA 30 Hour Construction Safety") == "OSHA_30"

    @pytest.mark.asyncio
    async def test_extract_dates_mmddyyyy(self):
        ocr = PatternOCRExtractor()
        issue, exp = ocr._extract_dates("Issue Date: 01/15/2024, Expiration: 01/15/2027")
        assert issue == "2024-01-15"
        assert exp == "2027-01-15"

    @pytest.mark.asyncio
    async def test_extract_dates_yyyymmdd(self):
        ocr = PatternOCRExtractor()
        issue, exp = ocr._extract_dates("Issue Date: 2024-01-15, Expiration: 2027-01-15")
        assert issue == "2024-01-15"
        assert exp == "2027-01-15"

    @pytest.mark.asyncio
    async def test_extract_cert_number_patterns(self):
        ocr = PatternOCRExtractor()
        cert_num = ocr._extract_cert_number("Certificate Number: ABC123456789")
        assert cert_num is not None
        assert len(cert_num) >= 4

    @pytest.mark.asyncio
    async def test_extract_authority_osha(self):
        ocr = PatternOCRExtractor()
        authority = ocr._extract_authority("This certificate is issued by OSHA")
        assert authority == "Osha"

    @pytest.mark.asyncio
    async def test_extract_authority_aha(self):
        ocr = PatternOCRExtractor()
        authority = ocr._extract_authority("American Heart Association")
        assert authority == "American Heart Association"


import aiofiles