"""
Unified Search Engine
=====================
Consolidated retrieval engine supporting Fast (Vector), Balanced (Hybrid), and Deep (ColBERT) modes.

Replaces:
- SearchEngine (Legacy)
- PrecisionSearchEngine (Wrapper)
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.index.database import Database
from src.models import Chunk, ChunkType, ExtractedImage, ImageType, SearchResult

# Try to load settings, fallback to defaults if not available
try:
    from neurosynth.config import Settings

    _settings = Settings()
except Exception:
    _settings = None

# Optional Dependencies
try:
    from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
except ImportError:
    BiomedCLIPSearcher = None

try:
    from deep_dx.retrieval.colbert_client import ColBERTClient
except ImportError:
    ColBERTClient = None

try:
    from deep_dx.retrieval.qdrant_retriever import QdrantRetriever
except ImportError:
    QdrantRetriever = None

try:
    from deep_dx.retrieval.bm25 import BM25Retriever
except ImportError:
    BM25Retriever = None

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    FAST = "fast"  # Vector Only (Qdrant/SQLite)
    BALANCED = "balanced"  # Hybrid (Vector + BM25)
    DEEP = "deep"  # Hybrid + ColBERT Reranking
    REASONING = "reasoning"  # Vector + Graph + RAPTOR


@dataclass
class RetrievalResult:
    """Unified result object for all search types."""

    chunks: list[SearchResult]
    images: list[ExtractedImage]
    total_chunks: int
    total_images: int
    mode: SearchMode
    latency_ms: float
    confidence: float
    warnings: list[str] = field(default_factory=list)
    graph_context: list[str] = field(default_factory=list)  # Phase 6: Graph Context


class UnifiedSearchEngine:
    """
    The Single Source of Truth for Retrieval.

    Modes:
    - Fast: <200ms, pure semantic search
    - Balanced: ~500ms, semantic + keyword (BM25)
    - Deep: ~1.5s, Hybrid + Cross-Encoder Reranking (ColBERT)
    - Reasoning: ~3s, Deep + Graph Traversal + Hierarchical Context
    """

    def __init__(self, db: Database):
        self.db = db
        self.mode = SearchMode.BALANCED  # Default mode
        if _settings and hasattr(_settings, "search_mode"):
            try:
                self.mode = SearchMode(_settings.search_mode)
            except (ValueError, KeyError):
                pass

        # Initialize Embedder (New)
        try:
            from src.neurosynth.llm.embeddings import EmbeddingClient

            self.embedder = EmbeddingClient()
        except ImportError:
            logger.warning(
                "EmbeddingClient import failed. Search engine cannot embed queries."
            )
            self.embedder = None

        # 1. Vector Store (Qdrant)
        self.qdrant = None
        if QdrantRetriever:
            try:
                self.qdrant = QdrantRetriever()
                logger.info("✓ Qdrant Connected")
            except Exception as e:
                logger.warning(f"Qdrant init failed: {e}")

        # 2. Keyword Index (BM25)
        self.bm25 = None
        if BM25Retriever:
            try:
                self.bm25 = BM25Retriever.load()
                if not self.bm25:  # Build if missing
                    self._build_bm25()
                logger.info("✓ BM25 Index Ready")
            except Exception as e:
                logger.warning(f"BM25 init failed: {e}")

        # 3. Reranker (ColBERT)
        self.colbert = None
        if ColBERTClient:
            try:
                self.colbert = ColBERTClient()
                logger.info("✓ ColBERT Reranker Ready")
            except Exception as e:
                logger.warning(f"ColBERT init failed: {e}")

        # 4. Vision (BiomedCLIP)
        self.vision = None
        if BiomedCLIPSearcher:
            try:
                self.vision = BiomedCLIPSearcher()
                logger.info("✓ BiomedCLIP Vision Ready")
            except Exception as e:
                logger.warning(f"Vision init failed: {e}")

        # 5. Knowledge Graph (Phase 6)
        self.graph = None
        try:
            import json

            import networkx as nx
            from networkx.readwrite import json_graph

            from src.index.graph import KnowledgeGraphBuilder

            graph_path = Path("data/knowledge_graph.json")
            if graph_path.exists():
                with open(graph_path) as f:
                    data = json.load(f)

                # Reconstruct graph wrapper
                # We instantiate a dummy builder just to use its search method if possible,
                # or just use the graph directly. Builder needs AIClient which we don't want here.
                # So we simply load the graph into NetworkX and implement search logic here or in a helper.

                # Let's use a lightweight wrapper or simple logic
                self.graph = json_graph.node_link_graph(data)
                logger.info(f"✓ Knowledge Graph Loaded ({len(self.graph.nodes)} nodes)")
            else:
                logger.info("ℹ️ No Knowledge Graph found (skipping)")

        except Exception as e:
            logger.warning(f"Graph load failed: {e}")

    def _build_bm25(self):
        """Build BM25 index from DB chunks (Fallback)."""
        logger.info("Building BM25 index from database...")
        all_chunks = self.db.get_all_chunks()
        chunk_dicts = [
            {"content": c.content, "id": c.id, "chunk_obj": c} for c in all_chunks
        ]
        self.bm25 = BM25Retriever(chunk_dicts)
        self.bm25.save()

    def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        mode: SearchMode | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """
        Execute search strategy based on mode.
        """
        start = time.time()
        mode = mode or self.mode
        warnings = []

        # Auto-embed if needed
        if not query_embedding and self.embedder:
            try:
                query_embedding = self.embedder.embed(query)
            except Exception as e:
                warnings.append(f"Query embedding failed: {e}")

        # Auto-downgrade mode if components missing
        if mode == SearchMode.DEEP and not self.colbert:
            warnings.append("ColBERT unavailable, downgrading to BALANCED")
            mode = SearchMode.BALANCED
        if mode == SearchMode.BALANCED and not self.bm25:
            # If BM25 missing, vector-only is fine
            warnings.append("BM25 unavailable, relying on Vector search")
            if not query_embedding:
                # If also no embedding, we are dead
                warnings.append("Critical: No embedding and no BM25")

            # Don't necessarily change mode name, just skip BM25 block

        # 1. Retrieval Phase
        candidates = []

        # A. Vector Search
        if self.qdrant and query_embedding:
            try:
                # Standardize qdrant search
                q_results = self.qdrant.search(
                    query_embedding,
                    top_k=top_k * 2 if mode != SearchMode.FAST else top_k,
                    filters=filters,  # Pass filters!
                )

                # Hydrate "Small-to-Big" Context
                for res in q_results:
                    if res.chunk.parent_context:
                        # Reconstruct context header (Source, Section, Evidence)
                        # Because parent_context is raw text, we must re-enrich it so LLM sees valid metadata.
                        header = f"Source: {res.chunk.source_title} | Section: {res.chunk.section_title}"
                        if res.chunk.evidence_level:
                            header += f" [Evidence: {res.chunk.evidence_level}]"

                        res.chunk.content = f"{header}\n{res.chunk.parent_context}"

                candidates.extend(q_results)
            except Exception as e:
                warnings.append(f"Qdrant failed: {e}")
                import traceback

                logger.error(traceback.format_exc())
                # Fallback to SQLite vector search if implemented in DB
                # candidates.extend(self.db.search_sqlite(query_embedding))

        # B. Keyword Search (Balanced/Deep only)
        if mode in [SearchMode.BALANCED, SearchMode.DEEP] and self.bm25:
            try:
                # BM25 returns raw hits, need to convert to SearchResult
                bm_hits = self.bm25.search(query, top_k=top_k)
                for hit in bm_hits:
                    # Convert hit to SearchResult (chunk_obj stored in hit[0])
                    chunk = hit[0].get("chunk_obj")
                    if chunk:
                        candidates.append(
                            SearchResult(chunk=chunk, score=0.5)
                        )  # Dummy score for BM25
            except Exception as e:
                warnings.append(f"BM25 failed: {e}")

        # Deduplicate candidates (by chunk ID)
        unique_map = {c.chunk.id: c for c in candidates}
        candidates = list(unique_map.values())

        # 2. Reranking Phase (Deep Only)
        if mode == SearchMode.DEEP and self.colbert:
            try:
                docs = [c.chunk.content for c in candidates]
                scores = self.colbert.rerank(query, docs) or []
                # Update scores (scores is list of dicts with index/score)
                if not isinstance(scores, list):
                    warnings.append("Reranker returned invalid format (not a list)")
                    scores = []
                if not scores:
                    warnings.append(
                        "Reranking returned no scores, falling back to original ranking"
                    )
                    candidates.sort(key=lambda x: x.score, reverse=True)
                else:
                    reranked_candidates = []
                    for r in scores:
                        idx = r["document_index"]
                        if idx < len(candidates):
                            cand = candidates[idx]
                            cand.score = r["score"]  # update with unified score
                            reranked_candidates.append(cand)

                    # Re-sort
                    reranked_candidates.sort(key=lambda x: x.score, reverse=True)
                    candidates = reranked_candidates[:top_k]
            except Exception as e:
                warnings.append(f"Reranking failed: {e}")
                # Fallback sort by vector score
                candidates.sort(key=lambda x: x.score, reverse=True)
        else:
            # Fast/Balanced: Sort by vector/dummy score
            candidates.sort(key=lambda x: x.score, reverse=True)
            candidates = candidates[:top_k]

        # 3. Image Search (Parallel)
        images = []
        if self.vision:
            try:
                # 1. Embed query into Visual Space using BiomedCLIP
                # embed_text returns (batch, dim), take [0] and convert to list
                vis_emb_result = self.vision.embed_text(query)
                if len(vis_emb_result) > 0:
                    vis_query_vec = vis_emb_result[0].tolist()

                    # 2. Search Qdrant "neurosurgical_figures_hybrid"
                    # We use the raw client attached to the QdrantRetriever or locally
                    q_client = self.qdrant.client if self.qdrant else None

                    if q_client:
                        # Use query_points with 'using' param for named vectors (qdrant-client v1.x)
                        query_response = q_client.query_points(
                            collection_name="neurosurgical_figures_hybrid",
                            query=vis_query_vec,
                            # using="biomed",  # Removed to use default vector
                            limit=top_k,
                            with_payload=True,
                            score_threshold=0.15,  # Minimum similarity threshold
                        )
                        v_results = query_response.points

                        # 3. Convert ScoredPoint -> ExtractedImage
                        for hit in v_results:
                            payload = hit.payload
                            if not payload:
                                continue

                            # Heuristic type mapping if not in payload
                            c_lower = payload.get("caption", "").lower()
                            img_type = ImageType.ILLUSTRATION
                            if "mri" in c_lower:
                                img_type = ImageType.IMAGING_MRI
                            elif "ct " in c_lower:
                                img_type = ImageType.IMAGING_CT
                            elif "intraoperative" in c_lower:
                                img_type = ImageType.SURGICAL_PHOTO

                            img = ExtractedImage(
                                id=payload.get("filename", str(hit.id)),
                                source_id=payload.get("source_pdf", "unknown"),
                                page=int(payload.get("page_num", 0)),
                                file_path=Path(payload.get("path", "")),
                                caption=payload.get("caption", ""),
                                surrounding_text=payload.get("context", ""),
                                image_type=img_type,
                                modality=payload.get("modality", "unknown"),
                                detected_regions=payload.get("detected_regions", []),
                            )
                            # Store retrieval score (could be useful for ranking later)
                            # img.score = hit.score
                            images.append(img)
            except Exception as e:
                warnings.append(f"Visual search failed: {e}")

        # 4. Graph Reasoning Phase (Phase 6)
        graph_context = []
        if mode == SearchMode.REASONING and self.graph:
            try:
                import networkx as nx

                # Simple Entity Linker: Check if graph nodes appear in query
                query_lower = query.lower()
                matched_nodes = [
                    node
                    for node in self.graph.nodes()
                    if str(node).lower() in query_lower
                ]

                if matched_nodes:
                    # Traversal: Get 1-hop subgraph
                    # We manually traverse to control output
                    edges = []
                    for node in matched_nodes:
                        # Outgoing
                        for neighbor in self.graph.neighbors(node):
                            rel = self.graph.edges[node, neighbor].get(
                                "relation", "related_to"
                            )
                            edges.append(f"{node} --[{rel}]--> {neighbor}")

                        # Incoming? (NetworkX DiGraph neighbors are successors)
                        # We could search predecessors too but stick to 1-hop forward for now

                    graph_context = list(set(edges))[:10]  # Limit to top 10 facts
            except Exception as e:
                warnings.append(f"Graph traversal failed: {e}")

        latency = (time.time() - start) * 1000

        return RetrievalResult(
            chunks=candidates,
            images=images,
            total_chunks=len(candidates),
            total_images=len(images),
            mode=mode,
            latency_ms=latency,
            confidence=candidates[0].score if candidates else 0.0,
            warnings=warnings,
            graph_context=graph_context,
        )
