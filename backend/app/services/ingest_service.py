from __future__ import annotations

import asyncio
import logging
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.db.models import RunStatus, Document
from app.services import metadata_service

logger = logging.getLogger(__name__)
settings = get_settings()

_app_dir = str(settings.app_dir)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
    logger.debug("Added app_dir to sys.path: %s", _app_dir)

try:
    from fetch_news import run_all_scrapers  # type: ignore[import]
    _fetcher_available = True
    logger.info("fetch_news module loaded successfully")
except ImportError as exc:
    _fetcher_available = False
    logger.error("Failed to import fetch_news: %s", exc)


def _read_new_sqlite_rows(sqlite_path: Path) -> list[dict]:
    if not sqlite_path.exists():
        logger.warning("SQLite metadata.db not found at %s", sqlite_path)
        return []
    rows = []
    with sqlite3.connect(str(sqlite_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT paper_id, source_name, paper_retrieval_time FROM document_metadata"
        )
        for paper_id, source_name, retrieval_time_str in cursor.fetchall():
            rows.append({
                "paper_id": paper_id,
                "source_name": source_name,
                "retrieval_time_str": retrieval_time_str,
            })
    logger.debug("Read %d rows from SQLite metadata.db", len(rows))
    return rows


def _run_vectorizer() -> int:
    script = settings.app_dir / "store_vector.py"
    if not script.exists():
        logger.error("store_vector.py not found at %s", script)
        return 0
    logger.info("Launching store_vector.py subprocess")
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        elapsed = time.perf_counter() - t0
        if result.returncode != 0:
            logger.error("store_vector.py exited with code %d | stderr: %s",
                         result.returncode, result.stderr[:500])
            return 0
        embedded_count = result.stdout.count("Embedded")
        logger.info("store_vector.py finished | elapsed=%.1fs embedded_batches=%d",
                    elapsed, embedded_count)
        return embedded_count
    except subprocess.TimeoutExpired:
        logger.error("store_vector.py timed out after 300s")
        return 0
    except Exception as exc:
        logger.exception("Unexpected error running store_vector.py: %s", exc)
        return 0


async def run_ingestion(triggered_by: str = "manual") -> int:
    async with AsyncSessionLocal() as db:
        run = await metadata_service.create_ingestion_run(db, triggered_by=triggered_by)
        run_id = run.id
        await db.commit()

    logger.info("Ingestion #%d started | triggered_by=%s", run_id, triggered_by)
    articles_fetched = 0
    articles_vectorized = 0
    error_msg: Optional[str] = None
    t0 = time.perf_counter()

    try:
        if not _fetcher_available:
            raise RuntimeError("fetch_news module not available")

        logger.info("Ingestion #%d | Step 1: Running RSS fetch", run_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_all_scrapers)
        logger.info("Ingestion #%d | RSS fetch completed", run_id)

        logger.info("Ingestion #%d | Step 2: Syncing SQLite → Postgres", run_id)
        sqlite_path = settings.app_dir.parent / "metadata.db"
        all_rows = _read_new_sqlite_rows(sqlite_path)
        read_dir = settings.app_dir / "news_database" / "read"

        async with AsyncSessionLocal() as db:
            for row in all_rows:
                try:
                    rt: Optional[datetime] = datetime.fromisoformat(row["retrieval_time_str"])
                except (ValueError, TypeError):
                    rt = None
                safe_source = row["source_name"].replace("/", "").replace("\\", "")
                pdf_name = f"{safe_source}_{row['paper_id']}.pdf"
                is_read = (read_dir / pdf_name).exists()
                status_val = "vectorized" if is_read else "pending"
                vectorized_at_val = datetime.now(timezone.utc) if is_read else None
                await metadata_service.upsert_document(
                    db=db,
                    paper_id=row["paper_id"],
                    source_name=row["source_name"],
                    retrieval_time=rt,
                    file_name=pdf_name,
                    vectorization_status=status_val,
                    vectorized_at=vectorized_at_val,
                )
            await db.commit()

        articles_fetched = len(all_rows)
        logger.info("Ingestion #%d | Synced %d documents to Postgres", run_id, articles_fetched)

        logger.info("Ingestion #%d | Step 3: Running vectorizer", run_id)
        articles_vectorized = await loop.run_in_executor(None, _run_vectorizer)

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            pending_docs = (
                await db.execute(
                    select(Document).where(Document.vectorization_status == "pending")
                )
            ).scalars().all()
            for doc in pending_docs:
                if doc.file_name and (read_dir / doc.file_name).exists():
                    doc.vectorization_status = "vectorized"
                    doc.vectorized_at = datetime.now(timezone.utc)
            await db.commit()

        status = RunStatus.completed.value

    except Exception as exc:
        logger.exception("Ingestion #%d failed: %s", run_id, exc)
        error_msg = str(exc)
        status = RunStatus.failed.value

    elapsed = time.perf_counter() - t0
    async with AsyncSessionLocal() as db:
        await metadata_service.update_ingestion_run(
            db=db,
            run_id=run_id,
            status=status,
            articles_fetched=articles_fetched,
            articles_vectorized=articles_vectorized,
            error_message=error_msg,
        )
        await db.commit()

    logger.info(
        "Ingestion #%d complete | status=%s fetched=%d vectorized=%d elapsed=%.1fs",
        run_id, status, articles_fetched, articles_vectorized, elapsed,
    )
    return run_id
