# VoxClone — Known Bugs and Root Causes

**Branch:** `feature/source-separation`
**Last updated:** 2026-06-18
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

### Fix Applied — `app/tasks/celery_app.py` + `app/tasks/async_runner.py`

Initial fix connected Redis in `worker_process_init`. A later refinement (Bug 9)
replaced `asyncio.run()` with a **persistent worker event loop** so the Redis
client and task coroutines share the same loop.

```python
# celery_app.py — worker_process_init
loop = get_worker_event_loop()
loop.run_until_complete(redis_service.connect())
```

**Verification:** Celery log shows `celery_worker_process_redis_connected` once
per worker process on startup; tasks reach `mark_started()` without Redis errors.

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

## Bug 7 — Unimplemented job types returned HTTP 500 ✅ FIXED

**Phase discovered:** 4  **Commit fixed:** `47be178`

### Symptom

Creating a job with `job_type: voice_replacement` or `voice_clone` created a DB
record in `queued` status, then the API returned HTTP 500 when dispatch failed.

### Root Cause

`JobType.ALL` includes planned types, but `_TASK_MAP` did not register tasks for
them. `create_job()` dispatched anyway and crashed.

### Fix Applied

`IMPLEMENTED_JOB_TYPES` derived from `_TASK_MAP`; `create_job()` returns HTTP 422
before creating a DB record for unregistered types.

---

## Bug 8 — Demucs WAV export fails (TorchCodec / unpinned PyTorch) ✅ FIXED

**Phase discovered:** 5  **Fix:** pinned ML stack in `requirements-ml.txt`

### Symptom

Demucs separation reached 100% then crashed saving stems:

```
ImportError: TorchCodec is required for save_with_torchcodec
RuntimeError: Could not load libtorchcodec
```

### Root Cause

Unpinned `pip install torch torchaudio` pulled TorchAudio ≥2.9, which routes
`torchaudio.save()` through TorchCodec. Demucs 4.0.1 calls `ta.save()` for WAV
export. Mismatched or missing TorchCodec wheels fail on CPU Ubuntu 24.04.

### Fix Applied

Pin matched pre-TorchCodec wheels in `backend/requirements-ml.txt`:

```
torch==2.8.0
torchaudio==2.8.0
demucs==4.0.1
```

See `docs/reports/PHASE5_M2_DEMUCS_DEPENDENCY_ANALYSIS.md` for validation evidence.

---

## Bug 9 — Redis `Future attached to a different loop` ✅ FIXED

**Phase discovered:** 5  **Fix:** `app/tasks/async_runner.py`

### Symptom

```
RuntimeError: Task ... got Future <Future pending> attached to a different loop
```

Failure at `vocal_separation_task` → `mark_started()` → `redis_service.set_progress()`.

### Root Cause

`worker_process_init` called `asyncio.run(redis_service.connect())`, creating and
**closing** event loop A. Each Celery task called `asyncio.run(_run())`, creating
a new loop B. The `redis.asyncio` client bound to loop A was reused on loop B.

All tasks calling `mark_started()` or `update_progress()` were vulnerable — not
only `vocal_separation_task`.

### Fix Applied

One persistent loop per worker process:

```python
# app/tasks/async_runner.py
def run_async(coro):
    return get_worker_event_loop().run_until_complete(coro)
```

- `worker_process_init` / `worker_process_shutdown`: `get_worker_event_loop().run_until_complete(...)`
- All Celery tasks: `return run_async(_run())` instead of `asyncio.run(_run())`

**Verification:** `mark_started()` and progress updates succeed after worker restart.

---

## No Known Open Bugs

As of Phase 7 M2 validation on `feature/whisper-multilingual`, no unresolved application bugs are known.

**Recently resolved (Phase 7):** Multilingual media was incorrectly transcribed with English-only Whisper models — fixed by language-first routing. See **Resolved Issue 1** below.

---

## Resolved Issues

### Resolved Issue 1 — English-only Whisper forced for all jobs ✅ FIXED (Phase 7 M2)

**Phase discovered:** 7 (multilingual validation)  
**Status:** Fixed in application code — routing, not model quality.

#### Symptom (before fix)

Mixed-language media (English introduction + Urdu content) on default `subtitle_generation` jobs:

- Model: `ggml-tiny.en.bin` regardless of content
- Output: English hallucinations, repeated subtitles, `(speaking in foreign language)`
- Karaoke: unusable transcript inherited from Whisper

#### Root Cause

`resolve_whisper_model()` mapped all size aliases to `.en.bin` files. `WHISPER_LANGUAGE=en` forced `-l en`. No multilingual models were installed or selectable.

#### Fix Applied

Phase 7 M2 — language-first routing in `whisper_models.py`:

- `language: "ur"` (and other non-English codes) → `ggml-{tier}.bin` + matching `-l`
- `language: "auto"` → multilingual model, omit `-l`
- Omitted `language` + `WHISPER_ROUTING_POLICY=english_first` → unchanged Phase 5 `.en` behaviour

#### Validation

Manual Urdu job: `language: ur`, `whisper_model: small` → `ggml-small.bin`, `detected_language: ur`, substantially improved subtitles.

Report: `docs/reports/PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md`

**Note:** Residual Urdu word errors are Whisper model-accuracy limits, not routing bugs.

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

### Limitation 2 — Urdu transcription accuracy on `ggml-small.bin`

**Phase discovered:** 7 (multilingual validation)  **Status:** Model-accuracy limitation, not a routing defect.

#### Symptom

Urdu subtitles after Phase 7 M2 routing fix are usable and contextually correct, but not word-perfect:

- Phonetic substitutions (e.g. expected **بیک گراؤنڈ**, observed **بیگروانٹ**)
- Occasional wrong word choice (e.g. expected **تھوڑا**, observed **کھوڑا**)
- English technical terms in Urdu speech not always recognised

#### Root Cause

Whisper multilingual `ggml-small.bin` word error rate on Urdu + code-mixed tutorial speech.
Routing correctly selects the multilingual model; remaining errors are ASR quality limits.

#### Mitigation

- Pass explicit `language: "ur"` (or `"auto"` for mixed media) — **required for non-English**
- Try larger multilingual model: `ggml-medium.bin` (Phase 7 M3 candidate)
- For English-only content, keep default `english_first` policy and `.en.bin` models
- Roman Urdu export: future milestone — see `PHASE7_M2_MULTILINGUAL_VALIDATION_REPORT.md` Section 11

---

## Bug Fix Order by Phase

```
Phase 2:
  Bug 1 (Redis) → Bug 2 (MissingGreenlet) → Bug 3 (LD_LIBRARY_PATH)

Phase 3:
  Bug 4 (filter escaping) → Bug 5 (no codec) → Bug 6 (route order)

Phase 4:
  Bug 7 (IMPLEMENTED_JOB_TYPES → HTTP 422)

Phase 5:
  Bug 8 (Demucs TorchCodec — pin torch 2.8.0)
  Bug 9 (async loop ownership — async_runner + run_async)
  Bug 1 refined: worker_process_init now uses persistent loop (see Bug 9)

Phase 7:
  Resolved Issue 1 (English-only Whisper forced — language-first routing)
```
