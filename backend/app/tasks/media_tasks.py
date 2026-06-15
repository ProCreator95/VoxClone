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
from app.models.job import JobStatus, JobType
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
    """
    Burn SRT subtitles into video using FFmpeg (Phase 3).

    Parameters (passed via job.parameters at job-creation time):
        subtitle_job_id (str, primary):
            UUID of a completed subtitle_generation job.  The task looks up
            that job's parameters["result_files"]["srt"] to resolve the SRT
            path automatically.  This is the intended production workflow.

        srt_path (str, testing only):
            Absolute path to an SRT file on disk.  Use only for local testing
            when you already know the server-side path.

        font_size  (int,   default 24)
        font_name  (str,   default "Arial")
        font_color (str,   default "&H00FFFFFF&"  — white, ASS hex)
        outline_color (str, default "&H00000000&" — black, ASS hex)

    Output:
        processed/<job_id>_subtitled.mp4  — H.264 video, audio stream-copied.
        result_path set to the above path.
        parameters["result_files"]["burned_video"] set to the same path.
        parameters["subtitle_job_id"] preserved for traceability.
    """

    async def _run() -> dict:
        # ── TOP-LEVEL SAFETY NET ──────────────────────────────────────────────
        # Catches anything that escapes the inner pipeline block; guarantees a
        # final traceback is always visible in the worker log.
        try:
            # ── DIAG 1: task entry ────────────────────────────────────────────
            logger.info(
                "diag_burn_task_entry",
                job_id=job_id,
                celery_request_id=self.request.id,
                celery_hostname=self.request.hostname,
            )

            setup_logging()
            ffmpeg = FFmpegService()

            # ── 1. Load job + media, mark started ────────────────────────────
            # mark_started() calls get_by_id_with_media() (selectinload) so
            # job.media is fully populated before the session closes.
            # expire_on_commit=False on AsyncSessionLocal means the loaded
            # attributes survive outside the get_db_context block.
            logger.info("diag_burn_entering_db_context_mark_started", job_id=job_id)
            try:
                async with get_db_context() as db:
                    logger.info(
                        "diag_burn_before_mark_started",
                        job_id=job_id,
                        celery_task_id=self.request.id,
                    )
                    job = await JobService(db).mark_started(job_id, self.request.id)
                    logger.info(
                        "diag_burn_mark_started_returned",
                        job_id=job_id,
                        job_status=job.status,
                        job_media_id=job.media_id,
                    )
                    media = job.media
                    params: dict = dict(job.parameters or {})
                    logger.info(
                        "diag_burn_media_loaded",
                        job_id=job_id,
                        media_id=media.id if media else None,
                        media_type=media.media_type if media else None,
                        media_path=media.file_path if media else None,
                        params_keys=list(params.keys()),
                    )
            except Exception as exc:
                logger.exception(
                    "diag_burn_mark_started_block_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                )
                raise

            # ── 2-6. Pipeline ─────────────────────────────────────────────────
            try:
                # ── 2. Resolve SRT path ───────────────────────────────────────
                await _update_progress(job_id, 5, "Resolving SRT source")

                subtitle_job_id: str = params.get("subtitle_job_id", "")
                srt_path_str: str = params.get("srt_path", "")

                if subtitle_job_id:
                    # ── PRIMARY WORKFLOW ──────────────────────────────────────
                    # Look up the SRT path from a completed subtitle_generation job.
                    logger.info(
                        "diag_burn_resolving_from_subtitle_job_id",
                        job_id=job_id,
                        subtitle_job_id=subtitle_job_id,
                    )
                    async with get_db_context() as db:
                        prior_job = await JobService(db).get_by_id(subtitle_job_id)

                    if prior_job.status != JobStatus.COMPLETED:
                        raise ValueError(
                            f"subtitle_job_id '{subtitle_job_id}' is in status "
                            f"'{prior_job.status}' — must be 'completed'."
                        )
                    if prior_job.job_type != JobType.SUBTITLE_GENERATION:
                        raise ValueError(
                            f"subtitle_job_id '{subtitle_job_id}' has job_type "
                            f"'{prior_job.job_type}' — must be 'subtitle_generation'."
                        )

                    prior_result_files: dict = (prior_job.parameters or {}).get("result_files", {})
                    srt_path_str = prior_result_files.get("srt", "")
                    if not srt_path_str:
                        raise ValueError(
                            f"subtitle_job '{subtitle_job_id}' has no 'srt' "
                            "entry in result_files — was it generated correctly?"
                        )

                    srt_path = Path(srt_path_str)
                    # Keep subtitle_job_id in params so it is visible in the
                    # completed job record for traceability and debugging.
                    params["subtitle_job_id"] = subtitle_job_id

                    logger.info(
                        "diag_burn_srt_resolved_from_subtitle_job",
                        job_id=job_id,
                        subtitle_job_id=subtitle_job_id,
                        srt_path=str(srt_path),
                    )

                elif srt_path_str:
                    # ── TESTING / TOOLING MODE ────────────────────────────────
                    # Caller supplies an absolute server-side path directly.
                    srt_path = Path(srt_path_str)
                    logger.info(
                        "diag_burn_srt_path_direct",
                        job_id=job_id,
                        srt_path=str(srt_path),
                    )

                else:
                    raise ValueError(
                        "burn_subtitles_task requires 'subtitle_job_id' (primary workflow) "
                        "or 'srt_path' (testing only) in job parameters."
                    )

                # ── 3. Validate inputs ────────────────────────────────────────
                await _update_progress(job_id, 15, "Validating inputs")

                logger.info(
                    "diag_burn_validation_start",
                    job_id=job_id,
                    media_type=media.media_type,
                    media_path=media.file_path,
                    srt_path=str(srt_path),
                )

                if media.media_type != MediaType.VIDEO:
                    raise ValueError(
                        f"Subtitle burn requires a video file; "
                        f"source media has media_type='{media.media_type}'."
                    )

                video_path = Path(media.file_path)
                if not video_path.exists():
                    raise FileNotFoundError(f"Source video not found: {video_path}")

                if not srt_path.exists():
                    raise FileNotFoundError(f"SRT file not found: {srt_path}")

                logger.info(
                    "diag_burn_validation_passed",
                    job_id=job_id,
                    video_path=str(video_path),
                    srt_path=str(srt_path),
                    video_size_bytes=video_path.stat().st_size,
                    srt_size_bytes=srt_path.stat().st_size,
                )

                # ── 4. Build output path ──────────────────────────────────────
                output_filename = f"{job_id}_subtitled.mp4"
                output_path = settings.PROCESSED_DIR / output_filename

                # ── 5. Burn subtitles via FFmpeg ──────────────────────────────
                await _update_progress(job_id, 20, "Burning subtitles with FFmpeg")

                logger.info(
                    "diag_burn_ffmpeg_start",
                    job_id=job_id,
                    video_path=str(video_path),
                    srt_path=str(srt_path),
                    output_path=str(output_path),
                    font_size=params.get("font_size", 24),
                    font_name=params.get("font_name", "Arial"),
                )

                await ffmpeg.burn_subtitles(
                    video_path,
                    srt_path,
                    output_path,
                    font_size=int(params.get("font_size", 24)),
                    font_name=str(params.get("font_name", "Arial")),
                    font_color=str(params.get("font_color", "&H00FFFFFF&")),
                    outline_color=str(params.get("outline_color", "&H00000000&")),
                )

                logger.info(
                    "diag_burn_ffmpeg_done",
                    job_id=job_id,
                    output_path=str(output_path),
                    output_exists=output_path.exists(),
                    output_size_bytes=(
                        output_path.stat().st_size if output_path.exists() else 0
                    ),
                )

                await _update_progress(job_id, 90, "Finalising output")

                # ── 6. Persist result ─────────────────────────────────────────
                params["result_files"] = {"burned_video": str(output_path)}

                logger.info(
                    "diag_burn_persisting_completion",
                    job_id=job_id,
                    result_path=str(output_path),
                    params_keys=list(params.keys()),
                )

                async with get_db_context() as db:
                    job_svc = JobService(db)
                    await job_svc.update(job_id, parameters=params)
                    await job_svc.mark_completed(job_id, str(output_path))

                logger.info(
                    "burn_subtitles_task_done",
                    job_id=job_id,
                    output=str(output_path),
                )
                return {"job_id": job_id, "result_path": str(output_path)}

            except Exception as exc:
                logger.exception(
                    "burn_subtitles_task_pipeline_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                    exc_message=str(exc),
                )
                try:
                    async with get_db_context() as db:
                        await JobService(db).mark_failed(job_id, str(exc))
                except Exception as mark_failed_exc:
                    logger.exception(
                        "diag_burn_mark_failed_itself_failed",
                        job_id=job_id,
                        original_exc_type=type(exc).__name__,
                        mark_failed_exc_type=type(mark_failed_exc).__name__,
                    )
                raise

        except Exception as top_exc:
            logger.exception(
                "diag_burn_run_top_level_exception",
                job_id=job_id,
                exc_type=type(top_exc).__name__,
                exc_message=str(top_exc),
            )
            raise

    return asyncio.run(_run())


# ── Task: Karaoke Generation ──────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=VoxCloneTask,
    name="app.tasks.media_tasks.karaoke_task",
    max_retries=1,
)
def karaoke_task(self: Task, job_id: str) -> dict:
    """
    Karaoke pipeline: transcribe with word-level timestamps and burn ASS into video.

    Pipeline:
        1. Load job + media from DB (eager-loaded to avoid DetachedInstanceError).
        2. Validate media is a video file — burn_ass() requires a video stream.
        3. Extract 16kHz mono WAV via FFmpeg.
        4. Transcribe with word_timestamps=True (--output-json-full).
        5. Write <job_id>_karaoke.ass with \\kf karaoke timing tags.
        6. Burn ASS into video via FFmpegService.burn_ass().
        7. Persist result_files + timing metadata in job.parameters.
        8. Set job.result_path to the output MP4.

    Parameters (passed via job.parameters at job-creation time):
        language        (str, optional  — default: WHISPER_LANGUAGE from settings)
        highlight_color (str, optional  — default: "&H0000FFFF&" yellow, ASS AABBGGRR)
        base_color      (str, optional  — default: "&H00FFFFFF&" white)
        font_name       (str, optional  — default: "Arial")
        font_size       (int, optional  — default: 24)

    Output:
        processed/<job_id>_audio.wav     — extracted WAV (kept for traceability)
        processed/<job_id>_karaoke.ass   — ASS subtitle file with \\kf tags
        processed/<job_id>_karaoke.mp4   — final output (also job.result_path)

    Routing: "ai" queue (defined in celery_app.py task_routes).
    """

    async def _run() -> dict:
        # ── TOP-LEVEL SAFETY NET ──────────────────────────────────────────────
        # Mirrors the structure used in generate_subtitles_task and
        # burn_subtitles_task: a top-level try/except ensures a final traceback
        # always appears in the worker log, even if inner handlers also re-raise.
        try:
            # ── DIAG 1: task entry ────────────────────────────────────────────
            logger.info(
                "diag_karaoke_task_entry",
                job_id=job_id,
                celery_request_id=self.request.id,
                celery_hostname=self.request.hostname,
            )

            setup_logging()

            # ── DIAG 2/3: services ───────────────────────────────────────────
            logger.info("diag_karaoke_creating_services", job_id=job_id)
            try:
                ffmpeg  = FFmpegService()
                whisper = WhisperService()
                logger.info(
                    "diag_karaoke_services_ok",
                    job_id=job_id,
                    whisper_binary=settings.WHISPER_CPP_BINARY,
                    whisper_model=str(settings.WHISPER_MODEL_PATH),
                )
            except Exception:
                logger.exception("diag_karaoke_services_failed", job_id=job_id)
                raise

            # ── 1. Load job + media, mark started ────────────────────────────
            # mark_started() calls get_by_id_with_media() which uses selectinload,
            # so job.media is fully populated before the session closes.
            # expire_on_commit=False on AsyncSessionLocal means the loaded Media
            # attributes survive outside the get_db_context block.
            # Accessing job.media after the session closes without eager loading
            # raises MissingGreenlet in SQLAlchemy async — see Bug 2.
            logger.info("diag_karaoke_entering_db_context_mark_started", job_id=job_id)
            try:
                async with get_db_context() as db:
                    logger.info(
                        "diag_karaoke_before_mark_started",
                        job_id=job_id,
                        celery_task_id=self.request.id,
                    )
                    job    = await JobService(db).mark_started(job_id, self.request.id)
                    logger.info(
                        "diag_karaoke_mark_started_returned",
                        job_id=job_id,
                        job_status=job.status,
                        job_media_id=job.media_id,
                    )
                    media  = job.media
                    params: dict = dict(job.parameters or {})
                    logger.info(
                        "diag_karaoke_media_loaded",
                        job_id=job_id,
                        media_id=media.id if media else None,
                        media_type=media.media_type if media else None,
                        media_path=media.file_path if media else None,
                        params_keys=list(params.keys()),
                    )
            except Exception as exc:
                logger.exception(
                    "diag_karaoke_mark_started_block_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                )
                raise

            # ── 2-8. Pipeline ─────────────────────────────────────────────────
            try:
                await _update_progress(job_id, 5, "Validating source")

                # ── 2. Validate media type ────────────────────────────────────
                # burn_ass() requires a video stream.  Failing here gives a clear
                # error message; failing inside FFmpeg produces an opaque
                # "no video stream" error that is harder to diagnose.
                if media.media_type != MediaType.VIDEO:
                    raise ValueError(
                        f"Karaoke pipeline requires a video file; "
                        f"source media has media_type='{media.media_type}'. "
                        "Upload a video file to use karaoke generation."
                    )

                video_path = Path(media.file_path)
                if not video_path.exists():
                    raise FileNotFoundError(f"Source video not found: {video_path}")

                logger.info(
                    "diag_karaoke_validation_passed",
                    job_id=job_id,
                    video_path=str(video_path),
                    video_size_bytes=video_path.stat().st_size,
                )

                # ── 3. Extract audio ──────────────────────────────────────────
                await _update_progress(job_id, 10, "Extracting audio from video")

                audio_path = settings.PROCESSED_DIR / f"{job_id}_audio.wav"
                logger.info(
                    "diag_karaoke_before_extract_audio",
                    job_id=job_id,
                    video_path=str(video_path),
                    audio_path=str(audio_path),
                )
                await ffmpeg.extract_audio(video_path, audio_path)
                logger.info(
                    "diag_karaoke_audio_extracted",
                    job_id=job_id,
                    audio_path=str(audio_path),
                    audio_exists=audio_path.exists(),
                )

                # ── 4. Transcribe with word-level timestamps ──────────────────
                await _update_progress(job_id, 25, "Transcribing with word-level timestamps")

                # Language may be overridden per-job via parameters["language"].
                language: Optional[str] = params.get("language") or None
                logger.info(
                    "diag_karaoke_before_transcribe",
                    job_id=job_id,
                    audio_path=str(audio_path),
                    language=language or "auto",
                    word_timestamps=True,
                )

                transcript = await whisper.transcribe(
                    audio_path=audio_path,
                    language=language,
                    word_timestamps=True,
                )

                total_words   = sum(len(seg.words) for seg in transcript.segments)
                has_words     = total_words > 0
                segment_count = len(transcript.segments)

                # Log word count regardless of value — zero words is a valid
                # (if unfortunate) outcome and should be visible in the worker log
                # so it can be distinguished from a whisper.cpp crash.
                logger.info(
                    "diag_karaoke_word_count",
                    job_id=job_id,
                    detected_language=transcript.language,
                    segment_count=segment_count,
                    word_count=total_words,
                    has_word_timestamps=has_words,
                )

                # ── 5. Generate ASS karaoke subtitle file ─────────────────────
                await _update_progress(job_id, 65, "Generating ASS karaoke subtitle file")

                ass_path    = settings.PROCESSED_DIR / f"{job_id}_karaoke.ass"
                ass_content = transcript.to_ass(
                    highlight_color=str(params.get("highlight_color", "&H0000FFFF&")),
                    base_color=str(params.get("base_color",      "&H00FFFFFF&")),
                    font_name=str(params.get("font_name",        "Arial")),
                    font_size=int(params.get("font_size",         24)),
                )
                ass_path.write_text(ass_content, encoding="utf-8")

                logger.info(
                    "diag_karaoke_ass_written",
                    job_id=job_id,
                    ass_path=str(ass_path),
                    ass_size_bytes=ass_path.stat().st_size,
                    kf_tags_present=has_words,
                )

                # ── 6. Burn ASS into video ────────────────────────────────────
                await _update_progress(job_id, 70, "Burning karaoke subtitles into video")

                output_path = settings.PROCESSED_DIR / f"{job_id}_karaoke.mp4"

                logger.info(
                    "diag_karaoke_ffmpeg_start",
                    job_id=job_id,
                    video_path=str(video_path),
                    ass_path=str(ass_path),
                    output_path=str(output_path),
                )

                await ffmpeg.burn_ass(video_path, ass_path, output_path)

                logger.info(
                    "diag_karaoke_ffmpeg_done",
                    job_id=job_id,
                    output_path=str(output_path),
                    output_exists=output_path.exists(),
                    output_size_bytes=(
                        output_path.stat().st_size if output_path.exists() else 0
                    ),
                )

                await _update_progress(job_id, 90, "Finalising")

                # ── 7. Persist result ─────────────────────────────────────────
                # word_count, segment_count, and has_word_timestamps are stored
                # now so future phases (dubbing, alignment, voice replacement,
                # lip-sync) can consume per-word timing data without re-running
                # whisper.cpp on the same media file.
                params["result_files"] = {
                    "ass":   str(ass_path),
                    "video": str(output_path),
                }
                params["detected_language"]   = transcript.language
                params["word_count"]          = total_words
                params["segment_count"]       = segment_count
                params["has_word_timestamps"] = has_words

                logger.info(
                    "diag_karaoke_persisting_completion",
                    job_id=job_id,
                    result_path=str(output_path),
                    word_count=total_words,
                    segment_count=segment_count,
                )

                async with get_db_context() as db:
                    job_svc = JobService(db)
                    await job_svc.update(job_id, parameters=params)
                    await job_svc.mark_completed(job_id, str(output_path))

                logger.info(
                    "karaoke_task_done",
                    job_id=job_id,
                    output=str(output_path),
                    word_count=total_words,
                    segment_count=segment_count,
                )
                return {
                    "job_id":        job_id,
                    "result_path":   str(output_path),
                    "ass":           str(ass_path),
                    "video":         str(output_path),
                    "word_count":    total_words,
                    "segment_count": segment_count,
                }

            except Exception as exc:
                logger.exception(
                    "karaoke_task_pipeline_failed",
                    job_id=job_id,
                    exc_type=type(exc).__name__,
                    exc_message=str(exc),
                )
                try:
                    async with get_db_context() as db:
                        await JobService(db).mark_failed(job_id, str(exc))
                except Exception as mark_failed_exc:
                    logger.exception(
                        "diag_karaoke_mark_failed_itself_failed",
                        job_id=job_id,
                        original_exc_type=type(exc).__name__,
                        mark_failed_exc_type=type(mark_failed_exc).__name__,
                    )
                raise

        except Exception as top_exc:
            logger.exception(
                "diag_karaoke_run_top_level_exception",
                job_id=job_id,
                exc_type=type(top_exc).__name__,
                exc_message=str(top_exc),
            )
            raise

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
    # voice_replacement and voice_clone are defined in JobType.ALL (models/job.py)
    # but are not yet implemented.  They are intentionally absent from _TASK_MAP.
    # Adding a task here is the only change needed to make a new job type dispatchable;
    # the API pre-flight check in jobs.py derives its allowlist from this map.
}

# Derived from _TASK_MAP so the API pre-flight check stays automatically in sync.
# Adding any future task to _TASK_MAP above immediately makes it dispatchable
# without touching the API layer.
IMPLEMENTED_JOB_TYPES: frozenset[str] = frozenset(_TASK_MAP.keys())


def dispatch_job(job_id: str, job_type: str) -> str:
    """
    Dispatch the appropriate Celery task for a given job type.
    Returns the Celery task ID.

    Raises ValueError if job_type has no registered task.  Callers should guard
    against this with IMPLEMENTED_JOB_TYPES before creating a DB record so that
    a failed dispatch cannot leave a zombie job in status=queued.
    """
    task_fn = _TASK_MAP.get(job_type)
    if task_fn is None:
        # This branch should not be reachable in normal operation because
        # create_job() in jobs.py checks IMPLEMENTED_JOB_TYPES first.
        # It is kept as a final safety net for direct/internal callers.
        raise ValueError(
            f"No Celery task registered for job_type='{job_type}'. "
            f"Implemented types: {sorted(IMPLEMENTED_JOB_TYPES)}"
        )

    result = task_fn.delay(job_id)
    logger.info("task_dispatched", job_id=job_id, job_type=job_type, celery_task_id=result.id)
    return result.id
