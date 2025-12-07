"""
Index module - Database, chunking, and vector search
"""

from .database import Database
from .chunker import SemanticChunker
from .search import SearchEngine
from .precision_search import (
    PrecisionSearchEngine,
    PrecisionRetrievalResult,
    PrecisionResult,
    QueryType,
    ConfidenceLevel,
    ColBERTClient,
    verify_synthesis
)

__all__ = [
    "Database", 
    "SemanticChunker", 
    "SearchEngine",
    "PrecisionSearchEngine",
    "PrecisionRetrievalResult",
    "PrecisionResult",
    "QueryType",
    "ConfidenceLevel",
    "ColBERTClient",
    "verify_synthesis"
]
