# VoxClone — Master Project Handoff

**Date:** 2026-06-14  
**Branch:** `feature/subtitle-burn`  
**Commit:** `2f9f643 Phase 3: subtitle burn-in complete`  
**Tags:** `v0.1-foundation` (Phase 1) · `phase2-subtitles-working` (Phase 2) · `phase3-subtitle-burn` (Phase 3)  
**Working tree:** clean

> This document is completely self-contained. A new developer can continue
> the project using only this file.

---

## 1. Project Overview

**VoxClone** is an offline-first AI media processing platform.  
Users upload a video or audio file, choose a processing pipeline (subtitle
generation, audio extraction, voice cloning, etc.), and download the result.
All AI models run locally — no cloud API keys, no GPU required for Phase 2.

**Primary use cases (current — Phases 1–3 complete):**
- Automatic subtitle generation from any video or audio (Phase 2)
- Subtitle burn-in — hardcode subtitles into video as H.264 MP4 (Phase 3)

**Planned use cases (future phases):**
- Vocal removal / karaoke
- Audio enhancement (noise removal)
- Text-to-speech
- Voice replacement / dubbing
- Voice cloning

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT (curl / Flutter)              │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP REST
┌───────────────────────▼─────────────────────────────────┐
│                  FastAPI  (port 8000)                     │
│  POST /uploads  →  UploadService  →  FFprobe metadata    │
│  POST /jobs     →  JobService     →  Celery.delay()      │
│  GET  /jobs/{id}/progress         →  Redis cache         │
│  GET  /jobs/{id}/download/{fmt}   →  FileResponse        │
└──────────┬────────────────────────┬────────────────────-─┘
           │ SQLAlchemy async       │ redis-py async
           │ (aiosqlite)            │
    ┌──────▼──────┐          ┌──────▼──────┐
    │   SQLite    │          │    Redis     │
    │ voxclone.db │          │ :6379/0  DB  │
    │  media tbl  │          │ :6379/1  RB  │  (DB=broker, RB=result backend)
    │  jobs  tbl  │          └──────────────┘
    └─────────────┘
           │                        │
┌──────────▼────────────────────────▼─────────────────────┐
│              Celery Worker (fork pool)                    │
│                                                          │
│  queue: media  →  extract_audio_task                     │
│                →  burn_subtitles_task                    │
│                                                          │
│  queue: ai     →  generate_subtitles_task                │
│                     │                                    │
│              ┌──────▼──────────────────┐                │
│              │   FFmpegService          │                │
│              │   (extract 16kHz WAV)    │                │
│              └──────┬──────────────────┘                │
│              ┌──────▼──────────────────┐                │
│              │   WhisperService         │                │
│              │   whisper.cpp subprocess │                │
│              │   (LD_LIBRARY_PATH set)  │                │
│              └──────┬──────────────────┘                │
│                     │ TranscriptResult                   │
│                     ↓                                    │
│         .srt  .vtt  .txt  written to processed/          │
└──────────────────────────────────────────────────────────┘
```

**Data flow for subtitle generation:**
```
POST /jobs {job_type: "subtitle_generation", media_id: X}
  → job created in SQLite (status=queued)
  → Redis key set: job:progress:<id> = {status: queued, progress: 0}
  → Celery task dispatched to "ai" queue
  → Worker: mark_started() → status=processing, started_at=now
  → Worker: FFmpeg extracts 16kHz mono WAV (if video input)
  → Worker: whisper.cpp subprocess → JSON output
  → Worker: write .txt .srt .vtt to processed/
  → Worker: mark_completed() → status=completed, result_path=srt
  → GET /jobs/{id}/download/srt → FileResponse
```

---

## 3. Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12.3 |
| Web framework | FastAPI + uvicorn | latest |
| Database | SQLite via aiosqlite | — |
| ORM | SQLAlchemy | 2.x (fully async) |
| Task queue | Celery | 5.x |
| Message broker | Redis | system |
| Progress cache | Redis | same instance |
| Speech recognition | whisper.cpp (CLI binary) | built from source |
| Media processing | FFmpeg | 6.1.1 (system) |
| Logging | structlog | JSON format |
| Settings | pydantic-settings | .env file |
| OS | Ubuntu 24.04.2 LTS | — |

---

## 4. Repository Layout

```
VoxClone/
├── backend/                         ← all Python code
│   ├── app/
│   │   ├── main.py                  FastAPI app factory + lifespan
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       ├── health.py        GET /health
│   │   │       ├── uploads.py       POST /uploads
│   │   │       ├── media.py         GET /media, /media/{id}
│   │   │       └── jobs.py          POST/GET /jobs + download endpoints
│   │   ├── core/
│   │   │   ├── config.py            All settings (pydantic-settings)
│   │   │   ├── exceptions.py        Domain exceptions + FastAPI handlers
│   │   │   └── logging.py           structlog JSON setup
│   │   ├── database/
│   │   │   ├── session.py           Async engine + get_db_context()
│   │   │   └── init_db.py           create_tables() on startup
│   │   ├── models/
│   │   │   ├── media.py             Media SQLAlchemy model
│   │   │   └── job.py               Job model + JobType + JobStatus
│   │   ├── schemas/
│   │   │   ├── job.py               JobCreate, JobResponse
│   │   │   └── media.py             MediaResponse
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py    FFmpeg wrapper (probe, extract, burn)
│   │   │   ├── job_service.py       Job CRUD + lifecycle
│   │   │   ├── media_service.py     Media CRUD
│   │   │   ├── redis_service.py     Redis singleton + progress cache
│   │   │   ├── upload_service.py    File ingestion pipeline
│   │   │   └── whisper_service.py   whisper.cpp subprocess wrapper
│   │   └── tasks/
│   │       ├── celery_app.py        Celery config + worker_process_init hook
│   │       └── media_tasks.py       All Celery task implementations
│   ├── uploads/                     Uploaded media files
│   ├── processed/                   Pipeline output files
│   ├── models/                      GGML model files
│   │   ├── ggml-tiny.en.bin         75 MB  (active default)
│   │   ├── ggml-base.en.bin         142 MB
│   │   └── ggml-small.en.bin        466 MB
│   ├── .env                         Active configuration
│   ├── .env.example                 Configuration template
│   └── requirements.txt
├── tools/
│   └── whisper.cpp/                 whisper.cpp source + build output
│       └── build/
│           ├── bin/whisper-cli      975 KB binary
│           ├── src/                 libwhisper.so.1
│           └── ggml/src/            libggml.so.0
└── docs/
    ├── context/                     Project state docs (← you are here)
    ├── testing/                     Test plans and setup guides
    └── reports/                     Phase completion reports
```

---

## 5. Environment Configuration (`.env`)

```bash
# ── Application ────────────────────────────────────────
APP_NAME=VoxClone
APP_VERSION=0.1.0
DEBUG=false

# ── Database ───────────────────────────────────────────
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db

# ── Redis ──────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Celery ─────────────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ── File storage ───────────────────────────────────────
UPLOAD_DIR=uploads
PROCESSED_DIR=processed

# ── FFmpeg ─────────────────────────────────────────────
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe

# ── Whisper (whisper.cpp — NO Python ML dependencies) ──
WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_THREADS=8
WHISPER_LANGUAGE=en
```

> **Note:** `WHISPER_CPP_BINARY` is a path relative to `backend/` (the cwd when
> running uvicorn and celery). The binary is resolved to an absolute path by
> `_resolve_binary()` in `whisper_service.py` before any subprocess call.

---

## 6. Startup Commands

All commands run from `backend/` with the venv activated.

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
```

### Terminal 1 — Redis

```bash
redis-server --daemonize yes
redis-cli ping   # → PONG
```

### Terminal 2 — FastAPI

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

FastAPI startup connects Redis and creates DB tables via the lifespan hook.  
API docs: http://localhost:8000/docs

### Terminal 3 — Celery Worker

```bash
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai \
  --concurrency 2 \
  --loglevel INFO
```

**Both queues are required.** `generate_subtitles_task` routes to `ai`,
`extract_audio_task` and `burn_subtitles_task` route to `media`.  
Without `--queues media,ai` those tasks will never be picked up.

**Expected startup log lines:**
```
celery_worker_process_redis_connected    ← once per worker process
celery_worker_ready
```

---

## 7. Current API Endpoints

Base URL: `http://localhost:8000/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health (DB + Redis ping) |
| POST | `/uploads` | Upload video/audio (multipart/form-data) |
| GET | `/media` | List all uploaded media |
| GET | `/media/{id}` | Media metadata + ffprobe info |
| DELETE | `/media/{id}` | Delete media and associated jobs |
| POST | `/jobs` | Create and dispatch a processing job |
| GET | `/jobs/{id}` | Job status, progress, result paths |
| GET | `/jobs/{id}/progress` | Live progress from Redis (low latency) |
| GET | `/jobs/{id}/result` | Download primary output file |
| GET | `/jobs/{id}/download/transcript` | Download .txt transcript (subtitle jobs) |
| GET | `/jobs/{id}/download/srt` | Download .srt subtitle file |
| GET | `/jobs/{id}/download/vtt` | Download .vtt subtitle file |
| DELETE | `/jobs/{id}` | Cancel an active job |

### Job creation payload

```json
POST /api/v1/jobs
{
  "media_id": "<uuid from /uploads>",
  "job_type": "subtitle_generation",
  "parameters": {
    "language": "en"
  }
}
```

Valid `job_type` values: `audio_extraction`, `subtitle_generation`,
`subtitle_burn`, `karaoke`, `audio_enhance`, `voice_replacement`, `voice_clone`

---

## 8. Database Schema

**No Alembic** — `create_all` on startup. Two tables:

### `media`

| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| filename | String(255) | stored filename |
| original_name | String(255) | user-provided filename |
| file_path | String(512) | absolute path on disk |
| file_size | Integer | bytes |
| mime_type | String(100) | e.g. `video/mp4` |
| media_type | String(20) | `video` or `audio` |
| duration | Float | seconds (from ffprobe) |
| format | String(50) | container format |
| width, height | Integer | video dimensions |
| codec_video, codec_audio | String(50) | |
| created_at, updated_at | DateTime(tz) | |

### `jobs`

| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| media_id | String(36) FK | → media.id CASCADE DELETE |
| job_type | String(50) | e.g. `subtitle_generation` |
| status | String(20) | queued/processing/completed/failed/cancelled |
| progress | Integer | 0–100 |
| current_step | String(255) | human-readable step name |
| result_path | String(512) | primary output file path |
| error_message | Text | populated on failure |
| parameters | JSON | input params + result_files after completion |
| celery_task_id | String(255) | Celery task UUID |
| started_at, completed_at | DateTime(tz) | |

**Subtitle job `parameters` after completion:**
```json
{
  "language": "en",
  "result_files": {
    "transcript": "/abs/path/processed/<id>_transcript.txt",
    "srt":        "/abs/path/processed/<id>_subtitles.srt",
    "vtt":        "/abs/path/processed/<id>_subtitles.vtt"
  },
  "detected_language": "en",
  "segment_count": 42
}
```

---

## 9. Completed Phases

### Phase 1 — Backend Foundation ✅ COMPLETE

- FastAPI app factory with lifespan (Redis connect/disconnect, DB create)
- SQLite + async SQLAlchemy ORM (Media + Job models)
- File upload endpoint with ffprobe metadata extraction
- Media CRUD endpoints
- Job creation, dispatch, status polling
- Redis progress cache (`job:progress:<id>` keys, 24h TTL)
- Celery task dispatch (task routing to named queues)
- structlog JSON logging throughout

### Phase 2 — Whisper Subtitle Pipeline ✅ COMPLETE

- `WhisperService` — wraps whisper.cpp CLI as an async subprocess
  - `_resolve_binary()` — resolves binary name/path, validates executable
  - `_build_subprocess_env()` — derives `LD_LIBRARY_PATH` from binary path
  - `transcribe(audio_path, language) → TranscriptResult`
  - `TranscriptResult.to_srt()`, `.to_vtt()`, `.to_txt()`
  - JSON output parser (handles two whisper.cpp JSON layouts)
- `generate_subtitles_task` — full pipeline: load job → extract audio → transcribe → write files → persist
- Subtitle download endpoints: `/jobs/{id}/download/{transcript,srt,vtt}`
- Comprehensive diagnostic logging (`diag_*` events) throughout task and services

**Three bugs diagnosed and fixed:**

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 1 | Redis not connected in Celery worker | `redis_service.connect()` only called in FastAPI lifespan; workers fork without it | `worker_process_init` signal in `celery_app.py` |
| 2 | `MissingGreenlet` on `job.media` | `lazy="select"` relationship triggers implicit SQL in async context | `get_by_id_with_media()` using `selectinload(Job.media)` |
| 3 | `libwhisper.so.1 not found` | whisper.cpp shared libs not on `LD_LIBRARY_PATH` | `_build_subprocess_env()` prepends build dirs |

### Phase 3 — Subtitle Burn-In ✅ COMPLETE

- `FFmpegService._escape_filter_path()` — escapes `\`, `:`, `'` in file paths before embedding in FFmpeg filter strings (required because project path contains a space)
- Rewrote `FFmpegService.burn_subtitles()` — explicit H.264 output (`-c:v libx264 -crf 23 -preset fast`), `libass` subtitle filter, optional style parameters (`font_name`, `font_size`, `font_color`, `outline_color`)
- Full `burn_subtitles_task` implementation:
  - **Primary workflow:** `subtitle_job_id` in parameters → look up prior job's `parameters["result_files"]["srt"]` automatically
  - **Testing mode:** `srt_path` in parameters → use path directly
  - Media type validation (rejects audio-only files with clear error)
  - File existence validation for both video and SRT before FFmpeg call
  - 16 `diag_burn_*` diagnostic events at every major step
  - `parameters["result_files"]["burned_video"]` written on completion
  - `parameters["subtitle_job_id"]` preserved in burn job record for traceability
- `GET /jobs/{id}/download/video` — typed MP4 download endpoint

**Two bugs diagnosed and fixed in Phase 3:**

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 4 | FFmpeg filter path corruption | `subtitles=<path>:force_style=...` — `:` in path breaks filter option parsing | `_escape_filter_path()` escapes `\`, `:`, `'` in `ffmpeg_service.py` |
| 5 | Undefined output codec | No `-c:v` flag — FFmpeg defaulted to `mpeg4` for `.mp4` output | Added `-c:v libx264 -crf 23 -preset fast` to burn command |

---

## 10. Exact Fixes Applied (Code Level)

### Fix 1 — `backend/app/tasks/celery_app.py`

Added `worker_process_init` and `worker_process_shutdown` signal handlers:

```python
import asyncio
from celery.signals import worker_process_init, worker_process_shutdown

@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
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

**Why `worker_process_init` and not `worker_ready`:**  
`worker_ready` fires in the parent supervisor process. `worker_process_init`
fires inside each **forked child process** — where tasks actually execute.

### Fix 2 — `backend/app/services/job_service.py`

Added `get_by_id_with_media()` and updated `mark_started` to call it:

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

# mark_started now calls:
job = await self.get_by_id_with_media(job_id)
```

`expire_on_commit=False` is already set on `AsyncSessionLocal`, so the
pre-loaded `Media` object remains accessible after the session closes.

### Fix 3 — `backend/app/services/whisper_service.py`

Added `_build_subprocess_env()` and passed `env=` to the subprocess:

```python
@staticmethod
def _build_subprocess_env(binary: str) -> dict[str, str]:
    build_dir       = Path(binary).parent.parent     # .../build/bin → .../build
    whisper_lib_dir = build_dir / "src"              # libwhisper.so.1
    ggml_lib_dir    = build_dir / "ggml" / "src"     # libggml.so.0

    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = (
        f"{whisper_lib_dir}:{ggml_lib_dir}"
        + (f":{existing}" if existing else "")
    )
    return env

# In _run_subprocess:
env = self._build_subprocess_env(binary)
process = await asyncio.create_subprocess_exec(*cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env=env,
)
```

### Additional — `backend/app/database/session.py`

`get_db_context()` now logs every rollback event for diagnostics:

```python
except Exception as _rollback_exc:
    _diag_logger.exception(
        "diag_db_context_rollback",
        exc_type=type(_rollback_exc).__name__,
        exc_message=str(_rollback_exc),
    )
    await session.rollback()
    raise
```

---

## 10b. Phase 3 Exact Fixes (Code Level)

### Fix 4 — `backend/app/services/ffmpeg_service.py`

Added `_escape_filter_path()` static method and rewrote `burn_subtitles()`:

```python
@staticmethod
def _escape_filter_path(path: Path) -> str:
    s = str(path)
    s = s.replace("\\", "\\\\")  # must come first
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s

async def burn_subtitles(
    self,
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    font_size: int = 24,
    font_name: str = "Arial",
    font_color: str = "&H00FFFFFF&",
    outline_color: str = "&H00000000&",
) -> None:
    escaped = self._escape_filter_path(srt_path)
    force_style = (
        f"FontName={font_name},FontSize={font_size},"
        f"PrimaryColour={font_color},OutlineColour={outline_color},"
        f"Outline=1,Shadow=0"
    )
    subtitle_filter = f"subtitles={escaped}:force_style='{force_style}'"
    cmd = [
        self.ffmpeg, "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy", "-y", str(output_path),
    ]
```

### Fix 5 — `backend/app/tasks/media_tasks.py`

`burn_subtitles_task` was replaced entirely.  Key additions over the old stub:

```python
# SRT resolution — primary workflow
if subtitle_job_id:
    async with get_db_context() as db:
        prior_job = await JobService(db).get_by_id(subtitle_job_id)
    # validate status == COMPLETED and job_type == SUBTITLE_GENERATION
    srt_path = Path(prior_job.parameters["result_files"]["srt"])
    params["subtitle_job_id"] = subtitle_job_id  # preserve for traceability

# Validation gates
if media.media_type != MediaType.VIDEO:
    raise ValueError(f"Subtitle burn requires a video file; got '{media.media_type}'")
if not video_path.exists():
    raise FileNotFoundError(...)
if not srt_path.exists():
    raise FileNotFoundError(...)

# Persist result_files (matches generate_subtitles_task pattern)
params["result_files"] = {"burned_video": str(output_path)}
async with get_db_context() as db:
    await job_svc.update(job_id, parameters=params)
    await job_svc.mark_completed(job_id, str(output_path))
```

### New endpoint — `backend/app/api/v1/endpoints/jobs.py`

```python
@router.get("/{job_id}/download/video")
async def download_burned_video(job_id: str, ...) -> FileResponse:
    # validates job_type == SUBTITLE_BURN and status == COMPLETED
    # reads parameters["result_files"]["burned_video"]
    # falls back to job.result_path for backward compatibility
    return FileResponse(path=..., filename=f"{job_id}_subtitled.mp4", media_type="video/mp4")
```

---

## 11. Known Pitfalls for the Next Developer

### Celery queue names are mandatory

Tasks are routed to named queues (`media`, `ai`). If Celery is started without
`--queues media,ai`, subtitle and audio tasks will queue up and never execute.
Default queue (`celery`) will receive nothing.

### whisper.cpp shared libraries must be on LD_LIBRARY_PATH

The `_build_subprocess_env()` method handles this automatically **only when
`WHISPER_CPP_BINARY` points into the whisper.cpp build tree** (i.e. the binary
is inside a `<build>/bin/` directory with `<build>/src/` and
`<build>/ggml/src/` siblings). If you move the binary or install it system-wide
via `make install`, `LD_LIBRARY_PATH` may not be needed (if `ldconfig` was run)
or may need manual configuration.

### SQLAlchemy async + lazy loading

**Never** access `job.media`, `media.jobs`, or any other `lazy="select"`
relationship inside an async Celery task without first loading it with
`selectinload`. The model still has `lazy="select"` intentionally (FastAPI
routes can use it via the greenlet context). In Celery tasks, always use
`get_by_id_with_media()` or an explicit `selectinload`.

### Redis connect is per-process, not per-task

`worker_process_init` fires once per forked worker process. The Redis
connection is then shared across all tasks that run in that process. This is
correct — `redis.asyncio.Redis` is connection-pool-based and handles
concurrency internally.

### FastAPI route declaration order is significant

FastAPI matches routes **in the order they are registered**. Literal path
segments (e.g. `/download/video`) MUST be declared before parameterised
segments (e.g. `/download/{format_type}`). If the parameterised route comes
first, the literal segment is captured as the parameter value and validated
against the type annotation, causing a 422 before the correct handler is
reached.

This bit us in Phase 3 (Bug 6): `/{job_id}/download/video` was placed after
`/{job_id}/download/{format_type}` and was therefore unreachable. The fix was
to declare `download_burned_video` before `download_subtitle_format` in
`jobs.py`. A guard comment now marks this ordering as intentional.

### No Alembic — schema changes require manual migration

DB schema is created via `create_all` on startup. Adding a column to an
existing DB requires either dropping and recreating, or a manual `ALTER TABLE`
SQL statement. Alembic migration is planned for Phase 12.

### SQLite is not suitable for production concurrent writes

For local development with a single Celery worker and low concurrency, SQLite
is fine. For production or multi-worker setups, migrate to PostgreSQL.

### Celery task retry on transient failures

Tasks use `task_acks_late=True` and `worker_prefetch_multiplier=1`. If a task
crashes mid-execution, it will be re-queued. `mark_started()` will raise
`JobConflictError` ("cannot start job in status 'processing'") on retry.
This is currently unhandled — re-queued tasks after a partial execution will
fail with a conflict error.

---

## 12. Testing Commands

### Health check

```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
# Expected: {"status": "ok", "database": "ok", "redis": "ok"}
```

### Verify Celery task registration

```bash
cd backend && source .venv/bin/activate
python3 -c "
from app.tasks.media_tasks import _TASK_MAP
for k, v in _TASK_MAP.items():
    print(f'{k}: {v.name}')
"
```

### Verify whisper.cpp binary and libraries

```bash
cd backend
# Binary executes:
../tools/whisper.cpp/build/bin/whisper-cli --version

# Libraries resolved:
ldd ../tools/whisper.cpp/build/bin/whisper-cli | grep -E "whisper|ggml"

# With correct LD_LIBRARY_PATH:
LD_LIBRARY_PATH=../tools/whisper.cpp/build/src:../tools/whisper.cpp/build/ggml/src \
  ldd ../tools/whisper.cpp/build/bin/whisper-cli | grep -E "whisper|ggml"
```

### Full subtitle pipeline test

```bash
cd backend && source .venv/bin/activate

# Upload
MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/video.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Submit subtitle job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Job ID: $JOB_ID"

# Poll progress (poll every 5s until completed or failed)
until curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status']); exit(0 if d['status'] in ('completed','failed') else 1)" 2>/dev/null
do sleep 5; done

# Inspect final job state
curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID" | python3 -m json.tool

# Download results
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/vtt"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/transcript"

# Verify Redis progress key
redis-cli GET "job:progress:$JOB_ID"

# Verify SQLite row
sqlite3 voxclone.db \
  "SELECT id, status, progress, started_at, completed_at FROM jobs WHERE id='$JOB_ID';"
```

**Success criteria:**
- `status = completed`
- `progress = 100`
- `started_at` is not NULL
- `parameters.result_files` has 3 paths
- `.srt` file starts with `1\n00:00:` (valid SubRip)
- `.vtt` file starts with `WEBVTT`
- `.txt` file contains readable transcribed text

### Phase 3 subtitle burn test

```bash
# Prerequisite: a completed subtitle_generation job
MEDIA_ID="da763e0f-57f6-4317-b83d-b926fe25fb21"
SUBTITLE_JOB_ID="ac849d78-fe28-4448-b029-a5c79a83ef94"

# Submit burn job
BURN_JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_burn\",\
\"parameters\":{\"subtitle_job_id\":\"$SUBTITLE_JOB_ID\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Burn job: $BURN_JOB_ID"

# Poll until terminal
until curl -s "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/progress" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d['status'], d.get('progress'), d.get('current_step'))
exit(0 if d['status'] in ('completed','failed') else 1)
" 2>/dev/null; do sleep 3; done

# Inspect job record
curl -s "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID" | python3 -m json.tool

# Download via generic route
curl -O -J "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/result"

# Download via typed route
curl -O -J "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/download/video"

# Verify output
ffprobe "processed/${BURN_JOB_ID}_subtitled.mp4" 2>&1 | grep -E "Duration|Video:|Audio:"
# Expected: Video: h264 ... Audio: opus
```

**Phase 3 success criteria:**
- `status = completed`, `progress = 100`
- `result_path` ends in `_subtitled.mp4`
- `parameters.result_files.burned_video` equals `result_path`
- `parameters.subtitle_job_id` matches `$SUBTITLE_JOB_ID`
- `GET /download/video` returns HTTP 200, `Content-Type: video/mp4`
- `ffprobe` Video stream: `h264`
- `ffprobe` Audio stream: `opus` (stream-copied)
- Subtitles are visibly hardcoded when played

---

## 13. Remaining Roadmap

### Phase 3 — Subtitle Burn-In ✅ COMPLETE

Implemented in commit `2f9f643`, tag `phase3-subtitle-burn`.
See sections 9 and 10b for full details.

### Phase 4 — Karaoke Generation (next recommended task)

**What:** Produce karaoke-style videos where each word is highlighted in sync with speech.

**Status:** `karaoke_task` stub exists in `media_tasks.py` (currently marks failed immediately).
No new dependencies required — uses whisper.cpp word timestamps and FFmpeg ASS filter.

**Implementation steps:**
1. Add `word_timestamps: bool = False` param to `WhisperService.transcribe()` — pass `--word-timestamps` to whisper.cpp CLI when true
2. Add `TranscriptResult.to_ass()` — generate Advanced SubStation Alpha format with per-word highlight style blocks
3. Implement `karaoke_task` in `media_tasks.py`:
   - Same pipeline as `generate_subtitles_task` but with word-timestamps enabled
   - Generate `.ass` file instead of `.srt`
   - Burn `.ass` into video via FFmpeg `subtitles=` filter (same path-escaping as Phase 3)
4. Add `GET /jobs/{id}/download/ass` endpoint
5. Re-use `GET /jobs/{id}/download/video` pattern for the output MP4

**See section 18 ("How to Start Phase 4") for full architectural details.**

### Phase 5 — Audio Enhancement

Noise removal and audio clarity improvement via DeepFilterNet.
Requires `pip install deepfilternet` + PyTorch CPU.
`audio_enhance_task` stub exists.

### Phase 6 — Vocal Removal

Separate vocals from music using Demucs (music source separation).
Requires `pip install demucs` + PyTorch.
`karaoke_task` stub exists — rename to `vocal_removal_task` or add a separate task.

### Phase 7 — Text-to-Speech (Piper)

Local TTS via Piper TTS. No source media needed — `media_id` may be nullable or point to a reference audio file.

### Phase 8 — Voice Replacement

Combines Phase 2 (transcript) + Phase 7 (TTS) + FFmpeg (audio track replacement).
Transcribe → generate new speech → replace audio stream in original video.

### Phase 9+ — Voice Cloning (OpenVoice)

Clone a speaker's voice from a reference clip. GPU strongly recommended.
`voice_clone_task` stub exists.

### Phase 10 — Flutter Frontend

Mobile + desktop UI. All Phase 1–9 APIs must be stable first.

### Phase 11 — Production Hardening

PostgreSQL + Alembic migrations, authentication, Docker Compose, GPU support, monitoring.

---

## 14. Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Alembic migrations | High | Currently `create_all` — no schema evolution |
| Automated test suite | High | Zero pytest tests currently |
| API authentication | High | All endpoints open — no auth |
| PostgreSQL support | Medium | SQLite unsuitable for production |
| WebSocket progress | Medium | Current polling wastes connections |
| File cleanup | Medium | `processed/` and `uploads/` accumulate indefinitely |
| Task retry on conflict | Medium | Re-queued tasks fail with `JobConflictError` |
| GPU task routing | Low | GPU tasks need separate Celery queues/pools |

---

## 15. Git Reference

```bash
# Current state
git log --oneline -5
# 2f9f643 Phase 3: subtitle burn-in complete   ← HEAD
# 19f8cc8 Finalize Phase 2 documentation and handoff
# 94f77e0 Phase 2 subtitle generation complete
# 52c5d3e Phase 1 foundation validated

git tag
# phase3-subtitle-burn      ← Phase 3 complete (current HEAD)
# phase2-subtitles-working  ← Phase 2 complete
# v0.1-foundation           ← Phase 1 complete

# Safe rollback points
git checkout v0.1-foundation           # Phase 1 only — no subtitle pipeline
git checkout phase2-subtitles-working  # Phase 2 complete — subtitles working
git checkout phase3-subtitle-burn      # Phase 3 complete — burn-in working (current)

# To commit Phase 4 work
git add .
git commit -m "Phase 4: karaoke generation

- Word-level timestamps via whisper.cpp --word-timestamps
- TranscriptResult.to_ass() for ASS subtitle format
- karaoke_task with word-highlight burn-in
- GET /jobs/{id}/download/ass endpoint"
git tag -a phase4-karaoke -m "Phase 4: karaoke generation"
```

---

## 16. Key Files Quick Reference

| File | What it does |
|------|-------------|
| `app/main.py` | FastAPI factory; lifespan connects Redis, creates tables |
| `app/core/config.py` | All env-var settings via pydantic-settings |
| `app/models/job.py` | Job DB model; `lazy="select"` on media relationship |
| `app/models/media.py` | Media DB model |
| `app/database/session.py` | `get_db_context()` — async context manager for Celery tasks |
| `app/services/job_service.py` | `get_by_id_with_media()` — always use in Celery tasks |
| `app/services/whisper_service.py` | `_build_subprocess_env()` — sets `LD_LIBRARY_PATH` |
| `app/services/ffmpeg_service.py` | `_escape_filter_path()`, `extract_audio()`, `burn_subtitles()`, `probe()` |
| `app/services/redis_service.py` | Module-level singleton; connect via `worker_process_init` |
| `app/tasks/celery_app.py` | `worker_process_init` hook — connects Redis in each worker |
| `app/tasks/media_tasks.py` | All task implementations; Phases 1–3 complete, Phases 4+ stubbed |
| `app/api/v1/endpoints/jobs.py` | All job endpoints including `download/video` (Phase 3) |

---

## 17. Phase 2 Validation Evidence

The subtitle pipeline was validated end-to-end on 2026-06-14.  
Tag: `phase2-subtitles-working` · Commit: `94f77e0`

### Successful run identifiers

| Field | Value |
|-------|-------|
| Media ID | `da763e0f-57f6-4317-b83d-b926fe25fb21` |
| Job ID | `ac849d78-fe28-4448-b029-a5c79a83ef94` |
| Final status | `completed` |
| Progress | `100` |
| Detected language | `en` |
| Segment count | `112` |

### Generated output files

```
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_transcript.txt
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.srt
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.vtt
```

### Verified components

| Component | Verified |
|-----------|---------|
| FastAPI upload endpoint (`POST /uploads`) | ✅ |
| SQLite persistence (media + job rows) | ✅ |
| Redis progress tracking (`job:progress:<id>`) | ✅ |
| Celery task dispatch (task routed to `ai` queue) | ✅ |
| Celery worker execution (task picked up and run) | ✅ |
| FFmpeg audio extraction (video → 16kHz mono WAV) | ✅ |
| whisper.cpp transcription (WAV → JSON segments) | ✅ |
| Transcript generation (`_transcript.txt`) | ✅ |
| SRT generation (`_subtitles.srt`) | ✅ |
| VTT generation (`_subtitles.vtt`) | ✅ |
| Job completion tracking (`started_at`, `completed_at` populated) | ✅ |
| Download-ready output artifacts (`GET /jobs/{id}/download/*`) | ✅ |

### Three bugs that had to be fixed before this run succeeded

**Bug 1 — Redis singleton not connected in Celery worker processes**

`redis_service.connect()` is called only in the FastAPI lifespan. Celery
workers fork a new process and never execute that lifespan. Every call to
`redis_service.set_progress()` inside the worker raised
`RuntimeError("RedisService not connected")`, which rolled back the DB
transaction and left every job stuck at `status=queued` forever.

Fix: `worker_process_init` signal in `celery_app.py` calls
`asyncio.run(redis_service.connect())` once per forked worker process.

**Bug 2 — SQLAlchemy `MissingGreenlet` caused by lazy-loaded `job.media`**

`Job.media` is defined with `lazy="select"`. In SQLAlchemy 2.x async, implicit
lazy-loading raises `MissingGreenlet: greenlet_spawn has not been called` because
the implicit SELECT has nowhere to `await`. This surfaced immediately after Bug 1
was fixed — the first line after `mark_started()` was `media = job.media`.

Fix: `get_by_id_with_media()` in `job_service.py` uses
`select(Job).options(selectinload(Job.media))` so `media` is fully populated
in the same async query. `mark_started()` now calls this instead of `get_by_id()`.

**Bug 3 — whisper.cpp shared libraries not found (`LD_LIBRARY_PATH` issue)**

The `whisper-cli` binary links against `libwhisper.so.1` and `libggml.so.0`
which live in the whisper.cpp build tree (`build/src/` and `build/ggml/src/`).
Without those directories on `LD_LIBRARY_PATH`, the dynamic linker reports
`not found` and the subprocess exits with a non-zero code before transcribing
anything.

Fix: `_build_subprocess_env()` in `whisper_service.py` derives both library
directories from the binary path using `pathlib` and prepends them to
`LD_LIBRARY_PATH` in the subprocess environment. No hardcoded paths — works
for any whisper.cpp build tree location.

---

---

## 18. Phase 3 Validation Evidence

The subtitle burn-in pipeline was validated end-to-end on 2026-06-14.  
Tag: `phase3-subtitle-burn` · Commit: `2f9f643`

### Run identifiers

| Field | Value |
|-------|-------|
| Media ID | `da763e0f-57f6-4317-b83d-b926fe25fb21` |
| Subtitle generation job ID | `ac849d78-fe28-4448-b029-a5c79a83ef94` |
| Subtitle burn job ID | `c4263f06-ef6d-4005-91e8-d422fb00be26` |
| Burn job final status | `completed` |
| Burn job final progress | `100` |

### Generated output files

```
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_transcript.txt
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.srt
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.vtt
processed/c4263f06-ef6d-4005-91e8-d422fb00be26_subtitled.mp4   ← Phase 3 output
```

### Verified components

| Component | Verified |
|-----------|---------|
| `subtitle_job_id` → SRT resolution from prior job | ✅ |
| Media type validation (VIDEO required) | ✅ |
| Source video file existence check | ✅ |
| SRT file existence check | ✅ |
| FFmpeg path escaping (`_escape_filter_path`) | ✅ |
| H.264 video re-encode (`-c:v libx264 -crf 23`) | ✅ |
| Audio stream-copy (no re-encode) | ✅ |
| `parameters.result_files.burned_video` written | ✅ |
| `parameters.subtitle_job_id` preserved | ✅ |
| `GET /jobs/{id}/result` serves burned MP4 | ✅ |
| `GET /jobs/{id}/download/video` serves burned MP4 | ✅ |

### FFprobe validation

```
ffprobe processed/c4263f06-ef6d-4005-91e8-d422fb00be26_subtitled.mp4

Video: h264 (High), yuv420p  — subtitles hardcoded into video stream
Audio: opus                   — stream-copied from source, not re-encoded
```

### Two bugs fixed before this run succeeded

**Bug 4 — FFmpeg filter path not escaped**

The project lives at a path containing a space (`Mustafa projects`). The
`subtitles=` filter string is parsed by FFmpeg's filtergraph engine, which uses
`:` as an option delimiter. Without escaping, any special character in the path
silently corrupts the filter expression, causing either a filter parse error or
no subtitles being rendered.

Fix: `_escape_filter_path()` in `ffmpeg_service.py` escapes `\` → `\\`,
`:` → `\:`, `'` → `\'` before path is embedded in the filter string.

**Bug 5 — No explicit video codec**

Without `-c:v`, FFmpeg defaults to `mpeg4` for `.mp4` output.
`mpeg4` produces lower-quality output and may not be supported by all players.

Fix: Added `-c:v libx264 -crf 23 -preset fast` to the burn command.
`ffprobe` confirms `Video: h264 (High)` on the output file.

---

## 19. How to Start Phase 4 — Karaoke Generation

### What karaoke generation produces

A video where each word is highlighted (changes colour) at the exact moment it
is spoken — the same visual effect as karaoke machines. The underlying format is
ASS (Advanced SubStation Alpha), which supports per-word style overrides that
the simpler SRT/VTT formats do not.

### Required architecture changes

#### A. `WhisperService.transcribe()` — add word-level timestamps

whisper.cpp supports word-level timestamps via the `--word-timestamps` flag.
When enabled, each segment's JSON output includes a `words` array:

```json
{
  "segments": [{
    "text": "Hello world",
    "start": 0.0, "end": 1.2,
    "words": [
      {"word": "Hello", "start": 0.0, "end": 0.6},
      {"word": "world", "start": 0.7, "end": 1.2}
    ]
  }]
}
```

Change required in `whisper_service.py`:
```python
async def transcribe(
    self,
    audio_path: Path,
    language: Optional[str] = None,
    word_timestamps: bool = False,   # ← new param
) -> TranscriptResult:
    if word_timestamps:
        cmd.append("--word-timestamps")
        cmd.append("true")
```

`TranscriptResult` needs a `words` field per segment:
```python
@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float

@dataclass
class Segment:
    ...
    words: list[WordTimestamp] = field(default_factory=list)
```

#### B. `TranscriptResult.to_ass()` — generate ASS subtitle format

ASS format supports inline style overrides. The karaoke effect uses `{\1c&H<colour>&}` tags to change the primary colour of individual words.

Example ASS karaoke line:
```
Dialogue: 0,0:00:00.00,0:00:01.20,Default,,0,0,0,,{\1c&H0000FF&}Hello {\1c&HFFFFFF&}world
```

The `to_ass()` method iterates over segments, and within each segment iterates
over word timestamps, emitting one `Dialogue` line per segment where each word
is wrapped in a colour override that fires at word start time.

#### C. `karaoke_task` in `media_tasks.py`

Full replacement of the current stub. Pipeline:

```
1. mark_started()
2. update_progress(10, "Extracting audio")
3. FFmpegService.extract_audio()       — same as Phase 2
4. update_progress(25, "Transcribing with word timestamps")
5. WhisperService.transcribe(word_timestamps=True)
6. update_progress(70, "Generating ASS subtitle file")
7. TranscriptResult.to_ass() → write <job_id>_karaoke.ass
8. update_progress(75, "Burning karaoke subtitles")
9. FFmpegService.burn_subtitles(video, ass_path, output)   — same FFmpeg filter
10. update_progress(90, "Finalising")
11. params["result_files"] = {"ass": str(ass_path), "video": str(output)}
12. mark_completed()
```

No new dependencies. No new queues. Routes to `ai` queue (same as
`generate_subtitles_task` — computationally intensive).

#### D. New API endpoints

```
GET /jobs/{id}/download/ass   — ASS subtitle file
GET /jobs/{id}/download/video — burned karaoke MP4 (re-use Phase 3 route pattern)
```

### Job creation payload

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "karaoke",
  "parameters": {
    "language": "en",
    "highlight_color": "&H000000FF&",   // yellow in ASS AABBGGRR
    "base_color":      "&H00FFFFFF&"    // white
  }
}
```

### Pitfalls to avoid

| Pitfall | Mitigation |
|---------|-----------|
| whisper.cpp `--word-timestamps` changes the JSON output schema | Parse `words` array defensively; fall back to segment-level if `words` absent |
| ASS format is whitespace-sensitive | Test `.to_ass()` output against `ffprobe` subtitle stream validation |
| Word timestamps may not be available on all whisper models | `ggml-tiny.en.bin` supports word timestamps; verify on first run |
| FFmpeg `subtitles=` filter with `.ass` file | Same path-escaping rule applies — use `_escape_filter_path()` |
| Task routes to `ai` queue | Celery must be started with `--queues media,ai` — already required |

---

*Last updated: 2026-06-14 by Cursor AI agent — Phase 3 complete; Bug 6 (FastAPI route ordering) fixed and documented.*
