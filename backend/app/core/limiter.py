import logging
from fastapi import Request
from slowapi import Limiter
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def create_limiter() -> Limiter:
    storage = settings.redis_url if settings.redis_url else "memory://"
    try:
        return Limiter(
            key_func=get_client_ip,
            storage_uri=storage,
            strategy="moving-window",
        )
    except Exception as exc:
        logger.warning("Failed to initialize Redis limiter storage, falling back to memory: %s", exc)
        return Limiter(
            key_func=get_client_ip,
            storage_uri="memory://",
            strategy="moving-window",
        )


limiter = create_limiter()
