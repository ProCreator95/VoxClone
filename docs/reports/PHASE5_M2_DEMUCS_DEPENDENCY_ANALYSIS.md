# Phase 5 Milestone 2 — Demucs Dependency Root Cause & Fix

**Status:** Validated — dependency pin confirmed on Ubuntu 24.04 / Python 3.12
**Date:** 2026-06-18
**Scope:** `vocal_separation` / Demucs subprocess save failure (not separation logic)

---

## Executive summary

Demucs completes inference (~100%) then crashes while writing stem WAV files. This is a **PyTorch/TorchAudio packaging regression**, not a VoxClone separation bug.

| Symptom | Cause |
|---------|-------|
| `ImportError: TorchCodec is required for save_with_torchcodec` | TorchAudio ≥2.9 routes `torchaudio.save()` through TorchCodec |
| `RuntimeError: Could not load libtorchcodec` | TorchCodec wheel mismatch (torch/torchaudio versions) or broken CPU wheel linkage |

**Fix:** Pin **matched, pre-TorchCodec** `torch` + `torchaudio` wheels. Do **not** install latest PyTorch on the worker without pins.

---

## Root cause (verified in project venv)

Reproduced on the current worker venv:

```
torch       2.12.1+cpu
torchaudio  2.11.0+cpu   ← mismatched pair; latest unpinned install
```

Minimal save test (same path Demucs uses):

```python
torchaudio.save("test.wav", tensor, 44100, encoding="PCM_S", bits_per_sample=16)
# → RuntimeError: Could not load libtorchcodec
```

Demucs 4.0.1 calls this from `demucs/audio.py`:

```python
ta.save(str(path), wav, sample_rate=samplerate,
        encoding=encoding, bits_per_sample=bits_per_sample)
```

Separation succeeds; only the **save** step fails.

### Why unpinned install breaks

1. Phase 5 docs said `pip install torch torchaudio --index-url …/cpu` with **no version pins**.
2. TorchAudio **2.9+** deprecated legacy backends; `save()` now requires TorchCodec ([PyTorch Audio PR #4039](https://github.com/pytorch/audio/pull/4039)).
3. TorchCodec is **not** a declared dependency of TorchAudio; wheels must be manually matched ([torchcodec compatibility table](https://github.com/pytorch/torchcodec#installing-torchcodec)).
4. On CPU-only Ubuntu 24.04 + Python 3.12, mismatched or bleeding-edge wheels fail to load native libs (observed: `libnvrtc.so.13` errors inside torchcodec despite CPU install).

---

## Phase 5 dependency strategy review

### What worked (Phase 1–4)

- **Whisper:** whisper.cpp binary — no Python ML stack, no version coupling.
- **FFmpeg:** system binary, stable across Ubuntu LTS.

### What was under-specified (Phase 5)

| Gap | Risk |
|-----|------|
| `requirements-ml.txt` only listed `demucs>=4.0.1` | Worker gets whatever torch pip resolves |
| Install docs: “latest CPU torch” | Pulls TorchAudio ≥2.9 → TorchCodec path |
| No ML self-test | Save failure only appears after full Demucs run (~minutes) |
| `SourceSeparationService` drops stderr from job record | Operators see generic failure message |

### Revised strategy

1. **Pin a tested matrix** in `requirements-ml.txt` (torch, torchaudio, demucs exact versions).
2. **Document ordered install** (torch pair first, then demucs extras).
3. **Ship a one-command self-test** that includes `torchaudio.save()` smoke test.
4. **Persist Demucs stderr** in `mark_failed()` messages (≤4 KB tail).
5. **Do not adopt TorchCodec** for VoxClone CPU deployments until upstream packaging stabilizes.
6. **Optional defense-in-depth** (future): Demucs `--mp3` + FFmpeg transcode to WAV — avoids `torchaudio.save()` entirely.

---

## Supported version matrix

### VoxClone-validated production pair (recommended)

| Package | Version | Notes |
|---------|---------|-------|
| **Python** | 3.12.x | Ubuntu 24.04 default; backend requires 3.11+ |
| **torch** | `2.8.0` | Last stable line before TorchCodec-default save |
| **torchaudio** | `2.8.0` | Must match torch major.minor exactly |
| **demucs** | `4.0.1` | Only PyPI release; uses `ta.save()` for WAV |
| **lameenc** | `≥1.2` | Demucs MP3 path (no torchaudio save) |
| **soundfile** | `≥0.12` | Optional; improves torchaudio backend selection |

Install:

```bash
pip install -r requirements-ml.txt
```

### Alternative (Python 3.11 workers only)

| torch | torchaudio | demucs |
|-------|------------|--------|
| 2.5.1 | 2.5.1 | 4.0.1 |

PyTorch 2.5.x officially supports Python ≤3.11. Use on 3.11 venvs if 2.8.0 wheels are unavailable.

### Versions to avoid (VoxClone CPU)

| Combination | Why |
|-------------|-----|
| torch ≥2.9 + torchaudio ≥2.9 | TorchCodec required for save/load |
| torch 2.12.x + torchaudio 2.11.x | Mismatched pair from unpinned install |
| torchcodec as manual add-on | Fragile; CPU wheel linkage issues on Ubuntu |
| `demucs` git HEAD / unpinned | Unpredictable against torch stack |

---

## Task 6 — Avoid torchaudio save?

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Pin torchaudio ≤2.8** | No code change; Demucs writes WAV natively | Must maintain pins | **Primary fix** |
| **Demucs `--mp3` + FFmpeg → WAV** | Bypasses `ta.save()` (uses lameenc) | Extra transcode step; lossy intermediate | Fallback if pins fail |
| **Demucs `--flac`** | Smaller files | Still uses `ta.save()` | Does not help |
| **Patch Demucs to use soundfile** | Direct control | Fork maintenance burden | Not recommended |
| **Adopt TorchCodec stack** | “Latest” torch | Broken on CPU Ubuntu today | Defer |

**Conclusion:** Pin versions first. Add `--mp3` + FFmpeg post-process only as a documented fallback, not default.

Fallback sketch (not implemented):

```bash
# demucs with MP3 output (lameenc, no torchaudio.save)
python -m demucs --mp3 --two-stems vocals …
ffmpeg -i vocals.mp3 -ar 44100 -ac 2 processed/{job_id}_vocals.wav
```

---

## Task 4 — ML self-test (run after install)

```bash
cd backend && source .venv/bin/activate

python - <<'EOF'
import torch
import torchaudio
import demucs

print("torch", torch.__version__)
print("torchaudio", torchaudio.__version__)
print("demucs", demucs.__version__)

# Smoke test: same API Demucs uses for WAV export
wav = torch.zeros(2, 4410)
torchaudio.save(
    "/tmp/voxclone_ml_selftest.wav",
    wav,
    44100,
    encoding="PCM_S",
    bits_per_sample=16,
)
print("torchaudio.save: OK")
EOF

python -m demucs --help >/dev/null && echo "demucs CLI: OK"
```

Expected: all imports succeed, `torchaudio.save: OK`, `demucs CLI: OK`.

If save fails, verify pins:

```bash
pip show torch torchaudio demucs | grep -E '^(Name|Version):'
# torch        2.8.0
# torchaudio   2.8.0
# demucs       4.0.1
```

---

## Task 5 — SourceSeparationService diagnostics (proposed)

**Current:** stderr logged server-side only; job `error_message` is generic.

**Proposed:** Include stderr tail in `SourceSeparationError` so `mark_failed()` persists it:

```python
stderr_text = stderr.decode(errors="replace").strip()
tail = stderr_text[-4000:] if stderr_text else "(no stderr)"
raise SourceSeparationError(
    f"Demucs separation failed (exit code {process.returncode}).\n\n{tail}"
)
```

Also extend `validate()` install hint to reference pinned versions and self-test doc.

---

## Ubuntu 24.04 CPU-only production matrix

| Layer | Component | Version / value |
|-------|-----------|-----------------|
| OS | Ubuntu | 24.04 LTS |
| Python | venv | 3.12.x |
| System | ffmpeg | distro package (`sudo apt install ffmpeg`) |
| System | libsox-dev | optional (`sudo apt install libsox-dev`) |
| PyTorch | torch | `2.8.0+cpu` |
| PyTorch | torchaudio | `2.8.0+cpu` |
| Separation | demucs | `4.0.1` |
| Separation | lameenc | `≥1.2` (transitive) |
| Worker | Celery concurrency | `1` when Demucs enabled |
| Worker | Queue | `ai` |
| Model | htdemucs weights | ~80–200 MB, cached on first run |
| RAM | per separation job | ~4–8 GB CPU (track length dependent) |

**Explicit exclusions:** `torchcodec`, unpinned `torch`/`torchaudio`, CUDA wheels on CPU-only hosts.

---

## Remediation checklist

- [ ] Uninstall broken stack: `pip uninstall -y torch torchaudio torchcodec demucs`
- [ ] Install pinned CPU pair (see above)
- [ ] `pip install -r requirements-ml.txt`
- [ ] Run ML self-test
- [ ] Re-run manual Demucs: `python -m demucs --two-stems vocals processed/<job_id>_separation_input.wav`
- [ ] Re-run `vocal_separation` job end-to-end
- [ ] Apply stderr persistence patch (Task 5) before next production deploy

---

## Files to update (this proposal)

| File | Change |
|------|--------|
| `backend/requirements-ml.txt` | Pin torch/torchaudio/demucs + notes |
| `backend/requirements.txt` | Point to pinned ML install |
| `docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` | Setup + self-test |
| `docs/reports/PHASE5_STEM_OWNERSHIP_AND_OPS.md` | ML deps pointer |
| `backend/app/services/source_separation_service.py` | Stderr in failure message (Task 5) |

**Not in scope:** Milestone 3 features, TorchCodec adoption, Demucs fork.
