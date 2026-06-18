from __future__ import annotations

"""
Whisper GGML model aliases and per-job-type defaults.

Job tasks resolve a short alias (tiny / base / small) to a concrete model file
under the models/ directory. Global WHISPER_MODEL_PATH in .env remains a fallback
for tooling that does not pass a job type.
"""

from pathlib import Path
from typing import Literal, Optional

from app.core.config import Settings, get_settings
from app.models.job import JobType

WhisperModelAlias = Literal["tiny", "base", "small"]

WHISPER_MODEL_ALIASES: frozenset[str] = frozenset({"tiny", "base", "small"})

WHISPER_MODEL_FILES: dict[str, str] = {
    "tiny": "ggml-tiny.en.bin",
    "base": "ggml-base.en.bin",
    "small": "ggml-small.en.bin",
}

WHISPER_MODEL_DEFAULTS: dict[str, str] = {
    JobType.SUBTITLE_GENERATION: "tiny",
    JobType.KARAOKE: "base",
}

_FILENAME_TO_ALIAS: dict[str, str] = {
    filename: alias for alias, filename in WHISPER_MODEL_FILES.items()
}


def validate_whisper_model_alias(value: str) -> str:
    if value not in WHISPER_MODEL_ALIASES:
        allowed = ", ".join(sorted(WHISPER_MODEL_ALIASES))
        raise ValueError(
            f"Invalid whisper_model '{value}'. Allowed values: {allowed}"
        )
    return value


def whisper_models_dir(settings: Optional[Settings] = None) -> Path:
    cfg = settings or get_settings()
    return Path(cfg.WHISPER_MODEL_PATH).parent


def whisper_model_path(alias: str, settings: Optional[Settings] = None) -> Path:
    validate_whisper_model_alias(alias)
    return whisper_models_dir(settings) / WHISPER_MODEL_FILES[alias]


def resolve_whisper_model(
    whisper_model: Optional[str],
    job_type: str,
    settings: Optional[Settings] = None,
) -> tuple[str, Path]:
    cfg = settings or get_settings()

    if whisper_model is not None:
        alias = validate_whisper_model_alias(whisper_model)
        return alias, whisper_model_path(alias, cfg)

    if job_type in WHISPER_MODEL_DEFAULTS:
        alias = WHISPER_MODEL_DEFAULTS[job_type]
        return alias, whisper_model_path(alias, cfg)

    global_name = Path(cfg.WHISPER_MODEL_PATH).name
    alias = _FILENAME_TO_ALIAS.get(global_name, "tiny")
    return alias, Path(cfg.WHISPER_MODEL_PATH)


def model_missing_message(model_path: Path, alias: str) -> str:
    return (
        f"whisper.cpp model file not found: {model_path}\n\n"
        f"Download the '{alias}' model with:\n"
        f"  bash scripts/download_whisper_model.sh {alias}.en\n"
        "or manually place the file under the models/ directory.\n"
        "See: docs/testing/WHISPER_CPP_SETUP.md"
    )
