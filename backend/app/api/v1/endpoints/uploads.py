from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import get_upload_service
from app.schemas.media import MediaResponse
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a media file",
    description=(
        "Upload a video or audio file. The server streams the file to disk, "
        "probes it with ffprobe, and returns the full media record. "
        "Supported video formats: mp4, webm, mov, mkv, avi. "
        "Supported audio formats: mp3, wav, flac, m4a."
    ),
)
async def upload_media(
    file: UploadFile = File(..., description="Media file to upload"),
    upload_svc: UploadService = Depends(get_upload_service),
) -> MediaResponse:
    media = await upload_svc.ingest(file)
    return MediaResponse.model_validate(media)
