"""
Configuration for Neurosurgical Chapter Synthesis Engine
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings - loaded from environment or config file"""
    
    # Paths
    library_path: Path = Field(
        default=Path("data/library"),
        description="Path to your PDF library"
    )
    processed_path: Path = Field(
        default=Path("data/processed"),
        description="Path for extracted content"
    )
    output_path: Path = Field(
        default=Path("data/output"),
        description="Path for generated chapters"
    )
    database_path: Path = Field(
        default=Path("data/index.db"),
        description="SQLite database path"
    )
    
    # API Keys
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude"
    )
    voyage_api_key: Optional[str] = Field(
        default=None,
        description="Voyage AI API key for embeddings"
    )
    
    # Processing settings
    chunk_size: int = Field(
        default=1500,
        description="Target chunk size in characters"
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap between chunks"
    )
    embedding_model: str = Field(
        default="voyage-3-lite",
        description="Voyage embedding model"
    )
    synthesis_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model for synthesis"
    )
    
    # Retrieval settings
    retrieval_top_k: int = Field(
        default=50,
        description="Number of chunks to retrieve per query"
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum similarity for retrieval"
    )
    dedup_threshold: float = Field(
        default=0.85,
        description="Similarity threshold for deduplication"
    )
    
    # Output settings
    max_images_per_section: int = Field(
        default=5,
        description="Maximum images per section"
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
