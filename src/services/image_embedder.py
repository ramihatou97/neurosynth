"""
Async Image Embedding Service

Wraps BiomedCLIP for image embedding with batch processing.
Designed for use in BatchIndexer to generate embeddings before Qdrant push.

BiomedCLIP produces 512-dim embeddings optimized for biomedical images,
enabling text-to-image search via shared embedding space.
"""

import asyncio
from pathlib import Path
from typing import Optional

import structlog

from src.config import settings
from src.models import ExtractedImage

logger = structlog.get_logger(__name__)


class AsyncImageEmbedder:
    """
    Async image embedding service using BiomedCLIP.

    Features:
    - Batch processing (configurable batch size, default 32)
    - GPU-optimized (MPS/CUDA/CPU auto-detection)
    - Lazy model loading (defers heavy initialization)
    - Graceful fallback if BiomedCLIP unavailable
    """

    SUPPORTED_MODELS = ["biomedclip", "none"]

    def __init__(self, model: str | None = None):
        """
        Initialize image embedder.

        Args:
            model: Embedding model to use. Options:
                   - "biomedclip": BiomedCLIP 512-dim (default)
                   - "none": Disable image embedding
        """
        self._model_name = model or self._get_default_model()
        self._embedder = None  # Lazy-loaded
        self._load_attempted = False
        self._load_error: str | None = None

    def _get_default_model(self) -> str:
        """Determine default model from settings."""
        # Map settings.image_embedding_model to our supported models
        setting_model = settings.image_embedding_model.lower()
        if setting_model in ("none", ""):
            return "none"
        # Both colpali and clip map to biomedclip for Qdrant search
        # (ColPali is for local storage, BiomedCLIP for Qdrant)
        return "biomedclip"

    def _get_embedder(self):
        """Lazy-load the BiomedCLIP embedder."""
        if self._embedder is not None:
            return self._embedder

        if self._load_attempted:
            # Already tried and failed
            return None

        self._load_attempted = True

        try:
            from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

            logger.info("loading_biomedclip", model="BiomedCLIP-PubMedBERT")
            self._embedder = BiomedCLIPSearcher()
            logger.info(
                "biomedclip_loaded",
                device=self._embedder.device,
                model="BiomedCLIP-PubMedBERT",
            )
            return self._embedder

        except ImportError as e:
            self._load_error = f"BiomedCLIP not available: {e}"
            logger.warning("biomedclip_import_error", error=str(e))
            return None

        except Exception as e:
            self._load_error = f"BiomedCLIP load failed: {e}"
            logger.error("biomedclip_load_error", error=str(e))
            return None

    @property
    def is_available(self) -> bool:
        """Check if image embedding is available."""
        if self._model_name == "none":
            return False
        return self._get_embedder() is not None

    async def embed_images(
        self,
        images: list[ExtractedImage],
        batch_size: int | None = None,
        show_progress: bool = False,
    ) -> list[ExtractedImage]:
        """
        Generate embeddings for images in batches.

        Modifies images in-place, setting the `embedding` field.

        Args:
            images: List of ExtractedImage objects to embed
            batch_size: Number of images per batch (default from settings)
            show_progress: Whether to log detailed progress

        Returns:
            Same list of images with embeddings populated
        """
        if not images:
            return images

        if self._model_name == "none":
            logger.info("image_embedding_disabled", reason="model=none")
            return images

        # Filter images that need embedding and have valid paths
        to_embed = [
            img
            for img in images
            if img.embedding is None
            and img.file_path is not None
            and Path(img.file_path).exists()
        ]

        if not to_embed:
            logger.debug("no_images_need_embedding", total=len(images))
            return images

        # Get embedder
        embedder = self._get_embedder()
        if embedder is None:
            logger.warning(
                "image_embedding_skipped",
                reason=self._load_error or "embedder not available",
                count=len(to_embed),
            )
            return images

        batch_size = batch_size or settings.image_embedding_batch_size

        logger.info(
            "embedding_images_start",
            count=len(to_embed),
            batch_size=batch_size,
            model=self._model_name,
        )

        # Process in batches (GPU memory management)
        loop = asyncio.get_event_loop()
        embedded_count = 0

        for i in range(0, len(to_embed), batch_size):
            batch = to_embed[i : i + batch_size]
            batch_paths = [str(img.file_path) for img in batch]

            try:
                # Run embedding in executor (BiomedCLIP is sync/GPU-bound)
                embeddings = await loop.run_in_executor(
                    None,
                    embedder.embed_image,
                    batch_paths,
                )

                # Assign embeddings to images
                for img, embedding in zip(batch, embeddings):
                    if embedding is not None and len(embedding) > 0:
                        # Convert to list if numpy array
                        if hasattr(embedding, "tolist"):
                            img.embedding = embedding.tolist()
                        else:
                            img.embedding = list(embedding)
                        embedded_count += 1

                if show_progress:
                    logger.debug(
                        "embedding_batch_complete",
                        batch=i // batch_size + 1,
                        embedded=embedded_count,
                    )

            except Exception as e:
                logger.error(
                    "embedding_batch_failed",
                    batch=i // batch_size + 1,
                    error=str(e),
                )
                # Continue with next batch

        logger.info(
            "embedding_images_complete",
            embedded=embedded_count,
            total=len(to_embed),
            skipped=len(to_embed) - embedded_count,
        )

        return images

    async def embed_paths(
        self,
        image_paths: list[Path],
        batch_size: int | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for image paths directly.

        Useful for search queries or non-ExtractedImage use cases.

        Args:
            image_paths: List of paths to image files
            batch_size: Number of images per batch

        Returns:
            List of embedding vectors (512-dim each)
        """
        if not image_paths:
            return []

        if self._model_name == "none":
            return []

        embedder = self._get_embedder()
        if embedder is None:
            return []

        batch_size = batch_size or settings.image_embedding_batch_size
        loop = asyncio.get_event_loop()
        all_embeddings = []

        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i : i + batch_size]
            batch_paths = [str(p) for p in batch]

            try:
                embeddings = await loop.run_in_executor(
                    None,
                    embedder.embed_image,
                    batch_paths,
                )

                for emb in embeddings:
                    if emb is not None and len(emb) > 0:
                        if hasattr(emb, "tolist"):
                            all_embeddings.append(emb.tolist())
                        else:
                            all_embeddings.append(list(emb))
                    else:
                        all_embeddings.append([])

            except Exception as e:
                logger.error("embed_paths_batch_failed", error=str(e))
                # Return empty embeddings for failed batch
                all_embeddings.extend([[]] * len(batch))

        return all_embeddings
