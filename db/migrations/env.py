"""
Alembic environment (SYNCHRONOUS).

Migrations run synchronously via psycopg2, not asyncpg. Two reasons:

  1. asyncpg sends every statement as a prepared statement, and Postgres
     rejects multiple commands in a prepared statement. Our append_only.sql
     is a multi-statement file with plpgsql $$ blocks, so it cannot run
     through asyncpg at all.
  2. Migrations have no concurrency requirement. Async buys nothing here.

The application itself still uses asyncpg (see db/session.py). Only the
migration path is sync.

Connects as troy_owner (SYNC_DATABASE_URL) — the app role has had
UPDATE/DELETE revoked and cannot alter schema.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from dotenv import load_dotenv

load_dotenv()

from alembic import context
from sqlalchemy import engine_from_config, pool

import db.models  # noqa: F401  (registers all models with Base.metadata)
from db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_sync_url() -> str:
    """
    Prefer an explicit sync URL. Otherwise downgrade an async URL by
    stripping the asyncpg driver, so a single DATABASE_URL still works.
    """
    url = os.environ.get("SYNC_DATABASE_URL")
    if url:
        return url

    url = os.environ.get("DATABASE_OWNER_URL") or os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql://")


db_url = _resolve_sync_url()
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Hand-written views are not autogenerate's business."""
    if type_ == "table" and name in {"signal_current", "signal_timeline"}:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
