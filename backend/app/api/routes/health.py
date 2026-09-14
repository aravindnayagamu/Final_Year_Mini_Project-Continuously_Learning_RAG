from __future__ import annotations

import logging

from fastapi import APIRouter

from app.db.session import engine
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/health", tags=["Health"])
async def health_check() -> dict:
    logger.debug("Health check requested")
    health: dict = {"status": "ok", "services": {}}

    try:
        import sqlalchemy
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        health["services"]["postgres"] = "ok"
        logger.debug("Postgres health: ok")
    except Exception as exc:
        health["services"]["postgres"] = f"error: {exc}"
        health["status"] = "degraded"
        logger.warning("Postgres health check failed: %s", exc)

    chroma_db = settings.chroma_db_path
    health["services"]["chromadb"] = "ok" if chroma_db.exists() else "not found"
    logger.debug("ChromaDB health: %s", health["services"]["chromadb"])

    health["services"]["gemini_api"] = (
        "configured" if settings.gemini_api_key else "missing key"
    )
    logger.debug("Gemini API key: %s", health["services"]["gemini_api"])

    from app.core.redis import ping_redis
    redis_ok = await ping_redis()
    health["services"]["redis"] = "ok" if redis_ok else ("not configured" if not settings.redis_url else "unreachable")
    health["services"]["celery"] = "configured" if settings.redis_url else "not configured"

    return health
