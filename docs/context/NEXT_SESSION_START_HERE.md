# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-20)

**Phases 1–5 are complete, committed, tagged, and pushed (production baseline).**

**Phase 6 Milestone 2 is complete** — `audio_enhance` pipeline implemented.

```
Phase 1: Upload → ffprobe → Media + Job persistence → Redis progress
Phase 2: subtitle_generation → whisper.cpp → SRT + VTT + TXT
Phase 3: subtitle_burn → FFmpeg H.264 burn-in → burned MP4
Phase 4: karaoke → word-level ASS → karaoke MP4 (with_vocals mode)
Phase 5: vocal_separation + all karaoke modes + separation_job_id reuse
Phase 6: audio_enhance → FFmpeg 48 kHz → deep-filter CLI → enhanced WAV
```

**Git state:** `feature/audio-enhancement` · Phase 5 baseline `phase5-final` @ `ddb2366`

---

## What to Do Next

Phase 6 M2 is complete. Next planned work is **Phase 7 (Text-to-Speech)** — not started.

Before running `audio_enhance` jobs:

1. Install/configure **`deep-filter` binary** — set `DEEPFILTER_BINARY` in `.env`
   (default: `deep-filter` on PATH, or `tools/experiments/bin/deep-filter` from PoC)
2. **Do not** `pip install deepfilternet` — see Integration Rules below
3. Celery worker: `pip install -r requirements-ml.txt` (Demucs only)
4. Restart workers after code changes

### Quick test — Audio enhancement

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

# Ensure deep-filter is available
deep-filter --version   # or path from DEEPFILTER_BINARY

MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/path/to/noisy_speech.wav" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"audio_enhance\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

until curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['status'] in ('completed','failed') else 1)" 2>/dev/null
do sleep 10; done

curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/enhanced"
```

See `docs/reports/PHASE6_M2_AUDIO_ENHANCEMENT_IMPLEMENTATION.md` for full validation procedure.

---

## DeepFilterNet Integration Rules

Project policy for Phase 6. Full document: `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`

### Dependency Protection

The validated Phase 5 ML stack is production baseline and must be preserved:

```text
torch==2.8.0+cpu
torchaudio==2.8.0+cpu
demucs==4.0.1
numpy==2.4.6
packaging==26.2
```

Do not upgrade, downgrade, or replace these packages as part of Phase 6.

### DeepFilterNet Installation Policy

DeepFilterNet integration **SHALL** use the `deep-filter` CLI binary.

The Python package (`pip install deepfilternet`) shall **NOT** be added to
`requirements.txt` or `requirements-ml.txt`.

### Approved Architecture

| System | Integration |
|--------|-------------|
| Whisper | whisper.cpp subprocess |
| Demucs | demucs subprocess |
| DeepFilterNet | `deep-filter` subprocess |

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
pip install -r requirements-ml.txt   # Demucs stack only — NOT deepfilternet
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 1 --loglevel INFO
```

---

## Key Files (Phase 6)

| File | Role |
|------|------|
| `app/services/audio_enhancement_service.py` | deep-filter subprocess wrapper |
| `app/services/ffmpeg_service.py` | `extract_enhancement_wav()` — 48 kHz mono prep |
| `app/tasks/media_tasks.py` | `audio_enhance_task` |
| `app/api/v1/endpoints/jobs.py` | `/download/enhanced` |
| `app/core/config.py` | `DEEPFILTER_BINARY`, `ENHANCEMENT_*` settings |
| `tools/experiments/deepfilternet_poc.py` | Isolated M1 PoC |

---

## Full Documentation

```
docs/context/MASTER_PROJECT_HANDOFF.md
docs/context/CURRENT_PROJECT_STATE.md
docs/reports/PHASE6_M2_AUDIO_ENHANCEMENT_IMPLEMENTATION.md
docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md
docs/reports/PHASE6_M1_DEEPFILTERNET_ANALYSIS.md
docs/reports/PHASE5_*.md
```
