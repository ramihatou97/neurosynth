"""
Configuration for Neurosurgical Chapter Synthesis Engine
"""

import logging
from pathlib import Path
from typing import Optional

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings - loaded from environment or config file"""

    # Paths
    library_path: Path = Field(
        default=Path("data/library"), description="Path to your PDF library"
    )
    processed_path: Path = Field(
        default=Path("data/processed"), description="Path for extracted content"
    )
    output_path: Path = Field(
        default=Path("data/output"), description="Path for generated chapters"
    )
    database_path: Path = Field(
        default=Path("data/index.db"), description="SQLite database path"
    )
    qdrant_path: Path | None = Field(
        default=Path("data/qdrant"), description="Path to local Qdrant storage"
    )

    # Qdrant Vector Store
    enable_qdrant_push: bool = Field(
        default=True, description="Push chunks to Qdrant after indexing"
    )
    qdrant_url: str = Field(
        default="http://localhost:6333", description="Qdrant server URL"
    )
    qdrant_collection_name: str = Field(
        default="neurosynth_chunks", description="Qdrant collection name"
    )
    qdrant_vector_dim: int = Field(
        default=1024, description="Vector dimension (1024 for voyage-3)"
    )

    # Batch Processing
    max_concurrent_pdfs: int = Field(
        default=3,
        description="Maximum PDFs to process concurrently during batch indexing",
    )
    embedding_batch_size: int = Field(
        default=128, description="Number of texts to embed in one VoyageAI API call"
    )

    # Image Pipeline
    image_qdrant_collection: str = Field(
        default="neurosurgical_figures_hybrid",
        description="Qdrant collection for image embeddings",
    )
    image_qdrant_vector_dim: int = Field(
        default=512,
        description="Vector dimension for image embeddings (512 for BiomedCLIP)",
    )
    image_embedding_batch_size: int = Field(
        default=32,
        description="Number of images to embed in one batch (GPU memory limited)",
    )
    enable_image_qdrant_push: bool = Field(
        default=True, description="Push images to Qdrant after indexing"
    )

    # Feature Flags
    enable_proposition_chunker: bool = Field(
        default=True, description="Enable Small-to-Big proposition chunking"
    )
    enable_raptor: bool = Field(
        default=True, description="Enable RAPTOR recursive summarization"
    )
    enable_graph_rag: bool = Field(default=True, description="Enable GraphRAG")
    enable_object_detection: bool = Field(
        default=False, description="Enable YOLO object detection"
    )
    enable_layout_analysis: bool = Field(
        default=False, description="Enable LayoutLM document analysis"
    )
    enable_vlm_verification: bool = Field(
        default=False, description="Enable VLM image verification"
    )

    # API Keys
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key for Claude"
    )
    voyage_api_key: str | None = Field(
        default=None, description="Voyage AI API key for embeddings"
    )

    # Processing settings
    chunk_size: int = Field(default=1500, description="Target chunk size in characters")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")
    embedding_model: str = Field(
        default="voyage-3-lite", description="Voyage embedding model for text"
    )
    image_embedding_model: str = Field(
        default="biomed-clip",
        description="Image embedding model (colpali-v1.2, clip-vit-large-patch14, none, biomed-clip)",
    )
    synthesis_model: str = Field(
        default="claude-sonnet-4-20250514", description="Claude model for synthesis"
    )

    # Retrieval settings
    retrieval_top_k: int = Field(
        default=50, description="Number of chunks to retrieve per query"
    )
    similarity_threshold: float = Field(
        default=0.7, description="Minimum similarity for retrieval"
    )
    dedup_threshold: float = Field(
        default=0.85, description="Similarity threshold for deduplication"
    )

    # Output settings
    max_images_per_section: int = Field(
        default=5, description="Maximum images per section"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()


def ensure_directories():
    """Create necessary directories if they don't exist"""
    settings.library_path.mkdir(parents=True, exist_ok=True)
    settings.processed_path.mkdir(parents=True, exist_ok=True)
    settings.output_path.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)


def configure_logging():
    """Configure structured logging for observability."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),  # Human-readable in dev
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
