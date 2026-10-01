"""
Production Seed Script for Prequal Compliance Platform.

Populates production-ready reference and sample data for:
- Organizations, Teams, Users (auth)
- Subcontractors with encrypted PII columns
- Projects with encrypted client columns
- Certifications (valid, expiring soon, expired)
- Violations (open, resolved)
- Project assignments
- Email templates
- State compliance sources
- Data quality checks
- Subscriptions

Run after Alembic migrations have been applied.

Usage:
    python scripts/seed_production_baseline.py

Environment:
    DATABASE_URL - PostgreSQL connection string
    ENCRYPTION_KEY - Must match the key used by the app for decrypting
"""

from __future__ import annotations

import os
import sys
import uuid
import base64
import logging
from datetime import date, timedelta, datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prequal_compliance",
)

# ---------------------------------------------------------------------------
# Encryption helpers (must match application layer)
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:  # pragma: no cover
    raise RuntimeError("cryptography is required for seeding encrypted columns")


def _get_fernet() -> Fernet:
    key_material = os.getenv("ENCRYPTION_KEY", os.getenv("SECRET_KEY", ""))
    if not key_material:
        logger.warning("No ENCRYPTION_KEY or SECRET_KEY set. Using temporary key.")
        return Fernet(Fernet.generate_key())

    if len(key_material) < 32:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"prequal_salt",
            iterations=480000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(key_material.encode())))

    return Fernet(key_material.encode()[:32])


def _encrypt(plaintext: str | None, fernet: Fernet) -> str | None:
    if plaintext is None or plaintext == "":
        return None
    return fernet.encrypt(plaintext.encode()).decode()


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

SEED_ORGANIZATIONS = [
    {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Riverside Development Group",
        "slug": "riverside-development",
    },
]

SEED_TEAMS = [
    {
        "id": "aaaaaaaa-0000-0000-0000-000000000002",
        "name": "Project Management",
        "owner_id": "aaaaaaaa-0000-0000-0000-000000000003",
        "description": "Primary project management team",
    },
]

SEED_USERS = [
    {
        "id": "aaaaaaaa-0000-0000-0000-000000000003",
        "email": "admin@riversidedev.com",
        "name": "Sarah Jenkins",
        "hashed_password": "fakehash_for_seeding_only",  # noqa: S106
        "role": "admin",
        "is_active": True,
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
    },
]

SEED_SUBCONTRACTORS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_name": "Midland Contracting LLC",
        "contact_first_name": "Robert",
        "contact_last_name": "Miller",
        "email": "rmiller@midlandcontracting.com",
        "phone": "555-0101",
        "address_line1": "1200 Industrial Parkway",
        "address_line2": "Suite 400",
        "city": "Columbus",
        "state": "OH",
        "zip_code": "43210",
        "country": "USA",
        "ein": "12-3456789",
        "license_number": "OH-GC-001234",
        "license_state": "OH",
        "license_expiration": date.today() + timedelta(days=365),
        "status": "active",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "company_name": "Summit Electrical Services",
        "contact_first_name": "Lisa",
        "contact_last_name": "Chen",
        "email": "lchen@summitelec.com",
        "phone": "555-0202",
        "address_line1": "450 Commerce Drive",
        "city": "Cincinnati",
        "state": "OH",
        "zip_code": "45202",
        "country": "USA",
        "ein": "98-7654321",
        "license_number": "OH-ELC-00987",
        "license_state": "OH",
        "license_expiration": date.today() + timedelta(days=180),
        "status": "active",
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "company_name": "Metro HVAC Systems",
        "contact_first_name": "James",
        "contact_last_name": "Thompson",
        "email": "jthompson@metrohvac.com",
        "phone": "555-0303",
        "address_line1": "890 River Road",
        "city": "Cleveland",
        "state": "OH",
        "zip_code": "44101",
        "country": "USA",
        "ein": "55-1234567",
        "license_number": "OH-HVAC-00555",
        "license_state": "OH",
        "license_expiration": date.today() + timedelta(days=60),
        "status": "active",
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "company_name": "Pinnacle Concrete",
        "contact_first_name": "Maria",
        "contact_last_name": "Gonzalez",
        "email": "mgonzalez@pinnacleconcrete.com",
        "phone": "555-0404",
        "address_line1": "2100 Quarry Lane",
        "city": "Dayton",
        "state": "OH",
        "zip_code": "45402",
        "country": "USA",
        "ein": "77-4444444",
        "license_number": "OH-CON-123456",
        "license_state": "OH",
        "license_expiration": date.today() - timedelta(days=5),
        "status": "active",
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "company_name": "Advanced Plumbing Solutions",
        "contact_first_name": "David",
        "contact_last_name": "Park",
        "email": "dpark@advancedplumbing.com",
        "phone": "555-0505",
        "address_line1": "3400 Waterworks Blvd",
        "city": "Cleveland",
        "state": "OH",
        "zip_code": "44102",
        "country": "USA",
        "ein": "33-9876543",
        "license_number": "OH-PLB-00789",
        "license_state": "OH",
        "license_expiration": date.today() + timedelta(days=14),
        "status": "active",
    },
    {
        "id": "66666666-6666-6666-6666-666666666666",
        "company_name": "Steelframe Structural Inc",
        "contact_first_name": "Amanda",
        "contact_last_name": "Wright",
        "email": "awright@steelframe.com",
        "phone": "555-0606",
        "address_line1": "1900 Ironworks Way",
        "city": "Columbus",
        "state": "OH",
        "zip_code": "43215",
        "country": "USA",
        "ein": "66-1122334",
        "license_number": "OH-STL-00321",
        "license_state": "OH",
        "license_expiration": date.today() - timedelta(days=45),
        "status": "active",
    },
]

SEED_PROJECTS = [
    {
        "id": "99999999-9999-9999-9999-999999999999",
        "project_name": "Riverside Office Complex",
        "project_number": "PRJ-2026-001",
        "description": "5-story commercial office building",
        "client_name": "Riverside Development Group",
        "client_contact": "Michael Torres, VP Operations",
        "start_date": date(2026, 3, 1),
        "estimated_end_date": date(2026, 12, 15),
        "status": "active",
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
    },
    {
        "id": "88888888-8888-8888-8888-888888888888",
        "project_name": "Parkside Residential Tower",
        "project_number": "PRJ-2026-002",
        "description": "24-story mixed-use residential",
        "client_name": "Parkside Living LLC",
        "client_contact": "Jennifer Walsh, Project Director",
        "start_date": date(2026, 1, 15),
        "estimated_end_date": date(2027, 6, 30),
        "status": "active",
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
    },
    {
        "id": "77777777-7777-7777-7777-777777777777",
        "project_name": "Highway 71 Overpass Repair",
        "project_number": "PRJ-2026-003",
        "description": "State-funded bridge deck replacement",
        "client_name": "Ohio Department of Transportation",
        "client_contact": "Robert Stein, Chief Engineer",
        "start_date": date(2026, 4, 1),
        "estimated_end_date": date(2026, 10, 31),
        "status": "active",
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
    },
]

SEED_CERTIFICATIONS = [
    # Midland Contracting - expired cert
    {
        "id": "aaaa1111-1111-1111-1111-111111111111",
        "subcontractor_id": "11111111-1111-1111-1111-111111111111",
        "certification_type": "OSHA 30",
        "certification_number": "OSHA30-2025-MC001",
        "issuing_authority": "OSHA Training Institute",
        "issue_date": date(2025, 1, 10),
        "expiration_date": date(2026, 1, 10),
        "status": "expired",
        "verification_status": "verified",
        "notes": "Renewal requested; awaiting documentation",
    },
    # Midland Contracting - valid cert
    {
        "id": "aaaa2222-2222-2222-2222-222222222222",
        "subcontractor_id": "11111111-1111-1111-1111-111111111111",
        "certification_type": "OSHA 30",
        "certification_number": "OSHA30-2026-MC002",
        "issuing_authority": "OSHA Training Institute",
        "issue_date": date(2026, 1, 15),
        "expiration_date": date(2027, 1, 15),
        "status": "valid",
        "verification_status": "verified",
    },
    # Summit Electrical - long-term cert
    {
        "id": "aaaa3333-3333-3333-3333-333333333333",
        "subcontractor_id": "22222222-2222-2222-2222-222222222222",
        "certification_type": "OSHA 10",
        "certification_number": "OSHA10-2025-SE009",
        "issuing_authority": "OSHA Training Institute",
        "issue_date": date(2025, 6, 1),
        "expiration_date": date(2028, 6, 1),
        "status": "valid",
        "verification_status": "verified",
    },
    # Metro HVAC - EPA cert
    {
        "id": "aaaa4444-4444-4444-4444-444444444444",
        "subcontractor_id": "33333333-3333-3333-3333-333333333333",
        "certification_type": "EPA Refrigerant Handler",
        "certification_number": "EPA-608-2024-HV005",
        "issuing_authority": "EPA",
        "issue_date": date(2024, 9, 15),
        "expiration_date": date(2029, 9, 15),
        "status": "valid",
        "verification_status": "verified",
    },
    # Pinnacle Concrete - soon to expire
    {
        "id": "aaaa5555-5555-5555-5555-555555555555",
        "subcontractor_id": "44444444-4444-4444-4444-444444444444",
        "certification_type": "OSHA 30",
        "certification_number": "OSHA30-2024-PC003",
        "issuing_authority": "OSHA Training Institute",
        "issue_date": date(2024, 6, 1),
        "expiration_date": date(2025, 6, 1),
        "status": "expired",
        "verification_status": "verified",
        "notes": "Expired; renewal overdue by 5 days",
    },
    # Advanced Plumbing - expiring in 14 days
    {
        "id": "aaaa6666-6666-6666-6666-666666666666",
        "subcontractor_id": "55555555-5555-5555-5555-555555555555",
        "certification_type": "OSHA 10",
        "certification_number": "OSHA10-2024-AP004",
        "issuing_authority": "OSHA Training Institute",
        "issue_date": date(2024, 7, 1),
        "expiration_date": date(2025, 7, 1),
        "status": "valid",
        "verification_status": "verified",
        "notes": "Expires in 14 days - alert should trigger",
    },
    # Steelframe Structural - expired license
    {
        "id": "aaaa7777-7777-7777-7777-777777777777",
        "subcontractor_id": "66666666-6666-6666-6666-666666666666",
        "certification_type": "Structural Welding",
        "certification_number": "AWS-D1.1-2023-SW001",
        "issuing_authority": "American Welding Society",
        "issue_date": date(2023, 2, 1),
        "expiration_date": date(2024, 2, 1),
        "status": "expired",
        "verification_status": "verified",
        "notes": "Expired 45 days ago; not renewed",
    },
]

SEED_VIOLATIONS = [
    {
        "id": "bbbb1111-1111-1111-1111-111111111111",
        "subcontractor_id": "11111111-1111-1111-1111-111111111111",
        "violation_type": "OSHA - Fall Protection",
        "violation_code": "1926.501(b)(1)",
        "description": "Failure to provide fall protection for work at heights over 6 feet.",
        "issued_by": "OSHA Area Office - Columbus",
        "issued_date": date(2025, 8, 14),
        "status": "resolved",
        "penalty_amount": 3520.00,
        "is_osha_violation": True,
        "osha_violation_id": "V-20250814-001-MC",
        "inspection_number": "INS-2025-COL-0887",
        "standard_cited": "1926.501(b)(1)",
        "initial_penalty": 3520.00,
        "final_penalty": 2000.00,
        "gravity_score": 8.0,
        "probability_score": 6.0,
        "risk_category": "high",
        "site_city": "Columbus",
        "site_state": "OH",
        "naics_code": "236220",
    },
    {
        "id": "bbbb2222-2222-2222-2222-222222222222",
        "subcontractor_id": "33333333-3333-3333-3333-333333333333",
        "violation_type": "OSHA - Electrical Safety",
        "violation_code": "1926.404(b)(1)",
        "description": "Exposed electrical equipment without proper guarding.",
        "issued_by": "OSHA Area Office - Cleveland",
        "issued_date": date(2026, 1, 22),
        "status": "open",
        "penalty_amount": 13147.00,
        "is_osha_violation": True,
        "osha_violation_id": "V-20260122-002-MH",
        "inspection_number": "INS-2026-CLE-0152",
        "standard_cited": "1926.404(b)(1)",
        "initial_penalty": 13147.00,
        "final_penalty": 13147.00,
        "gravity_score": 9.0,
        "probability_score": 7.0,
        "risk_category": "serious",
        "site_city": "Cleveland",
        "site_state": "OH",
        "naics_code": "238220",
    },
    {
        "id": "bbbb3333-3333-3333-3333-333333333333",
        "subcontractor_id": "44444444-4444-4444-4444-444444444444",
        "violation_type": "OSHA - Scaffold Safety",
        "violation_code": "1926.451(g)(1)",
        "description": "Scaffold planking not fully decked; missing guardrails on open sides.",
        "issued_by": "OSHA Area Office - Dayton",
        "issued_date": date(2025, 11, 3),
        "status": "open",
        "penalty_amount": 8250.00,
        "is_osha_violation": True,
        "osha_violation_id": "V-20251103-003-PC",
        "inspection_number": "INS-2025-DAY-0042",
        "standard_cited": "1926.451(g)(1)",
        "initial_penalty": 8250.00,
        "final_penalty": 8250.00,
        "gravity_score": 7.0,
        "probability_score": 5.0,
        "risk_category": "serious",
        "site_city": "Dayton",
        "site_state": "OH",
        "naics_code": "236220",
    },
]

SEED_PROJECT_SUBCONTRACTORS = [
    {
        "project_id": "99999999-9999-9999-9999-999999999999",
        "subcontractor_id": "11111111-1111-1111-1111-111111111111",
        "role": "General Contractor",
        "start_date": date(2026, 3, 1),
        "status": "active",
    },
    {
        "project_id": "99999999-9999-9999-9999-999999999999",
        "subcontractor_id": "22222222-2222-2222-2222-222222222222",
        "role": "Electrical Subcontractor",
        "start_date": date(2026, 4, 1),
        "status": "active",
    },
    {
        "project_id": "88888888-8888-8888-8888-888888888888",
        "subcontractor_id": "33333333-3333-3333-3333-333333333333",
        "role": "HVAC Subcontractor",
        "start_date": date(2026, 2, 15),
        "status": "active",
    },
    {
        "project_id": "88888888-8888-8888-8888-888888888888",
        "subcontractor_id": "44444444-4444-4444-4444-444444444444",
        "role": "Concrete Subcontractor",
        "start_date": date(2026, 2, 1),
        "status": "active",
    },
    {
        "project_id": "77777777-7777-7777-7777-777777777777",
        "subcontractor_id": "55555555-5555-5555-5555-555555555555",
        "role": "Plumbing Subcontractor",
        "start_date": date(2026, 4, 15),
        "status": "active",
    },
    {
        "project_id": "77777777-7777-7777-7777-777777777777",
        "subcontractor_id": "66666666-6666-6666-6666-666666666666",
        "role": "Structural Steel",
        "start_date": date(2026, 4, 1),
        "status": "active",
    },
]

SEED_EMAIL_TEMPLATES = [
    {
        "id": "cccc0001-0000-0000-0000-000000000001",
        "name": "cert_expiration_alert",
        "description": "Alert sent when a certification is nearing expiration",
        "template_type": "alert",
        "alert_type": "certification_expiration",
        "subject_template": "Certification Expiring Soon: {{certification_type}}",
        "html_body_template": "<html><body><h1>Certification Expiration Alert</h1><p>The {{certification_type}} for {{subcontractor_name}} expires on {{expiration_date}}.</p></body></html>",
        "text_body_template": "Certification Expiration Alert\n\nThe {{certification_type}} for {{subcontractor_name}} expires on {{expiration_date}}.",
        "template_variables": ["certification_type", "subcontractor_name", "expiration_date"],
        "language": "en",
        "is_active": True,
        "is_default": True,
    },
    {
        "id": "cccc0002-0000-0000-0000-000000000002",
        "name": "violation_alert",
        "description": "Alert sent when a new violation is recorded",
        "template_type": "alert",
        "alert_type": "violation",
        "subject_template": "New Violation: {{violation_type}}",
        "html_body_template": "<html><body><h1>New Violation Alert</h1><p>{{subcontractor_name}} has a new {{violation_type}} violation issued by {{issued_by}}.</p></body></html>",
        "text_body_template": "New Violation Alert\n\n{{subcontractor_name}} has a new {{violation_type}} violation issued by {{issued_by}}.",
        "template_variables": ["subcontractor_name", "violation_type", "issued_by"],
        "language": "en",
        "is_active": True,
        "is_default": True,
    },
    {
        "id": "cccc0003-0000-0000-0000-000000000003",
        "name": "renewal_request",
        "description": "Notification sent when a certification renewal is requested",
        "template_type": "notification",
        "alert_type": "renewal_request",
        "subject_template": "Certification Renewal Requested: {{certification_type}}",
        "html_body_template": "<html><body><h1>Renewal Request</h1><p>A renewal has been requested for {{certification_type}} ({{certification_number}}).</p></body></html>",
        "text_body_template": "Renewal Request\n\nA renewal has been requested for {{certification_type}} ({{certification_number}}).",
        "template_variables": ["certification_type", "certification_number"],
        "language": "en",
        "is_active": True,
        "is_default": True,
    },
    {
        "id": "cccc0004-0000-0000-0000-000000000004",
        "name": "weekly_digest",
        "description": "Weekly summary of compliance status",
        "template_type": "digest",
        "alert_type": None,
        "subject_template": "Weekly Compliance Digest for {{org_name}}",
        "html_body_template": "<html><body><h1>Weekly Compliance Digest</h1><p>Expiring: {{expiring_count}} | Open Violations: {{open_violations}} | Renewals Pending: {{renewals_pending}}</p></body></html>",
        "text_body_template": "Weekly Compliance Digest\n\nExpiring: {{expiring_count}}\nOpen Violations: {{open_violations}}\nRenewals Pending: {{renewals_pending}}",
        "template_variables": ["org_name", "expiring_count", "open_violations", "renewals_pending"],
        "language": "en",
        "is_active": True,
        "is_default": True,
    },
]

SEED_STATE_COMPLIANCE_SOURCES = [
    {
        "state_code": "OH",
        "state_name": "Ohio",
        "api_url": "https://com.ohio.gov/wps/portal/gov/oh/licensing",
        "api_key_env_var": "OH_LICENSE_API_KEY",
        "is_active": True,
        "priority": 1,
        "source_type": "license_board",
    },
    {
        "state_code": "PA",
        "state_name": "Pennsylvania",
        "api_url": "https://www.dos.pa.gov/ProfessionalLicensing",
        "api_key_env_var": "PA_LICENSE_API_KEY",
        "is_active": True,
        "priority": 2,
        "source_type": "license_board",
    },
    {
        "state_code": "KY",
        "state_name": "Kentucky",
        "api_url": "https:// Kentucky.gov/professional-licensing",
        "api_key_env_var": "KY_LICENSE_API_KEY",
        "is_active": False,
        "priority": 3,
        "source_type": "license_board",
    },
    {
        "state_code": "MI",
        "state_name": "Michigan",
        "api_url": "https://www.michigan.gov/lara",
        "api_key_env_var": "MI_LICENSE_API_KEY",
        "is_active": True,
        "priority": 4,
        "source_type": "license_board",
    },
    {
        "state_code": "IN",
        "state_name": "Indiana",
        "api_url": "https://www.in.gov/pla/licensing",
        "api_key_env_var": "IN_LICENSE_API_KEY",
        "is_active": False,
        "priority": 5,
        "source_type": "license_board",
    },
]

SEED_DATA_QUALITY_CHECKS = [
    {
        "check_name": "subcontractor_email_format",
        "table_name": "subcontractors",
        "column_name": "email",
        "check_type": "format",
        "check_query": "SELECT COUNT(*) FROM subcontractors WHERE email NOT LIKE '%@%.%' OR email IS NULL",
        "expected_threshold": 0.0,
        "severity": "warning",
        "is_active": True,
        "description": "All subcontractors should have a valid email format",
    },
    {
        "check_name": "certification_expiration_not_null",
        "table_name": "certifications",
        "column_name": "expiration_date",
        "check_type": "not_null",
        "check_query": "SELECT COUNT(*) FROM certifications WHERE expiration_date IS NULL",
        "expected_threshold": 0.0,
        "severity": "critical",
        "is_active": True,
        "description": "All certifications must have an expiration date",
    },
    {
        "check_name": "violation_penalty_non_negative",
        "table_name": "violations",
        "column_name": "penalty_amount",
        "check_type": "range",
        "check_query": "SELECT COUNT(*) FROM violations WHERE penalty_amount < 0",
        "expected_threshold": 0.0,
        "severity": "warning",
        "is_active": True,
        "description": "Violation penalties should be non-negative",
    },
    {
        "check_name": "project_subcontractor_unique",
        "table_name": "project_subcontractors",
        "column_name": None,
        "check_type": "duplicate",
        "check_query": "SELECT COUNT(*) FROM (SELECT project_id, subcontractor_id, COUNT(*) FROM project_subcontractors GROUP BY project_id, subcontractor_id HAVING COUNT(*) > 1) AS duplicates",
        "expected_threshold": 0.0,
        "severity": "critical",
        "is_active": True,
        "description": "Project-subcontractor pairs must be unique",
    },
    {
        "check_name": "subcontractor_ein_format",
        "table_name": "subcontractors",
        "column_name": "ein",
        "check_type": "format",
        "check_query": "SELECT COUNT(*) FROM subcontractors WHERE ein IS NOT NULL AND ein NOT LIKE '__-_______'",
        "expected_threshold": 0.0,
        "severity": "warning",
        "is_active": True,
        "description": "EIN format should match ##-#######",
    },
    {
        "check_name": "license_expiration_future",
        "table_name": "subcontractors",
        "column_name": "license_expiration",
        "check_type": "range",
        "check_query": "SELECT COUNT(*) FROM subcontractors WHERE license_expiration IS NOT NULL AND license_expiration < CURRENT_DATE - INTERVAL '30 days' AND status = 'active'",
        "expected_threshold": 0.0,
        "severity": "warning",
        "is_active": True,
        "description": "Active subcontractors should not have licenses expired by more than 30 days",
    },
    {
        "check_name": "certification_status_consistency",
        "table_name": "certifications",
        "column_name": "status",
        "check_type": "enum",
        "check_query": "SELECT COUNT(*) FROM certifications WHERE status NOT IN ('valid', 'expired', 'revoked', 'pending')",
        "expected_threshold": 0.0,
        "severity": "critical",
        "is_active": True,
        "description": "Certification status must be one of: valid, expired, revoked, pending",
    },
]

SEED_SUBSCRIPTIONS = [
    {
        "id": "dddd0001-0000-0000-0000-000000000001",
        "org_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "plan": "starter",
        "status": "active",
    },
]

# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------

def seed_database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    url = DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")
    engine = create_engine(url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    fernet = _get_fernet()

    summary: dict = {"tables": [], "counts": {}}

    try:
        # ------------------------------------------------------------------
        # Organizations
        # ------------------------------------------------------------------
        for org in SEED_ORGANIZATIONS:
            session.execute(
                text(
                    """INSERT INTO organizations (id, name, slug)
                    VALUES (:id, :name, :slug)
                    ON CONFLICT (slug) DO NOTHING"""
                ),
                org,
            )
        summary["tables"].append("organizations")
        summary["counts"]["organizations"] = len(SEED_ORGANIZATIONS)
        logger.info("Seeded %d organizations.", len(SEED_ORGANIZATIONS))

        # ------------------------------------------------------------------
        # Teams
        # ------------------------------------------------------------------
        for team in SEED_TEAMS:
            session.execute(
                text(
                    """INSERT INTO teams (id, name, description, owner_id)
                    VALUES (:id, :name, :description, :owner_id)
                    ON CONFLICT DO NOTHING"""
                ),
                team,
            )
        summary["tables"].append("teams")
        summary["counts"]["teams"] = len(SEED_TEAMS)
        logger.info("Seeded %d teams.", len(SEED_TEAMS))

        # ------------------------------------------------------------------
        # Users
        # ------------------------------------------------------------------
        for user in SEED_USERS:
            session.execute(
                text(
                    """INSERT INTO users (id, email, name, hashed_password, role, is_active, org_id)
                    VALUES (:id, :email, :name, :hashed_password, :role, :is_active, :org_id)
                    ON CONFLICT (email) DO NOTHING"""
                ),
                user,
            )
        summary["tables"].append("users")
        summary["counts"]["users"] = len(SEED_USERS)
        logger.info("Seeded %d users.", len(SEED_USERS))

        # ------------------------------------------------------------------
        # Team memberships
        # ------------------------------------------------------------------
        session.execute(
            text(
                """INSERT INTO team_members (id, team_id, user_id, role)
                VALUES (:id, :team_id, :user_id, :role)
                ON CONFLICT DO NOTHING"""  # relies on uq_team_member
            ),
            {
                "id": "eeee0001-0000-0000-0000-000000000001",
                "team_id": "aaaaaaaa-0000-0000-0000-000000000002",
                "user_id": "aaaaaaaa-0000-0000-0000-000000000003",
                "role": "admin",
            },
        )
        summary["tables"].append("team_members")
        summary["counts"]["team_members"] = 1
        logger.info("Seeded 1 team membership.")

        # ------------------------------------------------------------------
        # Subcontractors (with encryption)
        # ------------------------------------------------------------------
        for sub in SEED_SUBCONTRACTORS:
            row = {
                "id": sub["id"],
                "company_name": sub["company_name"],
                "contact_first_name": sub["contact_first_name"],
                "contact_last_name": sub["contact_last_name"],
                "email": sub["email"],
                "phone": sub["phone"],
                "address_line1": sub["address_line1"],
                "address_line2": sub.get("address_line2"),
                "city": sub["city"],
                "state": sub["state"],
                "zip_code": sub["zip_code"],
                "country": sub["country"],
                "ein": sub["ein"],
                "license_number": sub["license_number"],
                "license_state": sub["license_state"],
                "license_expiration": sub["license_expiration"],
                "status": sub["status"],
            }
            # encrypted columns
            row["encrypted_ein"] = _encrypt(sub["ein"], fernet)
            row["encrypted_contact_first_name"] = _encrypt(sub["contact_first_name"], fernet)
            row["encrypted_contact_last_name"] = _encrypt(sub["contact_last_name"], fernet)
            row["encrypted_email"] = _encrypt(sub["email"], fernet)
            row["encrypted_phone"] = _encrypt(sub["phone"], fernet)
            row["encrypted_address_line1"] = _encrypt(sub["address_line1"], fernet)
            row["encrypted_address_line2"] = _encrypt(sub.get("address_line2"), fernet)
            row["encrypted_city"] = _encrypt(sub["city"], fernet)
            row["encrypted_state"] = _encrypt(sub["state"], fernet)
            row["encrypted_zip_code"] = _encrypt(sub["zip_code"], fernet)

            session.execute(
                text(
                    """INSERT INTO subcontractors
                    (id, company_name, contact_first_name, contact_last_name, email, phone,
                     address_line1, address_line2, city, state, zip_code, country, ein,
                     encrypted_ein, encrypted_contact_first_name, encrypted_contact_last_name,
                     encrypted_email, encrypted_phone, encrypted_address_line1, encrypted_address_line2,
                     encrypted_city, encrypted_state, encrypted_zip_code,
                     license_number, license_state, license_expiration, status)
                    VALUES
                    (:id, :company_name, :contact_first_name, :contact_last_name, :email, :phone,
                     :address_line1, :address_line2, :city, :state, :zip_code, :country, :ein,
                     :encrypted_ein, :encrypted_contact_first_name, :encrypted_contact_last_name,
                     :encrypted_email, :encrypted_phone, :encrypted_address_line1, :encrypted_address_line2,
                     :encrypted_city, :encrypted_state, :encrypted_zip_code,
                     :license_number, :license_state, :license_expiration, :status)
                    ON CONFLICT (email) DO NOTHING"""
                ),
                row,
            )
        summary["tables"].append("subcontractors")
        summary["counts"]["subcontractors"] = len(SEED_SUBCONTRACTORS)
        logger.info("Seeded %d subcontractors (with encrypted columns).", len(SEED_SUBCONTRACTORS))

        # ------------------------------------------------------------------
        # Projects (with encryption)
        # ------------------------------------------------------------------
        for proj in SEED_PROJECTS:
            row = {
                **proj,
                "encrypted_client_name": _encrypt(proj["client_name"], fernet),
                "encrypted_client_contact": _encrypt(proj["client_contact"], fernet),
            }
            session.execute(
                text(
                    """INSERT INTO projects
                    (id, project_name, project_number, description, client_name, client_contact,
                     encrypted_client_name, encrypted_client_contact,
                     start_date, estimated_end_date, status, org_id)
                    VALUES
                    (:id, :project_name, :project_number, :description, :client_name, :client_contact,
                     :encrypted_client_name, :encrypted_client_contact,
                     :start_date, :estimated_end_date, :status, :org_id)
                    ON CONFLICT (project_number) DO NOTHING"""
                ),
                row,
            )
        summary["tables"].append("projects")
        summary["counts"]["projects"] = len(SEED_PROJECTS)
        logger.info("Seeded %d projects (with encrypted client columns).", len(SEED_PROJECTS))

        # ------------------------------------------------------------------
        # Certifications
        # ------------------------------------------------------------------
        for cert in SEED_CERTIFICATIONS:
            session.execute(
                text(
                    """INSERT INTO certifications
                    (id, subcontractor_id, certification_type, certification_number,
                     issuing_authority, issue_date, expiration_date, status,
                     verification_status, notes)
                    VALUES
                    (:id, :subcontractor_id, :certification_type, :certification_number,
                     :issuing_authority, :issue_date, :expiration_date, :status,
                     :verification_status, :notes)
                    ON CONFLICT DO NOTHING"""
                ),
                cert,
            )
        summary["tables"].append("certifications")
        summary["counts"]["certifications"] = len(SEED_CERTIFICATIONS)
        logger.info("Seeded %d certifications.", len(SEED_CERTIFICATIONS))

        # ------------------------------------------------------------------
        # Violations
        # ------------------------------------------------------------------
        for viol in SEED_VIOLATIONS:
            session.execute(
                text(
                    """INSERT INTO violations
                    (id, subcontractor_id, violation_type, violation_code, description,
                     issued_by, issued_date, status, penalty_amount, is_osha_violation,
                     osha_violation_id, inspection_number, standard_cited, initial_penalty,
                     final_penalty, gravity_score, probability_score, risk_category,
                     site_city, site_state, naics_code)
                    VALUES
                    (:id, :subcontractor_id, :violation_type, :violation_code, :description,
                     :issued_by, :issued_date, :status, :penalty_amount, :is_osha_violation,
                     :osha_violation_id, :inspection_number, :standard_cited, :initial_penalty,
                     :final_penalty, :gravity_score, :probability_score, :risk_category,
                     :site_city, :site_state, :naics_code)
                    ON CONFLICT DO NOTHING"""
                ),
                viol,
            )
        summary["tables"].append("violations")
        summary["counts"]["violations"] = len(SEED_VIOLATIONS)
        logger.info("Seeded %d violations.", len(SEED_VIOLATIONS))

        # ------------------------------------------------------------------
        # Project-Subcontractor assignments
        # ------------------------------------------------------------------
        for mapping in SEED_PROJECT_SUBCONTRACTORS:
            session.execute(
                text(
                    """INSERT INTO project_subcontractors
                    (project_id, subcontractor_id, role, start_date, status)
                    VALUES
                    (:project_id, :subcontractor_id, :role, :start_date, :status)
                    ON CONFLICT DO NOTHING"""
                ),
                mapping,
            )
        summary["tables"].append("project_subcontractors")
        summary["counts"]["project_subcontractors"] = len(SEED_PROJECT_SUBCONTRACTORS)
        logger.info("Seeded %d project/subcontractor assignments.", len(SEED_PROJECT_SUBCONTRACTORS))

        # ------------------------------------------------------------------
        # Email templates
        # ------------------------------------------------------------------
        for tmpl in SEED_EMAIL_TEMPLATES:
            session.execute(
                text(
                    """INSERT INTO email_templates
                    (id, name, description, template_type, alert_type,
                     subject_template, html_body_template, text_body_template,
                     template_variables, language, is_active, is_default)
                    VALUES
                    (:id, :name, :description, :template_type, :alert_type,
                     :subject_template, :html_body_template, :text_body_template,
                     :template_variables, :language, :is_active, :is_default)
                    ON CONFLICT (name) DO NOTHING"""
                ),
                tmpl,
            )
        summary["tables"].append("email_templates")
        summary["counts"]["email_templates"] = len(SEED_EMAIL_TEMPLATES)
        logger.info("Seeded %d email templates.", len(SEED_EMAIL_TEMPLATES))

        # ------------------------------------------------------------------
        # State compliance sources
        # ------------------------------------------------------------------
        for src in SEED_STATE_COMPLIANCE_SOURCES:
            session.execute(
                text(
                    """INSERT INTO state_compliance_sources
                    (state_code, state_name, api_url, api_key_env_var,
                     is_active, priority, source_type)
                    VALUES
                    (:state_code, :state_name, :api_url, :api_key_env_var,
                     :is_active, :priority, :source_type)
                    ON CONFLICT (state_code) DO NOTHING"""
                ),
                src,
            )
        summary["tables"].append("state_compliance_sources")
        summary["counts"]["state_compliance_sources"] = len(SEED_STATE_COMPLIANCE_SOURCES)
        logger.info("Seeded %d state compliance sources.", len(SEED_STATE_COMPLIANCE_SOURCES))

        # ------------------------------------------------------------------
        # Data quality checks
        # ------------------------------------------------------------------
        for check in SEED_DATA_QUALITY_CHECKS:
            session.execute(
                text(
                    """INSERT INTO data_quality_checks
                    (check_name, table_name, column_name, check_type, check_query,
                     expected_threshold, severity, is_active, description)
                    VALUES
                    (:check_name, :table_name, :column_name, :check_type, :check_query,
                     :expected_threshold, :severity, :is_active, :description)
                    ON CONFLICT (check_name) DO NOTHING"""
                ),
                check,
            )
        summary["tables"].append("data_quality_checks")
        summary["counts"]["data_quality_checks"] = len(SEED_DATA_QUALITY_CHECKS)
        logger.info("Seeded %d data quality checks.", len(SEED_DATA_QUALITY_CHECKS))

        # ------------------------------------------------------------------
        # Subscriptions
        # ------------------------------------------------------------------
        for sub in SEED_SUBSCRIPTIONS:
            session.execute(
                text(
                    """INSERT INTO subscriptions
                    (id, org_id, plan, status)
                    VALUES (:id, :org_id, :plan, :status)
                    ON CONFLICT DO NOTHING"""
                ),
                sub,
            )
        summary["tables"].append("subscriptions")
        summary["counts"]["subscriptions"] = len(SEED_SUBSCRIPTIONS)
        logger.info("Seeded %d subscriptions.", len(SEED_SUBSCRIPTIONS))

        session.commit()
        logger.info("Production baseline seed committed successfully.")

    except Exception:
        session.rollback()
        logger.exception("Production baseline seed failed")
        raise
    finally:
        session.close()

    return summary


if __name__ == "__main__":
    result = seed_database()
    print("Production Baseline Seed Summary")
    for tbl in result["tables"]:
        print(f"  {tbl}: {result['counts'][tbl]} records")
