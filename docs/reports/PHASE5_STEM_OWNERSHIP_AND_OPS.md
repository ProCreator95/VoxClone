# Phase 5 — Stem Ownership and Worker Operations

## Canonical stem ownership

| `stem_origin` | Producer | Reusable by Phase 6–9? |
|---------------|----------|------------------------|
| `canonical` | `vocal_separation` only | **Yes** — system of record |
| `inline` | `karaoke` (inline Demucs) | **No** — convenience / one-shot UX |

### Rules

1. Only `vocal_separation_task` may set `stem_origin: "canonical"`.
2. Karaoke inline separation must use `karaoke_inline_stem_origin()` → always `"inline"`.
3. Future phases resolve reusable stems via `require_canonical_stem_job()` in
   `app/models/stem_metadata.py` (checks `job_type` + `stem_origin`).
4. Phase 6+ should accept `source_job_id` pointing to a **`vocal_separation`** job,
   not a karaoke job, when canonical stems are required.

## Intermediate files

| Key | Producer | Purpose |
|-----|----------|---------|
| `intermediate_files.separation_input` | `vocal_separation`, karaoke no-vocals | Exact stereo WAV fed to Demucs (reproducibility) |
| `intermediate_files.audio` | karaoke with-vocals | 16 kHz mono WAV used for Whisper |
| `intermediate_files.instrumental_video` | karaoke no-vocals | Video + instrumental audio before ASS burn |

**Policy:** expose in metadata (do not delete after success). Rationale: Demucs
debugging and reproducibility without re-running FFmpeg; aligns with keeping
traceability artifacts (`_audio.wav`) in earlier phases.

## ML dependencies (Demucs)

Install only on Celery workers that run `vocal_separation` or karaoke inline separation.
Use pinned versions — see `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md` and
`backend/requirements-ml.txt`. Run the ML self-test in
`docs/reports/PHASE5_MILESTONE2_VOCAL_SEPARATION.md` after install.

## Celery worker concurrency (Demucs enabled)

Demucs + PyTorch subprocesses are RAM-heavy. Recommended:

```bash
celery -A app.tasks.celery_app worker \
  --queues media,ai \
  --concurrency=1 \
  --loglevel INFO
```

`docker-compose.yml` defaults to `--concurrency=2` — reduce to `1` on hosts
running source separation when OOM is observed.

## Demucs model selection

API parameter `separation_model` is whitelisted in
`app/services/separation_models.py` (currently `htdemucs` only). Invalid values
return HTTP 422 at job creation.
