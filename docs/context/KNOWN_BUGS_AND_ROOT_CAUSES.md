# VoxClone — Known Bugs and Root Causes

**Branch:** `feature/karaoke-generation`
**Last updated:** 2026-06-15
**All bugs listed here have been fixed. See "Known Limitations" at the bottom for non-bug behavioural constraints.**

---

## Bug 1 — RedisService not connected inside Celery workers ✅ FIXED

**Phase discovered:** 2  **Commit fixed:** `94f77e0`

### Symptom

After a `subtitle_generation` job is dispatched:
- Celery worker log shows `Using selector: EpollSelector` (task received)
- Redis queue is consumed (task dequeued)
- Job remains `status=queued`, `progress=0`, `started_at=NULL` indefinitely

### Root Cause

`redis_service.connect()` is called only inside the FastAPI lifespan hook.
Celery workers fork a new OS process and never execute that lifespan.
`redis_service._client` is `None` in every worker process.

The first call to `redis_service.set_progress()` inside `mark_started()` raises
`RuntimeError("RedisService not connected")`. This propagates out of the
`get_db_context()` block, triggering a DB rollback. The job row reverts to
`status=queued`. `mark_failed()` is never called because it is inside the
inner try/except block that the exception skipped past.

### Fix Applied — `app/tasks/celery_app.py`

```python
@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
    """Called inside each forked worker process."""
    setup_logging()
    from app.services.redis_service import redis_service
    asyncio.run(redis_service.connect())
    logger.info("celery_worker_process_redis_connected")
```

**Verification:** Celery log shows `celery_worker_process_redis_connected` once
per worker process on startup.

---

## Bug 2 — SQLAlchemy async lazy-loading of `job.media` ✅ FIXED

**Phase discovered:** 2  **Commit fixed:** `94f77e0`

### Symptom

After Bug 1 was fixed, the task immediately raised:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here.
```

### Root Cause

`Job.media` is defined with `lazy="select"`. In SQLAlchemy 2.x async, implicit
lazy-loading raises `MissingGreenlet` because there is no `await` in scope to
issue the implicit SELECT. The first access of `job.media` after `mark_started()`
returned triggered this error.

### Fix Applied — `app/services/job_service.py`

Added `get_by_id_with_media()` using `selectinload(Job.media)`.
`mark_started()` now calls this instead of `get_by_id()`.
`expire_on_commit=False` on `AsyncSessionLocal` ensures the pre-loaded
`Media` object is accessible after the session closes.

```python
async def get_by_id_with_media(self, job_id: str) -> Job:
    result = await self._db.execute(
        select(Job)
        .options(selectinload(Job.media))
        .where(Job.id == job_id)
    )
    ...
```

**Verification:** Celery log shows `diag_job_media_preloaded` with non-None
`media_id` and `media_type`.

---

## Bug 3 — whisper.cpp shared libraries not found ✅ FIXED

**Phase discovered:** 2  **Commit fixed:** `94f77e0`

### Symptom

```
libwhisper.so.1 => not found
libggml.so.0 => not found
```

The whisper-cli subprocess exited non-zero before transcribing anything.

### Root Cause

The `whisper-cli` binary links against `libwhisper.so.1` and `libggml.so.0`
which live in the whisper.cpp build tree (`build/src/` and `build/ggml/src/`).
Those directories were not on `LD_LIBRARY_PATH` for the Celery worker process.

### Fix Applied — `app/services/whisper_service.py`

Added `_build_subprocess_env()` that derives both library directories from the
binary path via `pathlib` and prepends them to `LD_LIBRARY_PATH`:

```python
@staticmethod
def _build_subprocess_env(binary: str) -> dict[str, str]:
    build_dir       = Path(binary).parent.parent
    whisper_lib_dir = build_dir / "src"
    ggml_lib_dir    = build_dir / "ggml" / "src"
    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = (
        f"{whisper_lib_dir}:{ggml_lib_dir}"
        + (f":{existing}" if existing else "")
    )
    return env
```

**Verification:** Celery log shows `whisper_cpp_ld_library_path` (DEBUG level)
with the two resolved paths; job proceeds to `subtitle_task_done`.

---

## Bug 4 — FFmpeg subtitle filter path not escaped ✅ FIXED

**Phase discovered:** 3  **Commit fixed:** `2f9f643`

### Symptom

Any `subtitle_burn` job would fail with an FFmpeg filter error:

```
Option subtitles not found.
```

or produce silent filter corruption when the SRT path contained a space.

### Root Cause

The FFmpeg `subtitles=` filter embeds the SRT file path directly in a filter
string using the syntax `subtitles=<path>:force_style='...'`. FFmpeg filter
syntax uses `:` as the option separator and `\` as the escape character.

The project path is `/home/shz/Documents/Mustafa projects/VoxClone/...`.
The space in `Mustafa projects` was not causing an immediate failure, but any
colon in the path would silently split the filter string, and the unescaped
form was brittle for any environment where `PROCESSED_DIR` contained
special characters.

The original code:
```python
subtitle_filter = f"subtitles={str(srt_path)}:force_style='FontSize={font_size}'"
```

### Fix Applied — `app/services/ffmpeg_service.py`

Added `_escape_filter_path()` as a static method:

```python
@staticmethod
def _escape_filter_path(path: Path) -> str:
    s = str(path)
    s = s.replace("\\", "\\\\")  # must come first
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s
```

The corrected filter construction:
```python
escaped = self._escape_filter_path(srt_path)
subtitle_filter = f"subtitles={escaped}:force_style='{force_style}'"
```

**Verification:** Phase 3 validated run produced a correctly subtitled MP4 at
job `c4263f06-ef6d-4005-91e8-d422fb00be26`.

---

## Bug 5 — No explicit video codec in burn command ✅ FIXED

**Phase discovered:** 3  **Commit fixed:** `2f9f643`

### Symptom

Without an explicit video codec, FFmpeg selected its default for `.mp4` output,
which could be `mpeg4` (lower compatibility) instead of `libx264` (universally
supported). Output quality and player compatibility were undefined.

### Root Cause

The original `burn_subtitles()` command specified `-c:a copy` but omitted any
`-c:v` flag. FFmpeg defaulted to `mpeg4` for `.mp4` containers.

### Fix Applied — `app/services/ffmpeg_service.py`

Added `-c:v libx264 -crf 23 -preset fast` to the FFmpeg command:

```python
cmd = [
    self.ffmpeg,
    "-i", str(video_path),
    "-vf", subtitle_filter,
    "-c:v", "libx264",
    "-crf", "23",
    "-preset", "fast",
    "-c:a", "copy",
    "-y",
    str(output_path),
]
```

**Verification:** `ffprobe` on Phase 3 output confirms `Video: h264 (High)`.

---

## Bug Fix Order by Phase

```
Phase 2:
  Bug 1 (Redis) → Bug 2 (MissingGreenlet) → Bug 3 (LD_LIBRARY_PATH) → Phase 2 working

Phase 3:
  Bug 4 (filter escaping) → Bug 5 (no codec) → Phase 3 working
```

---

## Bug 6 — FastAPI route ordering: `download/video` shadowed by `download/{format_type}` ✅ FIXED

**Phase discovered:** 3 (post-validation)  **Commit fixed:** after `2f9f643`

### Symptom

```
GET /api/v1/jobs/<burn_job_id>/download/video

HTTP 422 Unprocessable Entity
{
  "detail": [{
    "type": "literal_error",
    "loc": ["path", "format_type"],
    "msg": "Input should be 'transcript', 'srt' or 'vtt'",
    "input": "video"
  }]
}
```

### Root Cause

FastAPI registers and matches routes in **declaration order**. The parameterised
route `/{job_id}/download/{format_type}` was declared before the literal route
`/{job_id}/download/video`. When a request arrived for `/download/video`, FastAPI
matched the first route, captured `"video"` as `format_type`, and the
`Literal["transcript", "srt", "vtt"]` validator rejected it. The dedicated
`download_burned_video` handler was never reached.

### Fix Applied — `app/api/v1/endpoints/jobs.py`

Swapped the declaration order: `download_burned_video` (`/{job_id}/download/video`)
is now declared **before** `download_subtitle_format` (`/{job_id}/download/{format_type}`).

Added an explanatory comment above the first route so future developers cannot
inadvertently reverse this ordering:

```python
# ── IMPORTANT: route order matters in FastAPI ─────────────────────────────────
# download/video MUST be declared before download/{format_type}.
# FastAPI matches routes in declaration order.  If the parameterised route came
# first, "video" would be captured as format_type and rejected by the Literal
# validator before the dedicated handler is ever considered.
```

No logic changes were made to either handler.

**Verification:** `GET /jobs/<burn_job_id>/download/video` now returns HTTP 200
with `Content-Type: video/mp4`.

---

## No Known Open Bugs

As of Phase 4 (pre-commit), no unresolved bugs are known.

---

## Known Limitations (not bugs)

### Limitation 1 — Whisper `ggml-tiny.en.bin` drops lyrics on music-heavy content

**Phase discovered:** 4 (karaoke validation)  **Status:** Not fixable in application code.

#### Symptom

The karaoke output (and the plain subtitle output) contains silent gaps of
20–30 s at positions that clearly contain sung lyrics in the source video.
The karaoke video plays correctly for the transcribed segments but shows no
subtitle text during the gaps.

#### Investigation

Cross-referencing two independent transcription runs on the same media file:

| Run | Job ID | Flag | Gap 1 | Gap 2 |
|-----|--------|------|-------|-------|
| `subtitle_generation` | `d69ee4aa-...` | `--output-json` | 0:57.340 → 1:24.760 | 2:49.240 → 3:19.240 |
| `karaoke` | `0e44f8ef-...` | `--output-json-full` | 0:57.340 → 1:24.760 | 2:49.240 → 3:19.240 |

Both runs produced **identical timestamps and identical segment counts (76)**,
proving the gaps originate in whisper.cpp output before any application code
processes the data.  The tiny model emitted `(upbeat music)` at 0:54.76 →
0:57.34, then produced no segments for the subsequent ~27 s instrumental
section.  The karaoke pipeline renders exactly what Whisper transcribes.

#### Root Cause

`ggml-tiny.en.bin` has limited accuracy on overlapping music and vocals.
During instrumental sections with no dominant speech, the model either:
- Produces a generic placeholder (e.g. `(upbeat music)`) and then skips, or
- Generates no output at all for that time range.

This is a known characteristic of small Whisper models on music content, not
a defect in the transcription parsing code, the ASS generation, or the karaoke
video rendering.

#### Mitigation

Switch to a larger model in `backend/.env`:

```bash
# Better for music/vocals (already downloaded)
WHISPER_MODEL_PATH=models/ggml-base.en.bin    # 142 MB — recommended for music
WHISPER_MODEL_PATH=models/ggml-small.en.bin   # 466 MB — highest accuracy
```

Both `ggml-base.en.bin` and `ggml-small.en.bin` are already present in
`backend/models/`.  No code changes are required.

---

## Bug Fix Order by Phase

```
Phase 2:
  Bug 1 (Redis) → Bug 2 (MissingGreenlet) → Bug 3 (LD_LIBRARY_PATH) → Phase 2 working

Phase 3:
  Bug 4 (filter escaping) → Bug 5 (no codec) → Bug 6 (route order) → Phase 3 working

Phase 4:
  No bugs found. One pre-existing issue fixed: voice_replacement/voice_clone
  returned HTTP 500; now returns HTTP 422 via IMPLEMENTED_JOB_TYPES guard.
```
