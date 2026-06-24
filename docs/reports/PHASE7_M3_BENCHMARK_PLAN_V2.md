# Phase 7 — Milestone 3: Commercial Readiness and Whisper Benchmarking Plan (V2)

**Date:** 2026-06-23  
**Branch:** `feature/whisper-multilingual`  
**Supersedes:** `docs/reports/PHASE7_M3_BENCHMARK_PLAN.md` (V1 — retained for history)  
**Authoritative context:** `docs/context/PROJECT_SNAPSHOT_2026_06_22.md`  
**Prior validation:** `docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md`  
**Scope:** Documentation and measurement only — **no application code, API, or routing changes**

---

## Executive Summary

Phase 7 M3 selects **production Whisper defaults** for commercial MVP launch. Benchmarks run on the **local Ubuntu development machine** using direct `whisper-cli` commands. Results **estimate** suitability for **Hetzner VPS (4 vCPU / 8 GB RAM)**. Actual Hetzner validation is deferred to **Phase 8 Deployment**.

**Primary scope (drives launch decisions):** Compare **`ggml-base.en.bin`** vs **`ggml-small.en.bin`** on English speech and English music fixtures — the MVP products are **English subtitles** and **English karaoke**.

**Secondary scope (informational only):** Compare **`ggml-base.bin`** vs **`ggml-small.bin`** on one Urdu speech fixture — Urdu remains **experimental** and must not block launch.

**Benchmark matrix:** **6 timed runs** (not 8). Auto-detect (`language: auto`) is **optional** and not required for M3 sign-off.

**Accuracy method:** Manual qualitative review only. No WER, CER, jiwer, or automated transcript scoring.

**Deliverable:** `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` answering four mandatory questions (§7).

---

## Strategic Constraints (Locked)

These decisions govern how M3 results are interpreted:

| Area | Decision |
|------|----------|
| Hosting | Hetzner VPS — initial **4 vCPU / 8 GB RAM**; future **8 vCPU / 16 GB RAM** |
| Excluded | Cloud Run, serverless, Kubernetes, architecture rewrite |
| Database | **SQLite acceptable for MVP launch**; PostgreSQL deferred until proven growth |
| MVP products | English subtitles, English karaoke, audio enhancement, vocal separation |
| Experimental | Urdu subtitles |
| Deferred | Roman Urdu, voice cloning, dubbing, TTS, real-time processing |
| Hetzner in M3 | **Not required** — estimate from local data; Phase 8 validates on VPS |

### Decision evaluation order

All recommendations must be evaluated against:

1. Commercial launch readiness  
2. Hetzner hosting cost (4 vCPU / 8 GB)  
3. Operational simplicity  
4. Revenue generation potential  
5. User value  

Transcription quality alone does not override launch readiness or hosting economics.

---

## 1. Benchmark Scope

### 1.1 Primary — English production workloads (MVP)

| Model file | Alias | Role |
|------------|-------|------|
| `ggml-base.en.bin` | `base` | Current karaoke default; candidate subtitle default |
| `ggml-small.en.bin` | `small` | Higher accuracy candidate |

| Fixture | WAV path | Duration | `-l` flag | MVP product |
|---------|----------|----------|-----------|-------------|
| **EN-SPEECH** | `backend/processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav` | ~341 s | `en` | English subtitle generation |
| **EN-MUSIC** | `backend/processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav` | ~217 s | `en` | English karaoke generation |

Source media: `sampl_vid.webm` (Phase 2 validation), `believer_vid.webm` (Phase 4 karaoke — known music/lyric gaps on tiny model).

**Runs:** 4 (2 fixtures × 2 models)

### 1.2 Secondary — Urdu experimental (non-blocking)

| Model file | Alias | Role |
|------------|-------|------|
| `ggml-base.bin` | `base` | Minimum multilingual tier |
| `ggml-small.bin` | `small` | M2-validated Urdu tier |

| Fixture | WAV path | Duration | `-l` flag | Product status |
|---------|----------|----------|-----------|----------------|
| **UR-SPEECH** | `backend/processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav` | ~214 s | `ur` | Experimental Urdu subtitles |

Source media: `baluga.mp4` (Phase 7 M2 Urdu validation). File contains mixed EN intro + Urdu body; benchmark uses **explicit `-l ur`** to match experimental client usage.

**Runs:** 2 (1 fixture × 2 models)

**Note:** Urdu results inform the experimental default only. A poor Urdu score does **not** delay English MVP launch.

### 1.3 Optional — not required for M3 sign-off

| Item | When to run |
|------|-------------|
| **Auto-detect** (`-l` omitted) on mixed-language media | Post-MVP or ad hoc investigation |
| **60 s clip dry-runs** | Before full-length runs to verify setup |
| **API end-to-end job** | Sanity check routing metadata only — not for timing |
| **`ggml-tiny.en.bin`** | Already production default for subtitle_generation — no M3 comparison needed unless report discusses cost of upgrading from tiny |

### 1.4 Full matrix (6 runs)

| # | Scope | Fixture | Model file | `-l` |
|---|-------|---------|------------|------|
| 1 | Primary | EN-SPEECH | `ggml-base.en.bin` | `en` |
| 2 | Primary | EN-SPEECH | `ggml-small.en.bin` | `en` |
| 3 | Primary | EN-MUSIC | `ggml-base.en.bin` | `en` |
| 4 | Primary | EN-MUSIC | `ggml-small.en.bin` | `en` |
| 5 | Secondary | UR-SPEECH | `ggml-base.bin` | `ur` |
| 6 | Secondary | UR-SPEECH | `ggml-small.bin` | `ur` |

---

## 2. Methodology

### 2.1 Execution approach

- Run **`whisper-cli` directly** via subprocess-equivalent shell commands (mirrors `WhisperService._run_subprocess()`).
- Wrap each run with **`/usr/bin/time -v`** for wall-clock and peak RSS.
- Use **`--output-json`** (subtitle pipeline default; not `--output-json-full`).
- Stop Celery/Demucs workers during timed runs to avoid CPU/RAM contention.
- Record local environment metadata once per session (§5.1).

### 2.2 Hetzner estimation (no VPS required in M3)

Local benchmarks use the dev machine thread count (`WHISPER_THREADS` from `.env`, typically 8). For Hetzner suitability:

| Local observation | Estimation rule for 4 vCPU / 8 GB |
|-------------------|-------------------------------------|
| Peak RSS | Use as upper bound — VPS has same 8 GB but shares RAM with Redis, Celery, OS |
| Wall clock at `-t 8` | Estimate 4 vCPU runtime as **~1.5–2.0× local wall clock** (document assumption in report) |
| Peak RSS > 3 GB (small.en) | Flag risk for concurrent Demucs on 8 GB VPS |
| RTF > 1.0 on small.en for typical job | Flag user-wait risk; prefer base.en default unless quality gain justifies |

**Phase 8 Deployment** will re-run a subset on the actual Hetzner VPS with `-t 4` and confirm estimates.

### 2.3 Metrics

| Metric | Required | Collection |
|--------|----------|------------|
| Wall-clock runtime | Yes | `/usr/bin/time -v` → `Elapsed (wall clock) time` |
| Peak RAM (RSS) | Yes | `/usr/bin/time -v` → `Maximum resident set size (kbytes)` |
| Audio duration | Yes | `ffprobe` |
| Realtime factor (RTF) | Yes | Derived: wall clock ÷ audio duration |
| Segment count | Yes | `jq '.transcription \| length'` |
| Detected language | Yes | JSON output |
| Qualitative accuracy (1–5) | Yes | Manual transcript review (§2.4) |
| WER / CER / jiwer | **No** | Explicitly excluded |

### 2.4 Accuracy review (manual only)

Review `transcript.txt` extracted from JSON for each run.

| Score | Label | Criteria |
|-------|-------|------------|
| 5 | Production-ready | Few or no errors; no hallucination loops |
| 4 | MVP acceptable | Minor errors; good enough to ship |
| 3 | Marginal | Frequent errors; gist only |
| 2 | Poor | Major errors or repetition |
| 1 | Unusable | Wrong language, hallucinations, or empty |

**English (primary — drives defaults):**

| Fixture | Review focus |
|---------|--------------|
| EN-SPEECH | Word accuracy, proper nouns, sentence coherence |
| EN-MUSIC | Lyric capture in vocal sections; gaps during instrumentals |

**Urdu (secondary — experimental label only):**

| Fixture | Review focus |
|---------|--------------|
| UR-SPEECH | Arabic-script correctness; compare informally to M2 transcripts (`01e02636` small, `2b59867a` base) |

Record 2–3 example errors when score ≤ 3. One human reviewer minimum.

---

## 3. Repository Reference

### 3.1 No dedicated benchmark scripts

Benchmarks use shell commands only. Reference implementation:

- `backend/app/services/whisper_service.py` — CLI args, `LD_LIBRARY_PATH`
- `backend/tests/test_whisper_models.py` — run before benchmark (13 routing tests)

### 3.2 Models required on disk

```bash
ls -lh backend/models/ggml-base.en.bin backend/models/ggml-small.en.bin \
         backend/models/ggml-base.bin backend/models/ggml-small.bin
```

English-only MVP minimum disk: `.en.bin` trio (~681 MB). Add multilingual pair (+608 MB) only if offering experimental Urdu.

### 3.3 Related reports

| Report | Use |
|--------|-----|
| `PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md` | Urdu M2 baseline transcripts |
| `PHASE5_MILESTONE1_WHISPER_MODELS.md` | Current defaults: subtitle → `tiny`, karaoke → `base` |
| `docs/testing/WHISPER_CPP_SETUP.md` | Model sizes, CLI examples |

---

## 4. Pre-Benchmark Checklist

- [ ] All four model files present (§3.2)
- [ ] Fixture WAVs exist (§1.1, §1.2) or re-extract from `backend/uploads/`
- [ ] `LD_LIBRARY_PATH` set (§5.1)
- [ ] `whisper-cli --help` succeeds
- [ ] Output dirs: `mkdir -p /tmp/m3-v2/{en-speech,en-music,ur-speech}/{base.en,small.en,base,small}` — use consistent naming per run
- [ ] Celery/Demucs workers stopped
- [ ] `python -m unittest tests.test_whisper_models -v` passes
- [ ] Environment metadata recorded (§5.1)

---

## 5. Commands

### 5.1 Environment setup

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"

export REPO="/home/shz/Documents/Mustafa projects/VoxClone"
export WHISPER_BIN="$REPO/tools/whisper.cpp/build/bin/whisper-cli"
export BUILD="$REPO/tools/whisper.cpp/build"
export LD_LIBRARY_PATH="$BUILD/src:$BUILD/ggml/src${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export MODELS="$REPO/backend/models"
export M3="/tmp/m3-v2"
export THREADS=8   # Match backend/.env WHISPER_THREADS; note in report for Hetzner scaling

export WAV_EN_SPEECH="$REPO/backend/processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav"
export WAV_EN_MUSIC="$REPO/backend/processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav"
export WAV_UR="$REPO/backend/processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav"

mkdir -p "$M3"
```

### 5.2 Benchmark runner function

```bash
run_bench() {
  local scope="$1"       # primary | secondary
  local fixture="$2"     # en-speech | en-music | ur-speech
  local model_file="$3"  # full path to .bin
  local wav="$4"
  local lang="$5"        # en | ur
  local label="$6"       # e.g. base.en | small.en | base | small

  local outdir="$M3/$fixture/$label"
  mkdir -p "$outdir"
  local log="$outdir/time.log"
  local dur
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$wav")

  {
    echo "scope=$scope fixture=$fixture label=$label lang=$lang"
    echo "model=$model_file audio_duration_sec=$dur threads=$THREADS"
    date -Iseconds
  } | tee "$log"

  /usr/bin/time -v "$WHISPER_BIN" \
    -m "$model_file" \
    -f "$wav" \
    -t "$THREADS" \
    --output-json \
    -l "$lang" \
    -of "$outdir/output" \
    2>>"$log"

  grep -E "Elapsed \(wall clock\)|Maximum resident set size" "$log" > "$outdir/metrics.txt"

  jq -r '.transcription[]?.text // empty' "$outdir/output.json" \
    | tr -d '\n' | fold -s > "$outdir/transcript.txt"

  jq '{language: (.result.language // .language), segments: (.transcription | length)}' \
    "$outdir/output.json" > "$outdir/summary.json"
}
```

### 5.3 Six-run matrix

```bash
# Primary — English MVP (4 runs)
run_bench primary en-speech "$MODELS/ggml-base.en.bin"  "$WAV_EN_SPEECH" en base.en
run_bench primary en-speech "$MODELS/ggml-small.en.bin" "$WAV_EN_SPEECH" en small.en
run_bench primary en-music  "$MODELS/ggml-base.en.bin"  "$WAV_EN_MUSIC"  en base.en
run_bench primary en-music  "$MODELS/ggml-small.en.bin" "$WAV_EN_MUSIC"  en small.en

# Secondary — Urdu experimental (2 runs)
run_bench secondary ur-speech "$MODELS/ggml-base.bin"  "$WAV_UR" ur base
run_bench secondary ur-speech "$MODELS/ggml-small.bin" "$WAV_UR" ur small
```

### 5.4 Optional dry-run (60 s clip)

```bash
ffmpeg -y -i "$WAV_EN_SPEECH" -t 60 -acodec pcm_s16le -ar 16000 -ac 1 "$M3/en-speech_clip60.wav"
run_bench primary en-speech "$MODELS/ggml-base.en.bin" "$M3/en-speech_clip60.wav" en base.en
```

### 5.5 Optional auto-detect (not for M3 sign-off)

```bash
# Omit -l flag manually if investigating mixed-language behaviour post-MVP
/usr/bin/time -v "$WHISPER_BIN" \
  -m "$MODELS/ggml-base.bin" -f "$WAV_UR" -t "$THREADS" \
  --output-json -of "$M3/ur-speech/auto-base/output" \
  2>"$M3/ur-speech/auto-base/time.log"
```

---

## 6. Data Collection Tables

Copy into `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` after execution.

### 6.1 Environment record

| Field | Value |
|-------|-------|
| Date | |
| Hostname / OS | |
| CPU cores (`nproc`) | |
| RAM total (`free -h`) | |
| `WHISPER_THREADS` / `-t` | |
| whisper.cpp binary path | |
| Models verified | base.en, small.en, base, small |

### 6.2 Runtime and memory — primary (English MVP)

| Fixture | Model | Audio (s) | Wall (s) | RTF | Peak RSS (MB) | Segments | Rubric (1–5) |
|---------|-------|-----------|----------|-----|---------------|----------|--------------|
| EN-SPEECH | base.en | | | | | | |
| EN-SPEECH | small.en | | | | | | |
| EN-MUSIC | base.en | | | | | | |
| EN-MUSIC | small.en | | | | | | |

### 6.3 Runtime and memory — secondary (Urdu experimental)

| Fixture | Model | Audio (s) | Wall (s) | RTF | Peak RSS (MB) | Segments | Rubric (1–5) |
|---------|-------|-----------|----------|-----|---------------|----------|--------------|
| UR-SPEECH | base | | | | | | |
| UR-SPEECH | small | | | | | | |

### 6.4 Hetzner suitability estimate (derived — no VPS run in M3)

| Model | Peak RSS (MB) | Est. wall @ 4 vCPU | Fits 8 GB with Celery+Demucs? | MVP default candidate? |
|-------|---------------|--------------------|------------------------------|------------------------|
| base.en | | | | |
| small.en | | | | |
| base (ur) | | | | |
| small (ur) | | | | |

---

## 7. Success Criteria

M3 is **complete** when the benchmark report explicitly answers:

### A. Default English subtitle model?

Recommend `whisper_model` tier for `subtitle_generation` on English content (`language` omitted or `en`).

**Current default:** `tiny` → `ggml-tiny.en.bin` (Phase 5). M3 decides whether MVP should stay on `tiny`, upgrade to `base`, or offer `small` as opt-in.

**Decision inputs:** EN-SPEECH rubric + RTF + peak RSS + Hetzner estimate.

### B. Default English karaoke model?

Recommend `whisper_model` tier for `karaoke` on English content.

**Current default:** `base` → `ggml-base.en.bin` (Phase 5). M3 validates or upgrades to `small.en` for music-heavy content.

**Decision inputs:** EN-MUSIC rubric + RTF + peak RSS + user value (lyric accuracy).

### C. Default Urdu experimental model?

Recommend tier when client passes `language: ur` — **experimental only**.

**Decision inputs:** UR-SPEECH rubric + M2 comparison. Either tier may remain experimental (rubric ≤ 4). Poor Urdu scores do not block launch.

### D. Is Hetzner 4 vCPU / 8 GB still the recommended launch configuration?

Provide **GO / Conditional GO / NO-GO** with:

- Estimated peak RAM headroom for Whisper + Redis + Celery + one Demucs job  
- Estimated job duration for typical English subtitle and karaoke jobs  
- Whether upgrade to **8 vCPU / 16 GB** should be a revenue-triggered option only  
- Confirmation that **SQLite remains acceptable** for MVP (PostgreSQL not required for launch)

### Completion checklist

- [ ] All **6** matrix runs completed without error on local machine
- [ ] §6.2 and §6.3 tables filled (runtime + rubric)
- [ ] §6.4 Hetzner estimate filled from local data
- [ ] Questions **A, B, C, D** answered in report narrative
- [ ] Recommendations evaluated against five strategic criteria (§ opening)
- [ ] `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` written
- [ ] Hetzner physical validation explicitly deferred to Phase 8

### Explicit non-goals

- No application code, API, or routing changes  
- No WER/CER/jiwer  
- No required auto-detect runs  
- No required Hetzner VPS runs  
- No Roman Urdu, voice cloning, or PostgreSQL migration decisions  

---

## 8. Production Recommendation Framework

Apply **after** tables are filled. **English primary results override Urdu secondary results** for launch decisions.

### Step 1 — English subtitle default (Question A)

| Condition | Recommendation |
|-----------|----------------|
| small.en rubric ≥ 4 on EN-SPEECH **and** est. peak RSS < 2.5 GB **and** est. RTF acceptable | Consider `base` or `small` default; weigh vs current `tiny` speed advantage |
| base.en rubric ≥ 4 and small.en gain marginal | **Keep or set `base`** — simpler ops, lower RAM |
| Only small.en meets rubric ≥ 4 | Default `small` for subtitles **only if** Hetzner estimate passes (Question D) |
| tiny.en acceptable from prior Phase 2 evidence | **Retain `tiny` for speed**; document `base`/`small` as paid tier or parameter override |

### Step 2 — English karaoke default (Question B)

| Condition | Recommendation |
|-----------|----------------|
| base.en rubric ≥ 4 on EN-MUSIC | **Retain `base`** (current default) |
| small.en clearly better on lyrics (rubric + reviewer notes) | Upgrade karaoke default to `small` if Question D allows |
| Both ≥ 4 with small slower | **Retain `base`** — user value vs wait time |

### Step 3 — Urdu experimental default (Question C)

| Condition | Recommendation |
|-----------|----------------|
| Either tier rubric ≥ 3 | Document recommended experimental tier; label **not production-grade** |
| small > base on rubric | Suggest `whisper_model: small` for Urdu opt-in |
| Both ≤ 2 | Document `base` as minimum; discourage Urdu marketing |

**Never block English MVP on Urdu scores.**

### Step 4 — Hetzner launch config (Question D)

| Signal | Verdict |
|--------|---------|
| small.en peak RSS + Demucs headroom < 8 GB with ≥ 1 GB OS buffer | **GO** on 4 vCPU / 8 GB |
| Tight RAM or RTF > 2× realtime on est. 4 vCPU | **Conditional GO** — default base.en; upgrade path at revenue |
| Cannot run English MVP workloads | **NO-GO** — revise defaults before launch (not architecture) |

**SQLite:** Confirm MVP launch on SQLite is acceptable; note PostgreSQL migration trigger (concurrent writes, multi-worker).

---

## 9. Execution Sequence

| Step | Action | Est. time |
|------|--------|-----------|
| 1 | Pre-benchmark checklist (§4) | 10 min |
| 2 | Environment setup (§5.1) | 5 min |
| 3 | Optional 60 s dry-run | 5 min |
| 4 | **Primary:** 4 English runs | 25–45 min |
| 5 | **Secondary:** 2 Urdu runs | 10–20 min |
| 6 | Manual accuracy review | 20–30 min |
| 7 | Fill tables + Hetzner estimate | 15 min |
| 8 | Answer A–D; write benchmark report | 30 min |

**Total estimated time:** **~2–2.5 hours** (full-length fixtures on 8-core dev machine).

**Time-constrained minimum:** Run EN-SPEECH × 2 + EN-MUSIC × 2 only (4 runs) to answer A, B, D; add Urdu pair when time allows for C.

---

## 10. Blockers and Mitigations

| Blocker | Mitigation |
|---------|------------|
| `libwhisper.so.1` not found | Set `LD_LIBRARY_PATH` (§5.1) |
| Fixture WAV missing | Re-extract from `backend/uploads/` with FFmpeg 16 kHz mono |
| EN-SPEECH ~341 s lengthens session | Optional 60 s clip for dry-run; full file for final EN-SPEECH rows |
| Test media not in git | Verify local paths before each session |
| Dev 8-core vs Hetzner 4-core | Document scaling assumption in §6.4; Phase 8 confirms |

---

## 11. Post-M3 Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Benchmark plan V1 | `docs/reports/PHASE7_M3_BENCHMARK_PLAN.md` | Superseded by V2 |
| Benchmark plan V2 | `docs/reports/PHASE7_M3_BENCHMARK_PLAN_V2.md` | ✅ This document |
| Benchmark results | `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` | Pending execution |
| Hetzner validation | Phase 8 Deployment | Deferred |
| Session update | `docs/context/NEXT_SESSION_START_HERE.md` | After report |

---

*Plan V2 created: 2026-06-23 — aligned with commercial MVP strategy; documentation only.*
