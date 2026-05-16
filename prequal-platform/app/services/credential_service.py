import os
import re
import uuid
import aiofiles
from datetime import datetime, date
from typing import Optional, Protocol, List, Tuple
from app.schemas.credential_upload import (
    ExtractedCredentialData,
    FileValidationResult,
    validate_file_content_type,
    validate_file_size,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_MIME_TYPES,
)


UPLOAD_DIRECTORY = os.getenv("CREDENTIAL_UPLOAD_DIR", "uploads/credentials")


CERTIFICATION_PATTERNS = {
    "OSHA_10": [
        r"OSHA\s*10[-\s]?Hour",
        r"OSHA\s*10",
    ],
    "OSHA_30": [
        r"OSHA\s*30[-\s]?Hour",
        r"OSHA\s*30",
    ],
    "First_Aid": [
        r"First\s*Aid",
        r"CPR[/\\]?AED",
        r"Heartsaver",
    ],
    "AWS_CWI": [
        r"Certified\s*Welding\s*Inspector",
        r"CWI",
        r"AWS\s*WC\d+",
    ],
    "NICET": [
        r"NICET\s*Level\s*\d+",
        r"National\s*Inspector\s*Testing",
    ],
    "AABC": [
        r"AABC\s*Certified",
    ],
    "NACE": [
        r"NACE\s*Certified",
        r"Coating\s*Inspector",
    ],
    "Pharmacist": [
        r"Pharmacist",
        r"RPh",
    ],
    "Medical": [
        r"MD|MBBS|DO",
        r"Physician",
    ],
    "General": [
        r"Certification",
        r"Certificate",
        r"License",
    ],
}

CERT_NUMBER_PATTERNS = [
    r"(?:Cert(?:ificate)?\s*(?:Number|No\\.?|#|\\.?)?\\s*:?\\s*)([A-Z0-9-]{4,20})",
    r"(?:License\s*(?:Number|No\\.?|#|\\.?)?\\s*:?\\s*)([A-Z0-9-]{4,20})",
    r"(?:Permit\s*(?:Number|No\\.?|#|\\.?)?\\s*:?\\s*)([A-Z0-9-]{4,20})",
    r"(?:ID\s*:?\\s*)([A-Z0-9-]{4,20})",
    r"\\b([A-Z]{1,3}[-]?\\d{5,12})\\b",
]

DATE_PATTERNS = [
    (r"(\\d{1,2})[/\\-](\\d{1,2})[/\\-](\\d{4})", "%m/%d/%Y"),
    (r"(\\d{1,2})[/\\-](\\d{1,2})[/\\-](\\d{2})", "%m/%d/%y"),
    (r"(\\d{4})[/\\-](\\d{1,2})[/\\-](\\d{1,2})", "%Y/%m/%d"),
    (r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\\s+(\\d{1,2}),?\\s+(\\d{4})", "%b %d %Y"),
    (r"(\\d{1,2})\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\\s+(\\d{4})", "%d %b %Y"),
]

ISSUING_AUTHORITY_KEYWORDS = [
    "issued by", "issued from", "issuing authority", "authorized by",
    "administered by", "recognized by", "approved by", "certified by",
]


class OCRExtractor(Protocol):
    async def extract(self, file_path: str, mime_type: str) -> ExtractedCredentialData:
        ...


class PatternOCRExtractor:
    def __init__(self):
        self._cert_patterns = CERTIFICATION_PATTERNS
        self._date_patterns = DATE_PATTERNS
        self._cert_number_patterns = CERT_NUMBER_PATTERNS
        self._authority_keywords = ISSUING_AUTHORITY_KEYWORDS

    def _extract_dates(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        issue_date = None
        expiration_date = None
        
        text_lower = text.lower()
        
        date_pattern_results = []
        for pattern, fmt in self._date_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                try:
                    if len(match.groups()) == 3:
                        if fmt.count("%Y") == 2:
                            day, month, year = match.groups()
                            parsed = datetime.strptime(f"{month}/{day}/{year}", "%m/%d/%Y").date()
                        elif fmt.count("%y") == 1:
                            day, month, year = match.groups()
                            parsed = datetime.strptime(f"{month}/{day}/{year}", "%m/%d/%y").date()
                        elif fmt.count("%Y") == 1 and fmt.count("%m") == 1:
                            year, month, day = match.groups()
                            parsed = datetime.strptime(f"{year}/{month}/{day}", "%Y/%m/%d").date()
                        else:
                            continue
                        date_pattern_results.append((match.start(), parsed))
                except (ValueError, TypeError):
                    continue
        
        date_pattern_results.sort(key=lambda x: x[0])
        
        issue_candidates = []
        exp_candidates = []
        
        for i, (pos, d) in enumerate(date_pattern_results):
            context_start = max(0, pos - 50)
            context_end = min(len(text), pos + 100)
            context = text[context_start:context_end].lower()
            
            if any(kw in context for kw in ["issued", "effective", "date of", "completion", "earned"]):
                if "expir" not in context and "valid until" not in context and "renew" not in context:
                    issue_candidates.append(d)
            
            if any(kw in context for kw in ["expir", "valid until", "valid through", "renew", "term"]):
                exp_candidates.append(d)
        
        if issue_candidates:
            issue_date = min(issue_candidates).isoformat() if issue_candidates else None
        if exp_candidates:
            expiration_date = max(exp_candidates).isoformat() if exp_candidates else None
        
        if not issue_date and date_pattern_results:
            issue_date = date_pattern_results[0][1].isoformat()
        if not expiration_date and len(date_pattern_results) > 1:
            expiration_date = date_pattern_results[-1][1].isoformat()
        
        return issue_date, expiration_date

    def _extract_cert_type(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        scores: dict[str, float] = {}
        
        for cert_type, patterns in self._cert_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    scores[cert_type] = scores.get(cert_type, 0) + 1.0
        
        if not scores:
            match = re.search(r"certificate\s+of\s+(\w+)", text_lower)
            if match:
                return match.group(1).title()
            return None
        
        return max(scores, key=scores.get)

    def _extract_cert_number(self, text: str) -> Optional[str]:
        seen = set()
        
        for pattern in self._cert_number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip().upper()
                if len(cleaned) >= 4 and cleaned not in seen:
                    seen.add(cleaned)
        
        for num in list(seen):
            if re.match(r"^\d+$", num):
                continue
            if len(num) >= 6:
                return num
        
        return list(seen)[0] if seen else None

    def _extract_authority(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        
        for keyword in self._authority_keywords:
            pattern = rf"{keyword}[:\s]+([A-Za-z\s,]+?)(?:\n|,|\.|;|$)"
            match = re.search(pattern, text_lower)
            if match:
                authority = match.group(1).strip()
                if len(authority) > 3 and len(authority) < 100:
                    return authority.title()
        
        known_authorities = [
            (r"osha\s+10\s+hour.*?(?:construction|industry)", "OSHA"),
            (r"osha\s+30\s+hour.*?(?:construction|industry)", "OSHA"),
            (r"american\s+heart\s+association", "American Heart Association"),
            (r"red\s+cross", "American Red Cross"),
            (r"national\s+registry\s+of.*?emergency", "National Registry of Emergency Medical Technicians"),
            (r"msha", "Mine Safety and Health Administration"),
        ]
        
        for pattern, name in known_authorities:
            if re.search(pattern, text_lower):
                return name
        
        return None

    async def extract(self, file_path: str, mime_type: str) -> ExtractedCredentialData:
        raw_text = await self._read_file_text(file_path, mime_type)
        
        if not raw_text:
            return ExtractedCredentialData(
                cert_type=None,
                cert_number=None,
                issue_date=None,
                expiration_date=None,
                issuing_authority=None,
                confidence=0.0,
                raw_text=None,
            )
        
        cert_type = self._extract_cert_type(raw_text)
        cert_number = self._extract_cert_number(raw_text)
        issue_date, expiration_date = self._extract_dates(raw_text)
        issuing_authority = self._extract_authority(raw_text)
        
        confidence = 0.0
        if cert_type:
            confidence += 0.3
        if cert_number:
            confidence += 0.3
        if issue_date:
            confidence += 0.15
        if expiration_date:
            confidence += 0.15
        if issuing_authority:
            confidence += 0.1
        
        return ExtractedCredentialData(
            cert_type=cert_type,
            cert_number=cert_number,
            issue_date=issue_date,
            expiration_date=expiration_date,
            issuing_authority=issuing_authority,
            confidence=confidence,
            raw_text=raw_text[:5000] if raw_text else None,
        )

    async def _read_file_text(self, file_path: str, mime_type: str) -> Optional[str]:
        if mime_type == "application/pdf":
            return await self._extract_pdf_text(file_path)
        elif mime_type.startswith("image/"):
            return await self._extract_image_text(file_path, mime_type)
        return None

    async def _extract_pdf_text(self, file_path: str) -> Optional[str]:
        try:
            import PyPDF2
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts) if text_parts else None
        except ImportError:
            return await self._fallback_text_extraction(file_path)
        except Exception:
            return await self._fallback_text_extraction(file_path)

    async def _extract_image_text(self, file_path: str, mime_type: str) -> Optional[str]:
        try:
            import pytesseract
            from PIL import Image
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            import io
            img = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(img)
            return text if text.strip() else None
        except ImportError:
            return None
        except Exception:
            return None

    async def _fallback_text_extraction(self, file_path: str) -> Optional[str]:
        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            text = content.decode("utf-8", errors="ignore")
            cleaned = re.sub(r"[^\x20-\x7E\n]", " ", text)
            cleaned = re.sub(r"\s+", " ", cleaned)
            return cleaned.strip() if cleaned.strip() else None
        except Exception:
            return None


class SimpleStubOCR:
    async def extract(self, file_path: str, mime_type: str) -> ExtractedCredentialData:
        return ExtractedCredentialData(
            cert_type=None,
            cert_number=None,
            issue_date=None,
            expiration_date=None,
            issuing_authority=None,
            confidence=0.0,
            raw_text="[OCR_STUB] No actual OCR extraction performed - integration point for future OCR service",
        )


class VirusScanner(Protocol):
    async def scan(self, file_path: str) -> tuple[bool, Optional[str]]:
        ...


class StubVirusScanner:
    async def scan(self, file_path: str) -> tuple[bool, Optional[str]]:
        return True, None


class FileStorageService:
    def __init__(self, upload_dir: str = UPLOAD_DIRECTORY):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    def _generate_stored_filename(self, original_filename: str) -> str:
        ext = os.path.splitext(original_filename)[1]
        return f"{uuid.uuid4()}{ext}"

    def get_file_path(self, stored_filename: str) -> str:
        return os.path.join(self.upload_dir, stored_filename)

    async def save_file(self, content: bytes, original_filename: str) -> tuple[str, str]:
        stored_filename = self._generate_stored_filename(original_filename)
        file_path = self.get_file_path(stored_filename)
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        return stored_filename, file_path

    async def delete_file(self, stored_filename: str) -> bool:
        file_path = self.get_file_path(stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


class CredentialUploadService:
    def __init__(
        self,
        storage: Optional[FileStorageService] = None,
        ocr_extractor: Optional[OCRExtractor] = None,
        virus_scanner: Optional[VirusScanner] = None,
    ):
        self.storage = storage or FileStorageService()
        self.ocr_extractor = ocr_extractor or PatternOCRExtractor()
        self.virus_scanner = virus_scanner or StubVirusScanner()

    def validate_upload(
        self,
        content: bytes,
        content_type: str,
    ) -> FileValidationResult:
        size = len(content)
        
        if not validate_file_size(size):
            return FileValidationResult(
                is_valid=False,
                error=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES / (1024*1024)}MB",
            )
        
        if not validate_file_content_type(content_type):
            return FileValidationResult(
                is_valid=False,
                error=f"File type '{content_type}' not allowed. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}",
            )
        
        return FileValidationResult(
            is_valid=True,
            mime_type=content_type,
            size_bytes=size,
        )

    async def process_upload(
        self,
        content: bytes,
        original_filename: str,
        content_type: str,
        subcontractor_id: uuid.UUID,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        validation = self.validate_upload(content, content_type)
        if not validation.is_valid:
            return None, None, validation.error
        
        stored_filename, file_path = await self.storage.save_file(content, original_filename)
        
        is_clean, scan_error = await self.virus_scanner.scan(file_path)
        if not is_clean:
            await self.storage.delete_file(stored_filename)
            return None, None, f"Virus scan failed: {scan_error}"
        
        extracted = await self.ocr_extractor.extract(file_path, content_type)
        
        return stored_filename, file_path, None

    async def extract_credential_data(self, file_path: str, mime_type: str) -> ExtractedCredentialData:
        return await self.ocr_extractor.extract(file_path, mime_type)

    async def delete_uploaded_file(self, stored_filename: str) -> bool:
        return await self.storage.delete_file(stored_filename)