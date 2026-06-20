# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-18)

**Phases 1–5 are complete, committed, tagged, and pushed.**

```
Phase 1: Upload → ffprobe → Media + Job persistence → Redis progress
Phase 2: subtitle_generation → whisper.cpp → SRT + VTT + TXT
Phase 3: subtitle_burn → FFmpeg H.264 burn-in → burned MP4
Phase 4: karaoke → word-level ASS → karaoke MP4 (with_vocals mode)
Phase 5: vocal_separation + all karaoke modes + separation_job_id reuse
```

**Git state:** `feature/source-separation` · HEAD `ddb2366` · tags `phase5-source-separation` (`c0f67c5`), `phase5-complete` / `phase5-final` (`ddb2366`) · pushed to `origin`

---

## What to Do Next

### Before starting Phase 6

1. **Restart Celery workers** if code changed since last deploy — `async_runner` loop is created at process start.
2. **Install ML deps** on worker hosts if not already: `pip install -r requirements-ml.txt`

### Recommended next development work

**Phase 6 — Audio Enhancement:**

- Implement DeepFilterNet in `audio_enhance_task` (currently dispatches then marks failed)

See `docs/context/MASTER_PROJECT_HANDOFF.md` Section 13 for the full roadmap.

---

## Start the Backend

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping   # → PONG

# Terminal 2: FastAPI
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery (both queues; concurrency=1 when running Demucs)
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
pip install -r requirements-ml.txt   # worker only — first time or after ML dep changes
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 1 --loglevel INFO
```

API docs: http://localhost:8000/docs

---

## Quick Test — Vocal Separation (Phase 5)

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/song.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"vocal_separation\",\
\"parameters\":{\"separation_model\":\"htdemucs\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

until curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['status'] in ('completed','failed') else 1)" 2>/dev/null
do sleep 10; done

curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/vocals"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/instrumental"
```

---

## Key Files (Phase 5)

| File | Role |
|------|------|
| `app/tasks/async_runner.py` | Persistent worker event loop — **do not use `asyncio.run()` in tasks** |
| `app/tasks/celery_app.py` | Redis connect on worker loop via `get_worker_event_loop()` |
| `app/services/source_separation_service.py` | Demucs subprocess wrapper |
| `app/services/separation_models.py` | `htdemucs` whitelist |
| `app/services/karaoke_modes.py` | Karaoke `output_mode` validation (4 modes) |
| `app/services/stem_reuse.py` | Canonical stem reuse via `separation_job_id` |
| `app/services/whisper_models.py` | Per-job whisper model aliases + defaults |
| `app/models/stem_metadata.py` | `canonical` vs `inline` stem ownership |
| `requirements-ml.txt` | Pinned torch/torchaudio/demucs |
| `app/api/v1/endpoints/jobs.py` | `/download/vocals`, `/download/instrumental` |

---

## Full Documentation

```
docs/context/MASTER_PROJECT_HANDOFF.md    ← authoritative reference (all phases)
docs/context/CURRENT_PROJECT_STATE.md     ← component status + validation evidence
docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md
docs/reports/PHASE5_*.md                  ← Phase 5 milestone reports
docs/reports/PHASE5_DOCUMENTATION_SYNC.md ← Phase 5 doc/git alignment (pre–Phase 6)
docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md
```
