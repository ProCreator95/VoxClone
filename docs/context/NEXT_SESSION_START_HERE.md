# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-14)

**Phases 1, 2, and 3 are complete and fully validated.**

```
Phase 1: Upload → ffprobe metadata → Media + Job persistence → Redis progress
Phase 2: Upload video → generate_subtitles_task → whisper.cpp → SRT + VTT + TXT
Phase 3: subtitle_generation job → burn_subtitles_task → FFmpeg H.264 → burned MP4
```

**Git state:** `feature/subtitle-burn` · `2f9f643` · tag `phase3-subtitle-burn` · clean working tree

---

## All Bugs Fixed (Phases 2–3)

| # | Bug | Fix | Commit |
|---|-----|-----|--------|
| 1 | Redis not connected in Celery workers | `worker_process_init` signal in `celery_app.py` | `94f77e0` |
| 2 | `MissingGreenlet` on `job.media` lazy-load | `get_by_id_with_media()` with `selectinload` in `job_service.py` | `94f77e0` |
| 3 | `libwhisper.so.1 not found` | `_build_subprocess_env()` in `whisper_service.py` | `94f77e0` |
| 4 | FFmpeg filter path not escaped (space in project path) | `_escape_filter_path()` in `ffmpeg_service.py` | `2f9f643` |
| 5 | No explicit video codec in burn command | `-c:v libx264 -crf 23 -preset fast` in `ffmpeg_service.py` | `2f9f643` |

---

## What to Do Next

**Phase 4 — Karaoke Generation** is the next recommended step.

Karaoke generation produces word-level highlighted subtitles burned into video.
Each word lights up in sync with speech — same visual effect as karaoke machines.

### Phase 4 implementation checklist

1. Add `--word-timestamps` flag to `WhisperService.transcribe()`
2. Add `TranscriptResult.to_ass()` — generate Advanced SubStation Alpha format with per-word highlight style
3. Implement `karaoke_task` in `media_tasks.py` (full replacement of the current stub):
   - Extract audio (same as subtitle generation)
   - Transcribe with word-level timestamps
   - Generate `.ass` file with highlight colours
   - Burn `.ass` into video via FFmpeg
4. Add `GET /jobs/{id}/download/ass` endpoint
5. Add `GET /jobs/{id}/download/video` endpoint (re-use pattern from Phase 3)

See the "How to Start Phase 4" section in `docs/context/MASTER_PROJECT_HANDOFF.md` for the full architectural spec.

---

## Start the Backend

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping   # → PONG

# Terminal 2: FastAPI
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery  (both queues required)
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 2 --loglevel INFO
```

API docs: http://localhost:8000/docs

---

## Run a Full Phase 2 + 3 Pipeline Test

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

# 1. Upload a video
MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/video.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Generate subtitles (Phase 2)
SUBTITLE_JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Poll until completed
until curl -s "http://localhost:8000/api/v1/jobs/$SUBTITLE_JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['status'] in ('completed','failed') else 1)" 2>/dev/null
do sleep 5; done

# 3. Burn subtitles (Phase 3)
BURN_JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_burn\",\
\"parameters\":{\"subtitle_job_id\":\"$SUBTITLE_JOB_ID\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Poll until completed
until curl -s "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['status'] in ('completed','failed') else 1)" 2>/dev/null
do sleep 3; done

# 4. Download all outputs
curl -O -J "http://localhost:8000/api/v1/jobs/$SUBTITLE_JOB_ID/download/srt"
curl -O -J "http://localhost:8000/api/v1/jobs/$SUBTITLE_JOB_ID/download/vtt"
curl -O -J "http://localhost:8000/api/v1/jobs/$SUBTITLE_JOB_ID/download/transcript"
curl -O -J "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/download/video"

# 5. Verify burned video
ffprobe processed/${BURN_JOB_ID}_subtitled.mp4 2>&1 | grep -E "Duration|Video:|Audio:"
# Expected: Video: h264 ... Audio: opus (or source codec)
```

---

## Reuse Phase 3 Validated IDs

```bash
# Already validated — no need to re-run if files still exist on disk
MEDIA_ID="da763e0f-57f6-4317-b83d-b926fe25fb21"
SUBTITLE_JOB_ID="ac849d78-fe28-4448-b029-a5c79a83ef94"
BURN_JOB_ID="c4263f06-ef6d-4005-91e8-d422fb00be26"

# Download burned video directly
curl -O -J "http://localhost:8000/api/v1/jobs/$BURN_JOB_ID/download/video"
```

---

## Key Files

| File | Role |
|------|------|
| `app/tasks/celery_app.py` | Celery app config + `worker_process_init` Redis hook |
| `app/tasks/media_tasks.py` | All Celery tasks — Phases 1–3 implemented, Phases 4+ stubbed |
| `app/services/ffmpeg_service.py` | FFmpeg wrapper — `_escape_filter_path()`, `burn_subtitles()` |
| `app/services/whisper_service.py` | whisper.cpp subprocess + `LD_LIBRARY_PATH` setup |
| `app/services/job_service.py` | Job lifecycle; `get_by_id_with_media()` for eager loading |
| `app/services/redis_service.py` | Redis singleton + progress cache |
| `app/api/v1/endpoints/jobs.py` | All job + download endpoints including `download/video` |
| `app/database/session.py` | `get_db_context()` — async context manager for Celery tasks |
| `backend/.env` | Active configuration |

---

## Full Documentation

```
docs/context/MASTER_PROJECT_HANDOFF.md    ← single authoritative reference for all phases
docs/context/CURRENT_PROJECT_STATE.md     ← current component status + Phase 3 validation
docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md
docs/testing/WHISPER_CPP_SETUP.md
```
