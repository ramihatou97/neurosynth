"""Configuration management for NeuroSynth."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import enhancement modules with graceful fallback
try:
    from neurosynth.enhancements.config import (
        NeuroSynthEnhancedConfig,
        KeywordWeightConfig,
        AssociationWeightConfig,
        CaptionConfidenceConfig,
        NeurosurgicalKeywords,
    )
    ENHANCEMENTS_AVAILABLE = True
except ImportError:
    # Graceful degradation if enhancements not installed
    NeuroSynthEnhancedConfig = None  # type: ignore
    ENHANCEMENTS_AVAILABLE = False

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

    # Enhancement Module Configuration (v3.1)
    enable_enhancements: bool = Field(
        default=True,
        description="Enable enhancement module v3.1 features",
    )
    enable_enhanced_filtering: bool = Field(
        default=True,
        description="Enable 3-tier resilient image filtering (Enhanced → Basic → Permissive)",
    )
    enable_enhanced_captions: bool = Field(
        default=True,
        description="Enable multi-directional caption detection with confidence scoring",
    )
    enable_keyword_scoring: bool = Field(
        default=True,
        description="Enable neurosurgical keyword-based association scoring (340+ terms)",
    )
    enable_procedural_detection: bool = Field(
        default=True,
        description="Enable surgical procedure sequence detection (Step 1→2→3)",
    )

    # Enhancement Thresholds
    caption_confidence_threshold: float = Field(
        default=0.60,
        description="Minimum confidence for caption detection (0-1)",
    )
    visual_association_threshold: float = Field(
        default=0.50,
        description="Minimum score for image-text association (0-1)",
    )
    keyword_match_threshold: int = Field(
        default=2,
        description="Minimum keyword matches for relevance",
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
        default=600.0,  # 10 minutes - synthesis prompts can be very large
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
    embedding_cache_max_size_mb: int = Field(
        default=500,
        description="Maximum cache size in MB. Oldest entries evicted when exceeded. Set to 0 for unlimited.",
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

    @property
    def enhancement_config(self) -> Optional["NeuroSynthEnhancedConfig"]:  # type: ignore
        """
        Get enhancement module configuration.

        Returns None if enhancements disabled or unavailable.
        Auto-creates config with default weights on first access.
        Validates all weights on creation.
        """
        if not self.enable_enhancements or not ENHANCEMENTS_AVAILABLE:
            return None

        if not hasattr(self, '_enhancement_config_cache'):
            # Create enhancement config with defaults
            self._enhancement_config_cache = NeuroSynthEnhancedConfig(  # type: ignore
                # Paths
                output_base_dir=str(self.data_dir / "neurosynth_output"),
                images_subdir="images",
                metadata_subdir="metadata",
                latex_subdir="latex",

                # Feature flags (inherit from main config)
                enable_enhanced_filtering=self.enable_enhanced_filtering,
                enable_caption_detection=self.enable_enhanced_captions,
                enable_procedural_detection=self.enable_procedural_detection,
            )

            # Validate weights on creation
            self._enhancement_config_cache.keyword_weights.validate()  # type: ignore
            self._enhancement_config_cache.association_weights.validate()  # type: ignore
            self._enhancement_config_cache.caption_confidence.validate()  # type: ignore

        return self._enhancement_config_cache

    @property
    def enhancements_enabled(self) -> bool:
        """Check if enhancements are available and enabled."""
        return self.enable_enhancements and ENHANCEMENTS_AVAILABLE

    def print_enhancement_status(self) -> None:
        """Print current enhancement configuration status."""
        print("="*70)
        print("ENHANCEMENT MODULE STATUS")
        print("="*70)

        if not ENHANCEMENTS_AVAILABLE:
            print("❌ Enhancement module NOT AVAILABLE")
            print("   Files should be in: src/neurosynth/enhancements/")
            return

        if not self.enable_enhancements:
            print("⚠  Enhancement module DISABLED (enable_enhancements=False)")
            return

        print("✓ Enhancement module ACTIVE\n")

        print("Feature Flags:")
        print(f"  Resilient Filtering:     {'✓' if self.enable_enhanced_filtering else '✗'}")
        print(f"  Enhanced Captions:       {'✓' if self.enable_enhanced_captions else '✗'}")
        print(f"  Keyword Scoring:         {'✓' if self.enable_keyword_scoring else '✗'}")
        print(f"  Procedural Detection:    {'✓' if self.enable_procedural_detection else '✗'}")

        print("\nThresholds:")
        print(f"  Caption Confidence:      {self.caption_confidence_threshold:.2f}")
        print(f"  Visual Association:      {self.visual_association_threshold:.2f}")
        print(f"  Keyword Matches:         {self.keyword_match_threshold}")

        if self.enhancement_config:
            print("\n" + "="*70)
            self.enhancement_config.print_weights_summary()  # type: ignore

        print("="*70)


# Global settings instance (lazy loaded)
_settings: Settings | None = None

# Track the project config path for YAML overrides
_project_config_path: Path | None = None


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


def load_project_config(project_dir: Path) -> dict:
    """Load project-specific configuration from neurosynth.yaml.

    This merges YAML config values with environment-based settings.
    YAML values override environment defaults for runtime.

    Args:
        project_dir: Project directory containing neurosynth.yaml

    Returns:
        Dictionary of configuration values loaded from YAML
    """
    global _settings, _project_config_path
    import yaml

    config_path = project_dir / "neurosynth.yaml"
    if not config_path.exists():
        return {}

    _project_config_path = config_path

    try:
        config = yaml.safe_load(config_path.read_text())
        if not config:
            return {}

        # Get current settings and override with YAML values
        settings = get_settings()

        # Processing settings from YAML
        if "chunk_size" in config:
            settings.chunk_size = int(config["chunk_size"])
        if "chunk_overlap" in config:
            settings.chunk_overlap = int(config["chunk_overlap"])
        if "similarity_threshold" in config:
            settings.similarity_threshold = float(config["similarity_threshold"])

        # Output settings from YAML
        if "output_format" in config:
            if config["output_format"] in ("latex", "markdown"):
                settings.output_format = config["output_format"]

        # Visual extraction settings from YAML
        if "enable_visual_extraction" in config:
            settings.enable_visual_extraction = bool(config["enable_visual_extraction"])
        if "min_image_size" in config:
            settings.min_image_size = int(config["min_image_size"])
        if "max_image_size" in config:
            settings.max_image_size = int(config["max_image_size"])

        # Verification settings from YAML
        if "enable_verification" in config:
            settings.enable_verification = bool(config["enable_verification"])

        # Concurrency settings from YAML
        if "merge_concurrency" in config:
            settings.merge_concurrency = int(config["merge_concurrency"])
        if "synthesis_concurrency" in config:
            settings.synthesis_concurrency = int(config["synthesis_concurrency"])

        return config

    except Exception as e:
        from rich.console import Console
        Console().print(f"[yellow]Warning: Error reading neurosynth.yaml: {e}[/yellow]")
        return {}


def get_project_config_path() -> Path | None:
    """Get the path to the currently loaded project config."""
    return _project_config_path
