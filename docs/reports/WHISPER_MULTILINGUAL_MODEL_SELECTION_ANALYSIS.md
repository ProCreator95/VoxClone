# Whisper Multilingual Model Selection — Root Cause Analysis

**Status:** Investigation complete (documentation only — no code changes)
**Date:** 2026-06-22
**Branch:** `feature/audio-enhancement` (working tree)
**Trigger:** Multilingual media is being transcribed with `ggml-tiny.en.bin`

---

## Executive Summary

Multilingual media is transcribed with `ggml-tiny.en.bin` because **the pipeline is designed to always resolve Whisper aliases to English-only `.en.bin` files**. There is no pre-transcription language detection and no code path that selects multilingual GGML models. For `subtitle_generation` jobs, the default alias is `tiny`, which maps unconditionally to `ggml-tiny.en.bin`.

This is not a runtime misconfiguration or accidental fallback — it is the current intended architecture (Phase 5 per-job model selection scoped to English-only models). Urdu and other non-English languages are **not supported** by any model currently installed under `backend/models/`.

---

## Investigation Questions — Answers

### 1. How is `whisper_model_file` selected?

Selection flows through `resolve_whisper_model()` in `backend/app/services/whisper_models.py`:

| Priority | Condition | Result |
|----------|-----------|--------|
| 1 | `parameters.whisper_model` provided (`tiny` \| `base` \| `small`) | Alias validated → mapped via `WHISPER_MODEL_FILES` |
| 2 | Alias omitted, `job_type` in `WHISPER_MODEL_DEFAULTS` | Job-type default alias → mapped via `WHISPER_MODEL_FILES` |
| 3 | Neither applies | Fallback to global `WHISPER_MODEL_PATH` from `.env` |

The alias → filename mapping is **hardcoded and English-only**:

```python
WHISPER_MODEL_FILES = {
    "tiny":  "ggml-tiny.en.bin",
    "base":  "ggml-base.en.bin",
    "small": "ggml-small.en.bin",
}
```

Job-type defaults:

| Job type | Default alias | Resolved file |
|----------|---------------|---------------|
| `subtitle_generation` | `tiny` | `ggml-tiny.en.bin` |
| `karaoke` | `base` | `ggml-base.en.bin` |

After transcription completes, tasks persist metadata:

```python
params["whisper_model"] = resolved_alias          # e.g. "tiny"
params["whisper_model_file"] = model_path.name  # e.g. "ggml-tiny.en.bin"
```

This persistence happens in:

- `generate_subtitles_task` — `backend/app/tasks/media_tasks.py` (~lines 352–358)
- `_karaoke_persist_whisper_metadata` — same file (~lines 706–716)

The actual model used at runtime is resolved again inside `WhisperService.transcribe()` via the same `resolve_whisper_model()` call (~lines 437–439 in `whisper_service.py`).

---

### 2. Does language detection occur before model selection?

**No.**

Language handling order in the pipeline:

```
1. resolve_whisper_model()     ← model chosen here (alias → .en.bin)
2. WhisperService.transcribe() ← passes -l flag to whisper.cpp
3. whisper.cpp runs            ← may report detected language in JSON output
4. params["detected_language"] ← written AFTER transcription completes
```

There is no standalone language-detection service, no FFmpeg-based language probe, and no upload-time language metadata on media records. `_detect_media_type()` in `upload_service.py` detects **file type** (video/audio), not spoken language.

The `language` job parameter (optional) is read in tasks and passed to `transcribe()`, but it does **not** influence model selection — only the `-l` whisper.cpp flag:

```python
language: Optional[str] = params.get("language") or None
# ...
transcript = await whisper.transcribe(
    audio_path=audio_path,
    language=language,
    whisper_model=whisper_model_param,
    job_type=JobType.SUBTITLE_GENERATION,
)
```

Inside `WhisperService.transcribe()`:

```python
lang = language or self._settings.WHISPER_LANGUAGE or None
# WHISPER_LANGUAGE defaults to "en" in config.py
```

If `parameters.language` is omitted, whisper.cpp receives `-l en` (not auto-detect), because the settings default is `"en"`.

`detected_language` in completed job parameters comes from whisper.cpp JSON output **after** transcription:

```python
language = str((data.get("result") or {}).get("language") or "")
```

This is a **post-hoc report**, not an input to model routing.

---

### 3. Are English-only models being chosen automatically?

**Yes — always.**

Every supported alias resolves to a `.en.bin` file. There is no alias for multilingual equivalents (`ggml-tiny.bin`, `ggml-base.bin`, etc.).

Additional English-locking factors:

| Factor | Location | Effect |
|--------|----------|--------|
| `WHISPER_MODEL_FILES` | `whisper_models.py` | Only `.en.bin` filenames |
| `WHISPER_MODEL_PATH` default | `config.py` | `models/ggml-tiny.en.bin` |
| `WHISPER_LANGUAGE` default | `config.py` | `"en"` → `-l en` passed to whisper.cpp |
| API validation | `schemas/job.py` | Only `tiny` \| `base` \| `small` aliases |
| Documentation / setup | `WHISPER_CPP_SETUP.md`, `.env.example` | Explicitly documents English-only models |
| Installed files | `backend/models/` | Only three `.en.bin` files present |

The `whisper_model` API parameter controls **size tier** (tiny/base/small), not **language scope** (English vs multilingual). Users cannot request a multilingual model through the current API.

---

### 4. Can mixed-language media force multilingual models?

**No.**

There is no logic that:

- Detects multiple languages in source audio
- Switches model variant based on content language
- Escalates from `.en` to multilingual models when transcription quality is poor
- Reads user-provided locale hints from upload metadata

Even if a caller sets `parameters.language` to a non-English code (e.g. `"ur"`) or sets `WHISPER_LANGUAGE=""` for auto-detect, the **model file remains an English-only `.en.bin`**. Whisper `.en` models cannot transcribe non-English speech correctly; they are trained and optimized for English only. Passing `-l ur` with `ggml-tiny.en.bin` would be a model/language mismatch.

The `language` parameter is not validated in `JobCreate` — it is passed through silently — but it does not change model selection.

---

### 5. Is Urdu supported by currently installed Whisper models?

**No.**

### Installed models (verified on disk)

```
backend/models/ggml-tiny.en.bin    75 MB
backend/models/ggml-base.en.bin   142 MB
backend/models/ggml-small.en.bin  466 MB
```

No multilingual GGML files (e.g. `ggml-base.bin`, `ggml-small.bin`) are present.

### Urdu and Whisper

OpenAI Whisper (and whisper.cpp) supports Urdu under language code **`ur`**, but only via **multilingual** model weights. English-only `.en` variants do not include Urdu vocabulary or tokenizer coverage for Urdu script.

Expected behavior with current setup on Urdu audio:

- Model: `ggml-tiny.en.bin` (default for subtitle jobs)
- Language flag: `-l en` (settings default)
- Result: Garbled, empty, or incorrectly Romanized/English hallucination — not usable Urdu subtitles

To support Urdu, the system would need at minimum:

1. A multilingual GGML model (e.g. `ggml-base.bin` or larger)
2. `-l ur` or auto-detect with a multilingual model
3. API/config changes to select multilingual variants

---

## Root Cause Analysis

### Primary root cause

**Architectural constraint:** Model selection is decoupled from language and hardwired to English-only GGML files. The Phase 5 per-job `whisper_model` feature added size-tier selection (`tiny`/`base`/`small`) but did not add language-aware or multilingual model routing.

### Contributing factors

1. **Default subtitle job uses smallest English model** — `subtitle_generation` → `tiny` → `ggml-tiny.en.bin`, maximizing speed at the cost of accuracy for any language, including English.

2. **Default language hint is English** — `WHISPER_LANGUAGE=en` forces `-l en` unless overridden per job, which prevents whisper.cpp auto-detection even if a multilingual model were installed.

3. **Post-hoc `detected_language` creates false confidence** — Jobs may report `"detected_language": "en"` after running an English-only model with `-l en`, which does not prove the source audio was English.

4. **No multilingual models shipped or documented in resolver** — `WHISPER_MODEL_FILES`, download scripts, and setup docs only reference `.en.bin` files.

5. **API surface does not expose language scope** — Clients can pass `whisper_model` but cannot request multilingual models or declare expected source language in a validated way.

### What this is NOT

- Not a Celery worker caching the wrong model — model is resolved fresh per `transcribe()` call
- Not a bug in `whisper_model_file` persistence — metadata correctly reflects what was used
- Not missing `WHISPER_MODEL_PATH` — global path is a fallback; job-type defaults take precedence for Whisper tasks

---

## Affected Code Paths

```
POST /api/v1/jobs
  └── JobCreate (schemas/job.py)
        └── validates whisper_model alias only (tiny|base|small)
        └── no language / multilingual validation

dispatch_job → generate_subtitles_task | generate_karaoke_task
  └── media_tasks.py
        ├── params.get("language")           → optional -l override
        ├── params.get("whisper_model")      → optional size alias
        └── WhisperService.transcribe(...)

WhisperService.transcribe()  (whisper_service.py)
  └── resolve_whisper_model()  (whisper_models.py)  ← MODEL SELECTED
  └── lang = language or WHISPER_LANGUAGE         ← LANGUAGE HINT
  └── subprocess: whisper-cli -m <model> -l <lang> ...

Post-transcription
  └── params["detected_language"] = transcript.language
  └── params["whisper_model_file"] = model_path.name
```

### Key files

| File | Role |
|------|------|
| `backend/app/services/whisper_models.py` | Alias → `.en.bin` mapping, defaults, resolver |
| `backend/app/services/whisper_service.py` | Subprocess invocation, language flag, JSON parse |
| `backend/app/core/config.py` | `WHISPER_MODEL_PATH`, `WHISPER_LANGUAGE` defaults |
| `backend/app/tasks/media_tasks.py` | Job parameters → transcribe wiring, metadata persistence |
| `backend/app/schemas/job.py` | API validation (whisper_model aliases only) |
| `backend/app/api/v1/endpoints/jobs.py` | OpenAPI docs (no language/multilingual guidance) |
| `backend/.env.example` | Documents English-only model set |
| `docs/testing/WHISPER_CPP_SETUP.md` | Download instructions for `.en.bin` only |
| `backend/models/` | On-disk model inventory (English-only) |

---

## Recommended Fix (No Implementation)

Proposed direction for a follow-up milestone — **multilingual-aware Whisper model routing**.

### Option A — Dual variant aliases (minimal API change)

Extend the model registry to distinguish English vs multilingual:

```
tiny.en  → ggml-tiny.en.bin
base.en  → ggml-base.en.bin
tiny     → ggml-tiny.bin      (multilingual)
base     → ggml-base.bin
```

Add job parameter `whisper_model_variant: "en" | "multilingual"` (default based on `language` hint), or auto-select multilingual when `parameters.language` is set and not `"en"`.

### Option B — Language-first routing (recommended)

1. Accept validated `parameters.language` (BCP-47, e.g. `ur`, `hi`, `en`).
2. If `language == "en"` (or omitted with English-only policy) → use `.en.bin` for speed.
3. If `language != "en"` or `language` omitted with auto-detect policy → require multilingual model.
4. Optionally run a lightweight detection pass (small multilingual model or ffmpeg/speech heuristic) **before** main transcription when language is unknown.

### Option C — Single multilingual default (simplest operationally)

Replace English-only defaults with multilingual models (`ggml-base.bin`), set `WHISPER_LANGUAGE=""` for auto-detect, and document the RAM/speed tradeoff. English accuracy drops slightly vs `.en` models but all supported Whisper languages become available.

### Implementation checklist (future work)

- [ ] Add multilingual GGML files to `WHISPER_MODEL_FILES` (or parallel registry)
- [ ] Update `resolve_whisper_model()` to accept language / variant inputs
- [ ] Validate `parameters.language` in `JobCreate`
- [ ] Document download steps for multilingual models in `WHISPER_CPP_SETUP.md`
- [ ] Update `.env.example` with language routing policy
- [ ] Add integration tests: Urdu sample → multilingual model + `-l ur`
- [ ] Update OpenAPI job description with language parameters
- [ ] Decide policy for mixed-language content (auto-detect vs forced primary language)

### Urdu-specific recommendation

For Urdu content:

- Model: at least `ggml-base.bin` (multilingual); `ggml-small.bin` for higher accuracy
- Flag: `-l ur` when language is known; auto-detect only with multilingual weights
- Do **not** use any `.en.bin` model

---

## Verification Performed

| Check | Result |
|-------|--------|
| Read `whisper_models.py` resolver logic | Confirms hardcoded `.en.bin` mapping |
| Read `whisper_service.py` transcribe flow | Model selected before language flag |
| Read `media_tasks.py` subtitle + karaoke paths | No pre-detection; post-hoc `detected_language` |
| Read `config.py` / `.env.example` defaults | `WHISPER_LANGUAGE=en`, `WHISPER_MODEL_PATH=ggml-tiny.en.bin` |
| Grep codebase for multilingual / Urdu routing | No implementation found |
| List `backend/models/` | Only `ggml-{tiny,base,small}.en.bin` (681 MB total) |

---

## Related Documentation

| Document | Relevance |
|----------|-----------|
| `docs/reports/PHASE5_MILESTONE1_WHISPER_MODELS.md` | Per-job size selection design (English-only scope) |
| `docs/testing/WHISPER_CPP_SETUP.md` | States ".en models are English-only" |
| `docs/context/CURRENT_PROJECT_STATE.md` | Lists installed `.en.bin` models |
| `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md` | Whisper accuracy on music (English model limitation) |

---

## Conclusion

Multilingual media is transcribed with `ggml-tiny.en.bin` because the resolver, defaults, installed artifacts, and language settings collectively enforce an **English-only transcription stack**. Language is not detected before model selection, mixed-language content cannot trigger multilingual models, and Urdu is unsupported until multilingual GGML weights are added and routing logic ties model variant to source language.

**Next step:** Implement one of the recommended fix options in a dedicated milestone (separate from this analysis).
