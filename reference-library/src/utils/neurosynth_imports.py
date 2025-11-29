"""Bridge for importing NeuroSynth modules into Reference Library.

This module provides access to NeuroSynth's image processing pipeline
without code duplication. It handles path setup and provides wrapper
classes that integrate with Reference Library's configuration.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Add NeuroSynth source to Python path
_neurosynth_src = Path(__file__).parent.parent.parent.parent / "src"
if str(_neurosynth_src) not in sys.path:
    sys.path.insert(0, str(_neurosynth_src))

# Import NeuroSynth modules
try:
    from neurosynth.parsers.image_extractor import ImageExtractor as _BaseImageExtractor
    from neurosynth.models.visual import (
        VisualElement,
        ImageType,
        VisualIndex,
        FigurePlate,
    )
    NEUROSYNTH_AVAILABLE = True
except ImportError as e:
    NEUROSYNTH_AVAILABLE = False
    _import_error = str(e)

    # Create placeholder classes for type hints
    class VisualElement:  # type: ignore
        pass

    class ImageType:  # type: ignore
        pass

    class VisualIndex:  # type: ignore
        pass

    class FigurePlate:  # type: ignore
        pass


# Re-export for convenience
__all__ = [
    "NEUROSYNTH_AVAILABLE",
    "VisualElement",
    "ImageType",
    "VisualIndex",
    "FigurePlate",
    "ImageExtractor",
    "get_image_extractor",
]


@dataclass
class ImageExtractorConfig:
    """Configuration for image extraction."""
    min_image_size: int = 100
    max_image_size: int = 2048


class ImageExtractor:
    """Wrapper around NeuroSynth's ImageExtractor with Reference Library config.

    This wrapper:
    - Uses Reference Library's configuration instead of NeuroSynth's settings
    - Provides synchronous interface for UI integration
    - Handles batch processing efficiently
    """

    def __init__(
        self,
        min_size: int = 100,
        max_size: int = 2048,
    ):
        """Initialize the image extractor.

        Args:
            min_size: Minimum image dimension to extract (skip smaller)
            max_size: Maximum image dimension (resize larger images)
        """
        if not NEUROSYNTH_AVAILABLE:
            raise ImportError(
                f"NeuroSynth modules not available: {_import_error}. "
                "Ensure NeuroSynth is installed in the parent directory."
            )

        self.min_size = min_size
        self.max_size = max_size
        self._extractor = _BaseImageExtractor()
        # Override settings with our config
        self._extractor.min_size = min_size
        self._extractor.max_size = max_size

    def extract_images_sync(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Synchronously extract images from a PDF.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images

        Returns:
            List of VisualElement objects
        """
        return self._extractor._extract_images_sync(pdf_path, output_dir)

    def extract_images_hybrid_sync(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Extract images using hybrid approach: raw + snapshot.

        Combines raw image extraction with rendered snapshots to capture
        labels, arrows, and annotations that raw extraction misses.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images

        Returns:
            List of VisualElement objects (deduplicated)
        """
        return self._extractor._extract_images_hybrid_sync(pdf_path, output_dir)

    async def extract_images(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Asynchronously extract images from a PDF.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images

        Returns:
            List of VisualElement objects
        """
        return await self._extractor.extract_images(pdf_path, output_dir)

    def extract_batch_sync(
        self,
        pdf_paths: list[Path],
        output_base_dir: Path,
        on_progress: callable = None,
    ) -> dict[Path, list[VisualElement]]:
        """Extract images from multiple PDFs efficiently.

        Args:
            pdf_paths: List of PDF files to process
            output_base_dir: Base directory for extracted images
            on_progress: Optional callback(pdf_path, count) for progress

        Returns:
            Dict mapping PDF path to list of extracted VisualElements
        """
        results = {}

        for pdf_path in pdf_paths:
            # Create per-PDF output directory
            pdf_output_dir = output_base_dir / pdf_path.stem

            try:
                elements = self.extract_images_sync(pdf_path, pdf_output_dir)
                results[pdf_path] = elements

                if on_progress:
                    on_progress(pdf_path, len(elements))

            except Exception as e:
                print(f"Warning: Failed to extract images from {pdf_path.name}: {e}")
                results[pdf_path] = []

        return results


def get_image_extractor(
    min_size: int | None = None,
    max_size: int | None = None,
) -> ImageExtractor:
    """Get an ImageExtractor with Reference Library's config.

    Args:
        min_size: Override minimum image size
        max_size: Override maximum image size

    Returns:
        Configured ImageExtractor instance
    """
    # Import here to avoid circular imports
    try:
        from config import MIN_IMAGE_SIZE, MAX_IMAGE_SIZE
        default_min = MIN_IMAGE_SIZE
        default_max = MAX_IMAGE_SIZE
    except ImportError:
        default_min = 100
        default_max = 2048

    return ImageExtractor(
        min_size=min_size or default_min,
        max_size=max_size or default_max,
    )


# Lazy import for ColPali (heavy dependency)
_colpali_client = None

def get_colpali_client():
    """Get the ColPali client for visual embeddings (lazy loaded).

    Returns:
        ColPaliClient singleton or None if not available
    """
    global _colpali_client

    if not NEUROSYNTH_AVAILABLE:
        return None

    if _colpali_client is None:
        try:
            from neurosynth.llm.colpali import get_colpali_client as _get_client
            _colpali_client = _get_client()
        except ImportError:
            return None

    return _colpali_client


def get_qdrant_store(collection_name: str = "reference_library_visuals"):
    """Get a Qdrant visual store for similarity search.

    Args:
        collection_name: Name of the Qdrant collection

    Returns:
        QdrantVisualStore or None if not available
    """
    if not NEUROSYNTH_AVAILABLE:
        return None

    try:
        from neurosynth.dedup.qdrant_store import QdrantVisualStore
        # Import config for path
        try:
            from config import QDRANT_PATH
            path = QDRANT_PATH
        except ImportError:
            from config import DATA_DIR
            path = DATA_DIR / "qdrant"

        return QdrantVisualStore(
            path=str(path),
            collection_name=collection_name,
        )
    except ImportError:
        return None
