# Phase 5 — Milestone 1: Per-Job Whisper Model Selection

**Status:** Complete (included in Phase 5 pre-commit)
**Scope:** `whisper_model` parameter for `subtitle_generation` and `karaoke` only. No Demucs.

---

## Summary

Users can pass `parameters.whisper_model` (`tiny`, `base`, or `small`) when creating subtitle or karaoke jobs. When omitted, job-type defaults apply:

| Job type | Default |
|----------|---------|
| `subtitle_generation` | `tiny` |
| `karaoke` | `base` |

Completed jobs persist `whisper_model` and `whisper_model_file` in `parameters`.

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/services/whisper_models.py` | **New** — aliases, defaults, resolver |
| `backend/app/services/whisper_service.py` | Per-call model resolution in `transcribe()` |
| `backend/app/schemas/job.py` | API validation for `whisper_model` |
| `backend/app/tasks/media_tasks.py` | Wire defaults + persist metadata in both Whisper tasks |
| `backend/app/api/v1/endpoints/jobs.py` | OpenAPI description update |
| `backend/.env.example` | Document per-job overrides vs global fallback |

---

## API changes

### Request

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "subtitle_generation",
  "parameters": {
    "whisper_model": "base"
  }
}
```

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "karaoke"
}
```

Omitted `whisper_model` on karaoke uses `base` (behavior change from global `.env` tiny — intentional per Phase 5 spec).

### Validation (HTTP 422)

- Invalid alias (e.g. `"large"`)
- `whisper_model` on unsupported job types (e.g. `subtitle_burn`)

### Response (completed job parameters)

```json
{
  "whisper_model": "base",
  "whisper_model_file": "ggml-base.en.bin",
  "detected_language": "en",
  "segment_count": 112,
  "result_files": { "...": "..." }
}
```

No new download endpoints.

---

## Data model changes

**None.** Uses existing `jobs.parameters` JSON column.

New keys written on completion:

- `whisper_model` — resolved alias
- `whisper_model_file` — GGML filename

---

## Manual test plan

1. **Default subtitle job** — omit `whisper_model`; verify `parameters.whisper_model == "tiny"`.
2. **Subtitle with base** — pass `"whisper_model": "base"`; verify logs show `ggml-base.en.bin`.
3. **Default karaoke job** — omit `whisper_model`; verify `parameters.whisper_model == "base"`.
4. **Invalid model** — `"whisper_model": "xlarge"` → HTTP 422.
5. **Wrong job type** — `subtitle_burn` + `whisper_model` → HTTP 422.
6. **Regression** — Phase 2–4 flows still complete; SRT/ASS/MP4 outputs unchanged aside from model used.

```bash
# Invalid model → 422
curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"media_id":"<uuid>","job_type":"subtitle_generation","parameters":{"whisper_model":"xlarge"}}'
```

---

## Risks

| Risk | Notes |
|------|-------|
| Karaoke default now `base` | Slower than tiny; better lyrics on music — per approved spec |
| Missing GGML file | Job fails at transcribe with actionable error |
| `.env` WHISPER_MODEL_PATH | Still used as global fallback for non-Whisper-job tooling |

---

## Next step

**Milestone 2:** `vocal_separation` job — `SourceSeparationService`, Demucs subprocess, download endpoints.
