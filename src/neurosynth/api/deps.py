"""API dependencies - Redis connection, settings, etc."""

from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as redis
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API configuration settings."""

    redis_url: str = "redis://localhost:6379"
    jobs_data_dir: str = "/data/jobs"
    log_level: str = "info"
    cors_origins: list[str] = ["*"]

    class Config:
        env_prefix = ""
        case_sensitive = False


@lru_cache
def get_settings() -> APISettings:
    """Get cached API settings."""
    return APISettings()


# Redis connection pool
_redis_pool: redis.ConnectionPool | None = None


async def get_redis_pool() -> redis.ConnectionPool:
    """Get or create Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            decode_responses=True,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Dependency that yields a Redis connection."""
    pool = await get_redis_pool()
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis_pool() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
