# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-14)

**Phase 2 is complete and working.** The subtitle pipeline runs end-to-end:

```
Upload video → generate_subtitles_task → whisper.cpp → SRT + VTT + TXT files → download
```

All three Phase 2 bugs have been fixed and committed:

| Bug | Fix | Commit |
|-----|-----|--------|
| Redis not connected in Celery workers | `worker_process_init` signal in `celery_app.py` | `94f77e0` |
| `MissingGreenlet` on `job.media` lazy-load | `get_by_id_with_media()` with `selectinload` in `job_service.py` | `94f77e0` |
| `libwhisper.so.1 not found` | `_build_subprocess_env()` sets `LD_LIBRARY_PATH` in `whisper_service.py` | `94f77e0` |

**Git state:** `feature/subtitle-pipeline` · `94f77e0` · tag `phase2-subtitles-working` · clean working tree

---

## What to Do Next

**Phase 3 — Subtitle Burn-In** is the most natural next step.

- `burn_subtitles_task` stub already exists in `app/tasks/media_tasks.py`
- `FFmpegService.burn_subtitles()` is already implemented in `app/services/ffmpeg_service.py`
- See `docs/context/NEXT_PHASES_ROADMAP.md` for the full spec

### Phase 3 implementation checklist

1. Update `burn_subtitles_task` in `media_tasks.py`:
   - Accept `subtitle_job_id` in parameters — look up `srt_path` from prior job's `parameters.result_files.srt`
   - Call `ffmpeg.burn_subtitles(video_path, srt_path, output_path)`
   - Return burned video at `GET /jobs/{id}/result`
2. Optionally expose subtitle style parameters (font size, color, position)
3. Test: upload MP4 → generate subtitles → burn subtitles → inspect output video

---

## Start the Backend

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping   # → PONG

# Terminal 2: FastAPI
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery  (both queues required — tasks route to media or ai queue)
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 2 --loglevel INFO
```

---

## Run a Subtitle Job (end-to-end test)

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/video.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Poll until completed
watch -n 5 "curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/progress | python3 -m json.tool"

# Download results
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/vtt"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/transcript"
```

---

## Key Files

| File | Role |
|------|------|
| `app/tasks/celery_app.py` | Celery app config + `worker_process_init` Redis hook |
| `app/tasks/media_tasks.py` | All Celery tasks (subtitle pipeline + stubs) |
| `app/services/whisper_service.py` | whisper.cpp subprocess + `LD_LIBRARY_PATH` setup |
| `app/services/job_service.py` | Job lifecycle; `get_by_id_with_media()` for eager loading |
| `app/services/redis_service.py` | Redis singleton + progress cache |
| `app/database/session.py` | `get_db_context()` — now logs rollback events |
| `backend/.env` | Active configuration |

---

## Active .env (key values)

```bash
WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_THREADS=8
WHISPER_LANGUAGE=en
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db
```

---

## Full Documentation

```
docs/context/MASTER_PROJECT_HANDOFF.md   ← complete self-contained reference
docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md
docs/context/NEXT_PHASES_ROADMAP.md
docs/testing/WHISPER_CPP_SETUP.md
```
