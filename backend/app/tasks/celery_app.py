from __future__ import annotations

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def create_celery_app() -> Celery:
    settings = get_settings()

    app = Celery(
        "voxclone",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.tasks.media_tasks"],
    )

    app.conf.update(
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Reliability
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,

        # Result expiry (24 h)
        result_expires=86400,

        # Retry defaults
        task_max_retries=3,
        task_default_retry_delay=30,

        # Routing — separate queues for fast I/O vs heavy AI work
        task_routes={
            "app.tasks.media_tasks.extract_audio_task": {"queue": "media"},
            "app.tasks.media_tasks.generate_subtitles_task": {"queue": "ai"},
            "app.tasks.media_tasks.burn_subtitles_task": {"queue": "media"},
            "app.tasks.media_tasks.karaoke_task": {"queue": "ai"},
            "app.tasks.media_tasks.audio_enhance_task": {"queue": "ai"},
        },

        # Queue definitions
        task_queues={},
    )

    return app


celery_app = create_celery_app()


@worker_ready.connect
def on_worker_ready(**kwargs) -> None:
    setup_logging()
    logger.info("celery_worker_ready")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs) -> None:
    logger.info("celery_worker_shutdown")
