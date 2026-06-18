from __future__ import annotations

"""
SourceSeparationService — vocal/instrumental stem separation via Demucs.

Demucs runs in a subprocess so PyTorch is not loaded into the Celery fork
lifecycle. Demucs writes ``no_vocals.wav``; VoxClone exposes it as
``instrumental.wav`` in the stable result_files contract.
"""

import asyncio
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.separation_models import validate_separation_model
from app.utils.file_utils import resolve_output_path, safe_delete

logger = get_logger(__name__)


@dataclass(frozen=True)
class SeparationResult:
    """Paths to the two stems written into processed/."""

    vocals_path: Path
    instrumental_path: Path
    model: str
    device: str
    input_path: Path


class SourceSeparationError(RuntimeError):
    """Raised when Demucs separation fails or output stems are missing."""


class SourceSeparationService:
    """Separate vocals from accompaniment using Demucs (subprocess)."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def validate(self) -> None:
        """Verify Demucs is invokable via ``python -m demucs``."""
        cmd = [sys.executable, "-m", "demucs", "--help"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            raise SourceSeparationError(
                "Demucs is not available in this Python environment.\n\n"
                "Install pinned ML deps (see requirements-ml.txt):\n"
                "  pip install -r requirements-ml.txt\n\n"
                f"Diagnostic: {detail or 'demucs --help exited non-zero'}"
            )

    async def separate(
        self,
        input_path: Path,
        job_id: str,
        *,
        model: Optional[str] = None,
        device: Optional[str] = None,
    ) -> SeparationResult:
        """
        Run Demucs two-stem separation and copy outputs to processed/.

        Args:
            input_path: Stereo WAV suitable for Demucs (44.1 kHz recommended).
            job_id:     Job UUID used for stable output filenames.
            model:      Demucs model name (-n flag). Defaults to settings.
            device:     ``cpu`` or ``cuda``. Defaults to settings.

        Returns:
            SeparationResult with absolute paths to vocals and instrumental WAVs.
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Separation input not found: {input_path}")

        cfg = self._settings
        demucs_model = validate_separation_model(model or cfg.DEMUCS_MODEL)
        demucs_device = device or cfg.DEMUCS_DEVICE

        vocals_path = resolve_output_path(cfg.PROCESSED_DIR, job_id, "vocals", "wav")
        instrumental_path = resolve_output_path(
            cfg.PROCESSED_DIR, job_id, "instrumental", "wav"
        )

        temp_root = cfg.PROCESSED_DIR / ".demucs_tmp" / job_id
        safe_delete(temp_root, missing_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "-n",
            demucs_model,
            "--two-stems",
            "vocals",
            "-d",
            demucs_device,
            "-o",
            str(temp_root),
            str(input_path),
        ]

        logger.info(
            "demucs_separate_start",
            job_id=job_id,
            model=demucs_model,
            device=demucs_device,
            input=str(input_path),
            cmd=cmd,
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr.decode(errors="replace").strip()
            stderr_tail = stderr_text[-4000:] if stderr_text else "(no stderr captured)"
            logger.error(
                "demucs_separate_failed",
                job_id=job_id,
                returncode=process.returncode,
                stderr=stderr_tail,
            )
            safe_delete(temp_root, missing_ok=True)
            raise SourceSeparationError(
                f"Demucs separation failed (exit code {process.returncode}).\n\n"
                f"{stderr_tail}"
            )

        track_name = input_path.stem
        demucs_out_dir = temp_root / demucs_model / track_name
        demucs_vocals = demucs_out_dir / "vocals.wav"
        # Demucs names the accompaniment stem no_vocals.wav; API contract uses instrumental.wav.
        demucs_instrumental = demucs_out_dir / "no_vocals.wav"

        if not demucs_vocals.exists() or not demucs_instrumental.exists():
            safe_delete(temp_root, missing_ok=True)
            raise SourceSeparationError(
                f"Demucs completed but expected stems were not found under {demucs_out_dir}. "
                f"stdout tail: {stdout.decode(errors='replace')[-500:]}"
            )

        vocals_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(demucs_vocals, vocals_path)
        shutil.copy2(demucs_instrumental, instrumental_path)

        safe_delete(temp_root, missing_ok=True)

        logger.info(
            "demucs_separate_done",
            job_id=job_id,
            vocals=str(vocals_path),
            instrumental=str(instrumental_path),
            vocals_bytes=vocals_path.stat().st_size,
            instrumental_bytes=instrumental_path.stat().st_size,
        )

        return SeparationResult(
            vocals_path=vocals_path,
            instrumental_path=instrumental_path,
            model=demucs_model,
            device=demucs_device,
            input_path=input_path,
        )
