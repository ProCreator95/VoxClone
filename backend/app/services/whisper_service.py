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

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class WhisperSegment:
    """A single timed subtitle segment."""

    start: float    # seconds
    end: float      # seconds
    text: str


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

    All configuration is read from Settings.  No per-call model selection —
    the model is set once via WHISPER_MODEL_PATH in .env.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Public API ────────────────────────────────────────────────────────────

    async def validate(self) -> None:
        """
        Verify the environment is ready for transcription.

        Checks (in order):
          1. The whisper.cpp binary is present and executable.
          2. The GGML model file exists.

        Raises RuntimeError with an actionable message on the first failure.
        """
        # 1 — binary
        try:
            _resolve_binary(self._settings.WHISPER_CPP_BINARY)
        except RuntimeError:
            raise  # already has a good message

        # 2 — model file
        model_path = Path(self._settings.WHISPER_MODEL_PATH)
        if not model_path.exists():
            raise RuntimeError(
                f"whisper.cpp model file not found: {model_path}\n\n"
                "Download a model with:\n"
                "  bash scripts/download_whisper_model.sh tiny.en\n"
                "or manually:\n"
                "  mkdir -p models\n"
                "  wget -O models/ggml-tiny.en.bin \\\n"
                "    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin\n\n"
                "See: docs/testing/WHISPER_CPP_SETUP.md"
            )

    async def is_available(self) -> bool:
        """Return True if both the binary and model file are present."""
        try:
            await self.validate()
            return True
        except RuntimeError:
            return False

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptResult:
        """
        Transcribe *audio_path* using whisper.cpp and return a TranscriptResult.

        Args:
            audio_path:  Path to a 16kHz mono WAV file (FFmpegService.extract_audio
                         produces this format automatically).
            language:    BCP-47 language code override (e.g. "en").
                         Falls back to WHISPER_LANGUAGE from settings.
                         Pass None or "" to let whisper.cpp auto-detect.

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

        await self.validate()

        binary = _resolve_binary(self._settings.WHISPER_CPP_BINARY)
        model_path = Path(self._settings.WHISPER_MODEL_PATH)
        threads = self._settings.WHISPER_THREADS
        lang = language or self._settings.WHISPER_LANGUAGE or None

        logger.info(
            "whisper_cpp_transcribe_start",
            binary=binary,
            model=model_path.name,
            language=lang or "auto",
            threads=threads,
            audio=str(audio_path),
        )

        result = await self._run_subprocess(binary, model_path, audio_path, threads, lang)

        logger.info(
            "whisper_cpp_transcribe_done",
            language=result.language,
            segments=len(result.segments),
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
        binary: str,
        model_path: Path,
        audio_path: Path,
        threads: int,
        language: Optional[str],
    ) -> TranscriptResult:
        """Run whisper.cpp in a temp directory, parse JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = Path(tmpdir) / "output"

            cmd: list[str] = [
                binary,
                "-m", str(model_path),
                "-f", str(audio_path),
                "-t", str(threads),
                "--output-json",
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

            segments.append(WhisperSegment(start=start, end=end, text=text))

        language = str((data.get("result") or {}).get("language") or "")
        full_text = " ".join(seg.text for seg in segments)

        return TranscriptResult(segments=segments, language=language, text=full_text)
