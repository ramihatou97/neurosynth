"""NeuroSynth API - FastAPI Application.

Main entry point for the API service.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.client import AsyncAIClient
from neurosynth.api.deps import close_redis_pool, get_settings
from neurosynth.api.routes import health_router, jobs_router

logger = logging.getLogger(__name__)

# Global AI client instance
ai_client: Optional[AsyncAIClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - manage AI client and Redis pool."""
    global ai_client

    # Startup: Initialize persistent AI client
    settings = get_settings()
    logger.info("initializing_ai_client")
    ai_client = AsyncAIClient(
        voyage_api_key=settings.voyage_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        timeout=60.0,
    )
    logger.info("ai_client_initialized")

    yield  # Application runs

    # Shutdown: Close connections
    logger.info("shutting_down_ai_client")
    if ai_client:
        await ai_client.close()

    await close_redis_pool()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="NeuroSynth API",
        description="Neurosurgical Knowledge Synthesis System - Job Management API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(jobs_router)

    return app


# Create app instance
app = create_app()


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "NeuroSynth API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
