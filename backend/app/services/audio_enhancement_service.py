from __future__ import annotations

"""
AudioEnhancementService — speech noise reduction via DeepFilterNet deep-filter CLI.

The ``deep-filter`` binary runs in a subprocess so DeepFilterNet is never loaded
into the Celery worker Python process (Phase 6 dependency isolation policy).
"""

import asyncio
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.file_utils import safe_delete

logger = get_logger(__name__)


class AudioEnhancementError(RuntimeError):
    """Raised when deep-filter enhancement fails or output is missing."""


class AudioEnhancementService:
    """Enhance speech audio using the ``deep-filter`` CLI subprocess."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _resolve_binary(self) -> str:
        """Resolve DEEPFILTER_BINARY to an executable path."""
        raw = self._settings.DEEPFILTER_BINARY
        candidate = Path(raw)
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(raw)
        if found:
            return found
        raise AudioEnhancementError(
            "deep-filter binary is not available.\n\n"
            f"Configured DEEPFILTER_BINARY={raw!r} — file not found and not on PATH.\n"
            "Install the v0.5.6 release binary or set DEEPFILTER_BINARY to its path.\n"
            "See docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md"
        )

    async def validate(self) -> None:
        """Verify ``deep-filter`` is invokable (``--version``)."""
        binary = self._resolve_binary()
        process = await asyncio.create_subprocess_exec(
            binary,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            raise AudioEnhancementError(
                f"deep-filter is not executable (exit code {process.returncode}).\n\n"
                f"{detail or 'deep-filter --version exited non-zero'}"
            )
        version_line = stdout.decode(errors="replace").strip()
        logger.info("deepfilter_validate_ok", binary=binary, version=version_line)

    async def enhance(
        self,
        input_audio: Path,
        output_audio: Path,
    ) -> Path:
        """
        Run DeepFilterNet on a 48 kHz mono PCM WAV and write the enhanced output.

        Args:
            input_audio:  Preprocessed WAV suitable for deep-filter (48 kHz mono).
            output_audio: Stable destination path (e.g. processed/<job_id>_enhanced.wav).

        Returns:
            ``output_audio`` after successful validation.
        """
        if not input_audio.exists():
            raise FileNotFoundError(f"Enhancement input not found: {input_audio}")

        if input_audio.stat().st_size == 0:
            raise AudioEnhancementError(f"Enhancement input is empty: {input_audio}")

        binary = self._resolve_binary()
        cfg = self._settings

        temp_root = cfg.PROCESSED_DIR / ".dfn_tmp" / output_audio.stem
        safe_delete(temp_root, missing_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)

        cmd = [
            binary,
            "-v",
            "-o",
            str(temp_root),
            str(input_audio),
        ]

        logger.info(
            "diag_audio_enhance_subprocess_start",
            input=str(input_audio),
            output=str(output_audio),
            cmd=cmd,
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        stderr_tail = stderr_text[-4000:] if stderr_text else "(no stderr captured)"

        if process.returncode != 0:
            logger.error(
                "diag_audio_enhance_failed",
                returncode=process.returncode,
                stderr=stderr_tail,
                stdout=stdout_text[-500:] if stdout_text else "",
            )
            safe_delete(temp_root, missing_ok=True)
            raise AudioEnhancementError(
                f"deep-filter enhancement failed (exit code {process.returncode}).\n\n"
                f"{stderr_tail}"
            )

        temp_output = temp_root / input_audio.name
        if not temp_output.exists():
            safe_delete(temp_root, missing_ok=True)
            raise AudioEnhancementError(
                f"deep-filter completed but expected output was not found: {temp_output}. "
                f"stdout tail: {stdout_text[-500:] if stdout_text else '(empty)'}"
            )

        if temp_output.stat().st_size == 0:
            safe_delete(temp_root, missing_ok=True)
            raise AudioEnhancementError(
                f"deep-filter produced an empty output file: {temp_output}"
            )

        output_audio.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_output, output_audio)
        safe_delete(temp_root, missing_ok=True)

        if not output_audio.exists() or output_audio.stat().st_size == 0:
            raise AudioEnhancementError(
                f"Enhanced output missing or empty after copy: {output_audio}"
            )

        logger.info(
            "diag_audio_enhance_subprocess_complete",
            input=str(input_audio),
            output=str(output_audio),
            enhanced_bytes=output_audio.stat().st_size,
            stdout_tail=stdout_text[-500:] if stdout_text else "",
        )

        return output_audio
