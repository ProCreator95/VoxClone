from __future__ import annotations

"""
Whisper GGML model aliases, language-first routing, and per-job-type defaults.

Size aliases (tiny / base / small) map to English-only or multilingual GGML files
depending on the requested language and WHISPER_ROUTING_POLICY.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from app.core.config import Settings, get_settings
from app.models.job import JobType

WhisperModelAlias = Literal["tiny", "base", "small"]
WhisperModelVariant = Literal["english", "multilingual"]
WhisperRoutingPolicy = Literal["english_first", "multilingual_default"]

WHISPER_MODEL_ALIASES: frozenset[str] = frozenset({"tiny", "base", "small"})

WHISPER_ROUTING_POLICIES: frozenset[str] = frozenset({
    "english_first",
    "multilingual_default",
})

WHISPER_LANGUAGE_AUTO = "auto"

WHISPER_ENGLISH_MODEL_FILES: dict[str, str] = {
    "tiny": "ggml-tiny.en.bin",
    "base": "ggml-base.en.bin",
    "small": "ggml-small.en.bin",
}

WHISPER_MULTILINGUAL_MODEL_FILES: dict[str, str] = {
    "tiny": "ggml-tiny.bin",
    "base": "ggml-base.bin",
    "small": "ggml-small.bin",
}

# Backward-compatible alias for callers expecting the English map.
WHISPER_MODEL_FILES: dict[str, str] = WHISPER_ENGLISH_MODEL_FILES

WHISPER_MODEL_DEFAULTS: dict[str, str] = {
    JobType.SUBTITLE_GENERATION: "tiny",
    JobType.KARAOKE: "base",
}

# BCP-47 codes supported by OpenAI Whisper / whisper.cpp (-l flag).
WHISPER_LANGUAGE_CODES: frozenset[str] = frozenset({
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs",
    "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi",
    "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy",
    "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb",
    "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru",
    "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw",
    "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi",
    "yi", "yo", "yue", "zh",
})

_FILENAME_TO_ALIAS: dict[str, str] = {
    filename: alias
    for alias, filename in WHISPER_ENGLISH_MODEL_FILES.items()
}
for _alias, _filename in WHISPER_MULTILINGUAL_MODEL_FILES.items():
    _FILENAME_TO_ALIAS.setdefault(_filename, _alias)


@dataclass(frozen=True)
class ResolvedWhisperModel:
    """Result of language-first whisper model resolution."""

    alias: str
    path: Path
    variant: WhisperModelVariant
    cli_language: Optional[str]
    language_requested: Optional[str]


def validate_whisper_model_alias(value: str) -> str:
    if value not in WHISPER_MODEL_ALIASES:
        allowed = ", ".join(sorted(WHISPER_MODEL_ALIASES))
        raise ValueError(
            f"Invalid whisper_model '{value}'. Allowed values: {allowed}"
        )
    return value


def validate_whisper_routing_policy(value: str) -> str:
    if value not in WHISPER_ROUTING_POLICIES:
        allowed = ", ".join(sorted(WHISPER_ROUTING_POLICIES))
        raise ValueError(
            f"Invalid WHISPER_ROUTING_POLICY '{value}'. Allowed values: {allowed}"
        )
    return value


def validate_whisper_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == WHISPER_LANGUAGE_AUTO:
        return WHISPER_LANGUAGE_AUTO
    if normalized not in WHISPER_LANGUAGE_CODES:
        raise ValueError(
            f"Invalid language '{value}'. Use a Whisper BCP-47 code (e.g. 'en', 'ur') "
            f"or '{WHISPER_LANGUAGE_AUTO}' for auto-detection."
        )
    return normalized


def whisper_models_dir(settings: Optional[Settings] = None) -> Path:
    cfg = settings or get_settings()
    return Path(cfg.WHISPER_MODEL_PATH).parent


def whisper_model_path(
    alias: str,
    variant: WhisperModelVariant = "english",
    settings: Optional[Settings] = None,
) -> Path:
    validate_whisper_model_alias(alias)
    files = (
        WHISPER_ENGLISH_MODEL_FILES
        if variant == "english"
        else WHISPER_MULTILINGUAL_MODEL_FILES
    )
    return whisper_models_dir(settings) / files[alias]


def _resolve_alias(
    whisper_model: Optional[str],
    job_type: str,
    cfg: Settings,
) -> str:
    if whisper_model is not None:
        return validate_whisper_model_alias(whisper_model)

    if job_type in WHISPER_MODEL_DEFAULTS:
        return WHISPER_MODEL_DEFAULTS[job_type]

    global_name = Path(cfg.WHISPER_MODEL_PATH).name
    return _FILENAME_TO_ALIAS.get(global_name, "tiny")


def resolve_whisper_model(
    whisper_model: Optional[str],
    job_type: str,
    language: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> ResolvedWhisperModel:
    """
    Resolve size alias + language into a concrete GGML model path and CLI language.

    Routing (WHISPER_ROUTING_POLICY defaults to english_first for backward compat):

      language == "en"           → English-only model, -l en
      language == "auto"         → multilingual model, omit -l
      language == <other code>   → multilingual model, -l <code>
      language omitted + english_first → English-only model, -l en
      language omitted + multilingual_default → multilingual model, omit -l
    """
    cfg = settings or get_settings()
    alias = _resolve_alias(whisper_model, job_type, cfg)
    policy = validate_whisper_routing_policy(cfg.WHISPER_ROUTING_POLICY)

    if language is not None:
        lang = validate_whisper_language(language)
    else:
        lang = None

    if lang == "en":
        variant: WhisperModelVariant = "english"
        cli_language: Optional[str] = "en"
        language_requested = "en"
    elif lang == WHISPER_LANGUAGE_AUTO:
        variant = "multilingual"
        cli_language = None
        language_requested = WHISPER_LANGUAGE_AUTO
    elif lang is None and policy == "english_first":
        variant = "english"
        cli_language = "en"
        language_requested = None
    elif lang is None and policy == "multilingual_default":
        variant = "multilingual"
        cli_language = None
        language_requested = None
    else:
        variant = "multilingual"
        cli_language = lang
        language_requested = lang

    model_path = whisper_model_path(alias, variant, cfg)
    return ResolvedWhisperModel(
        alias=alias,
        path=model_path,
        variant=variant,
        cli_language=cli_language,
        language_requested=language_requested,
    )


def apply_whisper_metadata(params: dict, resolved: ResolvedWhisperModel) -> None:
    """Persist resolved whisper model fields on job parameters."""
    params["whisper_model"] = resolved.alias
    params["whisper_model_file"] = resolved.path.name
    params["whisper_model_variant"] = resolved.variant
    if resolved.language_requested is not None:
        params["language_requested"] = resolved.language_requested


def model_missing_message(model_path: Path, alias: str, variant: WhisperModelVariant) -> str:
    download_name = f"{alias}.en" if variant == "english" else alias
    return (
        f"whisper.cpp model file not found: {model_path}\n\n"
        f"Download the '{download_name}' model with:\n"
        f"  bash scripts/download_whisper_model.sh {download_name}\n"
        "or manually place the file under the models/ directory.\n"
        "See: docs/testing/WHISPER_CPP_SETUP.md"
    )
