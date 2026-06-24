# Next Session — Start Here

**This is the entry point for continuing VoxClone development.**

---

## Current State (as of 2026-06-23)

**Phases 1–7 and Phase 8 feasibility are complete.**

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
```

**Git state:** `feature/whisper-multilingual`

---

## Approved Roadmap (Phases 9–13)

| Phase | Name | Status |
|-------|------|--------|
| **9** | Flutter Frontend MVP | 🔜 **Next** |
| **10** | Authentication & User Management | Planned |
| **11** | Billing & Commercialization | Planned |
| **12** | Hetzner Deployment & Production Launch | Deferred |
| **13** | Roman Urdu & Translation Features | Deferred |

**Strategic locks:**

- Hetzner deployment → **Phase 12** (not before)
- Flutter frontend → **Phase 9**
- Roman Urdu → **Phase 13**
- Voice cloning production → **post-Phase 12** (GPU required)
- SQLite → **OK for MVP**; PostgreSQL deferred until proven growth
- No Cloud Run · no serverless · no Kubernetes · no architecture rewrite

**Architecture (unchanged):** FastAPI · Redis · Celery · SQLite · whisper.cpp · DeepFilterNet · Demucs

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
| Disqualified (commercial) | XTTS-v2 (CPML), F5-TTS weights (NC), Fish Speech (custom license) |
| Production requirement | **GPU worker** — not viable on 4 vCPU / 8 GB CPU-only VPS |
| MVP includes cloning? | **No** |

Voice cloning remains **out of MVP scope**. No packages installed; no code changes in Phase 8.

---

## Global Output Retention Policy (Planned)

**Not yet implemented** — policy defined for future phases.

| Setting | Default |
|---------|---------|
| Retention period | **10 days** (configurable via `.env` — not hard-coded) |
| Scope | All generated outputs (subtitles, karaoke, stems, enhanced audio, future clone outputs) |

Future: expiry timestamps, automated cleanup jobs, download availability indicators, user warnings before processing. See `PROJECT_SNAPSHOT_2026_06_22.md` §16.

---

## What to Do Next — Phase 9

1. **Flutter Frontend MVP** — upload, job creation, progress polling, download
2. English-first UI (subtitles, karaoke, enhancement, separation)
3. Surface retention warning before job submission
4. Wire to existing `POST /api/v1/uploads` and `POST /api/v1/jobs` APIs

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

---

## Key Files

| File | Role |
|------|------|
| `app/services/whisper_models.py` | Language-first routing |
| `app/services/whisper_service.py` | whisper.cpp subprocess |
| `app/tasks/media_tasks.py` | All Celery tasks |
| `tests/test_whisper_models.py` | Routing unit tests |

---

## Integration Rules (unchanged)

| System | Integration |
|--------|-------------|
| Whisper | whisper.cpp subprocess |
| Demucs | demucs subprocess |
| DeepFilterNet | `deep-filter` subprocess |

Full Phase 6 policy: `docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md`

---

## Full Documentation

```
docs/context/PROJECT_SNAPSHOT_2026_06_22.md          ← authoritative state
docs/context/MASTER_PROJECT_HANDOFF.md
docs/reports/PHASE8_VOICE_CLONING_FEASIBILITY_STUDY.md
docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md
docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md
docs/testing/WHISPER_CPP_SETUP.md
```
