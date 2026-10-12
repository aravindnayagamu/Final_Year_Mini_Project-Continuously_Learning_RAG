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


def record_query_metrics(question: str, retrieved: list, retrieval_time_ms: float) -> None:
    try:
        from record_metrics import update_metrics  # type: ignore[import]

        update_metrics(
            query=question,
            documents=retrieved,
            source="unknown",
            retrieval_time_ms=retrieval_time_ms,
            track_precision_at_6=True,
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