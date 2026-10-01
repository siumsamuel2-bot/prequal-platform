"""
Validate data integrity and referential constraints after seed/migration.

Usage:
    pytest tests/validate_production_schema.py -v

Checks:
- All required tables exist
- Foreign key constraints are valid
- Encrypted columns have corresponding plaintext values
- Seed data loaded correctly
- Indexes created successfully
- No orphaned records
"""

import pytest
from sqlalchemy import text

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


async def test_all_required_tables_exist(db_session):
    """Verify all production tables are present."""
    required = [
        "organizations", "users", "teams", "team_members", "organization_memberships",
        "subcontractors", "projects", "certifications", "project_subcontractors",
        "violations", "alert_preferences", "alert_notifications",
        "certification_renewals", "osha_inspections", "osha_api_logs",
        "sync_run_logs", "data_quality_checks", "data_quality_results",
        "state_credential_records", "uploaded_credentials",
        "email_templates", "notification_preferences", "notification_delivery_logs",
        "audit_logs", "failed_login_attempts", "account_lockouts",
        "state_compliance_sources", "subscriptions",
    ]
    for table in required:
        result = await db_session.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        )
        assert result.scalar() is not None, f"Missing table: {table}"


async def test_foreign_keys_valid_subcontractor_project(db_session):
    """No certifications reference non-existent subcontractors."""
    result = await db_session.execute(
        text("""
            SELECT COUNT(*) FROM certifications c
            LEFT JOIN subcontractors s ON s.id = c.subcontractor_id
            WHERE s.id IS NULL
        """)
    )
    assert result.scalar() == 0


async def test_foreign_keys_valid_violations(db_session):
    """No violations reference non-existent subcontractors."""
    result = await db_session.execute(
        text("""
            SELECT COUNT(*) FROM violations v
            LEFT JOIN subcontractors s ON s.id = v.subcontractor_id
            WHERE s.id IS NULL
        """)
    )
    assert result.scalar() == 0


async def test_foreign_keys_valid_project_assignments(db_session):
    """No project_subcontractors reference missing projects or subcontractors."""
    result = await db_session.execute(
        text("""
            SELECT COUNT(*) FROM project_subcontractors ps
            LEFT JOIN projects p ON p.id = ps.project_id
            LEFT JOIN subcontractors s ON s.id = ps.subcontractor_id
            WHERE p.id IS NULL OR s.id IS NULL
        """)
    )
    assert result.scalar() == 0


async def test_encrypted_columns_have_data(db_session):
    """Encrypted PII columns should not all be NULL when plaintext exists."""
    result = await db_session.execute(
        text("""
            SELECT COUNT(*) FROM subcontractors
            WHERE ein IS NOT NULL AND encrypted_ein IS NULL
        """)
    )
    assert result.scalar() == 0, "Plaintext EIN exists without encrypted_ein"


async def test_seed_data_loaded(db_session):
    """Seed data present in key tables."""
    subs = await db_session.execute(text("SELECT COUNT(*) FROM subcontractors"))
    assert subs.scalar() > 0, "No subcontractors seeded"

    projects = await db_session.execute(text("SELECT COUNT(*) FROM projects"))
    assert projects.scalar() > 0, "No projects seeded"

    certs = await db_session.execute(text("SELECT COUNT(*) FROM certifications"))
    assert certs.scalar() > 0, "No certifications seeded"


async def test_unique_constraints(db_session):
    """Unique constraints hold."""
    # Email uniqueness on users
    result = await db_session.execute(
        text("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1")
    )
    assert result.fetchall() == []

    # Email uniqueness on subcontractors
    result = await db_session.execute(
        text("SELECT email, COUNT(*) FROM subcontractors GROUP BY email HAVING COUNT(*) > 1")
    )
    assert result.fetchall() == []

    # Project number uniqueness
    result = await db_session.execute(
        text("SELECT project_number, COUNT(*) FROM projects GROUP BY project_number HAVING COUNT(*) > 1")
    )
    assert result.fetchall() == []


async def test_subscriptions_table_exists(db_session):
    """subscriptions table created by migration 019."""
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
    )
    assert result.scalar() is not None
