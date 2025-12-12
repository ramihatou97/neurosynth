"""
RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval
======================================================================
Implements recursive summarization to build a hierarchical tree of knowledge.
1. Groups chunks into clusters (GMM/K-Means).
2. Summarizes each cluster using an LLM.
3. Recursively summarizing the summaries until a root node is reached.

Reference: Sarthi et al., "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval", ICLR 2024.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from src.ai.client import AIClient  # Use existing AI client
from src.index.database import Database
from src.models import Chunk, ChunkType

# Optional Dependencies for Clustering
try:
    from sklearn.mixture import GaussianMixture

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Cluster:
    chunks: list[Chunk]
    centroid: list[float]
    level: int


class RecursiveSummarizer:
    """
    Builds the RAPTOR tree.
    """

    def __init__(self, ai_client: AIClient, database: Database, embedder=None):
        self.ai = ai_client
        self.db = database
        self.embedder = embedder  # Optional: AsyncEmbedder for summary embedding
        self.max_cluster_size = 10  # Soft limit
        self.target_levels = 3

    async def generate_tree(self, content_chunks: list[Chunk]) -> list[Chunk]:
        """
        Generate the full tree of summaries from leaf chunks.
        Returns: List of NEW summary chunks (leaves are not returned, they are already in DB).
        """
        if not content_chunks:
            return []

        logger.info(
            f"Starting RAPTOR tree generation for {len(content_chunks)} chunks."
        )

        current_level_chunks = content_chunks
        all_summary_chunks = []

        for level in range(1, self.target_levels + 1):
            logger.info(f"Processing Level {level}...")

            # 1. Cluster
            clusters = self._cluster_chunks(current_level_chunks)
            if not clusters:
                logger.info("No more clusters formed. Stopping recursion.")
                break

            # 2. Summarize
            summary_tasks = [self._summarize_cluster(c, level) for c in clusters]
            summaries = await asyncio.gather(*summary_tasks)

            # Filter failed summaries
            valid_summaries = [s for s in summaries if s]

            # Embed summary chunks (needed for next level clustering and search)
            if valid_summaries and self.embedder:
                try:
                    valid_summaries = await self.embedder.embed_chunks(valid_summaries)
                    embedded_count = sum(1 for s in valid_summaries if s.embedding)
                    logger.info(
                        f"  Embedded {embedded_count}/{len(valid_summaries)} summary chunks"
                    )
                except Exception as e:
                    logger.warning(f"  Failed to embed summary chunks: {e}")

            all_summary_chunks.extend(valid_summaries)

            # Prepare for next level recursion
            current_level_chunks = valid_summaries

            if len(current_level_chunks) <= 1:
                logger.info("Root node reached.")
                break

        return all_summary_chunks

    def _cluster_chunks(self, chunks: list[Chunk]) -> list[Cluster]:
        """
        Cluster chunks based on embeddings.
        Uses Gaussian Mixture Model if available, else naive grouping.
        """
        if not chunks:
            return []

        # Extract embeddings
        embeddings = [c.embedding for c in chunks if c.embedding]

        if len(embeddings) < len(chunks):
            logger.warning(
                "Some chunks lack embeddings. Skipping clustering for those."
            )
            # For robustness, we could compute them, but let's assume they exist for now.

        if not embeddings or len(embeddings) < 2:
            return [Cluster(chunks=chunks, centroid=[], level=0)]

        X = np.array(embeddings)
        n_samples = X.shape[0]

        # Determine number of clusters (Adaptive)
        # Aim for ~5-10 items per cluster
        n_clusters = max(1, n_samples // self.max_cluster_size)
        # Or use BIC to find optimal K (too slow for MVP)

        try:
            if SKLEARN_AVAILABLE and n_samples >= n_clusters:
                gmm = GaussianMixture(n_components=n_clusters, random_state=42)
                gmm.fit(X)
                labels = gmm.predict(X)
                # Soft clustering? RAPTOR allows chunks in multiple clusters.
                # For MVP, hard clustering is fine.
            else:
                # Fallback: Naive chunking (just group sequentially)
                logger.info(
                    "Sklearn unavailable or too few samples. Using sequential grouping."
                )
                labels = [i // self.max_cluster_size for i in range(n_samples)]

            # Group chunks by label
            clusters_map = {}
            for i, label in enumerate(labels):
                if label not in clusters_map:
                    clusters_map[label] = []
                clusters_map[label].append(chunks[i])

            return [
                Cluster(chunks=c_list, centroid=[], level=0)
                for c_list in clusters_map.values()
            ]

        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return []

    async def _summarize_cluster(self, cluster: Cluster, level: int) -> Chunk | None:
        """
        Generate a summary for a cluster of chunks.
        """
        # Concatenate text
        context_text = "\n\n".join([c.content for c in cluster.chunks])

        # Prompt
        prompt = (
            f"Synthesize the following information into a concise summary (Level {level} abstraction). "
            "Capture the main themes, key entities, and their relationships. "
            "Do not lose critical medical details.\n\n"
            f"{context_text[:10000]}"  # Truncate for safety
        )

        try:
            summary_text = await self.ai.generate(prompt)

            # Create Summary Chunk
            # ID is hash of content
            import hashlib

            s_id = hashlib.md5(summary_text.encode()).hexdigest()[:16]

            # Embed the summary (needed for next level clustering)
            # embedding = await self.ai.embed(summary_text)
            # Note: For MVP, we assume we need to call embedding service.
            # Here we mock or call it. Ideally we pass an Embedder interface.

            summary_chunk = Chunk(
                id=s_id,
                source_id="raptor_generated",
                source_title="RAPTOR Summary",
                section_title=f"Level {level} Summary",
                content=summary_text,
                chunk_type=ChunkType.SUMMARY,
                page_start=0,
                page_end=0,
                embedding=None,  # Needs embedding!
                parent_context=context_text,  # Traceability
                evidence_level="synthesis",
            )
            return summary_chunk

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return None
