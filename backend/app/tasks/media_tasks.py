from __future__ import annotations

"""
Celery tasks for media processing pipelines.

All tasks follow the same pattern:
  1. Load job from DB and mark as PROCESSING.
  2. Execute FFmpeg / AI operations with incremental progress updates.
  3. Mark job COMPLETED (with result_path) or FAILED (with error_message).

Since Celery workers run in their own process, we use asyncio.run() to
execute async SQLAlchemy/FFmpeg calls from within synchronous Celery tasks.
"""

import asyncio
from pathlib import Path
from typing import Any

from celery import Task

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.database.session import get_db_context
from app.models.job import JobStatus
from app.services.ffmpeg_service import FFmpegService
from app.services.job_service import JobService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


# ── Base Task ─────────────────────────────────────────────────────────────────

class VoxCloneTask(Task):
    """Base task that wires up logging and captures unhandled failures."""

    abstract = True

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        setup_logging()
        logger.error(
            "task_unhandled_failure",
            task_id=task_id,
            task_name=self.name,
            exc_type=type(exc).__name__,
            exc_message=str(exc),
        )


# ── Helper ────────────────────────────────────────────────────────────────────

async def _update_progress(job_id: str, progress: int, step: str) -> None:
    async with get_db_context() as db:
        await JobService(db).update_progress(job_id, progress, step)


# ── Task: Audio Extraction ────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.extract_audio_task",
    max_retries=2,
)
def extract_audio_task(self: Task, job_id: str) -> dict:
    """Extract WAV audio from a video file (Pipeline 1 — Step 1)."""

    async def _run() -> dict:
        setup_logging()
        ffmpeg = FFmpegService()

        async with get_db_context() as db:
            job_svc = JobService(db)
            job = await job_svc.mark_started(job_id, self.request.id)
            media = job.media

        try:
            await _update_progress(job_id, 10, "Validating source file")

            video_path = Path(media.file_path)
            if not video_path.exists():
                raise FileNotFoundError(f"Source file not found: {video_path}")

            output_filename = f"{job_id}_audio.wav"
            output_path = settings.PROCESSED_DIR / output_filename

            await _update_progress(job_id, 20, "Extracting audio with FFmpeg")
            await ffmpeg.extract_audio(video_path, output_path)

            await _update_progress(job_id, 90, "Finalising")

            async with get_db_context() as db:
                await JobService(db).mark_completed(job_id, str(output_path))

            logger.info("extract_audio_task_done", job_id=job_id, output=str(output_path))
            return {"job_id": job_id, "result_path": str(output_path)}

        except Exception as exc:
            logger.exception("extract_audio_task_failed", job_id=job_id)
            async with get_db_context() as db:
                await JobService(db).mark_failed(job_id, str(exc))
            raise

    return asyncio.run(_run())


# ── Task: Subtitle Generation (placeholder) ───────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.generate_subtitles_task",
    max_retries=1,
)
def generate_subtitles_task(self: Task, job_id: str) -> dict:
    """
    Generate SRT subtitles via whisper.cpp (Pipeline 1 — Step 2).

    The actual whisper.cpp integration will be added when the
    subtitle pipeline is implemented. This task currently demonstrates
    the scaffolding and progress-update pattern.
    """

    async def _run() -> dict:
        setup_logging()

        async with get_db_context() as db:
            job_svc = JobService(db)
            job = await job_svc.mark_started(job_id, self.request.id)
            media = job.media

        try:
            await _update_progress(job_id, 10, "Loading audio")

            audio_path = Path(job.parameters.get("audio_path", "")) if job.parameters else None
            if not audio_path or not audio_path.exists():
                raise FileNotFoundError("Audio file path not provided or missing in parameters")

            await _update_progress(job_id, 20, "Running speech recognition")

            # ── whisper.cpp integration goes here ──
            # Example (to be replaced with actual whisper.cpp subprocess call):
            # srt_content = await run_whisper(audio_path, model="base")
            srt_content = _placeholder_srt()

            output_filename = f"{job_id}_subtitles.srt"
            output_path = settings.PROCESSED_DIR / output_filename
            output_path.write_text(srt_content, encoding="utf-8")

            await _update_progress(job_id, 90, "Writing SRT file")

            async with get_db_context() as db:
                await JobService(db).mark_completed(job_id, str(output_path))

            return {"job_id": job_id, "result_path": str(output_path)}

        except Exception as exc:
            logger.exception("generate_subtitles_task_failed", job_id=job_id)
            async with get_db_context() as db:
                await JobService(db).mark_failed(job_id, str(exc))
            raise

    return asyncio.run(_run())


# ── Task: Subtitle Burn ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.burn_subtitles_task",
    max_retries=2,
)
def burn_subtitles_task(self: Task, job_id: str) -> dict:
    """Burn SRT subtitles into video (Pipeline 1 — Step 3)."""

    async def _run() -> dict:
        setup_logging()
        ffmpeg = FFmpegService()

        async with get_db_context() as db:
            job_svc = JobService(db)
            job = await job_svc.mark_started(job_id, self.request.id)
            media = job.media

        try:
            params = job.parameters or {}
            srt_path = Path(params.get("srt_path", ""))
            if not srt_path.exists():
                raise FileNotFoundError(f"SRT file not found: {srt_path}")

            video_path = Path(media.file_path)
            output_filename = f"{job_id}_subtitled.mp4"
            output_path = settings.PROCESSED_DIR / output_filename

            await _update_progress(job_id, 20, "Burning subtitles with FFmpeg")
            await ffmpeg.burn_subtitles(video_path, srt_path, output_path)

            await _update_progress(job_id, 90, "Finalising output")

            async with get_db_context() as db:
                await JobService(db).mark_completed(job_id, str(output_path))

            return {"job_id": job_id, "result_path": str(output_path)}

        except Exception as exc:
            logger.exception("burn_subtitles_task_failed", job_id=job_id)
            async with get_db_context() as db:
                await JobService(db).mark_failed(job_id, str(exc))
            raise

    return asyncio.run(_run())


# ── Task: Karaoke (placeholder) ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.karaoke_task",
)
def karaoke_task(self: Task, job_id: str) -> dict:
    """Remove vocals via Demucs (placeholder — implementation TBD)."""

    async def _run() -> dict:
        setup_logging()
        async with get_db_context() as db:
            await JobService(db).mark_started(job_id, self.request.id)

        async with get_db_context() as db:
            await JobService(db).mark_failed(
                job_id,
                "Karaoke pipeline not yet implemented. Coming soon.",
            )
        return {"job_id": job_id, "status": "not_implemented"}

    return asyncio.run(_run())


# ── Task: Audio Enhancement (placeholder) ─────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.audio_enhance_task",
)
def audio_enhance_task(self: Task, job_id: str) -> dict:
    """Enhance audio via DeepFilterNet (placeholder — implementation TBD)."""

    async def _run() -> dict:
        setup_logging()
        async with get_db_context() as db:
            await JobService(db).mark_started(job_id, self.request.id)

        async with get_db_context() as db:
            await JobService(db).mark_failed(
                job_id,
                "Audio enhancement pipeline not yet implemented. Coming soon.",
            )
        return {"job_id": job_id, "status": "not_implemented"}

    return asyncio.run(_run())


# ── Utilities ─────────────────────────────────────────────────────────────────

def _placeholder_srt() -> str:
    return (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "[whisper.cpp integration pending]\n\n"
        "2\n"
        "00:00:02,000 --> 00:00:04,000\n"
        "Subtitle generation will appear here.\n\n"
    )


# ── Task Dispatcher ───────────────────────────────────────────────────────────

_TASK_MAP: dict[str, Any] = {
    "audio_extraction": extract_audio_task,
    "subtitle_generation": generate_subtitles_task,
    "subtitle_burn": burn_subtitles_task,
    "karaoke": karaoke_task,
    "audio_enhance": audio_enhance_task,
}


def dispatch_job(job_id: str, job_type: str) -> str:
    """
    Dispatch the appropriate Celery task for a given job type.
    Returns the Celery task ID.
    """
    task_fn = _TASK_MAP.get(job_type)
    if task_fn is None:
        raise ValueError(f"No task registered for job_type='{job_type}'")

    result = task_fn.delay(job_id)
    logger.info("task_dispatched", job_id=job_id, job_type=job_type, celery_task_id=result.id)
    return result.id
