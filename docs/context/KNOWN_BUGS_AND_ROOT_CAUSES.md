# VoxClone — Known Bugs and Root Causes

**Branch:** `feature/subtitle-pipeline`
**Date documented:** 2026-06-13
**Fixes applied:** 2026-06-14 — all three bugs resolved, pipeline working

---

## Bug 1 — RedisService not connected inside Celery workers ✅ FIXED

### Symptom

After a `subtitle_generation` job is dispatched:
- Celery worker log shows `Using selector: EpollSelector` (task received)
- Redis queue is consumed (task dequeued)
- Job remains `status=queued`, `progress=0`, `started_at=NULL` indefinitely
- Redis progress key still shows `{"status": "queued", "current_step": "Queued"}`

### Evidence

**Programmatic proof (run in the venv):**
```bash
python3 -c "
from app.services.redis_service import redis_service
print('_client:', redis_service._client)
print('is None:', redis_service._client is None)
"
```
Output:
```
_client: None
is None: True
```
`redis_service._client` is `None` at module import time. It is **never** `None` inside the FastAPI process because `app/main.py` lifespan calls `await redis_service.connect()` on startup. Celery workers do not execute this lifespan.

**Code path that fails:**
```
generate_subtitles_task
  └─ async with get_db_context() as db:
       └─ JobService(db).mark_started(job_id, celery_task_id)
            ├─ get_by_id()            → OK, DB write works
            ├─ job.status = PROCESSING → OK
            ├─ await db.flush()        → OK, row updated in transaction
            └─ await redis_service.set_progress(...)
                 └─ self.client        → raises RuntimeError("not connected")
                      ↑
                      _client is None
```

**Cascade effect:**
- `RuntimeError` propagates out of `mark_started()`
- Propagates out of `async with get_db_context()`, triggering **rollback**
- DB row reverts to `status=queued` (the flush is undone)
- Exception propagates to the outer scope of `_run()` — **outside the task's try/except**
- `mark_failed()` is never called (it's inside the try/except, not the outer scope)
- Job stays `queued` forever
- Celery marks the task as FAILURE, but the job DB record never changes

**Why mark_failed() also can't save it:**  
Even if `mark_failed()` were called, it also calls `redis_service.set_progress()`, which would fail with the same `RuntimeError`.

### Affected Code

| File | Location |
|------|----------|
| `app/services/redis_service.py` | Line 99: `redis_service = RedisService()` — singleton created with `_client=None` |
| `app/main.py` | Lifespan calls `await redis_service.connect()` — only runs in FastAPI process |
| `app/services/job_service.py` | `mark_started()` — calls `redis_service.set_progress()` after DB flush |
| `app/tasks/media_tasks.py` | `generate_subtitles_task` — `mark_started()` is outside the task try/except |

### Fix Applied (`app/tasks/celery_app.py`)

```python
import asyncio
from celery.signals import worker_process_init, worker_process_shutdown

@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
    """Called inside each forked worker process."""
    setup_logging()
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
    logger.info("celery_worker_process_redis_connected")

@worker_process_shutdown.connect
def on_worker_process_shutdown(**kwargs) -> None:
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.disconnect())
    logger.info("celery_worker_process_redis_disconnected")
```

**Verification:** Celery log shows `celery_worker_process_redis_connected` once per worker process on startup.

---

## Bug 2 — SQLAlchemy async lazy-loading of `job.media` ✅ FIXED

### Symptom

If Bug 1 is fixed, the task will proceed past `mark_started()`. The next line is:

```python
media = job.media
```

This accesses the `media` relationship on the `Job` ORM object. The relationship is defined as:

```python
# app/models/job.py
media: Mapped["Media"] = relationship("Media", back_populates="jobs", lazy="select")
```

`lazy="select"` tells SQLAlchemy to issue an additional `SELECT` query when the attribute is first accessed. In the async SQLAlchemy driver, this synchronous-style implicit query is **not supported** — it raises:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

### Evidence

- SQLAlchemy 2.x async documentation explicitly states: lazy loading is not supported with `AsyncSession`. Use `selectin`, `joined`, or explicit `await session.run_sync(...)` instead.
- `job` is loaded via `select(Job).where(Job.id == job_id)` — no `.options(selectinload(...))` applied.
- `media = job.media` is the first access of this relationship inside the async context.

### Affected Code

| File | Location |
|------|----------|
| `app/models/job.py` | `lazy="select"` on `media` relationship |
| `app/services/job_service.py` | `get_by_id()` — no eager loading options |
| `app/tasks/media_tasks.py` | `media = job.media` — accesses lazy relationship |

### Fix Applied (`app/services/job_service.py`)

A new method `get_by_id_with_media` was added that uses `selectinload(Job.media)`. `mark_started` now calls this instead of `get_by_id`:

```python
from sqlalchemy.orm import selectinload

async def get_by_id_with_media(self, job_id: str) -> Job:
    result = await self._db.execute(
        select(Job)
        .options(selectinload(Job.media))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(job_id)
    logger.info("diag_job_media_preloaded",
                job_id=job_id,
                media_id=job.media.id if job.media else None,
                media_type=job.media.media_type if job.media else None)
    return job
```

`mark_started` calls `get_by_id_with_media` — so `job.media` is a plain Python attribute access from that point forward. `expire_on_commit=False` on `AsyncSessionLocal` means the `Media` object remains accessible after the session closes.

**Verification:** Celery log shows `diag_job_media_preloaded` with non-None `media_id` and `media_type`.

---

## Bug 3 — whisper.cpp shared libraries not found ✅ FIXED

### Symptom

After Bugs 1 and 2 were fixed, whisper.cpp still failed:

```
libwhisper.so.1 => not found
libggml.so.0 => not found
```

The binary at `tools/whisper.cpp/build/bin/whisper-cli` links against shared libraries in its own build tree. Without `LD_LIBRARY_PATH` pointing to those directories, the dynamic linker cannot find them.

### Affected Code

| File | Location |
|------|----------|
| `app/services/whisper_service.py` | `_run_subprocess` — `asyncio.create_subprocess_exec` called without `env=` |

### Fix Applied (`app/services/whisper_service.py`)

A new static method `_build_subprocess_env` derives the library directories from the binary path using `pathlib`, builds an env dict, and passes it to the subprocess:

```python
@staticmethod
def _build_subprocess_env(binary: str) -> dict[str, str]:
    build_dir = Path(binary).parent.parent  # .../build/bin → .../build
    whisper_lib_dir = build_dir / "src"          # libwhisper.so.1
    ggml_lib_dir    = build_dir / "ggml" / "src" # libggml.so.0

    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = (
        f"{whisper_lib_dir}:{ggml_lib_dir}"
        + (f":{existing}" if existing else "")
    )
    return env
```

`asyncio.create_subprocess_exec` now receives `env=self._build_subprocess_env(binary)`.

**Example resolved paths** (given `WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli`):
```
LD_LIBRARY_PATH=.../tools/whisper.cpp/build/src:.../tools/whisper.cpp/build/ggml/src
```

**Verification:** Celery log shows `whisper_cpp_ld_library_path` (DEBUG level) with the two paths; job reaches `subtitle_task_done`.

---

## Bug Fix Order Applied

```
Bug 1 (Redis) → Bug 2 (MissingGreenlet) → Bug 3 (LD_LIBRARY_PATH) → pipeline working
```
