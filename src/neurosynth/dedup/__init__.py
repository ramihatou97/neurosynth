"""Semantic deduplication engine."""

from typing import TYPE_CHECKING

from neurosynth.dedup.clustering import SemanticClusterer, VisualAssociator
from neurosynth.dedup.embeddings import EmbeddingGenerator
from neurosynth.dedup.merger import ClusterMerger
from neurosynth.dedup.qdrant_store import QdrantVisualStore, get_qdrant_store

# FAISS-based clustering (optional, recommended for large datasets)
if TYPE_CHECKING:
    from neurosynth.dedup.faiss_clustering import (
        FAISSClusterer,
        FAISSClusteringResult,
        get_clusterer,
    )

try:
    from neurosynth.dedup.faiss_clustering import (
        FAISSClusterer,
        FAISSClusteringResult,
        get_clusterer,
    )

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    FAISSClusterer = None  # type: ignore
    FAISSClusteringResult = None  # type: ignore
    get_clusterer = None  # type: ignore

__all__ = [
    "EmbeddingGenerator",
    "SemanticClusterer",
    "VisualAssociator",
    "ClusterMerger",
    "QdrantVisualStore",
    "get_qdrant_store",
    # FAISS (optional)
    "FAISSClusterer",
    "FAISSClusteringResult",
    "get_clusterer",
    "FAISS_AVAILABLE",
]
