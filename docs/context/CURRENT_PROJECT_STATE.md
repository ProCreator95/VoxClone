# VoxClone — Current Project State

**Date:** 2026-06-18
**Branch:** `feature/source-separation` (pushed to `origin/feature/source-separation`)
**Last commit:** `ddb2366 Phase 5 Milestone 4: stem reuse and reusable karaoke outputs`
**Tags:** `v0.1-foundation` · `phase2-subtitles-working` · `phase3-subtitle-burn` · `phase4-karaoke-generation` · `phase5-source-separation` · `phase5-complete` · `phase5-final`

---

## Environment

| Item | Value |
|------|-------|
| OS | Ubuntu 24.04.2 LTS |
| Python | 3.12.3 |
| Virtual env | `backend/.venv/` |
| Redis | `redis://localhost:6379/0` (default port) |
| SQLite DB | `backend/voxclone.db` |
| FFmpeg | 6.1.1 (system package, `/usr/bin/ffmpeg`) |
| whisper-cli | `tools/whisper.cpp/build/bin/whisper-cli` |
| Whisper models dir | `backend/models/` |
| ML stack (worker) | `torch 2.8.0+cpu`, `torchaudio 2.8.0+cpu`, `demucs 4.0.1` — see `requirements-ml.txt` |

### Whisper Models Present

```
backend/models/ggml-tiny.en.bin     75 MB   (subtitle_generation default)
backend/models/ggml-base.en.bin    142 MB   (karaoke default)
backend/models/ggml-small.en.bin   466 MB
```

### Active `.env` Settings (representative)

```
WHISPER_CPP_BINARY=../tools/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin
WHISPER_THREADS=8
WHISPER_LANGUAGE=en
DEMUCS_MODEL=htdemucs
DEMUCS_DEVICE=cpu
SEPARATION_SAMPLE_RATE=44100
SEPARATION_CHANNELS=2
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
DATABASE_URL=sqlite+aiosqlite:///./voxclone.db
```

---

## Repository Structure

```
VoxClone/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py
│   │   │   ├── uploads.py
│   │   │   ├── media.py
│   │   │   └── jobs.py              All job + download endpoints (Phase 5 stems)
│   │   ├── core/                    config, exceptions, logging
│   │   ├── database/                async SQLAlchemy session + init_db
│   │   ├── models/
│   │   │   ├── media.py
│   │   │   ├── job.py               JobType includes vocal_separation
│   │   │   └── stem_metadata.py     canonical vs inline stem ownership
│   │   ├── schemas/job.py           whisper_model, separation_model, output_mode validation
│   │   ├── services/
│   │   │   ├── ffmpeg_service.py    probe, extract, burn, extract_stereo_wav, transcode
│   │   │   ├── job_service.py       lifecycle + Redis progress
│   │   │   ├── redis_service.py     async Redis singleton
│   │   │   ├── source_separation_service.py   Demucs subprocess wrapper
│   │   │   ├── separation_models.py htdemucs whitelist
│   │   │   ├── karaoke_modes.py     karaoke output_mode validation (4 modes)
│   │   │   ├── stem_reuse.py        canonical stem reuse for karaoke
│   │   │   ├── whisper_models.py    per-job whisper model resolution
│   │   │   ├── whisper_service.py   whisper.cpp subprocess
│   │   │   └── upload_service.py
│   │   ├── tasks/
│   │   │   ├── async_runner.py      persistent worker event loop + run_async()
│   │   │   ├── celery_app.py        Celery config + worker_process_init
│   │   │   └── media_tasks.py       All Celery tasks (Phases 1–5)
│   │   └── main.py
│   ├── processed/                   Pipeline outputs + .demucs_tmp/
│   ├── models/                      GGML whisper models
│   ├── requirements.txt
│   ├── requirements-ml.txt          Pinned torch/torchaudio/demucs (worker only)
│   └── .env.example
├── docs/
│   ├── context/
│   ├── reports/                     Phase 5 milestone + dependency reports
│   └── testing/
└── tools/whisper.cpp/
```

---

## Component Status

### Phase 1 — Foundation ✅ COMPLETE

Upload, media CRUD, job creation/dispatch, Redis progress, Celery routing, download endpoints.

### Phase 2 — Subtitle Generation ✅ COMPLETE

`WhisperService`, `generate_subtitles_task`, SRT/VTT/TXT outputs, subtitle download endpoints.

### Phase 3 — Subtitle Burn-In ✅ COMPLETE

`burn_subtitles_task`, `FFmpegService.burn_subtitles()`, `GET /jobs/{id}/download/video`.

### Phase 4 — Karaoke Generation ✅ COMPLETE

Word-level ASS karaoke via whisper.cpp `--output-json-full`, `karaoke_task` (default `karaoke_video_with_vocals`), `/download/ass`, `/download/karaoke-video`.

Tag: `phase4-karaoke-generation` · Commit: `47be178`

### Phase 5 — Source Separation & Vocal Removal ✅ COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| `whisper_models.py` | ✅ | Per-job `whisper_model`: `tiny` \| `base` \| `small`; defaults by job type |
| `vocal_separation` job type | ✅ | Canonical stem owner (`stem_origin: canonical`) |
| `SourceSeparationService` | ✅ | Demucs subprocess; maps `no_vocals.wav` → `instrumental.wav` |
| `separation_models.py` | ✅ | Whitelist: `htdemucs` only |
| `stem_metadata.py` | ✅ | `canonical` vs `inline` ownership helpers |
| `stem_reuse.py` | ✅ | `resolve_canonical_stems()` — validate + load reusable stems |
| `karaoke_modes.py` | ✅ | All 4 output modes: video + stem-only |
| `karaoke` inline Demucs | ✅ | `karaoke_video_no_vocals` without reuse → `stem_origin: inline` |
| `separation_job_id` reuse | ✅ | Skips Demucs; `stem_origin: canonical` on karaoke job |
| `music_only` / `vocals_only` | ✅ | WAV-only output; no Whisper/video |
| `async_runner.py` | ✅ | Persistent worker event loop; fixes Redis loop mismatch |
| `GET /jobs/{id}/download/vocals` | ✅ | vocal_separation + inline/reused karaoke |
| `GET /jobs/{id}/download/instrumental` | ✅ | vocal_separation + inline/reused karaoke |
| `requirements-ml.txt` | ✅ | `torch==2.8.0`, `torchaudio==2.8.0`, `demucs==4.0.1` |
| Demucs dependency validation | ✅ | Manual + self-test passed (see Phase 5 reports) |

**Worker ML install:**

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-ml.txt
```

See `docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` for self-test commands.

Tag: `phase5-final` · Commit: `ddb2366` (also `phase5-complete` at same commit; `phase5-source-separation` at `c0f67c5` for M1–M3 baseline)

**Celery note:** Use `--concurrency=1` on hosts running Demucs when OOM is observed (`PHASE5_STEM_OWNERSHIP_AND_OPS.md`).

### Placeholder / Not Implemented

| job_type | API | Runtime |
|----------|-----|---------|
| `audio_enhance` | ✅ accepts job | ❌ marks failed — DeepFilterNet not implemented |
| `voice_replacement` | ❌ HTTP 422 | — |
| `voice_clone` | ❌ HTTP 422 | — |

---

## Bugs Fixed Across Phases 2–5

| # | Bug | Fixed in |
|---|-----|---------|
| 1 | Redis not connected in Celery workers | `celery_app.py` — `worker_process_init` |
| 2 | `MissingGreenlet` on `job.media` | `job_service.py` — `get_by_id_with_media()` |
| 3 | `libwhisper.so.1 not found` | `whisper_service.py` — `_build_subprocess_env()` |
| 4 | FFmpeg filter path not escaped | `ffmpeg_service.py` — `_escape_filter_path()` |
| 5 | No explicit video codec in burn | `ffmpeg_service.py` — `-c:v libx264` |
| 6 | `/download/video` route shadowed | `jobs.py` — literal routes before catch-all |
| 7 | Unimplemented job types returned HTTP 500 | `IMPLEMENTED_JOB_TYPES` pre-flight → 422 |
| 8 | Demucs WAV save — TorchCodec / unpinned torch | `requirements-ml.txt` — pin torch 2.8.0 pair |
| 9 | Redis `Future attached to a different loop` | `async_runner.py` + `run_async()` in tasks |

See `KNOWN_BUGS_AND_ROOT_CAUSES.md` for full write-ups.

---

## Phase 5 Validation Evidence

### Demucs dependency matrix (2026-06-18)

| Check | Result |
|-------|--------|
| Ubuntu 24.04 + Python 3.12 wheels | ✅ `torch-2.8.0+cpu`, `torchaudio-2.8.0+cpu` |
| `torchaudio.save()` self-test | ✅ |
| Manual Demucs two-stem run | ✅ `vocals.wav` + `no_vocals.wav` written |
| TorchCodec errors | ✅ None (torchcodec not installed) |

Report: `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md`

### Async event loop fix

Celery tasks now use `run_async()` on a single persistent loop shared with `worker_process_init` Redis connect. Prevents `mark_started()` → `set_progress()` loop mismatch.

### Milestone 4 — stem reuse (2026-06-20)

| Test | Result |
|------|--------|
| A — vocal_separation stems | ✅ `2ed4465c-...` vocals + instrumental on disk |
| B — `music_only` + `separation_job_id` | ✅ Demucs skipped, canonical instrumental reused |
| C — `vocals_only` + `separation_job_id` | ✅ Canonical vocals reused |
| D — `karaoke_video_no_vocals` + reuse | ✅ Video generated, no second Demucs run |

Report: `docs/reports/PHASE5_MILESTONE4_STEM_REUSE.md`

---

## Git State

**Branch:** `feature/source-separation` — synced with `origin/feature/source-separation`
**Working tree:** clean (Phase 5 committed and tagged)

### Commit log

```
ddb2366  Phase 5 Milestone 4: stem reuse and reusable karaoke outputs   ← HEAD, phase5-complete, phase5-final
fe6b264  Docs: align project documentation with Phase 5 state
c0f67c5  Phase 5: source separation, karaoke modes, and ML worker infrastructure   ← phase5-source-separation
47be178  Phase 4: karaoke generation complete   ← phase4-karaoke-generation
cd7133b  Phase 3: subtitle burn-in complete
2f9f643  Phase 3: subtitle burn-in complete
19f8cc8  Finalize Phase 2 documentation and handoff
94f77e0  Phase 2 subtitle generation complete
52c5d3e  Phase 1 foundation validated   ← v0.1-foundation
```

### Tags

```
v0.1-foundation              @ 52c5d3e
phase2-subtitles-working     @ 94f77e0
phase3-subtitle-burn         @ 2f9f643
phase4-karaoke-generation    @ 47be178
phase5-source-separation     @ c0f67c5   (M1–M3 + ML infrastructure)
phase5-complete              @ ddb2366   (full Phase 5 including M4)
phase5-final                 @ ddb2366   (validated Phase 5 complete)
```
