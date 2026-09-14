from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, IngestionRun, QueryLog, RunStatus

logger = logging.getLogger(__name__)


async def upsert_document(
    db: AsyncSession,
    paper_id: str,
    source_name: str,
    title: Optional[str] = None,
    retrieval_time: Optional[datetime] = None,
    file_name: Optional[str] = None,
    vectorization_status: str = "pending",
    chunk_count: Optional[int] = None,
    vectorized_at: Optional[datetime] = None,
) -> Document:
    logger.debug("Upserting document paper_id=%s source=%s", paper_id, source_name)
    stmt = pg_insert(Document).values(
        paper_id=paper_id,
        source_name=source_name,
        title=title,
        retrieval_time=retrieval_time,
        file_name=file_name,
        vectorization_status=vectorization_status,
        chunk_count=chunk_count,
        vectorized_at=vectorized_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id"],
        set_={
            "source_name": stmt.excluded.source_name,
            "title": stmt.excluded.title,
            "retrieval_time": stmt.excluded.retrieval_time,
            "file_name": stmt.excluded.file_name,
            "vectorization_status": stmt.excluded.vectorization_status,
            "chunk_count": stmt.excluded.chunk_count,
            "vectorized_at": stmt.excluded.vectorized_at,
        },
    )
    await db.execute(stmt)
    await db.flush()
    result = await db.execute(select(Document).where(Document.paper_id == paper_id))
    return result.scalar_one()


async def get_all_documents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Document], int]:
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(Document))
    total = total_result.scalar_one()
    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    documents = list(result.scalars().all())
    logger.debug("Fetched %d documents (page=%d, total=%d)", len(documents), page, total)
    return documents, total


async def get_document_stats(db: AsyncSession) -> dict:
    total_r = await db.execute(select(func.count()).select_from(Document))
    total = total_r.scalar_one()
    vec_r = await db.execute(
        select(func.count()).where(Document.vectorization_status == "vectorized")
    )
    vectorized = vec_r.scalar_one()
    pend_r = await db.execute(
        select(func.count()).where(Document.vectorization_status == "pending")
    )
    pending = pend_r.scalar_one()
    fail_r = await db.execute(
        select(func.count()).where(Document.vectorization_status == "failed")
    )
    failed = fail_r.scalar_one()
    logger.debug("Document stats: total=%d vectorized=%d pending=%d failed=%d",
                 total, vectorized, pending, failed)
    return {"total": total, "vectorized": vectorized, "pending": pending, "failed": failed}


async def log_query(
    db: AsyncSession,
    question: str,
    answer: str,
    context_chunks: int,
    retrieval_time_ms: float,
    model_used: str,
) -> QueryLog:
    entry = QueryLog(
        question=question,
        answer=answer,
        context_chunks=context_chunks,
        retrieval_time_ms=retrieval_time_ms,
        model_used=model_used,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    logger.info("Query logged id=%d chunks=%d retrieval_ms=%.1f",
                entry.id, context_chunks, retrieval_time_ms)
    return entry


async def get_recent_queries(db: AsyncSession, limit: int = 10) -> List[QueryLog]:
    result = await db.execute(
        select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit)
    )
    rows = list(result.scalars().all())
    logger.debug("Fetched %d recent queries", len(rows))
    return rows


async def get_today_query_count(db: AsyncSession) -> int:
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(func.count()).where(func.date(QueryLog.created_at) == today)
    )
    count = result.scalar_one()
    logger.debug("Today query count: %d", count)
    return count


async def create_ingestion_run(
    db: AsyncSession, triggered_by: str = "manual"
) -> IngestionRun:
    run = IngestionRun(triggered_by=triggered_by, status=RunStatus.running.value)
    db.add(run)
    await db.flush()
    await db.refresh(run)
    logger.info("Ingestion run created id=%d triggered_by=%s", run.id, triggered_by)
    return run


async def update_ingestion_run(
    db: AsyncSession,
    run_id: int,
    status: str,
    articles_fetched: int = 0,
    articles_vectorized: int = 0,
    error_message: Optional[str] = None,
) -> None:
    await db.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id)
        .values(
            status=status,
            completed_at=datetime.now(timezone.utc),
            articles_fetched=articles_fetched,
            articles_vectorized=articles_vectorized,
            error_message=error_message,
        )
    )
    await db.flush()
    logger.info("Ingestion run updated id=%d status=%s fetched=%d vectorized=%d",
                run_id, status, articles_fetched, articles_vectorized)


async def get_ingestion_runs(db: AsyncSession, limit: int = 20) -> List[IngestionRun]:
    result = await db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    )
    rows = list(result.scalars().all())
    logger.debug("Fetched %d ingestion runs", len(rows))
    return rows


async def get_ingestion_run(
    db: AsyncSession, run_id: int
) -> Optional[IngestionRun]:
    result = await db.execute(
        select(IngestionRun).where(IngestionRun.id == run_id)
    )
    return result.scalar_one_or_none()
