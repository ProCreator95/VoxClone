# Phase 5 — Milestone 2: Vocal Separation Job

**Status:** Complete (awaiting review)  
**Scope:** `vocal_separation` job type, Demucs subprocess, canonical stem outputs.

---

## Summary

New job type `vocal_separation` separates vocals from accompaniment using Demucs
(`htdemucs`, two-stem mode). Outputs:

- `processed/{job_id}_vocals.wav`
- `processed/{job_id}_instrumental.wav` (from Demucs `no_vocals.wav`)

Jobs record `stem_origin: "canonical"` — the reusable system-of-record for stems.

---

## Setup (worker)

Demucs requires a **matched, pinned** PyTorch pair. Unpinned `pip install torch torchaudio`
pulls TorchAudio ≥2.9, which needs TorchCodec for WAV save — separation completes but
export crashes. See `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md`.

```bash
cd backend && source .venv/bin/activate

# Pinned CPU stack (torch/torchaudio/demucs — see requirements-ml.txt)
pip install -r requirements-ml.txt
```

### ML self-test (run before first vocal_separation job)

```bash
python - <<'EOF'
import torch
import torchaudio
import demucs

print("torch", torch.__version__)
print("torchaudio", torchaudio.__version__)
print("demucs", demucs.__version__)

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

All checks must pass. If `torchaudio.save` fails, verify pins with
`pip show torch torchaudio demucs`.

First successful separation run downloads `htdemucs` weights (~80–200 MB).

---

## API example

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "vocal_separation",
  "parameters": {
    "separation_model": "htdemucs"
  }
}
```

---

## Completed job parameters

```json
{
  "separation_model": "htdemucs",
  "separation_device": "cpu",
  "input_sample_rate": 44100,
  "input_channels": 2,
  "duration_seconds": 216.5,
  "stem_origin": "canonical",
  "result_files": {
    "vocals": "/abs/processed/{job_id}_vocals.wav",
    "instrumental": "/abs/processed/{job_id}_instrumental.wav"
  }
}
```

`result_path` → vocals WAV.

**Intermediate files (M2 fix):** `parameters.intermediate_files.separation_input`
records the stereo WAV fed to Demucs for reproducibility (not deleted after success).

See `docs/reports/PHASE5_STEM_OWNERSHIP_AND_OPS.md` for ownership rules and worker concurrency.

---

## Files changed

| File | Change |
|------|--------|
| `app/models/stem_metadata.py` | **New** — `StemOrigin`, constants |
| `app/models/job.py` | `VOCAL_SEPARATION` job type |
| `app/services/source_separation_service.py` | **New** — Demucs subprocess wrapper |
| `app/services/ffmpeg_service.py` | `extract_stereo_wav()` for Demucs input |
| `app/core/config.py` | Demucs / separation settings |
| `app/tasks/media_tasks.py` | `vocal_separation_task` |
| `app/tasks/celery_app.py` | Route to `ai` queue |
| `app/api/v1/endpoints/jobs.py` | Download endpoints + OpenAPI |
| `backend/requirements-ml.txt` | **New** |
| `backend/.env.example` | Demucs settings |

---

## Manual test plan

1. Install ML deps on worker (see Setup).
2. Upload music video or audio.
3. `POST /jobs` with `job_type: vocal_separation`.
4. Poll until `completed`.
5. `GET /jobs/{id}` — verify `stem_origin`, `result_files`.
6. `GET /jobs/{id}/download/vocals` — HTTP 200, `audio/wav`.
7. `GET /jobs/{id}/download/instrumental` — HTTP 200.
8. `GET /jobs/{id}/result` — serves vocals WAV.
9. Regression: subtitle / karaoke / burn jobs still work.

---

## Next step

**Milestone 3:** Karaoke output modes `karaoke_video_with_vocals` and `karaoke_video_no_vocals`.
