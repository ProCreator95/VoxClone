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
| Upload Video → Extract Audio → Generate Subtitles → Burn Subtitles → Download | 🏗 In Progress |
| Voice Replacement | ⏳ Planned |
| Karaoke (vocal removal) | ⏳ Planned |
| Voice Cloning | ⏳ Planned |
| Audio Enhancement | ⏳ Planned |

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
celery -A app.tasks.celery_app worker --loglevel=info --queues=media,ai,default
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
| `subtitle_generation` | Generate SRT subtitles via whisper.cpp |
| `subtitle_burn` | Burn subtitles into video |
| `karaoke` | Remove vocals via Demucs |
| `voice_replacement` | Replace voice track |
| `voice_clone` | Clone voice via OpenVoice |
| `audio_enhance` | Denoise audio via DeepFilterNet |

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
