"""MID-690: security headers present on every response.

The CTO finding noted CSP / X-Content-Type-Options / X-Frame-Options were
already present; Strict-Transport-Security and Referrer-Policy were missing.
"""

from httpx import AsyncClient

import pytest


@pytest.mark.asyncio
async def test_security_headers_on_health(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_existing_security_headers_retained(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-xss-protection"] == "1; mode=block"
    assert resp.headers["content-security-policy"] == "default-src 'self'"
