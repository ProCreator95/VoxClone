from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from app.api.deps import get_job_service, get_media_service, get_redis
from app.core.exceptions import ResultNotReadyError
from app.models.job import JobStatus
from app.schemas.common import MessageResponse
from app.schemas.job import JobCreate, JobProgressResponse, JobResponse
from app.services.job_service import JobService
from app.services.media_service import MediaService
from app.services.redis_service import RedisService
from app.tasks.media_tasks import dispatch_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a processing job",
    description=(
        "Creates a processing job for an uploaded media file and immediately "
        "dispatches it to the Celery worker queue. "
        "Poll `/jobs/{id}/progress` for live status updates."
    ),
)
async def create_job(
    payload: JobCreate,
    media_svc: MediaService = Depends(get_media_service),
    job_svc: JobService = Depends(get_job_service),
) -> JobResponse:
    # Validate that the source media exists
    await media_svc.get_by_id(payload.media_id)

    # Persist the job record first so workers can look it up by ID
    job = await job_svc.create(
        media_id=payload.media_id,
        job_type=payload.job_type,
        parameters=payload.parameters,
    )

    # Dispatch to Celery (non-blocking) and record the task ID
    celery_task_id = dispatch_job(job.id, job.job_type)
    job = await job_svc.update(job.id, celery_task_id=celery_task_id)

    return JobResponse.model_validate(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get full job details",
)
async def get_job(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> JobResponse:
    job = await job_svc.get_by_id(job_id)
    return JobResponse.model_validate(job)


@router.get(
    "/{job_id}/progress",
    response_model=JobProgressResponse,
    summary="Get live job progress (from Redis)",
    description="Returns low-latency progress snapshot from Redis. Falls back to DB if not cached.",
)
async def get_job_progress(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
    redis: RedisService = Depends(get_redis),
) -> JobProgressResponse:
    cached = await redis.get_progress(job_id)
    if cached:
        return JobProgressResponse(**cached)

    # Fallback to DB
    job = await job_svc.get_by_id(job_id)
    return JobProgressResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
    )


@router.get(
    "/{job_id}/result",
    summary="Download the processed result file",
)
async def download_result(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> FileResponse:
    job = await job_svc.get_by_id(job_id)
    if job.status != JobStatus.COMPLETED or not job.result_path:
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    path = Path(job.result_path)
    if not path.exists():
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete(
    "/{job_id}",
    response_model=MessageResponse,
    summary="Cancel a queued or running job",
)
async def cancel_job(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> MessageResponse:
    await job_svc.mark_cancelled(job_id)
    return MessageResponse(message=f"Job '{job_id}' has been cancelled")
