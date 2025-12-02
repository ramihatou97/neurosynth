"""Health check endpoints."""

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from neurosynth.api.deps import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class ReadyResponse(BaseModel):
    """Readiness check response."""

    status: str
    redis: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe - checks if the API is up."""
    from neurosynth import __version__

    return HealthResponse(status="healthy", version=__version__)


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check(
    redis_client: redis.Redis = Depends(get_redis),
) -> ReadyResponse:
    """Readiness probe - checks if dependencies are ready."""
    from neurosynth import __version__

    # Check Redis connectivity
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    status = "ready" if redis_status == "connected" else "not_ready"

    return ReadyResponse(
        status=status,
        redis=redis_status,
        version=__version__,
    )
