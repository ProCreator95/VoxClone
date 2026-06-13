from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_job_service, get_media_service, get_redis
from app.core.exceptions import ResultNotReadyError
from app.models.job import JobStatus, JobType
from app.schemas.common import MessageResponse
from app.schemas.job import JobCreate, JobProgressResponse, JobResponse
from app.services.job_service import JobService
from app.services.media_service import MediaService
from app.services.redis_service import RedisService
from app.tasks.media_tasks import dispatch_job

_SUBTITLE_MIME = {
    "transcript": "text/plain",
    "srt": "text/plain",
    "vtt": "text/vtt",
}
_SUBTITLE_EXT = {
    "transcript": ".txt",
    "srt": ".srt",
    "vtt": ".vtt",
}

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


@router.get(
    "/{job_id}/download/{format_type}",
    summary="Download a specific subtitle output format",
    description=(
        "Download one of the three subtitle pipeline outputs:\n"
        "- **transcript** — plain-text transcript (.txt)\n"
        "- **srt** — SubRip subtitle file (.srt)\n"
        "- **vtt** — WebVTT subtitle file (.vtt)\n\n"
        "Only available for completed `subtitle_generation` jobs."
    ),
)
async def download_subtitle_format(
    job_id: str,
    format_type: Literal["transcript", "srt", "vtt"],
    job_svc: JobService = Depends(get_job_service),
) -> FileResponse:
    job = await job_svc.get_by_id(job_id)

    if job.job_type != JobType.SUBTITLE_GENERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Job '{job_id}' is of type '{job.job_type}', "
                "not 'subtitle_generation'. "
                "Use /jobs/{id}/result for other job types."
            ),
        )

    if job.status != JobStatus.COMPLETED:
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    result_files: dict = (job.parameters or {}).get("result_files", {})
    file_path_str = result_files.get(format_type)

    # Graceful fallback: if result_files is missing, try result_path for srt
    if not file_path_str and format_type == "srt" and job.result_path:
        file_path_str = job.result_path

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Output format '{format_type}' is not available for job '{job_id}'. "
                "The job may have been created with an older version of VoxClone."
            ),
        )

    path = Path(file_path_str)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Output file for format '{format_type}' has been deleted from disk.",
        )

    filename = f"{job_id}{_SUBTITLE_EXT[format_type]}"
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type=_SUBTITLE_MIME[format_type],
    )


@router.get(
    "/{job_id}/download/video",
    summary="Download the burned-in subtitle video",
    description=(
        "Download the hardcoded-subtitle MP4 produced by a `subtitle_burn` job.\n\n"
        "Only available for completed `subtitle_burn` jobs.  "
        "Use `GET /jobs/{id}/result` as a generic alternative."
    ),
)
async def download_burned_video(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> FileResponse:
    job = await job_svc.get_by_id(job_id)

    if job.job_type != JobType.SUBTITLE_BURN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Job '{job_id}' is of type '{job.job_type}', "
                "not 'subtitle_burn'. "
                "Use /jobs/{id}/download/{transcript|srt|vtt} for subtitle_generation jobs."
            ),
        )

    if job.status != JobStatus.COMPLETED:
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    result_files: dict = (job.parameters or {}).get("result_files", {})
    file_path_str = result_files.get("burned_video")

    # Graceful fallback for jobs completed before result_files was introduced
    if not file_path_str and job.result_path:
        file_path_str = job.result_path

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Burned video path is not recorded for job '{job_id}'. "
                "The job may have been created with an older version of VoxClone."
            ),
        )

    path = Path(file_path_str)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Burned video file has been deleted from disk.",
        )

    return FileResponse(
        path=str(path),
        filename=f"{job_id}_subtitled.mp4",
        media_type="video/mp4",
    )
