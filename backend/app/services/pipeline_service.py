from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import sys
import threading
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document

from app.fetch_news import RSS_SOURCES
import app.record_metrics as record_metrics
from app.retrive import recent_store, historical_store
from app.summary import create_summary

logger = logging.getLogger(__name__)
settings = get_settings()

_app_dir = str(settings.app_dir)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

SUMMARY_FILE = settings.app_dir / "latest_summary.json"
_summary_lock = threading.Lock()
_separate_lock = threading.Lock()


def _group_of(source_name: str) -> str:
    return source_name.split("_", 1)[0]

async def get_sources(db: AsyncSession) -> List[Dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                Document.source_name,
                func.count(Document.paper_id),
                func.max(Document.retrieval_time),
            ).group_by(Document.source_name)
        )
    ).all()
    counts = {name: (cnt, last) for name, cnt, last in rows}

    sources: List[Dict[str, Any]] = []
    for src in RSS_SOURCES:
        name = src["source_name"]
        cnt, last = counts.get(name, (0, None))
        sources.append({
            "source_name": name,
            "group": _group_of(name),
            "url": src["url"],
            "document_count": cnt,
            "last_fetched": last,
        })
    return sources


def get_metrics() -> Dict[str, Any]:
    with record_metrics._LOCK:
        return record_metrics._load_metrics()


def reset_metrics() -> Dict[str, Any]:
    record_metrics.reset_metrics()
    return get_metrics()


def record_query_metrics(question: str, retrieved: list, retrieval_time_ms: float, candidate_pool: list | None = None) -> None:
    try:
        from record_metrics import update_metrics  # type: ignore[import]

        update_metrics(
            query=question,
            documents=retrieved,
            source="unknown",
            retrieval_time_ms=retrieval_time_ms,
            track_precision_at_6=True,
            candidate_pool=candidate_pool,
        )
    except Exception as exc:
        logger.warning("Failed to record retrieval metrics: %s", exc)


def _parse_separation_output(text: str) -> Dict[str, int]:
    keys = {
        "Historical chunks moved": "historical_moved",
        "Unknown-time chunks moved": "unknown_moved",
        "Total historical chunks moved": "total_moved",
        "Recent chunks retained": "recent_retained",
    }
    out = {v: 0 for v in keys.values()}
    for line in text.splitlines():
        for prefix, key in keys.items():
            if line.startswith(prefix) and ":" in line:
                try:
                    out[key] = int(line.rsplit(":", 1)[1].strip())
                except ValueError:
                    pass
    return out


def run_separation() -> Dict[str, Any]:
    if not _separate_lock.acquire(blocking=False):
        raise RuntimeError("Separation is already running.")
    try:
        from separate_recent_data import separate_data  # type: ignore[import]

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            separate_data()
        result = _parse_separation_output(buf.getvalue())
        result["ran_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Recent/historical separation done: %s", result)
        return result
    finally:
        _separate_lock.release()


async def run_separation_async() -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_separation)


def get_vector_store_stats() -> Dict[str, Any]:
    return {
        "recent_chunks": recent_store._collection.count(),
        "historical_chunks": historical_store._collection.count(),
    }


def get_latest_summary() -> Optional[Dict[str, Any]]:
    if not SUMMARY_FILE.exists():
        return None
    try:
        return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def generate_summary_blocking() -> Dict[str, Any]:
    if not _summary_lock.acquire(blocking=False):
        raise RuntimeError("A summary is already being generated.")
    try:
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            text = create_summary()
        payload = {
            "summary": text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_time_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        SUMMARY_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
    finally:
        _summary_lock.release()


async def generate_summary() -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, generate_summary_blocking)


def get_user_preferences() -> Dict[str, Any]:
    path = settings.app_dir / "user_preferences.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_user_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    path = settings.app_dir / "user_preferences.json"
    existing = get_user_preferences()
    existing.update(preferences)
    existing.pop("preferred_location", None)
    existing.pop("preferred_language", None)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return existing


def run_recall_benchmark(num_samples: int = 15) -> Dict[str, Any]:
    try:
        from retrive import recent_store, historical_store, retrieve_documents  # type: ignore[import]
        from record_metrics import update_metrics  # type: ignore[import]
    except ImportError:
        from app.retrive import recent_store, historical_store, retrieve_documents
        from app.record_metrics import update_metrics

    sampled_items = []
    try:
        res_r = recent_store._collection.get(limit=max(15, num_samples), include=["documents", "metadatas"])
        for doc_id, text, meta in zip(res_r.get("ids", []), res_r.get("documents", []), res_r.get("metadatas", [])):
            if text and len(text.strip()) > 60:
                sampled_items.append((doc_id, text, meta))
    except Exception:
        pass

    try:
        res_h = historical_store._collection.get(limit=10, include=["documents", "metadatas"])
        for doc_id, text, meta in zip(res_h.get("ids", []), res_h.get("documents", []), res_h.get("metadatas", [])):
            if text and len(text.strip()) > 60:
                sampled_items.append((doc_id, text, meta))
    except Exception:
        pass

    import random
    if len(sampled_items) > num_samples:
        random.seed(42)
        sampled_items = random.sample(sampled_items, num_samples)

    benchmark_results = []
    for doc_id, text, meta in sampled_items:
        title = meta.get("title") or meta.get("headline")
        if not title:
            lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
            title = lines[0] if lines else text[:100]
        query = title[:120].strip()

        target_ids = [str(doc_id)]
        paper_id = meta.get("paper_id")
        if paper_id:
            target_ids.append(str(paper_id))

        retrieved_docs, candidate_pool, _, lat_sec = retrieve_documents(query, k=3)
        lat_ms = lat_sec * 1000.0

        update_metrics(
            query=query,
            documents=retrieved_docs,
            source="benchmark",
            retrieval_time_ms=lat_ms,
            track_precision_at_6=True,
            ground_truth_relevant_ids=target_ids,
            candidate_pool=candidate_pool,
        )
        top_ids = [r.get("id") for r in retrieved_docs] + [
            str(r.get("metadata", {}).get("paper_id")) for r in retrieved_docs if r.get("metadata", {}).get("paper_id")
        ]
        hit = any(tid in top_ids for tid in target_ids)
        benchmark_results.append({
            "query": query,
            "target_id": doc_id,
            "hit": hit,
        })

    return {
        "status": "success",
        "evaluated_queries": len(benchmark_results),
        "hits": sum(1 for b in benchmark_results if b["hit"]),
        "metrics": get_metrics(),
    }