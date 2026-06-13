from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.exceptions import FFmpegError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProbeResult:
    """Structured representation of ffprobe output."""

    duration: Optional[float] = None
    format_name: Optional[str] = None
    bitrate: Optional[int] = None

    # Video stream
    width: Optional[int] = None
    height: Optional[int] = None
    codec_video: Optional[str] = None
    fps: Optional[float] = None

    # Audio stream
    codec_audio: Optional[str] = None
    sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None

    raw: dict = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return self.codec_video is not None

    @property
    def has_audio(self) -> bool:
        return self.codec_audio is not None


async def _run(cmd: list[str], error_prefix: str) -> tuple[str, str]:
    """Run a subprocess and return (stdout, stderr). Raises FFmpegError on failure."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise FFmpegError(error_prefix, stderr=stderr.decode(errors="replace"))
    return stdout.decode(errors="replace"), stderr.decode(errors="replace")


class FFmpegService:
    """Wraps FFmpeg / ffprobe CLI tools for media operations."""

    def __init__(self) -> None:
        settings = get_settings()
        self.ffmpeg = settings.FFMPEG_PATH
        self.ffprobe = settings.FFPROBE_PATH

    # ── Probe ─────────────────────────────────────────────────────────────────

    async def probe(self, path: Path) -> ProbeResult:
        """Extract metadata from any media file via ffprobe."""
        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        logger.debug("ffprobe_start", path=str(path))
        stdout, _ = await _run(cmd, f"ffprobe failed for {path.name}")

        raw = json.loads(stdout)
        result = self._parse_probe(raw)
        logger.debug("ffprobe_done", path=str(path), duration=result.duration)
        return result

    def _parse_probe(self, raw: dict) -> ProbeResult:
        fmt = raw.get("format", {})
        streams = raw.get("streams", [])

        result = ProbeResult(raw=raw)

        try:
            result.duration = float(fmt["duration"])
        except (KeyError, ValueError, TypeError):
            pass

        try:
            result.bitrate = int(fmt["bit_rate"])
        except (KeyError, ValueError, TypeError):
            pass

        result.format_name = fmt.get("format_name")

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and result.codec_video is None:
                result.codec_video = stream.get("codec_name")
                result.width = stream.get("width")
                result.height = stream.get("height")
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = fps_str.split("/")
                    result.fps = round(int(num) / int(den), 3)
                except (ValueError, ZeroDivisionError):
                    pass

            elif codec_type == "audio" and result.codec_audio is None:
                result.codec_audio = stream.get("codec_name")
                try:
                    result.sample_rate = int(stream["sample_rate"])
                except (KeyError, ValueError, TypeError):
                    pass
                result.audio_channels = stream.get("channels")

        return result

    # ── Audio Extraction ──────────────────────────────────────────────────────

    async def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> None:
        """Extract audio from video as 16-bit PCM WAV (Whisper-compatible)."""
        cmd = [
            self.ffmpeg,
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-y",
            str(output_path),
        ]
        logger.info("extract_audio_start", src=str(video_path), dst=str(output_path))
        await _run(cmd, f"Audio extraction failed for {video_path.name}")
        logger.info("extract_audio_done", dst=str(output_path))

    # ── Subtitle Burning ──────────────────────────────────────────────────────

    async def burn_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        font_size: int = 24,
    ) -> None:
        """Burn SRT subtitles into video, re-encoding only video stream."""
        subtitle_filter = (
            f"subtitles={str(srt_path)}:force_style='FontSize={font_size}'"
        )
        cmd = [
            self.ffmpeg,
            "-i", str(video_path),
            "-vf", subtitle_filter,
            "-c:a", "copy",
            "-y",
            str(output_path),
        ]
        logger.info("burn_subtitles_start", src=str(video_path), srt=str(srt_path))
        await _run(cmd, f"Subtitle burning failed for {video_path.name}")
        logger.info("burn_subtitles_done", dst=str(output_path))

    # ── Audio Mixing ──────────────────────────────────────────────────────────

    async def replace_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> None:
        """Replace the audio track of a video with a new audio file."""
        cmd = [
            self.ffmpeg,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-shortest",
            "-y",
            str(output_path),
        ]
        logger.info("replace_audio_start", src=str(video_path))
        await _run(cmd, f"Audio replacement failed for {video_path.name}")
        logger.info("replace_audio_done", dst=str(output_path))

    # ── Utility ───────────────────────────────────────────────────────────────

    async def convert(
        self,
        input_path: Path,
        output_path: Path,
        extra_args: Optional[list[str]] = None,
    ) -> None:
        """Generic ffmpeg conversion with optional extra arguments."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            *(extra_args or []),
            "-y",
            str(output_path),
        ]
        await _run(cmd, f"Conversion failed for {input_path.name}")

    async def is_available(self) -> bool:
        """Return True if ffmpeg binary is reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg, "-version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
