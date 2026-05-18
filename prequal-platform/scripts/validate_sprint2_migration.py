"""
Sprint 2 Schema Validation Script
Validates that new models can be imported and migration is syntactically correct.
Usage: cd prequal-platform && python scripts/validate_sprint2_migration.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_model_imports():
    try:
        from app.models.auth import Organization, OrganizationMembership, User
        print("[PASS] auth models imported: Organization, OrganizationMembership, User")
    except Exception as e:
        print(f"[FAIL] auth model import failed: {e}")
        return False

    try:
        from app.models.compliance import Subcontractor, Project, Certification
        print("[PASS] compliance models imported: Subcontractor, Project, Certification")
    except Exception as e:
        print(f"[FAIL] compliance model import failed: {e}")
        return False

    try:
        from app.models.alerts import AlertConfig, AlertLog
        print("[PASS] alerts models imported: AlertConfig, AlertLog")
    except Exception as e:
        print(f"[FAIL] alerts model import failed: {e}")
        return False

    try:
        from app.models import Organization, OrganizationMembership, AlertConfig, AlertLog
        print("[PASS] __init__.py re-exports correct")
    except Exception as e:
        print(f"[FAIL] __init__.py re-export failed: {e}")
        return False

    return True


def test_migration_syntax():
    migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "alembic", "versions", "008_sprint2_auth_alerts_subcontractors.py")
    try:
        with open(migration_path, "r") as f:
            code = f.read()
        compile(code, migration_path, "exec")
        print("[PASS] Migration file compiles successfully")
        return True
    except SyntaxError as e:
        print(f"[FAIL] Migration syntax error at line {e.lineno}: {e.msg}")
        return False
    except FileNotFoundError:
        print(f"[FAIL] Migration file not found: {migration_path}")
        return False


def test_column_definitions():
    failures = []
    from app.models.auth import Organization, User, OrganizationMembership
    from app.models.compliance import Subcontractor, Project
    from app.models.alerts import AlertConfig, AlertLog

    if hasattr(Organization, "slug") and hasattr(Organization, "name"):
        print("[PASS] Organization has required columns")
    else:
        failures.append("Organization missing required columns")

    if hasattr(User, "org_id"):
        print("[PASS] User has org_id column")
    else:
        failures.append("User missing org_id")

    if hasattr(Project, "org_id"):
        print("[PASS] Project has org_id column")
    else:
        failures.append("Project missing org_id")

    if hasattr(Subcontractor, "org_id"):
        print("[PASS] Subcontractor has org_id column")
    else:
        failures.append("Subcontractor missing org_id")

    if hasattr(OrganizationMembership, "user_id") and hasattr(OrganizationMembership, "org_id"):
        print("[PASS] OrganizationMembership has required FK columns")
    else:
        failures.append("OrganizationMembership missing FK columns")

    if hasattr(AlertConfig, "email_enabled") and hasattr(AlertConfig, "lead_days"):
        print("[PASS] AlertConfig has required columns")
    else:
        failures.append("AlertConfig missing required columns")

    if hasattr(AlertLog, "channel") and hasattr(AlertLog, "status"):
        print("[PASS] AlertLog has required columns")
    else:
        failures.append("AlertLog missing required columns")

    if failures:
        for f in failures:
            print(f"[FAIL] {f}")
        return False
    return True


if __name__ == "__main__":
    all_ok = True
    print("=" * 60)
    print("Sprint 2 Schema Validation")
    print("=" * 60)

    print("\n[1/3] Model Imports")
    print("-" * 40)
    if not test_model_imports():
        all_ok = False

    print("\n[2/3] Migration Syntax")
    print("-" * 40)
    if not test_migration_syntax():
        all_ok = False

    print("\n[3/3] Column Definitions")
    print("-" * 40)
    if not test_column_definitions():
        all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL CHECKS PASSED")
    else:
        print("VALIDATION FAILED")
    print("=" * 60)
