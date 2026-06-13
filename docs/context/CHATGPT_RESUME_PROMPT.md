# ChatGPT/Cursor Resume Prompt

Paste everything below the line into a new chat to resume VoxClone development instantly.

---

---

## VoxClone — Resume Context

### What This Is

VoxClone is a Python FastAPI backend for offline AI media processing.
Stack: FastAPI · Celery · Redis · SQLite (SQLAlchemy async) · FFmpeg · whisper.cpp (C++ binary, no PyTorch).

**Repo:** `/home/shz/Documents/Mustafa projects/VoxClone`
**Branch:** `feature/subtitle-pipeline`
**Python:** 3.12.3 · **OS:** Ubuntu 24.04

### Completed (Working)

- Phase 1: Upload API, FFprobe metadata, media CRUD, job CRUD, Redis progress cache, Celery dispatch
- Phase 2 code: `WhisperService` (whisper.cpp subprocess), `generate_subtitles_task`, SRT/VTT/TXT output, subtitle download endpoints

### Current Bug: subtitle_generation task silently fails

**Symptom:** Job dispatched to Celery worker. Worker receives it. Job stays `status=queued, progress=0, started_at=null` forever. No error stored in DB.

**Root cause 1 (confirmed, not yet fixed):**

`RedisService` is a module-level singleton initialized with `_client=None`. `connect()` is called only in the FastAPI lifespan. Celery workers never call it. When `JobService.mark_started()` calls `redis_service.set_progress()`, it hits:

```python
raise RuntimeError("RedisService not connected. Call connect() first.")
```

This exception rolls back the DB transaction (job stays `queued`) and exits before the task's `try/except`, so `mark_failed()` is never called.

**Verified programmatically:**
```python
from app.services.redis_service import redis_service
print(redis_service._client is None)  # → True
```

**Root cause 2 (suspected, not yet triggered):**

`Job.media` relationship has `lazy="select"`. In SQLAlchemy 2.x async, this raises `MissingGreenlet`. Task accesses `media = job.media` immediately after `mark_started()` returns. Will surface once Bug 1 is fixed.

### Diagnostic Logging Already Added

`app/tasks/media_tasks.py`, `app/services/job_service.py`, `app/services/redis_service.py` all have `diag_*` log events. Run Celery with `--loglevel=info` to see them. Key event that confirms Bug 1: `diag_redis_client_is_none` (ERROR level).

### Key File Locations

```
backend/app/tasks/celery_app.py         ← ADD worker_process_init signal here
backend/app/tasks/media_tasks.py        ← ADD selectinload fix here
backend/app/services/redis_service.py   ← singleton definition
backend/app/services/job_service.py     ← mark_started() implementation
backend/app/services/whisper_service.py ← WhisperService (working)
backend/.env                            ← WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
backend/models/                         ← ggml-tiny.en.bin, base.en.bin, small.en.bin
```

### Fix 1 — Redis in Celery (apply first)

Add to `backend/app/tasks/celery_app.py`:

```python
from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    import asyncio
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
```

### Fix 2 — SQLAlchemy lazy-load (apply after Fix 1 if MissingGreenlet appears)

In `generate_subtitles_task` inside `backend/app/tasks/media_tasks.py`, replace:

```python
async with get_db_context() as db:
    job_svc = JobService(db)
    job = await job_svc.mark_started(job_id, self.request.id)
    media = job.media          # ← BREAKS in async
    params = dict(job.parameters or {})
```

With:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.job import Job as JobModel

async with get_db_context() as db:
    job_svc = JobService(db)
    job = await job_svc.mark_started(job_id, self.request.id)
    result = await db.execute(
        select(JobModel).where(JobModel.id == job_id).options(selectinload(JobModel.media))
    )
    job_full = result.scalar_one()
    media = job_full.media
    params = dict(job_full.parameters or {})
```

### Test After Fixes

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
redis-server --daemonize yes
uvicorn app.main:app --reload --port 8000 &
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 &

MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads -F "file=@test.mp4" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs -H "Content-Type: application/json" -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
sleep 60
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID | python3 -m json.tool
```

**Success criteria:** `status=completed`, `parameters.result_files` has 3 paths, `GET /jobs/$JOB_ID/download/srt` returns valid SRT.

### What Works Right Now (No Fixes Needed)

- `GET /health` → `{status: ok}`
- `POST /uploads` with MP4 → media created with ffprobe metadata
- `POST /jobs` → job created and dispatched (task received by worker)
- `WhisperService.validate()` → passes (binary + model present)
- `TranscriptResult.to_srt()/.to_vtt()/.to_txt()` → correct output

### Next Phase After This Is Fixed

Phase 3: Subtitle burn-in (FFmpeg hardcode SRT into video). Stub already exists in `media_tasks.py`.
