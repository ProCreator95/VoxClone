from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.api.deps import get_redis, get_session
from app.schemas.common import HealthStatus
from app.services.redis_service import RedisService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthStatus, summary="Health check")
async def health_check(
    db: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
) -> HealthStatus:
    """Returns live status of the API, database, and Redis."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    redis_status = "ok" if await redis.ping() else "unavailable"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthStatus(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
    )
