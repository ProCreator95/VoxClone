# VoxClone — Current Project State

**Date:** 2026-06-14
**Branch:** `feature/subtitle-pipeline`
**Last commit:** `94f77e0 Phase 2 subtitle generation complete`
**Tags:** `v0.1-foundation` (Phase 1), `phase2-subtitles-working` (Phase 2)

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

### Phase 2 — Complete ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `WhisperService` | ✅ Working | whisper.cpp subprocess, validates binary + model |
| `TranscriptResult` | ✅ Working | `.to_srt()`, `.to_vtt()`, `.to_txt()` correct |
| Whisper config settings | ✅ Working | `WHISPER_CPP_BINARY`, `WHISPER_MODEL_PATH`, `WHISPER_THREADS` |
| `generate_subtitles_task` | ✅ Working | Produces SRT/VTT/TXT via whisper.cpp |
| Subtitle download endpoints | ✅ Working | `/jobs/{id}/download/{transcript,srt,vtt}` |
| Diagnostic logging | ✅ In place | `diag_*` events on all code paths |

### Three bugs fixed in this session

| Bug | Fix applied in |
|-----|---------------|
| Redis not connected in Celery workers | `app/tasks/celery_app.py` — `worker_process_init` signal |
| `MissingGreenlet` on `job.media` lazy-load | `app/services/job_service.py` — `get_by_id_with_media()` with `selectinload` |
| `libwhisper.so.1 not found` / `libggml.so.0 not found` | `app/services/whisper_service.py` — `_build_subprocess_env()` sets `LD_LIBRARY_PATH` |

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
(none — working tree is clean)
```

### Tags

```
v0.1-foundation            → Phase 1 complete
phase2-subtitles-working   → Phase 2 complete (current HEAD = 94f77e0)
```
