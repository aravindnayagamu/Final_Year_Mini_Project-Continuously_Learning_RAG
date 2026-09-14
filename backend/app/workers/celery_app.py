from __future__ import annotations

import os
import ssl
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

broker = settings.redis_url if settings.redis_url else "redis://localhost:6379/0"
backend = settings.redis_url if settings.redis_url else "redis://localhost:6379/0"

celery_app = Celery("continual_rag", broker=broker, backend=backend)

is_ssl = broker.startswith("rediss://")

conf_updates = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 600,
    "beat_schedule": {
        "periodic-news-ingestion": {
            "task": "app.workers.tasks.ingest_news_task",
            "schedule": float(settings.fetch_interval_minutes * 60),
            "args": ("scheduler",),
        },
    },
}

if is_ssl:
    ssl_conf = {"ssl_cert_reqs": ssl.CERT_NONE}
    conf_updates["broker_use_ssl"] = ssl_conf
    conf_updates["redis_backend_use_ssl"] = ssl_conf

celery_app.conf.update(conf_updates)
celery_app.autodiscover_tasks(["app.workers"])
