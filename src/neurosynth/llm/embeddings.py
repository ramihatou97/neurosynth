"""
Unified embedding client for search and ingestion.

This module provides a unified interface for text embedding generation
across different models (Voyage, SBERT, etc.) to support both search-time
and ingestion-time embedding needs.
"""

from typing import Optional

from src.config import settings as app_settings
from src.neurosynth.llm.voyage import VoyageClient


class EmbeddingClient:
    """Wrapper for embedding generation with model selection.

    Provides a unified interface for text embeddings, automatically
    selecting the appropriate backend (Voyage, SBERT, etc.) based
    on the specified model name.
    """

    def __init__(self, model: str | None = None):
        """
        Initialize embedding client.

        Args:
            model: Embedding model name (e.g., "voyage-3-lite", "voyage-3",
                   "voyage-code-3", "SBERT"). If not specified, uses
                   settings.embedding_model.
        """
        self.model = model or app_settings.embedding_model

        # Initialize the appropriate backend
        # Currently only Voyage is supported, but this can be extended
        if self.model.startswith("voyage"):
            self.voyage_client = VoyageClient(model=self.model)
        else:
            # For other models (SBERT, etc.), use Voyage as fallback
            self.voyage_client = VoyageClient(model=app_settings.embedding_model)

    def embed(self, text: str) -> list[float]:
        """
        Synchronously embed a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        import asyncio

        result = asyncio.run(self.embed_async([text]))
        return result[0] if result else []

    async def embed_async(self, texts: list[str]) -> list[list[float]]:
        """
        Asynchronously embed multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = await self.voyage_client.embed_texts(texts)
        return [emb.tolist() for emb in embeddings]
