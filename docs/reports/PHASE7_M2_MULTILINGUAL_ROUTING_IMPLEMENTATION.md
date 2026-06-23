# Phase 7 — Milestone 2: Multilingual Whisper Routing Implementation

**Status:** Complete
**Date:** 2026-06-22
**Branch:** `feature/whisper-multilingual`
**Design baseline:** `docs/reports/PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md`
**Prior analysis:** `docs/reports/WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md`

---

## Summary

Implemented **Option B — language-first model routing**. Whisper size aliases (`tiny` / `base` / `small`) now resolve to English-only or multilingual GGML files based on `parameters.language` and `WHISPER_ROUTING_POLICY`.

Default policy **`english_first`** preserves Phase 5 behaviour: omitted `language` on `subtitle_generation` jobs still uses `ggml-tiny.en.bin` with `-l en`.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/app/services/whisper_models.py` | Dual registry, `ResolvedWhisperModel`, language-first `resolve_whisper_model()`, `apply_whisper_metadata()`, language validation |
| `backend/app/services/whisper_service.py` | Route via resolver; use `cli_language` from resolved model; extended logging |
| `backend/app/core/config.py` | Added `WHISPER_ROUTING_POLICY` (default `english_first`) |
| `backend/app/tasks/media_tasks.py` | Pass `language` into resolver; persist variant metadata |
| `backend/app/schemas/job.py` | Validate `parameters.language` on Whisper jobs |
| `backend/app/api/v1/endpoints/jobs.py` | OpenAPI description for language routing |
| `backend/.env.example` | Document routing policy and multilingual models |
| `docs/testing/WHISPER_CPP_SETUP.md` | Multilingual download instructions and model table |
| `backend/tests/test_whisper_models.py` | **New** — routing validation matrix (13 tests) |

**Not modified (Phase 5 / 6 preserved):** Demucs services, `audio_enhancement_service.py`, Celery routing, ML requirements, burn/karaoke FFmpeg paths.

---

## Routing Architecture

```
parameters.language + WHISPER_ROUTING_POLICY
        │
        ▼
resolve_whisper_model(whisper_model, job_type, language)
        │
        ├─ language == "en"
        │     → ggml-{tier}.en.bin  +  -l en
        │
        ├─ language == "auto"
        │     → ggml-{tier}.bin     +  omit -l (whisper.cpp auto-detect)
        │
        ├─ language == <non-en code>  (ur, hi, ar, fa, …)
        │     → ggml-{tier}.bin     +  -l <code>
        │
        ├─ language omitted + english_first  (DEFAULT)
        │     → ggml-{tier}.en.bin  +  -l en     ← Phase 5 behaviour
        │
        └─ language omitted + multilingual_default  (future, not default)
              → ggml-{tier}.bin     +  omit -l
```

**Size tier** (`whisper_model` / job defaults) is independent of variant:

| Job type | Default tier |
|----------|--------------|
| `subtitle_generation` | `tiny` |
| `karaoke` | `base` |

### Dual model registry

| Alias | English file | Multilingual file |
|-------|--------------|-------------------|
| `tiny` | `ggml-tiny.en.bin` | `ggml-tiny.bin` |
| `base` | `ggml-base.en.bin` | `ggml-base.bin` |
| `small` | `ggml-small.en.bin` | `ggml-small.bin` |

Existing API aliases (`tiny`, `base`, `small`) unchanged — variant is selected by language, not alias rename.

### New job metadata (on completion)

```json
{
  "whisper_model": "base",
  "whisper_model_file": "ggml-base.bin",
  "whisper_model_variant": "multilingual",
  "language_requested": "ur",
  "detected_language": "ur"
}
```

English-first jobs with omitted language omit `language_requested` (backward-compatible shape).

---

## Backward Compatibility Analysis

| Scenario | Before M2 | After M2 (`english_first`) | Compatible |
|----------|-----------|----------------------------|------------|
| `{ "job_type": "subtitle_generation" }` | `ggml-tiny.en.bin`, `-l en` | Same | ✅ |
| `{ "job_type": "karaoke" }` | `ggml-base.en.bin`, `-l en` | Same | ✅ |
| `whisper_model: tiny\|base\|small` | Size tier only | Same semantics | ✅ |
| `WHISPER_MODEL_PATH` global fallback | `.en.bin` | Unchanged | ✅ |
| Phase 6 `audio_enhance` | Unaffected | Unaffected | ✅ |
| Phase 5 Demucs / stem reuse | Unaffected | Unaffected | ✅ |

**Behavioural changes (additive only):**

- `parameters.language: "ur"` → multilingual model (requires `ggml-*.bin` on disk)
- `parameters.language: "auto"` → multilingual + auto-detect
- Invalid language codes → HTTP 422 (previously passed through silently)

**Not enabled by default:** `WHISPER_ROUTING_POLICY=multilingual_default`

---

## Validation Results

### Automated tests

```bash
cd backend && source .venv/bin/activate
python -m unittest tests.test_whisper_models -v
```

**Result:** 13/13 passed (2026-06-22)

| Test case | Expected routing | Result |
|-----------|-------------------|--------|
| English-only, omitted language | `ggml-tiny.en.bin`, `-l en` | ✅ PASS |
| English-only, `language: en` | `ggml-base.en.bin`, `-l en` | ✅ PASS |
| Urdu-only, `language: ur` | `ggml-base.bin`, `-l ur` | ✅ PASS |
| Mixed EN+Urdu, `language: auto` | `ggml-base.bin`, omit `-l` | ✅ PASS |
| Karaoke default (no language) | `ggml-base.en.bin`, `-l en` | ✅ PASS |
| Subtitle `whisper_model: small` | `ggml-small.en.bin` | ✅ PASS |
| Hindi / Arabic / Persian codes | multilingual + matching `-l` | ✅ PASS |
| `multilingual_default` policy | `ggml-tiny.bin`, omit `-l` | ✅ PASS |
| Invalid language in JobCreate | HTTP 422 (ValueError) | ✅ PASS |
| `language: auto` in JobCreate | Accepted | ✅ PASS |
| `apply_whisper_metadata()` | Persists variant + language_requested | ✅ PASS |

### Runtime / E2E (not executed)

Multilingual GGML files are **not installed** on the development host (only `.en.bin` trio present). Live transcription E2E for Urdu/mixed content requires:

```bash
cd backend/models
wget -O ggml-base.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
```

Then run subtitle/karaoke jobs with `parameters.language: "ur"` or `"auto"`.

---

## Migration Notes

### For English-only deployments (no action required)

Default `WHISPER_ROUTING_POLICY=english_first` preserves existing behaviour. Existing `.en.bin` models sufficient.

### For multilingual deployments

1. Download multilingual models (see `docs/testing/WHISPER_CPP_SETUP.md`).
2. Pass job language explicitly:
   - Urdu content: `{ "language": "ur", "whisper_model": "base" }`
   - Mixed English + Urdu: `{ "language": "auto", "whisper_model": "base" }`
3. Optional: set `WHISPER_ROUTING_POLICY=multilingual_default` to auto-detect when language omitted (future global policy — test before enabling).

### Operator checklist

| Step | Action |
|------|--------|
| Pull M2 code | `feature/whisper-multilingual` |
| Restart Celery worker | Required after config/code change |
| English hosts | No model download needed |
| Multilingual hosts | Download `ggml-{tiny,base,small}.bin` (~683 MB) |
| Client apps | Send `language` for non-English uploads |

### Disk impact

| Deployment | Models on disk |
|------------|----------------|
| English-only (current) | ~681 MB (`.en` trio) |
| Full bilingual | ~1.36 GB (`.en` + multilingual trio) |

---

## Configuration Reference

```bash
# .env — defaults preserve Phase 5 behaviour
WHISPER_ROUTING_POLICY=english_first
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_LANGUAGE=en   # legacy; routing uses parameters.language + policy
```

| Policy | Omitted `language` behaviour |
|--------|------------------------------|
| `english_first` (default) | `.en.bin` + `-l en` |
| `multilingual_default` | `.bin` + auto-detect |

---

## Related Reports

| Report | Relationship |
|--------|--------------|
| `PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md` | Design approved for M2 |
| `WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md` | Root cause |
| `PHASE5_MILESTONE1_WHISPER_MODELS.md` | Baseline API contract |
| `PHASE6_M2_VALIDATION_REPORT.md` | Subprocess isolation pattern |

---

## Next Steps (out of M2 scope)

- [ ] Download multilingual models and record E2E job IDs (Urdu sample, mixed EN+Urdu)
- [ ] Phase 5 English regression smoke test after multilingual models installed
- [ ] Update `docs/context/CURRENT_PROJECT_STATE.md` after validation tag
- [ ] Flutter client: send `language: "auto"` or explicit code for non-English media

---

*Milestone 2 implementation complete.*
