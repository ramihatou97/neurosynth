"""Semantic clustering for deduplication."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from rich.console import Console
from sklearn.cluster import AgglomerativeClustering

from neurosynth.config import get_settings
from neurosynth.dedup.embeddings import EmbeddingGenerator
from neurosynth.models.document import ContentChunk
from neurosynth.models.knowledge import KnowledgeCluster

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement

console = Console()


@dataclass
class ClusteringResult:
    """Result of clustering operation."""

    clusters: list[KnowledgeCluster]
    total_chunks: int
    num_clusters: int
    dedup_ratio: float
    similarity_stats: dict[str, float] = field(default_factory=dict)


class SemanticClusterer:
    """Cluster semantically similar chunks."""

    def __init__(
        self,
        similarity_threshold: float | None = None,
        min_cluster_size: int = 1,
    ):
        settings = get_settings()
        self.threshold = similarity_threshold or settings.similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.embedding_generator = EmbeddingGenerator()

    async def cluster_chunks(
        self,
        chunks: list[ContentChunk],
    ) -> ClusteringResult:
        """Cluster chunks based on semantic similarity."""
        if not chunks:
            return ClusteringResult(
                clusters=[],
                total_chunks=0,
                num_clusters=0,
                dedup_ratio=0.0,
            )

        console.print(f"[blue]Clustering {len(chunks)} chunks...[/blue]")

        # Build similarity matrix
        similarity_matrix = await self.embedding_generator.build_similarity_matrix(
            chunks
        )

        # Convert to distance matrix (1 - similarity)
        distance_matrix = 1 - similarity_matrix

        # Perform hierarchical clustering
        if len(chunks) < 2:
            # Not enough chunks to cluster, return single cluster
            labels = np.zeros(len(chunks), dtype=int)
        else:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=1 - self.threshold,
                metric="precomputed",
                linkage="average",
            )
            labels = clustering.fit_predict(distance_matrix)

        # Group chunks by cluster label
        cluster_groups: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            if label not in cluster_groups:
                cluster_groups[label] = []
            cluster_groups[label].append(idx)

        # Create KnowledgeCluster objects
        knowledge_clusters = []
        for label, indices in cluster_groups.items():
            if len(indices) >= self.min_cluster_size:
                cluster_chunks = [chunks[i] for i in indices]

                # Calculate cluster statistics
                cluster_similarities = []
                for i in indices:
                    for j in indices:
                        if i < j:
                            cluster_similarities.append(similarity_matrix[i, j])

                avg_similarity = (
                    np.mean(cluster_similarities) if cluster_similarities else 1.0
                )

                # Assign cluster IDs to chunks
                cluster = KnowledgeCluster(
                    chunks=cluster_chunks,
                    similarity_score=float(avg_similarity),
                )

                for chunk in cluster_chunks:
                    chunk.cluster_id = cluster.id

                knowledge_clusters.append(cluster)

        # Calculate overall statistics
        dedup_ratio = len(chunks) / max(len(knowledge_clusters), 1)

        result = ClusteringResult(
            clusters=knowledge_clusters,
            total_chunks=len(chunks),
            num_clusters=len(knowledge_clusters),
            dedup_ratio=dedup_ratio,
            similarity_stats={
                "mean": float(np.mean(similarity_matrix)),
                "max": (
                    float(
                        np.max(
                            similarity_matrix[
                                np.triu_indices_from(similarity_matrix, 1)
                            ]
                        )
                    )
                    if len(chunks) > 1
                    else 1.0
                ),
                "threshold": self.threshold,
            },
        )

        console.print(
            f"[green]Created {len(knowledge_clusters)} clusters "
            f"(dedup ratio: {dedup_ratio:.1f}:1)[/green]"
        )

        return result

    async def find_similar_clusters(
        self,
        query_chunk: ContentChunk,
        clusters: list[KnowledgeCluster],
        top_k: int = 5,
    ) -> list[tuple[KnowledgeCluster, float]]:
        """Find clusters most similar to a query chunk.

        Optimized: pre-normalizes query embedding once.
        """
        if not query_chunk.embedding:
            await self.embedding_generator.generate_embeddings([query_chunk])

        if query_chunk.embedding is None:
            return []

        # Pre-normalize query embedding (compute norm once)
        query_norm = np.linalg.norm(query_chunk.embedding)
        if query_norm == 0:
            return []
        normalized_query = query_chunk.embedding / query_norm

        results = []

        for cluster in clusters:
            # Use first chunk's embedding as cluster representative
            if cluster.chunks and cluster.chunks[0].embedding is not None:
                rep_embedding = cluster.chunks[0].embedding
                rep_norm = np.linalg.norm(rep_embedding)

                if rep_norm > 0:
                    # Compute cosine similarity efficiently
                    similarity = float(
                        np.dot(normalized_query, rep_embedding) / rep_norm
                    )
                    results.append((cluster, similarity))

        # Sort by similarity
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def merge_clusters(
        self,
        clusters: list[KnowledgeCluster],
        similarity_threshold: float = 0.90,
    ) -> list[KnowledgeCluster]:
        """Merge highly similar clusters using vectorized similarity computation.

        Optimized implementation:
        - Pre-computes norms once instead of O(n²) times
        - Uses vectorized matrix operations via numpy
        - Uses union-find for efficient transitive merging
        """
        if len(clusters) <= 1:
            return clusters

        # Build cluster representative embeddings
        representatives = []
        valid_indices = []  # Track which clusters have valid embeddings

        for i, cluster in enumerate(clusters):
            if cluster.chunks:
                embeddings = [
                    c.embedding for c in cluster.chunks if c.embedding is not None
                ]
                if embeddings:
                    avg_embedding = np.mean(embeddings, axis=0)
                    representatives.append(avg_embedding)
                    valid_indices.append(i)

        if len(representatives) < 2:
            return clusters

        # Stack into matrix for vectorized operations
        rep_matrix = np.vstack(representatives)

        # Pre-compute norms ONCE (not O(n²) times)
        norms = np.linalg.norm(rep_matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-10, norms)  # Avoid division by zero

        # Normalize all representatives
        normalized = rep_matrix / norms

        # Compute full similarity matrix with single matrix multiplication
        # This is O(n²) but uses optimized BLAS operations
        similarity_matrix = normalized @ normalized.T

        # Find merge pairs above threshold (upper triangle only)
        n = len(valid_indices)
        merge_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i, j] >= similarity_threshold:
                    merge_pairs.append((valid_indices[i], valid_indices[j]))

        # Union-find for transitive merging
        parent = {i: i for i in range(len(clusters))}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])  # Path compression
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[py] = px

        # Union all pairs that should be merged
        for i, j in merge_pairs:
            union(i, j)

        # Group clusters by their root parent
        groups: dict[int, list[int]] = {}
        for i in range(len(clusters)):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)

        # Create merged clusters
        merged = []
        for root, indices in groups.items():
            if len(indices) == 1:
                merged.append(clusters[indices[0]])
            else:
                # Merge all clusters in group
                combined_chunks = []
                for idx in indices:
                    combined_chunks.extend(clusters[idx].chunks)

                merged_cluster = KnowledgeCluster(
                    chunks=combined_chunks,
                    topic=clusters[indices[0]].topic,
                )
                merged.append(merged_cluster)

        return merged


class TopicClusterer:
    """Cluster chunks by topic for better organization."""

    def __init__(self):
        self.semantic_clusterer = SemanticClusterer()

    async def cluster_by_topic(
        self,
        chunks: list[ContentChunk],
        topic_assignments: dict[str, str],
    ) -> dict[str, list[KnowledgeCluster]]:
        """Cluster chunks within each topic group."""
        # Group chunks by assigned topic
        topic_groups: dict[str, list[ContentChunk]] = {}

        for chunk in chunks:
            topic = topic_assignments.get(chunk.id, "general")
            if topic not in topic_groups:
                topic_groups[topic] = []
            topic_groups[topic].append(chunk)

        # Cluster within each topic
        results: dict[str, list[KnowledgeCluster]] = {}

        for topic, topic_chunks in topic_groups.items():
            if topic_chunks:
                result = await self.semantic_clusterer.cluster_chunks(topic_chunks)
                for cluster in result.clusters:
                    cluster.topic = topic
                results[topic] = result.clusters

        return results


class VisualAssociator:
    """Associate visual elements with text clusters.

    IMPORTANT: This class does NOT deduplicate images.
    The dual-system philosophy:
    - TEXT: Aggressive deduplication (via SemanticClusterer)
    - IMAGES: Comprehensive inclusion (associate ALL relevant images)

    This ensures every procedural/anatomical concept is visually represented,
    regardless of redundancy in the visual content.
    """

    # Priority ordering for image types (higher = more important)
    TYPE_PRIORITY = {
        "surgical_step": 100,
        "anatomical": 80,
        "imaging": 60,
        "table": 40,
        "flowchart": 30,
        "unknown": 10,
    }

    def __init__(
        self,
        similarity_threshold: float | None = None,
        visual_relevance_threshold: float = 0.3,
    ):
        """Initialize the visual associator.

        Args:
            similarity_threshold: Threshold for text clustering
            visual_relevance_threshold: Minimum relevance score for visual association
        """
        settings = get_settings()
        self.semantic_clusterer = SemanticClusterer(similarity_threshold)
        self.embedding_generator = EmbeddingGenerator()
        self.visual_relevance_threshold = visual_relevance_threshold
        self.include_all_visuals = settings.include_all_relevant_visuals

    async def cluster_with_visual_association(
        self,
        chunks: list[ContentChunk],
        all_visuals: list["VisualElement"] | None = None,
    ) -> ClusteringResult:
        """Cluster text chunks and associate relevant visuals.

        This method:
        1. Clusters text chunks using aggressive deduplication
        2. Associates ALL relevant images to each cluster (no image deduplication)

        Args:
            chunks: Text chunks to cluster
            all_visuals: Optional list of all visual elements to associate

        Returns:
            ClusteringResult with visually-enriched clusters
        """
        # Step 1: Text clustering (aggressive deduplication)
        result = await self.semantic_clusterer.cluster_chunks(chunks)

        # Step 2: Collect all visuals from chunks if not provided
        if all_visuals is None:
            all_visuals = self._collect_visuals_from_chunks(chunks)

        if not all_visuals:
            console.print("[dim]No visual elements to associate[/dim]")
            return result

        console.print(
            f"[blue]Associating {len(all_visuals)} visual elements "
            f"with {len(result.clusters)} clusters...[/blue]"
        )

        # Step 3: Associate visuals with each cluster
        for cluster in result.clusters:
            await self._associate_visuals_to_cluster(cluster, all_visuals, chunks)

        # Count total associated visuals
        total_associations = sum(len(c.visual_elements) for c in result.clusters)
        console.print(
            f"[green]Associated {total_associations} visual elements "
            f"across {len(result.clusters)} clusters[/green]"
        )

        return result

    def _collect_visuals_from_chunks(
        self,
        chunks: list[ContentChunk],
    ) -> list["VisualElement"]:
        """Collect all unique visual elements from chunks."""
        seen_ids: set[str] = set()
        visuals: list[VisualElement] = []

        for chunk in chunks:
            for visual in chunk.visual_elements:
                if visual.id not in seen_ids:
                    seen_ids.add(visual.id)
                    visuals.append(visual)

        return visuals

    async def _associate_visuals_to_cluster(
        self,
        cluster: KnowledgeCluster,
        all_visuals: list["VisualElement"],
        all_chunks: list[ContentChunk],
    ) -> None:
        """Associate relevant visuals to a cluster.

        Association criteria (in order of importance):
        1. Direct attachment: Visual already attached to a chunk in the cluster
        2. Source matching: Visual from same PDF as cluster chunks
        3. Page proximity: Visual on pages referenced by cluster chunks
        4. Semantic relevance: Caption/context matches cluster content
        """

        associated: list[VisualElement] = []
        seen_ids: set[str] = set()

        # Get cluster context
        cluster_sources = self._get_cluster_sources(cluster)
        cluster_pages = self._get_cluster_pages(cluster)
        cluster_text = self._get_cluster_text(cluster)

        for visual in all_visuals:
            if visual.id in seen_ids:
                continue

            relevance_score = 0.0

            # Criterion 1: Already attached to cluster chunk
            if any(visual in chunk.visual_elements for chunk in cluster.chunks):
                relevance_score = 1.0

            # Criterion 2: Same source PDF
            elif visual.source_pdf and str(visual.source_pdf) in cluster_sources:
                relevance_score = 0.7

                # Criterion 3: Page proximity bonus
                if visual.page_number and visual.page_number in cluster_pages:
                    relevance_score = 0.9

            # Criterion 4: Semantic relevance (caption/context match)
            if relevance_score < 0.5:
                text_score = self._compute_text_relevance(visual, cluster_text)
                relevance_score = max(relevance_score, text_score)

            # Include if meets threshold OR if we want comprehensive coverage
            if (
                relevance_score >= self.visual_relevance_threshold
                or self.include_all_visuals
            ):
                # For comprehensive mode, still require some relevance
                if self.include_all_visuals and relevance_score < 0.1:
                    continue

                seen_ids.add(visual.id)
                visual.relevance_score = relevance_score
                associated.append(visual)

        # Sort by type priority then relevance
        associated.sort(
            key=lambda v: (
                -self.TYPE_PRIORITY.get(v.image_type.value, 0),
                -v.relevance_score,
            )
        )

        cluster.visual_elements = associated

    def _get_cluster_sources(self, cluster: KnowledgeCluster) -> set[str]:
        """Get all source PDFs referenced by cluster chunks."""
        sources: set[str] = set()
        for chunk in cluster.chunks:
            if chunk.source and chunk.source.path:
                sources.add(str(chunk.source.path))
        return sources

    def _get_cluster_pages(self, cluster: KnowledgeCluster) -> set[int]:
        """Get all page numbers referenced by cluster chunks."""
        pages: set[int] = set()
        for chunk in cluster.chunks:
            if chunk.page_start:
                pages.add(chunk.page_start)
            if chunk.page_end:
                pages.add(chunk.page_end)
            # Add surrounding pages for context
            if chunk.page_start:
                pages.update(range(max(1, chunk.page_start - 1), chunk.page_start + 2))
        return pages

    def _get_cluster_text(self, cluster: KnowledgeCluster) -> str:
        """Get combined text content of cluster for semantic matching."""
        texts = []
        for chunk in cluster.chunks[:5]:  # Limit to first 5 chunks for efficiency
            if chunk.content:
                texts.append(chunk.content[:500])
        return " ".join(texts).lower()

    def _compute_text_relevance(
        self,
        visual: "VisualElement",
        cluster_text: str,
    ) -> float:
        """Compute text-based relevance between visual and cluster.

        Uses simple keyword overlap for efficiency.
        For more sophisticated matching, embeddings could be used.
        """
        if not cluster_text:
            return 0.0

        # Combine caption and context
        visual_text = ""
        if visual.caption:
            visual_text += visual.caption.lower() + " "
        if visual.context_text:
            visual_text += visual.context_text.lower()

        if not visual_text.strip():
            return 0.0

        # Extract significant words (length > 3, not common)
        common_words = {"the", "and", "for", "with", "from", "this", "that", "which"}
        visual_words = {
            w for w in visual_text.split() if len(w) > 3 and w not in common_words
        }
        cluster_words = {
            w for w in cluster_text.split() if len(w) > 3 and w not in common_words
        }

        if not visual_words or not cluster_words:
            return 0.0

        # Jaccard-like overlap
        overlap = len(visual_words & cluster_words)
        union = len(visual_words | cluster_words)

        return overlap / union if union > 0 else 0.0

    async def associate_visuals_to_existing_clusters(
        self,
        clusters: list[KnowledgeCluster],
        visuals: list["VisualElement"],
    ) -> list[KnowledgeCluster]:
        """Associate visuals to pre-existing clusters.

        Use this when clusters have already been created and you
        want to add visual associations afterwards.

        Args:
            clusters: Existing knowledge clusters
            visuals: Visual elements to associate

        Returns:
            Same clusters with visual_elements populated
        """
        if not visuals:
            return clusters

        # Collect all chunks from clusters for context
        all_chunks = []
        for cluster in clusters:
            all_chunks.extend(cluster.chunks)

        console.print(
            f"[blue]Associating {len(visuals)} visuals to "
            f"{len(clusters)} existing clusters...[/blue]"
        )

        for cluster in clusters:
            await self._associate_visuals_to_cluster(cluster, visuals, all_chunks)

        return clusters

    def get_visuals_for_inline_display(
        self,
        cluster: KnowledgeCluster,
        max_inline: int = 3,
    ) -> list["VisualElement"]:
        """Get high-priority visuals for inline display within text.

        Selects the most relevant surgical steps and anatomical images
        for display alongside the synthesized text.

        Args:
            cluster: The knowledge cluster
            max_inline: Maximum number of inline figures

        Returns:
            List of visuals suitable for inline display
        """
        if not cluster.visual_elements:
            return []

        # Prioritize surgical steps and high-confidence anatomical
        inline_candidates = [
            v
            for v in cluster.visual_elements
            if v.image_type.value in ("surgical_step", "anatomical")
            and v.type_confidence >= 0.5
        ]

        # Sort by type priority and relevance
        inline_candidates.sort(
            key=lambda v: (
                -self.TYPE_PRIORITY.get(v.image_type.value, 0),
                -v.type_confidence,
                -v.relevance_score,
            )
        )

        return inline_candidates[:max_inline]

    def get_visuals_for_plate(
        self,
        cluster: KnowledgeCluster,
    ) -> list["VisualElement"]:
        """Get all visuals for figure plate at end of section.

        Returns all associated visuals not selected for inline display,
        organized by type for a comprehensive figure plate.

        Args:
            cluster: The knowledge cluster

        Returns:
            List of visuals for the figure plate
        """
        if not cluster.visual_elements:
            return []

        # Return all visuals sorted by type
        return sorted(
            cluster.visual_elements,
            key=lambda v: (
                -self.TYPE_PRIORITY.get(v.image_type.value, 0),
                v.page_number or 0,
            ),
        )
