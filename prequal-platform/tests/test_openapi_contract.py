"""OpenAPI contract tests (MID-622).

Validates the FastAPI application against its own OpenAPI specification
using schemathesis v4. Schemathesis generates requests conforming to the
schema and asserts that responses never fail with 5xx server errors.

Schemathesis v4 API notes (differs from v3):
- v3 ``schemathesis.from_pytest_fixture`` / ``schemathesis.from_asgi`` are
  replaced by the explicit loaders under ``schemathesis.openapi.*``
  (``from_dict``, ``from_path``, ``from_url``, ``from_asgi``).
- Cases are executed with ``case.call_and_validate()``; when the schema is
  loaded via ``from_asgi`` the transport is bound to the app directly and no
  base_url is required.

Run standalone with real data shapes against a SQLite test database:

    pytest tests/test_openapi_contract.py -v
"""

import os
import uuid

# Test database: unique file path per session (mirrors tests/conftest.py).
_test_db_path = os.path.join(
    os.path.dirname(__file__), "..", f"test_contract_{uuid.uuid4().hex}.db"
)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_test_db_path}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long-here")

import pytest_asyncio  # noqa: E402
import schemathesis  # noqa: E402
from hypothesis import HealthCheck, Phase, settings  # noqa: E402
import schemathesis.checks  # noqa: E402
from schemathesis.checks import not_a_server_error  # noqa: E402

import app.models.compliance  # noqa: F401,E402  ensure all models registered first
from app.database import Base, engine  # noqa: E402
from api.main import app  # noqa: E402  imported AFTER app.models so `app` is the FastAPI instance

# schemathesis v4: load the schema straight from the running ASGI app.
# Exclusions:
# - /metrics is Prometheus (text/plain, intentionally undocumented).
# - POST /api/compliance/states/sync/{state_code} invokes the external
#   compliance ETL pipeline, which uses PostgreSQL-only SQL (interval
#   literals) and cannot run in the SQLite test harness; it is covered in
#   PostgreSQL-parity mode (TEST_DATABASE_URL, MID-628).
schema = (
    schemathesis.openapi.from_asgi("/openapi.json", app=app)
    .exclude(path_regex=r"^/metrics$")
    .exclude(method="POST", path_regex=r"^/api/compliance/states/sync/")
)


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _init_db():
    """Create all tables so generated requests hit a real database.

    MID-634: teardown must NOT drop tables. ``tests/conftest.py`` already sets
    DATABASE_URL before this module is imported, so the ``setdefault`` above is
    a no-op and the shared session database is in use here. ``drop_all`` in the
    old teardown therefore wiped every table for all test modules that run
    after this one ("no such table" failures). Final cleanup is owned by the
    conftest session teardown, and cross-module row leakage is handled by the
    ``reset_shared_tables`` autouse fixture.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@schema.parametrize()
@settings(
    # Keep the suite fast: a handful of examples per operation.
    max_examples=3,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
    ],
    phases=[Phase.explicit, Phase.generate],
)
def test_openapi_contract(case):
    """Every documented operation must not fail with a server error.

    Auth-protected endpoints are expected to return 401/403 without
    credentials, so the suite validates the core contract guarantee:
    no operation fails with a 5xx server error.
    """
    case.call_and_validate(checks=(not_a_server_error,))
