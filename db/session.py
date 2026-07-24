"""
Async engine + session factory.

The app connects as the LEAST-PRIVILEGED role (troy_app), which has had
UPDATE and DELETE revoked on the evidence tables. Migrations connect as the
owner role. Two different URLs, on purpose — see .env.example:

    DATABASE_URL       = postgresql+asyncpg://troy_app:...@host/troy
    DATABASE_OWNER_URL = postgresql+asyncpg://troy_owner:...@host/troy
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.environ["DATABASE_URL"]
ECHO_SQL = os.getenv("SQL_ECHO", "0") == "1"

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=ECHO_SQL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,      # survives Postgres restarts / idle disconnects
    pool_recycle=1800,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objects stay usable after commit
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. One session per request."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """For jobs and scripts that aren't inside a request."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()