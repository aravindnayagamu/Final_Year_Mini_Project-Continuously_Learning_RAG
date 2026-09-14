from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class VectorizationStatus(str, enum.Enum):
    pending = "pending"
    vectorized = "vectorized"
    failed = "failed"


class RunTrigger(str, enum.Enum):
    scheduler = "scheduler"
    manual = "manual"


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    paper_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retrieval_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    vectorization_status: Mapped[str] = mapped_column(
        String(32),
        default=VectorizationStatus.pending.value,
        nullable=False,
    )
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vectorized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retrieval_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    triggered_by: Mapped[str] = mapped_column(
        String(32),
        default=RunTrigger.manual.value,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=RunStatus.running.value,
        nullable=False,
    )
    articles_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    articles_vectorized: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
