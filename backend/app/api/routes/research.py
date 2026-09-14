from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.core.config import get_settings
from app.core.limiter import limiter
from app.schemas.research import (
    ResearchPaperOut,
    ResearchQueryRequest,
    ResearchQueryResponse,
    ResearchUploadResponse,
)
from app.services import research_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["Research Assistant"])
settings = get_settings()


@router.post("/upload", response_model=ResearchUploadResponse)
async def upload_research_paper(
    file: UploadFile = File(...),
) -> ResearchUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported for research papers.",
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        return await research_service.process_and_store_paper(
            file_bytes=content,
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to process research paper upload: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to parse and index PDF.")


@router.get("/papers", response_model=List[ResearchPaperOut])
async def list_research_papers() -> List[ResearchPaperOut]:
    return await research_service.get_research_papers()


@router.post("/query", response_model=ResearchQueryResponse)
@limiter.limit(settings.query_rate_limit)
async def query_research_assistant(
    request: Request,
    payload: ResearchQueryRequest,
) -> ResearchQueryResponse:
    try:
        return await research_service.query_research(
            question=payload.question,
            paper_id=payload.paper_id,
            k=payload.k,
        )
    except Exception as exc:
        logger.exception("Research query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/papers/{paper_id}")
async def delete_research_paper(paper_id: str):
    await research_service.delete_research_paper(paper_id)
    return {"status": "ok", "deleted": paper_id}
