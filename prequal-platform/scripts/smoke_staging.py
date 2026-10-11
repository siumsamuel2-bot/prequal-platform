"""Staging acceptance smoke test (MID-644) - post-deploy end-to-end check.

Zero-dependency acceptance check for the free-tier staging deployment:
httpx + pytest only, no Docker/AWS/k6 (neither is installed in agent
runtimes). Reads ``BASE_URL`` from the environment; if unset the whole
module skips with a clear message so CI stays green.

Run:

    cd prequal-platform
    BASE_URL="https://prequal-staging-api.onrender.com" python -m pytest scripts/smoke_staging.py -v

Optional env:

    SMOKE_NON_ADMIN_EMAIL / SMOKE_NON_ADMIN_PASSWORD
        A pre-seeded *non-admin* staging account used for the fail-closed
        tenant-isolation check. Self-registered users are platform admins
        (the register endpoint creates ``role="admin"``, unscoped), so
        cross-tenant isolation cannot be exercised with them - this check
        needs the seeded account. Cross-tenant data separation itself is
        covered by the integration suite (tests/test_analytics_tenant_isolation.py).

Notes:
- Render free-tier cold starts take ~30-60 s; the health check retries
  within a 90 s window before failing.
- Login is rate-limited (10 attempts / 60 s per account) and failed
  attempts create lockouts - this suite never sends bad credentials.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

BASE_URL = (os.getenv("BASE_URL") or "").rstrip("/")
NON_ADMIN_EMAIL = os.getenv("SMOKE_NON_ADMIN_EMAIL") or ""
NON_ADMIN_PASSWORD = os.getenv("SMOKE_NON_ADMIN_PASSWORD") or ""

SUMMARY_PATH = "/api/analytics/summary"
HEALTH_TIMEOUT_S = 90.0  # covers one Render free-tier cold start
SUMMARY_KEYS = {
    "total_events",
    "unique_users",
    "total_feedback",
    "events_by_type",
    "recent_events",
    "events_today",
    "events_this_week",
}

pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="BASE_URL not set - staging smoke test skipped (set BASE_URL to run)"
)


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=False)


def test_health_200():
    """GET /health -> 200 (retrying across one cold-start window)."""
    with _client() as client:
        import time

        deadline = time.monotonic() + HEALTH_TIMEOUT_S
        last = None
        while True:
            last = client.get("/health")
            if last.status_code == 200:
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(5)
        assert last.status_code == 200, (
            f"/health did not return 200 within {HEALTH_TIMEOUT_S:.0f}s "
            f"(last: {last.status_code}) - service not deployed or still cold-starting"
        )


def test_protected_endpoint_401_without_token():
    """GET /api/analytics/summary without a token -> 401."""
    with _client() as client:
        r = client.get(SUMMARY_PATH)
        assert r.status_code == 401, (
            f"unauthenticated {SUMMARY_PATH} returned {r.status_code}, expected 401"
        )


def test_register_login_and_analytics_summary():
    """Self-registered user can log in and read the analytics summary."""
    with _client() as client:
        email = f"smoke-{uuid.uuid4().hex[:10]}@staging.example.com"
        password = f"Smoke!{uuid.uuid4().hex[:8]}aA1"
        r = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "name": "Staging Smoke"},
        )
        assert r.status_code == 200, f"register failed ({r.status_code}): {r.text[:200]}"
        assert r.json().get("access_token"), "register response missing access_token"

        r = client.post("/api/auth/login", json={"username": email, "password": password})
        assert r.status_code == 200, f"login failed ({r.status_code}): {r.text[:200]}"
        login_token = r.json().get("access_token")
        assert login_token, "login response missing access_token"

        r = client.get(
            SUMMARY_PATH, headers={"Authorization": f"Bearer {login_token}"}
        )
        assert r.status_code == 200, (
            f"{SUMMARY_PATH} with token returned {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        missing = SUMMARY_KEYS - set(body)
        assert not missing, f"{SUMMARY_PATH} response missing keys: {sorted(missing)}"


def test_tenant_isolation_fail_closed():
    """A non-admin account with no resolvable team must NOT read team-scoped data.

    Requires a seeded non-admin staging account (SMOKE_NON_ADMIN_EMAIL /
    SMOKE_NON_ADMIN_PASSWORD). Self-registered users are platform admins
    (role="admin", unscoped) and cannot exercise this check.
    """
    if not NON_ADMIN_EMAIL or not NON_ADMIN_PASSWORD:
        pytest.skip(
            "SMOKE_NON_ADMIN_EMAIL/SMOKE_NON_ADMIN_PASSWORD not set - tenant-isolation "
            "check skipped. Note: self-registered users are platform admins "
            '(register creates role="admin"), so cross-tenant isolation needs a '
            "seeded non-admin account."
        )
    with _client() as client:
        r = client.post(
            "/api/auth/login", json={"username": NON_ADMIN_EMAIL, "password": NON_ADMIN_PASSWORD}
        )
        assert r.status_code == 200, (
            f"seeded non-admin login failed ({r.status_code}) - check the staging seed"
        )
        token = r.json().get("access_token")
        assert token, "non-admin login response missing access_token"

        r = client.get(SUMMARY_PATH, headers={"Authorization": f"Bearer {token}"})
        # Fail-closed expectation: a non-admin whose team cannot be resolved
        # must get 403, never unscoped data. A 200 means the account has a team
        # (scoped to it) - report which, it is not a failure by itself.
        if r.status_code == 200:
            pytest.fail(
                "non-admin account resolved a team and read team-scoped data (200) - "
                "verify the seeded account really has no team membership; if it has "
                "one, this is expected app behaviour and the fail-closed check needs "
                "a truly team-less account"
            )
        assert r.status_code == 403, (
            f"non-admin no-team {SUMMARY_PATH} returned {r.status_code}, expected 403 (fail closed)"
        )
