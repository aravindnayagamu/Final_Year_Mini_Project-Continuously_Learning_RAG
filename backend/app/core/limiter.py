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
    storage_uri = settings.redis_url if settings.redis_url else "memory://"
    try:
        lim = Limiter(
            key_func=get_client_ip,
            storage_uri=storage_uri,
            strategy="moving-window",
        )
        # Eagerly verify the Redis connection so failures are loud at startup
        if settings.redis_url:
            try:
                from limits.storage import storage as _storage_factory  # type: ignore
                store = _storage_factory(storage_uri)
                store.check()
                logger.info(
                    "Redis rate-limit storage connected OK | host=%s",
                    storage_uri.split("@")[-1],
                )
            except Exception as conn_exc:
                logger.warning(
                    "Redis connectivity check failed – limits may fall back to memory: %s",
                    conn_exc,
                )
        return lim
    except Exception as exc:
        logger.warning(
            "Failed to initialize Redis limiter, falling back to memory: %s", exc
        )
        return Limiter(
            key_func=get_client_ip,
            storage_uri="memory://",
            strategy="moving-window",
        )


limiter = create_limiter()

# ---------------------------------------------------------------------------
# Pre-resolved rate-limit string constants.
#
# IMPORTANT: slowapi's @limiter.limit() decorator does NOT accept a callable
# or lambda – it only works with a plain string evaluated at decoration time.
# Using `lambda: get_settings().query_rate_limit` silently does nothing and
# the limit is never enforced.  Always use these constants in decorators.
# ---------------------------------------------------------------------------
QUERY_RATE_LIMIT: str = settings.query_rate_limit    # e.g. "5/minute"
INGEST_RATE_LIMIT: str = settings.ingest_rate_limit  # e.g. "2/minute"

logger.info(
    "Rate limits loaded | query=%s ingest=%s backend=%s",
    QUERY_RATE_LIMIT,
    INGEST_RATE_LIMIT,
    "redis" if settings.redis_url else "in-memory",
)
