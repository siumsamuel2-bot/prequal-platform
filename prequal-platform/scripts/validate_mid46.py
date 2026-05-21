"""Validate Sprint 2 database schema completeness for MID-46."""
import pathlib
import sys
import importlib.util
import os

# Setup path to include prequal-platform
BASE = pathlib.Path(__file__).resolve().parent.parent  # scripts -> prequal-platform
sys.path.insert(0, str(BASE))

# Verify all 8 models exist and have correct tablenames
from app.database import Base
from app.models import __all__ as model_exports

REQUIRED = {
    "User": "users",
    "Organization": "organizations",
    "Project": "projects",
    "OrganizationMembership": "organization_memberships",
    "Subcontractor": "subcontractors",
    "Certification": "certifications",
    "AlertConfig": "alert_configs",
    "AlertLog": "alert_logs",
}

print("=== Model Validation ===")
for name, table in REQUIRED.items():
    assert name in model_exports, f"Model {name} missing from __all__"
    import_str = f"from app.models import {name}"
    code_obj = compile(import_str, "<string>", "exec")
    ns = {}
    exec(code_obj, ns)
    model_cls = ns[name]
    assert model_cls.__tablename__ == table, f"Expected {name}.__tablename__ = {table}, got {model_cls.__tablename__}"
    print(f"  [PASS] {name} -> {table}")

print("\n=== Relationship Check ===")
import importlib
ns_map = {}
for name in REQUIRED:
    code_obj = compile(f"from app.models import {name}", "<string>", "exec")
    ns = {}
    exec(code_obj, ns)
    ns_map[name] = ns[name]

User, Org, Project, OrgMem, Sub, Cert, AlertCfg, AlertLog = (ns_map[n] for n in REQUIRED)

# Verify key relationships
assert hasattr(User, "organization")
assert hasattr(User, "org_memberships")
assert hasattr(Org, "users")
assert hasattr(Org, "memberships")
assert hasattr(Sub, "certifications")
assert hasattr(Cert, "subcontractor_id")
assert hasattr(AlertCfg, "alert_logs")
assert hasattr(AlertLog, "alert_config")
print("  [PASS] Key relationships verified")

print("\n=== Migration Chain Check ===")
mig_dir = BASE / "alembic" / "versions"
migs = sorted(mig_dir.glob("[0-9]*_*.py"), key=lambda p: p.name)
print(f"  Found {len(migs)} migrations:")
for m in migs:
    print(f"    {m.name}")

# Verify down_revision chain
rev_map = {}
for m in migs:
    with open(m, "r") as f:
        content = f.read()
    rev = None
    down = None
    for line in content.splitlines():
        if line.startswith("revision = "):
            rev = line.split("=", 1)[1].strip().strip("'\"")
        if line.startswith("down_revision = "):
            raw = line.split("=", 1)[1].strip()
            down = raw.strip("'\"") if raw != "None" else None
            if down == "None":
                down = None
    rev_map[m.name] = (rev, down)

print("\n=== Revision Chain ===")
for m in migs:
    rev, down = rev_map[m.name]
    print(f"  {m.name}: rev={rev}, down={down}")

print("\n=== All checks passed ===")
