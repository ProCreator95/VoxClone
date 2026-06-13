---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Tests WH-01 through WH-04 reference `openai-whisper` Python package — not used in final implementation
> - Whisper validation is now handled by `WhisperService._resolve_binary()` and `_build_subprocess_env()` (whisper.cpp)
> - Test environment requirements list `openai-whisper` as a dependency — it is not installed
> - Phase 2 has been validated end-to-end; the test plan is now a historical artifact
> - Phase 3 validation evidence supersedes this document as proof of pipeline correctness
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Section 12 — Testing Commands, Section 17 — Phase 2 Validation Evidence)

---

# Phase 2 — Whisper Subtitle Pipeline: Test Plan

## Overview

This document defines the test strategy for the Phase 2 subtitle generation pipeline.

**Feature under test:** Video → Audio Extraction → Whisper → Transcript + SRT + VTT → Download

---

## Test Scope

| Layer | What is tested |
|-------|---------------|
| Infrastructure | FastAPI startup, Redis, Celery worker |
| Installation | Whisper availability, model detection |
| API | Upload, job creation, job status, downloads |
| Pipeline | Full video → SRT/VTT/TXT round-trip |
| Error handling | Missing files, unsupported formats, unavailable Whisper |

---

## Test Categories

### 1. Infrastructure Tests

| ID | Test | Method |
|----|------|--------|
| INF-01 | FastAPI starts without errors | Manual / curl |
| INF-02 | `/health` returns `{"status": "ok"}` | curl |
| INF-03 | Redis is reachable | curl /health |
| INF-04 | Database (SQLite) is accessible | curl /health |
| INF-05 | Celery worker starts and connects to Redis broker | Manual log inspection |

### 2. Whisper Installation Tests

| ID | Test | Method |
|----|------|--------|
| WH-01 | `openai-whisper` Python package is importable | Python shell |
| WH-02 | Whisper `base` model loads without error | Python shell |
| WH-03 | Whisper transcribes a short WAV test file | Python shell |
| WH-04 | `WhisperService.is_available()` returns `True` | Python / API |

### 3. Upload API Tests

| ID | Test | Method |
|----|------|--------|
| UPL-01 | Upload a valid MP4 file — returns 201 with media_id | curl |
| UPL-02 | Upload rejects unsupported file extension | curl |
| UPL-03 | Media metadata is probed and returned (duration, codec, etc.) | curl GET /media/{id} |

### 4. Job Creation Tests

| ID | Test | Method |
|----|------|--------|
| JOB-01 | Create `subtitle_generation` job — returns 201 with job_id | curl |
| JOB-02 | Create job with invalid `job_type` — returns 422 | curl |
| JOB-03 | Create job with non-existent `media_id` — returns 404 | curl |
| JOB-04 | Job status starts as `queued`, transitions to `processing` | curl polling |
| JOB-05 | Job status transitions from `processing` to `completed` | curl polling |

### 5. Subtitle Pipeline Tests

| ID | Test | Method |
|----|------|--------|
| SUB-01 | Full pipeline completes for MP4 with speech | End-to-end |
| SUB-02 | `result_files.transcript` is a non-empty .txt path | API + file check |
| SUB-03 | `result_files.srt` is a valid SRT file | API + format validation |
| SUB-04 | `result_files.vtt` is a valid WebVTT file starting with `WEBVTT` | API + format validation |
| SUB-05 | `detected_language` is populated in job parameters | API |
| SUB-06 | `segment_count` > 0 for video with speech | API |

### 6. Download Endpoint Tests

| ID | Test | Method |
|----|------|--------|
| DL-01 | `GET /jobs/{id}/download/transcript` returns text/plain | curl |
| DL-02 | `GET /jobs/{id}/download/srt` returns valid SRT | curl |
| DL-03 | `GET /jobs/{id}/download/vtt` returns valid VTT | curl |
| DL-04 | Download on incomplete job returns 404 | curl |
| DL-05 | Download with invalid format returns 422 | curl |
| DL-06 | Generic `GET /jobs/{id}/result` returns primary SRT | curl |

### 7. Error Handling Tests

| ID | Test | Method |
|----|------|--------|
| ERR-01 | Job fails gracefully if Whisper not installed | Uninstall whisper, run job |
| ERR-02 | Job fails gracefully if source video is missing | Delete file, run job |
| ERR-03 | Failed job stores error message in DB | curl GET /jobs/{id} |
| ERR-04 | Failed job status is `failed` not `processing` | curl polling |

---

## Test Environment Requirements

```
Python 3.12+
FastAPI (uvicorn)
Redis 6+
Celery 5.4+
FFmpeg
openai-whisper (pip install openai-whisper)
A short test MP4 video with audio speech
```

---

## Test Data

Provide a short (5–15 second) MP4 video file with clear English speech.
A publicly available test clip or a screen recording with narration works well.

Store test files in: `backend/tests/fixtures/`

---

## Pass/Fail Criteria

- **PASS**: All P1 (infrastructure + core pipeline) tests pass
- **ACCEPTABLE**: Minor format differences in SRT/VTT timestamps (±1ms)
- **FAIL**: Any `500` response from a healthy endpoint, pipeline stuck in `processing`, or missing output files
