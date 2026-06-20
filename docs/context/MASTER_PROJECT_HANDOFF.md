# VoxClone — Master Project Handoff

**Date:** 2026-06-20
**Branch:** `feature/source-separation`
**Commit:** `47be178 Phase 4: karaoke generation complete` (Phase 5 staged, pre-commit)
**Tags:** `v0.1-foundation` · `phase2-subtitles-working` · `phase3-subtitle-burn` · `phase4-karaoke-generation`
**Working tree:** Phase 5 source separation + karaoke modes staged, awaiting commit

> This document is completely self-contained. A new developer can continue
> the project using only this file.

---

## 1. Project Overview

**VoxClone** is an offline-first AI media processing platform.
Users upload a video or audio file, choose a processing pipeline (subtitle
generation, audio extraction, voice cloning, etc.), and download the result.
All AI models run locally — no cloud API keys, no GPU required for Phase 2.

**Primary use cases (Phases 1–5 complete):**
- Automatic subtitle generation from any video or audio (Phase 2)
- Subtitle burn-in — hardcode subtitles into video as H.264 MP4 (Phase 3)
- Karaoke video with word-level ASS highlighting (Phase 4)
- Vocal/instrumental stem separation via Demucs (Phase 5)
- Karaoke over instrumental track (inline Demucs or reused stems, Phase 5 M3–M4)
- Stem-only karaoke output (`vocals_only`, `music_only`) with optional `separation_job_id` reuse (Phase 5 M4)

**Planned use cases (future phases):**
- Audio enhancement (noise removal) — Phase 6
- Text-to-speech — Phase 7
- Voice replacement / dubbing — Phase 8
- Voice cloning — Phase 9+

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
│                →  karaoke_task                           │
│                →  vocal_separation_task                  │
│                →  audio_enhance_task (placeholder)       │
│                     │                                    │
│              ┌──────▼──────────────────┐                │
│              │   FFmpegService          │                │
│              └──────┬──────────────────┘                │
│              ┌──────▼──────────────────┐                │
│              │   WhisperService         │                │
│              │   (whisper.cpp)          │                │
│              └──────┬──────────────────┘                │
│              ┌──────▼──────────────────┐                │
│              │ SourceSeparationService  │                │
│              │ (Demucs subprocess)      │                │
│              └──────┬──────────────────┘                │
│                     ↓                                    │
│         outputs written to processed/                    │
│                                                          │
│  Async runtime: one persistent event loop per worker     │
│  (app/tasks/async_runner.py — run_async())               │
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
| Source separation | Demucs 4.0.1 + PyTorch 2.8.0 CPU | worker-only; see `requirements-ml.txt` |
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
│   │   │   ├── job.py               Job model + JobType + JobStatus
│   │   │   └── stem_metadata.py     canonical vs inline stem ownership
│   │   ├── schemas/
│   │   │   ├── job.py               JobCreate, JobResponse, parameter validation
│   │   │   └── media.py             MediaResponse
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py    FFmpeg wrapper (probe, extract, burn, stereo WAV)
│   │   │   ├── job_service.py       Job CRUD + lifecycle
│   │   │   ├── media_service.py     Media CRUD
│   │   │   ├── redis_service.py     Redis singleton + progress cache
│   │   │   ├── upload_service.py    File ingestion pipeline
│   │   │   ├── whisper_service.py   whisper.cpp subprocess wrapper
│   │   │   ├── whisper_models.py    Per-job whisper model aliases + defaults
│   │   │   ├── source_separation_service.py   Demucs subprocess wrapper
│   │   │   ├── separation_models.py htdemucs whitelist
│   │   │   └── karaoke_modes.py     Karaoke output_mode validation
│   │   └── tasks/
│   │       ├── async_runner.py      Persistent worker event loop + run_async()
│   │       ├── celery_app.py        Celery config + worker_process_init hook
│   │       └── media_tasks.py       All Celery task implementations
│   ├── uploads/                     Uploaded media files
│   ├── processed/                   Pipeline output files
│   ├── models/                      GGML model files
│   │   ├── ggml-tiny.en.bin         75 MB  (subtitle_generation default)
│   │   ├── ggml-base.en.bin         142 MB (karaoke default)
│   │   └── ggml-small.en.bin        466 MB
│   ├── .env                         Active configuration
│   ├── .env.example                 Configuration template
│   ├── requirements.txt
│   └── requirements-ml.txt          Pinned torch/torchaudio/demucs (worker only)
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

# ── Source separation (Demucs — Celery worker only) ─────
DEMUCS_MODEL=htdemucs
DEMUCS_DEVICE=cpu
SEPARATION_SAMPLE_RATE=44100
SEPARATION_CHANNELS=2
```

> **ML worker install:** `pip install -r requirements-ml.txt` (pinned torch 2.8.0 + demucs 4.0.1).
> See `docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` for self-test.

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
# Install ML deps once per worker venv (Demucs / vocal_separation / karaoke no_vocals)
pip install -r requirements-ml.txt

celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai \
  --concurrency 1 \
  --loglevel INFO
```

**Both queues are required.** Tasks route to `media` or `ai` per `celery_app.py`.
Use `--concurrency 1` when running Demucs to reduce OOM risk (see `PHASE5_STEM_OWNERSHIP_AND_OPS.md`).

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
| GET | `/jobs/{id}/download/video` | Download burned-subtitle MP4 (subtitle_burn jobs) |
| GET | `/jobs/{id}/download/ass` | Download ASS karaoke subtitle file (karaoke jobs) |
| GET | `/jobs/{id}/download/karaoke-video` | Download karaoke MP4 (karaoke jobs) |
| GET | `/jobs/{id}/download/vocals` | Download vocals stem WAV (vocal_separation / inline karaoke) |
| GET | `/jobs/{id}/download/instrumental` | Download instrumental stem WAV |
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

**`job_type` values** — the schema layer accepts all names; the API returns HTTP 422 if a type is not yet implemented:

| job_type | Phase | Status |
|----------|-------|--------|
| `audio_extraction` | 1 | ✅ implemented |
| `subtitle_generation` | 2 | ✅ implemented |
| `subtitle_burn` | 3 | ✅ implemented |
| `karaoke` | 4–5 | ✅ implemented (modes: `karaoke_video_with_vocals`, `karaoke_video_no_vocals`) |
| `vocal_separation` | 5 | ✅ implemented |
| `audio_enhance` | 6 | ⏳ dispatches but marks failed — DeepFilterNet not implemented |
| `voice_replacement` | 8 | ⏳ HTTP 422 — not in `_TASK_MAP` |
| `voice_clone` | 9+ | ⏳ HTTP 422 — not in `_TASK_MAP` |

**Common parameters (Phase 5):**

```json
{ "whisper_model": "tiny" | "base" | "small" }
{ "separation_model": "htdemucs" }
{ "output_mode": "karaoke_video_with_vocals" | "karaoke_video_no_vocals" }
```

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

### Phase 4 — Karaoke Generation ✅ COMPLETE

- **`WhisperService.transcribe(word_timestamps=True)`** — passes `--output-json-full` to whisper.cpp (not `--word-timestamps`; see section 19 for rationale). Each segment's BPE token array is grouped into `WordTimestamp` objects by `_tokens_to_words()` using the leading-space word-boundary convention.
- **`WordTimestamp` / `WhisperSegment.words`** — new dataclasses added to `whisper_service.py`; segments fall back to empty `words=[]` when tokens are unavailable (graceful degradation to plain subtitles).
- **`TranscriptResult.to_ass()`** — generates ASS subtitle format with `\kf` karaoke timing. Colour parameters use ASS AABBGGRR format (`&H0000FFFF&` = yellow, `&H00FFFFFF&` = white).
- **`_build_karaoke_text()`** — builds per-segment `\kf`-tagged text. Pre-roll gap expressed as an empty `\kf` slot (standard ASS karaoke pattern; supported by libass, DirectVobSub, VSFilter).
- **`FFmpegService.burn_ass()`** — new method; differs from `burn_subtitles()` in that `force_style` is intentionally omitted (ASS carries its own `[V4+ Styles]` section that drives the karaoke colour effect).
- **`karaoke_task`** — full pipeline: validate video → extract audio → transcribe with word timestamps → write `.ass` → burn `.ass` into `.mp4` → persist `result_files`.
- **`IMPLEMENTED_JOB_TYPES`** — frozenset derived from `_TASK_MAP`; exported so `create_job()` can guard against unimplemented job types before creating a DB record (prevents zombie jobs with `status=queued`).
- **`GET /jobs/{id}/download/ass`** — ASS file download endpoint.
- **`GET /jobs/{id}/download/karaoke-video`** — karaoke MP4 download endpoint.
- **API pre-flight guard** in `create_job()` — returns HTTP 422 for `voice_replacement`, `voice_clone`, and any other planned-but-unimplemented job type, instead of creating a zombie DB record and then crashing with HTTP 500.

**Validated run:**

| Field | Value |
|-------|-------|
| Job ID | `0e44f8ef-0867-437b-a1fc-c9e8d4d90a08` |
| Status | `completed` |
| Output | `processed/0e44f8ef-..._karaoke.ass`, `processed/0e44f8ef-..._karaoke.mp4` |
| Word timestamps present | ✅ |
| Karaoke highlight effect | ✅ (confirmed in MP4 playback) |

**Known limitation — Whisper model accuracy on music content:**
The `ggml-tiny.en.bin` model drops lyrics during long instrumental sections (~27s and ~30s gaps observed in validation). This is a Whisper model limitation, not a code defect — the same gaps appear identically in `subtitle_generation` output (using `--output-json`) and `karaoke` output (using `--output-json-full`). See section 19 and `KNOWN_BUGS_AND_ROOT_CAUSES.md` for details. Use `ggml-base.en.bin` for better accuracy on music videos.

### Phase 5 — Source Separation & Vocal Removal ✅ COMPLETE (pre-commit)

**Milestone 1 — Per-job Whisper models:** `whisper_models.py`; defaults `subtitle_generation` → `tiny`, `karaoke` → `base`.

**Milestone 2 — Canonical vocal separation:** `vocal_separation` job type, `SourceSeparationService` (Demucs subprocess), `stem_origin: canonical`, stem download endpoints.

**Milestone 3 — Karaoke output modes:** `karaoke_video_with_vocals`, `karaoke_video_no_vocals` (inline Demucs, `stem_origin: inline`).

**Milestone 4 — Stem reuse + stem-only modes:** `vocals_only`, `music_only`, optional `separation_job_id` (reuse canonical stems, skip Demucs).

**Infrastructure:** `requirements-ml.txt` (torch 2.8.0 + demucs 4.0.1), `async_runner.py` (persistent worker loop), `stem_reuse.py` (canonical stem resolution).

See `docs/reports/PHASE5_*.md` for milestone reports and validation evidence.

---

## 10. Exact Fixes Applied (Code Level)

### Fix 1 — `backend/app/tasks/celery_app.py`

Added `worker_process_init` and `worker_process_shutdown` signal handlers using a
**persistent worker event loop** (`app/tasks/async_runner.py`):

```python
from app.tasks.async_runner import get_worker_event_loop

@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
    setup_logging()
    from app.services.redis_service import redis_service
    loop = get_worker_event_loop()
    loop.run_until_complete(redis_service.connect())
    logger.info("celery_worker_process_redis_connected")
```

Celery tasks call `run_async(coro)` — **not** `asyncio.run(coro)` — so Redis,
SQLAlchemy async sessions, and subprocess helpers share the same loop. See Bug 9
in `KNOWN_BUGS_AND_ROOT_CAUSES.md`.

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

### Redis connect is per-process, on a persistent event loop

`worker_process_init` connects Redis once per forked worker on
`get_worker_event_loop()`. Tasks must use `run_async()` from `async_runner.py` —
**never** `asyncio.run()` per task — or `redis.asyncio` clients raise
`Future attached to a different loop` (Bug 9).

### Demucs / ML dependencies are worker-only

Install `requirements-ml.txt` on Celery workers that run `vocal_separation` or
inline karaoke separation. Pin `torch==2.8.0` + `torchaudio==2.8.0`; unpinned
installs break Demucs WAV export via TorchCodec (Bug 8).

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

### Whisper model accuracy on music-heavy content

`ggml-tiny.en.bin` produces large silent gaps (20–30 s) when the audio has a
long instrumental section with no clear vocals. The model emits an `(upbeat
music)` marker and then produces no segments for the instrumental period.
The karaoke pipeline faithfully renders whatever whisper.cpp transcribes —
missing lyrics in the karaoke video always trace back to missing segments in
the Whisper JSON output, not to a rendering bug. For music videos, switch to
`ggml-base.en.bin` (142 MB) or `ggml-small.en.bin` (466 MB) in `.env`:
```bash
WHISPER_MODEL_PATH=models/ggml-base.en.bin
```

### Adding a new implemented job type

1. Write the Celery task function and register it in `_TASK_MAP` in `media_tasks.py`.
2. Add it to `JobType.ALL` in `models/job.py` (allows schema validation to pass).
3. That is all — `IMPLEMENTED_JOB_TYPES` is derived from `_TASK_MAP` automatically,
   so the API pre-flight check in `create_job()` will start accepting it with no
   further changes.

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

| Phase | Name | Status |
|-------|------|--------|
| 1 | Backend Foundation | ✅ `v0.1-foundation` |
| 2 | Subtitle Generation | ✅ `phase2-subtitles-working` |
| 3 | Subtitle Burn-In | ✅ `phase3-subtitle-burn` |
| 4 | Karaoke Generation | ✅ `phase4-karaoke-generation` (`47be178`) |
| 5 | Source Separation / Vocal Removal | ✅ complete — staged on `feature/source-separation` |
| 6 | Audio Enhancement (DeepFilterNet) | ⏳ `audio_enhance_task` placeholder |
| 7 | Text-to-Speech (Piper) | ⏳ planned |
| 8 | Voice Replacement | ⏳ planned |
| 9+ | Voice Cloning (OpenVoice) | ⏳ planned |
| 10 | Flutter Frontend | ⏳ planned |
| 11 | Production Hardening | ⏳ planned |

### Phase 6 — Audio Enhancement

Noise removal via DeepFilterNet. `audio_enhance_task` is registered in `_TASK_MAP`
but marks jobs failed with "not yet implemented".

Phase 5 M4 report: `docs/reports/PHASE5_MILESTONE4_STEM_REUSE.md`

### Phase 7+ — TTS, Voice Replacement, Voice Cloning

See original phase descriptions in prior roadmap sections; APIs for
`voice_replacement` and `voice_clone` return HTTP 422 until tasks are added to `_TASK_MAP`.

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
# Current state (2026-06-18)
git log --oneline -5
# (Phase 5 staged — not yet committed)
# 47be178 Phase 4: karaoke generation complete   ← HEAD, phase4-karaoke-generation
# cd7133b Phase 3: subtitle burn-in complete
# 2f9f643 Phase 3: subtitle burn-in complete
# 19f8cc8 Finalize Phase 2 documentation and handoff
# 94f77e0 Phase 2 subtitle generation complete

git tag
# phase4-karaoke-generation   ← Phase 4 complete (current HEAD)
# phase3-subtitle-burn
# phase2-subtitles-working
# v0.1-foundation

# Suggested Phase 5 commit + tag
git add .
git commit -m "Phase 5: source separation, karaoke modes, and ML worker deps"
git tag -a phase5-source-separation -m "Phase 5: vocal separation + karaoke modes"
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
| `app/services/ffmpeg_service.py` | `_escape_filter_path()`, `extract_audio()`, `burn_subtitles()`, `burn_ass()`, `extract_stereo_wav()` |
| `app/services/source_separation_service.py` | Demucs subprocess; stderr in failure messages |
| `app/services/whisper_models.py` | Per-job whisper model resolution |
| `app/services/separation_models.py` | `htdemucs` whitelist |
| `app/services/karaoke_modes.py` | Karaoke `output_mode` validation |
| `app/models/stem_metadata.py` | `canonical` vs `inline` stem ownership |
| `app/services/redis_service.py` | Module-level singleton; connect via `worker_process_init` on persistent loop |
| `app/tasks/async_runner.py` | `get_worker_event_loop()`, `run_async()` — required for all Celery async work |
| `app/tasks/celery_app.py` | `worker_process_init` — connects Redis on worker loop |
| `app/tasks/media_tasks.py` | All task implementations; Phases 1–5 complete; M4 pending |
| `app/api/v1/endpoints/jobs.py` | Job endpoints + `/download/vocals`, `/download/instrumental` |
| `requirements-ml.txt` | Pinned torch/torchaudio/demucs for worker |

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

## 19. Phase 4 — Karaoke Generation: Architecture and Implementation Notes

Phase 4 is **complete**. This section documents the actual implementation,
replacing the pre-implementation planning notes that were here before.

### What karaoke generation produces

A video where each word is highlighted (changes colour) as it is spoken — the
same visual effect as karaoke machines. The underlying format is ASS (Advanced
SubStation Alpha), which supports per-word `\kf` fill-sweep timing tags that
SRT/VTT cannot express.

---

### A. Word-level timestamps — `--output-json-full` vs `--word-timestamps`

The implementation uses `--output-json-full` instead of the `--word-timestamps`
flag that was originally planned. They are different flags with different JSON
schemas:

| Flag | Schema | Availability |
|------|--------|--------------|
| `--word-timestamps 1` | Adds a `words` array directly to each segment | whisper.cpp ≥ mid-2024 |
| `--output-json-full` | Adds a `tokens` array (BPE-level) to each segment | whisper.cpp ≥ mid-2023 |

**Why `--output-json-full` was chosen:**
1. Broader compatibility — available on all whisper.cpp builds from 2023 onward,
   including the build at `tools/whisper.cpp/` on this machine.
2. Higher word-boundary quality — BPE tokens are grouped by the leading-space
   convention in `_tokens_to_words()`, which handles contractions and punctuation
   more cleanly than whisper.cpp's own grouper.

**BPE-to-word grouping (`_tokens_to_words`):**
- A token whose `text` starts with `" "` (space) marks the start of a new word.
- Tokens without a leading space are sub-word continuations appended to the
  current group (e.g. `" today"` + `"'s"` → `"today's"`).
- Bracket-wrapped tokens like `[_BEG_]` and `[_TT_250]` are skipped entirely —
  they are whisper.cpp internal timing markers, not transcribed text.

**Token offsets** — both segment-level offsets and per-token offsets are in
milliseconds in the JSON output. `_group_to_word()` converts to seconds.

---

### B. `to_ass()` — ASS karaoke subtitle generation

The `\kf` (karaoke fill) tag sweeps a highlight colour left-to-right through
each word syllable. Timing is expressed in centiseconds (ASS spec).

**Colour format:** ASS uses `&HAABBGGRR&` (alpha, blue, green, red).

| Colour | ASS value | Hex breakdown |
|--------|-----------|---------------|
| Yellow | `&H0000FFFF&` | A=00, B=00, G=FF, R=FF |
| White  | `&H00FFFFFF&` | A=00, B=FF, G=FF, R=FF |
| Black  | `&H00000000&` | all zero |

`PrimaryColour` (= `highlight_color`) is the colour the word sweeps **to**.
`SecondaryColour` (= `base_color`) is the colour words sit in before they are
reached. For the default yellow-on-white effect, set:
```
highlight_color = &H0000FFFF&   (yellow)
base_color      = &H00FFFFFF&   (white)
```

**Pre-roll empty `\kf` tag:**
When the first word starts later than `seg.start`, a silent `{\kfN}` tag is
emitted with no text after it, before the first word's `{\kfM}tag`.
Consecutive `\kf` tags with empty text between them are valid ASS; per the
spec, the empty "syllable" consumes N centiseconds without visual change.
This is a standard pattern in karaoke editors (Aegisub) and is handled
identically by libass (FFmpeg, VLC, MPV), DirectVobSub, and VSFilter.

---

### C. `burn_ass()` vs `burn_subtitles()`

`FFmpegService.burn_ass()` deliberately omits `force_style`. ASS files carry
their own `[V4+ Styles]` section; passing `force_style` would override the
`PrimaryColour`/`SecondaryColour` values that drive the karaoke `\kf` effect.
`burn_subtitles()` uses `force_style` legitimately because SRT has no
embedded styling.

Both methods call `_escape_filter_path()` for the same reason: the FFmpeg
`subtitles=` filter uses `:` as an option separator regardless of subtitle format.

---

### D. Karaoke job creation payload

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "karaoke",
  "parameters": {
    "language": "en",
    "highlight_color": "&H0000FFFF&",
    "base_color":      "&H00FFFFFF&",
    "font_name":       "Arial",
    "font_size":       24
  }
}
```

Download endpoints after completion:
```
GET /api/v1/jobs/{id}/download/ass           → <job_id>_karaoke.ass
GET /api/v1/jobs/{id}/download/karaoke-video → <job_id>_karaoke.mp4
GET /api/v1/jobs/{id}/result                 → same MP4 (generic endpoint)
```

---

### E. Known limitation — Whisper model accuracy on music

`ggml-tiny.en.bin` drops lyrics during long instrumental sections. The model
emits an `(upbeat music)` or similar placeholder for a few seconds and then
produces no further segments until the next clear vocal section. Gaps of 20–30 s
have been observed on music videos (confirmed in job `0e44f8ef-...`).

**This is not a bug in the karaoke pipeline.** The same gaps appear with
identical timestamps in `subtitle_generation` runs (using `--output-json`) on
the same audio. The karaoke renderer faithfully renders exactly what Whisper
transcribes.

**Mitigation:** Set `WHISPER_MODEL_PATH=models/ggml-base.en.bin` in `.env`.
The `ggml-base.en.bin` (142 MB) and `ggml-small.en.bin` (466 MB) models are
already downloaded at `backend/models/` and produce significantly better
results on overlapping music and vocals.

---

### F. Phase 4 git commands (when ready to commit)

```bash
git add .
git commit -m "Phase 4: karaoke generation

- --output-json-full + BPE token grouping for word-level timestamps
- TranscriptResult.to_ass() with \\kf karaoke timing
- FFmpegService.burn_ass() (no force_style — ASS carries own styles)
- karaoke_task: extract → transcribe → write ASS → burn MP4
- GET /jobs/{id}/download/ass and /download/karaoke-video endpoints
- IMPLEMENTED_JOB_TYPES guard: voice_replacement/voice_clone return 422"
git tag -a phase4-karaoke -m "Phase 4: karaoke generation complete"
```

---

*Last updated: 2026-06-18 — Phase 5 complete (pre-commit on `feature/source-separation`).*
