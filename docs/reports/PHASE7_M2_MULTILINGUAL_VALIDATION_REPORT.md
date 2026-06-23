# Phase 7 — Milestone 2: Multilingual Whisper Validation Report

**Date:** 2026-06-22  
**Branch:** `feature/whisper-multilingual`  
**Implementation baseline:** `docs/reports/PHASE7_M2_MULTILINGUAL_ROUTING_IMPLEMENTATION.md`  
**Design baseline:** `docs/reports/PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md`  
**Validation type:** Manual end-to-end (subtitle generation)

---

## Executive Summary

Manual validation confirms that **language-first Whisper routing works as designed**. Urdu subtitle jobs with `parameters.language: "ur"` correctly select `ggml-small.bin`, detect Urdu, and produce substantially improved subtitles compared to the pre-fix English-only path.

**Root cause fixed:** English-only Whisper models were previously forced for all jobs regardless of content language.

**Remaining issues are model-accuracy limitations** (phonetic substitutions, occasional wrong Urdu words), not model-selection or routing defects.

**Production readiness:** **Conditional GO** — multilingual routing is validated for Urdu when clients pass `language: "ur"` (or `"auto"` for mixed content) and multilingual GGML files are installed. English-only deployments remain unchanged under default `WHISPER_ROUTING_POLICY=english_first`.

---

## 1. Validation Methodology

| Step | Action |
|------|--------|
| 1 | Install full English + multilingual GGML model set under `backend/models/` |
| 2 | Configure `WHISPER_ROUTING_POLICY=english_first` (production default) |
| 3 | Reproduce prior failure case: mixed-language tutorial media (English intro + Urdu body) — documented baseline from pre-M2 behaviour |
| 4 | Submit new `subtitle_generation` job with explicit Urdu routing parameters |
| 5 | Poll job to completion; inspect `jobs.parameters` metadata |
| 6 | Compare SRT output quality against pre-fix run (same media) |
| 7 | Confirm automated unit tests still pass (`tests/test_whisper_models.py`) |

**Scope:** Subtitle generation pipeline only in this validation session. Karaoke re-test on same media recommended but not recorded in this report.

**Out of scope:** Code changes, API changes, model downloads during this documentation task.

---

## 2. Runtime Configuration

| Setting | Value |
|---------|-------|
| Branch | `feature/whisper-multilingual` |
| `WHISPER_ROUTING_POLICY` | `english_first` |
| `WHISPER_MODEL_PATH` | `models/ggml-tiny.en.bin` |
| `WHISPER_CPP_BINARY` | `../tools/whisper.cpp/build/bin/whisper-cli` (typical) |
| `WHISPER_THREADS` | 8 (typical) |

**Default job behaviour (language omitted):** unchanged — `subtitle_generation` → `ggml-tiny.en.bin` + `-l en`.

---

## 3. Installed Multilingual Models

Verified on validation host:

| File | Variant | Approx. size |
|------|---------|--------------|
| `ggml-tiny.en.bin` | English-only | 75 MB |
| `ggml-base.en.bin` | English-only | 142 MB |
| `ggml-small.en.bin` | English-only | 466 MB |
| `ggml-tiny.bin` | Multilingual | 75 MB |
| `ggml-base.bin` | Multilingual | 142 MB |
| `ggml-small.bin` | Multilingual | 466 MB |

**Total disk:** ~1.36 GB (dual English + multilingual set).

---

## 4. Test Media Description

**Content type:** Tutorial / educational video with mixed-language speech.

**Structure:**

- Opening segment: English introduction
- Primary content: Urdu tutorial narration
- Domain: Technical / software tutorial context (background removal, editing terminology)

**Prior failure relevance:** This media previously triggered English-only model selection (default routing), producing unusable output for the Urdu sections.

---

## 5. Before vs After Comparison

### Previous behaviour (pre–Phase 7 M2)

| Observation | Detail |
|-------------|--------|
| Model selected | `ggml-tiny.en.bin` |
| Language flag | `-l en` (default) |
| Urdu sections | English hallucinations, repeated subtitle lines |
| Artefact text | `(speaking in foreign language)` |
| Tutorial comprehension | Poor — context not understood |
| Karaoke (same media) | Unusable — inherits bad transcript |
| Root cause class | **Model-selection bug** — wrong model variant for non-English content |

### New behaviour (post–Phase 7 M2, validated)

**Request:**

```json
{
  "job_type": "subtitle_generation",
  "parameters": {
    "language": "ur",
    "whisper_model": "small"
  }
}
```

| Observation | Detail |
|-------------|--------|
| Model selected | `ggml-small.bin` |
| Language flag | `-l ur` |
| Script output | Arabic-script Urdu (native orthography) |
| Repetition | Dramatically reduced vs pre-fix |
| Tutorial context | Correctly understood |
| Overall quality | Significantly improved |
| Root cause class | Routing **fixed**; residual errors are **Whisper WER limits** |

---

## 6. Routing Verification Evidence

Completed job metadata (confirmed):

```json
{
  "detected_language": "ur",
  "whisper_model": "small",
  "whisper_model_file": "ggml-small.bin",
  "whisper_model_variant": "multilingual",
  "language_requested": "ur"
}
```

**Interpretation:**

| Field | Expected | Verified |
|-------|----------|----------|
| `whisper_model_file` | `ggml-small.bin` (not `.en.bin`) | ✅ |
| `whisper_model_variant` | `multilingual` | ✅ |
| `language_requested` | `ur` | ✅ |
| `detected_language` | `ur` | ✅ |

Routing logic in `resolve_whisper_model()` behaved exactly as specified in Phase 7 M1 Option B.

**Automated tests (2026-06-22):** 13/13 passed in `tests/test_whisper_models.py`.

---

## 7. Accuracy Observations

### Successes

- Urdu language correctly detected end-to-end
- Multilingual model correctly selected for explicit `language: "ur"`
- Native Urdu script in SRT/VTT/TXT output
- Repetition and hallucination loops largely eliminated vs English-only path
- Technical tutorial semantics preserved well enough for practical use

### Residual transcription errors (not routing failures)

Whisper `ggml-small.bin` Urdu output is improved but not perfect. Observed error classes:

| Error class | Example |
|-------------|---------|
| Phonetic substitution | Expected **بیک گراؤنڈ** → observed **بیگروانٹ** |
| Wrong word choice | Expected **تھوڑا** → observed **کھوڑا** |
| English technical terms | Mixed EN/UR domain terms not always recognised correctly |
| Occasional mistranscriptions | Isolated word-level errors in otherwise coherent segments |

These patterns match **acoustic-model / vocabulary limitations** of `small` tier multilingual Whisper on Urdu + code-mixed technical speech, not incorrect model file selection.

---

## 8. Known Limitations

| Limitation | Type | Mitigation |
|------------|------|------------|
| Urdu WER on `ggml-small.bin` | Model accuracy | Try `ggml-medium.bin`; pass `whisper_model` appropriately after M3 evaluation |
| Mixed EN intro + Urdu body with omitted `language` | Routing policy | Use `language: "auto"` or explicit `"ur"` — default `english_first` still uses `.en` |
| English technical terms in Urdu speech | Whisper vocabulary | Expected; may improve with larger model or custom post-processing |
| Karaoke on Urdu | Untested in this session | Re-validate ASS word timing with `language: "ur"` on same media |
| Roman Urdu output | Not implemented | See Section 11 — future milestone candidate |
| Disk footprint (~1.36 GB dual set) | Ops | English-only hosts need only `.en.bin` trio |

---

## 9. Production Readiness Assessment

| Criterion | Status |
|-----------|--------|
| Routing implementation complete | ✅ |
| Unit tests pass | ✅ 13/13 |
| Manual Urdu E2E validated | ✅ |
| English backward compat (`english_first`) | ✅ by design (not re-tested in this session; covered by unit tests) |
| Multilingual models documented | ✅ `WHISPER_CPP_SETUP.md` |
| Client guidance for `language` param | ⚠️ Clients must send `ur` / `auto` for non-English |
| Phase 5 / 6 regression re-run | ⚠️ Recommended before tag; not in this validation session |

**Verdict: Conditional GO**

Safe to commit and tag Phase 7 M2 on `feature/whisper-multilingual` after documentation sync. Recommend one English smoke test and optional Urdu karaoke validation before production tag.

---

## 10. Recommended Next Milestone (Phase 7 M3 Candidates)

| Priority | Topic | Rationale |
|----------|-------|-----------|
| 1 | Evaluate `ggml-medium.bin` for Urdu quality | Address residual word errors; ~1.5 GiB disk/RAM cost |
| 2 | Automatic routing for mixed-language media | Document/client defaults for `language: "auto"` on uploads with unknown language |
| 3 | Multilingual tier benchmark | Compare tiny/base/small/medium on same Urdu fixture; WER or human rubric |
| 4 | Roman Urdu transliteration pipeline | Optional export for audiences preferring Latin script (Section 11) |
| 5 | Urdu karaoke validation | Confirm `\kf` ASS quality with Arabic-script tokens |

---

## 11. Roman Urdu — Future Enhancement Design Note

### Problem

Phase 7 M2 correctly outputs **native Urdu script** (Arabic orthography):

| Stage | Example |
|-------|---------|
| Spoken Urdu | *(Urdu speech)* |
| Current Whisper output | `السلام علیکم دوستو` |
| Desired optional output | `Assalam-o-Alaikum dosto` |

Whisper.cpp does **not** natively emit Roman Urdu (Latin transliteration). Roman output requires a **downstream transliteration step**.

### Recommendation

**Yes — Roman Urdu support should become a future Phase 7 milestone (proposed M4 or M3b)**, scoped as an **optional subtitle export format**, not a change to core transcription routing.

Routing (M2) and transliteration (future) should remain separate concerns.

---

### 11.1 Architecture options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A — Post-subtitle transliteration** ✅ Recommended | After SRT/VTT/TXT generated, run transliterator on text fields only | Preserves native script as source of truth; no Whisper change; can add sidecar files | Word count may change; timing unchanged |
| **B — Separate export format** | Primary outputs stay Urdu script; add `result_files.srt_roman` etc. | Clean API; burn-in can choose script | More download endpoints or format param |
| **C — During transcription** | Custom Whisper prompt / fine-tuned model for Roman output | Single pass | Not supported by whisper.cpp GGML; high effort |
| **D — Parallel ASR** | Second model trained for Roman Urdu | Theoretically best Roman accuracy | Violates subprocess-only architecture; heavy |

**Recommended:** **Option A + B** — post-process native script subtitles; expose as optional export via `subtitle_script` parameter.

---

### 11.2 When transliteration should occur

| Stage | Suitable? | Notes |
|-------|-----------|-------|
| During transcription | ❌ | whisper.cpp outputs one script per model; no Roman Urdu mode |
| After subtitle generation | ✅ | Transform completed segment text; timings preserved |
| Separate export format | ✅ | Best UX — keep `_subtitles.srt` native; add `_subtitles_roman.srt` |

Pipeline sketch:

```
Whisper (native Urdu script) → SRT/VTT/TXT
                           ↘ optional TransliterationService → *_roman.srt
```

---

### 11.3 Impact on karaoke subtitles

| Aspect | Impact |
|--------|--------|
| ASS `\kf` word timing | Roman text may differ in length vs Arabic script — highlight sweep may look misaligned |
| Word boundaries | Transliteration merges/splits words differently — `\kf` centisecond counts need per-word mapping |
| Recommendation | **Phase 1:** Roman Urdu for SRT/VTT/TXT only. **Phase 2:** Karaoke Roman Urdu only after word-alignment research |

Karaoke Roman Urdu is **higher complexity** than plain subtitles.

---

### 11.4 Accuracy considerations

- Rule-based transliteration (e.g. ALA-LC, ISO 233) handles standard Urdu well but struggles with English loanwords and names.
- ML transliteration (sequence models) better for mixed Urdu–English tutorial speech but adds dependency weight.
- Whisper transcription errors (e.g. **بیگروانٹ**) would propagate into Roman output — transliteration does not fix ASR errors.
- Human review may still be needed for broadcast-quality Roman captions.

---

### 11.5 Open-source Urdu transliteration libraries (investigation)

| Library / tool | Language | Notes |
|----------------|----------|-------|
| [indic-transliteration](https://github.com/indic-transliteration/indic_transliteration_py) | Python | Supports Devanagari/Arabic scripts → Latin; may need Urdu-specific tuning |
| [UrduHack](https://github.com/urduhack/urduhack) | Python | Urdu NLP toolkit; transliteration utilities in ecosystem |
| [Aksharamukha](https://github.com/virtualvinodh/aksharamukha) | Python / web | Script conversion; evaluate Urdu Arabic → Latin |
| [uTransliterater](https://github.com/ahsan-ul-ghor) | Python | Urdu-focused transliteration (community projects — verify maintenance) |
| ICU / Unicode CLDR | C++/Java bindings | Low-level; robust but integration heavier |

**Integration constraint:** Prefer a **lightweight Python post-processor** in the API process or Celery task (no change to whisper.cpp subprocess pattern). Evaluate dependency pins against Phase 5/6 protection rules before adding packages.

---

### 11.6 API design options (future — not implemented)

**Option 1 — `subtitle_script` parameter:**

```json
{
  "language": "ur",
  "whisper_model": "small",
  "subtitle_script": "urdu"
}
```

```json
{
  "language": "ur",
  "whisper_model": "small",
  "subtitle_script": "roman_urdu"
}
```

| Value | Output |
|-------|--------|
| `urdu` (default) | Native Arabic-script Urdu — current M2 behaviour |
| `roman_urdu` | Additional or primary Roman transliteration sidecar |

**Option 2 — Separate job type or export flag:**

```json
{ "export_formats": ["srt", "srt_roman"] }
```

**Recommendation:** Option 1 (`subtitle_script`) — minimal, explicit, backward compatible when omitted.

---

### 11.7 Milestone recommendation

| Milestone | Scope | Dependency |
|-----------|-------|------------|
| **Phase 7 M3** | `ggml-medium.bin` Urdu benchmark + mixed-language `auto` guidance | M2 validated ✅ |
| **Phase 7 M4 (proposed)** | Roman Urdu transliteration export (`subtitle_script: roman_urdu`) | M3 accuracy baseline |

Do **not** implement Roman Urdu in M2/M3 validation work — document only.

---

## 12. Conclusions

1. **Root cause fixed:** English-only models are no longer used when clients request Urdu via `parameters.language: "ur"`.
2. **Routing verified:** Job metadata confirms `ggml-small.bin`, `multilingual` variant, and `detected_language: ur`.
3. **Quality improved:** Subtitle usability moved from broken (hallucinations / foreign-language placeholders) to practical tutorial captions.
4. **Remaining gaps are model accuracy**, not application routing — larger models and optional Roman transliteration are the correct next investments.

---

## Related Reports

| Report | Purpose |
|--------|---------|
| `PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md` | Approved architecture |
| `PHASE7_M2_MULTILINGUAL_ROUTING_IMPLEMENTATION.md` | Code changes |
| `WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md` | Original root cause |
| `PHASE6_M2_VALIDATION_REPORT.md` | Validation report template |

---

*Validation report complete. Documentation-only update — no application code modified.*
