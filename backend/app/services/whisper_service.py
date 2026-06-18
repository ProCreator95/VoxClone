from __future__ import annotations

"""
WhisperService — speech-to-text transcription via whisper.cpp.

Invokes the whisper.cpp CLI binary as an async subprocess.
No Python ML dependencies (no PyTorch, no CUDA, no openai-whisper).

Configuration (all from Settings / .env):
    WHISPER_CPP_BINARY  — name or absolute path of the whisper-cli binary
    WHISPER_MODEL_PATH  — absolute or relative path to a GGML model file
    WHISPER_THREADS     — CPU thread count passed to whisper.cpp (-t)
    WHISPER_LANGUAGE    — BCP-47 code (e.g. "en") or "" for auto-detect

Supported model files (English-only, CPU-optimised):
    ggml-tiny.en.bin    ~75 MB   fastest, lowest accuracy
    ggml-base.en.bin   ~142 MB   good balance
    ggml-small.en.bin  ~466 MB   higher accuracy, slower

Usage::

    svc = WhisperService()
    await svc.validate()            # raises RuntimeError if setup is wrong
    result = await svc.transcribe(Path("audio.wav"))
    result.to_srt()                 # SubRip subtitle string
    result.to_vtt()                 # WebVTT subtitle string
    result.to_txt()                 # plain-text transcript
"""

import asyncio
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.whisper_models import (
    model_missing_message,
    resolve_whisper_model,
)

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class WordTimestamp:
    """Word-level timing extracted from whisper.cpp --output-json-full token data.

    whisper.cpp BPE tokens are grouped into words by the leading-space boundary
    convention: a token whose text starts with " " begins a new word; tokens
    without a leading space are sub-word continuations (e.g. "'s", ".").

    Populated only when transcribe(word_timestamps=True) is used.
    """

    word:       str
    start:      float   # seconds
    end:        float   # seconds
    confidence: float = 0.0  # average BPE token probability (0.0–1.0); for diagnostics


@dataclass
class WhisperSegment:
    """A single timed subtitle segment."""

    start: float    # seconds
    end:   float    # seconds
    text:  str
    words: list["WordTimestamp"] = field(default_factory=list)
    # Populated when transcribe(word_timestamps=True) is used.
    # Empty list when word timestamps were not requested or the token
    # array was absent from the JSON (graceful fallback for older builds).


@dataclass
class TranscriptResult:
    """
    Complete transcription output with helpers for common subtitle formats.

    Attributes:
        segments:  Ordered list of timed segments (start/end in seconds).
        language:  BCP-47 language tag reported by whisper.cpp (e.g. "en").
        text:      Full concatenated plain-text transcript.
    """

    segments: list[WhisperSegment] = field(default_factory=list)
    language: str = ""
    text: str = ""

    # ── Format converters ──────────────────────────────────────────────────────

    def to_txt(self) -> str:
        """Return the plain-text transcript."""
        if self.text.strip():
            return self.text.strip()
        return "\n".join(seg.text.strip() for seg in self.segments if seg.text.strip())

    def to_srt(self) -> str:
        """Return SubRip (SRT) subtitle content."""
        lines: list[str] = []
        for i, seg in enumerate(self.segments, start=1):
            lines.append(str(i))
            lines.append(f"{_srt_time(seg.start)} --> {_srt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """Return WebVTT subtitle content."""
        lines: list[str] = ["WEBVTT", ""]
        for seg in self.segments:
            lines.append(f"{_vtt_time(seg.start)} --> {_vtt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_ass(
        self,
        highlight_color: str = "&H0000FFFF&",
        base_color:      str = "&H00FFFFFF&",
        font_name:       str = "Arial",
        font_size:       int = 24,
        play_res_x:      int = 1280,
        play_res_y:      int = 720,
    ) -> str:
        """Return Advanced SubStation Alpha (ASS) subtitle content with karaoke timing.

        When word-level timestamps are present on segments (populated by
        transcribe(word_timestamps=True)), each Dialogue line uses \\kf
        karaoke timing tags so each word highlights at its exact spoken time.

        ASS colour format: &HAABBGGRR& (alpha, blue, green, red).
        Examples: &H0000FFFF& = yellow (G=FF R=FF), &H00FFFFFF& = white.
        PrimaryColour  = highlight_color — the colour a word shows when its
                         \\kf fill sweep arrives.
        SecondaryColour = base_color    — the colour words show before their
                         turn, and any words after the last \\kf has expired.

        Falls back to plain Dialogue lines (no \\kf tags) when word timestamps
        are unavailable, preserving usefulness for audio-only or fallback runs.
        This graceful degradation is intentional: the karaoke task succeeds
        with plain subtitles rather than failing when word timestamps are absent
        (e.g. very old whisper.cpp builds or segments where all tokens are
        special markers).
        """
        # ── Script Info ───────────────────────────────────────────────────────
        header = (
            "[Script Info]\n"
            "Title: VoxClone Karaoke\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 0\n"
            f"PlayResX: {play_res_x}\n"
            f"PlayResY: {play_res_y}\n"
            "ScaledBorderAndShadow: yes\n"
            "\n"
            # ── V4+ Styles ────────────────────────────────────────────────────
            # PrimaryColour / SecondaryColour drive the \kf highlight effect.
            # The order of fields in the Format line is fixed by the ASS spec;
            # libass ignores unrecognised fields but is strict about count.
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{font_name},{font_size},"
            f"{highlight_color},{base_color},"
            "&H00000000&,&H80000000&,"
            "0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,0\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text\n"
        )

        dialogue_lines: list[str] = []
        for seg in self.segments:
            start_ts = _ass_time(seg.start)
            end_ts   = _ass_time(seg.end)

            if seg.words:
                text = _build_karaoke_text(seg)
            else:
                # No word timestamps — plain subtitle text.
                # Karaoke \kf effect is silently omitted rather than crashing.
                text = seg.text.strip()

            dialogue_lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}"
            )

        return header + "\n".join(dialogue_lines) + "\n"

    @property
    def is_empty(self) -> bool:
        return not self.segments and not self.text.strip()


# ── Timestamp Formatters ──────────────────────────────────────────────────────

def _srt_time(seconds: float) -> str:
    """Float seconds → SRT timestamp  HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = min(999, int(round((seconds % 1) * 1000)))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(seconds: float) -> str:
    """Float seconds → VTT timestamp  HH:MM:SS.mmm"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = min(999, int(round((seconds % 1) * 1000)))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _parse_vtt_time(ts: str) -> float:
    """Parse a VTT/SRT timestamp string into float seconds (fallback parser)."""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except (ValueError, IndexError):
        pass
    return 0.0


def _ass_time(seconds: float) -> str:
    """Float seconds → ASS timestamp  H:MM:SS.cc  (centiseconds, not milliseconds).

    ASS uses centiseconds (2 decimal digits) unlike SRT/VTT which use milliseconds.
    The hour field is NOT zero-padded in ASS format.
    """
    seconds = max(0.0, seconds)
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = min(99, int(round((seconds % 1) * 100)))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _build_karaoke_text(seg: "WhisperSegment") -> str:
    r"""Build the \kf-tagged text string for a single ASS Dialogue line.

    \kf timing strategy:
        word[i]  duration = (word[i+1].start - word[i].start)  * 100  centiseconds
        last word duration = (segment.end    - last_word.start) * 100  centiseconds

    This keeps each word highlighted until the next word begins, which naturally
    bridges inter-word gaps (pauses) without extra logic.

    A pre-roll slot is emitted when the first word starts after the segment
    start — the subtitle is visible but nothing is highlighted during the gap.

    Minimum 1 centisecond is enforced for every \kf value to handle
    zero-duration tokens confirmed in actual whisper.cpp output
    (e.g. tokens at a segment boundary where offsets.from == offsets.to).

    Pre-roll note — consecutive \kf tags with empty text between them:
        The pre-roll emits {\kfN} immediately before the first word's {\kfM}
        tag, producing output like {\kf20}{\kf144}word.  Per the ASS
        specification (Aegisub/libass), \kf defines the duration of the TEXT
        that follows it; when no text exists between two \kf tags the empty
        "syllable" consumes N centiseconds without any visual change.  This is
        the correct and standard way to express a pre-roll gap in ASS karaoke
        and is handled identically by libass (FFmpeg, VLC, MPV), DirectVobSub
        (MPC-HC/MPC-BE), and VSFilter.  Karaoke editing tools such as Aegisub
        generate the same pattern.  The implementation is NOT changed for
        aesthetic reasons; the portability evidence is conclusive.
    """
    words = seg.words
    parts: list[str] = []

    # Pre-roll: emit a silent \kf slot so the full subtitle line is visible
    # before speech begins, giving the viewer time to read ahead.
    # See pre-roll note above for why an empty \kf tag is correct here.
    pre_roll_cs = max(0, int((words[0].start - seg.start) * 100))
    if pre_roll_cs > 0:
        parts.append(f"{{\\kf{pre_roll_cs}}}")

    for i, word in enumerate(words):
        if i < len(words) - 1:
            kf_cs = max(1, int((words[i + 1].start - word.start) * 100))
        else:
            kf_cs = max(1, int((seg.end - word.start) * 100))

        suffix = " " if i < len(words) - 1 else ""
        parts.append(f"{{\\kf{kf_cs}}}{word.word}{suffix}")

    return "".join(parts)


# ── Binary Resolver ───────────────────────────────────────────────────────────

def _resolve_binary(binary: str) -> str:
    """
    Return the resolved executable path for the whisper.cpp binary.

    Accepts:
      - A bare name  ("whisper-cli")  → searched on PATH via shutil.which
      - A relative path ("./main")    → resolved from cwd
      - An absolute path              → validated directly

    Raises RuntimeError with a clear, actionable message if not found.
    """
    # Absolute path or explicitly relative path (contains a slash)
    if os.sep in binary or (os.altsep and os.altsep in binary) or binary.startswith("."):
        p = Path(binary).resolve()
        if p.is_file() and os.access(str(p), os.X_OK):
            return str(p)
        raise RuntimeError(
            f"whisper.cpp binary not found or not executable: {binary}\n\n"
            "Possible fixes:\n"
            "  1. Build whisper.cpp: cd whisper.cpp && make -j\n"
            "  2. Set WHISPER_CPP_BINARY to the correct absolute path in .env\n"
            "  3. See: docs/testing/WHISPER_CPP_SETUP.md"
        )

    # Bare name — search PATH
    found = shutil.which(binary)
    if found:
        return found

    raise RuntimeError(
        f"whisper.cpp binary '{binary}' not found on PATH.\n\n"
        "Possible fixes:\n"
        "  1. Build and install whisper.cpp (see docs/testing/WHISPER_CPP_SETUP.md)\n"
        "  2. Add the build directory to PATH, or\n"
        "  3. Set WHISPER_CPP_BINARY=/absolute/path/to/whisper-cli in .env"
    )


# ── WhisperService ────────────────────────────────────────────────────────────

class WhisperService:
    """
    Invoke whisper.cpp as an async subprocess and return a TranscriptResult.

    Binary and thread settings come from Settings.  The GGML model file is
    selected per call via ``whisper_model`` + ``job_type`` (see whisper_models.py).
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_binary() -> None:
        """Ensure the whisper.cpp CLI binary is present and executable."""
        settings = get_settings()
        _resolve_binary(settings.WHISPER_CPP_BINARY)

    @staticmethod
    def _validate_model_file(model_path: Path, alias: str) -> None:
        if not model_path.exists():
            raise RuntimeError(model_missing_message(model_path, alias))

    async def validate(
        self,
        whisper_model: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> None:
        """
        Verify the environment is ready for transcription.

        Checks (in order):
          1. The whisper.cpp binary is present and executable.
          2. The resolved GGML model file exists.

        Raises RuntimeError with an actionable message on the first failure.
        """
        self._validate_binary()
        alias, model_path = resolve_whisper_model(
            whisper_model, job_type or "", self._settings
        )
        self._validate_model_file(model_path, alias)

    async def is_available(self) -> bool:
        """Return True if both the binary and model file are present."""
        try:
            await self.validate()
            return True
        except RuntimeError:
            return False

    async def transcribe(
        self,
        audio_path:      Path,
        language:        Optional[str] = None,
        word_timestamps: bool = False,
        whisper_model:   Optional[str] = None,
        job_type:        Optional[str] = None,
    ) -> TranscriptResult:
        """
        Transcribe *audio_path* using whisper.cpp and return a TranscriptResult.

        Args:
            audio_path:       Path to a 16kHz mono WAV file (FFmpegService.extract_audio
                              produces this format automatically).
            language:         BCP-47 language code override (e.g. "en").
                              Falls back to WHISPER_LANGUAGE from settings.
                              Pass None or "" to let whisper.cpp auto-detect.
            word_timestamps:  When True, passes --output-json-full to whisper.cpp
                              instead of the standard --output-json.  The resulting
                              BPE token array is grouped into WordTimestamp objects
                              by _tokens_to_words() and attached to each segment's
                              .words list.  Defaults to False so the subtitle_generation
                              pipeline is completely unaffected.
            whisper_model:    Optional alias (tiny / base / small).  When omitted,
                              ``job_type`` selects the default model for that pipeline.
            job_type:         Job type string used with ``whisper_model`` resolution.

        Raises:
            FileNotFoundError  if audio_path does not exist.
            RuntimeError       if the binary or model is misconfigured, or if
                               whisper.cpp exits with a non-zero return code.
        """
        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}\n"
                "Ensure FFmpeg audio extraction completed successfully."
            )

        resolved_alias, model_path = resolve_whisper_model(
            whisper_model, job_type or "", self._settings
        )
        self._validate_binary()
        self._validate_model_file(model_path, resolved_alias)

        binary  = _resolve_binary(self._settings.WHISPER_CPP_BINARY)
        threads = self._settings.WHISPER_THREADS
        lang    = language or self._settings.WHISPER_LANGUAGE or None

        logger.info(
            "whisper_cpp_transcribe_start",
            binary=binary,
            whisper_model=resolved_alias,
            model=model_path.name,
            language=lang or "auto",
            threads=threads,
            audio=str(audio_path),
            word_timestamps=word_timestamps,
            job_type=job_type,
        )

        result = await self._run_subprocess(
            binary, model_path, audio_path, threads, lang, word_timestamps
        )

        logger.info(
            "whisper_cpp_transcribe_done",
            language=result.language,
            segments=len(result.segments),
            word_timestamps=word_timestamps,
            total_words=sum(len(s.words) for s in result.segments),
        )
        return result

    # ── Subprocess execution ──────────────────────────────────────────────────

    @staticmethod
    def _build_subprocess_env(binary: str) -> dict[str, str]:
        """
        Return a copy of the current environment with the whisper.cpp shared
        library directories prepended to LD_LIBRARY_PATH.

        whisper.cpp links against libwhisper.so and libggml.so, which live
        inside the build tree alongside the binary.  When the binary is an
        absolute path (as resolved by _resolve_binary), the standard layout is:

            <build>/bin/whisper-cli      ← binary
            <build>/src/                 ← libwhisper.so.1
            <build>/ggml/src/            ← libggml.so.0

        Both directories are prepended so the dynamic linker finds them before
        any system paths, regardless of whether ldconfig was run.
        """
        build_dir = Path(binary).parent.parent  # <build>/bin → <build>
        whisper_lib_dir = build_dir / "src"
        ggml_lib_dir = build_dir / "ggml" / "src"

        env = os.environ.copy()
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = (
            f"{whisper_lib_dir}:{ggml_lib_dir}"
            + (f":{existing}" if existing else "")
        )

        logger.debug(
            "whisper_cpp_ld_library_path",
            binary=binary,
            build_dir=str(build_dir),
            whisper_lib_dir=str(whisper_lib_dir),
            ggml_lib_dir=str(ggml_lib_dir),
            LD_LIBRARY_PATH=env["LD_LIBRARY_PATH"],
        )
        return env

    async def _run_subprocess(
        self,
        binary:          str,
        model_path:      Path,
        audio_path:      Path,
        threads:         int,
        language:        Optional[str],
        word_timestamps: bool = False,
    ) -> TranscriptResult:
        """Run whisper.cpp in a temp directory, parse JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = Path(tmpdir) / "output"

            # --output-json-full is used instead of the simpler --word-timestamps flag
            # for two reasons:
            #   1. --output-json-full is available in all whisper.cpp builds from
            #      mid-2023 onward; --word-timestamps that adds a "words" array
            #      directly to each segment was introduced later and is absent from
            #      many installed versions.
            #   2. --output-json-full gives BPE token-level data (offsets + text per
            #      token), which _tokens_to_words() groups into proper words by the
            #      leading-space boundary convention.  This produces higher-quality
            #      word boundaries than whisper.cpp's own grouping, which sometimes
            #      runs punctuation into the preceding word.
            # Standard --output-json omits the tokens array entirely, so the existing
            # subtitle_generation pipeline is completely unaffected (word_timestamps
            # defaults to False).
            json_flag = "--output-json-full" if word_timestamps else "--output-json"

            cmd: list[str] = [
                binary,
                "-m", str(model_path),
                "-f", str(audio_path),
                "-t", str(threads),
                json_flag,
                "-of", str(output_prefix),
            ]
            if language:
                cmd.extend(["-l", language])

            env = self._build_subprocess_env(binary)
            logger.debug("whisper_cpp_cmd", cmd=" ".join(cmd))

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await process.communicate()

            stderr_text = stderr_bytes.decode(errors="replace")

            if process.returncode != 0:
                raise RuntimeError(
                    f"whisper.cpp exited with code {process.returncode}.\n\n"
                    f"Command: {' '.join(cmd)}\n\n"
                    f"stderr (last 800 chars):\n{stderr_text[-800:]}\n\n"
                    "Common causes:\n"
                    "  • Model file is corrupt — re-download it\n"
                    "  • Audio file format is not 16kHz mono WAV\n"
                    "  • Binary was built for a different architecture\n"
                    "  See: docs/testing/WHISPER_CPP_SETUP.md"
                )

            json_path = output_prefix.with_suffix(".json")
            if not json_path.exists():
                # Some whisper.cpp builds write <audio_basename>.json alongside the audio
                fallback = audio_path.with_suffix(".json")
                if fallback.exists():
                    json_path = fallback
                else:
                    raise RuntimeError(
                        f"whisper.cpp ran successfully (exit 0) but produced no JSON file.\n"
                        f"Expected: {json_path}\n\n"
                        f"stderr: {stderr_text[-400:]}\n\n"
                        "Try upgrading whisper.cpp — older builds may use a different "
                        "output flag. See: docs/testing/WHISPER_CPP_SETUP.md"
                    )

            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

        return self._parse_json(data)

    # ── JSON parser ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(data: dict) -> TranscriptResult:
        """
        Parse whisper.cpp JSON into a TranscriptResult.

        Handles two JSON layouts (old and new whisper.cpp builds):

        Layout A (preferred — uses millisecond offsets):
            {"transcription": [{"offsets": {"from": 0, "to": 2340}, "text": "..."}]}

        Layout B (fallback — uses timestamp strings like SRT format):
            {"transcription": [{"timestamps": {"from": "00:00:00,000", "to": "..."}, "text": "..."}]}

        When --output-json-full is used (word_timestamps=True), each segment
        also contains a "tokens" array.  _tokens_to_words() groups BPE tokens
        into WordTimestamp objects using the leading-space word-boundary
        convention.  The tokens key is absent from standard --output-json
        output, so this branch is a no-op for the subtitle_generation pipeline.
        """
        transcription: list[dict] = data.get("transcription") or []
        segments: list[WhisperSegment] = []

        for seg in transcription:
            text = str(seg.get("text") or "").strip()
            if not text:
                continue

            start = end = 0.0

            # Layout A: millisecond offsets (preferred)
            offsets = seg.get("offsets")
            if offsets and "from" in offsets and "to" in offsets:
                try:
                    start = float(offsets["from"]) / 1000.0
                    end = float(offsets["to"]) / 1000.0
                except (TypeError, ValueError):
                    pass

            # Layout B: string timestamps fallback
            elif (timestamps := seg.get("timestamps")):
                start = _parse_vtt_time(str(timestamps.get("from", "0")))
                end = _parse_vtt_time(str(timestamps.get("to", "0")))

            # Parse word-level tokens when present (--output-json-full output).
            # Absent in standard --output-json; safe to call on any data.
            words: list[WordTimestamp] = []
            raw_tokens = seg.get("tokens")
            if raw_tokens:
                words = WhisperService._tokens_to_words(raw_tokens)

            segments.append(WhisperSegment(start=start, end=end, text=text, words=words))

        language = str((data.get("result") or {}).get("language") or "")
        full_text = " ".join(seg.text for seg in segments)

        return TranscriptResult(segments=segments, language=language, text=full_text)

    @staticmethod
    def _tokens_to_words(tokens: list[dict]) -> list[WordTimestamp]:
        """Group whisper.cpp BPE tokens into word-level WordTimestamp objects.

        BPE tokenisation convention: tokens whose text starts with " " mark the
        beginning of a new word.  Tokens without a leading space are sub-word
        continuations appended to the preceding group:
            " today" + "'s"  → "today's"
            " It"    + "'s"  → "It's"
            " class" + "."   → "class."

        Special timing/boundary markers are identified by their bracket-wrapped
        text pattern rather than by token id, so future whisper.cpp releases
        that add new marker names are handled without code changes:
            [_BEG_]   — segment-start marker
            [_TT_N]   — timestamp slot markers (observed: _TT_250, _TT_400)
        """
        words: list[WordTimestamp] = []
        current_group: list[dict] = []

        for tok in tokens:
            text    = tok.get("text", "")
            stripped = text.strip()

            # Skip whisper.cpp internal markers such as [_BEG_] and [_TT_N].
            # Matching by text pattern rather than token id to stay robust
            # across whisper.cpp versions.
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            if not stripped:
                continue

            # A leading space is the BPE word-boundary signal.
            if text.startswith(" "):
                if current_group:
                    words.append(WhisperService._group_to_word(current_group))
                current_group = [tok]
            else:
                # No leading space = sub-word continuation (contraction, punct)
                if current_group:
                    current_group.append(tok)
                else:
                    # First non-special token has no leading space (rare edge case)
                    current_group = [tok]

        if current_group:
            words.append(WhisperService._group_to_word(current_group))

        return words

    @staticmethod
    def _group_to_word(group: list[dict]) -> WordTimestamp:
        """Merge a BPE token group into a single WordTimestamp.

        start = first token's offsets.from (ms → seconds)
        end   = last  token's offsets.to   (ms → seconds)
        word  = concatenated token texts, stripped of leading/trailing whitespace
        """
        word_text      = "".join(t.get("text", "") for t in group).strip()
        offsets_first  = group[0].get("offsets", {})
        offsets_last   = group[-1].get("offsets", {})
        start_ms       = offsets_first.get("from", 0)
        end_ms         = offsets_last.get("to", start_ms)
        probs          = [t.get("p", 0.0) for t in group]
        confidence     = round(sum(probs) / len(probs), 4) if probs else 0.0

        return WordTimestamp(
            word=word_text,
            start=start_ms / 1000.0,
            end=end_ms   / 1000.0,
            confidence=confidence,
        )
