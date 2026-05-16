"""
Seed script for Prequal Compliance Platform.

Populates initial reference data for new deployments.
Run after Alembic migrations have been applied.
"""

from __future__ import annotations

import os
import logging
from datetime import date, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prequal_compliance",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_SUBCONTRACTORS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_name": "Midland Contracting LLC",
        "email": "info@midlandcontracting.com",
        "phone": "555-0101",
        "address_line1": "1200 Industrial Parkway",
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
        "email": "bids@summitelec.com",
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
        "email": "service@metrohvac.com",
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
        "email": "estimating@pinnacleconcrete.com",
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
]

SEED_PROJECTS = [
    {
        "id": "99999999-9999-9999-9999-999999999999",
        "project_name": "Riverside Office Complex",
        "project_number": "PRJ-2026-001",
        "description": "5-story commercial office building",
        "client_name": "Riverside Development Group",
        "start_date": date(2026, 3, 1),
        "estimated_end_date": date(2026, 12, 15),
        "status": "active",
    },
    {
        "id": "88888888-8888-8888-8888-888888888888",
        "project_name": "Parkside Residential Tower",
        "project_number": "PRJ-2026-002",
        "description": "24-story mixed-use residential",
        "client_name": "Parkside Living LLC",
        "start_date": date(2026, 1, 15),
        "estimated_end_date": date(2027, 6, 30),
        "status": "active",
    },
]

SEED_CERTIFICATIONS = [
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
        "notes": "Renewal requested",
    },
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
]


def _mk_engine():
    url = DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")
    return create_engine(url, echo=False)


def seed_database(engine=None):
    summary = {"tables": [], "counts": {}}
    if engine is None:
        engine = _mk_engine()

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existing = session.execute(text("SELECT COUNT(*) FROM subcontractors")).scalar()
        if existing and existing > 0:
            logger.warning("Database already contains data. Skipping seed.")
            return summary

        for employer in SEED_SUBCONTRACTORS:
            session.execute(
                text(
                    """INSERT INTO subcontractors
                    (id, company_name, email, phone, address_line1, city, state, zip_code, country,
                     ein, license_number, license_state, license_expiration, status)
                    VALUES
                    (:id, :company_name, :email, :phone, :address_line1, :city, :state, :zip_code, :country,
                     :ein, :license_number, :license_state, :license_expiration, :status)
                    """
                ),
                employer,
            )
        summary["tables"].append("subcontractors")
        summary["counts"]["subcontractors"] = len(SEED_SUBCONTRACTORS)
        logger.info("Seeded %d subcontractors.", len(SEED_SUBCONTRACTORS))

        for project in SEED_PROJECTS:
            session.execute(
                text(
                    """INSERT INTO projects
                    (id, project_name, project_number, description, client_name,
                     start_date, estimated_end_date, status)
                    VALUES
                    (:id, :project_name, :project_number, :description, :client_name,
                     :start_date, :estimated_end_date, :status)
                    """
                ),
                project,
            )
        summary["tables"].append("projects")
        summary["counts"]["projects"] = len(SEED_PROJECTS)
        logger.info("Seeded %d projects.", len(SEED_PROJECTS))

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
                    """
                ),
                cert,
            )
        summary["tables"].append("certifications")
        summary["counts"]["certifications"] = len(SEED_CERTIFICATIONS)
        logger.info("Seeded %d certifications.", len(SEED_CERTIFICATIONS))

        for violation in SEED_VIOLATIONS:
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
                    """
                ),
                violation,
            )
        summary["tables"].append("violations")
        summary["counts"]["violations"] = len(SEED_VIOLATIONS)
        logger.info("Seeded %d violations.", len(SEED_VIOLATIONS))

        for mapping in SEED_PROJECT_SUBCONTRACTORS:
            session.execute(
                text(
                    """INSERT INTO project_subcontractors
                    (project_id, subcontractor_id, role, start_date, status)
                    VALUES
                    (:project_id, :subcontractor_id, :role, :start_date, :status)
                    """
                ),
                mapping,
            )
        summary["tables"].append("project_subcontractors")
        summary["counts"]["project_subcontractors"] = len(SEED_PROJECT_SUBCONTRACTORS)
        logger.info("Seeded %d project/subcontractor assignments.", len(SEED_PROJECT_SUBCONTRACTORS))

        session.commit()
        logger.info("Seed data committed successfully.")

    except Exception:
        session.rollback()
        logger.exception("Seed failed")
        raise
    finally:
        session.close()

    return summary


if __name__ == "__main__":
    result = seed_database()
    print("Seed Summary")
    for tbl in result["tables"]:
        print(f"  {tbl}: {result['counts'][tbl]} records")
