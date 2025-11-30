"""NeuroSynth API - FastAPI Application.

Main entry point for the API service.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from neurosynth.api.deps import close_redis_pool, get_settings
from neurosynth.api.routes import health_router, jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    await close_redis_pool()


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
