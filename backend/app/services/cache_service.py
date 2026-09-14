from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


def build_cache_key(prefix: str, *args: Any) -> str:
    raw = ":".join(str(a) for a in args)
    hashed = hashlib.sha256(raw.strip().lower().encode("utf-8")).hexdigest()
    return f"cache:{prefix}:{hashed}"


async def get_cached_json(key: str) -> Optional[dict]:
    client = get_redis()
    if client is None:
        return None
    try:
        data = await client.get(key)
        if data:
            return json.loads(data)
    except Exception as exc:
        logger.warning("Cache lookup failed for key %s: %s", key, exc)
    return None


async def set_cached_json(
    key: str,
    data: dict,
    ttl_seconds: Optional[int] = None,
) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        ttl = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
        serialized = json.dumps(data)
        await client.set(key, serialized, ex=ttl)
        return True
    except Exception as exc:
        logger.warning("Cache write failed for key %s: %s", key, exc)
        return False


async def delete_cache_pattern(pattern: str) -> int:
    client = get_redis()
    if client is None:
        return 0
    try:
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
    except Exception as exc:
        logger.warning("Cache eviction failed for pattern %s: %s", pattern, exc)
    return 0
