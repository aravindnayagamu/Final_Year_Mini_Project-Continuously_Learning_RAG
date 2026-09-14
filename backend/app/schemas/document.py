from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DocumentOut(BaseModel):
    paper_id: str
    source_name: str
    title: Optional[str]
    retrieval_time: Optional[datetime]
    file_name: Optional[str]
    vectorization_status: str
    chunk_count: Optional[int]
    vectorized_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStats(BaseModel):
    total: int
    vectorized: int
    pending: int
    failed: int
