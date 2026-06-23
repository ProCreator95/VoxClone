from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.job import JobType
from app.services.karaoke_modes import (
    DEFAULT_KARAOKE_OUTPUT_MODE,
    KARAOKE_IMPLEMENTED_OUTPUT_MODES,
    mode_requires_stems,
    validate_karaoke_output_mode,
)
from app.services.separation_models import validate_separation_model
from app.services.whisper_models import (
    WHISPER_MODEL_DEFAULTS,
    validate_whisper_language,
    validate_whisper_model_alias,
)

_WHISPER_JOB_TYPES = frozenset({
    JobType.SUBTITLE_GENERATION,
    JobType.KARAOKE,
})

_VOCAL_SEPARATION_JOB_TYPES = frozenset({JobType.VOCAL_SEPARATION})
_KARAOKE_JOB_TYPES = frozenset({JobType.KARAOKE})
_SEPARATION_MODEL_JOB_TYPES = _VOCAL_SEPARATION_JOB_TYPES | _KARAOKE_JOB_TYPES


class JobCreate(BaseModel):
    media_id: str = Field(..., description="ID of the source media file")
    job_type: str = Field(..., description="Processing pipeline to run")
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Pipeline-specific configuration. "
            "Whisper jobs accept optional `whisper_model`: tiny | base | small, "
            "and optional `language`: BCP-47 code (e.g. en, ur) or 'auto'. "
            f"Defaults: subtitle_generation={WHISPER_MODEL_DEFAULTS[JobType.SUBTITLE_GENERATION]!r}, "
            f"karaoke={WHISPER_MODEL_DEFAULTS[JobType.KARAOKE]!r}."
        ),
    )

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in JobType.ALL:
            raise ValueError(
                f"Unknown job_type '{v}'. Allowed: {sorted(JobType.ALL)}"
            )
        return v

    @model_validator(mode="after")
    def validate_parameters(self) -> "JobCreate":
        params = self.parameters or {}

        whisper_model = params.get("whisper_model")
        if whisper_model is not None:
            if not isinstance(whisper_model, str):
                raise ValueError("parameters.whisper_model must be a string")
            validate_whisper_model_alias(whisper_model)
            if self.job_type not in _WHISPER_JOB_TYPES:
                allowed = ", ".join(sorted(_WHISPER_JOB_TYPES))
                raise ValueError(
                    f"parameters.whisper_model is only supported for job types: {allowed}"
                )

        language = params.get("language")
        if language is not None:
            if not isinstance(language, str):
                raise ValueError("parameters.language must be a string")
            if self.job_type not in _WHISPER_JOB_TYPES:
                allowed = ", ".join(sorted(_WHISPER_JOB_TYPES))
                raise ValueError(
                    f"parameters.language is only supported for job types: {allowed}"
                )
            validate_whisper_language(language)

        separation_model = params.get("separation_model")
        if separation_model is not None:
            if not isinstance(separation_model, str):
                raise ValueError("parameters.separation_model must be a string")
            validate_separation_model(separation_model)
            if self.job_type not in _SEPARATION_MODEL_JOB_TYPES:
                raise ValueError(
                    "parameters.separation_model is only supported for "
                    f"job types: {sorted(_SEPARATION_MODEL_JOB_TYPES)}"
                )

        separation_job_id = params.get("separation_job_id")
        if separation_job_id is not None:
            if not isinstance(separation_job_id, str) or not separation_job_id.strip():
                raise ValueError(
                    "parameters.separation_job_id must be a non-empty string"
                )
            if self.job_type != JobType.KARAOKE:
                raise ValueError(
                    "parameters.separation_job_id is only supported for "
                    f"job_type '{JobType.KARAOKE}'"
                )
            resolved_mode = (
                params.get("output_mode")
                if params.get("output_mode") is not None
                else DEFAULT_KARAOKE_OUTPUT_MODE
            )
            if isinstance(resolved_mode, str):
                validate_karaoke_output_mode(resolved_mode)
                if not mode_requires_stems(resolved_mode):
                    raise ValueError(
                        "parameters.separation_job_id is only supported for output modes "
                        "that use stems: karaoke_video_no_vocals, vocals_only, music_only"
                    )

        output_mode = params.get("output_mode")
        if output_mode is not None:
            if not isinstance(output_mode, str):
                raise ValueError("parameters.output_mode must be a string")
            validate_karaoke_output_mode(output_mode)
            if self.job_type != JobType.KARAOKE:
                raise ValueError(
                    f"parameters.output_mode is only supported for job_type '{JobType.KARAOKE}'"
                )
            if output_mode not in KARAOKE_IMPLEMENTED_OUTPUT_MODES:
                allowed = ", ".join(sorted(KARAOKE_IMPLEMENTED_OUTPUT_MODES))
                raise ValueError(
                    f"output_mode '{output_mode}' is not implemented yet. "
                    f"Allowed values: {allowed}"
                )

        return self


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_id: str
    job_type: str
    status: str
    progress: int
    current_step: Optional[str] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    parameters: Optional[dict] = None
    celery_task_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobProgressResponse(BaseModel):
    """Lightweight progress snapshot — served from Redis for low latency."""

    job_id: str
    status: str
    progress: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None


class JobListItem(BaseModel):
    """Compact representation used in list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    status: str
    progress: int
    created_at: datetime
    completed_at: Optional[datetime] = None
