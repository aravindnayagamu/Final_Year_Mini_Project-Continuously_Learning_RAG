from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.query import QueryRequest, QueryResponse
from app.services import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: QueryRequest) -> QueryResponse:
    logger.info("POST /query | question=%r k=%d", request.question[:80], request.k)
    try:
        result = await rag_service.answer_question(
            question=request.question,
            k=request.k,
        )
        logger.info("POST /query | answered | chunks=%d", result.context_chunks)
        return result
    except RuntimeError as exc:
        logger.error("POST /query | service unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("POST /query | unhandled error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error during query.")
