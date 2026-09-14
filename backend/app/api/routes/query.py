import logging
from fastapi import APIRouter, Body, HTTPException, Request

from app.core.config import get_settings
from app.core.limiter import limiter
from app.schemas.query import QueryRequest, QueryResponse
from app.services import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/query", response_model=QueryResponse, tags=["RAG"])
@limiter.limit(settings.query_rate_limit)
async def query(request: Request, payload: QueryRequest = Body(...)) -> QueryResponse:
    logger.info("POST /query | question=%r k=%d", payload.question[:80], payload.k)
    try:
        result = await rag_service.answer_question(
            question=payload.question,
            k=payload.k,
        )
        logger.info("POST /query | answered | chunks=%d", result.context_chunks)
        return result
    except RuntimeError as exc:
        logger.error("POST /query | service unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("POST /query | unhandled error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error during query.")
