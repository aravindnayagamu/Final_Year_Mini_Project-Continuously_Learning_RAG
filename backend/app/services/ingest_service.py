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
        fetch_budget = min(45.0, total_budget * 0.15)
        await loop.run_in_executor(None, functools.partial(run_all_scrapers, fetch_budget))
        logger.info("Ingestion #%d | RSS fetch completed", run_id)

        logger.info("Ingestion #%d | Step 2: Reconciling document metadata in Postgres", run_id)
        sqlite_path = settings.app_dir.parent / "metadata.db"
        all_rows = _read_new_sqlite_rows(sqlite_path)
        read_dir = settings.app_dir / "news_database" / "read"

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            existing_ids = set((await db.execute(select(Document.paper_id))).scalars().all())
            new_rows = [r for r in all_rows if r["paper_id"] not in existing_ids]

            if new_rows:
                read_files = {p.name for p in read_dir.glob("*.pdf")}
                now_utc = datetime.now(timezone.utc)
                records = []
                for row in new_rows:
                    try:
                        rt: Optional[datetime] = datetime.fromisoformat(row["retrieval_time_str"])
                    except (ValueError, TypeError):
                        rt = None
                    safe_source = re.sub(r'[\\/*?:"<>|]', "", row["source_name"])
                    pdf_name = f"{safe_source}_{row['paper_id']}.pdf"
                    is_read = pdf_name in read_files
                    status_val = "vectorized" if is_read else "pending"
                    vectorized_at_val = now_utc if is_read else None
                    records.append({
                        "paper_id": row["paper_id"],
                        "source_name": row["source_name"],
                        "retrieval_time": rt,
                        "file_name": pdf_name,
                        "vectorization_status": status_val,
                        "vectorized_at": vectorized_at_val,
                    })

                for i in range(0, len(records), 500):
                    batch = records[i:i+500]
                    stmt = pg_insert(Document).values(batch).on_conflict_do_nothing()
                    await db.execute(stmt)
                await db.commit()

            total_docs = await db.scalar(select(func.count(Document.paper_id)))
            state["fetched"] = total_docs or len(all_rows)
        logger.info("Ingestion #%d | Total %d documents in Postgres metadata", run_id, state["fetched"])

        logger.info("Ingestion #%d | Step 3: Running vectorizer", run_id)
        vectorize_budget = min(60.0, max(30.0, remaining() - 30.0))
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
            if pending_docs:
                read_files = {p.name for p in read_dir.glob("*.pdf")}
                now_utc = datetime.now(timezone.utc)
                updated = False
                for doc in pending_docs:
                    if doc.file_name and doc.file_name in read_files:
                        doc.vectorization_status = "vectorized"
                        doc.vectorized_at = now_utc
                        updated = True
                if updated:
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