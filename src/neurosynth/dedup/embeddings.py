"""Embedding generation for semantic similarity."""

import numpy as np
from rich.console import Console

from neurosynth.llm.voyage import VoyageClient, embedding_cache
from neurosynth.models.document import ContentChunk

console = Console()


class EmbeddingGenerator:
    """Generate and manage embeddings for content chunks."""

    def __init__(self, use_cache: bool = True):
        self.client = VoyageClient()
        self.use_cache = use_cache

    async def generate_embeddings(
        self,
        chunks: list[ContentChunk],
        show_progress: bool = True,
    ) -> list[ContentChunk]:
        """Generate embeddings for all chunks."""
        # Separate cached and uncached chunks
        uncached_chunks = []
        uncached_indices = []

        for i, chunk in enumerate(chunks):
            if self.use_cache:
                cached = embedding_cache.get(chunk.content_hash)
                if cached is not None:
                    chunk.embedding = cached
                    continue

            uncached_chunks.append(chunk)
            uncached_indices.append(i)

        if not uncached_chunks:
            console.print(
                f"[green]All {len(chunks)} embeddings loaded from cache[/green]"
            )
            return chunks

        # Generate embeddings for uncached chunks
        texts = [c.content for c in uncached_chunks]

        if show_progress:
            console.print(
                f"[blue]Generating embeddings for {len(texts)} chunks...[/blue]"
            )

        embeddings = await self.client.embed_texts(texts)

        # Assign embeddings and cache
        for chunk, embedding in zip(uncached_chunks, embeddings, strict=False):
            chunk.embedding = embedding
            if self.use_cache:
                embedding_cache.set(chunk.content_hash, embedding)

        console.print(
            f"[green]Generated {len(embeddings)} new embeddings "
            f"(cache size: {embedding_cache.size})[/green]"
        )

        return chunks

    async def compute_similarity(
        self,
        chunk1: ContentChunk,
        chunk2: ContentChunk,
    ) -> float:
        """Compute similarity between two chunks."""
        if chunk1.embedding is None:
            await self.generate_embeddings([chunk1])
        if chunk2.embedding is None:
            await self.generate_embeddings([chunk2])

        return float(
            np.dot(chunk1.embedding, chunk2.embedding)
            / (np.linalg.norm(chunk1.embedding) * np.linalg.norm(chunk2.embedding))
        )

    async def build_similarity_matrix(
        self,
        chunks: list[ContentChunk],
    ) -> np.ndarray:
        """Build pairwise similarity matrix for chunks."""
        # Ensure all chunks have embeddings
        await self.generate_embeddings(chunks, show_progress=True)

        # Stack embeddings
        embeddings = np.vstack([c.embedding for c in chunks])

        # Normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / norms

        # Compute similarity matrix
        similarity_matrix = np.dot(normalized, normalized.T)

        return similarity_matrix

    async def find_duplicates(
        self,
        chunks: list[ContentChunk],
        threshold: float = 0.95,
    ) -> list[tuple[int, int, float]]:
        """Find near-duplicate chunks."""
        matrix = await self.build_similarity_matrix(chunks)

        duplicates = []
        n = len(chunks)

        for i in range(n):
            for j in range(i + 1, n):
                sim = matrix[i, j]
                if sim >= threshold:
                    duplicates.append((i, j, float(sim)))

        return sorted(duplicates, key=lambda x: -x[2])


class ExactDeduplicator:
    """Remove exact duplicates using content hashing."""

    @staticmethod
    def deduplicate(chunks: list[ContentChunk]) -> list[ContentChunk]:
        """Remove exact duplicate chunks based on content hash."""
        seen_hashes = set()
        unique_chunks = []

        for chunk in chunks:
            if chunk.content_hash not in seen_hashes:
                seen_hashes.add(chunk.content_hash)
                unique_chunks.append(chunk)

        removed = len(chunks) - len(unique_chunks)
        if removed > 0:
            console.print(f"[yellow]Removed {removed} exact duplicates[/yellow]")

        return unique_chunks

    @staticmethod
    def find_exact_duplicates(
        chunks: list[ContentChunk],
    ) -> dict[str, list[ContentChunk]]:
        """Group chunks by content hash to find duplicates."""
        groups: dict[str, list[ContentChunk]] = {}

        for chunk in chunks:
            if chunk.content_hash not in groups:
                groups[chunk.content_hash] = []
            groups[chunk.content_hash].append(chunk)

        # Return only groups with duplicates
        return {h: g for h, g in groups.items() if len(g) > 1}
