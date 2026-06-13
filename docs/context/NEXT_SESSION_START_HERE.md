# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

Read this document first. Then read `KNOWN_BUGS_AND_ROOT_CAUSES.md` for code-level detail.

---

## Situation Summary

VoxClone Phase 2 subtitle pipeline is **implemented but not yet working** due to two bugs:

1. `RedisService` is not connected inside Celery worker processes → `mark_started()` always fails with `RuntimeError("not connected")`
2. `job.media` uses SQLAlchemy `lazy="select"` which is incompatible with async SQLAlchemy

Both bugs have been identified with certainty. The code is instrumented with diagnostic logging. No fix has been applied yet.

**Your job: apply both fixes, retest, confirm the pipeline produces real SRT/VTT/TXT files.**

---

## Immediate Action Checklist

### Priority 1 — Fix Redis connection in Celery worker

**File to edit:** `backend/app/tasks/celery_app.py`

**Change:** Add a `worker_process_init` signal handler:

```python
from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    import asyncio
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
```

**Verify the fix works:**
```bash
# Read the Celery worker log after restarting it
# Look for: {"event": "redis_connected", ...}
```

### Priority 2 — Retest subtitle generation

After fixing Priority 1:

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

# Start services (3 terminals)
redis-server --daemonize yes
uvicorn app.main:app --reload --port 8000
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1

# Upload any MP4 with speech
MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/video.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create subtitle job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Watch Celery log for diag_* events
# Poll until completed (max 5 min for tiny.en model)
watch -n 5 "curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/progress | python3 -m json.tool"
```

**Expected:** Job transitions `queued → processing → completed`

If it fails at `diag_before_job_media_access` with `MissingGreenlet` → proceed to Priority 3.

### Priority 3 — Fix SQLAlchemy lazy-loading (if needed)

**File to edit:** `backend/app/tasks/media_tasks.py`

Replace this block inside `generate_subtitles_task`:

```python
# BEFORE (buggy):
async with get_db_context() as db:
    job_svc = JobService(db)
    job = await job_svc.mark_started(job_id, self.request.id)
    media = job.media                   # ← lazy load FAILS in async
    params: dict = dict(job.parameters or {})
```

With:

```python
# AFTER (fixed):
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.job import Job

async with get_db_context() as db:
    job_svc = JobService(db)
    job = await job_svc.mark_started(job_id, self.request.id)

    # Eagerly load media in the same session
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.media))
    )
    job_with_media = result.scalar_one()
    media = job_with_media.media
    params: dict = dict(job_with_media.parameters or {})
```

### Priority 4 — Full pipeline validation

After both fixes, run the complete validation from `docs/testing/PHASE2_MANUAL_TESTING.md`.

Verify:
1. `GET /jobs/{id}` shows `status=completed` and `parameters.result_files` with 3 paths
2. `GET /jobs/{id}/download/srt` returns valid SRT content
3. `GET /jobs/{id}/download/vtt` starts with `WEBVTT`
4. `GET /jobs/{id}/download/transcript` returns readable text

### Priority 5 — Commit Phase 2

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone"
git add .
git commit -m "Phase 2: whisper.cpp subtitle pipeline

- WhisperService wrapping whisper.cpp CLI subprocess
- generate_subtitles_task: video → audio → whisper → SRT/VTT/TXT
- Fix: Redis connection in Celery worker via worker_process_init signal
- Fix: SQLAlchemy lazy-load replaced with selectinload(Job.media)
- Subtitle download endpoints: /jobs/{id}/download/{transcript,srt,vtt}
- Diagnostic logging on all failure paths
- Full test suite and context documentation"
git push origin feature/subtitle-pipeline
```

---

## Key Files Reference

| What you'll edit | Path |
|-----------------|------|
| Fix 1 (Redis in Celery) | `backend/app/tasks/celery_app.py` |
| Fix 2 (lazy-load) | `backend/app/tasks/media_tasks.py` |
| Whisper logic | `backend/app/services/whisper_service.py` |
| Job lifecycle | `backend/app/services/job_service.py` |
| Diagnostic logs | all three files above already instrumented |

---

## Environment Quickstart

```bash
# All commands run from:
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

# Verify whisper binary works:
../tools/whisper.cpp/build/bin/whisper-cli --version

# Verify model exists:
ls -lh models/ggml-tiny.en.bin

# Verify config:
python3 -c "
from app.core.config import get_settings
s = get_settings()
print('binary:', s.WHISPER_CPP_BINARY)
print('model:', s.WHISPER_MODEL_PATH)
print('threads:', s.WHISPER_THREADS)
"

# Verify Redis is reachable:
redis-cli ping   # → PONG

# Verify Redis singleton starts disconnected:
python3 -c "from app.services.redis_service import redis_service; print('connected:', redis_service._client is not None)"
# → connected: False   (this is the bug — should say True after the fix)
```

---

## What Is NOT Broken

- FastAPI startup and all Phase 1 endpoints work perfectly
- File upload, metadata extraction, media CRUD all work
- `whisper-cli` binary is built and functional
- All 3 Whisper models are downloaded
- `WhisperService.validate()` passes (binary + model exist)
- `TranscriptResult.to_srt()`, `.to_vtt()`, `.to_txt()` produce correct output
- Subtitle download endpoints are correctly implemented (waiting for a completed job)

---

## Next Phase After Phase 2 Is Fixed

Phase 3: **Subtitle Burn-In** — burn SRT into video via FFmpeg.
- `burn_subtitles_task` stub already exists in `media_tasks.py`
- `FFmpegService.burn_subtitles()` is already implemented
- See `docs/context/NEXT_PHASES_ROADMAP.md` for full details
