---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Written when `openai-whisper` (Python package) was the planned backend
> - Final implementation uses whisper.cpp CLI exclusively — `openai-whisper` is not installed
> - Config schema described here (`WHISPER_BACKEND`, `WHISPER_MODEL`, `WHISPER_MODELS_DIR`) does not match `config.py`
> - "Files Modified" list predates the Phase 2 bug fixes (`celery_app.py`, `job_service.py`, `whisper_service.py`)
> - "Known Limitations" section describes limitations that were fixed before Phase 2 was validated
> - `requirements.txt` change adding `openai-whisper` was reverted; whisper.cpp needs no Python dependency
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Sections 9, 10, 17 — Phase 2 implementation and validation)

---

# Phase 2 Completion Report — Whisper Subtitle Pipeline

**Date:** June 13, 2026
**Phase:** 2.1 — Subtitle Generation Pipeline
**Status:** Implementation Complete

---

## Summary

Phase 2 delivers the first real AI feature of VoxClone: automatic subtitle generation powered by OpenAI Whisper. A user can upload any video, trigger a single API call, and receive a fully timed transcript in SRT, VTT, and plain-text formats.

---

## Features Implemented

### Core Pipeline

| Feature | Description |
|---------|-------------|
| Audio extraction | FFmpeg extracts 16kHz mono WAV from video for Whisper |
| Whisper transcription | openai-whisper Python package as default backend |
| whisper.cpp support | Optional high-performance CLI backend (configurable) |
| Transcript output | Plain-text transcript (.txt) |
| SRT generation | SubRip subtitle format (.srt) with proper timestamps |
| VTT generation | WebVTT subtitle format (.vtt) for web players |
| Language detection | Automatic language detection via Whisper |
| Multiple output storage | All three paths stored in `job.parameters.result_files` |

### API Endpoints Added

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/jobs/{id}/download/transcript` | Download .txt transcript |
| GET | `/api/v1/jobs/{id}/download/srt` | Download .srt subtitle file |
| GET | `/api/v1/jobs/{id}/download/vtt` | Download .vtt subtitle file |

### Existing Endpoints (unchanged, now fully operational for subtitles)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/jobs` | Create subtitle_generation job |
| GET | `/api/v1/jobs/{id}` | Get job status + result_files |
| GET | `/api/v1/jobs/{id}/progress` | Live progress from Redis |
| GET | `/api/v1/jobs/{id}/result` | Download primary result (SRT) |

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/app/services/whisper_service.py` | Core WhisperService, TranscriptResult, SRT/VTT/TXT converters |

## Files Modified

| File | Change |
|------|--------|
| `backend/app/tasks/media_tasks.py` | Replaced placeholder `generate_subtitles_task` with full Whisper pipeline |
| `backend/app/api/v1/endpoints/jobs.py` | Added 3 subtitle format download endpoints |
| `backend/app/core/config.py` | Added 6 Whisper configuration settings |
| `backend/requirements.txt` | Added `openai-whisper` dependency |
| `backend/.env.example` | Added Whisper environment variable documentation |

## Documentation Files Created

| File | Purpose |
|------|---------|
| `docs/testing/PHASE2_TEST_PLAN.md` | Test strategy and test ID matrix |
| `docs/testing/PHASE2_MANUAL_TESTING.md` | Step-by-step curl commands |
| `docs/testing/PHASE2_EXPECTED_RESULTS.md` | Exact expected API responses and file formats |
| `docs/reports/PHASE2_COMPLETION_REPORT.md` | This document |
| `docs/context/VOXCLONE_PROJECT_CONTEXT.md` | Full project context for new chat sessions |
| `docs/context/NEXT_PHASES_ROADMAP.md` | Future phase planning |
| `docs/context/GIT_CHECKPOINT.md` | Git commit and push instructions |
| `docs/context/HANDOFF_TO_NEXT_CHAT.md` | Master handoff document |

---

## Architecture Changes

### New Service Layer

**`WhisperService`** (`app/services/whisper_service.py`):
- `async def transcribe(audio_path, model, language) → TranscriptResult`
- Supports two backends: `openai` (Python package) and `cpp` (CLI binary)
- CPU-bound Python whisper runs in thread executor to avoid blocking the event loop
- `TranscriptResult.to_srt()`, `.to_vtt()`, `.to_txt()` pure conversion methods

### Celery Task Updates

`generate_subtitles_task` now implements the full pipeline:
1. Extracts audio from video if needed (reusing existing `FFmpegService.extract_audio`)
2. Runs `WhisperService.transcribe()`
3. Writes three output files to `PROCESSED_DIR`
4. Updates `job.parameters` with `result_files`, `detected_language`, `segment_count`
5. Sets `job.result_path` to SRT (primary output for backward compatibility)

### Configuration

New settings added to `Settings`:
```
WHISPER_BACKEND = "openai"    # "openai" | "cpp"
WHISPER_MODEL = "base"        # tiny|base|small|medium|large-v3
WHISPER_LANGUAGE = ""         # empty = auto-detect
WHISPER_CPP_BINARY = "whisper-cli"
WHISPER_MODELS_DIR = Path("models")
WHISPER_THREADS = 4
```

---

## Database Changes

**No schema changes** — existing `Job.parameters` JSON column stores all new subtitle metadata:

```json
{
  "model": "base",
  "language": "",
  "result_files": {
    "transcript": "/path/to/processed/<job-id>_transcript.txt",
    "srt": "/path/to/processed/<job-id>_subtitles.srt",
    "vtt": "/path/to/processed/<job-id>_subtitles.vtt"
  },
  "detected_language": "en",
  "segment_count": 12
}
```

The existing `result_path` field points to the SRT file for backward compatibility with the generic `/result` endpoint.

---

## API Changes

### New Endpoint: `GET /api/v1/jobs/{job_id}/download/{format_type}`

**format_type:** `transcript` | `srt` | `vtt`

**Response:** `FileResponse` with appropriate MIME type
- `transcript` → `text/plain`, filename `<job-id>.txt`
- `srt` → `text/plain`, filename `<job-id>.srt`
- `vtt` → `text/vtt`, filename `<job-id>.vtt`

**Error cases:**
- Job not found → 404
- Job not completed → 404 (result_not_ready)
- Wrong job_type → 400
- File deleted from disk → 404

---

## Known Limitations

1. **No streaming progress** — Whisper transcription progress is reported in bulk steps (25% → 70%), not word-by-word. This is a limitation of the Whisper API.

2. **CPU-only by default** — The `openai-whisper` backend runs on CPU. For GPU acceleration, install `torch` with CUDA support. whisper.cpp backend can use Metal (macOS) or CUDA.

3. **Model download on first use** — The first `subtitle_generation` job triggers a Whisper model download (~140MB for `base`). Subsequent runs use the cached model.

4. **Audio files** — If the uploaded media is an audio file (not video), it is passed directly to Whisper without re-encoding. Whisper supports WAV, MP3, and most audio formats natively.

5. **No word-level timestamps** — Segment-level timestamps only. Word-level timestamps are available in Whisper but not currently exposed.

6. **No subtitle editing API** — Generated subtitles are write-once. To edit, download and modify externally.

---

## Future Improvements

1. Add word-level timestamp support via `word_timestamps=True` Whisper option
2. Stream Whisper progress via WebSocket or SSE
3. Add subtitle burn-in (Phase 3) as a follow-up job type
4. Cache loaded Whisper models across Celery tasks to avoid re-loading
5. Support batch transcription of multiple media files
6. Add subtitle format validation endpoint
7. Support custom vocabulary / prompt injection for Whisper
8. Expose `WhisperService.list_available_models()` via API endpoint

---

## Phase 2 Validation Commands (Quick Reference)

```bash
# 1. Start services
redis-server --daemonize yes
uvicorn app.main:app --reload --port 8000 &
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 &

# 2. Health check
curl -s http://localhost:8000/api/v1/health

# 3. Upload video
MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@tests/fixtures/test_video.mp4" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Create subtitle job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 5. Poll until completed
until curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/progress \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['status']=='completed' else 1)"; do
  sleep 5; echo "Waiting..."
done

# 6. Download results
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/transcript"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt"
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/download/vtt"
```
