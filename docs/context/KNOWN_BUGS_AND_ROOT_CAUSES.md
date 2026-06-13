# VoxClone — Known Bugs and Root Causes

**Branch:** `feature/subtitle-pipeline`
**Date documented:** 2026-06-13
**Status:** Bugs identified, fixes not yet applied

---

## Bug 1 — RedisService not connected inside Celery workers (CRITICAL)

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

### Fix Required

Add a Celery `worker_process_init` signal handler to connect Redis in each worker process:

```python
# app/tasks/celery_app.py  — add this:
from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    import asyncio
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
```

Or — make `redis_service` lazy: auto-connect on first use instead of requiring explicit `connect()`.

---

## Bug 2 — SQLAlchemy async lazy-loading of `job.media` (SECONDARY)

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

### Fix Required

**Option A (preferred):** Eager-load `media` in `get_by_id()` when called from a task context:

```python
# In job_service.py — add an optional eager_load parameter:
from sqlalchemy.orm import selectinload

async def get_by_id(self, job_id: str, load_media: bool = False) -> Job:
    stmt = select(Job).where(Job.id == job_id)
    if load_media:
        stmt = stmt.options(selectinload(Job.media))
    result = await self._db.execute(stmt)
    ...
```

**Option B:** Change the relationship to `lazy="raise"` globally to catch all such accesses early, and use explicit `selectinload` everywhere.

**Option C (quickest):** Keep `mark_started()` as-is, but load the media in a **separate DB call** after `mark_started()` returns:

```python
async with get_db_context() as db:
    job = await JobService(db).mark_started(job_id, self.request.id)
    # Explicitly reload with media
    result = await db.execute(
        select(Job).where(Job.id == job_id).options(selectinload(Job.media))
    )
    job_with_media = result.scalar_one()
    media = job_with_media.media
    params = dict(job_with_media.parameters or {})
```

---

## Bug Order for Fixing

```
Fix Bug 1 first → retest → Bug 2 will surface if present → fix Bug 2 → retest → pipeline runs
```

Do not attempt to fix both simultaneously. Fixing one at a time allows you to verify each fix independently.

---

## Diagnostic Logging Already Added

The following diagnostic logs are already in place (added 2026-06-13):

- `app/tasks/media_tasks.py` — 13 `diag_*` checkpoints around task entry, service creation, DB context, `mark_started`, and `job.media` access
- `app/services/job_service.py` — 9 checkpoints inside `mark_started()` including `redis_client_is_none` log
- `app/services/redis_service.py` — `diag_redis_client_is_none` ERROR log when `_client is None` before `set_progress()`

Run Celery with `--loglevel=info` to see all `diag_*` events.
