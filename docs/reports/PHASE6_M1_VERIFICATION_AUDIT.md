# Phase 6 — Milestone 1 Verification Audit

**Date:** 2026-06-20  
**Auditor scope:** Verification-only — no production code changes, no Milestone 2 implementation  
**Source report audited:** `docs/reports/PHASE6_M1_DEEPFILTERNET_ANALYSIS.md`  
**Branch:** `feature/audio-enhancement`

---

## Executive Summary

Milestone 1 findings are **substantially correct**. Re-verification on the live worker venv confirms the core blockers for installing `deepfilternet` into the shared Python 3.12 environment: **no cp312 `deepfilterlib` wheel** and **Rust not installed** on the host. Dependency metadata conflicts for **numpy** and **packaging** remain real.

The **CLI subprocess recommendation is reaffirmed** and remains the lowest-risk path for Milestone 2.

**Go / No-Go for Milestone 2:** **GO** (conditional) — proceed with `deep-filter` CLI subprocess integration only; do not add `deepfilternet` to `requirements-ml.txt`.

---

## 1. Local Environment Verification

Commands run from `backend/` with `.venv` activated (2026-06-20):

```bash
python --version
pip show numpy torch torchaudio demucs packaging
```

### Actual values

| Package | Actual version |
|---------|----------------|
| Python | **3.12.3** |
| numpy | **2.4.6** |
| torch | **2.8.0+cpu** |
| torchaudio | **2.8.0+cpu** |
| demucs | **4.0.1** |
| packaging | **26.2** |

Additional checks:

- `pip check` → **No broken requirements found**
- `rustc` → **not installed**
- `python3.11` → **not installed** on host
- ffmpeg/ffprobe → **6.1.1** (system)

### Comparison vs M1 report

| Field | M1 documented | Actual (audit) | Match? | Impact |
|-------|---------------|----------------|--------|--------|
| Python | 3.12.3 | 3.12.3 | ✅ | None |
| torch | 2.8.0+cpu | 2.8.0+cpu | ✅ | None |
| torchaudio | 2.8.0+cpu | 2.8.0+cpu | ✅ | None |
| demucs | 4.0.1 | 4.0.1 | ✅ | None |
| numpy | 2.4.6 | 2.4.6 | ✅ | None |
| packaging | "24.x (typical)" | **26.2** | ⚠️ Underspecified | **Conflict with deepfilternet `packaging<24` is confirmed and worse than M1 implied** |
| Rust toolchain | not present (implied) | **not installed** | ✅ | Blocks source build of `deepfilterlib` on 3.12 |

**Correction to M1:** Section 2 states packaging conflict as "⚠️ Possible conflict — May block pip resolver." Audit confirms **definite metadata conflict**: installed `packaging==26.2` violates `deepfilternet==0.5.6` requirement `packaging>=23.0,<24.0`.

---

## 2. DeepFilterNet Release Status

Evidence collected from PyPI JSON API and GitHub REST API (2026-06-20).

### Latest release

| Source | Version | Date | Notes |
|--------|---------|------|-------|
| **PyPI** (`deepfilternet`) | **0.5.6** | 2023-08-31 | Only version returned as `info.version` |
| **GitHub** (latest non-prerelease) | **v0.5.6** | 2023-08-31T18:33:46Z | Tag matches PyPI |

**Finding:** **No release newer than 0.5.6 exists** on PyPI or GitHub as of audit date.

Prior GitHub releases: v0.5.4 (2023-08-28), v0.5.3 (2023-06-26).

### Python 3.12 support

| Check | Evidence | Result |
|-------|----------|--------|
| PyPI classifiers | 3.8, 3.9, 3.10, 3.11 only | **No 3.12 classifier** |
| `deepfilterlib` 0.5.6 wheels | 20 wheels: cp38/cp39/cp310/cp311 | **cp312 wheels: NONE** |
| Install on Python 3.12 | `pip install deepfilternet==0.5.6` in worker venv | Falls back to **sdist build** → **Cargo/Rust required** |
| PR [#636](https://github.com/Rikorose/DeepFilterNet/pull/636) | GitHub API: `state: open`, `merged: null` | **Not merged** — no official 3.12 / numpy 2.x release |

**M1 statement confirmed:** Official packages do not support Python 3.12 via wheels.

### numpy 2.x support

PyPI `requires_dist` for `deepfilternet==0.5.6`:

```
numpy (>=1.22,<2.0)
```

**Official numpy 2.x support: NO** (hard upper bound `<2.0`).

PR #636 (open, unmerged) targets newer numpy/Python — **not published to PyPI**.

### Official release notes (v0.5.6)

GitHub release body: `"Fixes #421 and #293"` — no Python 3.12 or numpy 2.x mention.

---

## 3. Python Package Compatibility

### Install test (worker venv, unmodified torch/torchaudio/demucs)

```bash
pip install deepfilternet==0.5.6 --dry-run
pip install deepfilternet==0.5.6          # full attempt
```

**Result:** **FAILED** before any torch/numpy modification.

```
Preparing metadata (pyproject.toml) did not run successfully.
Cargo, the Rust package manager, is not installed or is not on PATH.
```

Failure occurs resolving **`deepfilterlib==0.5.6`** (no cp312 wheel → source build).

### Dependency tree (from PyPI metadata)

```
deepfilternet==0.5.6
├── appdirs>=1.4,<2.0
├── deepfilterlib==0.5.6          ← Rust extension; no cp312 wheel
├── loguru>=0.5
├── numpy>=1.22,<2.0              ← conflicts with installed 2.4.6
├── packaging>=23.0,<24.0         ← conflicts with installed 26.2
├── requests>=2.27,<3.0
└── sympy>=1.6
```

Optional extras (not installed by default): `[train]`, `[eval]`, `[soundfile]`, `[dnsmos-local]`.

### Blockers for shared worker venv install

| Blocker | Severity | Modifies torch/torchaudio/demucs? |
|---------|----------|----------------------------------|
| No cp312 `deepfilterlib` wheel | **Critical** | No — fails before install completes |
| Rust/Cargo absent | **Critical** | No |
| numpy `<2.0` vs installed `2.4.6` | **High** | Would require numpy **downgrade** if install proceeded |
| packaging `<24` vs installed `26.2` | **High** | Would require packaging **downgrade** if install proceeded |

### Supplementary isolated test (numpy downgrade + torch 2.8)

In a **separate** `/tmp` venv (not production):

```bash
pip install torch==2.8.0 torchaudio==2.8.0 demucs==4.0.1 "numpy<2"
# → numpy 1.26.4; torchaudio.save(): OK
```

**Audit finding (refines M1):** numpy downgrade to `<2` with **torch 2.8 + demucs 4.0.1 on Python 3.12 works** in isolation. M1 stated downgrade "risks Demucs regression" — this is **conservative but not verified as broken** for the pinned 2.8 stack. The **primary blockers remain wheel/Rust**, not proven torch breakage.

**Verdict:** **Cannot install `deepfilternet` in the current worker venv without modifying the environment** — install never reaches numpy/packaging resolution because `deepfilterlib` build fails first. Even with Rust, pip would still need to reconcile numpy and packaging downgrades.

---

## 4. CLI Recommendation Re-evaluation

### A. `deep-filter` CLI subprocess

| Dimension | Assessment |
|-----------|------------|
| **Advantages** | Zero Python ML deps; no torch/numpy coupling; validated on Ubuntu 24.04 x86_64; ~122 MB RSS; mirrors Demucs subprocess pattern; models bundled in binary |
| **Disadvantages** | 48 kHz WAV only (FFmpeg prep required); x86_64 musl binary only in PoC (no aarch64 path); limited runtime configurability vs Python API; binary download/version management |
| **Operational complexity** | **Low** — ship or download static binary + ffmpeg |
| **Risk to Phase 5 baseline** | **Minimal** — no shared venv changes |

### B. Python package in shared worker venv

| Dimension | Assessment |
|-----------|------------|
| **Advantages** | Native Python API; easier unit testing; `deepFilter` CLI entry point after install |
| **Disadvantages** | **Blocked on Python 3.12** (no wheel + no Rust); numpy/packaging conflicts; loads PyTorch in worker ecosystem; higher RAM |
| **Operational complexity** | **High** — resolver conflicts, build toolchain, regression risk |
| **Risk to Phase 5 baseline** | **High** — shared dependency graph with Demucs |

### C. Dedicated isolated enhancement venv

| Dimension | Assessment |
|-----------|------------|
| **Advantages** | Could use Python 3.11 wheels (cp311 `deepfilterlib` exists); isolates numpy/packaging pins from Demucs venv |
| **Disadvantages** | Second venv to maintain; Python 3.11 **not installed** on current host; subprocess indirection still required; ops overhead |
| **Operational complexity** | **Medium–High** |
| **Risk to Phase 5 baseline** | **Low** if truly isolated subprocess |

### Final recommendation

**Unchanged: Approach A (`deep-filter` CLI subprocess) remains preferred for Milestone 2.**

Approach C is a documented fallback only if CLI capabilities prove insufficient. Approach B remains **not viable** on the current host without Rust toolchain + dependency downgrades + successful `deepfilterlib` build.

Audit re-verification: `deep-filter` binary executes (`deep_filter 0.5.6`).

---

## 5. Enhancement Suitability by Content Type

DeepFilterNet is a **speech enhancement** model (full-band 48 kHz). Recommendations based on upstream design, M1 PoC behaviour, and project pipeline context.

| Content type | Expected quality | Risks | Recommendation |
|--------------|------------------|-------|----------------|
| **Noisy speech** | Strong noise reduction; primary design target | Over-attenuation if already clean; clipping on hot signals (PoC: `Possible clipping detected`) | **Recommended** — default use case |
| **Voice-over recordings** | Good — similar to speech | Same clipping/post-filter artefacts | **Recommended** |
| **Podcasts** | Good for voice; music jingles may be altered | Intro/outro music treated as noise | **Recommended with caution** — document scope |
| **Meetings / multi-speaker** | Good for stationary noise | Crosstalk not separated; non-stationary interference | **Recommended** for noise; not for diarization |
| **Vocals stems** (post-Demucs) | Variable — isolated singing ≠ clean speech | Musical pitch content may be suppressed; consonants may sound processed | **Conditional** — speech-heavy vocals only; not default for music |
| **Instrumental stems** | Poor fit | Model targets speech; will damage musical timbre | **Not recommended** |
| **Mixed music** | Poor to moderate | PoC on music-heavy extract produced clipping warnings | **Not recommended** as default |
| **Karaoke tracks** | Poor fit | Designed to remove non-speech; backing track is "noise" to the model | **Not recommended** |

**M1 suitability section: confirmed.** No correction required beyond emphasising that **vocals stems from Demucs are not automatically safe** — suitability depends on whether the stem is speech-dominant.

---

## 6. PoC Implementation Review

**File:** `backend/tools/experiments/deepfilternet_poc.py`

### Validated behaviours

| Area | Status | Notes |
|------|--------|-------|
| Binary download logic | ✅ Works | Downloads v0.5.6 musl binary on first run |
| ffmpeg/ffprobe usage | ✅ Works | Resamples non-48 kHz to 48 kHz mono |
| Enhancement execution | ✅ Works | Exit 0; output WAV written |
| Diagnostics | ✅ Works | Prints elapsed time, RTF, byte size, metadata |
| Isolation from VoxClone | ✅ | No app imports; no worker venv mutation |

### Issues / improvements before M2

| Issue | Severity | Detail |
|-------|----------|--------|
| **Hardcoded x86_64 musl URL** | Medium | No `platform.machine()` detection; fails on aarch64 hosts |
| **No download integrity check** | Medium | No SHA256/size verification of release binary |
| **No download timeout** | Low | `urlretrieve` can hang on bad networks |
| **Temp cleanup incomplete on failure** | Low | `.tmp/` not removed if `deep-filter` fails after resample |
| **Output naming** | Medium | Enhanced file keeps resampled temp basename (`*_48k_mono.wav`), not stable `{job_id}_enhanced.wav` — acceptable for PoC; **M2 service must use job-scoped names** |
| **Error messages** | Low | ffmpeg/ffprobe failures raise `CalledProcessError` without surfacing stderr |
| **`_probe_wav` assumes `streams[0]`** | Low | Multi-stream containers may probe wrong stream |
| **RTF variability** | Info | M1 cited RTF **0.79**; script re-run measured **1.31** on same clip — load-dependent; M2 should not hard-code RTF |

### Production readiness

**PoC is fit for purpose as an experiment.** It is **not** production-ready as-is. M2 should implement patterns in `AudioEnhancementService` (configurable binary path, checksum optional, job-scoped paths, stderr capture, `safe_delete` on all paths).

---

## 7. Corrections Required in M1 Report

| M1 statement | Audit verdict | Corrected version |
|--------------|---------------|-------------------|
| packaging conflict "⚠️ Possible" | **Understated** | **Definite conflict:** installed `packaging==26.2` vs required `<24.0` |
| numpy downgrade "risks Demucs regression" | **Conservative** | Primary blocker is wheel/Rust; isolated test shows **torch 2.8 + demucs 4.0.1 + numpy 1.26.4 works** on Python 3.12 — downgrade risk is **unproven for pinned stack**, but still undesirable in shared venv |
| RTF **0.79** as single benchmark | **Incomplete** | Report **range 0.8–1.3 RTF** on same hardware/input under load variation; use for estimates, not SLA |
| PoC script test RTF **1.31** | **Missing from M1** | Second validated run: 216.5 s audio, 282.8 s wall, RTF 1.31 |
| "gitignored recommended" for output | **Not implemented** | No `.gitignore` entry for `tools/experiments/output/` or `bin/` — add in M2 or ops doc |

All other major M1 claims **confirmed** by this audit.

---

## 8. Updated Recommendations

1. **Milestone 2:** Implement `AudioEnhancementService` using **`deep-filter` CLI subprocess** — unchanged from M1.
2. **Do not** add `deepfilternet` to `requirements-ml.txt` on Python 3.12.
3. **Do not** upgrade torch/torchaudio — Phase 5 pin is authoritative.
4. **Document job scope:** speech/noise use cases only; warn against music/karaoke/instrumental inputs.
5. **M2 PoC → service gaps:** platform-aware binary selection, stderr tail in errors, job-scoped output paths, temp dir cleanup on failure, optional binary checksum.
6. **Runtime planning:** assume **~0.8–1.3× realtime** on one CPU core until M2 benchmarks on target hardware.
7. **Optional later:** isolated Python 3.11 venv only if CLI lacks required flags — not needed for initial M2.

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Shared venv dependency collision | High (if Python path chosen) | High | Use CLI subprocess |
| Demucs regression from numpy/packaging churn | Medium (if Python path) | Critical | Keep ML stacks separate |
| Non-speech content quality loss | High (user error) | Medium | API docs + validation warnings |
| Long file job timeout | Medium | Medium | Progress updates in M2; concurrency=1 |
| aarch64 deployment | Medium (wrong binary) | High | Platform detection in M2 service |
| Stale DeepFilterNet upstream (last release Aug 2023) | Known | Low | Accept for speech NR; monitor upstream |

---

## 10. Go / No-Go for Milestone 2

| Criterion | Result |
|-----------|--------|
| M1 findings accurate? | **Yes** — with minor corrections above |
| CLI path validated on target OS? | **Yes** |
| Python package viable in shared venv? | **No** |
| Phase 5 baseline protectable? | **Yes** — via subprocess isolation |
| PoC sufficient to proceed? | **Yes** — with documented M2 hardening items |

### Decision

**GO for Phase 6 Milestone 2**

Proceed with production design implementation using the **`deep-filter` CLI subprocess** pattern. Do not begin M2 with `pip install deepfilternet` into the worker venv.

---

## Appendix — Evidence Log

| Check | Command / source | Timestamp |
|-------|------------------|-----------|
| Worker versions | `pip show numpy torch torchaudio demucs packaging` | 2026-06-20 |
| PyPI latest | `https://pypi.org/pypi/deepfilternet/json` | 2026-06-20 |
| GitHub releases | `api.github.com/.../releases?per_page=5` | 2026-06-20 |
| PR #636 status | `api.github.com/.../pulls/636` → open, not merged | 2026-06-20 |
| cp312 wheels | PyPI `deepfilterlib/0.5.6/json` → NONE | 2026-06-20 |
| Install failure | `pip install deepfilternet==0.5.6` in worker venv | 2026-06-20 |
| numpy downgrade test | Isolated `/tmp/voxclone-numpy-test` venv | 2026-06-20 |
| CLI binary | `tools/experiments/bin/deep-filter --version` → 0.5.6 | 2026-06-20 |
| PoC script run | `deepfilternet_poc.py` → exit 0, RTF 1.31 | 2026-06-20 |

---

*Audit complete. No production code modified. Milestone 2 not started.*
