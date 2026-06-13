---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Section 2 (Whisper Validation) tests `import whisper` and `openai-whisper` — not used in this project
> - Celery startup command (Section 1.4) is missing `--queues media,ai`; without this flag, all tasks silently queue forever
> - Job creation payload includes `"model": "base"` — not a valid parameter for the whisper.cpp backend
> - Section 4.2 progress sequence does not match the actual `diag_*` log event sequence
> - Phase 2 pipeline has been validated; this guide is superseded by the validated test commands
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Section 12 — Testing Commands)
> `docs/context/NEXT_SESSION_START_HERE.md` (end-to-end pipeline test script)

---

# Phase 2 — Whisper Subtitle Pipeline: Manual Testing Guide

All commands assume you are inside `backend/` and the virtual environment is activated.

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
```

---

## Section 1: Infrastructure Validation

### 1.1 Start FastAPI Server

**Purpose:** Verify FastAPI starts cleanly with Whisper config loaded.

```bash
uvicorn app.main:app --reload --port 8000
```

**Expected startup output:**
```
INFO:     Started server process
INFO:     Waiting for application startup
{"event": "voxclone_starting", "version": "0.1.0", ...}
{"event": "creating_database_tables", ...}
{"event": "database_tables_ready", ...}
{"event": "voxclone_ready", ...}
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Failure indicators:**
- `ImportError` — missing dependency, run `pip install -r requirements.txt`
- `ConnectionRefusedError` on Redis — Redis not running, start with `redis-server`

---

### 1.2 Health Check

**Purpose:** Confirm API, database, and Redis are all healthy.

```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

**Expected response:**
```json
{
    "status": "ok",
    "app": "VoxClone",
    "version": "0.1.0",
    "database": "ok",
    "redis": "ok"
}
```

**Failure indicators:**
- `"status": "degraded"` — check `database` or `redis` fields
- Connection refused — FastAPI not running

---

### 1.3 Start Redis

```bash
redis-server --daemonize yes
redis-cli ping
```

**Expected:** `PONG`

---

### 1.4 Start Celery Worker

Open a **second terminal**:

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

**Expected startup output:**
```
[config]
.> app:         app.tasks.celery_app:0x...
.> transport:   redis://localhost:6379/0
.> results:     redis://localhost:6379/1
.> concurrency: 2 (prefork)

[queues]
.> celery          exchange=celery(direct) key=celery

[tasks]
  . app.tasks.media_tasks.extract_audio_task
  . app.tasks.media_tasks.generate_subtitles_task
  . app.tasks.media_tasks.burn_subtitles_task
  . app.tasks.media_tasks.karaoke_task
  . app.tasks.media_tasks.audio_enhance_task

[2026-...] INFO/MainProcess celery@hostname ready.
```

**Failure indicators:**
- `kombu.exceptions.OperationalError` — Redis not running
- Missing tasks in task list — check celery_app imports

---

## Section 2: Whisper Validation

### 2.1 Verify Whisper Installation

```bash
python3 -c "import whisper; print('whisper version:', whisper.__version__)"
```

**Expected:** `whisper version: 20231117` (or similar)

**If not installed:**
```bash
pip install openai-whisper
```

---

### 2.2 Verify Whisper Model Load

```bash
python3 -c "
import whisper
model = whisper.load_model('base')
print('Model loaded:', type(model).__name__)
print('Model device:', next(model.parameters()).device)
"
```

**Expected:**
```
Model loaded: Whisper
Model device: cpu
```
(First run downloads ~140MB model to `~/.cache/whisper/`)

---

### 2.3 Test Whisper Transcription Directly

```bash
python3 -c "
import whisper
model = whisper.load_model('base')
# Use any short WAV file for this test
result = model.transcribe('tests/fixtures/test_audio.wav')
print('Language:', result['language'])
print('Text:', result['text'][:100])
print('Segments:', len(result['segments']))
"
```

**Expected:**
```
Language: en
Text: Hello, this is a test transcription...
Segments: 3
```

---

## Section 3: Upload Testing

### 3.1 Upload a Test Video

```bash
# Replace with path to your test MP4 file
curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@tests/fixtures/test_video.mp4" \
  | python3 -m json.tool
```

**Expected response:**
```json
{
    "id": "abc12345-...",
    "filename": "a1b2c3d4e5f6.mp4",
    "original_name": "test_video.mp4",
    "file_size": 1234567,
    "media_type": "video",
    "mime_type": "video/mp4",
    "duration": 12.5,
    "width": 1280,
    "height": 720,
    "codec_video": "h264",
    "codec_audio": "aac",
    "status": "ready",
    "created_at": "2026-06-13T..."
}
```

Save the `id` value — you need it for job creation:
```bash
MEDIA_ID="abc12345-..."
```

---

## Section 4: Subtitle Job Creation and Execution

### 4.1 Create Subtitle Generation Job

```bash
curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"media_id\": \"$MEDIA_ID\",
    \"job_type\": \"subtitle_generation\",
    \"parameters\": {
      \"model\": \"base\",
      \"language\": \"\"
    }
  }" | python3 -m json.tool
```

**Expected response:**
```json
{
    "id": "job-uuid-...",
    "media_id": "abc12345-...",
    "job_type": "subtitle_generation",
    "status": "queued",
    "progress": 0,
    "current_step": "Queued",
    "parameters": {"model": "base", "language": ""},
    "created_at": "2026-06-13T..."
}
```

Save the job ID:
```bash
JOB_ID="job-uuid-..."
```

---

### 4.2 Poll Job Progress

```bash
# Poll every 5 seconds until completed
watch -n 5 "curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/progress | python3 -m json.tool"
```

**Expected progression:**
```json
{"job_id": "...", "status": "queued",      "progress": 0,  "current_step": "Queued"}
{"job_id": "...", "status": "processing",  "progress": 5,  "current_step": "Preparing audio"}
{"job_id": "...", "status": "processing",  "progress": 10, "current_step": "Extracting audio from video"}
{"job_id": "...", "status": "processing",  "progress": 25, "current_step": "Running Whisper speech recognition"}
{"job_id": "...", "status": "processing",  "progress": 70, "current_step": "Generating subtitle files"}
{"job_id": "...", "status": "processing",  "progress": 90, "current_step": "Saving results"}
{"job_id": "...", "status": "completed",   "progress": 100, "current_step": "Done"}
```

---

### 4.3 Get Full Job Details

```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID | python3 -m json.tool
```

**Expected (on completion):**
```json
{
    "id": "job-uuid-...",
    "status": "completed",
    "progress": 100,
    "result_path": "/path/to/processed/job-uuid-..._subtitles.srt",
    "parameters": {
        "model": "base",
        "language": "",
        "result_files": {
            "transcript": "/path/to/processed/job-uuid-..._transcript.txt",
            "srt": "/path/to/processed/job-uuid-..._subtitles.srt",
            "vtt": "/path/to/processed/job-uuid-..._subtitles.vtt"
        },
        "detected_language": "en",
        "segment_count": 8
    }
}
```

---

## Section 5: Download Testing

### 5.1 Download Plain Text Transcript

```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/download/transcript
```

**Expected:** Plain text content of the transcription.

```
Hello and welcome to this demonstration of VoxClone.
This is a test of the Whisper speech recognition pipeline.
```

---

### 5.2 Download SRT Subtitles

```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt
```

**Expected:**
```
1
00:00:00,000 --> 00:00:02,500
Hello and welcome to this demonstration of VoxClone.

2
00:00:02,500 --> 00:00:05,800
This is a test of the Whisper speech recognition pipeline.

```

---

### 5.3 Download WebVTT Subtitles

```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/download/vtt
```

**Expected:**
```
WEBVTT

00:00:00.000 --> 00:00:02.500
Hello and welcome to this demonstration of VoxClone.

00:00:02.500 --> 00:00:05.800
This is a test of the Whisper speech recognition pipeline.

```

---

### 5.4 Download via Generic Result Endpoint

```bash
curl -O -J "http://localhost:8000/api/v1/jobs/$JOB_ID/result"
```

**Expected:** Downloads the SRT file (primary output).

---

## Section 6: Error Case Testing

### 6.1 Download Before Job Completes

```bash
# Create a job then immediately try to download
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt
```

**Expected (job still processing):**
```json
{
    "error": "result_not_ready",
    "message": "Result for job '...' is not available yet",
    "detail": "Job status is 'processing'. Wait until status is 'completed'."
}
```

---

### 6.2 Invalid Format Type

```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID/download/pdf
```

**Expected:** HTTP 422 Unprocessable Entity

---

### 6.3 Non-existent Job

```bash
curl -s http://localhost:8000/api/v1/jobs/nonexistent-id/download/srt
```

**Expected:**
```json
{
    "error": "job_not_found",
    "message": "Job 'nonexistent-id' not found"
}
```

---

## Section 7: Cleanup Verification

Confirm output files exist on disk:

```bash
ls -lh processed/ | grep $JOB_ID
```

**Expected:**
```
-rw-r--r-- 1 user group  1.2K Jun 13 15:30 <JOB_ID>_audio.wav
-rw-r--r-- 1 user group  3.4K Jun 13 15:30 <JOB_ID>_transcript.txt
-rw-r--r-- 1 user group  4.1K Jun 13 15:30 <JOB_ID>_subtitles.srt
-rw-r--r-- 1 user group  3.9K Jun 13 15:30 <JOB_ID>_subtitles.vtt
```
