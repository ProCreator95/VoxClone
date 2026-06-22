# Phase 6 — Milestone 2: Audio Enhancement Production Integration

**Status:** Complete  
**Date:** 2026-06-20  
**Branch:** `feature/audio-enhancement`  
**Baseline:** Phase 5 production (`phase5-final` @ `ddb2366`)

---

## Summary

Implemented production-ready speech noise reduction via the **`deep-filter` CLI
subprocess**. The `audio_enhance` job type now runs a full pipeline: FFmpeg
preprocessing to 48 kHz mono WAV, DeepFilterNet enhancement, metadata persistence,
and a typed download endpoint.

**Policy compliance:** No changes to `requirements.txt`, `requirements-ml.txt`, or
Phase 5 ML pins. No `deepfilternet` Python package.

---

## Architecture

```
POST /jobs { job_type: "audio_enhance", media_id }
  → Celery ai queue → audio_enhance_task
  → FFmpegService.extract_enhancement_wav()  → processed/<id>_enhancement_input.wav
  → AudioEnhancementService.enhance()        → deep-filter subprocess
  → processed/<id>_enhanced.wav
  → GET /jobs/{id}/download/enhanced
```

| Layer | Integration |
|-------|-------------|
| Whisper | whisper.cpp subprocess (unchanged) |
| Demucs | demucs subprocess (unchanged) |
| DeepFilterNet | `deep-filter` subprocess (new) |

All ML systems remain isolated — no shared Python ML imports in Celery workers.

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/services/audio_enhancement_service.py` | **New** — validate, subprocess, stderr capture, temp cleanup |
| `backend/app/services/ffmpeg_service.py` | `extract_enhancement_wav()` — 48 kHz mono PCM |
| `backend/app/core/config.py` | `DEEPFILTER_BINARY`, `ENHANCEMENT_SAMPLE_RATE`, `ENHANCEMENT_CHANNELS` |
| `backend/.env.example` | Matching enhancement settings |
| `backend/app/tasks/media_tasks.py` | `audio_enhance_task` — full pipeline |
| `backend/app/api/v1/endpoints/jobs.py` | `GET /jobs/{id}/download/enhanced` (before catch-all route) |
| `docs/context/MASTER_PROJECT_HANDOFF.md` | Phase 6 M2 status, endpoint, architecture |
| `docs/context/CURRENT_PROJECT_STATE.md` | Component table updated |
| `docs/context/NEXT_SESSION_START_HERE.md` | M2 complete, test commands |

**Unchanged:** Celery routing, Redis progress, Phase 5 endpoints/behaviour, ML requirements pins.

---

## API

### Create job

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "audio_enhance"
}
```

### Completed job parameters

```json
{
  "enhancement_backend": "deep-filter-cli",
  "input_sample_rate": 48000,
  "input_channels": 1,
  "duration_seconds": 120.5,
  "intermediate_files": {
    "enhancement_input": "/abs/processed/<job_id>_enhancement_input.wav"
  },
  "result_files": {
    "enhanced_audio": "/abs/processed/<job_id>_enhanced.wav"
  }
}
```

`result_path` → `enhanced_audio` WAV.

### Download

```
GET /api/v1/jobs/{id}/download/enhanced   → audio/wav
GET /api/v1/jobs/{id}/result               → same file (generic)
```

---

## Configuration

```bash
# backend/.env
DEEPFILTER_BINARY=deep-filter                    # or absolute path to v0.5.6 binary
ENHANCEMENT_SAMPLE_RATE=48000
ENHANCEMENT_CHANNELS=1
```

PoC binary location: `backend/tools/experiments/bin/deep-filter`

---

## Validation procedure

### Prerequisites

```bash
cd backend && source .venv/bin/activate
deep-filter --version    # must print deep_filter 0.5.6 (or compatible)
redis-server --daemonize yes
```

Set `DEEPFILTER_BINARY` if binary is not on PATH.

### 1. Import / route checks

```bash
python -c "
from app.services.audio_enhancement_service import AudioEnhancementService
from app.tasks.media_tasks import _TASK_MAP
assert 'audio_enhance' in _TASK_MAP
print('OK')
"
```

### 2. ML pin verification

```bash
pip show torch torchaudio demucs numpy packaging | grep -E '^(Name|Version):'
# torch 2.8.0+cpu, torchaudio 2.8.0+cpu, demucs 4.0.1, numpy 2.4.6, packaging 26.2
grep -i deepfilter requirements.txt requirements-ml.txt || echo "OK: not in requirements"
```

### 3. End-to-end job (requires running API + Celery)

```bash
# Upload audio/video → POST audio_enhance job → poll progress → download enhanced
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/enhanced"
```

**Success criteria:**

- `status=completed`, `progress=100`
- `parameters.result_files.enhanced_audio` exists on disk
- `parameters.intermediate_files.enhancement_input` recorded
- Enhanced WAV size > 0
- Phase 5 jobs (subtitle, karaoke, vocal_separation) still work unchanged

### 4. Progress stages (observed via `/jobs/{id}/progress`)

| Progress | Step |
|----------|------|
| 10 | Loading job |
| 20 | Preparing audio |
| 40 | Running FFmpeg preprocessing |
| 70 | Running DeepFilterNet |
| 90 | Validating output |
| 100 | Completed |

---

## Structured logging events

| Event | When |
|-------|------|
| `diag_audio_enhance_start` | Task entry |
| `diag_audio_enhance_prepare_audio` | After media validation |
| `diag_audio_enhance_preprocess_complete` | After FFmpeg |
| `diag_audio_enhance_subprocess_start` | Before deep-filter |
| `diag_audio_enhance_subprocess_complete` | After successful enhancement |
| `diag_audio_enhance_validate_output` | Before mark_completed |
| `diag_audio_enhance_completed` | Task success |
| `diag_audio_enhance_failed` | Pipeline failure (includes stderr when available) |

---

## Known limitations

| Limitation | Notes |
|------------|-------|
| **Speech-focused model** | Not recommended for music, karaoke, or instrumental stems |
| **48 kHz mono input required** | FFmpeg resamples automatically; output is 48 kHz mono |
| **Binary deployment** | Worker must have `deep-filter` v0.5.6 accessible via `DEEPFILTER_BINARY` |
| **x86_64 musl binary validated** | PoC used `x86_64-unknown-linux-musl`; aarch64 needs separate release asset |
| **No `post_filter` parameter yet** | CLI supports `--pf`; not exposed in M2 API |
| **No `source_job_id` reuse** | Enhancement always runs on uploaded media (deferred) |
| **Long files** | RTF ≈ 0.8–1.3× realtime on one CPU core; no chunked progress inside deep-filter |
| **Route ordering** | `/download/enhanced` declared before `/download/{format_type}` (Bug 6) |

---

## Remaining Phase 6 work (future)

- Optional `post_filter` job parameter (`--pf`)
- `source_job_id` / canonical vocals stem input reuse
- Platform-aware binary selection in deployment docs
- Binary checksum verification on download
- End-to-end validation job ID recorded in this report when manual run completes

---

## Related documents

- `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md` — integration policy
- `docs/reports/PHASE6_M1_DEEPFILTERNET_ANALYSIS.md` — M1 design
- `docs/reports/PHASE6_M1_VERIFICATION_AUDIT.md` — M1 audit

---

*Milestone 2 complete. Phase 7 not started.*
