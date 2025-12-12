"""
Index module - Database, chunking, and vector search
"""

from .chunker import SemanticChunker
from .database import Database
from .graph import KnowledgeGraphBuilder
from .late_fusion import LateFusionRanker

# Backward Compatibility: Legacy PrecisionSearchEngine API
from .precision_search import (
    ConfidenceLevel,
    PrecisionResult,
    PrecisionRetrievalResult,
    PrecisionSearchEngine,
    QueryType,
    VerificationResult,
    verify_synthesis,
)
from .proposition_chunker import PropositionChunker

# Phase 6: Advanced RAG
from .raptor import RecursiveSummarizer
from .unified_search import RetrievalResult, SearchMode, UnifiedSearchEngine

# Legacy alias for SearchEngine (use UnifiedSearchEngine)
SearchEngine = UnifiedSearchEngine

__all__ = [
    # New API
    "Database",
    "SemanticChunker",
    "UnifiedSearchEngine",
    "SearchMode",
    "RetrievalResult",
    "PropositionChunker",
    "LateFusionRanker",
    "RecursiveSummarizer",
    "KnowledgeGraphBuilder",
    # Legacy API (Backward Compatibility)
    "SearchEngine",
    "PrecisionSearchEngine",
    "PrecisionRetrievalResult",
    "PrecisionResult",
    "QueryType",
    "ConfidenceLevel",
    "verify_synthesis",
    "VerificationResult",
]
