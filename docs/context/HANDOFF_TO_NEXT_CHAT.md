---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Active branch is `feature/subtitle-burn`, not `feature/subtitle-pipeline`
> - Lists Phase 3 (subtitle burn-in) as "stub ready" — Phase 3 is complete as of `2f9f643`
> - Phase numbering (Phases 3–10) does not match the current approved roadmap
> - Celery command missing `--queues media,ai` (tasks will not execute without this)
> - API endpoint list is missing `GET /jobs/{id}/download/video` (added in Phase 3)
> - Job payload shows `"model": "base"` — not a valid parameter for the whisper.cpp backend
> - `.env` example shows `WHISPER_CPP_BINARY=whisper-cli` (PATH-based); actual value is the relative build path
> - "Next Steps" section is now obsolete — Phase 4 (Karaoke) is the next step
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` — single authoritative reference
> `docs/context/NEXT_SESSION_START_HERE.md` — quick-start for new sessions

---

# VoxClone — Handoff Document for New Cursor Session

> Copy the contents of this file and paste it at the start of a new Cursor chat.
> This document contains everything needed to continue VoxClone development.

---

## Project Identity

**Name:** VoxClone
**Type:** Offline-first AI media processing platform (FastAPI backend)
**Location:** `/home/shz/Documents/Mustafa projects/VoxClone`
**Backend:** `backend/` directory
**Active branch:** `feature/subtitle-pipeline`

---

## What VoxClone Does

Upload a video or audio file → choose a processing pipeline → download the result.

All AI runs **locally** with no cloud dependencies.

### Current Pipelines (Phase 2 — working)

| Job Type | Input | Output |
|----------|-------|--------|
| `audio_extraction` | Video | WAV audio |
| `subtitle_generation` | Video or Audio | .txt transcript + .srt + .vtt |
| `subtitle_burn` | Video + SRT | Video with burned subtitles |

### Planned Pipelines (Phases 3–10)

- Subtitle burn-in (Phase 3, stub ready)
- User-facing audio extraction (Phase 4)
- Karaoke / vocal removal via Demucs (Phase 5)
- Audio enhancement via DeepFilterNet (Phase 6)
- Text-to-speech via Piper (Phase 7)
- Voice replacement / dubbing (Phase 8)
- Voice cloning via OpenVoice (Phase 9)
- Voice conversion (Phase 10)

---

## Technology Stack

```
Language:    Python 3.12
Framework:   FastAPI + uvicorn
Database:    SQLite (aiosqlite) → PostgreSQL planned
ORM:         SQLAlchemy 2.x (fully async)
Task Queue:  Celery 5.x + Redis
Cache:       Redis (job progress)
AI:          whisper.cpp CLI (Phase 2, no PyTorch/CUDA), Demucs/Piper/OpenVoice (future)
Media:       FFmpeg
Logging:     structlog (JSON)
```

---

## Start the Backend (3 terminals)

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping  # → PONG

# Terminal 2: FastAPI
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery worker
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
```

Docs: `http://localhost:8000/docs`

---

## Core API Endpoints

Base: `http://localhost:8000/api/v1`

```
GET  /health                                     → system health
POST /uploads                                    → upload video/audio
GET  /media                                      → list uploads
GET  /media/{id}                                 → media metadata
POST /jobs                                       → create processing job
GET  /jobs/{id}                                  → job status + results
GET  /jobs/{id}/progress                         → live progress (Redis)
GET  /jobs/{id}/result                           → download primary output
GET  /jobs/{id}/download/transcript              → download .txt (subtitle jobs)
GET  /jobs/{id}/download/srt                     → download .srt
GET  /jobs/{id}/download/vtt                     → download .vtt
DELETE /jobs/{id}                                → cancel job
```

---

## Job Creation Payload

```json
POST /api/v1/jobs
{
    "media_id": "<uuid from /uploads>",
    "job_type": "subtitle_generation",
    "parameters": {
        "model": "base",
        "language": ""
    }
}
```

Allowed job_type values: `audio_extraction`, `subtitle_generation`, `subtitle_burn`, `karaoke`, `audio_enhance`, `voice_replacement`, `voice_clone`

---

## Key Source Files

| File | Role |
|------|------|
| `app/main.py` | FastAPI app factory |
| `app/core/config.py` | All settings (env vars) |
| `app/models/job.py` | Job DB model + JobType + JobStatus |
| `app/models/media.py` | Media DB model |
| `app/services/whisper_service.py` | whisper.cpp subprocess wrapper (Phase 2) |
| `app/services/ffmpeg_service.py` | FFmpeg wrapper |
| `app/services/job_service.py` | Job lifecycle CRUD |
| `app/tasks/media_tasks.py` | All Celery task implementations |
| `app/api/v1/endpoints/jobs.py` | Job API routes (including download) |

---

## Subtitle Pipeline Flow (Implemented)

```
POST /jobs {job_type: "subtitle_generation"}
    ↓
generate_subtitles_task(job_id) [Celery]
    ↓
FFmpegService.extract_audio(video → 16kHz WAV)  [if video input]
    ↓
WhisperService.transcribe(audio_path, language)  ← whisper.cpp subprocess
    → TranscriptResult {segments, language, text}
    ↓
result.to_txt()  → <job-id>_transcript.txt
result.to_srt()  → <job-id>_subtitles.srt
result.to_vtt()  → <job-id>_subtitles.vtt
    ↓
job.parameters.result_files = {transcript, srt, vtt}
job.result_path = srt path
job.status = "completed"
    ↓
GET /jobs/{id}/download/srt  → FileResponse
```

---

## Configuration (`.env`)

```bash
WHISPER_CPP_BINARY=whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin  # tiny.en | base.en | small.en
WHISPER_THREADS=4
WHISPER_LANGUAGE=en         # "en" for .en models
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db
UPLOAD_DIR=uploads
PROCESSED_DIR=processed
```

---

## Database (SQLite)

File: `backend/voxclone.db`

Two tables:
- `media` — uploaded files with ffprobe metadata
- `jobs` — processing jobs with status, progress, and `parameters` JSON

Multiple output paths stored in `jobs.parameters.result_files`:
```json
{"transcript": "/path/...", "srt": "/path/...", "vtt": "/path/..."}
```

No Alembic yet — `create_all` used on startup.

---

## Git State

```bash
git branch                    # → feature/subtitle-pipeline
git log --oneline -3          # → recent commits
git tag                       # → v0.1-foundation (Phase 1)
```

To commit Phase 2:
```bash
git add .
git commit -m "Phase 2 subtitle pipeline validated"
git push origin feature/subtitle-pipeline
```

---

## Next Steps (What to Implement Next)

**Phase 3 — Subtitle Burn-In** is the most natural next phase.

The `burn_subtitles_task` stub already exists in `media_tasks.py`.
`FFmpegService.burn_subtitles()` is already implemented.

Steps:
1. Update `burn_subtitles_task` to accept `subtitle_job_id` (reference Phase 2 job)
2. Look up `srt_path` from `prior_job.parameters.result_files.srt`
3. Call `ffmpeg.burn_subtitles(video_path, srt_path, output_path)`
4. Return burned video

**Before running subtitles, install whisper.cpp:**
`docs/testing/WHISPER_CPP_SETUP.md`

**Then run the full Phase 2 validation:**
`docs/testing/PHASE2_MANUAL_TESTING.md`

---

## Documentation Index

```
docs/
├── testing/
│   ├── WHISPER_CPP_SETUP.md         # Install whisper.cpp + download models
│   ├── PHASE2_TEST_PLAN.md          # Test strategy and test IDs
│   ├── PHASE2_MANUAL_TESTING.md     # Step-by-step curl commands
│   └── PHASE2_EXPECTED_RESULTS.md   # Expected API responses
├── reports/
│   └── PHASE2_COMPLETION_REPORT.md  # What was built in Phase 2
└── context/
    ├── VOXCLONE_PROJECT_CONTEXT.md  # Full architecture reference
    ├── NEXT_PHASES_ROADMAP.md       # Phases 3–12 planning
    ├── GIT_CHECKPOINT.md            # Git commit instructions
    └── HANDOFF_TO_NEXT_CHAT.md      # This file
```
