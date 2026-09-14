from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class IngestResponse(BaseModel):
    run_id: int
    status: str
    message: str


class IngestionRunOut(BaseModel):
    id: int
    triggered_by: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    articles_fetched: int
    articles_vectorized: int
    error_message: Optional[str]

    model_config = {"from_attributes": True}
