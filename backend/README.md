# VoxClone Backend

Offline AI-powered media processing platform — FastAPI backend.

## Features

- Async REST API with FastAPI
- SQLite database (PostgreSQL-ready via SQLAlchemy)
- Background job processing with Celery + Redis
- FFmpeg-based media pipeline
- Structured JSON logging
- Docker-ready

## Supported Pipelines

| Pipeline | Status |
|---|---|
| Subtitle generation (whisper.cpp) | ✅ |
| Subtitle burn-in (FFmpeg) | ✅ |
| Karaoke video (ASS word highlight) | ✅ |
| Vocal separation (Demucs) | ✅ |
| Karaoke over instrumental (inline Demucs) | ✅ |
| Audio enhancement (DeepFilterNet) | ⏳ placeholder |
| Voice replacement / cloning | ⏳ planned |

See `docs/context/MASTER_PROJECT_HANDOFF.md` for full API and phase details.

## ML dependencies (Celery worker)

Source separation and inline karaoke Demucs require optional ML packages:

```bash
pip install -r requirements-ml.txt
```

Do not install unpinned `torch` — see `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md`.

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/   # Route handlers
│   ├── core/               # Config, logging, exceptions
│   ├── database/           # SQLAlchemy engine & session
│   ├── models/             # ORM models (Media, Job)
│   ├── schemas/            # Pydantic v2 request/response schemas
│   ├── services/           # Business logic (upload, media, job, ffmpeg, redis)
│   ├── tasks/              # Celery task definitions
│   └── utils/              # File helpers
├── uploads/                # Uploaded raw media
├── processed/              # AI-processed output files
├── logs/                   # Structured log files
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- FFmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- Redis (`sudo apt install redis-server` or Docker)

### 2. Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 3. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Run the Celery worker (separate terminal)

```bash
pip install -r requirements-ml.txt   # first time — Demucs / separation jobs
celery -A app.tasks.celery_app worker --loglevel=info --queues=media,ai --concurrency=1
```

### 6. (Optional) Celery Flower UI

```bash
celery -A app.tasks.celery_app flower --port=5555
```

Open http://localhost:5555 to monitor tasks.

## Docker

```bash
# Copy and configure environment
cp .env.example .env

# Start all services (API + Worker + Flower + Redis)
docker compose up -d

# Tail logs
docker compose logs -f api worker
```

## API Reference

Interactive docs available at **http://localhost:8000/docs** when running.

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (DB + Redis status) |
| `POST` | `/api/v1/uploads` | Upload a media file |
| `GET` | `/api/v1/media` | List all uploaded media |
| `GET` | `/api/v1/media/{id}` | Get media details |
| `DELETE` | `/api/v1/media/{id}` | Delete media and its jobs |
| `GET` | `/api/v1/media/{id}/download` | Download original file |
| `GET` | `/api/v1/media/{id}/jobs` | List jobs for media |
| `POST` | `/api/v1/jobs` | Create a processing job |
| `GET` | `/api/v1/jobs/{id}` | Get job status |
| `GET` | `/api/v1/jobs/{id}/progress` | Get live job progress |
| `GET` | `/api/v1/jobs/{id}/result` | Download job result |
| `DELETE` | `/api/v1/jobs/{id}` | Cancel a job |

### Job Types

| Type | Description |
|---|---|
| `audio_extraction` | Extract audio track from video |
| `subtitle_generation` | Generate SRT/VTT/TXT via whisper.cpp |
| `subtitle_burn` | Burn subtitles into video |
| `karaoke` | Karaoke (`output_mode`: with_vocals, no_vocals, vocals_only, music_only; optional `separation_job_id`) |
| `vocal_separation` | Demucs two-stem separation (vocals + instrumental) |
| `audio_enhance` | Dispatches but not implemented (marks failed) |
| `voice_replacement` | HTTP 422 — not implemented |
| `voice_clone` | HTTP 422 — not implemented |

## Database Migrations

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Generate a migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Database | SQLite (aiosqlite) |
| Validation | Pydantic v2 |
| Task Queue | Celery 5 |
| Message Broker | Redis 7 |
| Logging | structlog |
| Media | FFmpeg |
