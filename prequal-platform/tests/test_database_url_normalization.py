"""Unit tests for async database URL normalization (MID-653, MID-684).

A managed-Postgres URL (e.g. Neon) can carry libpq-only query params such as
``channel_binding=require``. SQLAlchemy's asyncpg dialect forwards unknown URL
query params straight to ``asyncpg.connect()``, which rejects them and crashes
app startup. ``_normalize_async_url`` must force the asyncpg driver, map
``sslmode`` -> ``ssl``, and strip those libpq-only params.
"""

from app.database import _normalize_async_url


def test_maps_plain_postgres_scheme_to_asyncpg():
    url = _normalize_async_url("postgresql://user:pw@host:5432/db")
    assert url.startswith("postgresql+asyncpg://")


def test_maps_sslmode_require_to_ssl_require():
    url = _normalize_async_url("postgresql://user:pw@host:5432/db?sslmode=require")
    assert "ssl=require" in url
    assert "sslmode=" not in url


def test_strips_channel_binding_leading_param():
    url = _normalize_async_url(
        "postgresql://user:pw@host:5432/db?channel_binding=require"
    )
    assert "channel_binding" not in url
    assert url.endswith("/db")


def test_strips_channel_binding_trailing_param_keeps_rest():
    url = _normalize_async_url(
        "postgresql://user:pw@host:5432/db?application_name=prequal&channel_binding=require"
    )
    assert "channel_binding" not in url
    assert "application_name=prequal" in url


def test_ssl_and_channel_binding_together():
    """The real Neon shape: both sslmode and channel_binding present."""
    url = _normalize_async_url(
        "postgresql://user:pw@host:5432/db?sslmode=require&channel_binding=require"
    )
    assert "ssl=require" in url
    assert "sslmode=" not in url
    assert "channel_binding" not in url


def test_channel_binding_before_sslmode():
    url = _normalize_async_url(
        "postgresql://user:pw@host:5432/db?channel_binding=require&sslmode=require"
    )
    assert "channel_binding" not in url
    assert "ssl=require" in url


def test_preserves_fragment():
    url = _normalize_async_url(
        "postgresql://user:pw@host:5432/db?channel_binding=require#frag"
    )
    assert "channel_binding" not in url
    assert url.endswith("#frag")


def test_sqlite_path_untouched():
    url = "sqlite+aiosqlite:///./test.db?sslmode=require&channel_binding=require"
    assert _normalize_async_url(url) == url
