---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Active branch is `feature/subtitle-burn`, not `feature/subtitle-pipeline`
> - Phase 3 (subtitle burn-in) listed as a planned capability — it is complete as of `2f9f643`
> - API endpoint table is missing `GET /jobs/{id}/download/video` (added in Phase 3)
> - Celery command shown without `--queues media,ai` (tasks will not execute without this)
> - Repo structure references `app/utils/file_utils.py`, `logs/`, `Dockerfile`, `docker-compose.yml` which do not exist
> - Redis progress cache key format shown as `job_progress:{job_id}` — actual format is `job:progress:{job_id}`
> - Redis TTL shown as 3600s — actual TTL is 86400s (24h)
> - Config schema (`LOGS_DIR`, `MAX_UPLOAD_SIZE_BYTES`) may not match current `config.py`
> - Git state section shows tag `v0.1-foundation` only; current tags include `phase2-subtitles-working` and `phase3-subtitle-burn`
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` — single authoritative reference

---

# VoxClone — Complete Project Context

> Paste this document at the start of a new Cursor chat to continue development without losing context.

---

## Project Vision

VoxClone is an **offline-first AI media processing platform**.

All heavy processing runs locally — no cloud API keys required.

**Current capabilities (implemented):**
- Video upload and metadata extraction
- Audio extraction from video
- Automatic subtitle generation (Whisper)
- SRT and WebVTT output

**Planned capabilities (roadmap):**
- Subtitle burn-in (FFmpeg)
- Audio extraction as a user-facing feature
- Karaoke / vocal removal (Demucs)
- Audio enhancement (DeepFilterNet)
- Text-to-speech (Piper)
- Voice replacement (dubbed video)
- Voice cloning (OpenVoice)
- Voice conversion
- Flutter mobile/desktop frontend

---

## Repository Structure

```
VoxClone/
├── backend/                    # FastAPI backend (Python)
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py         # FastAPI dependency injectors
│   │   │   └── v1/
│   │   │       ├── router.py   # API v1 root router
│   │   │       └── endpoints/
│   │   │           ├── health.py    # GET /health
│   │   │           ├── uploads.py   # POST /uploads
│   │   │           ├── media.py     # GET /media, /media/{id}
│   │   │           └── jobs.py      # POST/GET /jobs, download endpoints
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic Settings — all env vars
│   │   │   ├── exceptions.py   # Domain exceptions + FastAPI handlers
│   │   │   └── logging.py      # structlog setup
│   │   ├── database/
│   │   │   ├── base.py         # SQLAlchemy declarative base
│   │   │   ├── session.py      # Async engine, session factory, context manager
│   │   │   └── init_db.py      # create_tables() / drop_tables()
│   │   ├── models/
│   │   │   ├── media.py        # Media SQLAlchemy model
│   │   │   └── job.py          # Job SQLAlchemy model + JobType + JobStatus
│   │   ├── schemas/
│   │   │   ├── common.py       # HealthStatus, MessageResponse
│   │   │   ├── media.py        # MediaResponse, MediaListResponse
│   │   │   └── job.py          # JobCreate, JobResponse, JobProgressResponse
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py   # FFmpeg wrapper (probe, extract_audio, burn_subtitles)
│   │   │   ├── job_service.py      # Job CRUD + status transitions
│   │   │   ├── media_service.py    # Media CRUD
│   │   │   ├── redis_service.py    # Redis progress cache
│   │   │   ├── upload_service.py   # File ingestion pipeline
│   │   │   └── whisper_service.py  # Whisper transcription (Phase 2)
│   │   ├── tasks/
│   │   │   ├── celery_app.py       # Celery application instance
│   │   │   └── media_tasks.py      # All Celery tasks
│   │   ├── utils/
│   │   │   └── file_utils.py
│   │   └── main.py             # FastAPI app factory + lifespan
│   ├── uploads/                # Uploaded media files
│   ├── processed/              # Pipeline output files
│   ├── models/                 # GGML model files (ggml-tiny.en.bin etc.)
│   ├── logs/
│   ├── .env                    # Active environment config (not in git)
│   ├── .env.example            # Environment config template
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── testing/                # Test plans and expected results
│   ├── reports/                # Phase completion reports
│   └── context/                # This directory — project context docs
└── .gitignore
```

---

## Database Schema

**Database:** SQLite (file: `backend/voxclone.db`)
**ORM:** SQLAlchemy 2.x async

### Table: `media`

| Column | Type | Description |
|--------|------|-------------|
| id | String(36) PK | UUID |
| filename | String(255) | Stored filename (hex + extension) |
| original_name | String(255) | Original upload filename |
| file_path | String(512) | Absolute path on disk |
| file_size | Integer | Bytes |
| mime_type | String(100) | e.g. `video/mp4` |
| media_type | String(20) | `video` or `audio` |
| duration | Float | Seconds (from ffprobe) |
| format | String(50) | e.g. `mov,mp4,m4a,3gp,3g2,mj2` |
| width | Integer | Video width in pixels |
| height | Integer | Video height in pixels |
| codec_video | String(50) | e.g. `h264` |
| codec_audio | String(50) | e.g. `aac` |
| bitrate | Integer | bits/sec |
| sample_rate | Integer | Audio sample rate |
| audio_channels | Integer | 1=mono, 2=stereo |
| status | String(20) | `pending` / `ready` / `processing` / `error` |
| extra_metadata | JSON | Reserved for future use |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

### Table: `jobs`

| Column | Type | Description |
|--------|------|-------------|
| id | String(36) PK | UUID |
| media_id | String(36) FK→media.id | CASCADE delete |
| job_type | String(50) | See JobType constants |
| status | String(20) | `queued`/`processing`/`completed`/`failed`/`cancelled` |
| progress | Integer | 0–100 |
| current_step | String(255) | Human-readable step name |
| result_path | String(512) | Primary output file path |
| error_message | Text | Error details if status=failed |
| parameters | JSON | Input config + output result_files |
| celery_task_id | String(255) | Celery task UUID |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |
| started_at | DateTime(tz) | When worker picked it up |
| completed_at | DateTime(tz) | When terminal state reached |

### JobType Constants

```python
class JobType:
    AUDIO_EXTRACTION = "audio_extraction"
    SUBTITLE_GENERATION = "subtitle_generation"
    SUBTITLE_BURN = "subtitle_burn"
    KARAOKE = "karaoke"
    VOICE_REPLACEMENT = "voice_replacement"
    VOICE_CLONE = "voice_clone"
    AUDIO_ENHANCE = "audio_enhance"
```

### JobStatus Constants

```python
class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

## Redis Usage

Redis serves two purposes:

1. **Celery broker** (`redis://localhost:6379/0`) — task queue for dispatching jobs
2. **Celery result backend** (`redis://localhost:6379/1`) — task results
3. **Progress cache** (`redis://localhost:6379/0`) — key `job_progress:{job_id}`, TTL 3600s

Progress cache format:
```json
{
    "job_id": "...",
    "status": "processing",
    "progress": 45,
    "current_step": "Running Whisper speech recognition",
    "error_message": null
}
```

The `/jobs/{id}/progress` endpoint reads from Redis first (low latency), falling back to the database.

---

## Celery Workflow

All jobs follow this pattern:
1. `POST /api/v1/jobs` creates a `Job` record (status=`queued`)
2. `dispatch_job(job_id, job_type)` calls `.delay(job_id)` on the Celery task
3. Celery worker receives the task, calls `job_svc.mark_started()`
4. Task updates progress via `_update_progress(job_id, %, "step")`
5. Task calls `job_svc.mark_completed(job_id, result_path)` or `mark_failed()`

Celery app is defined in `app/tasks/celery_app.py`.
All tasks are in `app/tasks/media_tasks.py`.

The task dispatcher maps job types to Celery task functions:
```python
_TASK_MAP = {
    "audio_extraction": extract_audio_task,
    "subtitle_generation": generate_subtitles_task,
    "subtitle_burn": burn_subtitles_task,
    "karaoke": karaoke_task,
    "audio_enhance": audio_enhance_task,
}
```

---

## API Endpoints (Phase 2 State)

Base URL: `http://localhost:8000/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/uploads` | Upload media file (multipart/form-data, field: `file`) |
| GET | `/media` | List all media |
| GET | `/media/{id}` | Get media metadata |
| DELETE | `/media/{id}` | Delete media and its jobs |
| POST | `/jobs` | Create processing job |
| GET | `/jobs/{id}` | Get full job details |
| GET | `/jobs/{id}/progress` | Live progress (from Redis) |
| GET | `/jobs/{id}/result` | Download primary result file |
| DELETE | `/jobs/{id}` | Cancel job |
| GET | `/jobs/{id}/download/transcript` | Download .txt transcript (subtitle jobs) |
| GET | `/jobs/{id}/download/srt` | Download .srt subtitle file |
| GET | `/jobs/{id}/download/vtt` | Download .vtt subtitle file |

Interactive docs: `http://localhost:8000/docs`

---

## Environment Configuration

All settings in `backend/app/core/config.py`, loaded from `.env`:

```bash
# App
APP_NAME=VoxClone
APP_VERSION=0.1.0
DEBUG=false

# Database (SQLite default)
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Storage
UPLOAD_DIR=uploads
PROCESSED_DIR=processed
LOGS_DIR=logs
MAX_UPLOAD_SIZE_BYTES=2147483648

# FFmpeg
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe

# Whisper.cpp (Phase 2 — CPU-only, no PyTorch, no CUDA)
WHISPER_CPP_BINARY=whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin   # tiny.en | base.en | small.en
WHISPER_THREADS=4
WHISPER_LANGUAGE=en          # "en" for .en models; "" = auto-detect
```

---

## Installation Steps

```bash
# 1. Clone
git clone <repo-url> VoxClone
cd VoxClone/backend

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env as needed

# 5. Start Redis
redis-server --daemonize yes

# 6. Start FastAPI
uvicorn app.main:app --reload --port 8000

# 7. Start Celery worker (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## Development Workflow

```bash
# Activate venv
source backend/.venv/bin/activate
cd backend

# Run API with hot reload
uvicorn app.main:app --reload

# Run Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Check logs
tail -f logs/voxclone.log

# Reset database
rm voxclone.db  # tables recreate on next startup
```

---

## Technical Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Language | Python 3.12 | Rich AI/ML ecosystem |
| Framework | FastAPI | Async, auto-docs, type safety |
| Database | SQLite → PostgreSQL (future) | Zero-setup for dev |
| ORM | SQLAlchemy 2.x async | Type-safe, future-proof |
| Task queue | Celery + Redis | Battle-tested, distributed |
| Job progress | Redis cache | Low-latency polling |
| Logging | structlog JSON | Machine-parseable |
| Subtitles | whisper.cpp (CLI subprocess) | No PyTorch/CUDA, pure C++, offline, CPU-efficient |
| Audio | FFmpeg | Universal format support |
| Schema migration | No Alembic yet | Using create_all; add Alembic in Phase 3 |
| Multiple outputs | Stored in `job.parameters.result_files` | No schema change needed |

---

## Completed Phases

### Phase 1 — Backend Foundation
- FastAPI application factory
- SQLite + SQLAlchemy async
- Redis integration
- Celery task queue
- File upload with validation and ffprobe metadata extraction
- Job lifecycle management (create → dispatch → progress → complete/fail)
- Structured logging (structlog)
- Docker support
- All API endpoints for upload, media, jobs

### Phase 2 — Whisper Subtitle Pipeline
- `WhisperService` wrapping whisper.cpp CLI via async subprocess (CPU-only, no PyTorch)
- Full `generate_subtitles_task` Celery task
- SRT, VTT, TXT output generation from parsed whisper.cpp JSON
- Subtitle format download endpoints: `/jobs/{id}/download/{transcript,srt,vtt}`
- Binary + model validation with actionable error messages
- `WHISPER_CPP_BINARY`, `WHISPER_MODEL_PATH`, `WHISPER_THREADS`, `WHISPER_LANGUAGE` settings
- Validation test suite + `docs/testing/WHISPER_CPP_SETUP.md`

---

## Git State

**Current branch:** `feature/subtitle-pipeline`
**Base branch:** `main`
**Tag:** `v0.1-foundation` (Phase 1 complete)

```bash
git log --oneline -5
```
