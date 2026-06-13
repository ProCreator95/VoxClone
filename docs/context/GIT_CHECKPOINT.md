---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Pre-commit checklist for a commit that was completed in `94f77e0`
> - Branch referenced (`feature/subtitle-pipeline`) is not the active branch (`feature/subtitle-burn`)
> - References `WHISPER_BACKEND: openai` and `openai-whisper` — the final implementation uses whisper.cpp exclusively
> - Config schema (`WHISPER_MODEL`, `WHISPER_MODELS_DIR`) does not match the actual `config.py`
> - Checklist item "openai-whisper is importable" is invalid — openai-whisper is not used
> - Tag template `v0.2-subtitle-pipeline` was not applied; actual tags are `phase2-subtitles-working`, `phase3-subtitle-burn`
> - Commit message template references openai-whisper as a dependency
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Section 15 — Git Reference)

---

# Phase 2 Git Checkpoint

## Pre-Commit Verification

Run these checks before committing to ensure the implementation is clean.

### 1. Verify Working Tree

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone"
git status
```

Expected new/modified files:
```
Modified:
  backend/app/core/config.py
  backend/app/tasks/media_tasks.py
  backend/app/api/v1/endpoints/jobs.py
  backend/requirements.txt
  backend/.env.example

New:
  backend/app/services/whisper_service.py
  docs/testing/PHASE2_TEST_PLAN.md
  docs/testing/PHASE2_MANUAL_TESTING.md
  docs/testing/PHASE2_EXPECTED_RESULTS.md
  docs/reports/PHASE2_COMPLETION_REPORT.md
  docs/context/VOXCLONE_PROJECT_CONTEXT.md
  docs/context/NEXT_PHASES_ROADMAP.md
  docs/context/GIT_CHECKPOINT.md
  docs/context/HANDOFF_TO_NEXT_CHAT.md
```

### 2. Verify FastAPI Imports

```bash
cd backend
source .venv/bin/activate
python3 -c "from app.main import app; print('FastAPI app OK')"
```

Expected: `FastAPI app OK`

### 3. Verify Whisper Service Imports

```bash
python3 -c "
from app.services.whisper_service import WhisperService, TranscriptResult, WhisperSegment
svc = WhisperService()
print('WhisperService OK')
# Test SRT/VTT format conversion
from app.services.whisper_service import _srt_time, _vtt_time
print('SRT time:', _srt_time(65.5))   # expected: 00:01:05,500
print('VTT time:', _vtt_time(65.5))   # expected: 00:01:05.500
"
```

### 4. Verify Config Settings

```bash
python3 -c "
from app.core.config import get_settings
s = get_settings()
print('WHISPER_BACKEND:', s.WHISPER_BACKEND)
print('WHISPER_MODEL:', s.WHISPER_MODEL)
print('WHISPER_MODELS_DIR:', s.WHISPER_MODELS_DIR)
"
```

Expected:
```
WHISPER_BACKEND: openai
WHISPER_MODEL: base
WHISPER_MODELS_DIR: models
```

### 5. Verify Task Registration

```bash
python3 -c "
from app.tasks.media_tasks import _TASK_MAP
for k, v in _TASK_MAP.items():
    print(f'{k}: {v.name}')
"
```

Expected:
```
audio_extraction: app.tasks.media_tasks.extract_audio_task
subtitle_generation: app.tasks.media_tasks.generate_subtitles_task
subtitle_burn: app.tasks.media_tasks.burn_subtitles_task
karaoke: app.tasks.media_tasks.karaoke_task
audio_enhance: app.tasks.media_tasks.audio_enhance_task
```

### 6. Verify API Endpoints

Start the server and check the new endpoints appear in OpenAPI:

```bash
uvicorn app.main:app --reload --port 8000 &
sleep 3
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys, json
spec = json.load(sys.stdin)
paths = list(spec['paths'].keys())
subtitle_paths = [p for p in paths if 'download' in p]
print('Subtitle download paths:')
for p in subtitle_paths:
    print(' ', p)
"
```

Expected:
```
Subtitle download paths:
  /api/v1/jobs/{job_id}/download/{format_type}
```

### 7. Manual Testing Checklist

Before committing, verify manually:

- [ ] FastAPI starts without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Celery worker starts and registers all 5 tasks
- [ ] `openai-whisper` is importable
- [ ] Video upload returns `media_type: "video"` with metadata
- [ ] `POST /jobs` with `subtitle_generation` returns `status: "queued"`
- [ ] Job transitions from `queued` → `processing` → `completed`
- [ ] `GET /jobs/{id}/download/srt` returns valid SRT content
- [ ] `GET /jobs/{id}/download/vtt` starts with `WEBVTT`
- [ ] `GET /jobs/{id}/download/transcript` returns plain text

---

## Commit Commands

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone"

# Stage all new and modified files
git add backend/app/services/whisper_service.py
git add backend/app/core/config.py
git add backend/app/tasks/media_tasks.py
git add backend/app/api/v1/endpoints/jobs.py
git add backend/requirements.txt
git add backend/.env.example
git add docs/

# Review what's staged
git diff --cached --stat

# Commit
git commit -m "Phase 2 subtitle pipeline validated

- Add WhisperService with openai-whisper and whisper.cpp backends
- Implement generate_subtitles_task: video → audio → whisper → SRT/VTT/TXT
- Add subtitle format download endpoints: /jobs/{id}/download/{transcript,srt,vtt}
- Add Whisper config settings to Settings
- Add openai-whisper to requirements.txt
- Add Phase 2 test suite documentation
- Add project context and next phases roadmap"

# Push to feature branch
git push origin feature/subtitle-pipeline
```

---

## Post-Commit Verification

After pushing, verify the branch is up to date:

```bash
git log --oneline -5
git status  # should show "nothing to commit, working tree clean"
```

---

## Tagging the Phase 2 Release

After validation and PR merge:

```bash
git checkout main
git merge feature/subtitle-pipeline
git tag -a v0.2-subtitle-pipeline -m "Phase 2: Whisper subtitle pipeline"
git push origin main
git push origin v0.2-subtitle-pipeline
```
