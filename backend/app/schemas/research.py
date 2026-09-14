from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.query import SourceChunk


class ResearchPaperOut(BaseModel):
    paper_id: str
    file_name: str
    title: Optional[str] = None
    chunk_count: Optional[int] = None
    vectorization_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ResearchUploadResponse(BaseModel):
    paper_id: str
    file_name: str
    chunk_count: int
    message: str


class ResearchQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    paper_id: Optional[str] = None
    k: int = Field(default=5, ge=1, le=20)


class ResearchQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceChunk] = []
    retrieval_time_ms: float
    context_chunks: int
    model_used: Optional[str] = None
    created_at: str
