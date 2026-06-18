# Phase 5 — Milestone 3: Karaoke Video Output Modes

**Status:** Complete (awaiting review)

## Implemented modes

| `output_mode` | Behavior |
|---------------|----------|
| `karaoke_video_with_vocals` | Default. Whisper on mixed audio → txt/srt/vtt/ass → burn on original video |
| `karaoke_video_no_vocals` | Inline Demucs → Whisper on vocals stem → txt/srt/vtt/ass → instrumental audio + burn |

## API examples

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "karaoke"
}
```

```json
POST /api/v1/jobs
{
  "media_id": "<uuid>",
  "job_type": "karaoke",
  "parameters": {
    "output_mode": "karaoke_video_no_vocals"
  }
}
```

## Completed metadata

### `karaoke_video_with_vocals`

```json
{
  "output_mode": "karaoke_video_with_vocals",
  "whisper_model": "base",
  "intermediate_files": { "audio": "..._audio.wav" },
  "result_files": {
    "transcript": "..._transcript.txt",
    "srt": "..._subtitles.srt",
    "vtt": "..._subtitles.vtt",
    "ass": "..._karaoke.ass",
    "video": "..._karaoke.mp4"
  }
}
```

No `stem_origin` (no separation).

### `karaoke_video_no_vocals`

```json
{
  "output_mode": "karaoke_video_no_vocals",
  "stem_origin": "inline",
  "separation_model": "htdemucs",
  "intermediate_files": {
    "separation_input": "..._separation_input.wav",
    "instrumental_video": "..._instrumental_video.mp4"
  },
  "result_files": {
    "transcript": "...",
    "srt": "...",
    "vtt": "...",
    "ass": "...",
    "video": "...",
    "vocals": "..._vocals.wav",
    "instrumental": "..._instrumental.wav"
  }
}
```

## Downloads

| Artifact | Endpoint |
|----------|----------|
| transcript / srt / vtt | `/jobs/{id}/download/{transcript\|srt\|vtt}` |
| ass | `/jobs/{id}/download/ass` |
| mp4 | `/jobs/{id}/download/karaoke-video` |
| vocals / instrumental | `/jobs/{id}/download/vocals` or `/instrumental` (inline karaoke + vocal_separation) |

## Not yet implemented (Milestone 4)

- `vocals_only`
- `music_only`
- `separation_job_id` reuse
