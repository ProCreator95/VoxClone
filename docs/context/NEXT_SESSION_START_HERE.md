# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-24)

**Phases 1–8 are complete. Phase 9 Flutter Frontend MVP is in progress.**

```
Phase 1: Upload → ffprobe → Media + Job persistence → Redis progress
Phase 2: subtitle_generation → whisper.cpp → SRT + VTT + TXT
Phase 3: subtitle_burn → FFmpeg H.264 burn-in → burned MP4
Phase 4: karaoke → word-level ASS → karaoke MP4 (with_vocals mode)
Phase 5: vocal_separation + all karaoke modes + separation_job_id reuse
Phase 6: audio_enhance → FFmpeg 48 kHz → deep-filter CLI → enhanced WAV
Phase 7 M2: multilingual Whisper routing — language-first model selection (validated)
Phase 7 M3: Whisper benchmark — production model recommendations (complete)
Phase 8: Voice cloning feasibility study (complete — no implementation)
Phase 9: Flutter Frontend MVP — SaaS shell + placeholders (in progress)
```

**Git state:** `feature/flutter-frontend-mvp`

**Flutter app:** `frontend/` — run with `cd frontend && flutter run`

---

## Approved Roadmap (Phases 9–15)

| Phase | Name | Status |
|-------|------|--------|
| **9** | Flutter Frontend MVP | 🔄 **In progress** |
| **10** | Authentication & User Management | Planned |
| **11** | Billing & Commercialization | Planned |
| **12** | Creator Tools | Planned |
| **13** | Voice Cloning Experiments | Planned |
| **14** | Hetzner Deployment & Production Launch | Deferred |
| **15** | Roman Urdu & Translation Features | Deferred |

### Phase 12 — Creator Tools (planned)

- Voice Recorder Studio
- Karaoke Recording Studio
- Audio Cutter · Audio Joiner · Video Cutter · Video Joiner

### Phase 13 — Voice Cloning Experiments (planned)

- Chatterbox Turbo PoC
- OpenVoice V2 evaluation
- **Local laptop experimentation only** — no production deployment

**Voice cloning note:** Voice cloning remains **experimental** until GPU-backed infrastructure is justified commercially.

**Strategic locks:**

- Hetzner deployment → **Phase 14** (not before)
- Flutter frontend → **Phase 9** (in progress)
- Roman Urdu → **Phase 15**
- Voice cloning production → **Phase 14+** (GPU required; Phase 13 = local PoC only)
- SQLite → **OK for MVP**; PostgreSQL deferred until proven growth
- No Cloud Run · no serverless · no Kubernetes · no architecture rewrite

**Architecture (unchanged):** FastAPI · Redis · Celery · SQLite · whisper.cpp · DeepFilterNet · Demucs

---

## Phase 9 — Flutter UI (current work)

**Design doc:** `docs/reports/PHASE9_FLUTTER_FRONTEND_MVP_DESIGN.md`

**Completed (M1 + UI refactor):**

- Premium SaaS shell — fixed sidebar (desktop/tablet) + drawer (mobile)
- Home screen with MVP overview, retention notice, roadmap
- Placeholder screens: core features, creator tools, media tools, account, billing
- Theme system (System / Light / Dark)
- Settings persistence (API URL, theme)

**Next (M2+):**

1. Upload + media list (`POST /api/v1/uploads`, `GET /api/v1/media`)
2. Job submission + progress polling
3. Downloads

---

## Global Output Retention Policy (Planned)

**Not yet implemented** in backend — policy defined for future phases.

All generated outputs are subject to a configurable retention policy.

| Setting | Default |
|---------|---------|
| `OUTPUT_RETENTION_DAYS` | **10** (must remain configurable via env — never hard-coded) |

**Applies to:** subtitles · karaoke outputs · enhanced audio · vocal stems · music stems · future voice-cloning outputs · future creator-tool outputs

Future: expiry timestamps, automated cleanup jobs, download availability indicators, user warnings before processing. See `PROJECT_SNAPSHOT_2026_06_22.md` §16.

---

## Phase 7 M3 — Benchmark Complete ✅

**Report:** `docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md`

| Product | Recommended model |
|---------|-------------------|
| English subtitles | `base` → `ggml-base.en.bin` |
| English karaoke | `base` → `ggml-base.en.bin` |
| Urdu (experimental) | `small` → `ggml-small.bin` |
| Hetzner 4/8 CPU MVP | Conditional GO (Whisper/Demucs workloads) |

---

## Phase 8 — Voice Cloning Feasibility Complete ✅

**Report:** `docs/reports/PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md`

| Decision | Recommendation |
|----------|----------------|
| Best overall engine | **Chatterbox** (Multilingual V3 / Turbo) — MIT |
| PoC candidate | **Chatterbox-Turbo** (English-first) |
| Roadmap alternate | **OpenVoice V2** — MIT |
| Production requirement | **GPU worker** — Phase 13 local PoC; production at Phase 14+ |
| MVP includes cloning? | **No** |

---

## Whisper routing (Phase 7)

| `parameters.language` | Model | CLI flag |
|----------------------|-------|----------|
| omitted (default policy) | `ggml-{tier}.en.bin` | `-l en` |
| `"en"` | `ggml-{tier}.en.bin` | `-l en` |
| `"ur"`, `"hi"`, etc. | `ggml-{tier}.bin` | `-l <code>` |
| `"auto"` | `ggml-{tier}.bin` | omit `-l` |

Config: `WHISPER_ROUTING_POLICY=english_first` (default).

---

## Start the Backend

```bash
# Terminal 1: Redis
redis-server --daemonize yes && redis-cli ping   # → PONG

# Terminal 2: FastAPI
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery (both queues; concurrency=1 when running Demucs)
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
pip install -r requirements-ml.txt   # Demucs stack only — NOT deepfilternet
celery -A app.tasks.celery_app:celery_app worker \
  --queues media,ai --concurrency 1 --loglevel INFO
```

## Start the Flutter App

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/frontend"
flutter pub get
flutter run
```

---

## Key Files

| File | Role |
|------|------|
| `frontend/lib/core/routing/navigation_config.dart` | Sidebar navigation tree |
| `frontend/lib/core/widgets/app_shell.dart` | Responsive shell layout |
| `frontend/lib/features/home/home_screen.dart` | Home / welcome screen |
| `app/services/whisper_models.py` | Language-first routing |
| `app/tasks/media_tasks.py` | All Celery tasks |

---

## Full Documentation

```
docs/context/PROJECT_SNAPSHOT_2026_06_22.md          ← authoritative state
docs/reports/PHASE9_FLUTTER_FRONTEND_MVP_DESIGN.md
docs/context/MASTER_PROJECT_HANDOFF.md
docs/reports/PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md
docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md
```
