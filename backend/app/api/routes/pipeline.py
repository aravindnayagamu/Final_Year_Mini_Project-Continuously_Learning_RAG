import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter, INGEST_RATE_LIMIT
from app.db.session import get_db
from app.services import pipeline_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SourceOut(BaseModel):
    source_name: str
    group: str
    url: str
    document_count: int
    last_fetched: Optional[Any] = None


class SourcesResponse(BaseModel):
    total_sources: int
    groups: Dict[str, int]
    sources: List[SourceOut]


class SummaryOut(BaseModel):
    summary: str
    generated_at: str
    generation_time_ms: Optional[float] = None


@router.get("/sources", response_model=SourcesResponse, tags=["Sources"])
async def list_sources(db: AsyncSession = Depends(get_db)) -> SourcesResponse:
    logger.info("GET /sources")
    try:
        sources = await pipeline_service.get_sources(db)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"fetch_news unavailable: {exc}")
    groups: Dict[str, int] = {}
    for s in sources:
        groups[s["group"]] = groups.get(s["group"], 0) + 1
    return SourcesResponse(
        total_sources=len(sources),
        groups=groups,
        sources=[SourceOut(**s) for s in sources],
    )


@router.get("/metrics", tags=["Metrics"])
async def get_metrics() -> Dict[str, Any]:
    logger.info("GET /metrics")
    return pipeline_service.get_metrics()


@router.post("/metrics/reset", tags=["Metrics"])
async def reset_metrics() -> Dict[str, Any]:
    logger.info("POST /metrics/reset")
    return pipeline_service.reset_metrics()


@router.get("/maintenance/vector-stats", tags=["Maintenance"])
async def vector_stats() -> Dict[str, Any]:
    try:
        return pipeline_service.get_vector_store_stats()
    except Exception as exc:
        logger.exception("vector-stats failed")
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/maintenance/separate-recent", tags=["Maintenance"])
@limiter.limit(INGEST_RATE_LIMIT)
async def separate_recent(request: Request) -> Dict[str, Any]:
    logger.info("POST /maintenance/separate-recent")
    try:
        return await pipeline_service.run_separation_async()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.exception("separation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary", response_model=Optional[SummaryOut], tags=["Summary"])
async def latest_summary() -> Optional[Dict[str, Any]]:
    return pipeline_service.get_latest_summary()


@router.post("/summary", response_model=SummaryOut, tags=["Summary"])
@limiter.limit(INGEST_RATE_LIMIT)
async def generate_summary(request: Request) -> Dict[str, Any]:
    logger.info("POST /summary | generating news digest")
    try:
        return await pipeline_service.generate_summary()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.exception("summary generation failed")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {exc}")


@router.get("/summary/preferences", tags=["Summary"])
async def summary_preferences() -> Dict[str, Any]:
    return pipeline_service.get_user_preferences()


@router.post("/summary/preferences", tags=["Summary"])
async def update_summary_preferences(payload: Dict[str, Any]) -> Dict[str, Any]:
    return pipeline_service.save_user_preferences(payload)