from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MediaNotFoundError
from app.core.logging import get_logger
from app.models.media import Media, MediaStatus

logger = get_logger(__name__)


class MediaService:
    """CRUD and query operations for Media records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, media_id: str) -> Media:
        result = await self._db.execute(
            select(Media).where(Media.id == media_id)
        )
        media = result.scalar_one_or_none()
        if media is None:
            raise MediaNotFoundError(media_id)
        return media

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        media_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[Media], int]:
        """Return (items, total_count) for pagination."""
        query = select(Media)
        count_query = select(func.count()).select_from(Media)

        if media_type:
            query = query.where(Media.media_type == media_type)
            count_query = count_query.where(Media.media_type == media_type)

        if status:
            query = query.where(Media.status == status)
            count_query = count_query.where(Media.status == status)

        total_result = await self._db.execute(count_query)
        total: int = total_result.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(Media.created_at.desc()).offset(offset).limit(page_size)

        items_result = await self._db.execute(query)
        items = list(items_result.scalars().all())

        return items, total

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, **kwargs) -> Media:
        media = Media(**kwargs)
        self._db.add(media)
        await self._db.flush()
        await self._db.refresh(media)
        logger.info("media_created", media_id=media.id, original_name=media.original_name)
        return media

    async def update(self, media_id: str, **kwargs) -> Media:
        media = await self.get_by_id(media_id)
        for key, value in kwargs.items():
            setattr(media, key, value)
        await self._db.flush()
        await self._db.refresh(media)
        return media

    async def update_status(self, media_id: str, status: str) -> Media:
        return await self.update(media_id, status=status)

    async def delete(self, media_id: str) -> None:
        media = await self.get_by_id(media_id)
        await self._db.delete(media)
        await self._db.flush()
        logger.info("media_deleted", media_id=media_id)
