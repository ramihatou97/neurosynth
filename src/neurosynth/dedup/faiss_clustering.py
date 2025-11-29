"""FAISS-based semantic clustering for efficient large-scale deduplication.

This module provides high-performance clustering using FAISS IndexFlatIP
for similarity search, combined with Union-Find for transitive grouping.

For 5-20K chunks, IndexFlatIP provides exact search without training.
For larger datasets, consider IndexIVFFlat with training.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.dedup.embeddings import EmbeddingGenerator
from neurosynth.models.document import ContentChunk
from neurosynth.models.knowledge import KnowledgeCluster

if TYPE_CHECKING:
    pass

console = Console()

# FAISS is optional - import with fallback
try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    console.print(
        "[yellow]Warning: FAISS not installed. Install with: pip install faiss-cpu[/yellow]"
    )


class UnionFind:
    """Efficient Union-Find data structure with path compression and union by rank.

    Used for transitive clustering: if A~B and B~C, then A, B, C are in same cluster.
    """

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """Union by rank. Returns True if union performed (not already same set)."""
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True

    def get_groups(self) -> dict[int, list[int]]:
        """Return all groups as {root: [members]}."""
        groups: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)
        return groups


@dataclass
class FAISSClusteringResult:
    """Result of FAISS-based clustering operation."""

    clusters: list[KnowledgeCluster]
    total_chunks: int
    num_clusters: int
    dedup_ratio: float
    similarity_stats: dict[str, float] = field(default_factory=dict)
    faiss_search_time_ms: float = 0.0


class FAISSClusterer:
    """High-performance semantic clustering using FAISS IndexFlatIP.

    This clusterer uses:
    1. FAISS IndexFlatIP for exact inner product similarity (cosine for L2-normalized vectors)
    2. Union-Find for transitive clustering of similar chunks

    Suitable for 5-20K chunks without training. For larger datasets,
    consider IndexIVFFlat with nlist ~= sqrt(n).
    """

    def __init__(
        self,
        similarity_threshold: float | None = None,
        min_cluster_size: int = 1,
        k_neighbors: int = 50,
    ):
        """Initialize the FAISS clusterer.

        Args:
            similarity_threshold: Minimum cosine similarity to consider chunks related
            min_cluster_size: Minimum chunks per cluster (smaller clusters are dropped)
            k_neighbors: Number of neighbors to retrieve per query (trades recall vs speed)
        """
        if not FAISS_AVAILABLE:
            raise ImportError(
                "FAISS is required for FAISSClusterer. Install with: pip install faiss-cpu"
            )

        settings = get_settings()
        self.threshold = similarity_threshold or settings.similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.k_neighbors = k_neighbors
        self.embedding_generator = EmbeddingGenerator()

    async def cluster_chunks(
        self,
        chunks: list[ContentChunk],
    ) -> FAISSClusteringResult:
        """Cluster chunks using FAISS similarity search + Union-Find.

        Args:
            chunks: Content chunks with or without embeddings

        Returns:
            FAISSClusteringResult with knowledge clusters
        """
        if not chunks:
            return FAISSClusteringResult(
                clusters=[],
                total_chunks=0,
                num_clusters=0,
                dedup_ratio=0.0,
            )

        n = len(chunks)
        console.print(f"[blue]FAISS clustering {n} chunks (threshold={self.threshold})...[/blue]")

        # Ensure all chunks have embeddings
        await self.embedding_generator.generate_embeddings(chunks)

        # Stack and normalize embeddings
        embeddings = np.vstack([c.embedding for c in chunks]).astype(np.float32)
        faiss.normalize_L2(embeddings)

        # Build FAISS index
        d = embeddings.shape[1]  # Embedding dimension
        index = faiss.IndexFlatIP(d)  # Inner product (=cosine for normalized vectors)
        index.add(embeddings)

        # Search for k nearest neighbors for each embedding
        import time

        start = time.time()

        # Adjust k based on dataset size
        k = min(self.k_neighbors, n)

        # Batch search: similarities and indices for all vectors at once
        similarities, indices = index.search(embeddings, k)

        search_time_ms = (time.time() - start) * 1000
        console.print(f"  FAISS search completed in {search_time_ms:.1f}ms", style="dim")

        # Build clusters using Union-Find
        uf = UnionFind(n)

        # Union chunks that exceed threshold
        edges_added = 0
        for i in range(n):
            for j_idx in range(k):
                j = indices[i, j_idx]
                sim = similarities[i, j_idx]

                # Skip self-similarity and below-threshold pairs
                if j == i or sim < self.threshold:
                    continue

                if uf.union(i, j):
                    edges_added += 1

        console.print(f"  Created {edges_added} edges (above threshold)", style="dim")

        # Get groups from Union-Find
        groups = uf.get_groups()

        # Create KnowledgeCluster objects
        knowledge_clusters = []
        for root, member_indices in groups.items():
            if len(member_indices) >= self.min_cluster_size:
                cluster_chunks = [chunks[i] for i in member_indices]

                # Calculate average intra-cluster similarity
                cluster_sims = []
                for i in member_indices:
                    for j_idx in range(min(k, len(member_indices))):
                        j = indices[i, j_idx]
                        if j in member_indices and j != i:
                            cluster_sims.append(similarities[i, j_idx])

                avg_similarity = float(np.mean(cluster_sims)) if cluster_sims else 1.0

                cluster = KnowledgeCluster(
                    chunks=cluster_chunks,
                    similarity_score=avg_similarity,
                )

                # Assign cluster ID to chunks
                for chunk in cluster_chunks:
                    chunk.cluster_id = cluster.id

                knowledge_clusters.append(cluster)

        # Calculate statistics
        dedup_ratio = n / max(len(knowledge_clusters), 1)

        # Compute overall similarity stats from search results
        all_similarities = similarities[:, 1:].flatten()  # Exclude self-similarity
        valid_sims = all_similarities[all_similarities > 0]

        result = FAISSClusteringResult(
            clusters=knowledge_clusters,
            total_chunks=n,
            num_clusters=len(knowledge_clusters),
            dedup_ratio=dedup_ratio,
            similarity_stats={
                "mean": float(np.mean(valid_sims)) if len(valid_sims) > 0 else 0.0,
                "max": float(np.max(valid_sims)) if len(valid_sims) > 0 else 0.0,
                "threshold": self.threshold,
                "k_neighbors": self.k_neighbors,
            },
            faiss_search_time_ms=search_time_ms,
        )

        console.print(
            f"[green]Created {len(knowledge_clusters)} clusters "
            f"(dedup ratio: {dedup_ratio:.1f}:1)[/green]"
        )

        return result

    def merge_clusters(
        self,
        clusters: list[KnowledgeCluster],
        similarity_threshold: float = 0.90,
    ) -> list[KnowledgeCluster]:
        """Merge similar clusters using FAISS for efficient pairwise comparison.

        Args:
            clusters: Existing knowledge clusters to potentially merge
            similarity_threshold: Threshold for merging cluster representatives

        Returns:
            Merged list of knowledge clusters
        """
        if len(clusters) <= 1 or not FAISS_AVAILABLE:
            return clusters

        # Build cluster representative embeddings (mean of chunk embeddings)
        representatives = []
        valid_clusters = []

        for cluster in clusters:
            embeddings = [c.embedding for c in cluster.chunks if c.embedding is not None]
            if embeddings:
                avg = np.mean(embeddings, axis=0).astype(np.float32)
                representatives.append(avg)
                valid_clusters.append(cluster)

        if len(representatives) < 2:
            return clusters

        # Stack and normalize
        rep_matrix = np.vstack(representatives).astype(np.float32)
        faiss.normalize_L2(rep_matrix)

        # Build index and search
        d = rep_matrix.shape[1]
        index = faiss.IndexFlatIP(d)
        index.add(rep_matrix)

        n = len(valid_clusters)
        k = min(n, 20)  # Max 20 neighbors for cluster merging

        similarities, indices = index.search(rep_matrix, k)

        # Union-Find for transitive merging
        uf = UnionFind(n)

        for i in range(n):
            for j_idx in range(k):
                j = indices[i, j_idx]
                sim = similarities[i, j_idx]

                if j != i and sim >= similarity_threshold:
                    uf.union(i, j)

        # Build merged clusters
        groups = uf.get_groups()
        merged = []

        for root, member_indices in groups.items():
            if len(member_indices) == 1:
                merged.append(valid_clusters[member_indices[0]])
            else:
                # Merge all clusters in group
                combined_chunks = []
                for idx in member_indices:
                    combined_chunks.extend(valid_clusters[idx].chunks)

                merged_cluster = KnowledgeCluster(
                    chunks=combined_chunks,
                    topic=valid_clusters[member_indices[0]].topic,
                )
                merged.append(merged_cluster)

        console.print(
            f"[green]Merged {len(valid_clusters)} clusters into {len(merged)}[/green]"
        )

        return merged


def get_clusterer(use_faiss: bool = True) -> "FAISSClusterer | SemanticClusterer":
    """Factory function to get appropriate clusterer.

    Args:
        use_faiss: If True, use FAISS (recommended for large datasets).
                   Falls back to sklearn if FAISS not available.

    Returns:
        Clusterer instance (FAISSClusterer or SemanticClusterer)
    """
    if use_faiss and FAISS_AVAILABLE:
        return FAISSClusterer()
    else:
        from neurosynth.dedup.clustering import SemanticClusterer

        if use_faiss:
            console.print(
                "[yellow]FAISS not available, falling back to sklearn clustering[/yellow]"
            )
        return SemanticClusterer()
