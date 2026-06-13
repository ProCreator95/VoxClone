from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.ffmpeg_service import FFmpegService
from app.services.job_service import JobService
from app.services.media_service import MediaService
from app.services.redis_service import redis_service
from app.services.upload_service import UploadService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session (thin alias for route annotations)."""
    async for session in get_db():
        yield session


def get_media_service(db: AsyncSession = Depends(get_session)) -> MediaService:
    return MediaService(db)


def get_job_service(db: AsyncSession = Depends(get_session)) -> JobService:
    return JobService(db)


def get_upload_service(db: AsyncSession = Depends(get_session)) -> UploadService:
    return UploadService(db)


def get_ffmpeg_service() -> FFmpegService:
    return FFmpegService()


def get_redis():
    return redis_service
