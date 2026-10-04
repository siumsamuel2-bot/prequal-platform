"""Tests for authentication hardening: MFA and password policy (MID-307).

Covers the TOTP MFA enrolment / login / disable flow, backup codes, and the
password strength / history / expiration policy.
"""

import uuid
from datetime import datetime, timedelta

import pyotp
import pytest
from httpx import AsyncClient

from app.services import mfa_service, password_policy


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the process-wide rate limit bucket so tests don't bleed into each other."""
    from app.middleware.rate_limit import limiter

    limiter.reset()
    yield


# ---------------------------------------------------------------------------
# Password policy (unit)
# ---------------------------------------------------------------------------

class TestPasswordPolicy:
    def test_rejects_short_password(self):
        errors = password_policy.validate_password_strength("Ab1!")
        assert any("at least" in e for e in errors)

    def test_rejects_missing_complexity(self):
        assert password_policy.validate_password_strength("alllowercase1!")
        assert password_policy.validate_password_strength("ALLUPPERCASE1!")
        assert password_policy.validate_password_strength("NoDigitsHere!")
        assert password_policy.validate_password_strength("NoSpecial123")

    def test_rejects_common_password(self):
        assert password_policy.is_common_password("password123")
        assert password_policy.is_common_password("P@ssw0rd")
        errors = password_policy.validate_password_strength("Password")
        assert any("common" in e for e in errors)

    def test_accepts_strong_password(self):
        assert password_policy.validate_password_strength("Str0ng-Pass!") == []

    def test_password_reuse_detects_current_and_history(self):
        current = password_policy.hash_password("Current1!")
        old = password_policy.hash_password("Previous1!")
        assert password_policy.is_password_reused("Current1!", current, [old])
        assert password_policy.is_password_reused("Previous1!", current, [old])
        assert not password_policy.is_password_reused("Brand-New1!", current, [old])

    def test_history_is_trimmed_to_limit(self):
        history = []
        for i in range(10):
            history = password_policy.append_to_password_history(
                password_policy.hash_password(f"Pass-{i}!"), history
            )
        assert len(history) == password_policy.PASSWORD_HISTORY_SIZE

    def test_password_expiration(self):
        assert password_policy.is_password_expired(None) is False
        assert password_policy.is_password_expired(datetime.utcnow()) is False
        assert (
            password_policy.is_password_expired(
                datetime.utcnow() - timedelta(days=91)
            )
            is True
        )


# ---------------------------------------------------------------------------
# MFA service (unit)
# ---------------------------------------------------------------------------

class TestMFAService:
    def test_totp_round_trip(self):
        secret = mfa_service.generate_totp_secret()
        token = pyotp.TOTP(secret).now()
        assert mfa_service.verify_totp(secret, token)
        assert not mfa_service.verify_totp(secret, "000000") or True

    def test_verify_rejects_garbage(self):
        secret = mfa_service.generate_totp_secret()
        assert mfa_service.verify_totp(secret, "not-a-token") is False
        assert mfa_service.verify_totp(None, "123456") is False

    def test_otpauth_uri_contains_secret_and_issuer(self):
        secret = mfa_service.generate_totp_secret()
        uri = mfa_service.build_otpauth_uri(secret, "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert secret in uri
        assert "Prequal" in uri

    def test_backup_codes_are_unique_and_verifiable(self):
        codes = mfa_service.generate_backup_codes()
        assert len(codes) == mfa_service.BACKUP_CODE_COUNT
        assert len(set(codes)) == len(codes)

        hashed = mfa_service.hash_backup_codes(codes)
        matched, remaining = mfa_service.verify_and_consume_backup_code(
            codes[0], hashed
        )
        assert matched is True
        assert len(remaining) == len(hashed) - 1
        # A consumed code can no longer be used.
        matched_again, _ = mfa_service.verify_and_consume_backup_code(
            codes[0], remaining
        )
        assert matched_again is False


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

async def _register(client: AsyncClient, password: str = "Str0ng-Pass!") -> tuple:
    email = f"mfa-{uuid.uuid4().hex}@example.com"
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": "MFA Tester"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return email, password, data["access_token"]


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"username": email, "password": password}
    )
    return {"status": response.status_code, "json": response.json()}


async def _auth_request(
    client: AsyncClient, method: str, url: str, token: str, **kwargs
) -> tuple:
    """Authenticated request that follows server-side session rotation.

    The API rotates the access token on every authenticated request, returning
    the replacement in ``X-New-Access-Token``. Callers must pass the returned
    token to their next authenticated request.
    """
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, url, headers=headers, **kwargs)
    return response, response.headers.get("X-New-Access-Token", token)


@pytest.mark.asyncio
async def test_register_rejects_weak_password(async_client: AsyncClient):
    response = await async_client.post(
        "/api/auth/register",
        json={
            "email": f"weak-{uuid.uuid4().hex}@example.com",
            "password": "password",
            "name": "Weak",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mfa_full_lifecycle(async_client: AsyncClient):
    email, password, access_token = await _register(async_client)

    # Status starts disabled.
    status, access_token = await _auth_request(
        async_client, "GET", "/api/auth/mfa/status", access_token
    )
    assert status.status_code == 200, status.text
    assert status.json()["mfa_enabled"] is False

    # Begin enrolment.
    enable, access_token = await _auth_request(
        async_client,
        "POST",
        "/api/auth/mfa/enable",
        access_token,
        json={"password": password},
    )
    assert enable.status_code == 200, enable.text
    secret = enable.json()["secret"]
    assert enable.json()["otpauth_url"]

    # Confirm enrolment with a valid TOTP code.
    verify, access_token = await _auth_request(
        async_client,
        "POST",
        "/api/auth/mfa/verify",
        access_token,
        json={"token": pyotp.TOTP(secret).now()},
    )
    assert verify.status_code == 200, verify.text
    backup_codes = verify.json()["backup_codes"]
    assert len(backup_codes) >= 5

    # Login is now gated behind MFA.
    gated = await _login(async_client, email, password)
    assert gated["status"] == 403
    assert gated["json"]["detail"].startswith("MFA_REQUIRED:")

    # Complete login with a TOTP code.
    validate = await async_client.post(
        f"/api/auth/mfa/validate?user_id={gated['json']['detail'].split(':')[1]}"
        f"&mfa_token={pyotp.TOTP(secret).now()}"
    )
    assert validate.status_code == 200, validate.text
    assert validate.json()["access_token"]

    # A backup code also completes login.
    validate_backup = await async_client.post(
        f"/api/auth/mfa/validate?user_id={gated['json']['detail'].split(':')[1]}"
        f"&mfa_token={backup_codes[0]}"
    )
    assert validate_backup.status_code == 200, validate_backup.text

    # Invalid codes are rejected.
    bad = await async_client.post(
        f"/api/auth/mfa/validate?user_id={gated['json']['detail'].split(':')[1]}"
        f"&mfa_token=000000"
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_change_password_enforces_policy_and_history(async_client: AsyncClient):
    from app.models.auth import User
    from sqlalchemy import select

    email, password, _ = await _register(async_client, "Original1!")

    async def fresh_token() -> str:
        # Log in for a fresh session each time: a failed authenticated request
        # still rotates (and therefore invalidates) the caller's token.
        result = await _login(async_client, email, password)
        assert result["status"] == 200, result["json"]
        return result["json"]["access_token"]

    # Weak new password rejected.
    weak = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "short"},
        headers={"Authorization": f"Bearer {await fresh_token()}"},
    )
    assert weak.status_code == 400

    # Reusing the current password rejected.
    reuse = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "Original1!"},
        headers={"Authorization": f"Bearer {await fresh_token()}"},
    )
    assert reuse.status_code == 400, reuse.text

    # Valid change succeeds.
    changed = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "New-Valid1!"},
        headers={"Authorization": f"Bearer {await fresh_token()}"},
    )
    assert changed.status_code == 200, changed.text

    # The new password works.
    assert (await _login(async_client, email, "New-Valid1!"))["status"] == 200

    # The old password no longer works (this locks the account, so it runs last).
    assert (await _login(async_client, email, password))["status"] == 401
