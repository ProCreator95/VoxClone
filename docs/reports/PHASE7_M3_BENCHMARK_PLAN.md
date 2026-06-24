# Phase 7 — Milestone 3: Commercial Readiness and Whisper Benchmarking Plan

**Date:** 2026-06-23  
**Branch:** `feature/whisper-multilingual`  
**Authoritative context:** `docs/context/PROJECT_SNAPSHOT_2026_06_22.md`  
**Prior validation:** `docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md`  
**Scope:** Documentation and measurement only — **no application code, API, or routing changes**

---

## Executive Summary

This document defines a repeatable benchmark procedure to compare **`ggml-base.bin`** and **`ggml-small.bin`** on representative media fixtures. Results will inform production defaults for MVP launch on a **Hetzner VPS (4 vCPU / 8 GB RAM)** while respecting commercial readiness criteria:

1. MVP launch readiness  
2. Hosting cost on Hetzner  
3. Operational simplicity  
4. Revenue validation goals  

**Deliverable after execution:** `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` (filled data tables + production recommendations)

---

## 1. Repository Inspection Findings

### 1.1 Existing benchmark scripts

| Location | Purpose | Relevance to M3 |
|----------|---------|-----------------|
| `backend/tools/experiments/deepfilternet_poc.py` | DeepFilterNet CLI PoC | Not applicable to Whisper |
| *(none)* | Dedicated Whisper benchmark harness | **Does not exist** |

**Conclusion:** Benchmarks must be run via **direct `whisper-cli` subprocess commands** (mirrors production `WhisperService._run_subprocess()`) or optionally via the VoxClone API for end-to-end sanity checks. Direct CLI is preferred for isolated runtime/RAM measurement.

### 1.2 Existing test media

Media already present on the development machine (not committed to git — local `uploads/` and `processed/` artifacts):

| Fixture ID | Source file | Extracted WAV (16 kHz mono) | Duration | Category | Prior job evidence |
|------------|-------------|----------------------------|----------|----------|-------------------|
| **EN-SPEECH** | `uploads/…/sampl_vid.webm` (`da763e0f-…`) | `processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav` | ~340 s | English educational speech | Phase 2 validation (`ac849d78`) |
| **EN-MUSIC** | `uploads/d9f7d0d411cd40bfaaac2442757001a3.webm` (`believer_vid.webm`) | `processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav` | ~217 s | English music video (vocals + instrumental) | Phase 4 karaoke validation — known tiny-model lyric gaps |
| **UR-MIXED** | `uploads/4fb4b2a56f9e405db4b4a88ca389bbd5.mp4` (`baluga.mp4`) | `processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav` | ~214 s | Mixed EN intro + Urdu tutorial body | Phase 7 M2 Urdu validation (`01e02636`, `language: ur`, `small`) |
| **UR-SPEECH** | Same as UR-MIXED (full file) | Same WAV | ~214 s | Urdu-primary with code-mixed EN terms | Use `-l ur` — isolates Urdu routing path |
| **EN-SHORT** | `uploads/02fb6643e8f3454d85b96482d7ae9f91.mp4` | *(extract — see §4.2)* | ~10 s | Quick smoke / dry-run | No prior Whisper job |

**Recommended primary fixtures for full benchmark matrix:**

| Benchmark slot | WAV path | Language flag | Rationale |
|----------------|----------|---------------|-----------|
| English speech | `processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav` | `-l en` | Long-form clear speech; Phase 2 baseline |
| English music | `processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav` | `-l en` | Music-heavy content; karaoke-relevant |
| Urdu speech | `processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav` | `-l ur` | Phase 7 validated fixture |
| Mixed-language | `processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav` | *(omit `-l`)* | Tests auto-detection path (`language: auto` equivalent) |

**Optional acceleration clips (recommended for dry-runs):** Extract 60 s segments from each long fixture to iterate faster before full-length runs (see §4.2).

### 1.3 Existing Whisper validation reports

| Report | Content useful for M3 |
|--------|----------------------|
| `docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md` | Urdu accuracy observations, routing metadata, before/after on `baluga.mp4` |
| `docs/reports/PHASE7_M2_MULTILINGUAL_ROUTING_IMPLEMENTATION.md` | CLI flag behaviour, model resolution rules |
| `docs/reports/PHASE7_M1_WHISPER_MULTILINGUAL_DESIGN.md` | Routing policy design, disk/RAM estimates |
| `docs/reports/WHISPER_MULTILINGUAL_MODEL_SELECTION_ANALYSIS.md` | Pre-M2 root cause analysis |
| `docs/reports/PHASE5_MILESTONE1_WHISPER_MODELS.md` | Per-job defaults: subtitle → `tiny`, karaoke → `base` |
| `docs/testing/WHISPER_CPP_SETUP.md` | Model sizes, expected processing times, CLI examples |

### 1.4 Utility code relevant to measurement

| Code | Location | M3 usage |
|------|----------|----------|
| `WhisperService._run_subprocess()` | `backend/app/services/whisper_service.py` | **Reference for exact CLI args** — do not modify |
| `WhisperService._build_subprocess_env()` | same file | **Reference for `LD_LIBRARY_PATH`** |
| `resolve_whisper_model()` | `backend/app/services/whisper_models.py` | Confirms model file names only |
| `FFmpegService.extract_audio()` | `backend/app/services/ffmpeg_service.py` | Re-extract WAV if fixtures missing |
| `tests/test_whisper_models.py` | `backend/tests/` | Routing unit tests — run before benchmark to confirm M2 baseline |

**No existing code measures wall-clock or peak RSS.** Use shell `/usr/bin/time -v` wrapping `whisper-cli`.

---

## 2. Benchmark Methodology

### 2.1 Design principles

| Principle | Application |
|-----------|-------------|
| **Mirror production subprocess** | Same binary, `-m`, `-f`, `-t`, `--output-json`, `-l` flags as `WhisperService` |
| **Isolate Whisper** | Direct CLI — exclude Celery, Redis, FFmpeg extraction variance |
| **Control variables** | Fixed `WHISPER_THREADS`, same machine load, same WAV inputs |
| **Two model tiers only** | `ggml-base.bin` vs `ggml-small.bin` (multilingual) |
| **Commercial lens** | Recommend defaults that fit 4 vCPU / 8 GB Hetzner, not maximum accuracy alone |

### 2.2 Models under test

| Tier | File | Size | Multilingual |
|------|------|------|--------------|
| Base | `backend/models/ggml-base.bin` | ~142 MB | Yes |
| Small | `backend/models/ggml-small.bin` | ~466 MB | Yes |

English-only `.en.bin` models are **out of scope** for this matrix (MVP English defaults already validated in Phases 2–5). M3 focuses on multilingual tier selection for Urdu experimental path and `auto` routing.

### 2.3 Metrics

| Metric | Definition | Collection method |
|--------|------------|-------------------|
| **Wall-clock runtime** | Elapsed seconds from process start to exit 0 | `/usr/bin/time -f "%e"` or `date +%s.%N` before/after |
| **Peak RAM (RSS)** | Maximum resident set size of `whisper-cli` process | `/usr/bin/time -v` → `Maximum resident set size (kbytes)` |
| **Audio duration** | Input WAV length in seconds | `ffprobe -v error -show_entries format=duration -of csv=p=0` |
| **Realtime factor (RTF)** | `wall_clock / audio_duration` | Derived — lower is faster |
| **Segment count** | Number of transcription segments | `jq '.transcription \| length' output.json` |
| **Detected language** | whisper.cpp reported language | `jq -r '.result.language // .language' output.json` |
| **Accuracy (qualitative)** | Human rubric score 1–5 per fixture | Manual SRT/TXT review (see §2.5) |
| **Accuracy (quantitative, optional)** | WER/CER vs reference transcript | Only where reference exists (see §2.5) |

### 2.4 Environment constants

Record these in every benchmark run (dev machine now; Hetzner VPS when repeated):

```bash
# Record once per session
nproc                          # CPU threads available
grep WHISPER_THREADS backend/.env
uname -a
free -h                        # total system RAM
ls -lh backend/models/ggml-base.bin backend/models/ggml-small.bin
../tools/whisper.cpp/build/bin/whisper-cli --help 2>&1 | head -1
```

| Setting | Dev machine (observed) | Hetzner MVP target | Notes |
|---------|---------------------|-------------------|-------|
| CPU threads (`-t`) | 8 (`WHISPER_THREADS=8` in `.env`) | 4 | **Re-run full matrix on Hetzner with `-t 4`** |
| Binary | `tools/whisper.cpp/build/bin/whisper-cli` | Same build path | Requires `LD_LIBRARY_PATH` (see §4.1) |
| JSON flag | `--output-json` | `--output-json` | Subtitle pipeline default (`word_timestamps=False`) |

### 2.5 Accuracy review workflow

#### A. Qualitative rubric (required for all runs)

For each `(fixture, model)` pair, review `output.txt` or first 30 lines of SRT:

| Score | Label | Criteria |
|-------|-------|------------|
| 5 | Production-ready | Few or no word errors; no hallucination loops; timing plausible |
| 4 | Acceptable | Minor errors; usable for MVP English or experimental Urdu |
| 3 | Marginal | Frequent errors but gist preserved |
| 2 | Poor | Major segments wrong or repeated |
| 1 | Unusable | Hallucinations, wrong language, or empty output |

**Reviewers:** At minimum one human reviewer. Record reviewer name, date, and 2–3 example errors for scores ≤ 3.

**Fixture-specific focus:**

| Fixture | Review focus |
|---------|--------------|
| EN-SPEECH | Factual word accuracy, proper nouns (Spider-Man, etc.) |
| EN-MUSIC | Lyric capture during vocal sections; gap behaviour during instrumentals |
| UR-SPEECH (`-l ur`) | Arabic-script correctness, phonetic substitutions, technical terms |
| UR-MIXED (no `-l`) | English intro quality + Urdu body quality vs explicit `-l ur` run |

#### B. Quantitative WER (optional, EN-SPEECH only)

Phase 2 validation job `ac849d78` produced a reference transcript at:

```
backend/processed/ac849d78-fe28-4448-b029-a5c79a83ef94_transcript.txt
```

If pursuing WER:

1. Treat the existing `tiny.en` / Phase 2 transcript as **approximate reference** (not gold standard).
2. Normalize: lowercase, strip punctuation, collapse whitespace.
3. Compute WER with `jiwer` (install ad hoc: `pip install jiwer` — **not** added to project requirements).

```bash
python3 - <<'PY'
import jiwer
ref = open("backend/processed/ac849d78-fe28-4448-b029-a5c79a83ef94_transcript.txt").read()
hyp = open("/tmp/m3/en-speech/base/transcript.txt").read()
print("WER:", jiwer.wer(ref, hyp))
PY
```

**Note:** WER against a tiny-model reference biases toward tiny output. Use qualitative rubric as primary accuracy signal.

#### C. Urdu accuracy — compare against M2 baseline

Existing M2 outputs for comparison (no re-run required for reference):

| Model | Job ID | Transcript path |
|-------|--------|-----------------|
| `small` | `01e02636-…` | `processed/01e02636-…_transcript.txt` |
| `base` | `2b59867a-…` | `processed/2b59867a-…_transcript.txt` |

M3 runs should be compared side-by-side with these files for the same `baluga` audio fixture.

### 2.6 Output transcript locations

Direct CLI runs write JSON to a prefix specified by `-of`:

```
-of /tmp/m3/<fixture>/<model>/output   →   /tmp/m3/<fixture>/<model>/output.json
```

Extract plain text for review:

```bash
jq -r '.transcription[]?.text // empty' output.json | tr -d '\n' | fold -s > transcript.txt
```

**VoxClone pipeline outputs (API path, optional sanity check):**

```
backend/processed/<job_id>_transcript.txt
backend/processed/<job_id>_subtitles.srt
backend/processed/<job_id>_subtitles.vtt
```

---

## 3. Pre-Benchmark Checklist

Execute before any timed runs:

- [ ] Confirm models exist: `ls -lh backend/models/ggml-base.bin backend/models/ggml-small.bin`
- [ ] Confirm fixture WAVs exist (§1.2) or extract per §4.2
- [ ] Set `LD_LIBRARY_PATH` per §4.1
- [ ] Verify whisper-cli executes: `"$WHISPER_BIN" --help 2>&1 | head -1`
- [ ] Create output directory: `mkdir -p /tmp/m3/{en-speech,en-music,ur-speech,ur-mixed}/{base,small}`
- [ ] Close Demucs/Celery workers to avoid CPU/RAM contention
- [ ] Run routing unit tests: `cd backend && python -m unittest tests.test_whisper_models -v`
- [ ] Record environment metadata (§2.4)

---

## 4. Required Commands

### 4.1 Environment setup (every shell session)

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"

# Paths — adjust if repo location differs
export REPO="/home/shz/Documents/Mustafa projects/VoxClone"
export WHISPER_BIN="$REPO/tools/whisper.cpp/build/bin/whisper-cli"
export BUILD="$REPO/tools/whisper.cpp/build"
export LD_LIBRARY_PATH="$BUILD/src:$BUILD/ggml/src${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export MODELS="$REPO/backend/models"
export M3="/tmp/m3"
export THREADS=8          # Dev: match WHISPER_THREADS in .env
# export THREADS=4        # Hetzner MVP: use 4 vCPU

mkdir -p "$M3"/{en-speech,en-music,ur-speech,ur-mixed}/{base,small}
```

### 4.2 Fixture preparation

#### Use existing extracted WAVs (preferred)

```bash
export WAV_EN_SPEECH="$REPO/backend/processed/ac849d78-fe28-4448-b029-a5c79a83ef94_audio.wav"
export WAV_EN_MUSIC="$REPO/backend/processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav"
export WAV_UR="$REPO/backend/processed/01e02636-3273-4ca8-bbb5-649565e3b382_audio.wav"

# Verify format (must be 16 kHz mono PCM)
for w in "$WAV_EN_SPEECH" "$WAV_EN_MUSIC" "$WAV_UR"; do
  echo "=== $w ==="
  ffprobe -v error -show_entries stream=sample_rate,channels,codec_name -of default=noprint_wrappers=1 "$w"
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$w"
done
```

#### Optional: 60 s clips for fast iteration

```bash
clip() { ffmpeg -y -i "$1" -t 60 -acodec pcm_s16le -ar 16000 -ac 1 "$2"; }
clip "$WAV_EN_SPEECH" "$M3/en-speech/input_60s.wav"
clip "$WAV_EN_MUSIC"  "$M3/en-music/input_60s.wav"
clip "$WAV_UR"        "$M3/ur-speech/input_60s.wav"
# Use *_60s.wav paths in §4.3 during dry-run; full WAVs for final report
```

#### Fallback: extract from upload if processed WAV missing

```bash
ffmpeg -y -i "$REPO/backend/uploads/4fb4b2a56f9e405db4b4a88ca389bbd5.mp4" \
  -vn -acodec pcm_s16le -ar 16000 -ac 1 "$M3/ur-speech/input.wav"
```

### 4.3 Core benchmark command (single run)

Template — run once per `(fixture, model, language)` combination:

```bash
run_whisper_bench() {
  local fixture="$1"    # e.g. en-speech
  local model="$2"      # base | small
  local wav="$3"
  local lang_flag="${4:-}"   # "en", "ur", or empty for auto
  local model_file="$MODELS/ggml-${model}.bin"
  local outdir="$M3/$fixture/$model"
  mkdir -p "$outdir"

  local lang_args=()
  [[ -n "$lang_flag" ]] && lang_args=(-l "$lang_flag")

  local log="$outdir/time.log"
  local audio_dur
  audio_dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$wav")

  echo "=== $fixture / $model / lang=${lang_flag:-auto} ===" | tee "$log"
  echo "audio_duration_sec=$audio_dur" | tee -a "$log"
  echo "threads=$THREADS" | tee -a "$log"
  echo "model=$model_file" | tee -a "$log"
  date -Iseconds | tee -a "$log"

  /usr/bin/time -v "$WHISPER_BIN" \
    -m "$model_file" \
    -f "$wav" \
    -t "$THREADS" \
    --output-json \
    -of "$outdir/output" \
    "${lang_args[@]}" \
    2>>"$log"

  # Extract metrics from time log
  grep -E "Elapsed|Maximum resident" "$log" | tee -a "$outdir/metrics.txt"

  # Extract transcript
  jq -r '.transcription[]?.text // empty' "$outdir/output.json" 2>/dev/null \
    | tr -d '\n' | fold -s > "$outdir/transcript.txt"

  jq '{language: (.result.language // .language), segments: (.transcription | length)}' \
    "$outdir/output.json" > "$outdir/summary.json"
}
```

### 4.4 Full benchmark matrix (8 primary runs)

```bash
# English speech
run_whisper_bench en-speech base "$WAV_EN_SPEECH" en
run_whisper_bench en-speech small "$WAV_EN_SPEECH" en

# English music / karaoke-relevant
run_whisper_bench en-music base "$WAV_EN_MUSIC" en
run_whisper_bench en-music small "$WAV_EN_MUSIC" en

# Urdu explicit
run_whisper_bench ur-speech base "$WAV_UR" ur
run_whisper_bench ur-speech small "$WAV_UR" ur

# Mixed-language (auto-detect — no -l flag)
run_whisper_bench ur-mixed base "$WAV_UR" ""
run_whisper_bench ur-mixed small "$WAV_UR" ""
```

**Expected run count:** 8 timed runs × (3–6 min small / 1–3 min base on ~200 s audio) ≈ **30–60 min total** on 8-core dev machine. Full 340 s EN-SPEECH adds ~15–25 min.

### 4.5 Optional: English `.en.bin` cross-check (out of matrix, one run)

To validate MVP English defaults separately from multilingual tier:

```bash
/usr/bin/time -v "$WHISPER_BIN" \
  -m "$MODELS/ggml-base.en.bin" \
  -f "$WAV_EN_SPEECH" \
  -t "$THREADS" \
  --output-json \
  -l en \
  -of "$M3/en-speech/base.en/output" \
  2>"$M3/en-speech/base.en/time.log"
```

Document separately — not part of base vs small multilingual comparison.

### 4.6 Optional: API sanity check (not for RAM isolation)

After CLI matrix completes, optionally submit one job via API to confirm routing metadata unchanged:

```bash
# Requires FastAPI + Redis + Celery running
MEDIA_ID="<uuid for baluga.mp4>"
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\",\"parameters\":{\"language\":\"ur\",\"whisper_model\":\"base\"}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

Compare `whisper_model_file` in job parameters with CLI `-m` path. **Do not use API timing for M3 runtime tables** — includes FFmpeg extraction and queue overhead.

---

## 5. Data Collection Tables

Copy these tables into `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` after execution.

### 5.1 Environment record

| Field | Dev machine | Hetzner VPS |
|-------|-------------|-------------|
| Date | | |
| Hostname | | |
| CPU cores (`nproc`) | 8 | 4 (planned) |
| RAM total | | 8 GB (planned) |
| `WHISPER_THREADS` / `-t` | 8 | 4 |
| whisper.cpp build | | |
| `ggml-base.bin` size | 142 MB | |
| `ggml-small.bin` size | 466 MB | |

### 5.2 Runtime and memory matrix

| Fixture | Lang | Model | Audio dur (s) | Wall clock (s) | RTF | Peak RSS (MB) | Segments | Detected lang |
|---------|------|-------|---------------|----------------|-----|---------------|----------|---------------|
| EN-SPEECH | en | base | | | | | | |
| EN-SPEECH | en | small | | | | | | |
| EN-MUSIC | en | base | | | | | | |
| EN-MUSIC | en | small | | | | | | |
| UR-SPEECH | ur | base | | | | | | |
| UR-SPEECH | ur | small | | | | | | |
| UR-MIXED | auto | base | | | | | | |
| UR-MIXED | auto | small | | | | | | |

**RTF** = wall clock ÷ audio duration. **Target for MVP:** RTF < 1.0 on 4 vCPU for ≤ 5 min English speech jobs (ideal); document actuals even if slower.

### 5.3 Accuracy rubric matrix

| Fixture | Model | Rubric (1–5) | Notable errors (examples) | MVP acceptable? |
|---------|-------|--------------|---------------------------|-----------------|
| EN-SPEECH | base | | | |
| EN-SPEECH | small | | | |
| EN-MUSIC | base | | | |
| EN-MUSIC | small | | | |
| UR-SPEECH | base | | | |
| UR-SPEECH | small | | | |
| UR-MIXED | base | | | |
| UR-MIXED | small | | | |

### 5.4 M2 baseline comparison (Urdu fixture)

| Model | M2 job ID | M3 rubric | Delta vs M2 |
|-------|-----------|-----------|-------------|
| base | `2b59867a-…` | | |
| small | `01e02636-…` | | |

---

## 6. Recommended Execution Sequence

| Step | Action | Duration est. |
|------|--------|---------------|
| 1 | Read this plan + `PROJECT_SNAPSHOT_2026_06_22.md` | 10 min |
| 2 | Pre-benchmark checklist (§3) | 10 min |
| 3 | Environment setup (§4.1–4.2) | 5 min |
| 4 | **Dry-run:** 60 s clips × 2 models × 1 fixture | 5 min |
| 5 | **Primary matrix:** §4.4 full runs on dev (8-core) | 45–90 min |
| 6 | Accuracy review (§2.5) — fill rubric tables | 30–45 min |
| 7 | Write `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` | 30 min |
| 8 | Apply production recommendation framework (§8) | 15 min |
| 9 | **Repeat steps 4–7 on Hetzner VPS** with `THREADS=4` | 60–120 min |
| 10 | Update `NEXT_SESSION_START_HERE.md` with defaults | 10 min |

**Priority order if time-constrained:**

1. UR-SPEECH (`-l ur`) — base vs small  
2. EN-SPEECH — base vs small  
3. EN-MUSIC — base vs small  
4. UR-MIXED (auto) — base vs small  

---

## 7. Success Criteria

### 7.1 Benchmark execution complete when:

- [ ] All 8 primary matrix runs completed without error on dev machine
- [ ] All cells in §5.2 runtime table filled
- [ ] All cells in §5.3 accuracy rubric filled
- [ ] Peak RSS recorded for every run via `/usr/bin/time -v`
- [ ] Hetzner repeat completed OR explicitly deferred with rationale in report

### 7.2 Production recommendation complete when:

- [ ] Default `whisper_model` tier chosen for `subtitle_generation` (English MVP)
- [ ] Default `whisper_model` tier chosen for `karaoke` (English MVP)
- [ ] Urdu experimental tier documented (base vs small)
- [ ] VPS sizing recommendation: stay on 4 vCPU / 8 GB or upgrade trigger defined
- [ ] Decision explicitly evaluated against four commercial criteria (§8)
- [ ] `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` committed to `docs/reports/`

### 7.3 Explicit non-goals (M3)

- No application code changes
- No API changes
- No Whisper routing logic changes
- No `ggml-medium.bin` download (optional future phase)
- No Roman Urdu implementation

---

## 8. Production Recommendation Framework

After filling data tables, apply this decision tree **in order**:

### Step 1 — MVP launch readiness

| Question | If YES | If NO |
|----------|--------|-------|
| Does `base` meet rubric ≥ 4 on EN-SPEECH and EN-MUSIC? | Default English tier = `base` | Default English tier = `small` if RAM allows; else accept `base` gaps |
| Does `small` RTF × typical job duration fit user patience (< 2× realtime on 4 vCPU)? | `small` viable for karaoke | Keep karaoke default `base` |

### Step 2 — Hetzner hosting cost (4 vCPU / 8 GB)

| Peak RSS (small) | Verdict |
|------------------|---------|
| < 2 GB | Safe concurrent with Celery + Demucs at `--concurrency 1` |
| 2–4 GB | Whisper-only OK; avoid parallel Whisper + Demucs |
| > 4 GB | **Do not default to `small`** on 8 GB VPS; use `base` or upgrade to 16 GB |

| Peak RSS (base) | Verdict |
|-----------------|---------|
| < 1 GB | Preferred MVP default |
| 1–2 GB | Acceptable |

### Step 3 — Operational simplicity

| Factor | Recommendation |
|--------|----------------|
| Disk | English-only MVP needs `.en.bin` trio (~681 MB); add multilingual pair (+608 MB) only if offering experimental Urdu |
| Model count | Prefer single multilingual tier (`base` or `small`) for Urdu — not both in production defaults |
| Thread config | Set `WHISPER_THREADS=4` on Hetzner to match vCPU |

### Step 4 — Revenue validation goals

| Outcome | Action |
|---------|--------|
| English quality sufficient at `base` | **Ship MVP with `subtitle_generation` → tiny/base.en and `karaoke` → base.en** — no change |
| Urdu rubric ≤ 3 on both tiers | Market Urdu as **experimental**; do not block launch |
| Urdu `small` rubric = 4 but RTF > 2× on 4 vCPU | Document as opt-in `whisper_model: small`; default experimental tier = `base` |
| Neither tier usable for Urdu | Defer Urdu marketing; launch English MVP only |

### Expected outcome template (fill after benchmark)

```markdown
## Production defaults (M3 recommendation)

| Job type | English default | Urdu experimental | Rationale |
|----------|-----------------|-------------------|-----------|
| subtitle_generation | whisper_model: ??? | language: ur, whisper_model: ??? | |
| karaoke | whisper_model: ??? | language: ur, whisper_model: ??? | |

| VPS | Recommendation |
|-----|----------------|
| 4 vCPU / 8 GB | [GO / NO-GO for small default] |
| Upgrade trigger | Peak RSS > ??? MB or p95 job time > ??? s |
```

---

## 9. Known Blockers and Mitigations

| Blocker | Severity | Mitigation |
|---------|----------|------------|
| **`libwhisper.so.1` not found** when running CLI bare | High | Export `LD_LIBRARY_PATH` per §4.1 (matches `WhisperService._build_subprocess_env()`) |
| **Long fixture duration** (~340 s EN-SPEECH) | Medium | Use 60 s clips for iteration; run full length for final report row |
| **No committed test media in git** | Medium | Fixtures are local `uploads/` / `processed/` artifacts — verify paths before benchmark; re-extract from uploads if missing |
| **No automated WER tooling in repo** | Low | Qualitative rubric is primary; optional `jiwer` ad hoc |
| **Dev machine 8 cores vs Hetzner 4 cores** | Medium | **Must re-run matrix on Hetzner with `-t 4`** before production sign-off |
| **Concurrent Celery/Demucs jobs** | Medium | Stop workers during CLI benchmark; production concurrency documented separately |
| **EN-SPEECH reference transcript from tiny model** | Low | Do not over-weight WER; use rubric |
| **Mixed-language fixture** | Low | Same file used for UR-SPEECH (`-l ur`) and UR-MIXED (auto) — document cross-language intro behaviour |

---

## 10. Post-M3 Artifacts

| Artifact | Path | Owner |
|----------|------|-------|
| Benchmark plan (this document) | `docs/reports/PHASE7_M3_BENCHMARK_PLAN.md` | ✅ Created |
| Benchmark results | `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` | Pending execution |
| Session entry update | `docs/context/NEXT_SESSION_START_HERE.md` | After report complete |
| Production defaults | Document in report + snapshot addendum | After report complete |

---

*Plan created: 2026-06-23 — Phase 7 M3 documentation only; no application code modified.*
