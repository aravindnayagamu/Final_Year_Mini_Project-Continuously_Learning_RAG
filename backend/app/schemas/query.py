from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User's question")
    k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class SourceChunk(BaseModel):
    document: str
    source: str
    relevance: float
    distance: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceChunk]
    retrieval_time_ms: float
    context_chunks: int
    model_used: str
    created_at: datetime
