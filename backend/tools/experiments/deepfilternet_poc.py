#!/usr/bin/env python3
"""
DeepFilterNet proof-of-concept — isolated from VoxClone services.

Validates enhancement on a local WAV file using the precompiled ``deep-filter``
CLI (Rust/tract backend). Does not import VoxClone app code or touch the worker
venv ML stack.

Usage:
    python backend/tools/experiments/deepfilternet_poc.py \\
        --input path/to/audio.wav \\
        --output-dir backend/tools/experiments/output

Requirements:
    - ffmpeg on PATH (resample to 48 kHz mono when needed)
    - deep-filter binary (auto-downloaded on first run to tools/experiments/bin/)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEEP_FILTER_VERSION = "0.5.6"
DEEP_FILTER_URL = (
    "https://github.com/Rikorose/DeepFilterNet/releases/download/"
    f"v{DEEP_FILTER_VERSION}/deep-filter-{DEEP_FILTER_VERSION}-x86_64-unknown-linux-musl"
)
TARGET_SAMPLE_RATE = 48_000


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _ensure_deep_filter_binary(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / "deep-filter"
    if binary.exists():
        return binary

    print(f"Downloading deep-filter {DEEP_FILTER_VERSION} …")
    tmp = binary.with_suffix(".download")
    urllib.request.urlretrieve(DEEP_FILTER_URL, tmp)
    tmp.chmod(0o755)
    tmp.rename(binary)
    print(f"Saved binary to {binary}")
    return binary


def _probe_wav(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=sample_rate,channels,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    return {
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_seconds": float(stream.get("duration", 0)),
    }


def _prepare_input(input_path: Path, work_dir: Path) -> tuple[Path, Path | None]:
    """Return (path_for_deep_filter, optional_resampled_temp)."""
    meta = _probe_wav(input_path)
    if meta["sample_rate"] == TARGET_SAMPLE_RATE and meta["channels"] == 1:
        return input_path, None

    work_dir.mkdir(parents=True, exist_ok=True)
    resampled = work_dir / f"{input_path.stem}_48k_mono.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-ac",
        "1",
        str(resampled),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return resampled, resampled


def run_poc(input_path: Path, output_dir: Path, *, post_filter: bool = False) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be on PATH")

    binary = _ensure_deep_filter_binary(_script_dir() / "bin")
    output_dir.mkdir(parents=True, exist_ok=True)

    input_meta = _probe_wav(input_path)
    df_input, temp_resampled = _prepare_input(input_path, output_dir / ".tmp")

    cmd = [str(binary), "-v", "-o", str(output_dir), str(df_input)]
    if post_filter:
        cmd.insert(-1, "--pf")

    print("=== DeepFilterNet PoC ===")
    print(f"Input:        {input_path}")
    print(f"Input meta:   {input_meta}")
    print(f"DF input:     {df_input}")
    print(f"Output dir:   {output_dir}")
    print(f"Command:      {' '.join(cmd)}")

    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - started

    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"deep-filter failed (exit {proc.returncode})")

    enhanced_path = output_dir / df_input.name
    if not enhanced_path.exists():
        raise RuntimeError(f"Expected enhanced output missing: {enhanced_path}")

    out_meta = _probe_wav(enhanced_path)
    duration = out_meta["duration_seconds"] or input_meta["duration_seconds"]
    rtf = elapsed / duration if duration > 0 else None

    if temp_resampled is not None:
        temp_resampled.unlink(missing_ok=True)
        (output_dir / ".tmp").rmdir()

    diagnostics = {
        "backend": "deep-filter-cli",
        "deep_filter_version": DEEP_FILTER_VERSION,
        "input_path": str(input_path),
        "enhanced_path": str(enhanced_path),
        "input_meta": input_meta,
        "output_meta": out_meta,
        "elapsed_seconds": round(elapsed, 2),
        "real_time_factor": round(rtf, 4) if rtf is not None else None,
        "enhanced_bytes": enhanced_path.stat().st_size,
        "stdout_tail": proc.stdout.strip()[-500:],
    }

    print("\n=== Diagnostics ===")
    for key, value in diagnostics.items():
        print(f"{key}: {value}")

    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepFilterNet isolated PoC")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "processed"
        / "0e44f8ef-0867-437b-a1fc-c9e8d4d90a08_audio.wav",
        help="Input WAV (any sample rate; resampled to 48 kHz mono)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_script_dir() / "output" / "poc_latest",
        help="Directory for enhanced output",
    )
    parser.add_argument(
        "--post-filter",
        action="store_true",
        help="Enable DeepFilterNet post-filter (--pf)",
    )
    args = parser.parse_args()

    try:
        run_poc(args.input, args.output_dir, post_filter=args.post_filter)
    except Exception as exc:
        print(f"PoC failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
