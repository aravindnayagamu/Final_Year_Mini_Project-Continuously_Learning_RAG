from __future__ import annotations

import logging

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
        run_id = await ingest_service.run_ingestion(triggered_by="scheduler")
        logger.info("Scheduler ingestion complete | run_id=%d", run_id)
    except Exception as exc:
        logger.exception("Scheduler ingestion failed: %s", exc)


def start() -> None:
    _build_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started | interval=%d min", settings.fetch_interval_minutes)


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
