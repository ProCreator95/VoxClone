# Phase 2 Debug Handoff — Subtitle Generation Failure

**Date:** 2026-06-13
**Branch:** `feature/subtitle-pipeline`
**Issue:** `subtitle_generation` Celery task silently fails — job stays `queued` forever

---

## Current Failure — Detailed Description

### Symptoms

1. `POST /api/v1/jobs` with `job_type=subtitle_generation` returns `201 Created`, `status=queued`
2. Celery worker log shows the task was received:
   ```
   [INFO/ForkPoolWorker-X] Using selector: EpollSelector
   ```
3. Redis queue is consumed (task dequeued successfully)
4. After 30+ seconds, job is still:
   ```json
   { "status": "queued", "progress": 0, "started_at": null }
   ```
5. Redis progress key still shows initial value:
   ```json
   { "status": "queued", "current_step": "Queued", "progress": 0 }
   ```

### Evidence Collected

**SQLite database query:**
```bash
sqlite3 backend/voxclone.db \
  "SELECT id, status, progress, started_at, error_message FROM jobs ORDER BY created_at DESC LIMIT 3;"
```
Expected before fix:
```
<job-uuid>|queued|0||
```
`started_at` is NULL, `status` is still `queued`, `error_message` is NULL (no error stored).

**Redis query:**
```bash
redis-cli GET "job:progress:<job-uuid>"
```
Expected before fix:
```json
{"job_id": "...", "status": "queued", "progress": 0, "current_step": "Queued", "error_message": null}
```
Redis key was set when the job was created (via `JobService.create()`) and never updated — confirming `mark_started()` never completed.

**Celery worker observation:**
```bash
celery -A app.tasks.celery_app inspect active
```
Expected: empty (task completed — either success or failure — the worker moved on)

```bash
celery -A app.tasks.celery_app inspect reserved
```
Expected: empty (no tasks waiting)

The task was received, ran briefly, failed internally, and Celery marked it as FAILED — but no exception handler in the task updated the DB job status.

### Why There Is No Error in the DB

The task code structure is:

```python
def generate_subtitles_task(...):
    async def _run():
        ...
        # ← mark_started() is called HERE — OUTSIDE the try/except
        async with get_db_context() as db:
            job = await JobService(db).mark_started(job_id, ...)
            media = job.media
            params = dict(job.parameters or {})

        try:                              # ← try/except starts AFTER the block above
            await _update_progress(...)
            ...
        except Exception as exc:
            await JobService(db).mark_failed(job_id, str(exc))  # ← never reached
            raise

    return asyncio.run(_run())
```

When `mark_started()` raises (due to Redis not connected), the exception exits the `async with get_db_context()` block — rolling back the DB — then propagates to `asyncio.run()` which re-raises it. The `try/except` block is never entered, so `mark_failed()` is never called.

---

## Root Cause 1: Redis Not Connected in Celery Workers

### The Bug

```python
# app/services/redis_service.py — last line:
redis_service = RedisService()   # _client = None at creation
```

```python
# app/main.py — FastAPI lifespan:
await redis_service.connect()    # ← ONLY called here, in the FastAPI process
```

Celery workers import `redis_service` but never call `connect()`. When `mark_started()` calls `redis_service.set_progress()`, it hits:

```python
@property
def client(self) -> aioredis.Redis:
    if self._client is None:
        raise RuntimeError("RedisService not connected. Call connect() first.")
    return self._client
```

**Programmatically verified:**
```bash
cd backend && source .venv/bin/activate
python3 -c "from app.services.redis_service import redis_service; print(redis_service._client is None)"
# Output: True
```

### The Fix

Add a `worker_process_init` Celery signal handler in `app/tasks/celery_app.py`:

```python
from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    """Connect Redis in each Celery worker subprocess."""
    import asyncio
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
```

---

## Root Cause 2: SQLAlchemy Async Lazy-Loading

### The Bug

```python
# app/models/job.py:
media: Mapped["Media"] = relationship("Media", back_populates="jobs", lazy="select")
```

```python
# app/tasks/media_tasks.py — inside generate_subtitles_task:
media = job.media   # triggers lazy SELECT — not supported in async context
```

SQLAlchemy 2.x async does not support implicit lazy-loading (`lazy="select"`) — it raises `sqlalchemy.exc.MissingGreenlet` because the implicit query would need to run synchronously inside an async context.

This bug is masked by Bug 1. Once Bug 1 is fixed, if this error appears in the logs, it must be fixed next.

### The Fix

Load `media` eagerly when fetching the job in `mark_started()`:

```python
# In app/services/job_service.py — update get_by_id:
from sqlalchemy.orm import selectinload

async def get_by_id(self, job_id: str, load_media: bool = False) -> Job:
    stmt = select(Job).where(Job.id == job_id)
    if load_media:
        stmt = stmt.options(selectinload(Job.media))
    result = await self._db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(job_id)
    return job
```

Then call `await job_svc.mark_started(job_id, ..., load_media=True)` — but since `mark_started` doesn't take that param, the cleanest fix is to load media separately:

```python
async with get_db_context() as db:
    stmt = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.media))
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(job_id)
    # Now call mark_started using the already-loaded job
    job_svc = JobService(db)
    job = await job_svc.mark_started(job_id, self.request.id)
    # Access media directly — already loaded above on same session
    media = job.media
```

Actually the simplest fix for the task: load job + media in one query, then call mark_started in a second step.

---

## Diagnostic Logging Added (Already In Code)

The following diagnostic events are already instrumented and will appear in Celery logs when run with `--loglevel=info`:

### From `generate_subtitles_task`:
```
diag_task_entry
diag_creating_ffmpeg_service / diag_ffmpeg_service_ok
diag_creating_whisper_service / diag_whisper_service_ok
diag_entering_db_context_for_mark_started
diag_db_context_acquired
diag_before_mark_started
diag_mark_started_returned       ← only appears if mark_started succeeds
diag_before_job_media_access     ← only appears if mark_started succeeds
diag_job_media_access_ok         ← only appears if job.media works
diag_db_context_exiting
diag_mark_started_block_failed   ← appears when anything in the block fails
```

### From `JobService.mark_started()`:
```
diag_mark_started_entry
diag_mark_started_before_get_by_id
diag_mark_started_after_get_by_id    (includes job_status)
diag_mark_started_before_status_update
diag_mark_started_before_flush
diag_mark_started_after_flush
diag_mark_started_before_redis       (includes redis_client_is_none=True/False)
diag_mark_started_after_redis        ← only appears if Redis call succeeds
diag_mark_started_redis_failed       ← appears if Redis raises
```

### From `RedisService.set_progress()`:
```
diag_redis_set_progress_called       (DEBUG level)
diag_redis_client_is_none            (ERROR level — confirms root cause)
diag_redis_set_progress_failed       (EXCEPTION level with traceback)
```

---

## Validation After Fix

Once both bugs are fixed, the expected Celery log sequence for a successful run is:

```
diag_task_entry
diag_creating_ffmpeg_service → diag_ffmpeg_service_ok
diag_creating_whisper_service → diag_whisper_service_ok
diag_entering_db_context_for_mark_started
diag_db_context_acquired
diag_before_mark_started
  diag_mark_started_entry
  diag_mark_started_before_get_by_id
  diag_mark_started_after_get_by_id    job_status=queued
  diag_mark_started_before_status_update new_status=processing
  diag_mark_started_before_flush
  diag_mark_started_after_flush
  diag_mark_started_before_redis    redis_client_is_none=False   ← KEY LINE
  diag_mark_started_after_redis
  job_started
diag_mark_started_returned           job_status=processing
diag_before_job_media_access
diag_job_media_access_ok             media_type=video
diag_db_context_exiting
[... pipeline continues through whisper.cpp transcription ...]
subtitle_task_done                   language=en segments=N
```

And the job API should show:
```json
{
  "status": "completed",
  "progress": 100,
  "parameters": {
    "result_files": {
      "transcript": "processed/<id>_transcript.txt",
      "srt":        "processed/<id>_subtitles.srt",
      "vtt":        "processed/<id>_subtitles.vtt"
    },
    "detected_language": "en",
    "segment_count": <N>
  }
}
```
