"""Deep-Dx Configuration - Extends NeuroSynth settings"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from neurosynth.config import get_settings as get_neurosynth_settings


class DeepDxSettings(BaseSettings):
    """Deep-Dx specific settings."""

    # ColBERT Configuration
    colbert_checkpoint: str = Field(
        default="colbert-ir/colbertv2.0",
        description="ColBERT model checkpoint from HuggingFace",
    )
    colbert_index_name: str = Field(
        default="deep_dx_v1",
        description="Name for ColBERT/Dense index",
    )
    colbert_doc_maxlen: int = Field(
        default=300,
        description="Maximum document length in tokens for ColBERT",
    )
    colbert_query_maxlen: int = Field(
        default=64,
        description="Maximum query length in tokens",
    )
    colbert_nbits: int = Field(
        default=2,
        description="Compression bits for ColBERT index (1, 2, or 4)",
    )

    # RAPTOR Configuration
    raptor_enabled: bool = Field(
        default=False,
        description="Enable RAPTOR hierarchical indexing (Phase 3)",
    )
    raptor_levels: int = Field(
        default=3,
        description="Number of hierarchy levels for RAPTOR",
    )
    raptor_reduction_factor: int = Field(
        default=5,
        description="Summarization reduction factor (N chunks → 1 summary)",
    )

    # Knowledge Graph Configuration
    knowledge_graph_enabled: bool = Field(
        default=False,
        description="Enable knowledge graph (Phase 4)",
    )
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="",
        description="Neo4j password",
    )

    # Retrieval Configuration
    retrieval_top_k: int = Field(
        default=50,
        description="Number of chunks to retrieve",
    )
    hybrid_search_enabled: bool = Field(
        default=True,
        description="Enable BM25 sparse retrieval alongside dense",
    )
    synthesis_max_chunks: int = Field(
        default=5,
        description="Maximum chunks to include in synthesis",
    )

    # Critic Configuration
    critic_enabled: bool = Field(
        default=True,
        description="Enable critic verification (Phase 2)",
    )
    confidence_threshold_high: float = Field(
        default=0.85,
        description="High confidence threshold (output directly)",
    )
    confidence_threshold_medium: float = Field(
        default=0.70,
        description="Medium confidence threshold (flag as medium confidence)",
    )
    confidence_threshold_low: float = Field(
        default=0.50,
        description="Low confidence threshold (warn user)",
    )

    # Performance Configuration
    use_gpu: bool = Field(
        default=True,
        description="Use GPU for ColBERT if available",
    )
    cache_retrieval_results: bool = Field(
        default=True,
        description="Cache retrieval results in Redis",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds (1 hour default)",
    )

    # Paths (relative to NeuroSynth data directory)
    @property
    def colbert_index_path(self) -> Path:
        """Path to ColBERT index directory."""
        ns_settings = get_neurosynth_settings()
        return ns_settings.data_dir / "colbert_index"

    @property
    def eval_dataset_path(self) -> Path:
        """Path to evaluation dataset."""
        return Path(__file__).parent / "eval" / "gold_standard_eval.json"

    @property
    def knowledge_graph_path(self) -> Path:
        """Path to knowledge graph data."""
        ns_settings = get_neurosynth_settings()
        return ns_settings.data_dir / "knowledge_graph"


# Global Deep-Dx settings instance
_deepdx_settings: DeepDxSettings | None = None


def get_deepdx_settings() -> DeepDxSettings:
    """Get the global Deep-Dx settings instance."""
    global _deepdx_settings
    if _deepdx_settings is None:
        _deepdx_settings = DeepDxSettings()
    return _deepdx_settings


def reload_deepdx_settings() -> DeepDxSettings:
    """Force reload Deep-Dx settings."""
    global _deepdx_settings
    _deepdx_settings = DeepDxSettings()
    return _deepdx_settings
