# VoxClone — Master Project Handoff

**Date:** 2026-06-14  
**Branch:** `feature/subtitle-pipeline`  
**Commit:** `94f77e0 Phase 2 subtitle generation complete`  
**Tags:** `v0.1-foundation` (Phase 1) · `phase2-subtitles-working` (Phase 2)  
**Working tree:** clean

> This document is completely self-contained. A new developer can continue
> the project using only this file.

---

## 1. Project Overview

**VoxClone** is an offline-first AI media processing platform.  
Users upload a video or audio file, choose a processing pipeline (subtitle
generation, audio extraction, voice cloning, etc.), and download the result.
All AI models run locally — no cloud API keys, no GPU required for Phase 2.

**Primary use cases (current):**
- Automatic subtitle generation from any video or audio
- Subtitle burn-in (hardcode subtitles into video)

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

### Phase 1 — Backend Foundation ✅

- FastAPI app factory with lifespan (Redis connect/disconnect, DB create)
- SQLite + async SQLAlchemy ORM (Media + Job models)
- File upload endpoint with ffprobe metadata extraction
- Media CRUD endpoints
- Job creation, dispatch, status polling
- Redis progress cache (`job:progress:<id>` keys, 24h TTL)
- Celery task dispatch (task routing to named queues)
- structlog JSON logging throughout

### Phase 2 — Whisper Subtitle Pipeline ✅

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

---

## 13. Remaining Roadmap

### Phase 3 — Subtitle Burn-In (next recommended task)

**What:** Hardcode SRT subtitles into a video using FFmpeg.

**Status:** Stub exists in `media_tasks.py`. `FFmpegService.burn_subtitles()` is implemented.

**Implementation steps:**
1. Update `burn_subtitles_task` in `app/tasks/media_tasks.py`:
   - Accept `subtitle_job_id` in `parameters` — look up SRT from `prior_job.parameters.result_files.srt`
   - Or accept a direct `srt_path` parameter
   - Call `ffmpeg.burn_subtitles(video_path, srt_path, output_path)`
2. Return burned video via `GET /jobs/{id}/result`
3. Optionally expose style parameters (font, size, color, position)

**Test:** Upload MP4 → generate subtitles → burn subtitles → watch output video

### Phase 4 — User-facing Audio Extraction

Extract audio from video with format/quality control (MP3, FLAC, WAV).
`extract_audio_task` exists but targets 16kHz WAV for Whisper. Needs format options.

### Phase 5 — Karaoke / Vocal Removal

Separate vocals from music using Demucs. Requires `pip install demucs` + PyTorch.
`karaoke_task` stub exists. `DemucsService` to be created.

### Phase 6 — Audio Enhancement

Noise removal via DeepFilterNet. Requires `pip install deepfilternet` + PyTorch.
`audio_enhance_task` stub exists.

### Phase 7 — Text-to-Speech (Piper)

Local TTS via Piper. No source media needed — `media_id` may be nullable.

### Phase 8 — Voice Replacement

Combines Phase 2 (transcript), Phase 7 (TTS), and FFmpeg (audio replacement).

### Phase 9 — Voice Cloning (OpenVoice)

Clone a speaker's voice from a reference clip. GPU strongly recommended.
`voice_clone_task` stub exists.

### Phase 10 — Voice Conversion

Convert source voice to match a target voice.

### Phase 11 — Flutter Frontend

Mobile + desktop UI. All Phase 1–10 APIs must be stable first.

### Phase 12 — Production Hardening

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
# 94f77e0 Phase 2 subtitle generation complete
# 52c5d3e Phase 1 foundation validated

git tag
# phase2-subtitles-working   ← Phase 2 complete (HEAD)
# v0.1-foundation             ← Phase 1 complete

# Safe rollback points
git checkout v0.1-foundation           # Phase 1 only — no subtitle pipeline
git checkout phase2-subtitles-working  # Phase 2 complete (current)

# To commit Phase 3 work
git add .
git commit -m "Phase 3: subtitle burn-in

- Complete burn_subtitles_task with subtitle_job_id resolution
- FFmpeg hardcode SRT into video
- Add burned video download endpoint"
git tag -a phase3-subtitle-burn -m "Phase 3: subtitle burn-in"
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
| `app/services/ffmpeg_service.py` | `extract_audio()`, `burn_subtitles()`, `probe()` |
| `app/services/redis_service.py` | Module-level singleton; connect via `worker_process_init` |
| `app/tasks/celery_app.py` | `worker_process_init` hook — connects Redis in each worker |
| `app/tasks/media_tasks.py` | All task implementations; pipeline + placeholder stubs |

---

## 17. Phase 2 Validation Evidence

The subtitle pipeline was validated end-to-end on 2026-06-14. The following
run confirms every component of Phase 2 is working correctly.

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

*Last updated: 2026-06-14 by Cursor AI agent — Phase 2 validation evidence added; all three bugs documented with working run IDs.*
