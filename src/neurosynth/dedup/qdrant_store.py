"""Qdrant vector store for visual embeddings.

Provides persistent storage and similarity search for visual content
extracted from neurosurgical reference documents. Uses embedded Qdrant
for local operation without external dependencies.
"""

import asyncio
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from rich.console import Console

from neurosynth import get_logger
from neurosynth.config import get_settings

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement

console = Console()
logger = get_logger("dedup.qdrant_store")


class QdrantVisualStore:
    """Persistent vector store for visual embeddings using Qdrant.

    Uses singleton pattern for connection management.
    Stores embeddings locally using embedded Qdrant.
    """

    _instance: "QdrantVisualStore | None" = None
    _client = None
    _initialized: bool = False

    def __new__(cls) -> "QdrantVisualStore":
        """Singleton pattern for Qdrant connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the Qdrant store."""
        if QdrantVisualStore._initialized:
            return

        self.settings = get_settings()
        self.storage_path = self.settings.qdrant_path
        self.collection_name = self.settings.qdrant_collection_name

        # Ensure storage directory exists (only if path is set)
        if self.storage_path:
            try:
                self.storage_path.mkdir(parents=True, exist_ok=True)
            except AttributeError:
                # Handle case where path might be misconfigured as NoneType despite checks
                pass

        QdrantVisualStore._initialized = True

    def _ensure_client(self) -> None:
        """Ensure Qdrant client is initialized."""
        if QdrantVisualStore._client is not None:
            return

        try:
            from qdrant_client import QdrantClient

            # Initialize embedded Qdrant client (local storage)
            QdrantVisualStore._client = QdrantClient(path=str(self.storage_path))
            console.print(f"[dim]Qdrant store initialized at {self.storage_path}[/dim]")

        except ImportError:
            raise RuntimeError(
                "Qdrant client not installed. Install with: pip install qdrant-client"
            )

    @property
    def client(self):
        """Get the Qdrant client, initializing if necessary."""
        self._ensure_client()
        return QdrantVisualStore._client

    def _ensure_collection(self, vector_size: int = 128) -> None:
        """Ensure collection exists with correct configuration.

        Args:
            vector_size: Dimension of the embedding vectors
        """
        from qdrant_client.models import Distance, VectorParams

        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            console.print(
                f"[dim]Created Qdrant collection: {self.collection_name}[/dim]"
            )

    async def store_visual_elements(
        self,
        elements: list["VisualElement"],
    ) -> int:
        """Store visual elements with their embeddings.

        Args:
            elements: List of VisualElement objects with embeddings

        Returns:
            Number of elements stored
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._store_sync(elements))

    def _store_sync(self, elements: list["VisualElement"]) -> int:
        """Synchronous storage implementation."""
        from qdrant_client.models import PointStruct

        # Filter elements with embeddings
        to_store = [e for e in elements if e.visual_embedding is not None]

        if not to_store:
            return 0

        # Ensure collection exists with correct vector size
        first_embedding = to_store[0].visual_embedding
        if first_embedding is None:  # Should not happen after filter, but satisfy mypy
            return 0
        vector_size = len(first_embedding)
        self._ensure_collection(vector_size)

        # Create points
        points = []
        for element in to_store:
            point_id = str(uuid.uuid4())

            if element.visual_embedding is None:
                logger.warning(f"Skipping element {element.id} with no embedding")
                continue

            point = PointStruct(
                id=point_id,
                vector=element.visual_embedding.tolist(),
                payload={
                    "element_id": element.id,
                    "image_path": (
                        str(element.image_path) if element.image_path else None
                    ),
                    "source_pdf": (
                        str(element.source_pdf) if element.source_pdf else None
                    ),
                    "page_number": element.page_number,
                    "caption": element.caption[:500] if element.caption else "",
                    "image_type": element.image_type.value,
                    "type_confidence": element.type_confidence,
                    "visual_hash": element.visual_hash,
                    "width": element.width,
                    "height": element.height,
                    "embedding_model": element.embedding_model,
                },
            )
            points.append(point)

        # Upsert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        console.print(f"[dim]Stored {len(points)} visual embeddings in Qdrant[/dim]")
        return len(points)

    async def search_similar(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        score_threshold: float = 0.0,
        image_type_filter: str | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        """Search for similar visual elements.

        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of results
            score_threshold: Minimum similarity score
            image_type_filter: Filter by image type (e.g., "surgical_step")

        Returns:
            List of (payload, similarity_score) tuples
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._search_sync(
                query_embedding, top_k, score_threshold, image_type_filter
            ),
        )

    def _search_sync(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        score_threshold: float,
        image_type_filter: str | None,
    ) -> list[tuple[dict[str, Any], float]]:
        """Synchronous search implementation."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        # Build filter if needed
        query_filter = None
        if image_type_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="image_type",
                        match=MatchValue(value=image_type_filter),
                    )
                ]
            )

        try:
            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )

            return [(hit.payload, hit.score) for hit in results]
        except Exception as e:
            console.print(f"[yellow]Warning: Qdrant search failed: {e}[/yellow]")
            return []

    async def search_by_text_context(
        self,
        text: str,
        top_k: int = 10,
        image_type_filter: str | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        """Search for images relevant to given text context.

        This uses the caption and context_text fields stored in the payload,
        not embedding-based search. For embedding search, use search_similar().

        Args:
            text: Text to match against captions/context
            top_k: Maximum number of results
            image_type_filter: Filter by image type

        Returns:
            List of (payload, relevance_score) tuples
        """
        # This is a simple text-based search using Qdrant's scroll
        # For production, consider adding text embeddings or full-text search
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._search_by_text_sync(text, top_k, image_type_filter),
        )

    def _search_by_text_sync(
        self,
        text: str,
        top_k: int,
        image_type_filter: str | None,
    ) -> list[tuple[dict[str, Any], float]]:
        """Simple text-based search through captions."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if image_type_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="image_type",
                        match=MatchValue(value=image_type_filter),
                    )
                ]
            )

        try:
            # Scroll through all points (for small collections)
            # For larger collections, consider using full-text search
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,  # Adjust based on collection size
                scroll_filter=query_filter,
                with_payload=True,
            )

            # Simple keyword matching in caption
            text_lower = text.lower()
            keywords = set(text_lower.split())

            scored_results = []
            for point in results:
                payload = point.payload
                caption = (payload.get("caption") or "").lower()

                # Calculate simple relevance score
                caption_words = set(caption.split())
                overlap = len(keywords & caption_words)
                if overlap > 0:
                    score = overlap / len(keywords)
                    scored_results.append((payload, score))

            # Sort by score and return top-k
            scored_results.sort(key=lambda x: x[1], reverse=True)
            return scored_results[:top_k]

        except Exception as e:
            console.print(f"[yellow]Warning: Text search failed: {e}[/yellow]")
            return []

    async def find_duplicates(
        self,
        elements: list["VisualElement"],
        threshold: float = 0.95,
    ) -> list[tuple[str, str, float]]:
        """Find duplicate images based on visual similarity.

        Args:
            elements: List of VisualElement objects with embeddings
            threshold: Minimum similarity to consider duplicate

        Returns:
            List of (element_id_1, element_id_2, similarity) tuples
        """
        duplicates: list[tuple[str, str, float]] = []

        for element in elements:
            if element.visual_embedding is None:
                continue

            # Search for similar
            similar = await self.search_similar(
                element.visual_embedding,
                top_k=5,
                score_threshold=threshold,
            )

            for payload, score in similar:
                other_id = payload.get("element_id")
                if other_id and other_id != element.id:
                    # Avoid duplicate pairs
                    pair = tuple(sorted([element.id, other_id]))
                    dup_entry = (pair[0], pair[1], score)
                    if dup_entry not in duplicates:
                        duplicates.append(dup_entry)

        return duplicates

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status.value if info.status else "unknown",
                "collection_name": self.collection_name,
                "storage_path": str(self.storage_path),
            }
        except Exception:
            return {
                "points_count": 0,
                "status": "not_created",
                "collection_name": self.collection_name,
                "storage_path": str(self.storage_path),
            }

    def clear_collection(self) -> None:
        """Clear all data from collection."""
        try:
            self.client.delete_collection(self.collection_name)
            console.print(f"[dim]Cleared collection: {self.collection_name}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not clear collection: {e}[/yellow]")

    async def get_all_by_source(
        self,
        source_pdf: Path | str,
    ) -> list[dict[str, Any]]:
        """Get all visual elements from a specific source PDF.

        Args:
            source_pdf: Path to the source PDF

        Returns:
            List of payloads for matching elements
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._get_by_source_sync(str(source_pdf))
        )

    def _get_by_source_sync(self, source_pdf: str) -> list[dict[str, Any]]:
        """Synchronous source-based retrieval."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="source_pdf",
                    match=MatchValue(value=source_pdf),
                )
            ]
        )

        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                scroll_filter=query_filter,
                with_payload=True,
            )
            return [point.payload for point in results]
        except Exception:
            return []

    async def get_by_type(
        self,
        image_type: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all visual elements of a specific type.

        Args:
            image_type: Type to filter by (e.g., "surgical_step")
            limit: Maximum number of results

        Returns:
            List of payloads for matching elements
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._get_by_type_sync(image_type, limit)
        )

    def _get_by_type_sync(self, image_type: str, limit: int) -> list[dict[str, Any]]:
        """Synchronous type-based retrieval."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="image_type",
                    match=MatchValue(value=image_type),
                )
            ]
        )

        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                scroll_filter=query_filter,
                with_payload=True,
            )
            return [point.payload for point in results]
        except Exception:
            return []


def get_qdrant_store() -> QdrantVisualStore:
    """Get the global Qdrant store instance.

    Returns:
        QdrantVisualStore singleton instance
    """
    return QdrantVisualStore()
