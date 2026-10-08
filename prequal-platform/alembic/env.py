from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# MID-625 / MID-653: honor DATABASE_URL so `alembic upgrade head` targets the
# real database (e.g. Neon staging) instead of alembic.ini's localhost default.
# Alembic requires a *sync* driver, so normalize any Postgres scheme the app
# may be handed (plain, asyncpg, or psycopg3) onto `psycopg2`, which is in
# requirements.txt. libpq (psycopg2) wants `sslmode=require` while asyncpg
# wants `ssl=require`, so translate the SSL param here too. Normalizing in
# this one place means the board never has to hand-edit the URL scheme.
def _sync_alembic_url(url: str) -> str:
    url = url.replace("postgres://", "postgresql://", 1)
    url = url.replace("+asyncpg://", "://").replace("+psycopg://", "://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url.replace("ssl=require", "sslmode=require")


_database_url = os.getenv("DATABASE_URL", "")
if _database_url:
    config.set_main_option("sqlalchemy.url", _sync_alembic_url(_database_url))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base
import app.models.compliance  # noqa: F401
import app.models.auth  # noqa: F401 — registers auth models
import app.models.alerts  # noqa: F401 — registers alert models
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
