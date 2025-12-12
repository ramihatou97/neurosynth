"""
Precision Search Engine - Backward Compatibility Layer
=======================================================
This module provides backward-compatible aliases for code migrating from the
legacy PrecisionSearchEngine to the new UnifiedSearchEngine.

DEPRECATED: Import from src.index.unified_search instead.
"""

import logging
import re
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

from src.models import Chunk, ExtractedImage, SearchResult

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Query Classification (Ported from legacy)
# ═══════════════════════════════════════════════════════════════════════════


class QueryType(Enum):
    """Classification of query intent for routing"""

    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    SPATIAL = "spatial"
    CONTRAINDICATION = "contraindication"
    COMPARATIVE = "comparative"
    CONCEPTUAL = "conceptual"
    SAFETY = "safety"


class ConfidenceLevel(Enum):
    """Confidence level thresholds"""

    HIGH = "high"  # >= 0.85
    MEDIUM = "medium"  # 0.70 - 0.84
    LOW = "low"  # 0.50 - 0.69
    INSUFFICIENT = "insufficient"  # < 0.50


# Query classification patterns
SPATIAL_TERMS = [
    "anterior",
    "posterior",
    "medial",
    "lateral",
    "superior",
    "inferior",
    "above",
    "below",
    "deep to",
    "superficial to",
    "adjacent to",
    "relative to",
    "position of",
    "location of",
    "lies",
    "courses",
]

NEGATION_TERMS = [
    "not",
    "never",
    "avoid",
    "contraindication",
    "contraindicated",
    "should not",
    "do not",
    "don't",
    "cannot",
    "shouldn't",
    "risk",
    "complication",
    "warning",
    "caution",
    "danger",
]

PROCEDURAL_TERMS = [
    "how to",
    "steps",
    "technique",
    "procedure",
    "approach",
    "perform",
    "execute",
    "method",
    "protocol",
    "sequence",
]

CONCEPTUAL_TERMS = [
    "why",
    "rationale",
    "principle",
    "philosophy",
    "concept",
    "compare",
    "versus",
    "vs",
    "difference between",
    "advantages",
]

# ═══════════════════════════════════════════════════════════════════════════
# Result Dataclasses (Ported from legacy)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PrecisionResult:
    """Enhanced search result with precision metrics"""

    chunk: Chunk
    dense_score: float
    colbert_score: float | None = None
    final_score: float = 0.0
    has_safety_content: bool = False
    authority_score: int = 80
    authority_boost_applied: float = 0.0
    exam_frequency: int = 0
    exam_boost_applied: float = 0.0

    @property
    def citation(self) -> str:
        return f"{self.chunk.source_title}, p.{self.chunk.page_start}"


@dataclass
class PrecisionRetrievalResult:
    """Complete precision retrieval result"""

    query: str
    query_type: QueryType
    results: list[PrecisionResult]
    images: list[ExtractedImage]
    confidence: float
    confidence_level: ConfidenceLevel
    retrieval_time_ms: float
    systems_used: list[str]
    warnings: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# PrecisionSearchEngine Compatibility Wrapper
# ═══════════════════════════════════════════════════════════════════════════


class PrecisionSearchEngine:
    """
    Backward-compatible wrapper around UnifiedSearchEngine.

    DEPRECATED: Use UnifiedSearchEngine directly for new code.
    """

    def __init__(self, db: Any, colbert_enabled: bool = True):
        warnings.warn(
            "PrecisionSearchEngine is deprecated. Use UnifiedSearchEngine instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from src.index.unified_search import SearchMode, UnifiedSearchEngine

        self.db = db
        self._engine = UnifiedSearchEngine(db)
        self.colbert_enabled = colbert_enabled

        # Set mode based on colbert setting
        if colbert_enabled and self._engine.colbert:
            self._engine.mode = SearchMode.DEEP
        else:
            self._engine.mode = SearchMode.BALANCED

        # Expose sub-components for legacy access
        self.qdrant = self._engine.qdrant
        self.bm25 = self._engine.bm25
        self.colbert = self._engine.colbert
        self.vision_embedder = self._engine.vision

        # Compile patterns for query classification
        self._spatial_pattern = self._compile_pattern(SPATIAL_TERMS)
        self._negation_pattern = self._compile_pattern(NEGATION_TERMS)
        self._procedural_pattern = self._compile_pattern(PROCEDURAL_TERMS)
        self._conceptual_pattern = self._compile_pattern(CONCEPTUAL_TERMS)

        # Safety patterns
        self._safety_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in [
                r"\bcontraindication\b",
                r"\bwarning\b",
                r"\bcaution\b",
                r"\brisk\b",
                r"\bcomplication\b",
                r"\bavoid\b",
                r"\bnever\b",
                r"\bdo not\b",
                r"\bfatal\b",
                r"\bdangerous\b",
            ]
        ]

    def _compile_pattern(self, terms: list[str]) -> re.Pattern:
        escaped = [re.escape(t) for t in terms]
        return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)

    def classify_query(self, query: str) -> QueryType:
        """Classify query intent based on keywords and patterns"""
        query_lower = query.lower()
        if any(term in query_lower for term in NEGATION_TERMS):
            return QueryType.CONTRAINDICATION
        if any(term in query_lower for term in SPATIAL_TERMS):
            return QueryType.SPATIAL
        if any(term in query_lower for term in PROCEDURAL_TERMS):
            return QueryType.PROCEDURAL
        if " vs " in query_lower or "versus" in query_lower or "compare" in query_lower:
            return QueryType.COMPARATIVE
        return QueryType.FACTUAL

    def _has_safety_content(self, text: str) -> bool:
        return any(p.search(text) for p in self._safety_patterns)

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        if score >= 0.85:
            return ConfidenceLevel.HIGH
        elif score >= 0.70:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.50:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.INSUFFICIENT

    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 20,
        include_images: bool = True,
        filter_subspecialty: str | None = None,
    ) -> PrecisionRetrievalResult:
        """Execute precision search with ColBERT reranking."""
        import time

        from src.index.unified_search import SearchMode

        start_time = time.time()
        query_type = self.classify_query(query)
        systems_used = []
        all_warnings = []

        # Use UnifiedSearchEngine for retrieval
        mode = SearchMode.DEEP if self.colbert_enabled else SearchMode.BALANCED
        result = self._engine.search(
            query=query, query_embedding=query_embedding, mode=mode, top_k=top_k
        )

        # Track systems used
        if self._engine.qdrant:
            systems_used.append("dense_qdrant")
        if self._engine.bm25 and mode != SearchMode.FAST:
            systems_used.append("bm25")
        if self._engine.colbert and mode == SearchMode.DEEP:
            systems_used.append("colbert")

        all_warnings.extend(result.warnings)

        # Convert SearchResult -> PrecisionResult
        precision_results = []
        for sr in result.chunks:
            precision_results.append(
                PrecisionResult(
                    chunk=sr.chunk,
                    dense_score=sr.score,
                    colbert_score=sr.score if mode == SearchMode.DEEP else None,
                    final_score=sr.score,
                    has_safety_content=self._has_safety_content(sr.chunk.content),
                )
            )

        # Get images if requested
        images = []
        if include_images and self.vision_embedder:
            try:
                images = self._search_images_ai(query, top_k=5)
                systems_used.append("ai_vision_search")
            except Exception as e:
                all_warnings.append(f"Image search failed: {e}")

        elapsed_ms = (time.time() - start_time) * 1000
        confidence = result.confidence

        return PrecisionRetrievalResult(
            query=query,
            query_type=query_type,
            results=precision_results,
            images=images,
            confidence=confidence,
            confidence_level=self._score_to_level(confidence),
            retrieval_time_ms=elapsed_ms,
            systems_used=systems_used,
            warnings=all_warnings,
        )

    def _search_images_ai(self, query: str, top_k: int = 5) -> list[ExtractedImage]:
        """Search for images using BiomedCLIP and Qdrant"""
        from pathlib import Path

        if not self.vision_embedder or not self.qdrant or not self.qdrant.client:
            raise RuntimeError("AI Vision components not initialized")

        vector = self.vision_embedder.embed_text(query)
        if vector.size == 0:
            return []

        # Use query_points with 'using' param for named vectors (qdrant-client v1.x)
        query_response = self.qdrant.client.query_points(
            collection_name="neurosurgical_figures_hybrid",
            query=vector[0].tolist(),
            using="biomed",  # Named vector
            limit=top_k,
            with_payload=True,
        )
        results = query_response.points

        images = []
        for hit in results:
            payload = hit.payload
            images.append(
                ExtractedImage(
                    id=payload.get("filename", str(hit.id)),
                    source_id=payload.get("source_pdf", "unknown"),
                    page=payload.get("page_num", 0),
                    file_path=Path(payload.get("path", "")),
                    caption=payload.get("caption", ""),
                    surrounding_text=payload.get("context", ""),
                    image_type=payload.get("modality", "unknown"),
                    width=0,
                    height=0,
                    modality=payload.get("modality", "unknown"),
                    detected_regions=payload.get("detected_regions", []),
                    region_confidence=payload.get("region_confidence", 0.0),
                    ocr_caption=payload.get("ocr_caption", ""),
                    caption_source=payload.get("caption_source", "proximity"),
                )
            )
        return images

    def retrieve_for_topic(
        self,
        query_embedding: list[float],
        topic: str,
        chunk_types: list[Any] | None = None,
        top_k: int | None = None,
        include_images: bool = True,
    ) -> Any:
        """Adapter method for SynthesisEngine compatibility."""
        from src.index.search import RetrievalResult

        top_k = top_k or 20
        precision_result = self.search(
            query=topic,
            query_embedding=query_embedding,
            top_k=top_k,
            include_images=include_images,
        )

        search_results = [
            SearchResult(chunk=pr.chunk, score=pr.final_score)
            for pr in precision_result.results
        ]

        return RetrievalResult(
            chunks=search_results,
            images=precision_result.images,
            sources_used=set(r.chunk.source_id for r in precision_result.results),
            total_chunks=len(search_results),
            total_images=len(precision_result.images),
        )

    def quick_search(
        self, query: str, query_embedding: list[float], top_k: int = 10
    ) -> list[SearchResult]:
        """Quick search without ColBERT (for speed-critical paths)."""
        from src.index.unified_search import SearchMode

        result = self._engine.search(
            query=query,
            query_embedding=query_embedding,
            mode=SearchMode.FAST,
            top_k=top_k,
        )
        return result.chunks

    def update_bm25_index(self, chunks: list, auto_save: bool = True) -> int:
        """Update the BM25 index with newly ingested chunks."""
        if not self.bm25:
            logger.warning("BM25 index not initialized, cannot update")
            return 0
        chunk_dicts = [
            {"content": c.content, "id": c.id, "chunk_obj": c} for c in chunks
        ]
        added = self.bm25.add_documents(chunk_dicts)
        if auto_save and added > 0:
            self.bm25.save()
        return added

    def get_bm25_count(self) -> int:
        """Return the number of documents in the BM25 index."""
        return self.bm25.get_document_count() if self.bm25 else 0


# ═══════════════════════════════════════════════════════════════════════════
# Verification Function (Legacy)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class VerificationResult:
    """Result of synthesis verification"""

    claims_extracted: int
    claims_supported: int
    claims_contradicted: int
    claims_not_found: int
    verification_score: float
    contradictions: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.claims_contradicted == 0 and self.verification_score >= 0.7


def verify_synthesis(
    synthesis_text: str, source_chunks: list[Chunk], llm_client: Any
) -> VerificationResult:
    """Verify synthesized text against source chunks (placeholder)."""
    return VerificationResult(
        claims_extracted=0,
        claims_supported=0,
        claims_contradicted=0,
        claims_not_found=0,
        verification_score=1.0,
    )
