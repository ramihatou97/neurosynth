"""Configuration management for NeuroSynth."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env relative to this file, not CWD
# This allows NeuroSynth to work from any working directory
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
_user_env_file = Path.home() / ".neurosynth" / "config.env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=[_env_file, _user_env_file] if _env_file.exists() else [_user_env_file, ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")
    google_api_key: str = Field(..., description="Google API key for Gemini")
    voyage_api_key: str = Field(..., description="Voyage AI API key for embeddings")

    # Model Configuration
    gemini_model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model for extraction",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model for synthesis",
    )
    voyage_model: str = Field(
        default="voyage-large-2-instruct",
        description="Voyage model for embeddings",
    )

    # Processing Configuration
    chunk_size: int = Field(default=1000, description="Target chunk size in words")
    chunk_overlap: int = Field(default=100, description="Overlap between chunks in words")
    similarity_threshold: float = Field(
        default=0.92,
        description="Cosine similarity threshold for deduplication",
    )

    # Visual Processing Configuration
    enable_visual_extraction: bool = Field(
        default=True,
        description="Enable image extraction from PDFs",
    )
    min_image_size: int = Field(
        default=100,
        description="Minimum image dimension in pixels to extract",
    )
    max_image_size: int = Field(
        default=4096,
        description="Maximum image dimension (larger images will be resized)",
    )
    colpali_model: str = Field(
        default="vidore/colpali-v1.2",
        description="ColPali model identifier from HuggingFace",
    )
    colpali_batch_size: int = Field(
        default=4,
        description="Batch size for ColPali embedding generation",
    )
    include_all_relevant_visuals: bool = Field(
        default=True,
        description="Comprehensive visual coverage (include all relevant images)",
    )

    # Qdrant Configuration
    qdrant_path: Path = Field(
        default=Path.home() / ".neurosynth" / "qdrant",
        description="Path for embedded Qdrant database storage",
    )
    qdrant_collection_name: str = Field(
        default="neurosynth_visuals",
        description="Qdrant collection name for visual embeddings",
    )

    # Output Configuration
    output_format: Literal["latex", "markdown"] = Field(
        default="latex",
        description="Output format for generated chapters",
    )

    # LLM Configuration
    llm_timeout: float = Field(
        default=60.0,
        description="Timeout in seconds for LLM API calls",
    )
    llm_max_retries: int = Field(
        default=5,
        description="Maximum number of retries for LLM API calls",
    )

    # Concurrency Configuration (for parallel API calls)
    merge_concurrency: int = Field(
        default=15,
        description="Max concurrent Claude API calls for cluster merging",
    )
    synthesis_concurrency: int = Field(
        default=12,
        description="Max concurrent Claude API calls for section synthesis",
    )
    embedding_concurrency: int = Field(
        default=5,
        description="Max concurrent Voyage API batches for embedding",
    )
    voyage_batch_size: int = Field(
        default=32,
        description="Batch size for Voyage API calls",
    )

    # Embedding Cache Configuration
    embedding_cache_enabled: bool = Field(
        default=True,
        description="Enable persistent embedding cache",
    )
    embedding_cache_path: Path = Field(
        default=Path.home() / ".neurosynth" / "embedding_cache",
        description="Path for persistent embedding cache",
    )

    # Verification Configuration
    enable_verification: bool = Field(
        default=True,
        description="Enable post-synthesis verification with Gemini",
    )

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Base data directory")

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
