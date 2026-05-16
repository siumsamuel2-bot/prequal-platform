"""pytest fixtures for the Prequal alerting test suite.

Provides async database session and test client fixtures.
"""

import os

# Use a file-based SQLite so that multiple AsyncSession connections share
# the same database. In-memory SQLite creates a fresh DB per connection.
_test_db_path = os.path.join(os.path.dirname(__file__), "..", "test_prequal.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"

import pytest_asyncio  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from api.main import app as fastapi_app  # noqa: E402
from app.database import AsyncSessionLocal, Base, engine  # noqa: E402

# Import models so Base.metadata includes all tables
import app.models.compliance  # noqa: F401,E402


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create an async engine and initialize all tables."""
    # Clean up any stale test DB from a previous run
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a fresh async session for each test."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture
async def async_client(db_engine):
    """Async HTTP test client for FastAPI."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client