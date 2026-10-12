from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

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


def _normalise_item(item: Any, default_source: str) -> dict[str, Any]:
    if isinstance(item, Mapping):
        content = item.get("document", item.get("page_content", item.get("content", "")))
        metadata = item.get("metadata") or {}
        source = item.get("news_type") or item.get("source_type") or default_source
        record_id = item.get("id") or item.get("chunk_id") or metadata.get("chunk_id")
        distance = item.get("distance")
    else:
        content = getattr(item, "page_content", str(item))
        metadata = getattr(item, "metadata", {}) or {}
        source = default_source
        record_id = metadata.get("chunk_id") or metadata.get("id")
        distance = None

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
    }


def _is_relevant(query_tokens: set[str], content: str) -> tuple[bool, float]:
    if not query_tokens:
        return False, 0.0
    overlap = query_tokens.intersection(_words(content))
    score = 100.0 * len(overlap) / len(query_tokens)

    return bool(overlap), round(score, 2)


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


def _check_temporal_assignment(item: dict[str, Any], metrics: dict[str, Any]) -> None:
    timestamp = item["metadata"].get("paper_retrieval_time")
    if not timestamp:
        metrics["temporal_assignment"]["unknown_timestamp_count"] += 1
        return
    try:
        parsed = datetime.fromisoformat(str(timestamp))
        if parsed.tzinfo is None:
            # Existing app timestamps without a timezone are treated as UTC,
            # matching separate_recent_data.py's current rule.
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        metrics["temporal_assignment"]["unknown_timestamp_count"] += 1
        return

    expected_source = "recent" if parsed >= datetime.now(timezone.utc) - timedelta(hours=24) else "historical"
    if item["source"] not in ("recent", "historical"):
        return
    metrics["temporal_assignment"]["verified"] += 1
    if item["source"] == expected_source:
        metrics["temporal_assignment"]["correct"] += 1
    verified = metrics["temporal_assignment"]["verified"]
    correct = metrics["temporal_assignment"]["correct"]
    metrics["temporal_assignment"]["accuracy_score"] = _score_pct(correct, verified)


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
        relevant, score = _is_relevant(query_tokens, item["document"])
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