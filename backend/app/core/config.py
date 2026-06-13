from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "VoxClone"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./voxclone.db"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── File Storage ─────────────────────────────────────────────────────────
    UPLOAD_DIR: Path = Path("uploads")
    PROCESSED_DIR: Path = Path("processed")
    LOGS_DIR: Path = Path("logs")
    MAX_UPLOAD_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB

    # ── Media Formats ─────────────────────────────────────────────────────────
    ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset({"mp4", "webm", "mov", "mkv", "avi"})
    ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset({"mp3", "wav", "flac", "m4a"})

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" | "console"

    # ── Computed ─────────────────────────────────────────────────────────────
    @property
    def allowed_extensions(self) -> frozenset[str]:
        return self.ALLOWED_VIDEO_EXTENSIONS | self.ALLOWED_AUDIO_EXTENSIONS

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @field_validator("UPLOAD_DIR", "PROCESSED_DIR", "LOGS_DIR", mode="before")
    @classmethod
    def coerce_path(cls, v: Any) -> Path:
        return Path(v)

    @model_validator(mode="after")
    def create_directories(self) -> "Settings":
        for directory in (self.UPLOAD_DIR, self.PROCESSED_DIR, self.LOGS_DIR):
            directory.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
