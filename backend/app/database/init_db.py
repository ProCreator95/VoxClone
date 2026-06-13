from __future__ import annotations

from app.core.logging import get_logger
from app.database.base import Base
from app.database.session import engine

logger = get_logger(__name__)


async def create_tables() -> None:
    """Create all database tables on startup (idempotent)."""
    # Import models so SQLAlchemy registers them before create_all
    from app.models import media, job  # noqa: F401

    logger.info("creating_database_tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_ready")


async def drop_tables() -> None:
    """Drop all tables — intended for tests only."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
