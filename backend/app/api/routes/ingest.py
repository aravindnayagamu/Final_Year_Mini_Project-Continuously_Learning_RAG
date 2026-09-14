import asyncio
import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.ingest import IngestResponse, IngestionRunOut
from app.services import ingest_service, metadata_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

_ingestion_lock = asyncio.Lock()


@router.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
@limiter.limit(settings.ingest_rate_limit)
async def trigger_ingestion(
    request: Request,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    logger.info("POST /ingest | manual trigger requested")
    if _ingestion_lock.locked():
        logger.warning("POST /ingest | rejected — ingestion already running")
        raise HTTPException(
            status_code=409,
            detail="An ingestion job is already running. Please wait.",
        )

    if settings.redis_url:
        try:
            from app.workers.tasks import ingest_news_task
            task = ingest_news_task.delay(triggered_by="manual")
            logger.info("Ingestion dispatched to Celery task %s", task.id)
            return IngestResponse(
                run_id=-1,
                status="started",
                message=f"Ingestion job queued via Celery (task {task.id}).",
            )
        except Exception as exc:
            logger.warning("Failed to dispatch Celery task, falling back to background task: %s", exc)

    async def _run() -> None:
        async with _ingestion_lock:
            logger.info("Background ingestion job starting")
            run_id = await ingest_service.run_ingestion(triggered_by="manual")
            logger.info("Background ingestion job done | run_id=%d", run_id)

    background_tasks.add_task(_run)
    logger.info("POST /ingest | background task queued")
    return IngestResponse(
        run_id=-1,
        status="started",
        message="Ingestion job started in the background. Check /ingest/runs for updates.",
    )


@router.get("/ingest/runs", response_model=List[IngestionRunOut], tags=["Ingestion"])
async def list_ingestion_runs(
    db: AsyncSession = Depends(get_db),
) -> List[IngestionRunOut]:
    logger.info("GET /ingest/runs")
    runs = await metadata_service.get_ingestion_runs(db, limit=20)
    return [IngestionRunOut.model_validate(r) for r in runs]


@router.get("/ingest/runs/{run_id}", response_model=IngestionRunOut, tags=["Ingestion"])
async def get_ingestion_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
) -> IngestionRunOut:
    logger.info("GET /ingest/runs/%d", run_id)
    run = await metadata_service.get_ingestion_run(db, run_id)
    if not run:
        logger.warning("GET /ingest/runs/%d | not found", run_id)
        raise HTTPException(status_code=404, detail="Run not found.")
    return IngestionRunOut.model_validate(run)
