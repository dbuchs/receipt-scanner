from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "receipt_scanner",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.watched_folder",
        "app.tasks.retraining",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "poll-watched-folder": {
            "task": "app.tasks.watched_folder.poll_watched_folder",
            "schedule": settings.WATCHED_FOLDER_POLL_SECONDS,
        },
        "nightly-retrain": {
            "task": "app.tasks.retraining.retrain_classifier",
            "schedule": 86400,  # every 24 hours
        },
    },
)
