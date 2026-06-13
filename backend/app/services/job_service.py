from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import JobConflictError, JobNotFoundError
from app.core.logging import get_logger
from app.models.job import Job, JobStatus
from app.services.redis_service import redis_service

logger = get_logger(__name__)


class JobService:
    """CRUD and lifecycle management for processing Jobs."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, job_id: str) -> Job:
        result = await self._db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    async def get_by_id_with_media(self, job_id: str) -> Job:
        """Load a Job and eagerly fetch its Media in a single query.

        Uses selectinload so the async session never issues a lazy SQL
        round-trip when the caller accesses job.media.  Required for all
        Celery tasks that run outside the FastAPI request context.
        """
        result = await self._db.execute(
            select(Job)
            .options(selectinload(Job.media))
            .where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(job_id)
        logger.info(
            "diag_job_media_preloaded",
            job_id=job_id,
            media_id=job.media.id if job.media else None,
            media_type=job.media.media_type if job.media else None,
        )
        return job

    async def get_by_celery_id(self, celery_task_id: str) -> Optional[Job]:
        result = await self._db.execute(
            select(Job).where(Job.celery_task_id == celery_task_id)
        )
        return result.scalar_one_or_none()

    async def list_for_media(self, media_id: str) -> list[Job]:
        result = await self._db.execute(
            select(Job)
            .where(Job.media_id == media_id)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(
        self,
        media_id: str,
        job_type: str,
        parameters: Optional[dict] = None,
    ) -> Job:
        job = Job(
            media_id=media_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            parameters=parameters,
        )
        self._db.add(job)
        await self._db.flush()
        await self._db.refresh(job)

        await redis_service.set_progress(
            job_id=job.id,
            status=JobStatus.QUEUED,
            progress=0,
            current_step="Queued",
        )

        logger.info("job_created", job_id=job.id, media_id=media_id, job_type=job_type)
        return job

    # ── Status Transitions ────────────────────────────────────────────────────

    async def update(self, job_id: str, **kwargs) -> Job:
        """Generic field update — used for persisting Celery task IDs etc."""
        job = await self.get_by_id(job_id)
        for key, value in kwargs.items():
            setattr(job, key, value)
        await self._db.flush()
        await self._db.refresh(job)
        return job

    async def mark_started(self, job_id: str, celery_task_id: str) -> Job:
        # ── DIAG 6: mark_started entry ────────────────────────────────────────
        logger.info(
            "diag_mark_started_entry",
            job_id=job_id,
            celery_task_id=celery_task_id,
        )

        # ── DIAG 6a: before get_by_id ─────────────────────────────────────────
        logger.info("diag_mark_started_before_get_by_id", job_id=job_id)
        try:
            job = await self.get_by_id_with_media(job_id)
        except Exception as exc:
            logger.exception(
                "diag_mark_started_get_by_id_failed",
                job_id=job_id,
                exc_info=True,
            )
            raise

        # ── DIAG 7: after get_by_id ───────────────────────────────────────────
        logger.info(
            "diag_mark_started_after_get_by_id",
            job_id=job_id,
            job_status=job.status,
            job_type=job.job_type,
        )

        if job.status not in (JobStatus.QUEUED,):
            logger.warning(
                "diag_mark_started_wrong_status",
                job_id=job_id,
                current_status=job.status,
            )
            raise JobConflictError(
                f"Cannot start job in status '{job.status}'",
                detail=f"Job {job_id} must be in 'queued' status to start.",
            )

        # ── DIAG 8: before status update ──────────────────────────────────────
        logger.info(
            "diag_mark_started_before_status_update",
            job_id=job_id,
            new_status=JobStatus.PROCESSING,
        )
        job.status = JobStatus.PROCESSING
        job.celery_task_id = celery_task_id
        job.started_at = datetime.now(timezone.utc)

        # ── DIAG 9: before flush ──────────────────────────────────────────────
        logger.info("diag_mark_started_before_flush", job_id=job_id)
        try:
            await self._db.flush()
        except Exception as exc:
            logger.exception(
                "diag_mark_started_flush_failed",
                job_id=job_id,
                exc_info=True,
            )
            raise
        # ── DIAG 9a: after flush ──────────────────────────────────────────────
        logger.info("diag_mark_started_after_flush", job_id=job_id)

        # ── DIAG 10: before redis set_progress ───────────────────────────────
        redis_client_is_none = redis_service._client is None
        logger.info(
            "diag_mark_started_before_redis",
            job_id=job_id,
            redis_client_is_none=redis_client_is_none,
            redis_url=redis_service._url,
        )
        try:
            await redis_service.set_progress(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress=0,
                current_step="Starting",
            )
        except Exception as exc:
            logger.exception(
                "diag_mark_started_redis_failed",
                job_id=job_id,
                redis_client_is_none=redis_client_is_none,
                exc_type=type(exc).__name__,
                exc_info=True,
            )
            raise

        # ── DIAG 11: after redis set_progress ────────────────────────────────
        logger.info("diag_mark_started_after_redis", job_id=job_id)
        logger.info("job_started", job_id=job_id, celery_task_id=celery_task_id)
        return job

    async def update_progress(
        self,
        job_id: str,
        progress: int,
        current_step: Optional[str] = None,
    ) -> None:
        """Update progress in both DB and Redis."""
        job = await self.get_by_id(job_id)
        job.progress = progress
        if current_step:
            job.current_step = current_step
        await self._db.flush()

        await redis_service.set_progress(
            job_id=job_id,
            status=job.status,
            progress=progress,
            current_step=current_step,
        )

    async def mark_completed(self, job_id: str, result_path: str) -> Job:
        job = await self.get_by_id(job_id)
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.result_path = result_path
        job.current_step = "Done"
        job.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        await redis_service.set_progress(
            job_id=job_id, status=JobStatus.COMPLETED, progress=100, current_step="Done"
        )
        logger.info("job_completed", job_id=job_id, result_path=result_path)
        return job

    async def mark_failed(self, job_id: str, error_message: str) -> Job:
        job = await self.get_by_id(job_id)
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        await redis_service.set_progress(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=job.progress,
            error_message=error_message,
        )
        logger.error("job_failed", job_id=job_id, error=error_message)
        return job

    async def mark_cancelled(self, job_id: str) -> Job:
        job = await self.get_by_id(job_id)
        if job.is_terminal:
            raise JobConflictError(
                f"Cannot cancel job with status '{job.status}'",
                detail="Only active (queued/processing) jobs can be cancelled.",
            )
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        await redis_service.set_progress(
            job_id=job_id, status=JobStatus.CANCELLED, progress=job.progress
        )
        logger.info("job_cancelled", job_id=job_id)
        return job
