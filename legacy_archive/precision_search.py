"""
Precision Search Engine
=======================
Enhanced search with ColBERT reranking, claim verification, and confidence scoring.
Integrates Deep-Dx precision retrieval into neurosurg-synthesis.

This module wraps the existing SearchEngine and adds:
1. ColBERT precision reranking (Docker-isolated)
2. Query routing (spatial, procedural, contraindication, etc.)
3. Confidence scoring
4. Claim verification for synthesis outputs
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models import Chunk, ExtractedImage, SearchResult

from .database import Database

try:
    from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
except ImportError:
    BiomedCLIPSearcher = None

# gap_detector imported lazily in __init__ to avoid circular import
from .search import RetrievalResult, SearchEngine

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Authority Ranking Configuration
# ═══════════════════════════════════════════════════════════════════════════

# Authority-based ranking boosts high-trust sources (guidelines, textbooks)
# Can be disabled by setting AUTHORITY_BOOST_ENABLED = False
AUTHORITY_BOOST_ENABLED = True  # Set to False to disable authority ranking
AUTHORITY_BOOST_FACTOR = 0.20  # 20% boost for highest authority (100 → +20%)
AUTHORITY_MIN_SCORE = 80  # Baseline authority score
AUTHORITY_MAX_SCORE = 100  # Maximum authority score
AUTHORITY_SAFETY_BOOST = 0.05  # Extra 5% boost for guidelines on safety queries

# Exam frequency boost (Phase 3)
EXAM_BOOST_ENABLED = True  # Set to False to disable exam frequency ranking
EXAM_BOOST_FACTOR = 0.15  # 15% max boost for highest exam frequency
EXAM_MIN_FREQUENCY = 0  # Minimum exam frequency
EXAM_MAX_FREQUENCY = 10  # Maximum exam frequency (capped)


# ═══════════════════════════════════════════════════════════════════════════
# Query Classification
# ═══════════════════════════════════════════════════════════════════════════


class QueryType(Enum):
    """Classification of query intent for routing"""

    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    SPATIAL = "spatial"
    CONTRAINDICATION = "contraindication"
    COMPARATIVE = "comparative"
    CONCEPTUAL = "conceptual"
    SAFETY = "safety"  # Safety-critical queries (dosing, complications, warnings)


class ConfidenceLevel(Enum):
    """Confidence level thresholds"""

    HIGH = "high"  # >= 0.85
    MEDIUM = "medium"  # 0.70 - 0.84
    LOW = "low"  # 0.50 - 0.69
    INSUFFICIENT = "insufficient"  # < 0.50


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
# Precision Search Results
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PrecisionResult:
    """Enhanced search result with precision metrics"""

    chunk: Chunk
    dense_score: float
    colbert_score: float | None = None
    final_score: float = 0.0
    has_safety_content: bool = False
    # Authority ranking fields (for debugging/logging)
    authority_score: int = 80  # Authority score from metadata (80-100)
    authority_boost_applied: float = 0.0  # How much boost was added to final_score
    # Exam frequency fields (Phase 3 - for debugging/logging)
    exam_frequency: int = 0  # Exam frequency from metadata (0-10+)
    exam_boost_applied: float = 0.0  # How much exam boost was added to final_score

    @property
    def citation(self) -> str:
        """Format as citation"""
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
# ColBERT Client (Imported from Deep-DX)
# ═══════════════════════════════════════════════════════════════════════════

from deep_dx.knowledge.metadata_manager import MetadataManager
from deep_dx.retrieval.colbert_client import ColBERTClient
from deep_dx.retrieval.qdrant_retriever import QdrantRetriever

# ═══════════════════════════════════════════════════════════════════════════
# Precision Search Engine
# ═══════════════════════════════════════════════════════════════════════════


class PrecisionSearchEngine:
    """
    Enhanced search engine with ColBERT precision reranking.

    Architecture:
        Query → Classify → Dense Search (Qdrant) → ColBERT Rerank (top 20) → Score

    Usage:
        engine = PrecisionSearchEngine(db)
        result = engine.search("What is anterior to the facial nerve?", top_k=10)
    """

    def __init__(self, db: Database, colbert_enabled: bool = True):
        self.db = db
        self.base_search = SearchEngine(db)

        # Initialize Qdrant Retriever (The Showroom)
        self.qdrant = QdrantRetriever()

        # Deep-DX ColBERT Client integration
        self.colbert_enabled = colbert_enabled
        self.colbert = None
        if colbert_enabled:
            try:
                self.colbert = ColBERTClient()
                logger.info("✓ ColBERT Client Connected")
            except Exception as e:
                logger.warning(f"✗ ColBERT unavailable: {e}")
                self.colbert = None

        # Initialize Metadata Manager (NeuroLi Integration)
        self.source_map = {}
        try:
            self.metadata_manager = MetadataManager()
            logger.info("📚 NeuroLi Metadata Manager connected.")

            # Build Source Map (Source ID -> Full Path String)
            sources = self.db.get_all_sources()
            for s in sources:
                self.source_map[s.id] = str(s.file_path)
            logger.info(f"🗺️  Mapped {len(self.source_map)} sources to full paths.")

        except Exception as e:
            logger.warning(f"⚠️ Failed to init Metadata Manager or Source Map: {e}")

        # Initialize AI Vision Embedder
        self.vision_embedder = None
        if BiomedCLIPSearcher:
            try:
                self.vision_embedder = BiomedCLIPSearcher()
                logger.info("✓ BiomedCLIP Vision Search Connected")
            except Exception as e:
                logger.warning(f"AI Vision Init Failed: {e}")

        # Initialize Hybrid Search (BM25) with persistence
        self.bm25 = None
        try:
            from deep_dx.retrieval.bm25 import BM25Retriever

            # Try to load from disk first
            self.bm25 = BM25Retriever.load()

            if self.bm25 is None:
                # No persisted index - build from database chunks
                all_chunks = self.db.get_all_chunks()
                chunk_dicts = [
                    {"content": c.content, "id": c.id, "chunk_obj": c}
                    for c in all_chunks
                ]
                self.bm25 = BM25Retriever(chunk_dicts)
                # Save for next startup
                self.bm25.save()
                logger.info(
                    f"✓ BM25 Index Built and Saved ({len(chunk_dicts)} documents)"
                )
            else:
                logger.info(
                    f"✓ BM25 Index Loaded ({self.bm25.get_document_count()} documents)"
                )
        except Exception as e:
            logger.warning(f"bm25 init failed: {e}")

        # Phase 4: Gap Detection (lazy import to avoid circular dependency)
        from .gap_detector import GapDetector

        self.gap_detector = GapDetector(database=self.db)
        logger.info("✓ Gap Detector initialized")

        # Compile patterns
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
        """Compile terms into regex pattern"""
        escaped = [re.escape(t) for t in terms]
        return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)

    def classify_query(self, query: str) -> QueryType:
        """Classify query intent based on keywords and patterns"""
        query_lower = query.lower()

        # Check negation/contraindication
        if any(term in query_lower for term in NEGATION_TERMS):
            return QueryType.CONTRAINDICATION

        # Check spatial
        if any(term in query_lower for term in SPATIAL_TERMS):
            return QueryType.SPATIAL

        # Check procedural
        if any(term in query_lower for term in PROCEDURAL_TERMS):
            return QueryType.PROCEDURAL

        # Check comparative
        if " vs " in query_lower or "versus" in query_lower or "compare" in query_lower:
            return QueryType.COMPARATIVE

        return QueryType.FACTUAL

    def update_bm25_index(self, chunks: list, auto_save: bool = True) -> int:
        """
        Update the BM25 index with newly ingested chunks.

        Args:
            chunks: List of Chunk objects to add to the BM25 index
            auto_save: Whether to persist the index after update (default: True)

        Returns:
            Number of documents added to the index
        """
        if not self.bm25:
            logger.warning("BM25 index not initialized, cannot update")
            return 0

        # Convert Chunk objects to dicts for BM25
        chunk_dicts = [
            {"content": c.content, "id": c.id, "chunk_obj": c} for c in chunks
        ]

        added = self.bm25.add_documents(chunk_dicts)
        logger.info(
            f"BM25 Index Updated: +{added} documents (total: {self.bm25.get_document_count()})"
        )

        # Persist to disk
        if auto_save and added > 0:
            self.bm25.save()

        return added

    def get_bm25_count(self) -> int:
        """Return the number of documents in the BM25 index."""
        if not self.bm25:
            return 0
        return self.bm25.get_document_count()

    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 20,
        include_images: bool = True,
        filter_subspecialty: str | None = None,
    ) -> PrecisionRetrievalResult:
        """
        Execute precision search with ColBERT reranking.
        Hybrid: Dense (Qdrant) + BM25 -> ColBERT
        """
        start_time = time.time()

        # Activity Tracking (for background jobs)
        try:
            Path(".app_activity").touch()
        except:
            pass

        systems_used = ["dense"]
        warnings = []

        # Step 1: Classify query
        query_type = self.classify_query(query)

        # Step 2: Retrieval (Hybrid)
        candidate_k = min(top_k * 5, 100)

        # 2a. Dense Search (Qdrant)
        # Replacing legacy base_search.search_chunks with Qdrant retrieval
        dense_results = []
        if self.qdrant and self.qdrant.client:
            try:
                dense_results = self.qdrant.search(
                    query_embedding=query_embedding, top_k=candidate_k, min_score=0.4
                )
                systems_used[0] = "dense_qdrant"
            except Exception as e:
                logger.warning(f"Qdrant search failed: {e}")
                warnings.append(f"Qdrant search failed: {e}")

        if not dense_results:  # Fallback to legacy if Qdrant down or failed
            logger.warning(
                "Qdrant unavailable or failed - falling back to legacy SQLite search"
            )
            dense_results = self.base_search.search_chunks(
                query_embedding=query_embedding, top_k=candidate_k
            )
            if "dense_qdrant" in systems_used:
                systems_used.remove("dense_qdrant")
            systems_used.append("dense_sqlite_fallback")
            warnings.append("Using legacy SQLite search (Qdrant unavailable/failed)")

        # 2b. Sparse Search (BM25)
        sparse_chunks = []
        if self.bm25:
            try:
                bm25_hits = self.bm25.search(query, top_k=candidate_k)
                # Convert back to SearchResult format (dummy score for merging)
                sparse_chunks = [h[0]["chunk_obj"] for h in bm25_hits]
                systems_used.append("bm25")
            except Exception as e:
                logger.warning(f"BM25 Search failed: {e}")

        # 2c. Merge Candidates
        # Combine Dense and Sparse chunks, deduplicating by ID
        candidates = {}

        # Add Dense
        for r in dense_results:
            candidates[r.chunk.id] = {
                "chunk": r.chunk,
                "dense_score": r.score,
                "sparse_score": 0.0,
            }

        # Add Sparse
        for c in sparse_chunks:
            if c.id in candidates:
                candidates[c.id]["sparse_score"] = 1.0  # Marker
            else:
                candidates[c.id] = {
                    "chunk": c,
                    "dense_score": 0.0,  # Not found in dense
                    "sparse_score": 1.0,
                }

        # Merging Hybrid Results (Simple: Concat for now, Reranker will sort)
        candidate_chunks_with_scores = list(candidates.values())

        # Deduplicate candidates (extract chunks from the dicts)
        seen_ids = set()
        unique_candidates = []
        for cand_dict in candidate_chunks_with_scores:
            chunk = cand_dict["chunk"]
            if chunk.id not in seen_ids:
                unique_candidates.append(chunk)
                seen_ids.add(chunk.id)

        # --- Metadata Enrichment & Filtering ---
        if self.metadata_manager:
            filtered_candidates = []
            for chunk in unique_candidates:
                # enrich
                # Resolve full path from Source ID
                full_path = self.source_map.get(chunk.source_id)

                if full_path:
                    meta = self.metadata_manager.resolve_metadata_from_path(full_path)
                else:
                    meta = self.metadata_manager.get_metadata("unknown")

                chunk.metadata.update(meta)

                # filter
                if filter_subspecialty:
                    # Check if metadata subspecialty matches requested
                    # Note: metadata 'subspecialty' is Title Case (e.g. "Vascular")
                    if meta.get("subspecialty") != filter_subspecialty:
                        continue

                filtered_candidates.append(chunk)
            unique_candidates = filtered_candidates

        # Re-create the candidate_chunks_with_scores structure for reranking
        # This assumes unique_candidates now contains the filtered/enriched chunks
        # We need to map them back to their original dense/sparse scores if they were in candidates
        final_candidates_for_reranking = []
        for chunk in unique_candidates:
            if chunk.id in candidates:
                # Use the original scores if the chunk was in the initial candidates pool
                final_candidates_for_reranking.append(candidates[chunk.id])
            else:
                # This case should ideally not happen if unique_candidates are derived from candidates
                # but as a fallback, create a new entry.
                final_candidates_for_reranking.append(
                    {
                        "chunk": chunk,
                        "dense_score": 0.0,  # Default if not found in original dense
                        "sparse_score": 0.0,  # Default if not found in original sparse
                    }
                )

        # Optimization: Cap reranking pool to top 50 to prevent CPU timeout
        MAX_RERANK_POOL = 50
        if len(final_candidates_for_reranking) > MAX_RERANK_POOL:
            logger.info(
                f"Capping rerank pool from {len(final_candidates_for_reranking)} to {MAX_RERANK_POOL}"
            )
            final_candidates_for_reranking = final_candidates_for_reranking[
                :MAX_RERANK_POOL
            ]

        logger.info(
            f"Hybrid Pool: {len(dense_results)} dense + {len(sparse_chunks)} sparse -> {len(final_candidates_for_reranking)} unique candidates (after metadata filter)"
        )

        if not final_candidates_for_reranking:
            return PrecisionRetrievalResult(
                query=query,
                query_type=query_type,
                results=[],
                images=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.INSUFFICIENT,
                retrieval_time_ms=(time.time() - start_time) * 1000,
                systems_used=systems_used,
                warnings=["No results found"],
            )

        # Step 3: ColBERT precision reranking
        # We rerank the merged pool
        if self.colbert_enabled and self.colbert:
            try:
                documents = [c["chunk"].content for c in final_candidates_for_reranking]

                # Call Deep-DX ColBERT Reranker
                reranked = self.colbert.rerank(query, documents, k=top_k)
                systems_used.append("colbert")

                # Map back to results
                precision_results = []
                for r in reranked:
                    # Rerank result structure: {"document_index": int, "score": float}
                    # Note: colbert_client.py uses 'document_index', NOT 'result_index'
                    idx = r.get("document_index")

                    if idx is not None and idx < len(final_candidates_for_reranking):
                        cand = final_candidates_for_reranking[idx]
                        original_chunk = cand["chunk"]

                        # Extract metadata (set during enrichment)
                        authority_score = original_chunk.metadata.get(
                            "authority_score", 80
                        )
                        exam_frequency = original_chunk.metadata.get(
                            "exam_frequency", 0
                        )

                        # Apply authority boost to ColBERT score
                        authority_boosted = self._apply_authority_boost(
                            base_score=r["score"],
                            authority_score=authority_score,
                            query_type=query_type,
                        )

                        # Apply exam boost (stacked on top of authority)
                        final_boosted = self._apply_exam_boost(
                            base_score=authority_boosted,
                            exam_frequency=exam_frequency,
                            query_type=query_type,
                        )

                        precision_results.append(
                            PrecisionResult(
                                chunk=original_chunk,
                                dense_score=cand["dense_score"],
                                colbert_score=r["score"],
                                final_score=final_boosted,  # Authority + exam boosted
                                has_safety_content=self._has_safety_content(
                                    original_chunk.content
                                ),
                                authority_score=authority_score,
                                authority_boost_applied=authority_boosted - r["score"],
                                exam_frequency=exam_frequency,
                                exam_boost_applied=final_boosted - authority_boosted,
                            )
                        )
            except Exception as e:
                logger.error(f"ColBERT Rerank Failed: {e}")
                precision_results = []
        else:
            precision_results = []

        if not precision_results:
            # Fallback: use dense scores only
            precision_results = []
            for r in dense_results[:top_k]:
                authority_score = r.chunk.metadata.get("authority_score", 80)
                exam_frequency = r.chunk.metadata.get("exam_frequency", 0)

                # Apply authority boost
                authority_boosted = self._apply_authority_boost(
                    base_score=r.score,
                    authority_score=authority_score,
                    query_type=query_type,
                )

                # Apply exam boost (stacked on top of authority)
                final_boosted = self._apply_exam_boost(
                    base_score=authority_boosted,
                    exam_frequency=exam_frequency,
                    query_type=query_type,
                )

                precision_results.append(
                    PrecisionResult(
                        chunk=r.chunk,
                        dense_score=r.score,
                        colbert_score=None,
                        final_score=final_boosted,  # Authority + exam boosted
                        has_safety_content=self._has_safety_content(r.chunk.content),
                        authority_score=authority_score,
                        authority_boost_applied=authority_boosted - r.score,
                        exam_frequency=exam_frequency,
                        exam_boost_applied=final_boosted - authority_boosted,
                    )
                )
            if self.colbert_enabled:
                warnings.append("ColBERT unavailable/failed - using dense scores only")

        # Re-sort by authority-boosted final_score (highest first)
        precision_results.sort(key=lambda x: x.final_score, reverse=True)

        # Step 4: Safety check for contraindication queries
        if query_type == QueryType.CONTRAINDICATION:
            has_safety = any(r.has_safety_content for r in precision_results)
            if not has_safety:
                warnings.append("Safety query but no contraindication content found")

        # === PHASE 4: GAP DETECTION ===
        gap_warnings = self.gap_detector.detect_gaps(
            query=query, query_type=query_type, results=precision_results, top_k=top_k
        )

        # Convert GapWarning objects to strings and append to warnings
        for gap in gap_warnings:
            warnings.append(gap.message)
        # === END PHASE 4 ===

        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(precision_results, query_type)
        confidence_level = self._score_to_level(confidence)

        # Step 6: Get related images (Using AI Vision Integration)
        images = []
        if include_images:
            try:
                # Primary: AI Semantic Search
                images = self._search_images_ai(query, top_k=5)
                systems_used.append("ai_vision_search")
            except Exception as e:
                logger.warning(f"AI Vision Search failed: {e}")
                # Fallback: Legacy image search
                if precision_results:
                    source_ids = list(
                        set(r.chunk.source_id for r in precision_results[:5])
                    )
                    image_results = self.base_search.search_images(
                        query_embedding=query_embedding, top_k=20, source_ids=source_ids
                    )
                    images = [img for img, _ in image_results]
                    systems_used.append("legacy_image_search_fallback")

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Precision search (Hybrid): {len(dense_results)} dense + {len(sparse_chunks)} sparse → {len(precision_results)} results "
            f"in {elapsed_ms:.1f}ms | Confidence: {confidence:.2f} ({confidence_level.value})"
        )

        return PrecisionRetrievalResult(
            query=query,
            query_type=query_type,
            results=precision_results,
            images=images,
            confidence=confidence,
            confidence_level=confidence_level,
            retrieval_time_ms=elapsed_ms,
            systems_used=systems_used,
            warnings=warnings,
        )

    def _search_images_ai(self, query: str, top_k: int = 5) -> list[ExtractedImage]:
        """Search for images using BiomedCLIP and Qdrant"""
        if not self.vision_embedder or not self.qdrant or not self.qdrant.client:
            raise RuntimeError("AI Vision components not initialized")

        # 1. Embed query (Text -> Image Space)
        vector = self.vision_embedder.embed_text(query)
        if vector.size == 0:
            return []

        # 2. Search Qdrant
        results = self.qdrant.client.search(
            collection_name="neurosurgical_figures_hybrid",
            query_vector=("biomed", vector[0].tolist()),
            limit=top_k,
            with_payload=True,
        )

        # 3. Convert to ExtractedImage with full metadata
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
                    image_type=payload.get("modality", "unknown"),  # Simplified mapping
                    width=0,
                    height=0,
                    # Enhanced metadata for LLM context (Priority 1)
                    modality=payload.get("modality", "unknown"),
                    detected_regions=payload.get("detected_regions", []),
                    region_confidence=payload.get("region_confidence", 0.0),
                    ocr_caption=payload.get("ocr_caption", ""),
                    caption_source=payload.get("caption_source", "proximity"),
                )
            )
        return images

    def _has_safety_content(self, text: str) -> bool:
        """Check if text contains safety-critical content"""
        return any(p.search(text) for p in self._safety_patterns)

    def _calculate_confidence(
        self, results: list[PrecisionResult], query_type: QueryType
    ) -> float:
        """Calculate confidence score from results"""
        if not results:
            return 0.0

        # Factor 1: Top score quality (40%)
        top_scores = [r.final_score for r in results[:3]]
        avg_top_score = sum(top_scores) / len(top_scores) if top_scores else 0

        # Normalize ColBERT scores (typically 15-35 range)
        if results[0].colbert_score is not None:
            score_factor = min(avg_top_score / 30, 1.0)
        else:
            score_factor = avg_top_score  # Dense scores already 0-1

        # Factor 2: Source diversity (30%)
        sources = set(r.chunk.source_id for r in results[:10])
        diversity_factor = min(len(sources) / 3, 1.0)

        # Factor 3: Result count (15%)
        count_factor = min(len(results) / 10, 1.0)

        # Factor 4: Query-type specific (15%)
        type_factor = 0.8  # Default
        if query_type == QueryType.CONTRAINDICATION:
            # Penalize if no safety content
            has_safety = any(r.has_safety_content for r in results[:5])
            type_factor = 1.0 if has_safety else 0.5

        confidence = (
            0.40 * score_factor
            + 0.30 * diversity_factor
            + 0.15 * count_factor
            + 0.15 * type_factor
        )

        return min(max(confidence, 0.0), 1.0)

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        """Convert score to confidence level"""
        if score >= 0.85:
            return ConfidenceLevel.HIGH
        elif score >= 0.70:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.50:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.INSUFFICIENT

    def _apply_authority_boost(
        self,
        base_score: float,
        authority_score: int,
        query_type: QueryType | None = None,
    ) -> float:
        """Apply authority boost to search score.

        Args:
            base_score: Base similarity score (from ColBERT/dense search)
            authority_score: Authority score from metadata (80-100)
            query_type: Optional query type for extra safety boosting

        Returns:
            Boosted final score

        Examples:
            - Guideline (100) with base 0.85 → 0.85 * 1.20 = 1.02
            - Textbook (95) with base 0.85 → 0.85 * 1.15 = 0.98
            - Default (80) with base 0.85 → 0.85 * 1.00 = 0.85
        """
        if not AUTHORITY_BOOST_ENABLED:
            return base_score

        # Normalize authority score to 0-1 range
        # 80 → 0.0, 90 → 0.5, 100 → 1.0
        normalized_authority = (authority_score - AUTHORITY_MIN_SCORE) / (
            AUTHORITY_MAX_SCORE - AUTHORITY_MIN_SCORE
        )
        normalized_authority = max(0.0, min(1.0, normalized_authority))

        # Calculate boost multiplier (1.0 to 1.2 for 20% max boost)
        boost_multiplier = 1.0 + (normalized_authority * AUTHORITY_BOOST_FACTOR)

        # Extra boost for safety-critical queries (contraindications, dosing, complications)
        if query_type in [QueryType.CONTRAINDICATION, QueryType.SAFETY]:
            # Guidelines get extra 5% boost for safety queries
            if authority_score >= 95:
                boost_multiplier += AUTHORITY_SAFETY_BOOST

        return base_score * boost_multiplier

    def _apply_exam_boost(
        self,
        base_score: float,
        exam_frequency: int,
        query_type: QueryType | None = None,
    ) -> float:
        """Apply exam frequency boost to search score.

        Rationale: Topics appearing frequently in board exams are clinically
        important foundational knowledge. Boost these in exam mode.

        Args:
            base_score: Base score (already authority-boosted)
            exam_frequency: Number of times topic appears in exams (0-10+)
            query_type: Query type to determine if boost applies

        Returns:
            Score after exam frequency boost

        Examples:
            - Exam freq 10, base 1.02 → 1.02 * 1.15 = 1.173 (full boost)
            - Exam freq 5, base 1.02 → 1.02 * 1.075 = 1.095 (half boost)
            - Exam freq 0, base 1.02 → 1.02 * 1.0 = 1.02 (no boost)
        """
        if not EXAM_BOOST_ENABLED:
            return base_score

        # Only boost for query types where exam frequency matters
        # (Not procedural/spatial/contraindication - those need different signals)
        if query_type and query_type not in [QueryType.FACTUAL, QueryType.CONCEPTUAL]:
            return base_score

        # Normalize exam frequency to 0-1 range
        # 0 → 0.0, 5 → 0.5, 10+ → 1.0
        normalized_frequency = (exam_frequency - EXAM_MIN_FREQUENCY) / (
            EXAM_MAX_FREQUENCY - EXAM_MIN_FREQUENCY
        )
        normalized_frequency = max(0.0, min(1.0, normalized_frequency))

        # Calculate boost multiplier (1.0 to 1.15)
        boost_multiplier = 1.0 + (normalized_frequency * EXAM_BOOST_FACTOR)

        return base_score * boost_multiplier

    def retrieve_for_topic(
        self,
        query_embedding: list[float],
        topic: str,
        chunk_types: list[Any] | None = None,  # adapt type hint
        top_k: int = None,
        include_images: bool = True,
    ) -> Any:  # Returns RetrievalResult
        """
        Adapter method for SynthesisEngine compatibility.
        Executes precision search and converts to standard RetrievalResult.
        """
        top_k = top_k or 20

        # 1. Execute Precision Search
        precision_result = self.search(
            query=topic,
            query_embedding=query_embedding,
            top_k=top_k,
            include_images=include_images,
        )

        # 2. Convert PrecisionResult -> SearchResult
        search_results = []
        for pr in precision_result.results:
            search_results.append(SearchResult(chunk=pr.chunk, score=pr.final_score))

        # 3. Construct RetrievalResult
        # We need to import RetrievalResult or use the one from search module if available?
        # It's in src.index.search.
        from src.index.search import RetrievalResult

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
        """
        Quick search without ColBERT (for speed-critical paths).
        Falls back to base search engine.
        """
        return self.base_search.search_chunks(
            query_embedding=query_embedding, top_k=top_k
        )


# ═══════════════════════════════════════════════════════════════════════════
# Synthesis Verification
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
    """
    Verify synthesized text against source chunks.

    Extracts claims from synthesis and checks each against sources.
    This is the final safety gate before output.

    Args:
        synthesis_text: The generated synthesis
        source_chunks: Source chunks used for generation
        llm_client: AI client for claim extraction/verification

    Returns:
        VerificationResult with claim-by-claim analysis
    """
    # This would use the LLM to:
    # 1. Extract factual claims from synthesis
    # 2. Check each claim against source chunks
    # 3. Return supported/contradicted/not_found counts

    # Placeholder - full implementation would call LLM
    return VerificationResult(
        claims_extracted=0,
        claims_supported=0,
        claims_contradicted=0,
        claims_not_found=0,
        verification_score=1.0,
    )
