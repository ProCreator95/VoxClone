# Phase 5 — Documentation Audit

> **Superseded for git/state accuracy** by `PHASE5_DOCUMENTATION_SYNC.md` (2026-06-18).
> This file remains as a historical record of the pre-commit documentation pass.

**Date:** 2026-06-18
**Auditor:** Documentation maintainer pass (pre-commit on `feature/source-separation`)

---

## Current project phase

| Field | Value |
|-------|-------|
| **Current phase** | Phase 5 complete (pre-commit); Phase 5 Milestone 4 pending |
| **Branch** | `feature/source-separation` |
| **HEAD commit** | `47be178` — Phase 4: karaoke generation complete |
| **Pending tag** | `phase5-source-separation` (at Phase 5 commit) |

### Completed phases

| Phase | Name | Tag |
|-------|------|-----|
| 1 | Backend Foundation | `v0.1-foundation` |
| 2 | Subtitle Generation | `phase2-subtitles-working` |
| 3 | Subtitle Burn-In | `phase3-subtitle-burn` |
| 4 | Karaoke Generation | `phase4-karaoke-generation` |
| 5 | Source Separation / Vocal Removal | *(pending commit + tag)* |

### Next phase (recommended)

**Phase 5 Milestone 4** — `vocals_only`, `music_only`, `separation_job_id` reuse
**Then Phase 6** — Audio Enhancement (DeepFilterNet)

---

## New Phase 5 capabilities (from code)

| Capability | Implementation |
|------------|----------------|
| Per-job Whisper models | `whisper_models.py` — `tiny` / `base` / `small` |
| `vocal_separation` job | `vocal_separation_task`, `SourceSeparationService` |
| Demucs integration | Subprocess `htdemucs` two-stem; pinned ML stack |
| Canonical stems | `stem_origin: canonical` on vocal_separation jobs |
| Karaoke modes | `karaoke_video_with_vocals`, `karaoke_video_no_vocals` |
| Inline stems | `stem_origin: inline` on karaoke no-vocals mode |
| Stem downloads | `GET /jobs/{id}/download/vocals`, `/download/instrumental` |
| Worker async runtime | `async_runner.py` — persistent loop + `run_async()` |
| ML deps | `requirements-ml.txt` — torch 2.8.0, torchaudio 2.8.0, demucs 4.0.1 |

### Implemented job types (`IMPLEMENTED_JOB_TYPES`)

```
audio_extraction, subtitle_generation, subtitle_burn, karaoke,
vocal_separation, audio_enhance (placeholder — marks failed)
```

Returns HTTP 422: `voice_replacement`, `voice_clone`

---

## Documentation files changed

### Authoritative context (updated)

| File | Changes |
|------|---------|
| `docs/context/CURRENT_PROJECT_STATE.md` | Full refresh — Phase 5, branch, services, validation, git state |
| `docs/context/NEXT_SESSION_START_HERE.md` | Phase 5 complete; next steps; ML install; vocal separation test |
| `docs/context/KNOWN_BUGS_AND_ROOT_CAUSES.md` | Bugs 7–9; branch; async loop + Demucs fixes |
| `docs/context/MASTER_PROJECT_HANDOFF.md` | Architecture, API, roadmap, Phase 5 section, git, key files, pitfalls |

### Deprecated context (pointer notes only)

| File | Change |
|------|--------|
| `docs/context/NEXT_PHASES_ROADMAP.md` | Note: Phases 3–5 done on `feature/source-separation` |
| `docs/context/HANDOFF_TO_NEXT_CHAT.md` | Obsolete next-steps note updated |
| `docs/context/VOXCLONE_PROJECT_CONTEXT.md` | Branch pointer updated |
| `docs/context/PHASE2_DEBUG_HANDOFF.md` | Branch pointer updated |
| `docs/context/CHATGPT_RESUME_PROMPT.md` | Branch pointer updated |
| `docs/context/GIT_CHECKPOINT.md` | Branch pointer updated |
| `docs/project_context.md` | Branch pointer updated |

### Phase 5 reports (status lines)

| File | Change |
|------|--------|
| `docs/reports/PHASE5_MILESTONE1_WHISPER_MODELS.md` | Status → pre-commit complete |
| `docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` | Status → pre-commit complete |
| `docs/reports/PHASE5_MILESTONE3_KARAOKE_MODES.md` | Status → pre-commit complete |
| `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md` | Status → validated |

### Other project docs

| File | Change |
|------|--------|
| `backend/README.md` | Pipelines, job types, ML install, Celery concurrency |

### Unchanged (already accurate)

| File | Notes |
|------|-------|
| `docs/reports/PHASE5_STEM_OWNERSHIP_AND_OPS.md` | Accurate; references ML deps |
| `docs/reports/PHASE2_COMPLETION_REPORT.md` | Historical Phase 2 report |
| `docs/testing/*` | Phase 2 testing guides — still valid for subtitle pipeline |

---

## Inconsistencies fixed

| Issue | Resolution |
|-------|------------|
| Branch listed as `feature/karaoke-generation` | → `feature/source-separation` |
| Phase 4 shown as pre-commit / next step | → Phase 4 tagged `phase4-karaoke-generation` at `47be178` |
| Karaoke listed as next phase | → Phase 5 complete; M4 recommended next |
| Roadmap Phase 5 = Audio Enhancement | → Phase 5 = source separation; Phase 6 = audio enhance |
| `audio_enhance` documented as HTTP 422 | → dispatches but marks failed (in `_TASK_MAP`) |
| Missing `/download/vocals`, `/download/instrumental` | Added to endpoint tables |
| Missing `async_runner`, Demucs services | Added to structure and key files |
| Bug 1 fix showed `asyncio.run()` only | Updated; cross-ref Bug 9 persistent loop |
| Tag `phase4-karaoke` vs `phase4-karaoke-generation` | Corrected to actual tag name |
| Milestone reports "awaiting review" | → pre-commit complete |

---

## Remaining documentation gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| `backend/README.md` | ~~Medium~~ | Updated in this audit pass |
| `docs/context/MASTER_PROJECT_HANDOFF.md` Section 20 | Low | Optional Phase 5 deep-dive section (M1–M3 covered in Section 9 + reports) |
| End-to-end Phase 5 API curl guide in handoff | Low | Covered in `NEXT_SESSION_START_HERE.md` and M2 report |
| `phase5-source-separation` tag | — | Create at commit time (not documentation) |
| Phase 5 Milestone 4 spec doc | — | Not written until M4 is scoped |

---

## Roadmap consistency check

All updated authoritative docs now agree on:

| Item | Value |
|------|-------|
| Completed | Phases 1–5 (M1–M3) |
| Current work | Phase 5 pre-commit on `feature/source-separation` |
| Next | Phase 5 M4, then Phase 6 Audio Enhancement |
| Branch | `feature/source-separation` |
| Latest tag | `phase4-karaoke-generation` |
| Stale branches referenced | Only in deprecated docs (with pointer notes) |

---

## Recommended commit message

```
Phase 5: source separation, karaoke modes, and worker ML deps

- Add vocal_separation job with Demucs subprocess and canonical stems
- Add karaoke output modes (with_vocals / no_vocals) and per-job whisper models
- Pin torch 2.8.0 + demucs 4.0.1 in requirements-ml.txt
- Fix Celery async loop ownership via async_runner.run_async()
- Update project documentation for Phase 5 pre-commit state
```

Suggested tag: `phase5-source-separation`

---

## Validation performed

Documentation was cross-checked against:

- `backend/app/models/job.py` — job types
- `backend/app/tasks/media_tasks.py` — `_TASK_MAP`, task implementations
- `backend/app/api/v1/endpoints/jobs.py` — download routes
- `backend/app/tasks/async_runner.py` — worker loop pattern
- `backend/requirements-ml.txt` — pinned versions
- Git: branch, tags, staged file list
