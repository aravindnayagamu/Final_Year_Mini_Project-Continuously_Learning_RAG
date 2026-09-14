from __future__ import annotations

import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def create_limiter() -> Limiter:
    storage = settings.redis_url if settings.redis_url else "memory://"
    try:
        return Limiter(key_func=get_remote_address, storage_uri=storage)
    except Exception as exc:
        logger.warning("Failed to initialize Redis limiter storage, falling back to memory: %s", exc)
        return Limiter(key_func=get_remote_address, storage_uri="memory://")


limiter = create_limiter()
