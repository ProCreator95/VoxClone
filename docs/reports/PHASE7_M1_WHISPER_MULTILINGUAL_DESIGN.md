# Phase 7 — Milestone 1: Whisper Multilingual Support — Investigation and Design

**Status:** Complete (investigation + design only — no code changes)
**Date:** 2026-06-22
**Branch:** `feature/whisper-multilingual`
**Baseline:** Phase 6 production complete (`feature/audio-enhancement`); Phase 5 baseline `phase5-final` @ `ddb2366`
**Prior analysis:** `docs/reports/WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md`

---

## Executive Summary

Mixed-language media (e.g. English introduction + Urdu content) fails because VoxClone **always** resolves Whisper size aliases to English-only `.en.bin` models and passes `-l en` by default. Urdu, Hindi, Arabic, Persian, and other non-English languages are unsupported until multilingual GGML weights are installed and model routing is tied to language intent.

**Recommended architecture:** **Option B — language-first routing**, with a backward-compatible default policy and explicit `auto` language mode for mixed-language content. Option A may be added later as a power-user override. Option C is **not recommended** as a default migration path.

**Go / No-Go:** **GO** for Phase 7 Milestone 2 implementation (Option B). **NO-GO** for Option C as an immediate global replacement without a migration period.

---

## 1. Documentation Reviewed

| Document | Purpose |
|----------|---------|
| `docs/context/MASTER_PROJECT_HANDOFF.md` | Architecture, Whisper subprocess pattern, Phase 5 parameters, known music-accuracy limitation |
| `docs/context/CURRENT_PROJECT_STATE.md` | Environment pins, installed `.en.bin` models, component status through Phase 6 |
| `docs/context/NEXT_SESSION_START_HERE.md` | Phase 6 completion state, DeepFilterNet integration rules |
| `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md` | Whisper `.en` music gaps (Limitation 1); subprocess/LD_LIBRARY_PATH fixes |
| `docs/reports/WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md` | Root-cause analysis, affected code paths, initial option sketch |
| `docs/reports/PHASE6_M2_VALIDATION_REPORT.md` | Phase 6 validation posture; confirms Whisper/Demucs subprocess isolation unchanged |
| `docs/reports/PHASE5_MILESTONE1_WHISPER_MODELS.md` | Per-job `whisper_model` API contract and defaults |
| `docs/testing/WHISPER_CPP_SETUP.md` | Model sizes, CPU timing baselines, English-only documentation |
| `backend/app/services/whisper_models.py` | Current resolver (verified unchanged) |
| `backend/app/services/whisper_service.py` | Subprocess invocation, language flag, JSON parse |
| `backend/app/tasks/media_tasks.py` | Subtitle + karaoke Whisper wiring |
| `backend/app/core/config.py` | `WHISPER_MODEL_PATH`, `WHISPER_LANGUAGE` defaults |
| HuggingFace `ggerganov/whisper.cpp` model table | Multilingual GGML file names and disk sizes |

---

## 2. Current Architecture

### 2.1 End-to-end flow

```
POST /api/v1/jobs  (subtitle_generation | karaoke)
  │
  ├─ JobCreate validates whisper_model ∈ {tiny, base, small}  (language NOT validated)
  │
  └─ Celery task (media_tasks.py)
        │
        ├─ FFmpeg: extract / reuse audio (16 kHz mono WAV)
        │
        ├─ language ← parameters.language OR None
        ├─ whisper_model ← parameters.whisper_model OR job-type default
        │
        └─ WhisperService.transcribe(audio, language, whisper_model, job_type)
              │
              ├─ resolve_whisper_model()  → alias + Path (*.en.bin)     ← MODEL SELECTED
              ├─ lang = language OR WHISPER_LANGUAGE ("en")             ← LANGUAGE HINT
              └─ whisper-cli -m <model> -f <wav> -t <threads> -l en ...
                    │
                    └─ JSON → SRT/VTT/TXT/ASS; detected_language persisted post-hoc
```

### 2.2 Model resolution (today)

`resolve_whisper_model()` in `whisper_models.py`:

| Priority | Input | Output |
|----------|-------|--------|
| 1 | `whisper_model` param set | Validated alias → `WHISPER_MODEL_FILES[alias]` |
| 2 | Alias omitted + known `job_type` | `WHISPER_MODEL_DEFAULTS[job_type]` → file |
| 3 | Fallback | Global `WHISPER_MODEL_PATH` from `.env` |

Hardcoded mapping (English-only):

| Alias | File | Job default |
|-------|------|-------------|
| `tiny` | `ggml-tiny.en.bin` | `subtitle_generation` |
| `base` | `ggml-base.en.bin` | `karaoke` |
| `small` | `ggml-small.en.bin` | — |

### 2.3 Language parameter handling

| Layer | Behaviour |
|-------|-----------|
| `parameters.language` | Optional; read in tasks; **not validated** at API layer |
| `WhisperService.transcribe()` | `lang = language or WHISPER_LANGUAGE or None` |
| `config.py` default | `WHISPER_LANGUAGE = "en"` |
| whisper.cpp CLI | `-l <code>` appended when `lang` is truthy; omitted only when `lang` is `None`/empty |
| `detected_language` | Parsed from JSON **after** run; does not influence model choice |

**Effective default today:** every job without `parameters.language` runs with `-l en` on an `.en.bin` model.

### 2.4 Language auto-detection behaviour

Whisper.cpp supports auto-detection when the `-l` flag is **omitted**, but only on **multilingual** model weights. With current defaults:

- Model: English-only (`.en.bin`)
- Flag: `-l en`

Auto-detection is **never exercised** in production paths. Post-transcription `detected_language` reflects whisper.cpp's report for the forced run, not a pre-selection probe.

### 2.5 whisper.cpp multilingual model support

Per upstream `ggerganov/whisper.cpp` and OpenAI Whisper documentation:

- Models **without** `.en` in the filename are **multilingual** (99 languages).
- Models **with** `.en` are English-only, faster and slightly more accurate for English.
- Same size tiers exist in both variants: `tiny`, `base`, `small`, `medium` (+ `large-v3`, `turbo` multilingual-only).
- VoxClone currently documents and installs **only** the three `.en` tiers.

Supported language codes include (relevant to stated requirements):

| Language | BCP-47 | Multilingual model | `.en` model |
|----------|--------|--------------------|-------------|
| English | `en` | ✅ | ✅ |
| Urdu | `ur` | ✅ | ❌ |
| Hindi | `hi` | ✅ | ❌ |
| Arabic | `ar` | ✅ | ❌ |
| Persian (Farsi) | `fa` | ✅ | ❌ |

### 2.6 Installed artifacts (verified)

```
backend/models/ggml-tiny.en.bin     75 MB
backend/models/ggml-base.en.bin    142 MB
backend/models/ggml-small.en.bin   466 MB
Total: ~681 MB — English-only only
```

No `ggml-tiny.bin`, `ggml-base.bin`, or `ggml-small.bin` present.

### 2.7 Phase 5 / Phase 6 isolation

| System | Integration | Phase 7 impact |
|--------|-------------|----------------|
| Whisper | whisper.cpp subprocess | **In scope** |
| Demucs | demucs subprocess | None — no shared model dir |
| DeepFilterNet | `deep-filter` subprocess | None — no Whisper dependency |
| ML Python stack | `requirements-ml.txt` pins | None — Whisper stays subprocess-only |

Phase 6 dependency protection rules remain satisfied: no new Python ML packages required for multilingual Whisper.

---

## 3. Root Cause Summary

### Observed failure (mixed English + Urdu)

| Symptom | Cause |
|---------|-------|
| Model `ggml-tiny.en.bin` used | `subtitle_generation` default alias `tiny` → hardcoded `.en.bin` map |
| Repeated English hallucinations | English-only model forced to interpret non-English speech |
| `(speaking in foreign language)` | Known Whisper behaviour when model/language cannot represent audio |
| Bad subtitles and karaoke | Same transcript feeds SRT/VTT/ASS pipelines faithfully |

### Architectural root cause

Model selection is **decoupled from language**. Phase 5 added per-job **size** selection (`tiny`/`base`/`small`) but scoped exclusively to English-only GGML files. Language is applied as a CLI hint **after** the wrong model is already chosen.

### Contributing defaults

1. `WHISPER_LANGUAGE=en` — forces English mode unless overridden per job.
2. Omitted `parameters.language` — inherits English default; no auto-detect path.
3. No multilingual models on disk — even correct routing would fail at `validate()` until download.
4. `detected_language` post-hoc — can misleadingly report `en` when `-l en` was forced.

---

## 4. Model Compatibility Matrix

### 4.1 GGML variants (tiny / base / small)

| Tier | English-only file | Multilingual file | Disk (each) | RAM @ runtime (approx.) | Languages |
|------|-------------------|-------------------|-------------|-------------------------|-----------|
| tiny | `ggml-tiny.en.bin` | `ggml-tiny.bin` | 75 MiB | ~300 MB | en only / 99 langs |
| base | `ggml-base.en.bin` | `ggml-base.bin` | 142 MiB | ~500 MB | en only / 99 langs |
| small | `ggml-small.en.bin` | `ggml-small.bin` | 466 MiB | ~1.2 GB | en only / 99 langs |

Source: HuggingFace `ggerganov/whisper.cpp` model table; RAM from `docs/testing/WHISPER_CPP_SETUP.md` (English tiers; multilingual same order of magnitude).

### 4.2 Language × model compatibility

| Scenario | `.en.bin` model | Multilingual `.bin` model | `-l en` | `-l ur` (etc.) | No `-l` (auto) |
|----------|-----------------|---------------------------|---------|----------------|----------------|
| English speech | ✅ Optimal | ✅ Good | ✅ | ❌ Wrong lang | ✅ → en |
| Urdu speech | ❌ Fails / hallucinates | ✅ | ❌ | ✅ | ✅ → ur |
| Hindi / Arabic / Persian | ❌ | ✅ | ❌ | ✅ | ✅ |
| Mixed EN + Urdu | ❌ | ⚠️ Partial — single-pass auto-detect; code-switching limitations | ❌ | ⚠️ Urdu forced for English sections | ⚠️ Best available single-pass |
| Music-heavy English (known gap) | ⚠️ tiny weak; base/small better | ⚠️ Slightly worse EN WER vs `.en` | ✅ | — | — |

### 4.3 Feature compatibility (VoxClone pipelines)

| Pipeline | Depends on | Multilingual change risk |
|----------|------------|--------------------------|
| `subtitle_generation` | `--output-json` | Low — same JSON layout |
| `karaoke` | `--output-json-full`, word tokens | Low — token grouping unchanged |
| `subtitle_burn` | SRT from prior job | None — no Whisper in burn task |
| `vocal_separation` | Demucs only | None |
| `audio_enhance` | deep-filter only | None |

---

## 5. Urdu Support Analysis

### 5.1 Whisper capability

- Urdu is in the Whisper multilingual language set (`ur`).
- Requires a multilingual GGML file (`ggml-base.bin` minimum recommended; `ggml-small.bin` for higher quality on non-Latin script).
- Output is typically Arabic-script Unicode (Urdu orthography). UTF-8 SRT/VTT/ASS paths already used — no encoding change expected.

### 5.2 Minimum viable Urdu stack

| Setting | Value |
|---------|-------|
| Model | `ggml-base.bin` (or `ggml-small.bin`) |
| Language flag | `-l ur` when Urdu is known; omit `-l` for unknown/mixed |
| Must NOT use | Any `.en.bin` model |

### 5.3 Mixed English introduction + Urdu body

This is the reported test case. Recommended handling:

| Approach | Viability |
|----------|-----------|
| `-l en` + `.en.bin` | ❌ Current broken path |
| `-l ur` + multilingual | ⚠️ English intro transcribed poorly |
| Auto-detect + multilingual | ✅ **Best single-pass option** — whisper.cpp detects dominant language per run; handles many code-switching cases better than forced English |
| Segment split + per-segment language | 🔮 Future — out of scope for M2; requires audio segmentation |

**Design implication:** Option B must define an **`auto` language mode** (omit `-l`, use multilingual model) distinct from `language: "en"`.

### 5.4 Karaoke-specific note

Urdu karaoke ASS relies on word-level tokens from `--output-json-full`. Multilingual models produce the same JSON schema; `\kf` timing quality depends on token boundaries for Arabic-script words — requires M2 validation with real Urdu sample, but no architectural blocker.

---

## 6. Performance Estimates

Baseline from `docs/testing/WHISPER_CPP_SETUP.md` (32 GB RAM, 8-core CPU, English `.en` models). Multilingual same-tier models have **similar parameter counts and GGML sizes** — expect **comparable CPU time and RAM** (within ~10–20%).

### 6.1 Relative speed (same tier)

| Tier | Speed vs realtime (CPU) | RAM |
|------|-------------------------|-----|
| tiny / tiny.en | ~10× | ~300 MB |
| base / base.en | ~6× | ~500 MB |
| small / small.en | ~3× | ~1.2 GB |

### 6.2 Wall-clock estimates (base tier, ~6× realtime)

| Audio length | base.en (today karaoke default) | base (multilingual) |
|--------------|-----------------------------------|---------------------|
| 1 minute | 10–30 s | ~10–35 s |
| 10 minutes | 90–240 s | ~100–260 s |
| 60 minutes | 8–20 min | ~9–22 min |

### 6.3 Accuracy tradeoffs (English)

Published Whisper benchmarks (LibriSpeech / general guidance):

| Tier | English WER (`.en`) | English WER (multilingual) | Delta |
|------|---------------------|----------------------------|-------|
| tiny | ~7.6% | ~12% | Multilingual worse |
| base | ~5.0% | ~10% | Multilingual worse |
| small | ~3.4% | ~7% | Multilingual worse |

**Implication:** Option B preserves `.en` models for `language=en`, avoiding regression for English-only workloads. Option C would accept this WER increase globally.

### 6.4 Worker / queue impact

- Whisper runs on Celery `ai` queue alongside Demucs and `audio_enhance`.
- Multilingual base/small use same RAM envelope as current `.en` counterparts — no new queue required.
- `--concurrency=1` guidance for Demucs OOM remains applicable; no change.

---

## 7. Storage Requirements

### 7.1 Current

| Files | Disk |
|-------|------|
| `ggml-tiny.en.bin` + `ggml-base.en.bin` + `ggml-small.en.bin` | **~681 MB** |

### 7.2 Option A / B (retain English + add multilingual)

Download three multilingual counterparts:

| File | Disk |
|------|------|
| `ggml-tiny.bin` | 75 MiB |
| `ggml-base.bin` | 142 MiB |
| `ggml-small.bin` | 466 MiB |
| **Additional** | **~683 MiB** |
| **Total both sets** | **~1.36 GB** |

### 7.3 Option C (multilingual only — replace `.en`)

| Deployment | Disk |
|------------|------|
| Remove `.en`, keep multilingual trio | **~683 MB** (similar to today) |
| Or base-only minimal deploy | **~142 MB** (+ optional small for quality) |

### 7.4 Optional future tiers (not in M2 scope)

| Model | Disk | Notes |
|-------|------|-------|
| `ggml-medium.bin` | 1.5 GiB | Higher quality; slow on CPU |
| `ggml-large-v3-turbo.bin` | 1.5 GiB | Best quality/speed balance for large model |
| Quantized (`-q5_0`, `-q8_0`) | 30–60% smaller | Accuracy tradeoff; not validated in VoxClone |

### 7.5 Git / repo policy

GGML files remain **out of git** (same as today). Document download in `WHISPER_CPP_SETUP.md`. Optional: `scripts/download_whisper_model.sh` extension for multilingual variants.

---

## 8. API Impact Assessment

### 8.1 Current API surface

```json
{
  "media_id": "<uuid>",
  "job_type": "subtitle_generation",
  "parameters": {
    "whisper_model": "tiny | base | small",
    "language": "<optional, unvalidated string>"
  }
}
```

Completed job metadata:

```json
{
  "whisper_model": "tiny",
  "whisper_model_file": "ggml-tiny.en.bin",
  "detected_language": "en"
}
```

### 8.2 Option A — separate aliases

**Proposed API extension:**

```
whisper_model: tiny.en | base.en | small.en | tiny | base | small
```

| Aspect | Impact |
|--------|--------|
| Breaking change | ⚠️ **Yes, if bare `tiny`/`base`/`small` flip from `.en` to multilingual** |
| Backward compat | ✅ Safe only if `.en` suffix required for English-only OR bare aliases stay `.en` and new bare names mean multilingual (confusing) |
| Client burden | High — clients must understand two parallel alias sets |
| Validation | Extend `WHISPER_MODEL_ALIASES` and `JobCreate` validator |

**Assessment:** Useful as an **optional power-user override** alongside Option B, not as the primary routing mechanism.

### 8.3 Option B — language-first routing (recommended)

**Minimal API changes:**

| Change | Type | Details |
|--------|------|---------|
| `parameters.language` validation | Additive | Accept BCP-47 codes Whisper supports + sentinel `"auto"` |
| OpenAPI / job description | Docs | Document language values and routing behaviour |
| `whisper_model_file` values | Behavioural | May become `ggml-base.bin` etc. when language ≠ en |
| New env settings | Server-side | e.g. `WHISPER_ROUTING_POLICY`, optional `WHISPER_DEFAULT_LANGUAGE` |
| `whisper_model` param | **Unchanged** | Still `tiny` \| `base` \| `small` — controls size tier only |

**Proposed routing rules (M2 target):**

```
resolve(language, whisper_model_alias, job_type):
  tier ← whisper_model_alias OR job-type default OR global fallback

  if language == "en":
    model ← ggml-{tier}.en.bin
    cli_lang ← "en"
  elif language == "auto" OR language is None AND policy == "auto":
    model ← ggml-{tier}.bin
    cli_lang ← omit -l
  elif language is None AND policy == "english_first":   # backward compatible default
    model ← ggml-{tier}.en.bin
    cli_lang ← "en"
  else:  # explicit non-English code (ur, hi, ar, fa, ...)
    model ← ggml-{tier}.bin
    cli_lang ← language
```

**New persisted metadata (recommended):**

```json
{
  "whisper_model": "base",
  "whisper_model_file": "ggml-base.bin",
  "whisper_model_variant": "multilingual",
  "language_requested": "auto",
  "detected_language": "ur"
}
```

### 8.4 Option C — multilingual globally

| Aspect | Impact |
|--------|--------|
| API | No new parameters required |
| Default behaviour | **Breaking** — all jobs slower for English; WER regression |
| `WHISPER_LANGUAGE` | Must change default from `"en"` to `""` |
| `whisper_model_file` | Always `ggml-*.bin` — clients parsing `.en.bin` break |
| Phase 5 regression | English subtitle/karaoke quality and timing baselines shift |

### 8.5 Phase 5 / Phase 6 backward compatibility matrix

| Client / behaviour | Option A | Option B (`english_first` default) | Option C |
|--------------------|----------|-------------------------------------|----------|
| Omit `language`, English media | ✅ if aliases unchanged | ✅ unchanged | ⚠️ behaviour change |
| Omit `language`, Urdu media | ❌ unless client picks multilingual alias | ⚠️ needs `language:auto` or policy flip | ✅ |
| `whisper_model=tiny` for subtitles | ✅ | ✅ same alias semantics | ✅ tier unchanged |
| Karaoke default `base` | ✅ | ✅ | ⚠️ model file name changes |
| Parse `whisper_model_file.endswith('.en.bin')` | ✅ | ✅ for English jobs | ❌ |
| `audio_enhance` / Demucs jobs | ✅ | ✅ | ✅ |

---

## 9. Option Evaluation

### Option A — Dual alias sets (`tiny.en` / `tiny`, etc.)

| Criterion | Assessment |
|-----------|------------|
| Solves Urdu / multilingual | ✅ When client selects non-`.en` alias |
| Mixed-language auto routing | ❌ Still manual unless combined with language param |
| Backward compatibility | ⚠️ Fragile — alias semantics easy to misconfigure |
| API complexity | High — six+ aliases, documentation burden |
| Implementation effort | Medium — registry + validation refactor |
| Operator burden | Must download both model sets |

**Verdict:** **Secondary mechanism** — expose as explicit override (`whisper_model: "base"` + internal variant flag) rather than primary UX.

---

### Option B — Language-first routing ✅ Preferred

| Criterion | Assessment |
|-----------|------------|
| Solves Urdu / multilingual | ✅ With explicit code or `auto` |
| Mixed-language | ✅ `language: "auto"` + multilingual model |
| Backward compatibility | ✅ With `english_first` default policy |
| API complexity | Low — validate existing `language` param + document `auto` |
| Implementation effort | Medium — extend `resolve_whisper_model()`, thread language into resolver, update tasks |
| Operator burden | Download multilingual trio alongside existing `.en` files |

**Verdict:** **Recommended for Phase 7 M2.**

---

### Option C — Multilingual only, remove `.en`

| Criterion | Assessment |
|-----------|------------|
| Solves Urdu / multilingual | ✅ |
| Mixed-language | ✅ With auto-detect default |
| Backward compatibility | ❌ English speed/accuracy regression |
| API complexity | Lowest |
| Implementation effort | Low–medium — simplify map, change defaults |
| Disk | Can reduce if `.en` removed (~683 MB vs ~1.36 GB dual) |

**Verdict:** **Not recommended as default.** Acceptable only as a **deployment profile** for hosts that never process English (e.g. Urdu-only appliance).

---

## 10. Recommended Architecture

### 10.1 Decision

Implement **Option B** in Phase 7 Milestone 2 with:

1. **Dual on-disk model registry** — English and multilingual filenames per tier.
2. **Language-first resolver** — model variant derived from `language` + server policy.
3. **`language: "auto"`** — multilingual model, omit `-l` (critical for mixed EN+Urdu).
4. **`WHISPER_ROUTING_POLICY=english_first`** — default preserves Phase 5 behaviour until operators opt in.
5. **Validated `parameters.language`** — reject unsupported codes at API layer (422).
6. **Extended job metadata** — `whisper_model_variant`, `language_requested` for auditability.

### 10.2 Proposed resolver signature (M2 — design only)

```python
resolve_whisper_model(
    whisper_model: Optional[str],
    job_type: str,
    language: Optional[str],      # NEW
    settings: Settings,
) -> ResolvedWhisperModel:
    # alias, path, variant ("english" | "multilingual"), cli_language (str | None)
```

### 10.3 Configuration additions (design)

| Setting | Default | Purpose |
|---------|---------|---------|
| `WHISPER_ROUTING_POLICY` | `english_first` | `english_first` \| `auto` — behaviour when `language` omitted |
| `WHISPER_LANGUAGE` | `en` | Fallback when policy is `english_first` and language omitted |
| `WHISPER_MODEL_PATH` | `models/ggml-tiny.en.bin` | Unchanged global fallback for non-job tooling |

### 10.4 Files to change (M2 scope — not implemented in M1)

| File | Change |
|------|--------|
| `whisper_models.py` | Dual registry, language-aware resolver, variant metadata |
| `whisper_service.py` | Pass language into resolver; omit `-l` when `cli_language is None` |
| `media_tasks.py` | Thread `language` into resolver; persist new metadata keys |
| `schemas/job.py` | Validate `language` against allowlist + `"auto"` |
| `config.py` | `WHISPER_ROUTING_POLICY` |
| `.env.example` | Document policy and multilingual downloads |
| `docs/testing/WHISPER_CPP_SETUP.md` | Multilingual download + routing guide |

**Explicit non-changes:** `audio_enhancement_service.py`, Demucs services, Celery routing, ML requirements.

### 10.5 Migration strategy

#### Phase A — Documentation + downloads (operator)

1. Download multilingual trio to `backend/models/`.
2. Set `WHISPER_ROUTING_POLICY=auto` on hosts serving multilingual users.
3. Keep `english_first` on English-only deployments — zero behaviour change.

#### Phase B — M2 implementation

1. Ship language-aware resolver behind policy flag.
2. Add API validation for `language`.
3. Log `whisper_model_variant` in structured logs (`whisper_cpp_transcribe_start`).

#### Phase C — Validation (M2 or M3)

| Test | Pass criteria |
|------|---------------|
| English job, omit language, `english_first` | Still `ggml-tiny.en.bin`, `-l en` |
| Urdu job, `language: "ur"`, `whisper_model: "base"` | `ggml-base.bin`, `-l ur`, Arabic-script output |
| Mixed EN+Urdu, `language: "auto"`, `policy: auto` | `ggml-base.bin`, no `-l`, no foreign-language hallucination loop |
| Karaoke + Urdu | ASS `\kf` tags present; playable output |
| Phase 5 regression | English subtitle + karaoke + stem reuse unchanged under `english_first` |
| Phase 6 regression | `audio_enhance` smoke test unchanged |
| Missing multilingual file | Actionable `RuntimeError` with download hint |

#### Phase D — Client / docs rollout

1. Update Flutter/client to send `language: "auto"` or explicit code for non-English uploads.
2. Update `MASTER_PROJECT_HANDOFF.md` and `CURRENT_PROJECT_STATE.md` after M2 validation.

### 10.6 Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Operators omit multilingual download | Medium | Fail fast with clear message; document in setup |
| Mixed-language quality imperfect | Medium | Document `auto` limits; future segment-level enhancement |
| English WER regression if policy mis-set | Medium | Default `english_first`; explicit opt-in to `auto` |
| Disk doubles (~1.36 GB) | Low | Acceptable for dev machine; offer tier-minimal deploy docs |
| Invalid `language` codes | Low | API validation against Whisper allowlist |
| Karaoke Arabic-script rendering | Low | Validate ASS/FFmpeg burn with Urdu sample in M2 |

---

## 11. Go / No-Go Recommendation

### GO — Phase 7 Milestone 2 implementation

| Criterion | Status |
|-----------|--------|
| Problem understood | ✅ |
| Safe architecture identified | ✅ Option B |
| Phase 5 / 6 isolation preserved | ✅ Subprocess-only; no ML pin changes |
| Backward compatibility path | ✅ `english_first` policy |
| Storage / performance acceptable | ✅ ~683 MB additional; same-tier CPU cost |
| Urdu / multilingual achievable | ✅ With multilingual GGML + routing |

**Proceed with M2:** language-first routing (Option B), dual model registry, `language: "auto"`, validated language parameter, extended metadata, setup documentation.

### NO-GO — defer or reject

| Item | Reason |
|------|--------|
| Option C as immediate global default | Breaks English baseline without migration |
| Option A alone without language routing | Does not fix omitted-language mixed-media case |
| M2 without multilingual files on disk | Jobs will fail at validate — coordinate download in deployment checklist |
| Python openai-whisper / PyTorch Whisper | Violates architecture; unnecessary |

### Conditional items before production tag

- [ ] Record validation job IDs for Urdu, mixed-language, and English regression
- [ ] Confirm `english_first` default on existing Phase 5 CI/smoke hosts
- [ ] Update context docs after M2 implementation (not in M1)

---

## 12. Related Reports

| Report | Relationship |
|--------|--------------|
| `WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md` | M1 input — root cause |
| `PHASE5_MILESTONE1_WHISPER_MODELS.md` | Baseline API contract |
| `PHASE6_M2_VALIDATION_REPORT.md` | Subprocess architecture validation pattern to follow |
| `PHASE6_DEPENDENCY_PROTECTION_RULES.md` | Confirms no Python ML changes needed |

---

*Milestone 1 complete. No application code, API, or model artifacts were modified during this design phase.*
