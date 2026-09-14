import logging
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.document import DocumentOut, DocumentStats
from app.services import metadata_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents", response_model=List[DocumentOut], tags=["Documents"])
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentOut]:
    logger.info("GET /documents | page=%d page_size=%d", page, page_size)
    documents, total = await metadata_service.get_all_documents(
        db, page=page, page_size=page_size
    )
    logger.debug("GET /documents | returned=%d total=%d", len(documents), total)
    return [DocumentOut.model_validate(doc) for doc in documents]


@router.get("/documents/stats", response_model=DocumentStats, tags=["Documents"])
async def document_stats(db: AsyncSession = Depends(get_db)) -> DocumentStats:
    logger.info("GET /documents/stats")
    stats = await metadata_service.get_document_stats(db)
    return DocumentStats(**stats)
