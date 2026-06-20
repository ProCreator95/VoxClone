from __future__ import annotations

"""
Resolve reusable canonical stems from a completed vocal_separation job.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobStatus, JobType
from app.models.stem_metadata import require_canonical_stem_job
from app.services.job_service import JobService


@dataclass(frozen=True)
class ResolvedCanonicalStems:
    """Paths and metadata from a completed vocal_separation job."""

    separation_job_id: str
    vocals_path: Path
    instrumental_path: Path
    separation_model: str | None


async def resolve_canonical_stems(
    db: AsyncSession,
    separation_job_id: str,
) -> ResolvedCanonicalStems:
    """
    Load and validate a completed vocal_separation job for stem reuse.

    Raises:
        ValueError: job missing, wrong type, not completed, or stems absent on disk.
    """
    job_svc = JobService(db)
    job = await job_svc.get_by_id(separation_job_id)

    if job.status != JobStatus.COMPLETED:
        raise ValueError(
            f"separation_job_id '{separation_job_id}' must reference a completed job; "
            f"got status '{job.status}'."
        )

    params = job.parameters or {}
    require_canonical_stem_job(
        job.job_type,
        params.get("stem_origin"),
        job_id=separation_job_id,
    )

    result_files: dict = params.get("result_files") or {}
    vocals_str = result_files.get("vocals")
    instrumental_str = result_files.get("instrumental")

    if not vocals_str or not instrumental_str:
        raise ValueError(
            f"separation_job_id '{separation_job_id}' has no stem paths in result_files."
        )

    vocals_path = Path(vocals_str)
    instrumental_path = Path(instrumental_str)

    if not vocals_path.exists():
        raise FileNotFoundError(
            f"Vocals stem not found for separation_job_id '{separation_job_id}': "
            f"{vocals_path}"
        )
    if not instrumental_path.exists():
        raise FileNotFoundError(
            f"Instrumental stem not found for separation_job_id '{separation_job_id}': "
            f"{instrumental_path}"
        )

    return ResolvedCanonicalStems(
        separation_job_id=separation_job_id,
        vocals_path=vocals_path,
        instrumental_path=instrumental_path,
        separation_model=params.get("separation_model"),
    )
