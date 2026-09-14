from __future__ import annotations

import asyncio
import logging
from app.workers.celery_app import celery_app
from app.services import ingest_service

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.ingest_news_task", bind=True)
def ingest_news_task(self, triggered_by: str = "celery") -> dict:
    logger.info("Celery task %s started | triggered_by=%s", self.request.id, triggered_by)
    try:
        run_id = asyncio.run(ingest_service.run_ingestion(triggered_by=triggered_by))
        logger.info("Celery task %s finished | run_id=%d", self.request.id, run_id)
        return {"task_id": self.request.id, "run_id": run_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Celery task %s failed: %s", self.request.id, exc)
        return {"task_id": self.request.id, "status": "failed", "error": str(exc)}
