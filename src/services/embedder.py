"""
Async Text Embedding Service

Wraps VoyageAI embedding API with batch processing and chunk integration.
Designed for use in BatchIndexer to generate embeddings before storage.
"""

from typing import Optional

import structlog

from src.models import Chunk

logger = structlog.get_logger(__name__)

EMBEDDING_BATCH_SIZE = 128  # Voyage API limit per request


class AsyncEmbedder:
    """
    Async text embedding service using VoyageAI.

    Features:
    - Batch processing (128 texts per API call)
    - Connection pooling via httpx.AsyncClient
    - Automatic retry with exponential backoff
    - Lazy client initialization (defers API key validation)
    """

    def __init__(self, voyage_api_key: str | None = None):
        """
        Initialize embedder.

        Args:
            voyage_api_key: Optional Voyage API key (defaults to settings/env)
        """
        self._voyage_key = voyage_api_key
        self._client = None  # Lazy-loaded

    async def _get_client(self):
        """Lazy-load the AsyncAIClient to avoid API key check at init."""
        if self._client is None:
            from src.ai.client import AsyncAIClient

            self._client = AsyncAIClient(voyage_api_key=self._voyage_key)
        return self._client

    async def embed_chunks(
        self,
        chunks: list[Chunk],
        show_progress: bool = False,
    ) -> list[Chunk]:
        """
        Generate embeddings for chunks in batches.

        Modifies chunks in-place, setting the `embedding` field.

        Args:
            chunks: List of Chunk objects to embed
            show_progress: Whether to log detailed progress

        Returns:
            Same list of chunks with embeddings populated
        """
        if not chunks:
            return chunks

        client = await self._get_client()
        texts = [c.content for c in chunks]

        logger.info(
            "embedding_chunks_start",
            count=len(chunks),
            batch_size=EMBEDDING_BATCH_SIZE,
        )

        # get_embeddings handles batching internally (128 per API call)
        embeddings = await client.get_embeddings(texts)

        # Assign embeddings to chunks
        embedded_count = 0
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                chunk.embedding = embedding
                embedded_count += 1

        logger.info(
            "embedding_chunks_complete",
            embedded=embedded_count,
            total=len(chunks),
        )

        return chunks

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Raw text embedding without Chunk objects.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        client = await self._get_client()
        return await client.get_embeddings(texts)

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures client is closed."""
        await self.close()
