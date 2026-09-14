from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.services import ingest_service

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


def _build_scheduler() -> AsyncIOScheduler:
    scheduler.add_job(
        func=_scheduled_ingestion,
        trigger=IntervalTrigger(minutes=settings.fetch_interval_minutes),
        id="news_ingestion",
        name="Scheduled news ingestion",
        replace_existing=True,
    )
    return scheduler


async def _scheduled_ingestion() -> None:
    logger.info("Scheduler fired — starting news ingestion")
    try:
        if settings.redis_url:
            try:
                from app.workers.tasks import ingest_news_task
                task = ingest_news_task.delay(triggered_by="scheduler")
                logger.info("Scheduler dispatched ingestion to Celery task %s", task.id)
                return
            except Exception as exc:
                logger.warning("Failed to dispatch Celery task from scheduler, falling back: %s", exc)

        run_id = await ingest_service.run_ingestion(triggered_by="scheduler")
        logger.info("Scheduler ingestion complete | run_id=%d", run_id)
    except Exception as exc:
        logger.exception("Scheduler ingestion failed: %s", exc)


async def _check_and_run_if_due() -> None:
    try:
        from app.db.session import AsyncSessionLocal
        from app.services import metadata_service

        async with AsyncSessionLocal() as db:
            runs = await metadata_service.get_ingestion_runs(db, limit=1)
            should_run = False
            if not runs:
                should_run = True
            else:
                last_run = runs[0]
                if last_run.started_at:
                    now = datetime.now(timezone.utc)
                    last_started = last_run.started_at
                    if last_started.tzinfo is None:
                        last_started = last_started.replace(tzinfo=timezone.utc)
                    elapsed_min = (now - last_started).total_seconds() / 60.0
                    if elapsed_min >= settings.fetch_interval_minutes:
                        should_run = True
            if should_run:
                logger.info("Ingestion is due on startup — triggering scheduled ingestion")
                await _scheduled_ingestion()
    except Exception as exc:
        logger.warning("Startup ingestion check failed: %s", exc)


def start() -> None:
    _build_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started | interval=%d min", settings.fetch_interval_minutes)
        try:
            asyncio.create_task(_check_and_run_if_due())
        except RuntimeError:
            pass


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
