# VoxClone — Project Snapshot

**Date:** 2026-06-24 (updated)  
**Purpose:** Standalone context document for starting new ChatGPT or Cursor sessions without prior chat history.  
**Audience:** Developers, AI assistants, and stakeholders resuming work on VoxClone.

---

## 1. Executive Summary

**VoxClone** is an offline-first AI media processing platform. Users upload video or audio, submit processing jobs via a REST API, and download results. All AI models run locally — no cloud API keys required for core pipelines.

**Current maturity:** Phases 1–8 are complete. **Phase 9 Flutter Frontend MVP** is in progress (M1 shell + UI refactor on `feature/flutter-frontend-mvp`). Branch: `feature/flutter-frontend-mvp`.

**Business objective:** Launch a commercially viable MVP as quickly as possible and validate demand before investing in GPU infrastructure, voice cloning production, or advanced multilingual features.

**Infrastructure decision:** **Hetzner VPS** selected (initial: 4 vCPU / 8 GB RAM; future: 8 vCPU / 16 GB RAM) — **deployment deferred to Phase 14**. Retain current stack — **no Cloud Run, no serverless, no Kubernetes, no architecture rewrite.**

**Database:** **SQLite acceptable for MVP launch.** PostgreSQL deferred until proven growth.

**Recommended next work:** **Phase 9 — Flutter Frontend MVP** (see approved roadmap below).

---

## 2. Current Repository State

### Environment

| Item | Value |
|------|-------|
| OS | Ubuntu 24.04.2 LTS |
| Python | 3.12.3 |
| Virtual env | `backend/.venv/` |
| Redis | `redis://localhost:6379/0` |
| SQLite DB | `backend/voxclone.db` |
| FFmpeg | 6.1.1 (system, `/usr/bin/ffmpeg`) |
| whisper-cli | `tools/whisper.cpp/build/bin/whisper-cli` |
| Whisper models | `backend/models/` |
| ML stack (Celery worker) | `torch 2.8.0+cpu`, `torchaudio 2.8.0+cpu`, `demucs 4.0.1`, `numpy 2.4.6`, `packaging 26.2` |
| Audio enhancement | `deep-filter` CLI 0.5.6 subprocess — **not** in Python requirements |

### Repository layout (high level)

```
VoxClone/
├── backend/           FastAPI app, Celery tasks, services, models, tests
├── frontend/          Flutter mobile client (Phase 9)
├── docs/
│   ├── context/       Project state and handoff docs (this file lives here)
│   ├── reports/       Phase completion and validation reports
│   └── testing/       Setup guides (e.g. WHISPER_CPP_SETUP.md)
└── tools/whisper.cpp/ Built whisper.cpp binary and shared libraries
```

### Implemented job types

| job_type | Status |
|----------|--------|
| `audio_extraction` | ✅ |
| `subtitle_generation` | ✅ |
| `subtitle_burn` | ✅ |
| `karaoke` | ✅ (4 output modes) |
| `vocal_separation` | ✅ |
| `audio_enhance` | ✅ |
| `voice_replacement` | ❌ HTTP 422 |
| `voice_clone` | ❌ HTTP 422 |

### Key documentation index

| Document | Role |
|----------|------|
| `docs/context/PROJECT_SNAPSHOT_2026_06_22.md` | Authoritative snapshot for new sessions (business + technical state) |
| `docs/context/NEXT_SESSION_START_HERE.md` | Quick entry point for next dev session |
| `docs/context/CURRENT_PROJECT_STATE.md` | Detailed component status |
| `docs/context/MASTER_PROJECT_HANDOFF.md` | Full self-contained developer handoff |
| `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md` | Fixed bugs + known limitations |
| `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` | Whisper production defaults |
| `docs/reports/PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md` | Voice cloning engine evaluation |

---

## 3. Current Branch Status

**Active branch:** `feature/flutter-frontend-mvp`  
**Remote:** See `git status` for sync state with origin.

**Recent commit history (main line):**

```
Phase 9 M1: Flutter premium UI shell (frontend/)
Phase 8: Voice cloning feasibility study
Phase 7 M3: Whisper commercial benchmark
149dc96 Phase 6 Milestone 2: DeepFilterNet audio enhancement via CLI subprocess
```

**Phase tags:** `v0.1-foundation` · `phase2-subtitles-working` · `phase3-subtitle-burn` · `phase4-karaoke-generation` · `phase5-source-separation` · `phase5-complete` · `phase5-final`

**Other branches (feature history):**

| Branch | Phase |
|--------|-------|
| `feature/flutter-frontend-mvp` | Phase 9 (current) |
| `feature/whisper-multilingual` | Phase 7 |
| `feature/subtitle-pipeline` | Phase 2 |
| `feature/subtitle-burn` | Phase 3 |
| `feature/karaoke-generation` | Phase 4 |
| `feature/source-separation` | Phase 5 |
| `feature/audio-enhancement` | Phase 6 |
| `main` | Stable baseline |

**Working tree:** See `git status` for the authoritative list.

---

## 4. Completed Phases

| Phase | Name | Status | Tag / baseline |
|-------|------|--------|----------------|
| 1 | Backend Foundation | ✅ Complete | `v0.1-foundation` |
| 2 | Subtitle Generation | ✅ Complete | `phase2-subtitles-working` |
| 3 | Subtitle Burn-In | ✅ Complete | `phase3-subtitle-burn` |
| 4 | Karaoke Generation | ✅ Complete | `phase4-karaoke-generation` |
| 5 | Source Separation & Vocal Removal | ✅ Complete | `phase5-final` @ `ddb2366` |
| 6 | Audio Enhancement (DeepFilterNet) | ✅ M2 Complete | `feature/audio-enhancement` |
| 7 | Multilingual Whisper Routing | ✅ M2 Complete + validated | `feature/whisper-multilingual` |
| 7 M3 | Whisper Commercial Benchmark | ✅ Complete | `PHASE7_M3_WHISPER_BENCHMARK_REPORT.md` |
| 8 | Voice Cloning Feasibility | ✅ Complete (study only) | `PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md` |

### Phase summaries

**Phase 1:** Upload, media CRUD, job dispatch, Redis progress, Celery routing, SQLite persistence.

**Phase 2:** `WhisperService` (whisper.cpp subprocess), SRT/VTT/TXT outputs, subtitle download endpoints.

**Phase 3:** FFmpeg H.264 subtitle burn-in, `GET /jobs/{id}/download/video`.

**Phase 4:** Word-level ASS karaoke via `--output-json-full`, karaoke MP4 download.

**Phase 5:** Demucs vocal separation, four karaoke output modes, canonical stem reuse via `separation_job_id`, pinned ML stack in `requirements-ml.txt`.

**Phase 6:** `AudioEnhancementService` via `deep-filter` CLI subprocess; FFmpeg 48 kHz prep; `GET /jobs/{id}/download/enhanced`. Phase 5 ML pins preserved — DeepFilterNet not added to Python requirements.

**Phase 7 M2:** Language-first Whisper model routing — English → `.en.bin` + `-l en`; non-English / `auto` → `.bin` multilingual models. Validated manually for Urdu.

---

## 5. Active Features

All features below are implemented and available via `POST /api/v1/jobs`.

### Subtitle generation

- whisper.cpp transcription → `.txt`, `.srt`, `.vtt`
- Per-job `whisper_model`: `tiny` | `base` | `small`
- Per-job `language`: BCP-47 code or `"auto"` (Phase 7)

### Subtitle burn-in

- Hardcode SRT into video (H.264 MP4)
- Primary workflow: `subtitle_job_id` references prior subtitle job

### Karaoke

- Word-level ASS highlighting burned into MP4
- Output modes: `karaoke_video_with_vocals`, `karaoke_video_no_vocals`, `vocals_only`, `music_only`
- Optional `separation_job_id` to reuse canonical Demucs stems

### Vocal separation

- Demucs `htdemucs` (CPU) → vocals + instrumental WAV stems
- Download: `/download/vocals`, `/download/instrumental`

### Audio enhancement

- FFmpeg 48 kHz mono prep → `deep-filter` CLI → enhanced WAV
- Download: `/download/enhanced`

### Multilingual routing (Phase 7)

| `parameters.language` | Model selected | CLI flag |
|----------------------|----------------|----------|
| omitted (default policy) | `ggml-{tier}.en.bin` | `-l en` |
| `"en"` | `ggml-{tier}.en.bin` | `-l en` |
| `"ur"`, `"hi"`, `"ar"`, `"fa"`, etc. | `ggml-{tier}.bin` | `-l <code>` |
| `"auto"` | `ggml-{tier}.bin` | omit `-l` |

Config: `WHISPER_ROUTING_POLICY=english_first` (default — preserves Phase 5 English behaviour).

---

## 6. Hosting and Deployment Strategy

### Platform decision

**Selected hosting platform: Hetzner VPS**

| Target | Spec | Purpose |
|--------|------|---------|
| **Initial deployment** | 4 vCPU, 8 GB RAM | MVP launch, validate demand |
| **Future upgrade** | 8 vCPU, 16 GB RAM | Scale after proven demand |

### Deployment constraints (locked until post-launch)

- **No Google Cloud Run migration planned**
- **No architecture rewrite planned**
- **Avoid major infrastructure changes before commercial launch**
- Retain current architecture: FastAPI, Redis, Celery, **SQLite** (MVP), whisper.cpp, DeepFilterNet CLI, Demucs
- **PostgreSQL deferred** until proven growth (Phase 14+ migration candidate)

### Production considerations

| Topic | Guidance |
|-------|----------|
| Database | SQLite OK for MVP; PostgreSQL when growth requires (Phase 14+) |
| Celery | `--queues media,ai --concurrency 1` when running Demucs (OOM risk) |
| Whisper models | English-only hosts: ~681 MB (`.en.bin` trio); full multilingual: ~1.36 GB |
| DeepFilterNet | `deep-filter` v0.5.6 binary must be on PATH or set via `DEEPFILTER_BINARY` |
| Demucs ML stack | Install `requirements-ml.txt` on Celery workers only |
| Alembic | Not yet implemented — schema via `create_all` on startup |

### Startup (development reference)

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping

# Terminal 2: FastAPI
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery
cd backend && source .venv/bin/activate
pip install -r requirements-ml.txt
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 1 --loglevel INFO
```

---

## 7. Architecture Decisions

### Stack (retained — no rewrite)

```
Client (curl / future Flutter)
    ↓ HTTP REST
FastAPI (port 8000)
    ↓                    ↓
SQLite/PostgreSQL    Redis (broker + progress cache)
    ↓                    ↓
Celery Worker (queues: media, ai)
    ├── FFmpegService
    ├── WhisperService      (whisper.cpp subprocess)
    ├── SourceSeparationService (Demucs subprocess)
    └── AudioEnhancementService (deep-filter subprocess)
```

### Core technology choices

| Layer | Technology |
|-------|------------|
| API | FastAPI + uvicorn |
| Task queue | Celery 5.x |
| Broker / cache | Redis |
| Database | SQLite (MVP); PostgreSQL deferred until proven growth |
| ORM | SQLAlchemy 2.x async |
| Speech recognition | whisper.cpp CLI |
| Source separation | Demucs 4.0.1 + PyTorch 2.8.0 CPU |
| Audio enhancement | DeepFilterNet `deep-filter` CLI 0.5.6 |
| Media | FFmpeg 6.1.1 |

### Integration policy (all ML isolated as subprocesses)

| System | Integration method |
|--------|-------------------|
| Whisper | whisper.cpp subprocess |
| Demucs | `python -m demucs` subprocess |
| DeepFilterNet | `deep-filter` subprocess |

**DeepFilterNet Python package (`pip install deepfilternet`) is explicitly forbidden** in requirements files — conflicts with validated Phase 5 ML stack (numpy `< 2.0`, packaging `< 24`, no Python 3.12 wheel for `deepfilterlib`).

### Async runtime

Celery workers use a **persistent event loop** (`app/tasks/async_runner.py` → `run_async()`). Never use `asyncio.run()` per task — causes Redis loop mismatch (Bug 9, fixed).

### Explicit non-decisions

- No Cloud Run
- No microservices split
- No GPU requirement for MVP (CPU-only validated)
- No shared Python ML dependency graph across Whisper/Demucs/DeepFilterNet

---

## 8. Whisper Multilingual Status

### Phase 7 M2 — complete and validated

Language-first routing implemented in `app/services/whisper_models.py`. Unit tests in `backend/tests/test_whisper_models.py` (13 cases).

### Supported languages (explicitly validated / documented)

| Language | BCP-47 | Routing | Validation status |
|----------|--------|---------|-------------------|
| English | `en` | `.en.bin` + `-l en` | Production-ready (Phases 2–5) |
| Urdu | `ur` | `.bin` + `-l ur` | Validated M2 — quality improved, not production-grade |
| Hindi | `hi` | `.bin` + `-l hi` | Routing supported; not separately validated |
| Arabic | `ar` | `.bin` + `-l ar` | Routing supported; not separately validated |
| Persian | `fa` | `.bin` + `-l fa` | Routing supported; not separately validated |
| Mixed / unknown | `auto` | `.bin`, omit `-l` | Routing supported; auto-detection delegated to whisper.cpp |

Full BCP-47 whitelist is in `whisper_models.py` (`WHISPER_SUPPORTED_LANGUAGES`).

### Installed models

| File | Variant | Size |
|------|---------|------|
| `ggml-tiny.en.bin` | English-only | 75 MB |
| `ggml-base.en.bin` | English-only | 142 MB |
| `ggml-small.en.bin` | English-only | 466 MB |
| `ggml-tiny.bin` | Multilingual | 75 MB |
| `ggml-base.bin` | Multilingual | 142 MB |
| `ggml-small.bin` | Multilingual | 466 MB |

**Total (dual set):** ~1.36 GB

### Key findings

| Finding | Detail |
|---------|--------|
| Urdu quality improved significantly | Multilingual `ggml-small.bin` + `-l ur` vs pre-M2 English-only path |
| Urdu not production-grade | Phonetic substitutions, occasional wrong words — model WER, not routing |
| Roman Urdu NOT implemented | Deferred until transcription accuracy improves |
| English default unchanged | `WHISPER_ROUTING_POLICY=english_first` preserves Phase 5 behaviour |
| Root cause fixed (M2) | Pre-M2: all jobs forced to `.en.bin` regardless of content language |

### Urdu job example

```json
{
  "job_type": "subtitle_generation",
  "parameters": {
    "language": "ur",
    "whisper_model": "small"
  }
}
```

Expected metadata after completion: `whisper_model_file=ggml-small.bin`, `whisper_model_variant=multilingual`, `detected_language=ur`.

---

## 9. DeepFilterNet Audio Enhancement Status

### Phase 6 — M2 complete

| Component | Status |
|-----------|--------|
| `AudioEnhancementService` | ✅ `deep-filter` CLI subprocess |
| `audio_enhance_task` | ✅ Registered in `_TASK_MAP`, `ai` queue |
| FFmpeg preprocessing | ✅ 48 kHz mono WAV via `extract_enhancement_wav()` |
| Download endpoint | ✅ `GET /jobs/{id}/download/enhanced` |
| Dependency policy | ✅ Phase 5 ML pins unchanged; no `deepfilternet` in requirements |

### Pipeline

```
source media → FFmpeg 48 kHz mono WAV → deep-filter CLI → processed/<job_id>_enhanced.wav
```

### Operational requirements

- Worker must have `deep-filter` v0.5.6 accessible (via PATH or `DEEPFILTER_BINARY` in `.env`)
- Binary is **not** pip-installed — separate deployment step on Hetzner VPS
- Full HTTP/Celery E2E validation noted as pending before production release tag (see `PHASE6_M2_VALIDATION_REPORT.md`)

### Reports

- `docs/reports/PHASE6_M1_DEEPFILTERNET_ANALYSIS.md`
- `docs/reports/PHASE6_M2_AUDIO_ENHANCEMENT_IMPLEMENTATION.md`
- `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`
- `docs/reports/PHASE6_M2_VALIDATION_REPORT.md`

---

## 10. Product Strategy

### Business objective

Launch a commercially viable MVP quickly. Validate market demand before investing in:

- Larger Whisper models (`medium`, `large`)
- GPU infrastructure
- Advanced multilingual features
- Roman Urdu transliteration

### MVP feature focus (prioritize for launch)

| Feature | Priority | Notes |
|---------|----------|-------|
| English subtitles | **Primary** | Core value proposition |
| English karaoke | **Primary** | Differentiated output |
| Audio enhancement | **Primary** | Noise removal via DeepFilterNet |
| Vocal separation | **Primary** | Stems for karaoke / remix workflows |

### Urdu / multilingual positioning

- **Treat Urdu support as experimental** — do not market as production-grade
- Do **not** prioritize Urdu perfection before launch
- Clients may pass `language: "ur"` for testing; set expectations accordingly
- Roman Urdu export deferred (see Section 11)

### Post-launch investment triggers

Only after MVP validates demand:

- `ggml-medium.bin` or larger models
- GPU workers for Demucs / future TTS
- Roman Urdu transliteration layer
- Dedicated Urdu quality engineering

---

## 11. Deferred Features

| Feature | Phase | Reason deferred |
|---------|-------|-----------------|
| Roman Urdu transliteration | **15** | Transcription accuracy + translation pipeline |
| Urdu translation / localization | **15** | Post-MVP multilingual expansion |
| Voice cloning (production) | **13–14** | Phase 8 feasibility only; GPU required; local PoC in Phase 13 |
| Voice replacement / dubbing | Post-**14** | Depends on cloning + pipeline maturity |
| Flutter frontend | **9** (in progress) | SaaS shell + API wiring |
| API authentication | **10** | Pre-launch hardening |
| Billing / commercialization | **11** | After frontend MVP |
| Creator Tools (recorder, editors) | **12** | Post-billing feature expansion |
| Hetzner deployment | **14** | Deferred until Phases 9–13 progress |
| PostgreSQL migration | **14+** | SQLite acceptable for MVP |
| `ggml-medium.bin` / larger Whisper | — | M3 recommends `base.en`; upgrade at revenue |
| WebSocket progress | Post-MVP | Nice-to-have |
| Cloud Run / serverless / K8s | — | **Explicitly rejected** |
| Architecture rewrite | — | **Explicitly rejected** |

---

## 12. Known Issues

### Open application bugs

**None known** as of Phase 7 M2 validation.

### Known limitations (not bugs)

| # | Limitation | Mitigation |
|---|------------|------------|
| L1 | `ggml-tiny.en.bin` drops lyrics on music-heavy content (20–30 s gaps) | Use `base` or `small` English model |
| L2 | Urdu word errors on `ggml-small.bin` (phonetic substitutions) | Use `small` + explicit `language: "ur"`; try `medium` after M3 benchmark |
| L3 | Celery task retry after partial execution → `JobConflictError` | Unhandled — re-queued tasks may fail |
| L4 | SQLite unsuitable for multi-worker concurrent writes at scale | PostgreSQL migration when growth requires (Phase 14+) |
| L5 | No API authentication | Phase 10 |
| L6 | `processed/` and `uploads/` accumulate indefinitely | Configurable retention policy planned (§16); not yet implemented |
| L7 | Phase 6 full E2E HTTP validation not recorded in M2 session | Run before production tag |

### Fixed bugs (reference)

Nine bugs fixed across Phases 2–7. Full write-ups in `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md`:

1. Redis not connected in Celery workers
2. SQLAlchemy `MissingGreenlet` on `job.media`
3. whisper.cpp `LD_LIBRARY_PATH`
4. FFmpeg filter path escaping
5. Missing explicit H.264 codec in burn
6. FastAPI route ordering (`download/video`)
7. Unimplemented job types returned HTTP 500
8. Demucs TorchCodec / unpinned PyTorch
9. Redis loop mismatch (`asyncio.run` vs persistent loop)
10. Phase 7: English-only Whisper forced for all jobs (routing fix)

---

## 13. Approved Roadmap (Phases 8–15)

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| **8** | Voice Cloning Feasibility | ✅ Complete | `PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md` — no implementation |
| **9** | Flutter Frontend MVP | 🔄 In progress | SaaS shell + core feature wiring; `frontend/` |
| **10** | Authentication & User Management | ⏳ Planned | |
| **11** | Billing & Commercialization | ⏳ Planned | Premium tiers; voice cloning as future add-on |
| **12** | Creator Tools | ⏳ Planned | Voice Recorder Studio · Karaoke Recording Studio · Audio Cutter · Audio Joiner · Video Cutter · Video Joiner |
| **13** | Voice Cloning Experiments | ⏳ Planned | Chatterbox Turbo PoC · OpenVoice V2 evaluation · **local laptop only** · no production deployment |
| **14** | Hetzner Deployment & Production Launch | ⏳ Planned | 4 vCPU / 8 GB MVP; GPU worker evaluated after revenue validation |
| **15** | Roman Urdu & Translation Features | ⏳ Planned | Includes Urdu localization gap from voice engines |

**Voice cloning note:** Voice cloning remains **experimental** until GPU-backed infrastructure is justified commercially. Phase 13 is local experimentation only; production deployment is deferred to Phase 14+ when revenue validates GPU spend.

### Phase 7 M3 — Complete ✅

Whisper benchmark complete. Recommendations:

| Product | Recommended model |
|---------|-------------------|
| English subtitles | `base` → `ggml-base.en.bin` |
| English karaoke | `base` → `ggml-base.en.bin` |
| Urdu (experimental) | `small` → `ggml-small.bin` |
| Hetzner 4/8 MVP | Conditional GO (CPU workloads only) |

Report: `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md`

### Phase 8 — Voice Cloning Feasibility ✅

Recommended engine for future PoC: **Chatterbox-Turbo** (MIT, pip install, English MVP). GPU required for production; **Phase 13 = local laptop experiments only**; production GPU hosting evaluated at Phase 14.

Report: `docs/reports/PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md`

### Strategic evaluation order (all phases)

1. Commercial launch readiness  
2. Hetzner hosting cost  
3. Operational simplicity  
4. Revenue generation potential  
5. User value  

---

## 14. Immediate Action Items

### Phase 9 — Flutter Frontend MVP (in progress)

- [x] Premium SaaS application shell (sidebar / drawer navigation)
- [x] Theme system (light / dark / system)
- [x] Placeholder screens for Creator Tools, Media Tools, Account, Billing
- [ ] Wire to existing REST API (Phases 1–7 backends)
- [ ] Surface retention warning before job submission (see §16)
- [ ] English-first product scope; Urdu experimental toggle optional

### Pre–Phase 14 (Phases 10–13)

- [ ] Phase 10: Authentication & user management
- [ ] Phase 11: Billing tiers (subtitle, karaoke, enhancement, separation)
- [ ] Phase 12: Creator Tools implementation
- [ ] Phase 13: Voice cloning local PoC (Chatterbox / OpenVoice)
- [ ] Implement configurable output retention (§16) before production launch

### Phase 14 — Hetzner deployment (deferred)

- [ ] Provision Hetzner VPS (4 vCPU / 8 GB RAM)
- [ ] Deploy: FastAPI, Redis, Celery, SQLite, whisper.cpp, Demucs, `deep-filter`
- [ ] Confirm Phase 7 M3 Whisper estimates with `-t 4`
- [ ] Evaluate GPU worker add-on when commercially justified

### Completed

- [x] Phase 7 M3 Whisper benchmark
- [x] Phase 8 Voice cloning feasibility study

---

## 15. Commercialization Strategy

This section documents the commercial direction of VoxClone. It complements Section 10 (Product Strategy) with explicit business, customer, infrastructure, and revenue-validation framing.

### Business Goal

Launch a commercially viable MVP as quickly as possible while minimizing infrastructure cost and operational complexity.

The primary objective is validating market demand before investing in larger AI models, GPU infrastructure, advanced multilingual support, voice cloning, or large-scale cloud architecture.

### Target Customers

**Initial focus:**

- YouTubers
- Content creators
- Course creators
- Educational channels
- Small businesses
- Social media agencies

**Not initially targeting:**

- Enterprise customers
- Broadcast media
- Real-time transcription customers
- Live streaming workloads

### MVP Launch Scope

**Prioritize:**

- English subtitle generation
- English karaoke generation
- Audio enhancement
- Vocal separation

**Experimental:**

- Urdu subtitles
- Multilingual subtitles

**Deferred:**

- Roman Urdu subtitles
- Voice cloning
- Voice replacement
- Dubbing workflows
- Real-time processing
- Hetzner production deployment (Phase 14)
- Roman Urdu (Phase 15)

### Infrastructure Strategy

**Selected hosting platform:** Hetzner VPS

| Target | Spec |
|--------|------|
| Initial deployment | 4 vCPU, 8 GB RAM |
| Future upgrade | 8 vCPU, 16 GB RAM |

**Important decisions:**

- No Cloud Run migration planned
- No serverless migration planned
- No Kubernetes
- No microservices split
- No architecture rewrite
- **Hetzner deployment deferred to Phase 14**

**Current architecture remains:**

- FastAPI
- Redis
- Celery
- SQLite (MVP)
- whisper.cpp
- DeepFilterNet
- Demucs

**PostgreSQL:** deferred until proven growth (not required for MVP launch).

### Cost-Control Strategy

The project is being developed under strict budget constraints.

**Guiding principles:**

- CPU-only inference where practical
- Open-source models
- Self-hosted infrastructure
- Avoid recurring AI API costs
- Avoid GPU hosting until justified by revenue

### Revenue Validation Strategy

Before investing in:

- Larger Whisper models
- GPU infrastructure
- Roman Urdu
- Voice cloning
- Advanced multilingual support

The project should first demonstrate:

- Paying customers
- Repeat usage
- Sustainable hosting economics

---

## 16. Global Output Retention Policy (Planned)

**Status:** Policy defined — **not yet implemented** in application code.

### Principle

All generated outputs are subject to a **configurable retention policy**. The default retention period is **10 days** (`OUTPUT_RETENTION_DAYS=10`). This value must **never be hard-coded** in application logic — it must remain configurable via environment variables (or settings file) without code changes.

### Planned configuration

```bash
# Future .env keys (illustrative — not implemented)
OUTPUT_RETENTION_DAYS=10
OUTPUT_RETENTION_ENABLED=true
```

### Scope — applies to all generated outputs

| Output category | Examples |
|-----------------|----------|
| Subtitles | SRT, VTT, TXT (`processed/*_subtitles.*`, `*_transcript.txt`) |
| Karaoke outputs | MP4, ASS (`processed/*_karaoke.mp4`, `*_karaoke.ass`) |
| Enhanced audio | WAV (`processed/*_enhanced.wav`) |
| Vocal stems | WAV (`processed/*_vocals.wav`) |
| Music stems | WAV (`processed/*_instrumental.wav`) |
| Burned video | MP4 (`processed/*_subtitled.mp4`) |
| Future voice-cloning outputs | `processed/*_cloned.wav` (planned) |
| Future creator-tool outputs | Recordings, trimmed/joined media (planned) |
| Any future generated media | Under `processed/` and related download paths |

### Future implementation requirements

| Capability | Description |
|------------|-------------|
| Configurable retention period | `OUTPUT_RETENTION_DAYS` (default 10) via `.env` / settings |
| Expiry timestamps | Persist `expires_at` on job records or output metadata |
| Automated cleanup jobs | Celery beat or cron task to delete expired files |
| Download availability indicators | API returns `expires_at` / `days_remaining` on job responses |
| User-facing retention warnings | Inform users **before processing** that files are retained for a limited period |
| Admin adjustment | Change retention duration via config reload — no deploy required |

### User communication (required at launch)

Before job submission, clients must display that outputs are stored for **{N} days** (default 10) and may be **automatically deleted** after the retention window. Flutter Phase 9 should surface this in the upload/job flow.

---

## Quick Reference — Key Files

| File | Role |
|------|------|
| `app/services/whisper_models.py` | Language-first routing, dual model registry |
| `app/services/whisper_service.py` | whisper.cpp subprocess wrapper |
| `app/services/source_separation_service.py` | Demucs subprocess |
| `app/services/audio_enhancement_service.py` | deep-filter subprocess |
| `app/tasks/media_tasks.py` | All Celery task implementations |
| `app/tasks/async_runner.py` | Persistent worker event loop |
| `app/core/config.py` | Settings including `WHISPER_ROUTING_POLICY` |
| `backend/tests/test_whisper_models.py` | Phase 7 routing unit tests |
| `backend/requirements-ml.txt` | Pinned Demucs stack (worker only) |

---

## Session Continuity

### Starting a New ChatGPT Session

This snapshot (`docs/context/PROJECT_SNAPSHOT_2026_06_22.md`) is the **authoritative project state document** for VoxClone. Provide it at the start of any new ChatGPT or Cursor session when continuing development, planning, or commercialization work.

**Why use this document:**

- It consolidates technical state, business strategy, infrastructure decisions, and next-phase guidance in one place.
- It does not depend on prior chat history — each session can start fresh without losing context.
- It records locked decisions (Hetzner VPS, no Cloud Run, MVP scope, deferred features) that should not be re-litigated unless business requirements change.

**How to use it:**

1. Attach or paste this file (or reference its path) at the beginning of the session.
2. State the specific task (e.g. "Execute Phase 7 M3 benchmark" or "Draft Hetzner deployment checklist").
3. For deep technical implementation detail, cross-reference `docs/context/MASTER_PROJECT_HANDOFF.md` and `docs/context/NEXT_SESSION_START_HERE.md`.

**Related entry points:**

| Document | When to use |
|----------|-------------|
| `PROJECT_SNAPSHOT_2026_06_22.md` | Business + technical state; commercial direction; session bootstrap |
| `NEXT_SESSION_START_HERE.md` | Quick dev startup commands and Phase 7 routing reference |
| `MASTER_PROJECT_HANDOFF.md` | Full API, schema, and implementation handoff for developers |

---

*Snapshot updated: 2026-06-24 — Phase 9 Flutter shell in progress; approved roadmap Phases 9–15; retention policy expanded.*
