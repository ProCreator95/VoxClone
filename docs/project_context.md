---

> **DEPRECATED**
>
> This document is retained for historical reference only.
>
> **Reasons for deprecation:**
> - Early vision/requirements document; predates all implementation
> - Contains no implementation state, branch info, or phase completion status
> - Phase completion and architecture are fully documented in the authoritative handoff
> - Roadmap ordering does not match the current approved phase sequence
>
> **Use instead:**
> `docs/context/MASTER_PROJECT_HANDOFF.md` — single authoritative reference

---

Project Name: VoxClone

Mission:
VoxClone is an offline AI-powered media processing platform.

Primary Features:

1. Video Subtitle Generation
   - Upload video
   - Extract audio
   - Speech-to-text
   - Generate subtitles
   - Burn subtitles into video

2. Voice Replacement
   - Remove original speech
   - Replace with user audio
   - Export dubbed video

3. Karaoke Generation
   - Remove vocals
   - Export instrumental track

4. Voice Cloning
   - Convert one voice into another
   - Offline processing only

5. Audio Enhancement
   - Noise removal
   - Voice enhancement

Requirements:

- CPU-only friendly
- No real-time processing
- Background jobs
- Users upload media
- AI processes asynchronously
- Users download results later

Tech Stack:

Frontend:
- Flutter

Backend:
- FastAPI
- SQLite
- Redis
- Celery

AI:
- whisper.cpp
- FFmpeg
- Demucs
- OpenVoice
- DeepFilterNet
- Piper

Supported Formats:

Video:
- mp4
- webm
- mov
- mkv
- avi

Audio:
- mp3
- wav
- flac
- m4a

Architecture Rules:

- Modular design
- Service-based architecture
- Async APIs
- Background task processing
- Docker-ready
- Future PostgreSQL support
- Type hints everywhere
- Pydantic v2
- Structured logging
- Progress tracking

Development Rule:

Build one complete pipeline at a time.

Pipeline 1:
Upload Video → Extract Audio → Generate Subtitles → Burn Subtitles → Download Video

Do not implement voice cloning until subtitle pipeline is complete.
