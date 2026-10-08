import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/prequal_compliance"
)


def _normalize_async_url(url: str) -> str:
    """Force a Postgres URL onto the async ``asyncpg`` driver (installed).

    MID-653: a plain ``postgresql://`` (or ``postgres://``, or a psycopg3
    ``+psycopg``) URL handed to ``create_async_engine`` selects the psycopg3
    dialect, which is not in requirements.txt -> ``ModuleNotFoundError`` at
    import time (this broke the Render deploy inside ``alembic/env.py``, which
    imports this module). ``asyncpg`` is already installed and expects the
    ``ssl`` query parameter (e.g. Neon's ``?ssl=require``), so map any
    ``sslmode=`` form to ``ssl=`` for this engine.
    """
    if url.startswith("sqlite"):
        return url
    for prefix in (
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    return url.replace("sslmode=require", "ssl=require")


ASYNC_DATABASE_URL = _normalize_async_url(DATABASE_URL)

# Connection pool tuning — read from env so Ops can adjust per environment
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

# SQLite has different pool settings than PostgreSQL
if ASYNC_DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
        pool_pre_ping=True,
    )
else:
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE,
        pool_timeout=POOL_TIMEOUT,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()