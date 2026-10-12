from __future__ import annotations

import asyncio
import functools
import os
import logging
import re
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
from app.services import metadata_service, pipeline_service

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


def _run_vectorizer(budget_seconds: float) -> int:
    script = settings.app_dir / "store_vector.py"
    if not script.exists():
        logger.error("store_vector.py not found at %s", script)
        return 0
    logger.info("Launching store_vector.py subprocess | budget=%.0fs", budget_seconds)
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["INGEST_VECTORIZE_DEADLINE"] = str(time.time() + budget_seconds)
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=budget_seconds + 30,
            env=env,
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
        logger.error("store_vector.py timed out after %.0fs", budget_seconds + 30)
        return 0
    except Exception as exc:
        logger.exception("Unexpected error running store_vector.py: %s", exc)
        return 0


async def run_ingestion(triggered_by: str = "manual") -> int:
    total_budget = float(settings.ingest_timeout_seconds)

    async with AsyncSessionLocal() as db:
        await metadata_service.fail_stale_ingestion_runs(db, int(total_budget) + 60)
        run = await metadata_service.create_ingestion_run(db, triggered_by=triggered_by)
        run_id = run.id
        await db.commit()

    logger.info("Ingestion #%d started | triggered_by=%s | budget=%.0fs", run_id, triggered_by, total_budget)
    state = {"fetched": 0, "vectorized": 0}
    error_msg: Optional[str] = None
    t0 = time.perf_counter()

    def remaining() -> float:
        return total_budget - (time.perf_counter() - t0)

    async def _pipeline() -> None:
        if not _fetcher_available:
            raise RuntimeError("fetch_news module not available")

        loop = asyncio.get_running_loop()

        logger.info("Ingestion #%d | Step 1: Running RSS fetch", run_id)
        fetch_budget = max(30.0, total_budget * 0.35)
        await loop.run_in_executor(None, functools.partial(run_all_scrapers, fetch_budget))
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
                safe_source = re.sub(r'[\\/*?:"<>|]', "", row["source_name"])
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

        state["fetched"] = len(all_rows)
        logger.info("Ingestion #%d | Synced %d documents to Postgres", run_id, state["fetched"])

        logger.info("Ingestion #%d | Step 3: Running vectorizer", run_id)
        vectorize_budget = max(30.0, remaining() - 90.0)
        state["vectorized"] = await loop.run_in_executor(
            None, functools.partial(_run_vectorizer, vectorize_budget)
        )

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

        logger.info("Ingestion #%d | Step 4: Moving >24h chunks to historical store", run_id)
        try:
            sep = await loop.run_in_executor(None, pipeline_service.run_separation)
            logger.info("Ingestion #%d | separation result: %s", run_id, sep)
        except Exception as exc:
            logger.warning("Ingestion #%d | separation step failed: %s", run_id, exc)

    try:
        await asyncio.wait_for(_pipeline(), timeout=total_budget)
        status = RunStatus.completed.value

    except asyncio.TimeoutError:
        logger.error("Ingestion #%d exceeded %.0fs limit", run_id, total_budget)
        error_msg = f"Run exceeded the {int(total_budget)}s time limit."
        status = RunStatus.failed.value

    except Exception as exc:
        logger.exception("Ingestion #%d failed: %s", run_id, exc)
        error_msg = str(exc)
        status = RunStatus.failed.value

    articles_fetched = state["fetched"]
    articles_vectorized = state["vectorized"]

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