from __future__ import annotations

from typing import Literal

KaraokeOutputMode = Literal[
    "karaoke_video_with_vocals",
    "karaoke_video_no_vocals",
    "vocals_only",
    "music_only",
]

KARAOKE_OUTPUT_MODES: frozenset[str] = frozenset({
    "karaoke_video_with_vocals",
    "karaoke_video_no_vocals",
    "vocals_only",
    "music_only",
})

# Milestone 3 implements video modes only; stems-only modes follow in Milestone 4.
KARAOKE_VIDEO_OUTPUT_MODES: frozenset[str] = frozenset({
    "karaoke_video_with_vocals",
    "karaoke_video_no_vocals",
})

# Subset implemented per milestone; API rejects others until enabled.
KARAOKE_IMPLEMENTED_OUTPUT_MODES: frozenset[str] = KARAOKE_VIDEO_OUTPUT_MODES

DEFAULT_KARAOKE_OUTPUT_MODE: KaraokeOutputMode = "karaoke_video_with_vocals"


def validate_karaoke_output_mode(value: str) -> str:
    if value not in KARAOKE_OUTPUT_MODES:
        allowed = ", ".join(sorted(KARAOKE_OUTPUT_MODES))
        raise ValueError(
            f"Invalid output_mode '{value}'. Allowed values: {allowed}"
        )
    return value


def resolve_karaoke_output_mode(parameters: dict | None) -> str:
    raw = (parameters or {}).get("output_mode")
    if raw is None:
        return DEFAULT_KARAOKE_OUTPUT_MODE
    if not isinstance(raw, str):
        raise ValueError("parameters.output_mode must be a string")
    return validate_karaoke_output_mode(raw)
