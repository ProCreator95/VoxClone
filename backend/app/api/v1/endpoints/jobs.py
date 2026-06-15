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
from app.tasks.media_tasks import IMPLEMENTED_JOB_TYPES, dispatch_job

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
    # Guard BEFORE creating the DB record.
    # JobType.ALL (used by JobCreate.validate_job_type) includes planned-but-not-yet-
    # implemented types such as voice_replacement and voice_clone.  Without this check,
    # a valid job record would be created in the DB and then dispatch_job() would raise
    # ValueError, leaving the job stuck in status=queued (a zombie job) and returning
    # HTTP 500 to the caller.  Checking IMPLEMENTED_JOB_TYPES first keeps both concerns
    # separate: the schema layer validates the name is known, this layer validates it is
    # runnable.  IMPLEMENTED_JOB_TYPES is derived from _TASK_MAP in media_tasks.py, so
    # adding a new task there automatically makes it available here with no API changes.
    if payload.job_type not in IMPLEMENTED_JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Job type '{payload.job_type}' is planned but not yet implemented. "
                f"Currently available: {sorted(IMPLEMENTED_JOB_TYPES)}."
            ),
        )

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


# ── IMPORTANT: route order is load-bearing in FastAPI ────────────────────────
# FastAPI matches routes in declaration order.  Every literal path segment
# ("video", "ass", "karaoke-video") MUST be declared before the parameterised
# catch-all route /download/{format_type}.  If the parameterised route came
# first, those literal strings would be captured as format_type and rejected
# by the Literal["transcript","srt","vtt"] validator — HTTP 422 — before the
# dedicated handler is ever reached.  This cost us one round of debugging in
# Phase 3 (Bug 6 in KNOWN_BUGS_AND_ROOT_CAUSES.md).
#
# When adding a new Phase N download endpoint:
#   • Declare it ABOVE the /download/{format_type} route.
#   • Add it to the Required declaration order comment below.
#
# Required declaration order (DO NOT REORDER):
#   1. /download/video           ← Phase 3: subtitle_burn jobs
#   2. /download/ass             ← Phase 4: karaoke jobs (ASS file)
#   3. /download/karaoke-video   ← Phase 4: karaoke jobs (MP4)
#   4. /download/{format_type}   ← must remain LAST

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


@router.get(
    "/{job_id}/download/ass",
    summary="Download the ASS karaoke subtitle file",
    description=(
        "Download the Advanced SubStation Alpha (ASS) karaoke subtitle file produced "
        "by a `karaoke` job.  The file contains `\\kf` timing tags for word-level "
        "highlighting.\n\n"
        "Only available for completed `karaoke` jobs."
    ),
)
async def download_karaoke_ass(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> FileResponse:
    job = await job_svc.get_by_id(job_id)

    if job.job_type != JobType.KARAOKE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Job '{job_id}' is of type '{job.job_type}', not 'karaoke'. "
                "Use /jobs/{id}/download/{transcript|srt|vtt} for subtitle_generation jobs."
            ),
        )

    if job.status != JobStatus.COMPLETED:
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    result_files: dict = (job.parameters or {}).get("result_files", {})
    file_path_str = result_files.get("ass")

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"ASS subtitle path is not recorded for job '{job_id}'. "
                "The job may have been created with an older version of VoxClone."
            ),
        )

    path = Path(file_path_str)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ASS subtitle file has been deleted from disk.",
        )

    return FileResponse(
        path=str(path),
        filename=f"{job_id}_karaoke.ass",
        media_type="text/plain",
    )


@router.get(
    "/{job_id}/download/karaoke-video",
    summary="Download the karaoke video",
    description=(
        "Download the H.264 MP4 with karaoke subtitles burned in, produced by a "
        "`karaoke` job.\n\n"
        "Only available for completed `karaoke` jobs.  "
        "Use `GET /jobs/{id}/download/video` for `subtitle_burn` jobs."
    ),
)
async def download_karaoke_video(
    job_id: str,
    job_svc: JobService = Depends(get_job_service),
) -> FileResponse:
    job = await job_svc.get_by_id(job_id)

    if job.job_type != JobType.KARAOKE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Job '{job_id}' is of type '{job.job_type}', not 'karaoke'. "
                "Use /jobs/{id}/download/video for subtitle_burn jobs."
            ),
        )

    if job.status != JobStatus.COMPLETED:
        raise ResultNotReadyError(job_id=job_id, current_status=job.status)

    result_files: dict = (job.parameters or {}).get("result_files", {})
    file_path_str = result_files.get("video")

    # Graceful fallback for jobs completed before result_files was introduced
    if not file_path_str and job.result_path:
        file_path_str = job.result_path

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Karaoke video path is not recorded for job '{job_id}'. "
                "The job may have been created with an older version of VoxClone."
            ),
        )

    path = Path(file_path_str)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karaoke video file has been deleted from disk.",
        )

    return FileResponse(
        path=str(path),
        filename=f"{job_id}_karaoke.mp4",
        media_type="video/mp4",
    )


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
