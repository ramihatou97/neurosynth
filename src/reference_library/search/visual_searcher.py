"""Visual similarity search using ColPali embeddings and Qdrant vector store."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from reference_library import config

# Visual search availability check
VISUAL_SEARCH_AVAILABLE = False
try:
    from ..utils.neurosynth_imports import (
        NEUROSYNTH_AVAILABLE,
        get_colpali_client,
        get_qdrant_store,
    )

    if NEUROSYNTH_AVAILABLE:
        VISUAL_SEARCH_AVAILABLE = True
except ImportError:
    pass


class VisualSearcher:
    """Manages visual embeddings and similarity search using ColPali and Qdrant."""

    def __init__(self, database, collection_name: str = None):
        """Initialize the visual searcher.

        Args:
            database: Database instance for tracking embeddings
            collection_name: Qdrant collection name (default from config)
        """
        self.database = database
        self.collection_name = collection_name or config.QDRANT_COLLECTION
        self.enabled = (
            VISUAL_SEARCH_AVAILABLE
            and config.VISUAL_SEARCH_ENABLED
            and config.COLPALI_ENABLED
        )

        self.colpali = None
        self.qdrant = None

        if self.enabled:
            self._init_resources()

    def _init_resources(self):
        """Initialize ColPali client and Qdrant store."""
        try:
            print("Initializing visual search resources...")

            # Get ColPali client (lazy loaded, may take time on first call)
            self.colpali = get_colpali_client()
            if not self.colpali:
                print("ColPali client not available")
                self.enabled = False
                return

            # Get Qdrant store
            self.qdrant = get_qdrant_store(self.collection_name)
            if not self.qdrant:
                print("Qdrant store not available")
                self.enabled = False
                return

            print("Visual search initialized successfully")

        except Exception as e:
            print(f"Failed to initialize visual search: {e}")
            self.enabled = False

    def embed_image(
        self, image_path: str, figure_id: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Generate embedding for a single image and store in Qdrant.

        Args:
            image_path: Path to the image file
            figure_id: Unique identifier for the figure
            metadata: Optional metadata to store with the embedding

        Returns:
            True if embedded successfully
        """
        if not self.enabled:
            return False

        # Check if already embedded
        if self.database.is_figure_embedded(figure_id):
            return True

        path = Path(image_path)
        if not path.exists():
            return False

        try:
            # Generate embedding using ColPali
            embedding = self.colpali.embed_image(path)

            # Prepare metadata
            store_metadata = {
                "figure_id": figure_id,
                "image_path": str(image_path),
            }
            if metadata:
                store_metadata.update(metadata)

            # Store in Qdrant
            self.qdrant.upsert(
                ids=[figure_id], embeddings=[embedding], metadatas=[store_metadata]
            )

            # Track in database (figure_id used as both element_id and point_id for Qdrant)
            self.database.track_visual_embedding(figure_id, figure_id, "colpali")
            return True

        except Exception as e:
            print(f"Error embedding image {figure_id}: {e}")
            return False

    def embed_images_batch(
        self,
        figures: list[dict[str, Any]],
        on_progress: callable | None = None,
        batch_size: int = 16,
    ) -> int:
        """Batch embed multiple images.

        Args:
            figures: List of figure dicts with id, image_path, pdf_path, page_number
            on_progress: Optional callback(current, total)
            batch_size: Number of images to process at once

        Returns:
            Number of images embedded
        """
        if not self.enabled:
            return 0

        embedded = 0
        total = len(figures)

        # Process in batches for efficiency
        for i in range(0, total, batch_size):
            batch = figures[i : i + batch_size]

            for fig in batch:
                figure_id = fig.get("id")
                image_path = fig.get("image_path")

                if not figure_id or not image_path:
                    continue

                # Skip if already embedded
                if self.database.is_figure_embedded(figure_id):
                    embedded += 1
                    continue

                # Prepare metadata
                metadata = {
                    "pdf_path": fig.get("pdf_path", ""),
                    "page_number": fig.get("page_number", 0),
                    "image_type": fig.get("image_type", "unknown"),
                    "caption": (fig.get("caption") or "")[:200],  # Truncate caption
                }

                if self.embed_image(image_path, figure_id, metadata):
                    embedded += 1

            if on_progress:
                on_progress(min(i + batch_size, total), total)

        return embedded

    def search_by_image(
        self,
        query_image_path: str,
        n_results: int = 20,
        image_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar images using visual similarity.

        Args:
            query_image_path: Path to the query image
            n_results: Maximum results to return
            image_types: Optional filter by image types

        Returns:
            List of dicts with: figure_id, image_path, pdf_path, page_number, score
        """
        if not self.enabled:
            return []

        path = Path(query_image_path)
        if not path.exists():
            return []

        try:
            # Generate query embedding
            query_embedding = self.colpali.embed_image(path)

            # Build filter if specified
            filter_dict = None
            if image_types:
                filter_dict = {"image_type": {"$in": image_types}}

            # Search Qdrant
            results = self.qdrant.search(
                query_embedding, limit=n_results, filter=filter_dict
            )

            # Transform results
            clean_results = []
            for result in results:
                clean_results.append(
                    {
                        "figure_id": result.id,
                        "image_path": result.payload.get("image_path", ""),
                        "pdf_path": Path(result.payload.get("pdf_path", "")),
                        "page_number": result.payload.get("page_number", 0),
                        "image_type": result.payload.get("image_type", "unknown"),
                        "caption": result.payload.get("caption", ""),
                        "score": result.score,
                    }
                )

            return clean_results

        except Exception as e:
            print(f"Visual search error: {e}")
            return []

    def search_by_text(
        self, query: str, n_results: int = 20, image_types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Search for images using text query (if ColPali supports text-to-image).

        Args:
            query: Text query
            n_results: Maximum results to return
            image_types: Optional filter by image types

        Returns:
            List of dicts with search results
        """
        if not self.enabled:
            return []

        try:
            # ColPali can embed text queries for cross-modal search
            if hasattr(self.colpali, "embed_text"):
                query_embedding = self.colpali.embed_text(query)
            else:
                # Fallback: use image embedding model on rendered text
                # This may not work well, return empty
                return []

            # Build filter
            filter_dict = None
            if image_types:
                filter_dict = {"image_type": {"$in": image_types}}

            # Search Qdrant
            results = self.qdrant.search(
                query_embedding, limit=n_results, filter=filter_dict
            )

            # Transform results
            clean_results = []
            for result in results:
                clean_results.append(
                    {
                        "figure_id": result.id,
                        "image_path": result.payload.get("image_path", ""),
                        "pdf_path": Path(result.payload.get("pdf_path", "")),
                        "page_number": result.payload.get("page_number", 0),
                        "image_type": result.payload.get("image_type", "unknown"),
                        "caption": result.payload.get("caption", ""),
                        "score": result.score,
                    }
                )

            return clean_results

        except Exception as e:
            print(f"Text-to-image search error: {e}")
            return []

    def get_embedding_count(self) -> int:
        """Get number of embedded images in Qdrant."""
        if not self.enabled or not self.qdrant:
            return 0
        try:
            return self.qdrant.count()
        except (RuntimeError, ConnectionError, AttributeError):
            # RuntimeError: Qdrant internal errors
            # ConnectionError: Qdrant connection issues
            # AttributeError: Qdrant not properly initialized
            return 0

    def clear_index(self):
        """Clear the visual index (for rebuilding)."""
        if not self.enabled or not self.qdrant:
            return

        try:
            self.qdrant.clear()
            print("Visual index cleared")
        except Exception as e:
            print(f"Error clearing visual index: {e}")


def get_visual_searcher(database, collection_name: str = None) -> VisualSearcher | None:
    """Factory function to get a VisualSearcher if available.

    Args:
        database: Database instance
        collection_name: Optional Qdrant collection name

    Returns:
        VisualSearcher instance or None if not available
    """
    if not VISUAL_SEARCH_AVAILABLE:
        return None

    try:
        searcher = VisualSearcher(database, collection_name)
        if searcher.enabled:
            return searcher
        return None
    except Exception:
        return None
