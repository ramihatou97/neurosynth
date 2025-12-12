"""
Qdrant Vector Store Service

Handles pushing embedded chunks and images to Qdrant for vector search.
Provides collection management and batch upsert operations.

Collections:
- neurosynth_chunks: Text chunks (VoyageAI 1024-dim)
- neurosurgical_figures_hybrid: Images (BiomedCLIP 512-dim)
"""

import hashlib
from typing import Optional

import structlog
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.config import settings
from src.models import Chunk, ExtractedImage, SourceMetadata

logger = structlog.get_logger(__name__)


class QdrantService:
    """
    Service for pushing chunks to Qdrant vector store.

    Features:
    - Lazy client initialization
    - Automatic collection creation
    - Batch upsert with proper payloads
    - Deterministic point IDs from chunk IDs
    """

    def __init__(
        self,
        url: str | None = None,
        collection_name: str | None = None,
        vector_dim: int | None = None,
    ):
        """
        Initialize Qdrant service.

        Args:
            url: Qdrant server URL (defaults to settings.qdrant_url)
            collection_name: Collection name for chunks (defaults to settings.qdrant_collection_name)
            vector_dim: Vector dimension for chunks (defaults to settings.qdrant_vector_dim)
        """
        self.url = url or settings.qdrant_url
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.vector_dim = vector_dim or settings.qdrant_vector_dim
        # Image collection settings
        self.image_collection_name = settings.image_qdrant_collection
        self.image_vector_dim = settings.image_qdrant_vector_dim
        self._client: QdrantClient | None = None
        self._image_collection_initialized = False

    @property
    def client(self) -> QdrantClient:
        """Lazy-load Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(url=self.url)
            self._ensure_collection()
        return self._client

    def _ensure_collection(self):
        """Create text chunk collection if it doesn't exist."""
        try:
            self._client.get_collection(self.collection_name)
            logger.debug("qdrant_collection_exists", name=self.collection_name)
        except (UnexpectedResponse, Exception):
            logger.info("creating_qdrant_collection", name=self.collection_name)
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_dim,
                    distance=models.Distance.COSINE,
                ),
            )

    def _ensure_image_collection(self):
        """Create image collection if it doesn't exist."""
        if self._image_collection_initialized:
            return

        try:
            self.client.get_collection(self.image_collection_name)
            logger.debug("image_collection_exists", name=self.image_collection_name)
        except (UnexpectedResponse, Exception):
            logger.info("creating_image_collection", name=self.image_collection_name)
            self.client.create_collection(
                collection_name=self.image_collection_name,
                vectors_config={
                    "biomed": models.VectorParams(
                        size=self.image_vector_dim,
                        distance=models.Distance.COSINE,
                    ),
                },
            )
        self._image_collection_initialized = True

    def push_chunks(
        self,
        chunks: list[Chunk],
        source: SourceMetadata,
    ) -> int:
        """
        Push embedded chunks to Qdrant.

        Args:
            chunks: Chunks with embeddings
            source: Source document metadata

        Returns:
            Number of points pushed
        """
        points = []

        for chunk in chunks:
            if chunk.embedding is None:
                continue

            # Generate deterministic point ID from chunk ID
            point_id = hashlib.md5(chunk.id.encode()).hexdigest()

            payload = {
                "text": chunk.content[:2000],  # Truncate for payload size
                "source_doc_id": chunk.source_id,
                "source_title": chunk.source_title,
                "section_title": chunk.section_title,
                "chunk_type": chunk.chunk_type.value,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "file_path": str(source.file_path),
                "specialty": source.specialty.value,
                "evidence_level": chunk.evidence_level,
                "parent_context": chunk.parent_context,
                "is_proposition": chunk.is_proposition,
                "original_chunk_id": chunk.id,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=chunk.embedding,
                    payload=payload,
                )
            )

        if not points:
            logger.warning("no_embedded_chunks_to_push", source=source.title)
            return 0

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        logger.info(
            "qdrant_push_complete",
            count=len(points),
            source=source.title,
            collection=self.collection_name,
        )
        return len(points)

    def push_images(
        self,
        images: list[ExtractedImage],
        source: SourceMetadata,
    ) -> int:
        """
        Push embedded images to Qdrant image collection.

        Uses BiomedCLIP embeddings (512-dim) for image similarity search.

        Args:
            images: ExtractedImage objects with embeddings
            source: Source document metadata

        Returns:
            Number of images pushed
        """
        # Filter images with valid embeddings
        valid_images = [
            img
            for img in images
            if img.embedding is not None and len(img.embedding) > 0
        ]

        if not valid_images:
            logger.debug("no_embedded_images_to_push", source=source.title)
            return 0

        # Ensure image collection exists
        self._ensure_image_collection()

        points = []
        for img in valid_images:
            # Generate deterministic point ID from image ID and source
            point_id = hashlib.md5(f"{source.id}:{img.id}".encode()).hexdigest()

            # Build payload with image metadata
            payload = {
                "filename": img.id,
                "source_pdf": source.id,
                "source_title": source.title,
                "page_num": img.page,
                "caption": img.caption or "",
                "context": img.surrounding_text or "",
                "image_type": img.image_type.value if img.image_type else "unknown",
                "path": str(img.file_path) if img.file_path else "",
                "modality": getattr(img, "modality", "unknown"),
                "detected_regions": getattr(img, "detected_regions", []),
                "region_confidence": getattr(img, "region_confidence", 0.0),
                "ocr_caption": getattr(img, "ocr_caption", ""),
                "caption_source": getattr(img, "caption_source", "proximity"),
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={"biomed": img.embedding},
                    payload=payload,
                )
            )

        # Upsert to image collection
        self.client.upsert(
            collection_name=self.image_collection_name,
            points=points,
        )

        logger.info(
            "qdrant_image_push_complete",
            count=len(points),
            source=source.title,
            collection=self.image_collection_name,
        )
        return len(points)

    def get_collection_info(self) -> dict:
        """Get text chunk collection statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_image_collection_info(self) -> dict:
        """Get image collection statistics."""
        try:
            info = self.client.get_collection(self.image_collection_name)
            return {
                "name": self.image_collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
            }
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """Close the Qdrant client."""
        if self._client:
            self._client.close()
            self._client = None
