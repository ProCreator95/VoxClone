# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-22)

**Phases 1–6 are complete.** **Phase 7 Milestone 2 is complete and validated** — multilingual Whisper routing.

```
Phase 1: Upload → ffprobe → Media + Job persistence → Redis progress
Phase 2: subtitle_generation → whisper.cpp → SRT + VTT + TXT
Phase 3: subtitle_burn → FFmpeg H.264 burn-in → burned MP4
Phase 4: karaoke → word-level ASS → karaoke MP4 (with_vocals mode)
Phase 5: vocal_separation + all karaoke modes + separation_job_id reuse
Phase 6: audio_enhance → FFmpeg 48 kHz → deep-filter CLI → enhanced WAV
Phase 7: multilingual Whisper routing — language-first model selection (M2 validated)
```

**Git state:** `feature/whisper-multilingual`

---

## What to Do Next

Phase 7 M2 is validated. Next planned work is **Phase 7 Milestone 3** (Urdu quality / model benchmark) or **Phase 7 M4** (Roman Urdu transliteration — design only today).

### Quick test — Urdu subtitles

Requires multilingual models (`ggml-base.bin` or `ggml-small.bin`) in `backend/models/`.

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate

JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"<MEDIA_UUID>\",\"job_type\":\"subtitle_generation\",\"parameters\":{\"language\":\"ur\",\"whisper_model\":\"small\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Poll until completed, then verify parameters:
curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID" | python3 -m json.tool
# Expect: whisper_model_file=ggml-small.bin, whisper_model_variant=multilingual, detected_language=ur
```

**Mixed English + Urdu media:** use `"language": "auto"`.

**English-only (default):** omit `language` — `WHISPER_ROUTING_POLICY=english_first` preserves Phase 5 behaviour.

See `docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md` for validation evidence.

---

## Whisper routing (Phase 7)

| `parameters.language` | Model | CLI flag |
|----------------------|-------|----------|
| omitted (default policy) | `ggml-{tier}.en.bin` | `-l en` |
| `"en"` | `ggml-{tier}.en.bin` | `-l en` |
| `"ur"`, `"hi"`, etc. | `ggml-{tier}.bin` | `-l <code>` |
| `"auto"` | `ggml-{tier}.bin` | omit `-l` |

Config: `WHISPER_ROUTING_POLICY=english_first` (default).

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

## Key Files (Phase 7)

| File | Role |
|------|------|
| `app/services/whisper_models.py` | Language-first routing, dual model registry |
| `app/services/whisper_service.py` | Subprocess; uses resolved `cli_language` |
| `app/schemas/job.py` | Validates `parameters.language` on Whisper jobs |
| `app/core/config.py` | `WHISPER_ROUTING_POLICY` |
| `tests/test_whisper_models.py` | Routing unit tests (13 cases) |

---

## Integration Rules (unchanged)

| System | Integration |
|--------|-------------|
| Whisper | whisper.cpp subprocess |
| Demucs | demucs subprocess |
| DeepFilterNet | `deep-filter` subprocess |

Full Phase 6 policy: `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`

---

## Full Documentation

```
docs/context/MASTER_PROJECT_HANDOFF.md
docs/context/CURRENT_PROJECT_STATE.md
docs/reports/PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md
docs/reports/PHASE7_M2_MULTILINGUAL_ROUTING_IMPLEMENTATION.md
docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md
docs/reports/PHASE6_M2_VALIDATION_REPORT.md
docs/reports/PHASE5_*.md
docs/testing/WHISPER_CPP_SETUP.md
```
