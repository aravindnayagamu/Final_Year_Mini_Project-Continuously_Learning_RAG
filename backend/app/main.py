from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.models import Base
from app.db.session import engine
from app.api.routes import health, query, documents, ingest, research
from app.workers import scheduler

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up Continual RAG API")
    logger.info("DB: %s", settings.database_url.split("@")[-1])
    logger.info("App dir: %s", settings.app_dir)
    logger.info("Gemini model: %s", settings.gemini_model)

    logger.info("Creating Postgres tables (if missing)")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Starting APScheduler (interval=%d min)", settings.fetch_interval_minutes)
    scheduler.start()

    yield

    logger.info("Shutting down Continual RAG API")
    scheduler.stop()
    await engine.dispose()
    logger.info("DB engine disposed — shutdown complete")


app = FastAPI(
    title="Continual RAG API",
    description="Backend for the Continual RAG news pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(health.router, prefix=PREFIX)
app.include_router(query.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(ingest.router, prefix=PREFIX)
app.include_router(research.router, prefix=PREFIX)

logger.debug("All routers registered under %s", PREFIX)
