from __future__ import annotations

"""
Demucs model names supported by VoxClone.

Only whitelisted models may be passed via API or task parameters so Demucs
failures surface as HTTP 422 instead of opaque subprocess errors.
"""

from typing import Literal

from app.core.config import get_settings

SeparationModelName = Literal["htdemucs"]

SUPPORTED_SEPARATION_MODELS: frozenset[str] = frozenset({"htdemucs"})


def validate_separation_model(value: str) -> str:
    """Return *value* if supported; raise ValueError otherwise."""
    if value not in SUPPORTED_SEPARATION_MODELS:
        allowed = ", ".join(sorted(SUPPORTED_SEPARATION_MODELS))
        raise ValueError(
            f"Invalid separation_model '{value}'. Allowed values: {allowed}"
        )
    return value


def default_separation_model() -> str:
    """Configured default, validated against the whitelist."""
    return validate_separation_model(get_settings().DEMUCS_MODEL)
