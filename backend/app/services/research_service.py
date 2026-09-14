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
from app.services import metadata_service
from app.services.rag_service import _get_gemini_client
from app.retrive import vector_store

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
        vector_store.add_texts(texts=texts, metadatas=metadatas)

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
    try:
        vector_store._collection.delete(where={"paper_id": paper_id})
    except Exception as exc:
        logger.warning("Could not delete Chroma vectors for %s: %s", paper_id, exc)

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


async def query_research(
    question: str,
    paper_id: Optional[str] = None,
    k: int = 5,
) -> ResearchQueryResponse:
    t0 = time.perf_counter()
    where_filter = {"paper_id": paper_id} if paper_id else {"doc_type": "research_paper"}

    try:
        results = vector_store._collection.query(
            query_texts=[question],
            n_results=k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.warning("Vector search with filter failed, falling back: %s", exc)
        results = vector_store._collection.query(
            query_texts=[question],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

    retrieval_time = time.perf_counter() - t0
    retrieval_time_ms = retrieval_time * 1000

    relevance_fn = vector_store._select_relevance_score_fn()
    sources: List[SourceChunk] = []
    context_chunks_text: List[str] = []

    if results and results.get("documents") and len(results["documents"]) > 0:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

        for doc_str, meta, dist in zip(docs, metas, dists):
            rel = relevance_fn(dist)
            sources.append(
                SourceChunk(
                    document=doc_str,
                    source=meta.get("source", "Research Paper"),
                    relevance=float(rel),
                    distance=float(dist),
                )
            )
            context_chunks_text.append(doc_str)

    merged_context = "\n\n".join(context_chunks_text)

    if not merged_context:
        answer = "I could not find relevant information in the uploaded research paper(s)."
    else:
        prompt = (
            "You are an expert AI research assistant.\n"
            "Answer the question accurately based on the research paper context provided below.\n"
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

    return ResearchQueryResponse(
        question=question,
        answer=answer,
        sources=sources,
        retrieval_time_ms=retrieval_time_ms,
        context_chunks=len(sources),
        model_used=settings.gemini_model,
        created_at=now_iso,
    )
