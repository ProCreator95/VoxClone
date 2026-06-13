from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

_diag_logger = get_logger(__name__)

_settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────

connect_args: dict = {}
if _settings.is_sqlite:
    # Required for SQLite to allow multi-threaded access
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    connect_args=connect_args,
)

# ── Session Factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Dependency helper ─────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside of FastAPI (e.g. Celery tasks)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as _rollback_exc:
            _diag_logger.exception(
                "diag_db_context_rollback",
                exc_type=type(_rollback_exc).__name__,
                exc_message=str(_rollback_exc),
            )
            await session.rollback()
            raise
        finally:
            await session.close()
