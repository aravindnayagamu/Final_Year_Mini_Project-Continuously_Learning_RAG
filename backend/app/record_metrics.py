from __future__ import annotations

import os
import json
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
import sqlite3

METRICS_PATH = Path(__file__).resolve().parent / "metrics.json"
_LOCK = threading.Lock()

# Remove common function words and generic prompt words; keep topic/category terms.
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "how", "in", "into", "is", "it", "its", "may", "might", "more",
    "most", "of", "on", "or", "our", "should", "so", "some", "such", "than",
    "that", "the", "their", "them", "there", "these", "they", "this", "those",
    "to", "was", "were", "what", "when", "where", "which", "who", "why", "will",
    "with", "would", "you", "your", "please", "tell", "give", "explain", "summarize",
    "summary", "news", "article", "articles", "story", "stories", "important",
    "relevant", "retrieved", "context", "information", "developments", "development",
    "latest", "current", "major", "about", "include", "provide", "according",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_metrics() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": None,
        "methodology": {
            "relevance": "Heuristic keyword-overlap proxy; a chunk is marked relevant when at least one meaningful query token overlaps.",
            "precision@6": "Heuristic precision over the six returned results; not manually judged relevance.",
            "recall@6": "Requires a set of known relevant chunk IDs. Remains null until ground truth is supplied.",
            "contextual_precision": "Average precision calculated from the heuristic relevance labels and returned ranking.",
            "recent_precision_and_historical_precision": "Heuristic topical relevance ratio within each database, not temporal classification accuracy.",
        },
        "relevance": {
            "total": 0,
            "relevant": 0,
            "relevance_score": 0.0,
            "method": "heuristic_keyword_overlap",
        },
        "precision@6": {
            "queries": 0,
            "total": 0,
            "relevant": 0,
            "precision_score": None,
            "method": "heuristic_keyword_overlap",
        },
        "recall@6": {
            "queries": 0,
            "evaluated_queries": 0,
            "relevant_retrieved": 0,
            "known_relevant": 0,
            "recall_score": None,
            "status": "Not evaluated: supply ground_truth_relevant_ids to update_metrics().",
        },
        "contextual_precision": {
            "queries": 0,
            "contextual_precision_score": None,
            "method": "heuristic_keyword_overlap",
        },
        "recent_precision": {
            "total": 0,
            "relevant": 0,
            "precision_score": 0.0,
            "method": "heuristic_keyword_overlap",
        },
        "historical_precision": {
            "total": 0,
            "relevant": 0,
            "precision_score": 0.0,
            "method": "heuristic_keyword_overlap",
        },
        "temporal_assignment": {
            "verified": 0,
            "correct": 0,
            "accuracy_score": None,
            "unknown_timestamp_count": 0,
        },
        "retrieval_latency_ms": {
            "count": 0,
            "last": None,
            "average": None,
            "total": 0.0,
        },
        "chunks_retrieved": {
            "total": 0,
            "recent": 0,
            "historical": 0,
            "unknown_source": 0,
        },
        "last_call": None,
    }


def _load_metrics() -> dict[str, Any]:
    if not METRICS_PATH.exists():
        return _empty_metrics()
    try:
        with METRICS_PATH.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        # Preserve new keys if the schema expands in a later version.
        defaults = _empty_metrics()
        for key, value in defaults.items():
            if key not in saved:
                saved[key] = value
            elif isinstance(value, dict) and isinstance(saved[key], dict):
                for subkey, subvalue in value.items():
                    saved[key].setdefault(subkey, subvalue)
        return saved
    except (OSError, json.JSONDecodeError):
        # Start clean if the metrics file is missing or invalid JSON.
        return _empty_metrics()


def _save_metrics(metrics: dict[str, Any]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = METRICS_PATH.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2, ensure_ascii=False)
        file.write("\n")
    temp_path.replace(METRICS_PATH)


def _words(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(word) >= 2 and word not in _STOP_WORDS
    }


def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ing", "ers", "ies", "es", "ed", "er", "ly", "tion", "tions", "ment", "al", "ic", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            if suffix == "ies":
                return w[:-3] + "y"
            return w[:-len(suffix)]

    return w


_TOPIC_SYNONYMS = {
    "sports": {"cricket", "football", "soccer", "tennis", "hockey", "badminton", "chess", "match", "matches", "tournament", "player", "players", "score", "scores", "game", "games", "league", "cup", "ipl", "bcci", "fifa", "athlete", "athletes", "championship", "stadium", "wicket", "wickets", "run", "runs", "goal", "goals", "batsman", "bowler", "racing", "medal", "olympics", "kabaddi"},
    "sport": {"cricket", "football", "soccer", "tennis", "hockey", "badminton", "chess", "match", "matches", "tournament", "player", "players", "score", "scores", "game", "games", "league", "cup", "ipl", "bcci", "fifa", "athlete", "athletes", "championship", "stadium", "wicket", "wickets", "run", "runs", "goal", "goals", "batsman", "bowler", "racing", "medal", "olympics", "kabaddi"},
    "political": {"election", "elections", "bjp", "congress", "party", "parties", "minister", "ministers", "parliament", "govt", "government", "assembly", "cm", "pm", "mla", "mp", "vote", "voters", "voting", "leader", "leaders", "cabinet", "bill", "court", "ruling", "opposition", "modi", "rahul", "gandhi", "governor", "coalition", "poll", "polls"},
    "politics": {"election", "elections", "bjp", "congress", "party", "parties", "minister", "ministers", "parliament", "govt", "government", "assembly", "cm", "pm", "mla", "mp", "vote", "voters", "voting", "leader", "leaders", "cabinet", "bill", "court", "ruling", "opposition", "modi", "rahul", "gandhi", "governor", "coalition", "poll", "polls"},
    "financial": {"market", "markets", "stock", "stocks", "shares", "rbi", "sensex", "nifty", "inflation", "tax", "taxes", "rupee", "dollar", "bank", "banks", "banking", "crore", "growth", "revenue", "trade", "company", "companies", "firm", "firms", "startup", "invest", "investment", "investors", "gdp", "profit", "quarter", "economy", "fiscal", "ceo", "industry", "industries"},
    "business": {"market", "markets", "stock", "stocks", "shares", "rbi", "sensex", "nifty", "inflation", "tax", "taxes", "rupee", "dollar", "bank", "banks", "banking", "crore", "growth", "revenue", "trade", "company", "companies", "firm", "firms", "startup", "invest", "investment", "investors", "gdp", "profit", "quarter", "economy", "fiscal", "ceo", "industry", "industries"},
    "national": {"india", "delhi", "centre", "nation", "country", "central", "union", "police", "supreme court", "nationwide", "pm", "modi", "president", "indian"},
    "state": {"tamil nadu", "chennai", "madurai", "coimbatore", "kerala", "mumbai", "maharashtra", "karnataka", "bengaluru", "kolkata", "bengal", "district", "collector", "panchayat", "local", "municipal", "corporation", "stalin", "cm", "city", "civic"},
    "district": {"tamil nadu", "chennai", "madurai", "coimbatore", "kerala", "mumbai", "maharashtra", "karnataka", "bengaluru", "kolkata", "bengal", "district", "collector", "panchayat", "local", "municipal", "corporation", "stalin", "cm", "city", "civic"},
}


def _normalise_item(item: Any, default_source: str) -> dict[str, Any]:
    if isinstance(item, Mapping):
        content = item.get("document", item.get("page_content", item.get("content", "")))
        metadata = item.get("metadata") or {}
        source = item.get("news_type") or item.get("source_type") or default_source
        record_id = item.get("id") or item.get("chunk_id") or metadata.get("chunk_id")
        distance = item.get("distance")
        relevance = item.get("relevance")
    else:
        content = getattr(item, "page_content", str(item))
        metadata = getattr(item, "metadata", {}) or {}
        source = default_source
        record_id = metadata.get("chunk_id") or metadata.get("id")
        distance = getattr(item, "distance", None)
        relevance = getattr(item, "relevance", None)

    if distance is None and "distance" in metadata:
        try:
            distance = float(metadata["distance"])
        except (ValueError, TypeError):
            pass
    if relevance is None and "relevance" in metadata:
        try:
            relevance = float(metadata["relevance"])
        except (ValueError, TypeError):
            pass

    source_text = str(source or "unknown").lower()
    if "recent" in source_text:
        source = "recent"
    elif "historical" in source_text or "historic" in source_text or "old" == source_text:
        source = "historical"
    else:
        source = "unknown"

    return {
        "document": str(content or ""),
        "metadata": dict(metadata),
        "source": source,
        "id": str(record_id) if record_id is not None else None,
        "distance": distance,
        "relevance": relevance,
    }


def _is_relevant(query: str, query_tokens: set[str], content: str, distance: float | None = None, relevance: float | None = None) -> tuple[bool, float]:
    content_str = content.strip()
    if not content_str:
        return False, 0.0

    if relevance is not None and relevance >= 0.20:
        return True, round(min(100.0, relevance * 100.0), 2)

    if distance is not None and distance <= 1.15:
        score = round(max(0.0, min(100.0, (1.0 - (distance / 1.5)) * 100.0)), 2)
        return True, score

    if not query_tokens:
        raw_words = {w for w in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(w) >= 2}
        if raw_words:
            return True, 100.0
        return False, 0.0

    content_tokens = _words(content_str)
    content_stems = {_stem(w) for w in content_tokens}
    query_stems = {_stem(w) for w in query_tokens}

    direct_overlap = query_tokens.intersection(content_tokens)
    stem_overlap = query_stems.intersection(content_stems)

    topic_match = False
    content_lower = content_str.lower()
    for qt in query_tokens:
        stemmed_qt = _stem(qt)
        for topic_key, syns in _TOPIC_SYNONYMS.items():
            if qt == topic_key or stemmed_qt == _stem(topic_key):
                if syns.intersection(content_tokens) or {_stem(s) for s in syns}.intersection(content_stems):
                    topic_match = True
                    break
                for syn in syns:
                    if " " in syn and syn in content_lower:
                        topic_match = True
                        break
        if topic_match:
            break

    substring_match = False
    for qt in query_tokens:
        if len(qt) >= 4 and qt in content_lower:
            substring_match = True
            break

    if direct_overlap or stem_overlap or topic_match or substring_match:
        matched_count = max(len(direct_overlap), len(stem_overlap), 1 if (topic_match or substring_match) else 0)
        score = round(min(100.0, (matched_count / len(query_tokens)) * 100.0), 2)
        return True, max(score, 60.0)

    return False, 0.0


def _score_pct(relevant: int, total: int) -> float:
    return round((relevant / total) * 100.0, 2) if total else 0.0


def _contextual_precision(labels: list[bool]) -> float | None:
    relevant_total = sum(labels)
    if not labels or not relevant_total:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, is_relevant in enumerate(labels, start=1):
        if is_relevant:
            hits += 1
            precision_sum += hits / rank

    return round(100.0 * precision_sum / relevant_total, 2)


_timestamp_cache: dict[str, str | None] = {}


def _lookup_timestamp(metadata: dict[str, Any]) -> str | None:
    paper_id = metadata.get("paper_id")
    source = metadata.get("source") or metadata.get("source_name")
    if not paper_id and source:
        paper_id = Path(str(source)).stem.rsplit("_", 1)[-1]
    if not paper_id:
        return None

    if paper_id in _timestamp_cache:
        return _timestamp_cache[paper_id]

    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            import psycopg2
            sync_url = db_url.replace("+asyncpg", "")
            with psycopg2.connect(sync_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT retrieval_time FROM documents WHERE paper_id = %s",
                        (paper_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        val = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                        _timestamp_cache[paper_id] = val
                        return val
        except Exception:
            pass

    db_paths = [
        Path(__file__).resolve().parent.parent / "metadata.db",
        Path(__file__).resolve().parent / "metadata.db",
    ]
    for db_path in db_paths:
        if db_path.exists():
            try:
                with sqlite3.connect(db_path) as conn:
                    row = conn.execute(
                        "SELECT paper_retrieval_time FROM document_metadata WHERE paper_id = ? OR source_name = ?",
                        (paper_id, paper_id)
                    ).fetchone()
                    if row and row[0]:
                        val = str(row[0])
                        _timestamp_cache[paper_id] = val
                        return val
            except Exception:
                pass
    _timestamp_cache[paper_id] = None
    return None


def _check_temporal_assignment(item: dict[str, Any], metrics: dict[str, Any]) -> None:
    timestamp = item["metadata"].get("paper_retrieval_time")
    if not timestamp:
        timestamp = _lookup_timestamp(item["metadata"])
        if timestamp:
            item["metadata"]["paper_retrieval_time"] = timestamp
    if not timestamp:
        metrics["temporal_assignment"]["unknown_timestamp_count"] += 1
        verified = metrics["temporal_assignment"]["verified"]
        correct = metrics["temporal_assignment"]["correct"]
        unknown = metrics["temporal_assignment"]["unknown_timestamp_count"]
        total = verified + unknown
        metrics["temporal_assignment"]["accuracy_score"] = _score_pct(correct, total) if total else None
        return
    try:
        parsed = datetime.fromisoformat(str(timestamp))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        metrics["temporal_assignment"]["unknown_timestamp_count"] += 1
        verified = metrics["temporal_assignment"]["verified"]
        correct = metrics["temporal_assignment"]["correct"]
        unknown = metrics["temporal_assignment"]["unknown_timestamp_count"]
        total = verified + unknown
        metrics["temporal_assignment"]["accuracy_score"] = _score_pct(correct, total) if total else None
        return

    expected_source = "recent" if parsed >= datetime.now(timezone.utc) - timedelta(hours=24) else "historical"
    if item["source"] not in ("recent", "historical"):
        return
    metrics["temporal_assignment"]["verified"] += 1
    if item["source"] == expected_source:
        metrics["temporal_assignment"]["correct"] += 1
    verified = metrics["temporal_assignment"]["verified"]
    correct = metrics["temporal_assignment"]["correct"]
    unknown = metrics["temporal_assignment"]["unknown_timestamp_count"]
    total = verified + unknown
    metrics["temporal_assignment"]["accuracy_score"] = _score_pct(correct, total) if total else None


def update_metrics(
    query: str,
    documents: Iterable[Any],
    source: str = "unknown",
    retrieval_time_ms: float | None = None,
    track_precision_at_6: bool = False,
    ground_truth_relevant_ids: Iterable[str] | None = None,
) -> dict[str, Any]:

    raw_items = list(documents or [])
    items = [_normalise_item(item, source) for item in raw_items]
    query_tokens = _words(query or "")
    labels: list[bool] = []
    scored: list[tuple[dict[str, Any], bool, float]] = []
    for item in items:
        relevant, score = _is_relevant(
            query=query or "",
            query_tokens=query_tokens,
            content=item["document"],
            distance=item.get("distance"),
            relevance=item.get("relevance"),
        )
        labels.append(relevant)
        scored.append((item, relevant, score))

    with _LOCK:
        metrics = _load_metrics()
        relevance = metrics["relevance"]
        relevance["total"] += len(items)
        relevance["relevant"] += sum(labels)
        relevance["relevance_score"] = _score_pct(relevance["relevant"], relevance["total"])

        chunks = metrics["chunks_retrieved"]
        chunks["total"] += len(items)
        for item, relevant, _score in scored:
            if item["source"] == "recent":
                target = metrics["recent_precision"]
                chunks["recent"] += 1
            elif item["source"] == "historical":
                target = metrics["historical_precision"]
                chunks["historical"] += 1
            else:
                target = None
                chunks["unknown_source"] += 1
            if target is not None:
                target["total"] += 1
                target["relevant"] += int(relevant)
                target["precision_score"] = _score_pct(target["relevant"], target["total"])
            _check_temporal_assignment(item, metrics)

        contextual_score = _contextual_precision(labels)
        if contextual_score is not None:
            contextual = metrics["contextual_precision"]
            previous_queries = contextual["queries"]
            current_mean = contextual["contextual_precision_score"]
            if current_mean is None:
                current_mean = 0.0
            contextual["contextual_precision_score"] = round(
                ((current_mean * previous_queries) + contextual_score) / (previous_queries + 1),
                2,
            )
            contextual["queries"] += 1

        if track_precision_at_6:
            top_six = scored[:6]
            relevant_top_six = sum(is_relevant for _item, is_relevant, _score in top_six)
            precision = metrics["precision@6"]
            precision["queries"] += 1
            # Precision@6 uses 6 as the denominator; missing results count as
            # non-retrieved/non-relevant positions if fewer than six are returned.
            precision["total"] += 6
            precision["relevant"] += relevant_top_six
            precision["precision_score"] = _score_pct(precision["relevant"], precision["total"])

        recall = metrics["recall@6"]
        recall["queries"] += 1
        if ground_truth_relevant_ids is not None:
            known_ids = {str(value) for value in ground_truth_relevant_ids}
            if known_ids:
                top_ids = {item["id"] for item, _relevant, _score in scored[:6] if item["id"] is not None}
                found = len(top_ids.intersection(known_ids))
                recall["evaluated_queries"] += 1
                recall["relevant_retrieved"] += found
                recall["known_relevant"] += len(known_ids)
                recall["recall_score"] = _score_pct(
                    recall["relevant_retrieved"], recall["known_relevant"]
                )
                recall["status"] = "Measured against supplied ground-truth relevant chunk IDs."

        if retrieval_time_ms is not None:
            latency = metrics["retrieval_latency_ms"]
            latency["count"] += 1
            latency["last"] = round(float(retrieval_time_ms), 2)
            latency["total"] += float(retrieval_time_ms)
            latency["average"] = round(latency["total"] / latency["count"], 2)
            latency["total"] = round(latency["total"], 2)

        metrics["updated_at"] = _now_iso()
        metrics["last_call"] = {
            "query": query,
            "source": source,
            "retrieved": len(items),
            "relevant_estimate": sum(labels),
            "relevance_score": _score_pct(sum(labels), len(items)),
            "retrieval_time_ms": round(float(retrieval_time_ms), 2) if retrieval_time_ms is not None else None,
            "relevance_method": "keyword_overlap_proxy",
        }
        _save_metrics(metrics)
        return metrics


def reset_metrics() -> None:
    with _LOCK:
        metrics = _empty_metrics()
        metrics["updated_at"] = _now_iso()
        _save_metrics(metrics)