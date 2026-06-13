from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Optional


def human_readable_size(size_bytes: int) -> str:
    """Convert byte count to a human-readable string (e.g. '1.4 MB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} PB"


def safe_delete(path: Path, *, missing_ok: bool = True) -> bool:
    """Delete a file or directory tree. Returns True if deletion occurred."""
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=missing_ok)
        return True
    except OSError:
        return False


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_checksum(path: Path, algorithm: str = "sha256") -> str:
    """Compute hex digest of a file using the given hash algorithm."""
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stem_with_suffix(path: Path, new_suffix: str) -> Path:
    """Return a sibling path with the same stem but a different extension."""
    return path.with_suffix(new_suffix)


def resolve_output_path(
    processed_dir: Path,
    job_id: str,
    label: str,
    extension: str,
) -> Path:
    """Build a canonical output path for a processed file."""
    filename = f"{job_id}_{label}.{extension.lstrip('.')}"
    return processed_dir / filename
