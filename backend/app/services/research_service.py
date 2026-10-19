from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select, delete

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.db.models import Document as DocumentModel
from app.schemas.query import SourceChunk
from app.schemas.research import (
    ResearchPaperOut,
    ResearchQueryResponse,
    ResearchUploadResponse,
)
from app.services import cache_service, metadata_service
from app.services.rag_service import _get_gemini_client
from app.retrive import recent_store, historical_store

logger = logging.getLogger(__name__)
settings = get_settings()

RESEARCH_DIR = settings.app_dir / "research_database"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)


async def process_and_store_paper(
    file_bytes: bytes,
    filename: str,
) -> ResearchUploadResponse:
    paper_id = hashlib.md5(file_bytes).hexdigest()
    safe_name = f"{paper_id}_{filename}"
    file_path = RESEARCH_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    reader = PdfReader(io.BytesIO(file_bytes))
    extracted_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            extracted_text += txt + "\n"

    extracted_text = extracted_text.strip()
    if not extracted_text:
        raise ValueError("No extractable text found in the PDF file.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=250,
        add_start_index=True,
    )
    splits = splitter.split_text(extracted_text)

    texts: List[str] = []
    metadatas: List[dict] = []

    for chunk in splits:
        cleaned = chunk.strip().encode("utf-8", errors="ignore").decode("utf-8")
        if cleaned:
            texts.append(cleaned)
            metadatas.append({
                "source": filename,
                "paper_id": paper_id,
                "doc_type": "research_paper",
            })

    if texts:
        ids = [f"{paper_id}_{i}" for i in range(len(texts))]
        recent_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    title = filename.rsplit(".", 1)[0]
    async with AsyncSessionLocal() as db:
        await metadata_service.upsert_document(
            db=db,
            paper_id=paper_id,
            source_name="ResearchPaper",
            title=title,
            retrieval_time=datetime.now(timezone.utc),
            file_name=filename,
            vectorization_status="vectorized",
            chunk_count=len(texts),
        )
        await db.commit()

    logger.info("Indexed research paper %s with %d chunks", filename, len(texts))

    return ResearchUploadResponse(
        paper_id=paper_id,
        file_name=filename,
        chunk_count=len(texts),
        message=f"Successfully parsed and indexed {len(texts)} chunks.",
    )


async def get_research_papers() -> List[ResearchPaperOut]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.source_name == "ResearchPaper")
            .order_by(DocumentModel.created_at.desc())
        )
        res = await db.execute(stmt)
        docs = res.scalars().all()
        return [
            ResearchPaperOut(
                paper_id=d.paper_id,
                file_name=d.file_name or d.paper_id,
                title=d.title,
                chunk_count=d.chunk_count,
                vectorization_status=d.vectorization_status,
                created_at=d.created_at,
            )
            for d in docs
        ]


async def delete_research_paper(paper_id: str) -> bool:
    for store in (recent_store, historical_store):
        try:
            store._collection.delete(where={"paper_id": paper_id})
        except Exception as exc:
            logger.warning("Could not delete Chroma vectors for %s from store: %s", paper_id, exc)

    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(DocumentModel).where(DocumentModel.paper_id == paper_id)
        )
        await db.commit()

    for p in RESEARCH_DIR.glob(f"{paper_id}_*"):
        try:
            p.unlink()
        except OSError:
            pass

    logger.info("Deleted research paper %s", paper_id)
    return True


def _is_unavailable_response(answer: str, context_chunks: int, sources: list) -> bool:
    if context_chunks == 0 or not sources:
        return True
    lower = answer.lower().strip()
    negative_phrases = (
        "chunk not available",
        "chunks not available",
        "no chunk available",
        "no chunks available",
        "no chunks found",
        "could not find",
        "cannot find",
        "not found in the retrieved",
        "not found in the context",
        "not available in the retrieved",
        "not available in the context",
        "no relevant information",
    )

    return any(phrase in lower for phrase in negative_phrases)


def _search_store_candidates(
    store,
    question: str,
    n_results: int,
    where_filter: Optional[dict] = None,
) -> List[tuple[str, dict, float]]:
    try:
        kwargs = {
            "query_texts": [question],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter
        res = store._collection.query(**kwargs)
        if not res or not res.get("documents") or len(res["documents"]) == 0:
            return []
        docs = res["documents"][0]
        metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
        dists = res["distances"][0] if res.get("distances") else [0.0] * len(docs)
        return list(zip(docs, metas, dists))
    except Exception as exc:
        logger.warning("Vector search on store failed: %s", exc)
        return []


async def query_research(
    question: str,
    paper_id: Optional[str] = None,
    k: int = 5,
) -> ResearchQueryResponse:
    cache_key = cache_service.build_cache_key("research_query", paper_id or "all", question, k)
    cached = await cache_service.get_cached_json(cache_key)
    if cached:
        cached_answer = cached.get("answer", "")
        cached_chunks = int(cached.get("context_chunks", 0))
        cached_sources = cached.get("sources", [])
        if _is_unavailable_response(cached_answer, cached_chunks, cached_sources):
            logger.info("Ignoring unavailable cached response for research query=%r", question[:80])
            await cache_service.delete_cache_pattern(cache_key)
        else:
            logger.info("Cache hit for research query=%r paper_id=%s", question[:80], paper_id)
            return ResearchQueryResponse(
                question=cached["question"],
                answer=cached["answer"],
                sources=[SourceChunk(**s) for s in cached["sources"]],
                retrieval_time_ms=float(cached["retrieval_time_ms"]),
                context_chunks=int(cached["context_chunks"]),
                model_used=cached["model_used"] + " (cached)",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    t0 = time.perf_counter()
    candidates: List[tuple[str, dict, float]] = []

    all_registered_papers = await get_research_papers()
    if not all_registered_papers:
        return ResearchQueryResponse(
            question=question,
            answer="No research papers have been uploaded yet. Please upload a PDF research paper to begin.",
            sources=[],
            retrieval_time_ms=(time.perf_counter() - t0) * 1000,
            context_chunks=0,
            model_used=settings.gemini_model,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    if paper_id:
        where_filter = {"paper_id": paper_id}
        for store in (recent_store, historical_store):
            candidates.extend(_search_store_candidates(store, question, k * 2, where_filter))
    else:
        # Cross-paper synthesis across all uploaded papers
        k_per_paper = max(3, k)
        for p in all_registered_papers:
            p_filter = {"paper_id": p.paper_id}
            # Similarity search for that paper
            for store in (recent_store, historical_store):
                candidates.extend(_search_store_candidates(store, question, k_per_paper, p_filter))
            # Guarantee intro chunk for each paper
            for store in (recent_store, historical_store):
                try:
                    intro = store._collection.get(where={"paper_id": p.paper_id}, limit=1)
                    if intro and intro.get("documents") and len(intro["documents"]) > 0:
                        candidates.append((
                            intro["documents"][0],
                            intro["metadatas"][0] if intro.get("metadatas") else {"source": p.file_name, "paper_id": p.paper_id},
                            0.20,
                        ))
                        break
                except Exception:
                    pass

        # Query across all research papers globally
        for store in (recent_store, historical_store):
            candidates.extend(_search_store_candidates(store, question, k * 3, {"doc_type": "research_paper"}))

    retrieval_time = time.perf_counter() - t0
    retrieval_time_ms = retrieval_time * 1000

    relevance_fn = recent_store._select_relevance_score_fn()

    # Deduplicate candidate chunks by text snippet
    seen_texts = set()
    unique_candidates: List[tuple[str, dict, float]] = []
    for doc_str, meta, dist in candidates:
        key = doc_str.strip()
        if key and key not in seen_texts:
            seen_texts.add(key)
            unique_candidates.append((doc_str, meta, dist))

    # Sort by distance (lowest distance = highest similarity)
    unique_candidates.sort(key=lambda x: x[2])

    # In cross-paper synthesis, guarantee that each paper gets representation
    if not paper_id and all_registered_papers:
        paper_top_map: dict[str, list[tuple[str, dict, float]]] = {p.paper_id: [] for p in all_registered_papers}
        for doc_str, meta, dist in unique_candidates:
            pid = meta.get("paper_id")
            if pid in paper_top_map and len(paper_top_map[pid]) < 3:
                paper_top_map[pid].append((doc_str, meta, dist))

        selected_set = set()
        guaranteed_candidates: List[tuple[str, dict, float]] = []
        for pid, plist in paper_top_map.items():
            for c in plist:
                selected_set.add(c[0].strip())
                guaranteed_candidates.append(c)

        remaining_candidates = [c for c in unique_candidates if c[0].strip() not in selected_set]
        max_total = max(len(all_registered_papers) * 4, 10)
        top_candidates = guaranteed_candidates + remaining_candidates[:max(0, max_total - len(guaranteed_candidates))]
    else:
        top_candidates = unique_candidates[:k]

    sources: List[SourceChunk] = []
    context_blocks: List[str] = []

    for doc_str, meta, dist in top_candidates:
        rel = relevance_fn(dist)
        source_name = meta.get("source", "Research Paper")
        sources.append(
            SourceChunk(
                document=doc_str,
                source=source_name,
                relevance=float(rel),
                distance=float(dist),
            )
        )
        context_blocks.append(f"[Document: {source_name}]\n{doc_str}")

    merged_context = "\n\n".join(context_blocks)

    if not merged_context:
        answer = "I could not find relevant information in the uploaded research paper(s)."
    else:
        prompt = (
            "You are an expert AI research assistant.\n"
            "Answer the question accurately based on the research paper context provided below.\n"
            "When performing cross-paper synthesis or answering questions about multiple papers, synthesize findings and clearly refer to each paper by name.\n"
            "Cite methodology, findings, data, or experimental setup where relevant.\n"
            "If the answer cannot be found in the context, state that clearly.\n\n"
            f"Context:\n{merged_context}\n\n"
            f"Question:\n{question}\n\n"
            "Answer:"
        )
        client = _get_gemini_client()
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        answer = resp.text or "No response generated."

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        async with AsyncSessionLocal() as db:
            await metadata_service.log_query(
                db=db,
                question=f"[Research] {question}",
                answer=answer,
                context_chunks=len(sources),
                retrieval_time_ms=retrieval_time_ms,
                model_used=settings.gemini_model,
            )
            await db.commit()
    except Exception as exc:
        logger.error("Failed to log research query to db: %s", exc)

    if not _is_unavailable_response(answer, len(sources), sources):
        await cache_service.set_cached_json(
            cache_key,
            {
                "question": question,
                "answer": answer,
                "sources": [s.model_dump() for s in sources],
                "retrieval_time_ms": retrieval_time_ms,
                "context_chunks": len(sources),
                "model_used": settings.gemini_model,
            },
            ttl_seconds=settings.cache_ttl_seconds,
        )
    else:
        await cache_service.delete_cache_pattern(cache_key)

    return ResearchQueryResponse(
        question=question,
        answer=answer,
        sources=sources,
        retrieval_time_ms=retrieval_time_ms,
        context_chunks=len(sources),
        model_used=settings.gemini_model,
        created_at=now_iso,
    )