from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.job import JobType


class JobCreate(BaseModel):
    media_id: str = Field(..., description="ID of the source media file")
    job_type: str = Field(..., description="Processing pipeline to run")
    parameters: Optional[dict[str, Any]] = Field(
        default=None, description="Pipeline-specific configuration"
    )

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in JobType.ALL:
            raise ValueError(
                f"Unknown job_type '{v}'. Allowed: {sorted(JobType.ALL)}"
            )
        return v


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
