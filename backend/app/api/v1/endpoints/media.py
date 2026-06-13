from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from app.api.deps import get_media_service, get_job_service
from app.core.exceptions import MediaNotFoundError, StorageError
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.job import JobListItem
from app.schemas.media import MediaListItem, MediaResponse
from app.services.job_service import JobService
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


@router.get(
    "",
    response_model=PaginatedResponse[MediaListItem],
    summary="List uploaded media",
)
async def list_media(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    media_type: str | None = Query(default=None, description="Filter by 'video' or 'audio'"),
    status: str | None = Query(default=None, description="Filter by status"),
    media_svc: MediaService = Depends(get_media_service),
) -> PaginatedResponse[MediaListItem]:
    items, total = await media_svc.list(
        page=page, page_size=page_size, media_type=media_type, status=status
    )
    return PaginatedResponse.build(
        items=[MediaListItem.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{media_id}",
    response_model=MediaResponse,
    summary="Get media details",
)
async def get_media(
    media_id: str,
    media_svc: MediaService = Depends(get_media_service),
) -> MediaResponse:
    media = await media_svc.get_by_id(media_id)
    return MediaResponse.model_validate(media)


@router.delete(
    "/{media_id}",
    response_model=MessageResponse,
    summary="Delete media and all its jobs",
)
async def delete_media(
    media_id: str,
    media_svc: MediaService = Depends(get_media_service),
) -> MessageResponse:
    media = await media_svc.get_by_id(media_id)
    file_path = Path(media.file_path)
    await media_svc.delete(media_id)
    if file_path.exists():
        file_path.unlink(missing_ok=True)
    return MessageResponse(message=f"Media '{media_id}' deleted successfully")


@router.get(
    "/{media_id}/download",
    summary="Download the original uploaded file",
)
async def download_media(
    media_id: str,
    media_svc: MediaService = Depends(get_media_service),
) -> FileResponse:
    media = await media_svc.get_by_id(media_id)
    path = Path(media.file_path)
    if not path.exists():
        raise StorageError(
            f"File for media '{media_id}' not found on disk",
            detail=str(path),
        )
    return FileResponse(
        path=str(path),
        media_type=media.mime_type,
        filename=media.original_name,
    )


@router.get(
    "/{media_id}/jobs",
    response_model=list[JobListItem],
    summary="List all jobs for a media file",
)
async def list_media_jobs(
    media_id: str,
    media_svc: MediaService = Depends(get_media_service),
    job_svc: JobService = Depends(get_job_service),
) -> list[JobListItem]:
    await media_svc.get_by_id(media_id)  # raises 404 if not found
    jobs = await job_svc.list_for_media(media_id)
    return [JobListItem.model_validate(j) for j in jobs]
