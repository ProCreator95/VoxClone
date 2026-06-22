# Phase 6 — Milestone 1: DeepFilterNet Feasibility, Dependency Validation, and Architecture Design

**Status:** Complete (research + PoC + design + integration rules hardened)
**Date:** 2026-06-20
**Branch:** `feature/audio-enhancement`
**Baseline:** Phase 5 production (`phase5-final` @ `ddb2366` on `feature/source-separation`)

---

## Documentation Reviewed

| Document | Purpose |
|----------|---------|
| `docs/context/MASTER_PROJECT_HANDOFF.md` | Architecture, stack, Celery model, Phase 5 baseline |
| `docs/context/CURRENT_PROJECT_STATE.md` | Environment pins, component status |
| `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md` | ML pin lessons (Bug 8), async loop ownership (Bug 9) |
| `docs/context/NEXT_SESSION_START_HERE.md` | Phase 6 entry point |
| `docs/reports/PHASE5_MILESTONE1_WHISPER_MODELS.md` | Milestone report structure reference |
| `docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` | Demucs service + ML self-test pattern |
| `docs/reports/PHASE5_MILESTONE3_KARAOKE_MODES.md` | Job parameters / download endpoint patterns |
| `docs/reports/PHASE5_MILESTONE4_STEM_REUSE.md` | Canonical stem reuse for future enhancement inputs |
| `docs/reports/PHASE5_STEM_OWNERSHIP_AND_OPS.md` | Worker concurrency, stem ownership rules |
| `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md` | Torch pin strategy (authoritative for ML deps) |
| `docs/reports/PHASE5_DOCUMENTATION_SYNC.md` | Phase 5 git/doc alignment |

---

## 1. DeepFilterNet Investigation

### Project overview

[DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) is an open-source speech enhancement framework using deep filtering for full-band (48 kHz) noise suppression. Maintained by Hendrik Schröter (Rikorose). Latest PyPI release: **0.5.6** (August 2023). Default inference model in current tooling: **DeepFilterNet3**.

Two integration surfaces exist:

| Surface | Backend | Python deps | Notes |
|---------|---------|-------------|-------|
| **Python package** (`deepfilternet`) | PyTorch | torch, torchaudio, deepfilterlib (Rust extension) | `from df import enhance, init_df` |
| **CLI binary** (`deep-filter`) | tract (Rust) | **None** | Precompiled releases; 48 kHz WAV only |

VoxClone Phase 6 originally planned the Python package. This milestone evaluates both paths.

### Installation requirements

**Python path (`pip install deepfilternet==0.5.6`):**

| Requirement | Detail |
|-------------|--------|
| PyTorch | `>=1.9` per upstream README; tested against VoxClone `torch==2.8.0+cpu` (theoretical — not co-installed) |
| Rust toolchain | Required on **Python 3.12** — no `cp312` wheel for `deepfilterlib` |
| Build tools | `maturin` if building from source |
| System | Linux, macOS, Windows supported upstream |

**CLI path (`deep-filter` release binary):**

| Requirement | Detail |
|-------------|--------|
| Binary | Download from [GitHub releases v0.5.6](https://github.com/Rikorose/DeepFilterNet/releases/tag/v0.5.6) |
| Ubuntu 24.04 x86_64 | `deep-filter-0.5.6-x86_64-unknown-linux-musl` (validated in PoC) |
| ffmpeg | Resample non-48 kHz inputs before enhancement |

### Supported Python versions

| Source | Python support |
|--------|----------------|
| PyPI `deepfilternet` 0.5.6 | `>=3.8,<4.0` (classifiers: 3.8–3.11) |
| PyPI `deepfilterlib` 0.5.6 wheels | **cp38, cp39, cp310, cp311 only** — no cp312 |
| VoxClone backend | **Python 3.12.3** (Ubuntu 24.04 default) |
| Open PR [#636](https://github.com/Rikorose/DeepFilterNet/pull/636) | Python 3.12 + numpy 2.x — **not merged, not published** |

**Finding:** Official PyPI packages do not ship Python 3.12 wheels. On 3.12, pip falls back to building `deepfilterlib` from source, which requires Rust/Cargo (not present on the dev host).

### Ubuntu 24.04 compatibility

| Check | Result |
|-------|--------|
| `deep-filter` musl binary on x86_64 | ✅ Runs; PoC completed |
| `pip install deepfilternet` on Python 3.12 | ❌ Fails — no cp312 wheel, Rust required |
| ffmpeg resample 16 kHz → 48 kHz | ✅ Standard pipeline step |

### CPU-only support

Both paths support CPU-only inference. The PoC used the CPU-only tract binary (no CUDA). Python path accepts CPU torch wheels from `download.pytorch.org/whl/cpu`.

### Memory requirements

| Backend | Observed (PoC) | Engineering estimate |
|---------|----------------|------------------------|
| `deep-filter` CLI | **~122 MB RSS** peak (`/usr/bin/time -v`) | 150–300 MB for typical speech |
| Python + PyTorch | Not measured (install blocked) | 500 MB–1.5 GB model + torch overhead |
| Demucs (reference) | 4–8 GB per job | Documented in Phase 5 ops |

DeepFilterNet is **much lighter** than Demucs. Combined worker RAM is dominated by Demucs when both queues share a host.

### Model download requirements

| Backend | Model delivery |
|---------|----------------|
| `deep-filter` CLI | Models bundled inside release binary (~35 MB download); no separate HuggingFace step observed |
| Python `init_df()` | Downloads pretrained weights to user cache on first run (~few MB per model variant) |

PoC log: `Running with model type deepfilternet3 lookahead 2` — DeepFilterNet3 loaded without manual model path.

### Runtime dependencies (Python package)

From PyPI metadata for `deepfilternet==0.5.6`:

```
appdirs>=1.4,<2.0
deepfilterlib==0.5.6
loguru>=0.5
numpy>=1.22,<2.0          ← hard upper bound <2.0
packaging>=23.0,<24.0     ← hard upper bound <24.0
requests>=2.27,<3.0
sympy>=1.6
```

Optional extras: `[train]`, `[eval]`, `[soundfile]`, `[dnsmos-local]`.

### Typical enhancement quality

DeepFilterNet targets **speech** noise suppression (fans, traffic, room noise). Published demos and ICASSP/INTERSPEECH papers report strong perceptual quality on speech at low complexity.

| Content type | Expected behaviour |
|--------------|-------------------|
| Noisy speech / podcast | Strong noise reduction; primary use case |
| Whisper pipeline input (16 kHz mono) | Beneficial if resampled; may improve transcription SNR |
| Music / karaoke stems | **Not recommended** — designed for speech; may attenuate musical content |
| Full-band music video | Risk of over-suppression; out of scope for Phase 6 default |

PoC on project karaoke extract (`0e44f8ef-…_audio.wav`, music-heavy) completed with clipping warnings — expected for non-speech-dominant content.

### Licensing

Dual-licensed **MIT** or **Apache-2.0** at user choice ([DeepFilterNet LICENSE](https://github.com/Rikorose/DeepFilterNet)). Compatible with VoxClone's offline-first deployment model. No cloud API keys required.

---

## 2. Compatibility Matrix

Current VoxClone ML stack (validated Phase 5):

```
Python 3.12.3
torch==2.8.0+cpu
torchaudio==2.8.0+cpu
demucs==4.0.1
numpy==2.4.6          ← present in worker venv (transitive)
```

| Component | DeepFilterNet 0.5.6 requirement | VoxClone current | Compatible? | Notes |
|-----------|--------------------------------|------------------|-------------|-------|
| Python | 3.8–3.11 wheels; 3.12 needs source build | **3.12.3** | ⚠️ **Blocked** | No cp312 `deepfilterlib` wheel |
| torch | >=1.9 (README) | **2.8.0+cpu** | ✅ Likely | Same major; not co-tested in-process |
| torchaudio | Implicit via torch | **2.8.0+cpu** | ✅ Likely | Do not upgrade (Bug 8) |
| numpy | **>=1.22,<2.0** | **2.4.6** | ❌ **Conflict** | Hard pin in deepfilternet metadata |
| packaging | **>=23,<24** | 24.x (typical) | ⚠️ Possible conflict | May block pip resolver |
| soundfile | optional `<0.13` extra | `>=0.12.1` in requirements-ml | ✅ | Within range |
| demucs | — | 4.0.1 | ⚠️ Indirect | Shares torch; RAM stacking risk |
| deepfilterlib | ==0.5.6 | not installed | ❌ | Build failure on 3.12 without Rust |
| Whisper (whisper.cpp) | — | subprocess binary | ✅ Isolated | No Python ML coupling |
| Celery worker | — | fork pool, concurrency=1 | ✅ | Subprocess pattern fits |

### Install validation (2026-06-20)

```bash
# Isolated fresh Python 3.12 venv
pip install deepfilternet==0.5.6
# → deepfilterlib source build → "Cargo, the Rust package manager, is not installed"

# Main worker venv dry-run with numpy pin
pip install deepfilternet==0.5.6 "numpy>=1.22,<2.0"
# → Same Rust/Cargo failure (no cp312 wheel)
```

---

## 3. Dependency Risk Analysis

### Direct conflicts

| Conflict | Severity | Impact |
|----------|----------|--------|
| **numpy 2.x vs `<2.0`** | **High** | Cannot install `deepfilternet` alongside current worker numpy without downgrade |
| **No cp312 deepfilterlib wheel** | **High** | pip install fails on VoxClone Python without Rust build chain |
| **packaging `<24`** | Medium | May conflict with newer setuptools/pip transitive deps |

### Indirect conflicts

| Risk | Severity | Impact |
|------|----------|--------|
| **numpy downgrade breaks torch 2.8 / demucs** | **High** | Torch 2.8 ships/tested with numpy 2.x on this host; downgrading risks Demucs regression |
| **Shared torch in-process** | Medium | Two PyTorch consumers in one worker increases OOM and import-time side effects |
| **Demucs + DFN concurrent jobs** | Medium | Even subprocess isolation: host RAM may exceed limits at concurrency >1 |
| **Sample rate mismatch** | Low | Pipeline uses 16 kHz (Whisper) and 44.1 kHz (Demucs); DFN wants 48 kHz — FFmpeg bridge required |

### Packaging risks

1. Adding `deepfilternet` to `requirements-ml.txt` would force pip to reconcile **numpy<2** with torch/demucs stack that currently resolves **numpy 2.4.6**.
2. Upgrading torch/torchaudio to satisfy a future DeepFilterNet release is **explicitly rejected** — Phase 5 Demucs pin is production baseline (Bug 8).
3. Unmerged community wheels (PR #636) are **not production-grade** — no official maintainer release for 3.12.

### Runtime risks

| Risk | Mitigation |
|------|------------|
| PyTorch loaded in Celery parent before fork | Use **subprocess** (Demucs pattern) — never import torch in task module top-level |
| Model init latency on every job | Lazy-init in subprocess or long-lived sidecar; cache model in child process |
| Non-speech content degradation | Document job scope; optional `attenuation_limit` parameter (future) |
| Clipping on hot inputs | PoC observed `Possible clipping detected (1.000)` — normalize or warn in service |

### Mitigation strategies

| Strategy | Preserves Demucs? | Recommendation |
|----------|-------------------|----------------|
| **A. Subprocess `deep-filter` CLI** | ✅ Yes | **Approved for M2** — zero Python ML coupling |
| **B. Subprocess dedicated Python venv** (3.11 + pinned numpy<2 + torch 2.8) | ✅ Yes | Fallback if CLI insufficient; higher ops burden |
| **C. Add deepfilternet to shared requirements-ml.txt** | ❌ Risk | **Do not do** |
| **D. Upgrade torch for DeepFilterNet** | ❌ Risk | **Do not do** without full Demucs re-validation |
| **E. Build deepfilterlib from source on 3.12** | ✅ If isolated | Acceptable for PoC/dev; adds Rust toolchain to worker image |

**Priority rule (per project spec):** Preserving the Demucs pipeline is higher priority than introducing DeepFilterNet. Any integration must not modify `torch==2.8.0` / `torchaudio==2.8.0` / `demucs==4.0.1` pins.

---

## 4. Runtime Estimates

PoC benchmark (validated):

| Metric | Value |
|--------|-------|
| Input | 216.5 s mono speech/music extract @ 48 kHz |
| Wall time | 176 s (~2 min 56 s) |
| Real-time factor (RTF) | **0.79** (faster than real-time on 1 CPU core) |
| CPU utilization | ~99% single core |
| Peak RSS | **122 MB** |

Engineering estimates (RTF ≈ 0.8, single CPU core, `deep-filter` CLI, DeepFilterNet3):

| Audio length | Estimated processing time | Assumptions |
|--------------|---------------------------|-------------|
| 1 minute | ~48 s | Linear scaling; 48 kHz mono |
| 5 minutes | ~4 min | Same |
| 30 minutes | ~24 min | Same; consider progress updates every 30–60 s |

Variables that increase runtime:

- Post-filter enabled (`--pf`): ~5–15% overhead (estimate)
- Python PyTorch backend: typically slower than tract CLI
- Resampling FFmpeg step: negligible vs inference
- First-run model load: ~2–3 s (observed in PoC logs)

Variables that increase memory:

- Python path with torch loaded: +500 MB–1.5 GB
- Long files: streaming/chunked processing keeps RSS flat (CLI handles internally)

---

## 5. Experimental PoC Summary

### Location

```
backend/tools/experiments/deepfilternet_poc.py
backend/tools/experiments/bin/deep-filter          # release binary (local download)
backend/tools/experiments/output/                  # PoC artifacts (gitignored recommended)
```

### Run

```bash
cd backend
python tools/experiments/deepfilternet_poc.py \
  --input processed/0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav \
  --output-dir tools/experiments/output/poc_latest
```

### PoC results (2026-06-20)

| Check | Result |
|-------|--------|
| Binary download + execute | ✅ `deep_filter 0.5.6` |
| ffmpeg resample 16 kHz → 48 kHz | ✅ |
| Enhancement completes | ✅ exit 0 |
| Output WAV written | ✅ `{output_dir}/{stem}.wav` |
| Diagnostics printed | ✅ duration, RTF, byte size |
| VoxClone services touched | ✅ None |
| `pip install deepfilternet` on 3.12 | ❌ Rust required |

Sample diagnostics:

```
elapsed_seconds: 176.35
real_time_factor: 0.7943
enhanced_bytes: 20787662
backend: deep-filter-cli
deep_filter_version: 0.5.6
```

Log excerpt: `Enhanced audio file … in 171.99 (RTF: 0.7942617)` — tract backend, DeepFilterNet3.

---

## 6. Proposed AudioEnhancementService

**Design only — not implemented in M1.**

Follows `SourceSeparationService` subprocess isolation pattern. Does **not** import PyTorch or DeepFilterNet in the Celery worker process.

### Responsibilities

| Responsibility | Owner |
|----------------|-------|
| Validate input path, media type, duration | `AudioEnhancementService.validate()` |
| Resolve enhancement backend (CLI default) | Service config |
| Prepare 48 kHz mono WAV via FFmpeg | `FFmpegService` (new helper or reuse transcode) |
| Run enhancement subprocess | `asyncio.create_subprocess_exec` |
| Manage temp dirs (`.dfn_tmp/<job_id>/`) | Service + `safe_delete()` |
| Copy stable output to `processed/{job_id}_enhanced.wav` | Service |
| Model lifecycle | CLI: none; Python path: lazy init in **child** process only |
| Return `EnhancementResult` dataclass | Absolute paths + metadata |

### Proposed interface

```python
@dataclass(frozen=True)
class EnhancementResult:
    enhanced_path: Path
    input_path: Path
    sample_rate: int
    duration_seconds: float
    backend: str          # "deep-filter-cli" | "deepfilternet-python"
    model: str            # e.g. "DeepFilterNet3"
    post_filter: bool

class AudioEnhancementService:
    async def validate(self) -> None: ...
    async def enhance(
        self,
        input_path: Path,
        job_id: str,
        *,
        post_filter: bool = False,
        attenuation_limit: float | None = None,  # future CLI flag if exposed
    ) -> EnhancementResult: ...
```

### Service boundaries

```
┌─────────────────────────────────────────────────────────┐
│ audio_enhance_task (Celery, ai queue)                    │
│   run_async() → JobService / Redis progress              │
│   FFmpegService.extract_* → 48 kHz WAV                   │
│   AudioEnhancementService.enhance() → subprocess         │
│   persist parameters.result_files.enhanced               │
└─────────────────────────────────────────────────────────┘
          │ subprocess only
          ▼
┌─────────────────────────────────────────────────────────┐
│ deep-filter binary  OR  python -m df.enhance (isolated)  │
│   No torch import in Celery parent process               │
└─────────────────────────────────────────────────────────┘
```

### Integration points

| Point | Phase 5 behaviour | Phase 6 addition |
|-------|-------------------|------------------|
| `media_tasks.audio_enhance_task` | Placeholder → `mark_failed` | Wire service + FFmpeg prep |
| `celery_app.py` routing | `ai` queue | **Unchanged** |
| `async_runner.run_async()` | Required | **Unchanged** |
| `FFmpegService` | extract/burn/transcode | Add/resample helper for 48 kHz |
| `requirements-ml.txt` | torch/demucs pins | **Do not add deepfilternet** in M2 initial PR |
| Config (`.env`) | — | `DEEP_FILTER_BINARY`, `ENHANCEMENT_SAMPLE_RATE=48000` |

### Worker requirements

- ffmpeg + ffprobe (already required)
- `deep-filter` binary in `backend/tools/` or configurable path
- **Keep `--concurrency=1`** when Demucs and enhancement share a worker host
- Optional: separate Celery queue `ai-enhance` in a future ops hardening phase (not M2 scope)

### Failure handling

| Failure | Action |
|---------|--------|
| Binary missing | `validate()` at task start → actionable error in `mark_failed()` |
| Non-zero subprocess exit | Capture stderr tail (≤4 KB, Demucs pattern) → `mark_failed()` |
| Input missing / wrong format | Fail before subprocess |
| Output missing after exit 0 | `AudioEnhancementError` with stdout tail |
| OOM | Worker process death → existing retry/conflict limitation applies |

### Cleanup strategy

| Artifact | Policy |
|----------|--------|
| `.dfn_tmp/<job_id>/` | Delete on success and failure (`safe_delete`) |
| Resampled intermediate | Record in `parameters.intermediate_files.enhancement_input` (Phase 5 reproducibility pattern) |
| Enhanced output | Persist at `processed/{job_id}_enhanced.wav` |
| Binary / models | Ship with deploy or download once in worker setup |

---

## 7. Future Integration Strategy

**Design only — no schema/endpoint changes in M1.**

### Future job type behaviour

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "audio_enhance",
  "parameters": {
    "post_filter": false,
    "source_job_id": "<optional completed vocal_separation or audio_extraction job>"
  }
}
```

Pipeline:

1. Load media (or resolve audio from `source_job_id` canonical stem / prior extraction).
2. Extract/resample to 48 kHz mono WAV.
3. Run `AudioEnhancementService.enhance()`.
4. Persist metadata; `result_path` → enhanced WAV.

Optional `source_job_id` follows Phase 5 `separation_job_id` reuse pattern — enhancement can consume canonical **vocals** stem from a completed `vocal_separation` job (speech-only path).

### Future output files

| File | Purpose |
|------|---------|
| `processed/{job_id}_enhanced.wav` | Primary output (48 kHz mono) |
| `processed/{job_id}_enhancement_input.wav` | Intermediate resampled input (optional metadata) |

### Future result schema (`parameters` after completion)

```json
{
  "post_filter": false,
  "enhancement_backend": "deep-filter-cli",
  "enhancement_model": "DeepFilterNet3",
  "input_sample_rate": 48000,
  "duration_seconds": 216.5,
  "result_files": {
    "enhanced": "/abs/processed/{job_id}_enhanced.wav"
  },
  "intermediate_files": {
    "enhancement_input": "/abs/processed/{job_id}_enhancement_input.wav"
  }
}
```

### Future download endpoints

Add **after** literal routes, **before** catch-all `/{format_type}` (Bug 6 lesson):

```
GET /api/v1/jobs/{id}/download/enhanced   → audio/wav
```

Reuse existing patterns from `download_vocals_stem()`:

- Validate `job_type == audio_enhance` and `status == completed`
- Read `parameters.result_files.enhanced`
- Return `FileResponse`

`GET /jobs/{id}/result` continues to serve primary output (enhanced WAV).

### Phase 5 compatibility

| Area | Breaking change? |
|------|------------------|
| Existing job types | No |
| Demucs / karaoke / Whisper | No |
| Celery routing | No |
| Redis progress keys | No |
| Stem reuse model | Enhancement **reads** canonical stems; does not mutate Phase 5 jobs |
| `requirements-ml.txt` | Unchanged in initial integration |

---

## 8. Recommendation

**Approved for Phase 6 Milestone 2:** subprocess integration using the **`deep-filter` CLI**,
mirroring `SourceSeparationService`. This is **project policy** — see
**DeepFilterNet Integration Rules** below and
`docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`.

Rationale:

1. **PoC validated** enhancement quality path on Ubuntu 24.04 / x86_64 without touching the torch stack.
2. **Python package install is blocked** on Python 3.12 without Rust and conflicts on numpy 2.x / packaging.
3. **Demucs pins remain untouched** — highest priority constraint satisfied.
4. **Operational simplicity** — static binary, ~122 MB RAM, RTF ≈ 0.8–1.3 on one core.
5. **Whisper isolation preserved** — whisper.cpp remains a separate subprocess stack.

Deferred to M2+:

- Optional Python-backend subprocess in an isolated 3.11 venv if CLI features prove insufficient (requires exception process).
- `source_job_id` reuse from canonical vocals stems.
- Chunked progress reporting for long files.

Do **not** do in M2:

- Merge `deepfilternet` into `requirements-ml.txt` or `requirements.txt`
- Upgrade, downgrade, or replace torch/torchaudio/demucs/numpy/packaging pins
- Modify existing download endpoints until enhancement task is implemented

---

## DeepFilterNet Integration Rules

**Project policy** — hardened 2026-06-20 after M1 verification audit.
Authoritative summary: `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`

### Dependency Protection

The validated Phase 5 ML stack is production baseline and must be preserved:

```text
torch==2.8.0+cpu
torchaudio==2.8.0+cpu
demucs==4.0.1
numpy==2.4.6
packaging==26.2
```

Do not upgrade, downgrade, or replace these packages as part of Phase 6.

### DeepFilterNet Installation Policy

DeepFilterNet integration **SHALL** use the `deep-filter` CLI binary.

The Python package:

```bash
pip install deepfilternet
```

shall **NOT** be added to:

- `requirements.txt`
- `requirements-ml.txt`

unless a future compatibility investigation and full regression validation are completed.

### Reason

DeepFilterNet 0.5.6 currently has:

- no official Python 3.12 wheel for `deepfilterlib`
- `numpy` `< 2.0` requirement
- `packaging` `< 24` requirement

These conflict with the validated VoxClone worker environment (audit confirmed 2026-06-20).

### Approved Architecture

| System | Integration |
|--------|-------------|
| Whisper | whisper.cpp subprocess |
| Demucs | `python -m demucs` subprocess |
| DeepFilterNet | `deep-filter` subprocess |

All ML systems remain isolated from each other. No shared Python dependency
integration is permitted for DeepFilterNet in Phase 6.

### Future Exception Process

Any future proposal to use the Python DeepFilterNet package must include:

1. Full dependency analysis
2. Demucs regression validation
3. Torch compatibility validation
4. Python 3.12 compatibility validation
5. Explicit approval in a milestone report

---

## 9. Go / No-Go Assessment

| Question | Verdict |
|----------|---------|
| Can DeepFilterNet enhance audio on VoxClone's target OS? | **GO** — CLI validated |
| Can the Python package install in the worker venv as-is? | **NO-GO** — Python 3.12 + numpy 2.x blockers |
| Can integration proceed without destabilizing Demucs/torch 2.8? | **GO** — via subprocess isolation |
| Can integration proceed without destabilizing Whisper? | **GO** — independent stack |
| Is production integration ready after M1? | **NO** — M2 implementation required |
| Is Phase 6 technically feasible overall? | **CONDITIONAL GO** |

### Final decision

**CONDITIONAL GO for Phase 6 Milestone 2**

Proceed with architecture design and PoC evidence above. Blockers for the **Python in-venv** approach are real but ** circumvented** by the CLI subprocess strategy. Milestone 2 should implement `AudioEnhancementService` + `audio_enhance_task` wiring using `deep-filter`, with FFmpeg resampling and new download endpoint — still preserving all Phase 5 validated behaviour.

If M2 requires Python-only APIs (training flags, custom models), spawn an **isolated interpreter** rather than sharing `requirements-ml.txt`.

---

## Appendix A — PoC artifact paths

```
backend/tools/experiments/deepfilternet_poc.py
backend/tools/experiments/bin/deep-filter
backend/tools/experiments/output/poc_run/poc_input_48k.wav   # enhanced output
backend/tools/experiments/output/poc_run/run.log
```

## Appendix B — References

- DeepFilterNet repository: https://github.com/Rikorose/DeepFilterNet
- PyPI deepfilternet 0.5.6: https://pypi.org/project/deepfilternet/0.5.6/
- Release binaries v0.5.6: https://github.com/Rikorose/DeepFilterNet/releases/tag/v0.5.6
- Phase 5 Demucs pin analysis: `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md`
- Phase 6 M1 verification audit: `docs/reports/PHASE6_M1_VERIFICATION_AUDIT.md`
- Phase 6 dependency protection rules: `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`

---

*Milestone 1 complete. Integration rules hardened 2026-06-20. No production code, schemas, endpoints, or Celery tasks were modified.*
