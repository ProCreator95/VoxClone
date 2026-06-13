from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_PROGRESS_TTL = 60 * 60 * 24  # 24 hours
_PROGRESS_KEY_PREFIX = "job:progress:"


class RedisService:
    """Manages Redis connections and job-progress caching."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client: Optional[aioredis.Redis] = None
        self._url = settings.REDIS_URL

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            self._url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("redis_connected", url=self._url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisService not connected. Call connect() first.")
        return self._client

    # ── Health ────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    # ── Job Progress ──────────────────────────────────────────────────────────

    async def set_progress(
        self,
        job_id: str,
        status: str,
        progress: int,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Cache a progress snapshot for low-latency polling by clients."""
        key = f"{_PROGRESS_KEY_PREFIX}{job_id}"
        payload = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "current_step": current_step,
            "error_message": error_message,
        }
        await self.client.set(key, json.dumps(payload), ex=_PROGRESS_TTL)

    async def get_progress(self, job_id: str) -> Optional[dict]:
        """Retrieve cached progress, or None if not found."""
        key = f"{_PROGRESS_KEY_PREFIX}{job_id}"
        data = await self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def delete_progress(self, job_id: str) -> None:
        key = f"{_PROGRESS_KEY_PREFIX}{job_id}"
        await self.client.delete(key)

    # ── Generic Key/Value ─────────────────────────────────────────────────────

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        await self.client.set(key, value, ex=ttl)

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)


# Module-level singleton — shared across the application lifetime
redis_service = RedisService()
