---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Phase 3 (Subtitle Burn-In) is shown as `🔜 not yet done` — it is complete as of `2f9f643`
> - Phase numbering conflicts with the current approved roadmap:
>   - This doc: Phase 4 = Audio Extraction, Phase 5 = Karaoke/Vocal Removal, Phase 6 = Audio Enhancement
>   - Current roadmap: Phase 4 = Karaoke Generation, Phase 5 = Audio Enhancement, Phase 6 = Vocal Removal
> - Phase 3 API design shows `"font_color": "white"` — the implemented API uses ASS hex format (`"&H00FFFFFF&"`)
> - Phase 3 implementation steps describe the stub state, not the completed implementation
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` (Section 13 — Remaining Roadmap, Section 19 — How to Start Phase 4)

---

# VoxClone — Next Phases Roadmap

## Overview

```
Phase 1  ✅  Backend Foundation
Phase 2  ✅  Whisper Subtitle Pipeline
Phase 3  🔜  Subtitle Burn-In
Phase 4  🔜  Audio Extraction Service
Phase 5  🔜  Karaoke / Vocal Removal
Phase 6  🔜  Audio Enhancement
Phase 7  🔜  Text-To-Speech
Phase 8  🔜  Voice Replacement
Phase 9  🔜  Voice Cloning
Phase 10 🔜  Voice Conversion
Phase 11 🔜  Flutter Frontend
Phase 12 🔜  Production Release
```

---

## Phase 3 — Subtitle Burn-In

### Objective

Embed (burn) SRT subtitles permanently into a video using FFmpeg.

```
Video + SRT
     ↓
  FFmpeg
     ↓
Video With Hardcoded Subtitles
```

### Dependencies

- `ffmpeg` (already available)
- `FFmpegService.burn_subtitles()` (already implemented as stub in Phase 1)
- Completed `subtitle_generation` job (provides SRT path)

### API Design

```
POST /api/v1/jobs
{
    "media_id": "<media-uuid>",
    "job_type": "subtitle_burn",
    "parameters": {
        "srt_path": "/path/to/subtitles.srt",   // OR
        "subtitle_job_id": "<subtitle-job-uuid>", // reference a prior job
        "font_size": 24,
        "font_color": "white",
        "position": "bottom"
    }
}
```

### Implementation Steps

1. Complete `burn_subtitles_task` in `media_tasks.py` (stub exists)
2. Add `subtitle_job_id` resolution — look up SRT from a prior job's `result_files.srt`
3. Add FFmpeg subtitle style options (font, size, color, position)
4. Return burned video via `GET /jobs/{id}/result`

### Expected Outputs

- `<job-id>_subtitled.mp4` — video with burned subtitles

### Testing Strategy

1. Upload MP4 → Generate subtitles (Phase 2) → Burn subtitles (Phase 3)
2. Verify output video has visible subtitles using ffprobe
3. Test font size and color parameters
4. Test with SRT from file vs. from subtitle_job_id

---

## Phase 4 — Audio Extraction Service

### Objective

Expose audio extraction as a standalone user-facing feature. Users upload a video and receive a high-quality audio file.

```
Video
  ↓
FFmpeg
  ↓
Audio (WAV / MP3 / FLAC)
```

### Dependencies

- `ffmpeg` (already available)
- `FFmpegService.extract_audio()` (already implemented)
- `extract_audio_task` in `media_tasks.py` (already implemented)

### API Design

Currently `extract_audio_task` exists but targets WAV for Whisper. For user-facing extraction:

```
POST /api/v1/jobs
{
    "media_id": "<video-media-uuid>",
    "job_type": "audio_extraction",
    "parameters": {
        "format": "mp3",         // "wav" | "mp3" | "flac" | "m4a"
        "sample_rate": 44100,    // target sample rate
        "bitrate": "320k",       // for lossy formats
        "channels": 2            // 1=mono, 2=stereo
    }
}
```

### Implementation Steps

1. Extend `FFmpegService.extract_audio()` to support format and quality params
2. Update `extract_audio_task` to accept format parameters
3. Return audio file via `GET /jobs/{id}/result`

### Expected Outputs

- `<job-id>_audio.<ext>` (e.g. `_audio.mp3`)

### Testing Strategy

1. Upload MP4, create `audio_extraction` job with `format=mp3`
2. Verify output is valid MP3 using `ffprobe`
3. Test each format (wav, mp3, flac, m4a)
4. Test quality parameters

---

## Phase 5 — Karaoke / Vocal Removal

### Objective

Separate vocals from music/instruments using Demucs, producing isolated stems.

```
Video/Audio
     ↓
  Demucs
     ↓
vocals.wav + no_vocals.wav + drums.wav + bass.wav + other.wav
```

### Dependencies

- `demucs` Python package (`pip install demucs`)
- `torch` (required by Demucs)
- ~1GB+ disk space for model download
- 4GB+ RAM recommended

### Implementation Steps

1. Install Demucs: `pip install demucs`
2. Create `app/services/demucs_service.py`
3. Implement `DemucsService.separate(audio_path, model) → StemResult`
4. Implement `karaoke_task` in `media_tasks.py` (stub exists)
5. Add `DEMUCS_MODEL` to config (e.g. `htdemucs`, `mdx_extra`)
6. Store all stems in `result_files`

### API Parameters

```json
{
    "job_type": "karaoke",
    "parameters": {
        "model": "htdemucs",
        "stems": ["vocals", "no_vocals"]
    }
}
```

### Expected Outputs

- `<job-id>_vocals.wav`
- `<job-id>_no_vocals.wav`
- `<job-id>_drums.wav`
- `<job-id>_bass.wav`
- `<job-id>_other.wav`

### Download Endpoints

```
GET /jobs/{id}/download/vocals
GET /jobs/{id}/download/no_vocals
GET /jobs/{id}/download/drums
GET /jobs/{id}/download/bass
```

### Testing Strategy

1. Use a music track with clear vocals
2. Verify vocals stem contains voice content
3. Verify no_vocals stem is silence or near-silence for the vocal frequency range
4. Test model quality levels

---

## Phase 6 — Audio Enhancement

### Objective

Remove background noise and enhance audio quality using DeepFilterNet.

```
Noisy Audio
     ↓
DeepFilterNet
     ↓
Clean Audio
```

### Dependencies

- `deepfilternet` Python package
- `pip install deepfilternet`
- Requires PyTorch

### Implementation Steps

1. Create `app/services/deepfilter_service.py`
2. Implement `enhance_audio_task` in `media_tasks.py` (stub exists)
3. Process audio in chunks for large files
4. Add `DEEPFILTER_ATT_FACTOR` to config (0.0–1.0 noise suppression strength)

### API Parameters

```json
{
    "job_type": "audio_enhance",
    "parameters": {
        "attenuation_limit": 100,
        "post_filter": true
    }
}
```

### Expected Outputs

- `<job-id>_enhanced.wav`

### Testing Strategy

1. Use a recording with background noise (fan, traffic, etc.)
2. Measure SNR improvement
3. Verify speech intelligibility is preserved
4. Test with music (should not degrade quality)

---

## Phase 7 — Text-To-Speech

### Objective

Convert written text to natural speech using Piper TTS.

```
Text Input
     ↓
   Piper
     ↓
Speech Audio (.wav)
```

### Dependencies

- Piper TTS (`pip install piper-tts` or binary download)
- Piper voice models (ONNX + JSON config)
- ~50–200MB per voice model

### Implementation Steps

1. Create `app/services/piper_service.py`
2. Add `JobType.TTS = "tts"` to job model
3. Create `tts_task` in `media_tasks.py`
4. Add voice model management endpoints
5. Add `PIPER_MODELS_DIR` and `PIPER_BINARY` to config

### API Design

```
POST /api/v1/jobs
{
    "media_id": null,  // TTS doesn't require a source media
    "job_type": "tts",
    "parameters": {
        "text": "Hello, this is a test of VoxClone TTS.",
        "voice": "en_US-amy-medium",
        "speed": 1.0
    }
}
```

Note: TTS jobs don't have a source media file — `media_id` may be nullable.

### Expected Outputs

- `<job-id>_speech.wav`

### Testing Strategy

1. Submit short text, verify audio is generated
2. Test multiple voice models
3. Test speed parameter (0.5x to 2.0x)
4. Measure audio quality (listening test)

---

## Phase 8 — Voice Replacement (Dubbing)

### Objective

Replace the original voice track in a video with a newly generated voice, producing a dubbed video.

```
Transcript
     ↓
Generated Voice (Piper)
     ↓
Align with Video Timing
     ↓
Dubbed Video
```

### Dependencies

- Phase 2 (subtitle pipeline for transcript)
- Phase 7 (Piper TTS for voice generation)
- FFmpeg (audio replacement)

### Implementation Steps

1. Create `voice_replacement_task` in `media_tasks.py` (stub exists)
2. Segment transcript by timing
3. Generate TTS for each segment with timing alignment
4. Mix generated speech back into video using FFmpeg
5. Optionally preserve background music (requires Demucs - Phase 5)

### Expected Outputs

- `<job-id>_dubbed.mp4`

---

## Phase 9 — Voice Cloning

### Objective

Clone a specific speaker's voice from a reference audio clip, then synthesize new speech in that cloned voice using OpenVoice.

```
Reference Audio (target voice)
             +
          Text
             ↓
         OpenVoice
             ↓
    Speech in Target Voice
```

### Dependencies

- OpenVoice (`pip install openvoice` or from source)
- CUDA GPU strongly recommended
- ~2GB model download

### Implementation Steps

1. Create `app/services/openvoice_service.py`
2. Add `JobType.VOICE_CLONE = "voice_clone"` (already in JobType)
3. Create `voice_clone_task` in `media_tasks.py` (stub exists)
4. Accept reference audio (upload separately as media)
5. Synthesize text in cloned voice

### API Design

```json
{
    "media_id": "<reference-audio-uuid>",
    "job_type": "voice_clone",
    "parameters": {
        "text": "Text to speak in the cloned voice",
        "speed": 1.0,
        "language": "en"
    }
}
```

### Expected Outputs

- `<job-id>_cloned_speech.wav`

---

## Phase 10 — Voice Conversion

### Objective

Convert the speaking style of an audio recording to match a target voice, without changing the words.

```
Source Voice (audio with speech)
             +
   Target Voice (reference)
             ↓
     Voice Conversion Model
             ↓
    Source Content in Target Voice
```

### Dependencies

- FreeVC, kNN-VC, or similar voice conversion model
- Both source and target audio must be uploaded as media

### Implementation Steps

1. Create `app/services/voice_conversion_service.py`
2. Add `JobType.VOICE_CONVERSION = "voice_conversion"` to job model
3. Create `voice_conversion_task`
4. Two-media job creation (extend `JobCreate` schema)

### Expected Outputs

- `<job-id>_converted.wav`

---

## Phase 11 — Flutter Frontend

### Objective

Mobile and desktop UI for VoxClone.

### Features

1. Home screen with recent jobs
2. Upload screen (video/audio picker)
3. Job type selector with parameter controls
4. Progress screen with real-time updates
5. Results screen with download buttons
6. Settings screen (API URL, Whisper model, etc.)

### Dependencies

- Flutter SDK
- Dart HTTP client (dio or http package)
- File picker package
- All Phase 1–10 backend APIs must be stable

### Architecture

```
Flutter App
     ↓
HTTP → VoxClone REST API (localhost or remote)
```

### API Considerations

- All backend API responses already use JSON
- Download endpoints return file streams — Flutter needs to handle FileResponse
- Progress polling via periodic HTTP calls (or upgrade to WebSocket in parallel)

---

## Phase 12 — Production Release

### Objective

Harden VoxClone for production use and distribute.

### Tasks

1. **PostgreSQL migration** — Swap SQLite for PostgreSQL + Alembic migrations
2. **Authentication** — JWT-based API auth or API key management
3. **Rate limiting** — Slowapi or similar
4. **Storage** — Optional S3/MinIO backend for uploads/outputs
5. **Docker Compose** — Full production stack (API + Celery + Redis + Postgres)
6. **GPU support** — CUDA-enabled Docker image
7. **Monitoring** — Prometheus + Grafana for job queue metrics
8. **CI/CD** — GitHub Actions: lint, test, build Docker image
9. **Documentation** — OpenAPI spec finalization, user guide
10. **Distribution** — Installer script or Electron app packaging

---

## Technical Debt to Address Before Production

| Item | Priority | Notes |
|------|----------|-------|
| Alembic migrations | High | Currently using create_all (no schema evolution) |
| Test suite | High | No automated tests yet |
| API authentication | High | All endpoints currently open |
| PostgreSQL support | Medium | SQLite not suitable for production |
| WebSocket progress | Medium | Current polling is inefficient for mobile |
| File cleanup | Medium | Processed files accumulate indefinitely |
| GPU task routing | Medium | Celery queue routing for GPU vs CPU tasks |
| Error retry logic | Low | Max retries set but no backoff strategy |
