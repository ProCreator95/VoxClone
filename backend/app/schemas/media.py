from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    original_name: str
    file_size: int
    mime_type: str
    media_type: str

    # Probed metadata — may be None until ffprobe completes
    duration: Optional[float] = None
    format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    codec_video: Optional[str] = None
    codec_audio: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None

    status: str
    extra_metadata: Optional[dict] = None

    created_at: datetime
    updated_at: datetime


class MediaListItem(BaseModel):
    """Lightweight representation used in list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    media_type: str
    file_size: int
    duration: Optional[float] = None
    status: str
    created_at: datetime


class MediaUpdateStatus(BaseModel):
    """Internal — used by services to update media status."""

    status: str
    extra_metadata: Optional[dict] = Field(default=None)
