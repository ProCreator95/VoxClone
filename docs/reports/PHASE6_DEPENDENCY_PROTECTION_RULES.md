# Phase 6 — DeepFilterNet Dependency Protection Rules

**Date:** 2026-06-20  
**Status:** Authoritative project policy for Phase 6  
**Branch:** `feature/audio-enhancement`  
**Phase 5 baseline:** `phase5-final` @ `ddb2366`

---

## Purpose

This document records validated dependency and architecture decisions from Phase 6
Milestone 1 and its verification audit. It governs all Phase 6 production work until
explicitly superseded by a future milestone report.

**Related reports:**

- `docs/reports/PHASE6_M1_DEEPFILTERNET_ANALYSIS.md` — feasibility and design
- `docs/reports/PHASE6_M1_VERIFICATION_AUDIT.md` — independent re-verification
- `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md` — Phase 5 ML pin rationale

---

## Rationale

Phase 5 validated a pinned CPU ML stack for Demucs source separation. Phase 6 M1
investigated integrating DeepFilterNet for speech noise removal.

**Findings (verified 2026-06-20):**

| Issue | Evidence |
|-------|----------|
| No Python 3.12 wheel for `deepfilterlib` 0.5.6 | PyPI wheel index — cp312: NONE |
| `pip install deepfilternet` fails on worker venv | Requires Rust/Cargo to build from source |
| numpy conflict | deepfilternet requires `numpy>=1.22,<2.0`; worker has `numpy==2.4.6` |
| packaging conflict | deepfilternet requires `packaging>=23.0,<24.0`; worker has `packaging==26.2` |
| Latest upstream release | PyPI/GitHub latest remains **0.5.6** (2023-08-31) |
| CLI path works | `deep-filter` 0.5.6 musl binary validated on Ubuntu 24.04 x86_64 |

Preserving the Demucs pipeline is **higher priority** than introducing DeepFilterNet
via shared Python dependencies. Subprocess isolation avoids all conflicts.

---

## Approved Architecture

All ML inference systems run as **isolated subprocesses**. No shared Python ML imports
in the Celery worker parent process.

| System | Approved integration | Python deps in worker venv |
|--------|----------------------|----------------------------|
| **Whisper** | whisper.cpp subprocess | None (GGML binary) |
| **Demucs** | `python -m demucs` subprocess | torch, torchaudio, demucs |
| **DeepFilterNet** | `deep-filter` CLI subprocess | **None** |

```
Celery worker (ai queue)
  ├── WhisperService        → whisper-cli subprocess
  ├── SourceSeparationService → demucs subprocess
  └── AudioEnhancementService   → deep-filter subprocess  (M2)
```

FFmpeg handles format conversion (e.g. resample to 48 kHz mono before DeepFilterNet).

PoC reference: `backend/tools/experiments/deepfilternet_poc.py`

---

## Dependency Protection

The validated Phase 5 ML stack is the **production baseline**. These exact versions
must be preserved during Phase 6:

```text
torch==2.8.0+cpu
torchaudio==2.8.0+cpu
demucs==4.0.1
numpy==2.4.6
packaging==26.2
```

### Prohibited changes (Phase 6)

- Upgrade or downgrade `torch` / `torchaudio`
- Change `demucs` version
- Downgrade `numpy` or `packaging` to satisfy DeepFilterNet Python metadata
- Add `deepfilternet` or `deepfilterlib` to `requirements.txt` or `requirements-ml.txt`
- Import DeepFilterNet / PyTorch enhancement code in Celery task modules at import time
- Merge DeepFilterNet into the same Python process as Demucs inference

Violations risk repeating Phase 5 Bug 8 (TorchCodec / unpinned torch regression).

---

## DeepFilterNet Installation Policy

### Required

- Ship or download the **`deep-filter` release binary** (v0.5.6 validated)
- Configure binary path via settings (e.g. `DEEP_FILTER_BINARY`) in M2
- Run enhancement via `asyncio.create_subprocess_exec` (same pattern as Demucs)

### Forbidden (unless exception process completed)

```bash
pip install deepfilternet
```

This package shall **NOT** appear in:

- `backend/requirements.txt`
- `backend/requirements-ml.txt`
- Worker setup documentation as a standard install step

---

## Future Exception Process

A proposal to use the **Python DeepFilterNet package** (shared or isolated venv) must
be documented in a **new milestone report** and include all of:

1. **Full dependency analysis** — resolver output, wheel availability, pin impact
2. **Demucs regression validation** — end-to-end `vocal_separation` + stem export self-test
3. **Torch compatibility validation** — pinned 2.8.0 pair unchanged or explicitly re-baselined
4. **Python 3.12 compatibility validation** — official wheels or approved build chain
5. **Explicit approval** — report signed off before merge; update this document

Until then, the CLI subprocess path is the only approved integration.

---

## Phase 6 Milestone 2 Scope Reminder

**Implemented (M2):**

- `AudioEnhancementService` — `deep-filter` subprocess wrapper ✅
- `audio_enhance_task` production wiring ✅
- FFmpeg 48 kHz prep ✅
- `GET /jobs/{id}/download/enhanced` ✅

**Still out of scope:**

- Modifying existing Phase 5 download endpoints or job behaviour
- Python-package DeepFilterNet integration
- `post_filter` / `source_job_id` parameters

See `docs/reports/PHASE6_M2_AUDIO_ENHANCEMENT_IMPLEMENTATION.md`.

---

*Policy effective 2026-06-20. M2 implementation complete 2026-06-20.*
