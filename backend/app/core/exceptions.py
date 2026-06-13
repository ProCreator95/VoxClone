from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Domain Exceptions ─────────────────────────────────────────────────────────

class VoxCloneError(Exception):
    """Base exception for all VoxClone errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail or message
        super().__init__(message)


class MediaNotFoundError(VoxCloneError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "media_not_found"

    def __init__(self, media_id: str) -> None:
        super().__init__(
            message=f"Media '{media_id}' not found",
            detail=f"No media record exists with id={media_id}",
        )


class JobNotFoundError(VoxCloneError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "job_not_found"

    def __init__(self, job_id: str) -> None:
        super().__init__(
            message=f"Job '{job_id}' not found",
            detail=f"No job record exists with id={job_id}",
        )


class UnsupportedMediaFormatError(VoxCloneError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "unsupported_format"

    def __init__(self, extension: str, allowed: frozenset[str]) -> None:
        super().__init__(
            message=f"Unsupported format '.{extension}'",
            detail=f"Allowed extensions: {sorted(allowed)}",
        )


class FileTooLargeError(VoxCloneError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "file_too_large"

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(
            message="Uploaded file exceeds the size limit",
            detail=f"File size {size_bytes} bytes exceeds limit of {max_bytes} bytes",
        )


class FFmpegError(VoxCloneError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "ffmpeg_error"

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message=message, detail=stderr or message)


class JobConflictError(VoxCloneError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "job_conflict"


class StorageError(VoxCloneError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "storage_error"


class ResultNotReadyError(VoxCloneError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "result_not_ready"

    def __init__(self, job_id: str, current_status: str) -> None:
        super().__init__(
            message=f"Result for job '{job_id}' is not available yet",
            detail=f"Job status is '{current_status}'. Wait until status is 'completed'.",
        )


# ── Exception Handlers ────────────────────────────────────────────────────────

def _error_response(exc: VoxCloneError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VoxCloneError)
    async def voxclone_exception_handler(
        request: Request, exc: VoxCloneError
    ) -> JSONResponse:
        logger.warning(
            "domain_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        return _error_response(exc)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_error",
            path=request.url.path,
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "detail": str(exc),
            },
        )
