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
from typing import Any, Optional

from celery import Task

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.database.session import get_db_context
from app.models.job import JobStatus
from app.models.media import MediaType
from app.services.ffmpeg_service import FFmpegService
from app.services.job_service import JobService
from app.services.whisper_service import WhisperService
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


# ── Task: Subtitle Generation ─────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.generate_subtitles_task",
    max_retries=1,
)
def generate_subtitles_task(self: Task, job_id: str) -> dict:
    """
    Full subtitle pipeline via Whisper speech recognition.

    Pipeline:
        1. Load job + media from DB.
        2. If media is video → extract WAV audio via FFmpeg.
           If media is audio → use the file directly.
        3. Run WhisperService.transcribe() on the WAV file.
        4. Write three output files:
              <job_id>_transcript.txt  — plain text
              <job_id>_subtitles.srt   — SubRip subtitles
              <job_id>_subtitles.vtt   — WebVTT subtitles
        5. Persist all paths in job.parameters['result_files'].
        6. Set job.result_path to the .srt file (primary output).
    """

    async def _run() -> dict:
        # ── TOP-LEVEL SAFETY NET ──────────────────────────────────────────────
        # Catches anything that escapes inner blocks; logs a final traceback so
        # the root cause is always visible even if inner handlers also re-raise.
        try:
            # ── DIAG 1: task entry ────────────────────────────────────────────
            logger.info(
                "diag_task_entry",
                job_id=job_id,
                celery_request_id=self.request.id,
                celery_hostname=self.request.hostname,
            )

            setup_logging()

            # ── DIAG 2: creating FFmpegService ────────────────────────────────
            logger.info("diag_creating_ffmpeg_service", job_id=job_id)
            try:
                ffmpeg = FFmpegService()
                logger.info("diag_ffmpeg_service_ok", job_id=job_id)
            except Exception:
                logger.exception("diag_ffmpeg_service_failed", job_id=job_id)
                raise

            # ── DIAG 3: creating WhisperService ───────────────────────────────
            logger.info("diag_creating_whisper_service", job_id=job_id)
            try:
                whisper = WhisperService()
                logger.info(
                    "diag_whisper_service_ok",
                    job_id=job_id,
                    binary=settings.WHISPER_CPP_BINARY,
                    model_path=str(settings.WHISPER_MODEL_PATH),
                )
            except Exception:
                logger.exception("diag_whisper_service_failed", job_id=job_id)
                raise

            # ── 1. Load job ───────────────────────────────────────────────────
            # ── DIAG 4: entering first get_db_context ─────────────────────────
            logger.info("diag_entering_db_context_for_mark_started", job_id=job_id)
            try:
                async with get_db_context() as db:
                    logger.info("diag_db_context_acquired", job_id=job_id)

                    # ── DIAG 5: before mark_started ───────────────────────────
                    logger.info(
                        "diag_before_mark_started",
                        job_id=job_id,
                        celery_task_id=self.request.id,
                    )
                    job = await JobService(db).mark_started(job_id, self.request.id)

                    # ── DIAG 12: mark_started returned ────────────────────────
                    logger.info(
                        "diag_mark_started_returned",
                        job_id=job_id,
                        job_status=job.status,
                        job_started_at=str(job.started_at),
                    )

                    # ── DIAG 13: before accessing job.media ───────────────────
                    logger.info(
                        "diag_before_job_media_access",
                        job_id=job_id,
                        job_media_id=job.media_id,
                    )
                    media = job.media
                    logger.info(
                        "diag_job_media_access_ok",
                        job_id=job_id,
                        media_id=media.id if media else None,
                        media_type=media.media_type if media else None,
                        media_path=media.file_path if media else None,
                    )

                    params: dict = dict(job.parameters or {})
                    logger.info(
                        "diag_db_context_exiting",
                        job_id=job_id,
                        params_keys=list(params.keys()),
                    )

            except Exception as exc:
                logger.exception(
                    "diag_mark_started_block_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                )
                raise

            # ── 2-5. Pipeline ─────────────────────────────────────────────────
            try:
                await _update_progress(job_id, 5, "Preparing audio")

                # ── 2. Resolve audio path ─────────────────────────────────────
                # Caller may pre-supply an extracted WAV in parameters["audio_path"]
                supplied_audio = params.get("audio_path", "")
                audio_path: Path

                if supplied_audio and Path(supplied_audio).exists():
                    audio_path = Path(supplied_audio)
                    logger.info("subtitle_task_using_supplied_audio", path=str(audio_path))
                elif media.media_type == MediaType.VIDEO:
                    await _update_progress(job_id, 10, "Extracting audio from video")
                    audio_filename = f"{job_id}_audio.wav"
                    audio_path = settings.PROCESSED_DIR / audio_filename
                    video_path = Path(media.file_path)
                    logger.info(
                        "diag_before_video_path_check",
                        job_id=job_id,
                        video_path=str(video_path),
                        video_path_exists=video_path.exists(),
                    )
                    if not video_path.exists():
                        raise FileNotFoundError(f"Source video not found: {video_path}")
                    logger.info(
                        "diag_before_extract_audio",
                        job_id=job_id,
                        video_path=str(video_path),
                        output_path=str(audio_path),
                    )
                    await ffmpeg.extract_audio(video_path, audio_path)
                    logger.info(
                        "diag_after_extract_audio",
                        job_id=job_id,
                        output_path=str(audio_path),
                        output_exists=audio_path.exists(),
                    )
                    logger.info("subtitle_task_audio_extracted", path=str(audio_path))
                else:
                    # Media is already audio
                    audio_path = Path(media.file_path)
                    logger.info(
                        "diag_audio_media_path_check",
                        job_id=job_id,
                        audio_path=str(audio_path),
                        audio_path_exists=audio_path.exists(),
                    )
                    if not audio_path.exists():
                        raise FileNotFoundError(f"Audio file not found: {audio_path}")

                await _update_progress(job_id, 25, "Running whisper.cpp speech recognition")

                # ── 3. Transcribe ─────────────────────────────────────────────
                # Language may be overridden per-job via parameters["language"].
                # Falls back to WHISPER_LANGUAGE from settings (default: "en").
                language: Optional[str] = params.get("language") or None

                transcript = await whisper.transcribe(
                    audio_path=audio_path,
                    language=language,
                )

                await _update_progress(job_id, 70, "Generating subtitle files")

                # ── 4. Write output files ─────────────────────────────────────
                txt_path = settings.PROCESSED_DIR / f"{job_id}_transcript.txt"
                srt_path = settings.PROCESSED_DIR / f"{job_id}_subtitles.srt"
                vtt_path = settings.PROCESSED_DIR / f"{job_id}_subtitles.vtt"

                txt_path.write_text(transcript.to_txt(), encoding="utf-8")
                srt_path.write_text(transcript.to_srt(), encoding="utf-8")
                vtt_path.write_text(transcript.to_vtt(), encoding="utf-8")

                await _update_progress(job_id, 90, "Saving results")

                # ── 5. Persist result paths ───────────────────────────────────
                params["result_files"] = {
                    "transcript": str(txt_path),
                    "srt": str(srt_path),
                    "vtt": str(vtt_path),
                }
                params["detected_language"] = transcript.language
                params["segment_count"] = len(transcript.segments)

                async with get_db_context() as db:
                    job_svc = JobService(db)
                    await job_svc.update(job_id, parameters=params)
                    await job_svc.mark_completed(job_id, str(srt_path))

                logger.info(
                    "subtitle_task_done",
                    job_id=job_id,
                    language=transcript.language,
                    segments=len(transcript.segments),
                    srt=str(srt_path),
                )
                return {
                    "job_id": job_id,
                    "result_path": str(srt_path),
                    "transcript": str(txt_path),
                    "srt": str(srt_path),
                    "vtt": str(vtt_path),
                    "language": transcript.language,
                    "segment_count": len(transcript.segments),
                }

            except Exception as exc:
                logger.exception(
                    "subtitle_task_pipeline_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                )
                try:
                    async with get_db_context() as db:
                        await JobService(db).mark_failed(job_id, str(exc))
                except Exception as mark_failed_exc:
                    logger.exception(
                        "diag_mark_failed_itself_failed",
                        job_id=job_id,
                        original_exc_type=type(exc).__name__,
                        mark_failed_exc_type=type(mark_failed_exc).__name__,
                    )
                raise

        except Exception as top_exc:
            logger.exception(
                "diag_run_top_level_exception",
                job_id=job_id,
                exc_type=type(top_exc).__name__,
                exc_message=str(top_exc),
            )
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
