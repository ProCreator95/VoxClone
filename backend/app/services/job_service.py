from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        job = await self.get_by_id(job_id)
        if job.status not in (JobStatus.QUEUED,):
            raise JobConflictError(
                f"Cannot start job in status '{job.status}'",
                detail=f"Job {job_id} must be in 'queued' status to start.",
            )
        job.status = JobStatus.PROCESSING
        job.celery_task_id = celery_task_id
        job.started_at = datetime.now(timezone.utc)
        await self._db.flush()
        await redis_service.set_progress(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress=0,
            current_step="Starting",
        )
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
