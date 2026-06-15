# VoxClone — Current Project State

**Date:** 2026-06-15
**Branch:** `feature/karaoke-generation`
**Last commit:** `2f9f643 Phase 3: subtitle burn-in complete` (Phase 4 staged, pre-commit engineering review in progress)
**Tags:** `v0.1-foundation` (Phase 1) · `phase2-subtitles-working` (Phase 2) · `phase3-subtitle-burn` (Phase 3)

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

### Active `.env` Settings

```
WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_THREADS=8
WHISPER_LANGUAGE=en
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
```

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
│   │   │   │   └── jobs.py         POST/GET /jobs + all download endpoints
│   │   │   └── router.py
│   │   ├── core/
│   │   │   ├── config.py           All settings (pydantic-settings)
│   │   │   ├── exceptions.py       Domain exceptions + FastAPI handlers
│   │   │   └── logging.py          structlog JSON setup
│   │   ├── database/
│   │   │   ├── session.py          Async engine, get_db_context()
│   │   │   └── init_db.py          create_tables() on startup
│   │   ├── models/
│   │   │   ├── media.py            Media SQLAlchemy model
│   │   │   └── job.py              Job model + JobType + JobStatus
│   │   ├── schemas/
│   │   │   ├── job.py              JobCreate, JobResponse
│   │   │   └── media.py            MediaResponse
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py   FFmpeg wrapper (probe, extract, burn) — Phase 3 updated
│   │   │   ├── job_service.py      Job lifecycle; get_by_id_with_media() for eager loading
│   │   │   ├── media_service.py    Media CRUD
│   │   │   ├── redis_service.py    Redis singleton + progress cache
│   │   │   ├── upload_service.py   File ingestion pipeline
│   │   │   └── whisper_service.py  whisper.cpp subprocess wrapper
│   │   ├── tasks/
│   │   │   ├── celery_app.py       Celery app config + worker_process_init Redis hook
│   │   │   └── media_tasks.py      All Celery tasks (Phase 3 burn task complete)
│   │   └── main.py                 FastAPI app factory + lifespan
│   ├── uploads/                    Uploaded media files
│   ├── processed/                  Pipeline output files
│   ├── models/                     GGML model files
│   ├── .env                        Active configuration
│   ├── .env.example                Configuration template
│   └── requirements.txt
├── docs/
│   ├── context/                    ← you are here
│   ├── testing/
│   └── reports/
└── tools/
    └── whisper.cpp/                whisper.cpp source + built binary
```

---

## Component Status

### Phase 1 — Foundation ✅ COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI startup | ✅ | Lifespan connects Redis, creates DB tables |
| `GET /health` | ✅ | Returns `{status: ok, database: ok, redis: ok}` |
| File upload | ✅ | `POST /uploads` multipart, validates extension, streams to disk |
| FFprobe metadata | ✅ | Duration, codec, resolution, sample rate extracted |
| Media CRUD | ✅ | `GET /media`, `GET /media/{id}`, `DELETE /media/{id}` |
| Job creation | ✅ | `POST /jobs` creates DB record, dispatches Celery task |
| Job status polling | ✅ | `GET /jobs/{id}`, `GET /jobs/{id}/progress` |
| Redis progress cache | ✅ | Set on job create; polled by `/progress` endpoint |
| Celery task dispatch | ✅ | Tasks received and executed by worker |
| Download endpoint | ✅ | `GET /jobs/{id}/result` returns FileResponse |

### Phase 2 — Subtitle Generation ✅ COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| `WhisperService` | ✅ | whisper.cpp subprocess, validates binary + model |
| `_build_subprocess_env()` | ✅ | Sets `LD_LIBRARY_PATH` for whisper.cpp shared libs |
| `TranscriptResult` | ✅ | `.to_srt()`, `.to_vtt()`, `.to_txt()` all correct |
| `generate_subtitles_task` | ✅ | Full pipeline: extract audio → transcribe → write 3 files |
| Subtitle download endpoints | ✅ | `/jobs/{id}/download/{transcript,srt,vtt}` |
| Diagnostic logging | ✅ | 17 `diag_*` events on all code paths |

### Phase 3 — Subtitle Burn-In ✅ COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| `FFmpegService._escape_filter_path()` | ✅ | Escapes `\`, `:`, `'` for FFmpeg filter syntax |
| `FFmpegService.burn_subtitles()` | ✅ | H.264 output, `libass` filter, style params |
| `burn_subtitles_task` | ✅ | Full implementation — `subtitle_job_id` + `srt_path` modes |
| SRT resolution from prior job | ✅ | Looks up `parameters["result_files"]["srt"]` from subtitle job |
| Media type validation | ✅ | Rejects audio-only files with clear error |
| File existence validation | ✅ | Checks both video and SRT before calling FFmpeg |
| `result_files` persistence | ✅ | `parameters["result_files"]["burned_video"]` written on completion |
| `subtitle_job_id` traceability | ✅ | Persisted back in burn job's parameters |
| `GET /jobs/{id}/download/video` | ✅ | Typed MP4 download endpoint |
| 16 diagnostic log events | ✅ | `diag_burn_*` events at every major step |

### Phase 4 — Karaoke Generation ✅ COMPLETE (pre-commit)

| Component | Status | Notes |
|-----------|--------|-------|
| `WordTimestamp` / `WhisperSegment.words` | ✅ | New dataclasses for per-word timing |
| `WhisperService.transcribe(word_timestamps=True)` | ✅ | Uses `--output-json-full` + BPE token grouping |
| `_tokens_to_words()` | ✅ | Groups BPE tokens into words by leading-space convention |
| `TranscriptResult.to_ass()` | ✅ | ASS with `\kf` karaoke timing; pre-roll gap handled cleanly |
| `FFmpegService.burn_ass()` | ✅ | ASS burn; `force_style` intentionally omitted |
| `karaoke_task` | ✅ | Full pipeline: validate → extract → transcribe → ASS → MP4 |
| `IMPLEMENTED_JOB_TYPES` guard | ✅ | Unimplemented types (voice_replacement etc.) return 422 not 500 |
| `GET /jobs/{id}/download/ass` | ✅ | ASS file download |
| `GET /jobs/{id}/download/karaoke-video` | ✅ | Karaoke MP4 download |
| End-to-end validation | ✅ | Job `0e44f8ef-0867-437b-a1fc-c9e8d4d90a08` — status `completed` |

**Known limitation:** `ggml-tiny.en.bin` produces 20–30 s gaps during instrumental
sections of music videos. This is a Whisper model limitation, not a code bug.
Switch to `ggml-base.en.bin` or `ggml-small.en.bin` for music content.
See `KNOWN_BUGS_AND_ROOT_CAUSES.md` for the full investigation.

### Bugs Fixed Across Phases 2–4

| # | Bug | Fixed in |
|---|-----|---------|
| 1 | Redis not connected in Celery workers | `celery_app.py` — `worker_process_init` signal |
| 2 | `MissingGreenlet` on `job.media` lazy-load | `job_service.py` — `get_by_id_with_media()` with `selectinload` |
| 3 | `libwhisper.so.1 not found` | `whisper_service.py` — `_build_subprocess_env()` |
| 4 | FFmpeg filter path not escaped (space in project path) | `ffmpeg_service.py` — `_escape_filter_path()` |
| 5 | No explicit video codec in burn command | `ffmpeg_service.py` — added `-c:v libx264 -crf 23 -preset fast` |
| 6 | FastAPI route ordering — `/download/video` shadowed | `jobs.py` — literal routes before parameterised catch-all |
| 7 | `voice_replacement`/`voice_clone` returned HTTP 500 | `jobs.py` + `media_tasks.py` — `IMPLEMENTED_JOB_TYPES` pre-flight |

### Infrastructure Readiness

| Item | Status |
|------|--------|
| whisper-cli binary | ✅ Built at `tools/whisper.cpp/build/bin/whisper-cli` |
| Whisper models | ✅ All 3 downloaded (tiny.en, base.en, small.en) |
| FFmpeg | ✅ System package installed; libass and libx264 available |
| Redis | ✅ Installed, default config |

---

## Phase 3 Validation Evidence

Validated end-to-end on 2026-06-14.

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
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav         (WAV from Phase 2)
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_transcript.txt    (plain text from Phase 2)
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.srt     (SRT from Phase 2)
processed/ac849d78-fe28-4448-b029-a5c79a83ef94_subtitles.vtt     (VTT from Phase 2)
processed/c4263f06-ef6d-4005-91e8-d422fb00be26_subtitled.mp4     (burned video — Phase 3)
```

### Verified components

| Component | Verified |
|-----------|---------|
| `subtitle_job_id` resolution (SRT from prior job) | ✅ |
| Media type validation (VIDEO accepted) | ✅ |
| FFmpeg path escaping (space in project path) | ✅ |
| H.264 video re-encode | ✅ |
| Audio stream-copy (no re-encode) | ✅ |
| `result_files.burned_video` written to parameters | ✅ |
| `subtitle_job_id` persisted in burn job parameters | ✅ |
| `GET /jobs/{id}/result` serves burned MP4 | ✅ |
| `GET /jobs/{id}/download/video` serves burned MP4 | ✅ |

### FFprobe validation

```
ffprobe processed/c4263f06-ef6d-4005-91e8-d422fb00be26_subtitled.mp4

Duration: [source duration]
Video: h264 (High), yuv420p — subtitles hardcoded
Audio: opus — stream-copied, no re-encode
```

---

## Phase 4 Validation Evidence

Validated end-to-end on 2026-06-14.

### Run identifiers

| Field | Value |
|-------|-------|
| Job ID | `0e44f8ef-0867-437b-a1fc-c9e8d4d90a08` |
| Status | `completed` |
| Progress | `100` |
| Detected language | `en` |
| Segment count | 76 |
| Word count | present (word_timestamps=True) |

### Generated output files

```
processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav       (~6.9 MB WAV)
processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_karaoke.ass     (10 KB ASS — 76 Dialogue lines)
processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_karaoke.mp4     (92 MB H.264 MP4)
```

### Verified components

| Component | Verified |
|-----------|---------|
| Video-only validation (MediaType.VIDEO required) | ✅ |
| FFmpeg audio extraction (16kHz mono WAV) | ✅ |
| `--output-json-full` transcription | ✅ |
| BPE token → word grouping (`_tokens_to_words`) | ✅ |
| ASS file generation with `\kf` tags | ✅ |
| `burn_ass()` — H.264 re-encode, ASS filter, no `force_style` | ✅ |
| `parameters["result_files"]["ass"]` and `["video"]` written | ✅ |
| `GET /jobs/{id}/download/ass` returns ASS file | ✅ |
| `GET /jobs/{id}/download/karaoke-video` returns MP4 | ✅ |
| `GET /jobs/{id}/result` returns MP4 (generic endpoint) | ✅ |

### FFprobe validation

```
ffprobe processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_karaoke.mp4

Duration: 00:03:36.56
Video: h264 (High), yuv420p — karaoke subtitles hardcoded
Audio: (stream-copied from source)
```

---

## Git State

**Branch:** `feature/karaoke-generation`
**Working tree:** Phase 4 changes present, pre-commit engineering review complete

### Commit log

```
2f9f643  Phase 3: subtitle burn-in complete       ← last committed, phase3-subtitle-burn
19f8cc8  Finalize Phase 2 documentation and handoff
94f77e0  Phase 2 subtitle generation complete      ← phase2-subtitles-working
52c5d3e  Phase 1 foundation validated              ← v0.1-foundation
```

### Tags (rollback checkpoints)

```
v0.1-foundation           → Phase 1 complete
phase2-subtitles-working  → Phase 2 complete
phase3-subtitle-burn      → Phase 3 complete (last tag)
phase4-karaoke            → Phase 4 complete (pending commit)
```
