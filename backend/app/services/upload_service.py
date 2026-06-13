from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, StorageError, UnsupportedMediaFormatError
from app.core.logging import get_logger
from app.models.media import Media, MediaStatus, MediaType
from app.services.ffmpeg_service import FFmpegService
from app.services.media_service import MediaService

logger = get_logger(__name__)
_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _detect_media_type(extension: str) -> str:
    settings = get_settings()
    if extension in settings.ALLOWED_VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    return MediaType.AUDIO


def _resolve_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


class UploadService:
    """Handles file ingestion: validation → disk write → probe → DB record."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()
        self._media_svc = MediaService(db)
        self._ffmpeg = FFmpegService()

    async def ingest(self, file: UploadFile) -> Media:
        """Full upload pipeline: validate → save → probe → persist."""
        extension = self._validate_extension(file.filename or "")
        dest_path, stored_filename = self._build_dest_path(extension)

        file_size = await self._stream_to_disk(file, dest_path)
        self._validate_size(file_size)

        probe_result = await self._probe_file(dest_path)

        media_type = _detect_media_type(extension)
        mime_type = _resolve_mime(file.filename or stored_filename)

        media = await self._media_svc.create(
            filename=stored_filename,
            original_name=file.filename or stored_filename,
            file_path=str(dest_path),
            file_size=file_size,
            mime_type=mime_type,
            media_type=media_type,
            status=MediaStatus.READY,
            duration=probe_result.duration,
            format=probe_result.format_name,
            width=probe_result.width,
            height=probe_result.height,
            codec_video=probe_result.codec_video,
            codec_audio=probe_result.codec_audio,
            bitrate=probe_result.bitrate,
            sample_rate=probe_result.sample_rate,
            audio_channels=probe_result.audio_channels,
        )

        logger.info(
            "upload_ingested",
            media_id=media.id,
            original_name=file.filename,
            size_bytes=file_size,
            media_type=media_type,
        )
        return media

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_extension(self, filename: str) -> str:
        if "." not in filename:
            raise UnsupportedMediaFormatError(
                extension="", allowed=self._settings.allowed_extensions
            )
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in self._settings.allowed_extensions:
            raise UnsupportedMediaFormatError(
                extension=ext, allowed=self._settings.allowed_extensions
            )
        return ext

    def _build_dest_path(self, extension: str) -> tuple[Path, str]:
        stored_filename = f"{uuid4().hex}.{extension}"
        dest_path = self._settings.UPLOAD_DIR / stored_filename
        return dest_path, stored_filename

    async def _stream_to_disk(self, file: UploadFile, dest_path: Path) -> int:
        """Write upload to disk in chunks; return total bytes written."""
        written = 0
        try:
            async with aiofiles.open(dest_path, "wb") as f:
                while True:
                    chunk = await file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    await f.write(chunk)
                    written += len(chunk)
        except OSError as exc:
            raise StorageError(
                f"Failed to write uploaded file: {exc}", detail=str(exc)
            ) from exc
        return written

    def _validate_size(self, size_bytes: int) -> None:
        if size_bytes > self._settings.MAX_UPLOAD_SIZE_BYTES:
            raise FileTooLargeError(
                size_bytes=size_bytes,
                max_bytes=self._settings.MAX_UPLOAD_SIZE_BYTES,
            )

    async def _probe_file(self, path: Path):
        try:
            return await self._ffmpeg.probe(path)
        except Exception as exc:
            logger.warning("probe_failed", path=str(path), error=str(exc))
            from app.services.ffmpeg_service import ProbeResult
            return ProbeResult()
