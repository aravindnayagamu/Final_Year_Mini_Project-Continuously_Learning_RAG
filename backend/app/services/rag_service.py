from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from typing import List

from google import genai

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.schemas.query import QueryResponse, SourceChunk
from app.services import cache_service, metadata_service

logger = logging.getLogger(__name__)
settings = get_settings()

_app_dir = str(settings.app_dir)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
    logger.debug("Added app_dir to sys.path: %s", _app_dir)

try:
    from retrive import retrieve_documents  # type: ignore[import]
    from news_response import build_prompt  # type: ignore[import]
    _rag_available = True
    logger.info("RAG modules loaded successfully (retrive, news_response)")
except ImportError as exc:
    _rag_available = False
    logger.error("Failed to import RAG modules: %s", exc)

_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        logger.debug("Initialising Gemini client (model=%s)", settings.gemini_model)
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


async def answer_question(question: str, k: int = 5) -> QueryResponse:
    if not _rag_available:
        raise RuntimeError(
            "RAG modules could not be imported. "
            "Verify APP_DIR points to the correct app directory."
        )

    cache_key = cache_service.build_cache_key("rag_query", question, k)
    cached = await cache_service.get_cached_json(cache_key)
    if cached:
        logger.info("Cache hit for question=%r", question[:80])
        return QueryResponse(
            question=cached["question"],
            answer=cached["answer"],
            sources=[SourceChunk(**s) for s in cached["sources"]],
            retrieval_time_ms=float(cached["retrieval_time_ms"]),
            context_chunks=int(cached["context_chunks"]),
            model_used=cached["model_used"] + " (cached)",
            created_at=datetime.now(timezone.utc),
        )

    logger.info("RAG query started | question=%r k=%d", question[:80], k)

    t0 = time.perf_counter()
    retrieved_docs, relevant_docs, merged_context, retrieval_time = retrieve_documents(
        question, k=k
    )
    retrieval_time_ms = retrieval_time * 1000
    logger.info(
        "Retrieval complete | chunks=%d relevant=%d latency=%.1fms",
        len(retrieved_docs), len(relevant_docs), retrieval_time_ms,
    )

    sources: List[SourceChunk] = [
        SourceChunk(
            document=r["document"],
            source=r["metadata"].get("source", "Unknown"),
            relevance=float(r["relevance"]),
            distance=float(r["distance"]),
        )
        for r in retrieved_docs
    ]

    if not merged_context:
        logger.warning("No relevant context found for question: %r", question[:80])
        answer = "I could not find the answer in the retrieved documents."
    else:
        prompt = build_prompt(question, merged_context)
        logger.debug("Calling Gemini model=%s prompt_chars=%d", settings.gemini_model, len(prompt))
        client = _get_gemini_client()
        gen_start = time.perf_counter()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        gen_ms = (time.perf_counter() - gen_start) * 1000
        answer = response.text or "No response generated."
        logger.info("Gemini response received | gen_latency=%.1fms answer_chars=%d",
                    gen_ms, len(answer))

    total_ms = (time.perf_counter() - t0) * 1000
    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            await metadata_service.log_query(
                db=db,
                question=question,
                answer=answer,
                context_chunks=len(relevant_docs),
                retrieval_time_ms=retrieval_time_ms,
                model_used=settings.gemini_model,
            )
            await db.commit()
    except Exception as exc:
        logger.error("Failed to persist query log to Postgres: %s", exc)

    logger.info("RAG query complete | total_ms=%.1f", total_ms)

    await cache_service.set_cached_json(
        cache_key,
        {
            "question": question,
            "answer": answer,
            "sources": [s.model_dump() for s in sources],
            "retrieval_time_ms": retrieval_time_ms,
            "context_chunks": len(relevant_docs),
            "model_used": settings.gemini_model,
        },
        ttl_seconds=settings.cache_ttl_seconds,
    )

    return QueryResponse(
        question=question,
        answer=answer,
        sources=sources,
        retrieval_time_ms=retrieval_time_ms,
        context_chunks=len(relevant_docs),
        model_used=settings.gemini_model,
        created_at=now,
    )
