# Phase 7 — Milestone 3: Whisper Benchmark Report

**Date:** 2026-06-23  
**Branch:** `feature/whisper-multilingual`  
**Plan:** `docs/reports/PHASE7_M3_BENCHMARK_PLAN_V2.md`  
**Execution evidence:** `/tmp/m3-v2/` (6 runs) · `/tmp/m3_v2_benchmark.log` (`ALL_BENCHMARKS_COMPLETE`)  
**Scope:** Analysis of completed benchmarks only — no code changes

---

## Executive Summary

Six benchmark runs completed successfully on the local Ubuntu development machine (8 CPU threads, 32 GB RAM). Results drive **MVP production defaults** for English workloads and **experimental** Urdu guidance.

| Question | Recommendation |
|----------|----------------|
| **A. English subtitle model** | **`base`** → `ggml-base.en.bin` |
| **B. English karaoke model** | **`base`** → `ggml-base.en.bin` (retain current default) |
| **C. Urdu experimental model** | **`small`** → `ggml-small.bin` with `language: ur` |
| **D. Hetzner 4 vCPU / 8 GB** | **Conditional GO** — suitable for MVP with `base.en` defaults, `WHISPER_THREADS=4`, Celery `--concurrency 1`; **not** suitable for defaulting to `small.en` |

**Do not default to `ggml-small.en.bin` for MVP English products** — 7–11× realtime factor and ~870 MB peak RSS on this host make it incompatible with cost and launch-readiness goals on 8 GB VPS.

**Note:** Application defaults remain unchanged in this milestone (subtitle → `tiny`, karaoke → `base` per Phase 5). This report records **recommended** production configuration for commercial launch planning.

---

## 1. Environment

| Field | Value |
|-------|-------|
| Date | 2026-06-23 |
| Host | Ubuntu 24.04 · Linux 6.8.0-124-generic · x86_64 |
| CPU cores | 8 (`nproc`) |
| RAM total | 31 GiB |
| `WHISPER_THREADS` / `-t` | 8 |
| whisper.cpp binary | `tools/whisper.cpp/build/bin/whisper-cli` |
| Models verified | `ggml-base.en.bin`, `ggml-small.en.bin`, `ggml-base.bin`, `ggml-small.bin` |
| Hetzner physical run | **Not performed** — suitability estimated from local data (Phase 8 Deployment) |

### Fixtures

| ID | WAV | Duration | Purpose |
|----|-----|----------|---------|
| EN-SPEECH | `processed/ac849d78-…_audio.wav` | 340.5 s | English subtitle (Phase 2 `sampl_vid.webm`) |
| EN-MUSIC | `processed/0e44f8ef-…_audio.wav` | 216.5 s | English karaoke (`believer_vid.webm`) |
| UR-SPEECH | `processed/01e02636-…_audio.wav` | 213.8 s | Urdu experimental (`baluga.mp4`, `-l ur`) |

---

## 2. Runtime and Memory — Primary (English MVP)

Wall times parsed from `/usr/bin/time -v` metrics files. **RTF** = wall clock ÷ audio duration (values > 1.0 mean slower than realtime).

| Fixture | Model | Audio (s) | Wall clock | Wall (s) | RTF | Peak RSS (MB) | Segments | Detected lang | Status |
|---------|-------|-----------|------------|----------|-----|---------------|----------|---------------|--------|
| EN-SPEECH | base.en | 340.5 | 8:42.00 | 522 | **1.53** | 404.3 | 111 | en | ok |
| EN-SPEECH | small.en | 340.5 | 42:57.04 | 2577 | **7.57** | 871.9 | 114 | en | ok |
| EN-MUSIC | base.en | 216.5 | 13:55.19 | 835 | **3.86** | 392.6 | 47 | en | ok |
| EN-MUSIC | small.en | 216.5 | 38:48.04 | 2328 | **10.75** | 860.4 | 60 | en | ok |

**Raw outputs:** `/tmp/m3-v2/en-speech/{base.en,small.en}/`, `/tmp/m3-v2/en-music/{base.en,small.en}/`

---

## 3. Runtime and Memory — Secondary (Urdu Experimental)

| Fixture | Model | Audio (s) | Wall clock | Wall (s) | RTF | Peak RSS (MB) | Segments | Detected lang | Status |
|---------|-------|-----------|------------|----------|-----|---------------|----------|---------------|--------|
| UR-SPEECH | base | 213.8 | 44:53.00 | 2693 | **12.59** | 393.8 | 11 | ur | ok |
| UR-SPEECH | small | 213.8 | 29:21.91 | 1762 | **8.24** | 862.4 | 22 | ur | ok |

**Raw outputs:** `/tmp/m3-v2/ur-speech/{base,small}/`

**M2 comparison:** M3 `small` transcript aligns with Phase 7 M2 job `01e02636` (coherent Urdu tutorial). M3 `base` produced severe repetition collapse (11 segments vs 22 for small) — **regression vs M2 job `2b59867a`**.

---

## 4. Qualitative Accuracy (Manual Review)

Reviewer: benchmark execution session · Rubric 1–5 per `PHASE7_M3_BENCHMARK_PLAN_V2.md`

### Primary — English MVP

| Fixture | Model | Rubric | MVP acceptable? | Notes |
|---------|-------|--------|-----------------|-------|
| EN-SPEECH | base.en | **5** | Yes | Clear educational speech; coherent paragraphs; minor wording variants (e.g. “faced” vs “face”) |
| EN-SPEECH | small.en | **5** | Yes (opt-in only) | Marginally cleaner punctuation; not worth 5× runtime vs base.en |
| EN-MUSIC | base.en | **3** | Marginal | Captures song structure; lyric errors (“believe up”, “CEO” for “sea”); known music difficulty |
| EN-MUSIC | small.en | **4** | Yes (opt-in only) | Better lyric phrases (“believer”); 60 vs 47 segments; still some errors; 2.8× slower wall time vs base.en on same fixture |

### Secondary — Urdu Experimental

| Fixture | Model | Rubric | MVP acceptable? | Notes |
|---------|-------|--------|-----------------|-------|
| UR-SPEECH | base | **1** | No | Long repetition loops; 11 segments; unusable for subtitles |
| UR-SPEECH | small | **4** | Experimental only | Tutorial semantics preserved; phonetic substitutions (M2-class); not production-grade |

---

## 5. Hetzner 4 vCPU / 8 GB Suitability Estimate

**Method:** Local 8-thread results × **1.8×** wall-clock scaling factor (conservative estimate for 4 vCPU with `WHISPER_THREADS=4`). Peak RSS treated as **lower bound** — VPS shares RAM with OS, Redis, FastAPI, Celery, and Demucs.

| Model | Peak RSS (MB) | Example job | Local wall (s) | Est. Hetzner wall (s) | Est. RTF @ 4 vCPU |
|-------|---------------|-------------|----------------|----------------------|-------------------|
| base.en | ~400 | 5.7 min speech | 522 | ~940 (~16 min) | ~2.8 |
| base.en | ~393 | 3.6 min music | 835 | ~1500 (~25 min) | ~6.9 |
| small.en | ~872 | 5.7 min speech | 2577 | ~4640 (~77 min) | ~13.6 |
| small.bin (ur) | ~862 | 3.6 min Urdu | 1762 | ~3170 (~53 min) | ~14.8 |

### RAM headroom model (8 GB VPS)

| Component | Est. RAM |
|-----------|----------|
| OS + buffers | ~1.0 GB |
| Redis + FastAPI | ~0.3 GB |
| Celery + Demucs (concurrency 1) | ~2.0–3.0 GB |
| whisper-cli **base.en** | ~0.4 GB |
| **Total (base.en path)** | **~4–5 GB** — acceptable margin |
| whisper-cli **small.en** | ~0.9 GB |
| **Total (small.en path)** | **~5–6 GB** — tight; risky if Demucs concurrent |

### Verdict (Question D)

**Conditional GO** for Hetzner **4 vCPU / 8 GB RAM** as MVP launch configuration when:

- English defaults use **`ggml-base.en.bin`** (`whisper_model: base`), not `small.en`
- **`WHISPER_THREADS=4`** on VPS
- **Celery `--concurrency 1`** when Demucs is enabled
- **SQLite** remains acceptable for MVP (PostgreSQL deferred until proven growth)
- Jobs are **async batch** — RTF > 1.0 is acceptable if UX sets expectations on wait time

**Upgrade trigger (8 vCPU / 16 GB):** Revenue validation + customer demand for `small.en` quality tier or concurrent job load causing queue SLA misses.

**Phase 8 Deployment** must confirm estimates on actual Hetzner hardware.

---

## 6. Final Recommendations

### A. Recommended English subtitle model

**Recommendation: `base` → `ggml-base.en.bin`**

| Criterion | Assessment |
|-----------|------------|
| Launch readiness | Rubric 5 on EN-SPEECH; substantial upgrade over `tiny` (not re-benchmarked here but established in Phase 2) |
| Hetzner cost | ~400 MB RSS; est. ~16 min for 5.7 min video @ 4 vCPU — viable async |
| Operational simplicity | Single tier change from `tiny`; no new dependencies |
| Revenue / user value | Better accuracy for paying subtitle customers without `small.en` wait penalty |

**Implementation note:** Current code default is still `tiny` for `subtitle_generation`. Adopt `base` as launch default in a future config/product milestone — not in M3 scope.

**Opt-in:** `whisper_model: small` for customers accepting long runtimes (~77 min est. on Hetzner for this fixture length).

---

### B. Recommended English karaoke model

**Recommendation: `base` → `ggml-base.en.bin` (retain current Phase 5 default)**

| Criterion | Assessment |
|-----------|------------|
| Launch readiness | Rubric 3 on music — acceptable for MVP; `small.en` rubric 4 does not justify 2.8× wall time |
| Hetzner cost | ~393 MB RSS; est. ~25 min for 3.6 min music video @ 4 vCPU |
| User value | `small.en` captures more lyric segments (60 vs 47) but MVP karaoke ships with `base` + opt-in `small` |

**Do not change karaoke default to `small.en` for launch.**

---

### C. Recommended Urdu experimental model

**Recommendation: `small` → `ggml-small.bin` with explicit `language: ur`**

| Criterion | Assessment |
|-----------|------------|
| Quality | Rubric 4 experimental; `base` rubric 1 (unusable) on same fixture |
| Launch blocking | **Does not block** English MVP — market as experimental only |
| Ops | ~862 MB RSS; slow (est. ~53 min @ 4 vCPU for 3.6 min clip) — document wait times |

**Never recommend `ggml-base.bin` for Urdu** on this evidence. Roman Urdu remains deferred.

---

### D. Hetzner 4 vCPU / 8 GB launch configuration

**Conditional GO** — remains the recommended MVP deployment target.

| Item | Decision |
|------|----------|
| VPS size | 4 vCPU / 8 GB RAM at launch |
| Whisper defaults | English `base.en`; Urdu experimental `small.bin` only on opt-in |
| Threads | `WHISPER_THREADS=4` |
| Worker concurrency | `--concurrency 1` for Demucs safety |
| Database | SQLite acceptable for MVP |
| Future upgrade | 8 vCPU / 16 GB when revenue validates load or `small.en` product tier |

---

## 7. Decision Evaluation (Strategic Criteria)

| Criterion | M3 outcome |
|-----------|------------|
| 1. Commercial launch readiness | **Unblocked** — English `base.en` defaults identified; no architecture changes required |
| 2. Hetzner hosting cost | **Fits** with `base.en`; **does not fit** with default `small.en` |
| 3. Operational simplicity | **Low change** — tier selection only; same whisper.cpp subprocess |
| 4. Revenue generation potential | **`base` subtitle tier** supports paid quality upgrade from free/tiny tier |
| 5. User value | **`base.en`** best balance of accuracy vs wait time for English MVP |

---

## 8. Benchmark Execution Record

| Run # | Fixture | Model | Status |
|-------|---------|-------|--------|
| 1 | EN-SPEECH | base.en | ✅ ok |
| 2 | EN-SPEECH | small.en | ✅ ok |
| 3 | EN-MUSIC | base.en | ✅ ok |
| 4 | EN-MUSIC | small.en | ✅ ok |
| 5 | UR-SPEECH | base | ✅ ok |
| 6 | UR-SPEECH | small | ✅ ok |

**Failures:** None.

**Total benchmark wall time (sequential):** ~2 h 58 min (8 threads, full-length fixtures).

**Transcripts for review:** `/tmp/m3-v2/<fixture>/<label>/transcript.txt`

---

## 9. Next Steps

| Priority | Action |
|----------|--------|
| 1 | Phase 8 — Hetzner deployment validation with `-t 4` on subset (EN-SPEECH base.en + EN-MUSIC base.en) |
| 2 | Product decision — adopt `base` as subtitle default (currently `tiny` in code) |
| 3 | Document customer-facing model tiers (`tiny` fast / `base` standard / `small` premium) |
| 4 | Commercial launch prep — pricing, MVP packaging (English focus) |
| 5 | Optional Phase 7 M4 — Roman Urdu design only (deferred) |

---

## 10. Related Documents

```
docs/reports/PHASE7_M3_BENCHMARK_PLAN_V2.md
docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md
docs/context/PROJECT_SNAPSHOT_2026_06_22.md
docs/context/NEXT_SESSION_START_HERE.md
```

---

*Report generated from existing `/tmp/m3-v2` benchmark outputs — 2026-06-23. Phase 7 M3 benchmark execution complete.*
