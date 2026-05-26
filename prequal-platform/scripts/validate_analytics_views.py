"""Validation script for analytics materialized views.

Run this after applying migration 010_analytics_materialized_views.py
to ensure all views are present, queryable, and return expected shapes.

Usage:
    python scripts/validate_analytics_views.py

Exit codes:
    0 — all validations passed
    1 — one or more validations failed

Owner: Data Engineer
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from sqlalchemy import text


EXPECTED_VIEWS = [
    "mv_compliance_summary",
    "mv_compliance_trends",
    "mv_certification_status",
    "mv_project_compliance",
    "mv_recent_alerts",
]


async def validate_view_exists(view_name: str, db) -> tuple[bool, str]:
    """Check that a materialized view exists in the database."""
    result = await db.execute(
        text(
            """
            SELECT matviewname FROM pg_matviews
            WHERE matviewname = :name
            """
        ),
        {"name": view_name},
    )
    if result.scalar() is None:
        return False, f"View {view_name} not found in pg_matviews"
    return True, f"View {view_name} exists"


async def validate_view_is_queryable(view_name: str, db) -> tuple[bool, str]:
    """Check that the view can be queried without error."""
    try:
        await db.execute(text(f"SELECT * FROM {view_name} LIMIT 1"))
        return True, f"View {view_name} is queryable"
    except Exception as exc:
        return False, f"View {view_name} query failed: {exc}"


async def validate_view_has_computed_at(view_name: str, db) -> tuple[bool, str]:
    """Check that the view has a computed_at column."""
    result = await db.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :name AND column_name = 'computed_at'
            """
        ),
        {"name": view_name},
    )
    if result.scalar() is None:
        return False, f"View {view_name} missing computed_at column"
    return True, f"View {view_name} has computed_at column"


async def main() -> int:
    print("=== Analytics Views Validation ===")
    print()

    db = AsyncSessionLocal()
    try:
        all_passed = True

        for view in EXPECTED_VIEWS:
            for fn_name, fn in (
                ("exists", validate_view_exists),
                ("queryable", validate_view_is_queryable),
                ("has_computed_at", validate_view_has_computed_at),
            ):
                passed, msg = await fn(view, db)
                status = "PASS" if passed else "FAIL"
                print(f"  [{status}] {view} — {fn_name}: {msg}")
                if not passed:
                    all_passed = False

        print()
        if all_passed:
            print("=== ALL VALIDATIONS PASSED ===")
            return 0
        else:
            print("=== SOME VALIDATIONS FAILED ===")
            return 1
    finally:
        await db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
