---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - WH-01 and WH-02 tests reference `openai-whisper` Python package — not installed in this project
> - ERR-03 expected error message references `openai-whisper is not installed` — actual errors reference whisper.cpp binary/model paths
> - INF-05 expected task list shows 5 tasks and default `celery` queue; Celery must use `--queues media,ai`
> - Progress step "Running Whisper speech recognition" is accurate but the full `diag_*` event sequence is not documented here
> - Phase 2 has been validated with actual job IDs; this document's hypothetical examples are superseded
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Section 17 — Phase 2 Validation Evidence with real job IDs and outputs)

---

# Phase 2 — Whisper Subtitle Pipeline: Expected Results Reference

This document defines the exact expected outputs for every test in the Phase 2 test plan.

---

## INF-01: FastAPI Startup

**Command:** `uvicorn app.main:app --reload --port 8000`

**Expected stdout (structured JSON logs):**
```json
{"event": "voxclone_starting", "version": "0.1.0", "debug": false, "level": "info"}
{"event": "creating_database_tables", "level": "info"}
{"event": "database_tables_ready", "level": "info"}
{"event": "redis_connected", "level": "info"}
{"event": "voxclone_ready", "level": "info"}
```

**Expected HTTP:** Server responds on `http://localhost:8000`

---

## INF-02: Health Check

**Command:** `curl -s http://localhost:8000/api/v1/health`

**Expected HTTP Status:** `200 OK`

**Expected Body:**
```json
{
    "status": "ok",
    "app": "VoxClone",
    "version": "0.1.0",
    "database": "ok",
    "redis": "ok"
}
```

---

## INF-05: Celery Worker Startup

**Command:** `celery -A app.tasks.celery_app worker --loglevel=info`

**Expected tasks registered:**
```
[tasks]
  . app.tasks.media_tasks.audio_enhance_task
  . app.tasks.media_tasks.burn_subtitles_task
  . app.tasks.media_tasks.extract_audio_task
  . app.tasks.media_tasks.generate_subtitles_task
  . app.tasks.media_tasks.karaoke_task
```

**Expected final line:** `celery@hostname ready.`

---

## WH-01: Whisper Import

**Command:** `python3 -c "import whisper; print(whisper.__version__)"`

**Expected:** Any version string (e.g. `20231117`)

---

## WH-02: Model Load

**Command:**
```python
import whisper
model = whisper.load_model('base')
print(type(model).__name__)
```

**Expected:** `Whisper`

**Note:** First run downloads ~140MB. Subsequent runs use cache.

---

## UPL-01: Upload MP4

**Command:** `curl -X POST /api/v1/uploads -F "file=@test_video.mp4"`

**Expected HTTP Status:** `201 Created`

**Expected Body (structure):**
```json
{
    "id": "<uuid>",
    "filename": "<hex>.mp4",
    "original_name": "test_video.mp4",
    "file_size": <integer>,
    "media_type": "video",
    "mime_type": "video/mp4",
    "duration": <float>,
    "status": "ready"
}
```

---

## UPL-02: Invalid Extension

**Command:** `curl -X POST /api/v1/uploads -F "file=@document.pdf"`

**Expected HTTP Status:** `422 Unprocessable Entity`

**Expected Body:**
```json
{
    "error": "unsupported_format",
    "message": "Unsupported format '.pdf'"
}
```

---

## JOB-01: Create Subtitle Job

**Expected HTTP Status:** `201 Created`

**Expected Body:**
```json
{
    "id": "<job-uuid>",
    "media_id": "<media-uuid>",
    "job_type": "subtitle_generation",
    "status": "queued",
    "progress": 0,
    "current_step": "Queued",
    "celery_task_id": "<celery-uuid>"
}
```

---

## JOB-02: Invalid job_type

**Command:** `POST /api/v1/jobs` with `"job_type": "invalid_type"`

**Expected HTTP Status:** `422 Unprocessable Entity`

---

## JOB-05: Job Completes

**Expected final state from** `GET /api/v1/jobs/{id}`:
```json
{
    "status": "completed",
    "progress": 100,
    "current_step": "Done",
    "result_path": "/path/to/processed/<job-id>_subtitles.srt",
    "parameters": {
        "result_files": {
            "transcript": "/path/to/processed/<job-id>_transcript.txt",
            "srt": "/path/to/processed/<job-id>_subtitles.srt",
            "vtt": "/path/to/processed/<job-id>_subtitles.vtt"
        },
        "detected_language": "en",
        "segment_count": <integer>
    }
}
```

---

## SUB-03: SRT Format Validation

**Valid SRT structure:**
```
1
00:00:00,000 --> 00:00:02,340
[segment text here]

2
00:00:02,340 --> 00:00:05,180
[segment text here]

```

**Validation rules:**
- First line of each block: sequential integer index
- Second line: `HH:MM:SS,mmm --> HH:MM:SS,mmm`
- Third line: non-empty text
- Blocks separated by blank lines
- Note: SRT uses **comma** as millisecond separator

---

## SUB-04: VTT Format Validation

**Valid VTT structure:**
```
WEBVTT

00:00:00.000 --> 00:00:02.340
[segment text here]

00:00:02.340 --> 00:00:05.180
[segment text here]

```

**Validation rules:**
- File must start with `WEBVTT`
- Empty line after `WEBVTT` header
- Cue format: `HH:MM:SS.mmm --> HH:MM:SS.mmm`
- Note: VTT uses **period** as millisecond separator (unlike SRT)
- Cues separated by blank lines

---

## DL-01: Transcript Download

**Command:** `GET /api/v1/jobs/{id}/download/transcript`

**Expected HTTP Status:** `200 OK`
**Expected Content-Type:** `text/plain`
**Expected Content-Disposition:** `attachment; filename="<job-id>.txt"`
**Expected Body:** Plain text transcript (no timestamps, no indices)

---

## DL-02: SRT Download

**Command:** `GET /api/v1/jobs/{id}/download/srt`

**Expected HTTP Status:** `200 OK`
**Expected Content-Type:** `text/plain`
**Expected Content-Disposition:** `attachment; filename="<job-id>.srt"`
**Expected Body:** Valid SRT content (see SUB-03)

---

## DL-03: VTT Download

**Command:** `GET /api/v1/jobs/{id}/download/vtt`

**Expected HTTP Status:** `200 OK`
**Expected Content-Type:** `text/vtt`
**Expected Content-Disposition:** `attachment; filename="<job-id>.vtt"`
**Expected Body:** Valid VTT content starting with `WEBVTT`

---

## DL-04: Download Before Completion

**Expected HTTP Status:** `404 Not Found`

**Expected Body:**
```json
{
    "error": "result_not_ready",
    "message": "Result for job '...' is not available yet",
    "detail": "Job status is 'processing'. Wait until status is 'completed'."
}
```

---

## ERR-03: Failed Job Error Message

**From** `GET /api/v1/jobs/{id}` when job has failed:
```json
{
    "status": "failed",
    "error_message": "openai-whisper is not installed. Install it with: pip install openai-whisper"
}
```

---

## Progress Step Sequence

The complete expected progress sequence during subtitle generation:

| Progress % | Step |
|------------|------|
| 0 | Queued |
| 0 | Starting |
| 5 | Preparing audio |
| 10 | Extracting audio from video |
| 25 | Running Whisper speech recognition |
| 70 | Generating subtitle files |
| 90 | Saving results |
| 100 | Done |

---

## Processing Time Benchmarks (approximate)

These are guidelines, not hard limits. Actual times depend on hardware.

| Video Length | Whisper Model | Expected Time |
|-------------|--------------|--------------|
| 10 seconds | tiny | 5–15 seconds |
| 10 seconds | base | 10–30 seconds |
| 60 seconds | base | 30–120 seconds |
| 5 minutes | base | 2–8 minutes |
| 5 minutes | small | 5–15 minutes |

CPU-only inference. GPU acceleration dramatically reduces these times.
