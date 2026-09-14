from __future__ import annotations

import logging
from typing import Optional
from redis import asyncio as aioredis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> Optional[aioredis.Redis]:
    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
        except Exception as exc:
            logger.error("Failed to initialize Redis client: %s", exc)
            return None
    return _redis_client


async def ping_redis() -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("Redis ping failed: %s", exc)
        return False


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            logger.warning("Error closing Redis client: %s", exc)
        finally:
            _redis_client = None
