import pytest
from datetime import date, datetime
from uuid import uuid4
from pydantic import ValidationError

from app.schemas.compliance import (
    SubcontractorCreate, SubcontractorResponse, SubcontractorStatus,
    CertificationCreate, CertificationResponse, CertificationStatus,
    ViolationCreate, ViolationResponse, ViolationStatus,
    ProjectCreate, ProjectResponse, ProjectStatus,
    ComplianceStatusResponse,
    Token, LoginRequest, RegisterRequest,
    AlertType, AlertMethod
)


class TestSubcontractorSchemas:
    def test_subcontractor_create_valid(self):
        data = {
            "company_name": "ABC Construction",
            "email": "test@abc.com",
            "contact_first_name": "John",
            "contact_last_name": "Doe",
            "phone": "555-1234"
        }
        sub = SubcontractorCreate(**data)
        assert sub.company_name == "ABC Construction"
        assert sub.email == "test@abc.com"

    def test_subcontractor_create_invalid_email(self):
        with pytest.raises(ValidationError):
            SubcontractorCreate(
                company_name="ABC Construction",
                email="invalid-email"
            )

    def test_subcontractor_response_from_attributes(self):
        now = datetime.utcnow()
        data = {
            "id": uuid4(),
            "company_name": "ABC Construction",
            "email": "test@abc.com",
            "contact_first_name": "John",
            "contact_last_name": "Doe",
            "phone": "555-1234",
            "address_line1": None,
            "address_line2": None,
            "city": None,
            "state": None,
            "zip_code": None,
            "country": "USA",
            "ein": None,
            "license_number": None,
            "license_state": None,
            "license_expiration": None,
            "status": "active",
            "created_at": now,
            "updated_at": now
        }
        sub = SubcontractorResponse(**data)
        assert sub.company_name == "ABC Construction"
        assert sub.status == SubcontractorStatus.ACTIVE


class TestCertificationSchemas:
    def test_certification_create_valid(self):
        data = {
            "subcontractor_id": uuid4(),
            "certification_type": "OSHA 30",
            "expiration_date": date.today()
        }
        cert = CertificationCreate(**data)
        assert cert.certification_type == "OSHA 30"

    def test_certification_response_computed_fields(self):
        now = datetime.utcnow()
        future_date = date.today()
        data = {
            "id": uuid4(),
            "subcontractor_id": uuid4(),
            "certification_type": "OSHA 30",
            "certification_number": None,
            "issuing_authority": None,
            "issue_date": None,
            "expiration_date": future_date,
            "status": "valid",
            "verification_status": "unverified",
            "verified_at": None,
            "verified_by": None,
            "notes": None,
            "created_at": now,
            "updated_at": now
        }
        cert = CertificationResponse(**data)
        assert cert.is_expired == False
        assert cert.days_until_expiration == 0


class TestViolationSchemas:
    def test_violation_create_valid(self):
        data = {
            "subcontractor_id": uuid4(),
            "violation_type": "Safety",
            "description": "Missing guardrails",
            "issued_date": date.today()
        }
        violation = ViolationCreate(**data)
        assert violation.violation_type == "Safety"

    def test_violation_status_enum(self):
        assert ViolationStatus.OPEN.value == "open"
        assert ViolationStatus.RESOLVED.value == "resolved"


class TestProjectSchemas:
    def test_project_create_valid(self):
        data = {
            "project_name": "Building A",
            "project_number": "PRJ-001"
        }
        project = ProjectCreate(**data)
        assert project.project_name == "Building A"

    def test_project_response_from_attributes(self):
        now = datetime.utcnow()
        data = {
            "id": uuid4(),
            "project_name": "Building A",
            "project_number": "PRJ-001",
            "description": None,
            "client_name": None,
            "client_contact": None,
            "start_date": None,
            "estimated_end_date": None,
            "actual_end_date": None,
            "address_line1": None,
            "address_line2": None,
            "city": None,
            "state": None,
            "zip_code": None,
            "country": "USA",
            "budget": None,
            "status": "planning",
            "created_at": now,
            "updated_at": now
        }
        project = ProjectResponse(**data)
        assert project.project_name == "Building A"
        assert project.status == ProjectStatus.PLANNING


class TestComplianceStatus:
    def test_compliance_status_response(self):
        data = {
            "subcontractor_id": uuid4(),
            "company_name": "ABC Construction",
            "compliance_score": 85.0,
            "status": "COMPLIANT",
            "active_certifications": 5,
            "expiring_certifications": 1,
            "expired_certifications": 0,
            "open_violations": 0,
            "resolved_violations": 2
        }
        status = ComplianceStatusResponse(**data)
        assert status.compliance_score == 85.0
        assert status.status == "COMPLIANT"


class TestTokenSchemas:
    def test_token_response(self):
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        token = Token(**data)
        assert token.token_type == "bearer"

    def test_login_request(self):
        data = {
            "username": "admin",
            "password": "password123"
        }
        login = LoginRequest(**data)
        assert login.username == "admin"

    def test_register_request(self):
        data = {
            "email": "test@example.com",
            "password": "password123",
            "name": "Test User"
        }
        register = RegisterRequest(**data)
        assert register.email == "test@example.com"