# VoxClone — Current Project State

**Date:** 2026-06-13
**Branch:** `feature/subtitle-pipeline`
**Last commit:** `52c5d3e Phase 1 foundation validated`

---

## Environment

| Item | Value |
|------|-------|
| OS | Ubuntu 24.04.2 LTS |
| Python | 3.12.3 |
| Virtual env | `backend/.venv/` |
| Redis | `redis://localhost:6379/0` (default port) |
| SQLite DB | `backend/voxclone.db` |
| FFmpeg | 6.1.1 (system package, `/usr/bin/ffmpeg`) |
| whisper-cli | `tools/whisper.cpp/build/bin/whisper-cli` (975 KB built binary) |
| Whisper models dir | `backend/models/` |

### Whisper Models Present

```
backend/models/ggml-tiny.en.bin     75 MB   (active default)
backend/models/ggml-base.en.bin    142 MB
backend/models/ggml-small.en.bin   466 MB
```

### Active `.env` Settings (key whisper entries)

```
WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_THREADS=8
```

Note: `WHISPER_LANGUAGE` is not set in `.env` — defaults to `"en"` from `config.py`.

---

## Repository Structure

```
VoxClone/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── health.py       GET /health
│   │   │   │   ├── uploads.py      POST /uploads
│   │   │   │   ├── media.py        GET /media, /media/{id}
│   │   │   │   └── jobs.py         POST/GET /jobs + download endpoints
│   │   │   └── router.py
│   │   ├── core/
│   │   │   ├── config.py           All settings (pydantic-settings)
│   │   │   ├── exceptions.py       Domain exceptions + FastAPI handlers
│   │   │   └── logging.py          structlog setup
│   │   ├── database/
│   │   │   ├── session.py          Async engine, session factory
│   │   │   └── init_db.py          create_tables() on startup
│   │   ├── models/
│   │   │   ├── media.py            Media SQLAlchemy model
│   │   │   └── job.py              Job model + JobType + JobStatus
│   │   ├── schemas/
│   │   │   ├── job.py              JobCreate, JobResponse
│   │   │   └── media.py            MediaResponse
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py   FFmpeg wrapper (probe, extract, burn)
│   │   │   ├── job_service.py      Job CRUD + lifecycle (mark_started etc.)
│   │   │   ├── media_service.py    Media CRUD
│   │   │   ├── redis_service.py    Redis singleton + progress cache
│   │   │   ├── upload_service.py   File ingestion pipeline
│   │   │   └── whisper_service.py  whisper.cpp subprocess wrapper (Phase 2)
│   │   ├── tasks/
│   │   │   ├── celery_app.py       Celery application config
│   │   │   └── media_tasks.py      All Celery tasks
│   │   └── main.py                 FastAPI app factory + lifespan
│   ├── uploads/                    Uploaded media files
│   ├── processed/                  Pipeline output files
│   ├── models/                     GGML model files
│   ├── tools/whisper.cpp/          whisper.cpp source + built binary
│   ├── .env                        Active configuration
│   ├── .env.example                Configuration template
│   └── requirements.txt
├── docs/
│   ├── testing/
│   │   ├── WHISPER_CPP_SETUP.md
│   │   ├── PHASE2_TEST_PLAN.md
│   │   ├── PHASE2_MANUAL_TESTING.md
│   │   └── PHASE2_EXPECTED_RESULTS.md
│   ├── reports/
│   │   └── PHASE2_COMPLETION_REPORT.md
│   └── context/                    ← you are here
└── tools/
    └── whisper.cpp/                whisper.cpp repo (built)
```

---

## Component Status

### Phase 1 — Fully Working

| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI startup | ✅ Working | Lifespan connects Redis, creates DB tables |
| `GET /health` | ✅ Working | Returns `{status: ok, database: ok, redis: ok}` |
| File upload | ✅ Working | `POST /uploads` multipart, validates extension, streams to disk |
| FFprobe metadata | ✅ Working | Duration, codec, resolution, sample rate extracted |
| Media CRUD | ✅ Working | `GET /media`, `GET /media/{id}`, `DELETE /media/{id}` |
| Job creation | ✅ Working | `POST /jobs` creates DB record, dispatches Celery task |
| Job status polling | ✅ Working | `GET /jobs/{id}`, `GET /jobs/{id}/progress` |
| Redis progress cache | ✅ Working | Set on job create; polled by `/progress` endpoint |
| Celery task dispatch | ✅ Working | Tasks are received by the worker |
| Download endpoint | ✅ Working | `GET /jobs/{id}/result` returns FileResponse |

### Phase 2 — In Progress

| Component | Status | Notes |
|-----------|--------|-------|
| `WhisperService` | ✅ Implemented | whisper.cpp subprocess, validates binary + model |
| `TranscriptResult` | ✅ Implemented | `.to_srt()`, `.to_vtt()`, `.to_txt()` correct |
| Whisper config settings | ✅ Implemented | `WHISPER_CPP_BINARY`, `WHISPER_MODEL_PATH`, `WHISPER_THREADS` |
| `generate_subtitles_task` | ❌ Failing | See KNOWN_BUGS_AND_ROOT_CAUSES.md |
| Subtitle download endpoints | ✅ Implemented | `/jobs/{id}/download/{transcript,srt,vtt}` |
| Diagnostic logging | ✅ Added | `diag_*` events on all failure paths |

### Infrastructure Readiness

| Item | Status |
|------|--------|
| whisper-cli binary | ✅ Built at `tools/whisper.cpp/build/bin/whisper-cli` |
| Whisper models | ✅ All 3 downloaded (tiny.en, base.en, small.en) |
| FFmpeg | ✅ System package installed |
| Redis | ✅ Installed, default config |

---

## Git State

**Branch:** `feature/subtitle-pipeline`
**Ahead of origin:** 0 commits (last pushed: Phase 1 foundation)
**Last commit hash:** `52c5d3e`

### Modified (not yet committed)

```
backend/.env.example
backend/app/api/v1/endpoints/jobs.py
backend/app/core/config.py
backend/app/services/job_service.py
backend/app/services/redis_service.py
backend/app/tasks/media_tasks.py
backend/requirements.txt
```

### Untracked (not yet added)

```
backend/app/services/whisper_service.py
docs/context/
docs/reports/
docs/testing/
tools/
```

### Recommended commit strategy

Do **not** commit until bugs 1 and 2 are fixed and the subtitle pipeline produces a real SRT file. Then commit everything as:

```
git add .
git commit -m "Phase 2: whisper.cpp subtitle pipeline

- WhisperService wrapping whisper.cpp CLI subprocess
- generate_subtitles_task: video → audio → whisper → SRT/VTT/TXT
- Fix Redis connection in Celery worker (worker_process_init signal)
- Fix SQLAlchemy lazy-load: selectinload(Job.media) in mark_started
- Add subtitle download endpoints /jobs/{id}/download/{transcript,srt,vtt}
- Diagnostic logging on all failure paths
- Full test suite and context documentation"
```
