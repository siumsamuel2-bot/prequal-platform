# Running the Backend Test Suite Against PostgreSQL (MID-628)

Closes the SQLite-shim parity gap from the architecture review
([MID-576](/MID/issues/MID-576), Phase 5).

By default, `tests/conftest.py` uses file-based SQLite with hand-written
shims for PostgreSQL-only features (materialized views, Alembic-only
tables). Setting `TEST_DATABASE_URL` switches the whole suite into
**PostgreSQL parity mode**: the real Alembic migrations run and no SQLite
shims are used, so PG-specific behavior (upserts, concurrency,
`REFRESH MATERIALIZED VIEW CONCURRENTLY`) is exercised exactly as in
production.

## CI

The `test-postgres` job in `.github/workflows/ci-cd.yml` runs on every
push/PR:

- Spins up a `postgres:15` service container.
- Sets `TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_db`.
- Runs the full backend suite and uploads `pg-test-results.xml` as an artifact.

The job is **advisory** (`continue-on-error: true`) until the suite is green
against PostgreSQL; failures are visible in the job and artifact summary and
are routed to the Backend Engineer. Once green, remove `continue-on-error`
from the job so PG regressions block builds.

SQLite stays the default for fast local runs — no environment variables
needed.

## Local run

1. Start a disposable PostgreSQL instance:

```bash
docker run -d --name prequal-test-pg \
  -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test_db \
  -p 5432:5432 postgres:15
```

2. Run the suite in parity mode:

```bash
cd prequal-platform
export TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_db
pytest tests/ -v --cov=app --cov=api --junitxml=pg-test-results.xml
```

3. Clean up:

```bash
docker rm -f prequal-test-pg
```

## How parity mode works

- `conftest.py` reads `TEST_DATABASE_URL` before importing `app.database`;
  when it starts with `postgresql`, the app engine connects to PostgreSQL
  instead of SQLite.
- The session fixture applies real migrations via Alembic
  (`alembic upgrade head`, sync psycopg2 driver from `requirements.txt`),
  which creates the analytics materialized views (migration 010), data
  quality tables (migrations 014/027), and all other schema as in
  production.
- Teardown runs `alembic downgrade base` (best-effort) against the
  disposable test database.
