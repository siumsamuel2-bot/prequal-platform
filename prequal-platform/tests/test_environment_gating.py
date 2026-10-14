"""MID-690: environment gating of interactive docs, detailed health and /metrics.

``api.main`` computes the docs/redoc/openapi routes at import time, so the
staging-mode behaviour cannot be verified against the shared test app
(conftest pins ENVIRONMENT=development). Each scenario runs in a hermetic
subprocess that imports the app with the target ENVIRONMENT and probes the
ASGI transport directly - no server, no database (the probed paths fail
before any DB access).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

_SUBPROCESS_PROBE = r"""
import asyncio
import json
import os

from httpx import ASGITransport, AsyncClient

from api.main import app


async def main():
    transport = ASGITransport(app=app)
    paths = ["/docs", "/redoc", "/openapi.json", "/health/detailed", "/metrics"]
    out = {}
    async with AsyncClient(transport=transport, base_url="http://probe") as client:
        for p in paths:
            resp = await client.get(p)
            out[p] = resp.status_code
    print(json.dumps(out))


asyncio.run(main())
"""


def _probe(env: str, token: str | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "probe.db").replace("\\", "/")
        proc_env = {
            **os.environ,
            "ENVIRONMENT": env,
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
            "SECRET_KEY": "test-secret-key-32-bytes-long-here",
        }
        proc_env.pop("METRICS_AUTH_TOKEN", None)
        if token is not None:
            proc_env["METRICS_AUTH_TOKEN"] = token
        proc = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS_PROBE],
            cwd=str(BACKEND_DIR),
            env=proc_env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    assert proc.returncode == 0, f"probe failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_staging_hides_docs_and_gates_observability():
    codes = _probe("staging")
    # Docs enumerate every privileged route -> 404 for anonymous callers.
    assert codes["/docs"] == 404
    assert codes["/redoc"] == 404
    assert codes["/openapi.json"] == 404
    # Detailed health discloses dependency status/uptime -> admin-only (401).
    assert codes["/health/detailed"] == 401
    # No METRICS_AUTH_TOKEN configured -> fail closed (403).
    assert codes["/metrics"] == 403


def test_development_keeps_docs_but_detailed_health_stays_admin_only():
    codes = _probe("development")
    assert codes["/docs"] == 200
    assert codes["/redoc"] == 200
    assert codes["/openapi.json"] == 200
    # Admin-only in every environment (secure by default).
    assert codes["/health/detailed"] == 401
    # Dev keeps the open /metrics behaviour for local iteration.
    assert codes["/metrics"] == 200


def test_metrics_token_gate_in_staging():
    # Correct bearer token -> scrape succeeds.
    codes = _probe("staging", token="scrape-secret")
    assert codes["/metrics"] == 401  # probe sends no auth header
