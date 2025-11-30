"""
Batch Page Processor for NeuroSynth
====================================
Optimizes PDF image extraction through batch processing and deduplication.

Key features:
- XRef-based deduplication (same image referenced multiple times)
- Perceptual hash-based duplicate detection (identical images with different xrefs)
- Position caching for efficient re-extraction
- Batch processing with statistics

Version: 1.0
"""

import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

from .config import NeuroSynthEnhancedConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class BatchProcessingResult:
    """
    Result of batch page processing with deduplication statistics.

    Caches enable efficient subsequent extractions:
    - xref_cache: Direct image bytes lookup by xref
    - hash_cache: Duplicate detection via perceptual hash
    - position_cache: Spatial information for layout analysis
    """
    pages_processed: int = 0
    images_found: int = 0
    duplicates_skipped: int = 0

    # Caches
    xref_cache: Dict[int, bytes] = field(default_factory=dict)       # xref -> image bytes
    hash_cache: Dict[str, int] = field(default_factory=dict)         # hash -> xref
    position_cache: Dict[int, Tuple] = field(default_factory=dict)   # xref -> (page, bbox)

    # Performance
    processing_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            'pages_processed': self.pages_processed,
            'images_found': self.images_found,
            'duplicates_skipped': self.duplicates_skipped,
            'deduplication_ratio': (
                self.duplicates_skipped / max(1, self.images_found) * 100
            ),
            'processing_time': round(self.processing_time, 3),
            'cache_sizes': {
                'xref_cache': len(self.xref_cache),
                'hash_cache': len(self.hash_cache),
                'position_cache': len(self.position_cache),
            }
        }


# =============================================================================
# BATCH PAGE PROCESSOR
# =============================================================================

class BatchPageProcessor:
    """
    Processes PDF pages in batches with intelligent deduplication.

    Deduplication strategies:
    1. XRef deduplication: If same xref seen before, skip extraction
    2. Hash deduplication: If identical image (different xref), mark as duplicate

    This significantly improves performance for PDFs with repeated images
    (common in medical literature with reference figures appearing multiple times).
    """

    def __init__(self, config: NeuroSynthEnhancedConfig):
        """
        Initialize batch processor with configuration.

        Args:
            config: Master configuration object
        """
        if not HAS_FITZ:
            raise ImportError("PyMuPDF (fitz) required for batch processing")

        self.config = config
        self.perf_config = config.performance

        # Deduplication caches (persistent across process_pages calls)
        self.xref_cache: Dict[int, bytes] = {}
        self.hash_cache: Dict[str, int] = {}
        self.position_cache: Dict[int, Tuple] = {}

        # Feature flags
        self.enable_xref_dedup = self.perf_config.enable_xref_dedup
        self.enable_hash_cache = self.perf_config.enable_hash_cache

        logger.info(
            f"BatchPageProcessor initialized: "
            f"xref_dedup={self.enable_xref_dedup}, "
            f"hash_cache={self.enable_hash_cache}"
        )

    def process_pages(
        self,
        doc: fitz.Document,
        pages: Set[int]
    ) -> BatchProcessingResult:
        """
        Process pages in batch with deduplication.

        Algorithm:
        1. Iterate through specified pages
        2. Extract image list from each page
        3. For each image:
           a. Check if xref already processed (skip if so)
           b. Extract image bytes
           c. Compute perceptual hash
           d. Check if hash seen before (mark duplicate if so)
           e. Cache image bytes, hash, and position
        4. Return statistics and caches

        Args:
            doc: PyMuPDF Document object
            pages: Set of page numbers to process (0-indexed)

        Returns:
            BatchProcessingResult with caches and statistics
        """
        start_time = time.time()

        result = BatchProcessingResult()

        # Convert to sorted list for consistent processing
        page_list = sorted(pages) if pages else range(len(doc))

        for page_num in page_list:
            try:
                if page_num < 0 or page_num >= len(doc):
                    logger.warning(f"Page {page_num} out of range, skipping")
                    continue

                page = doc[page_num]
                self._process_single_page(page, page_num, result)
                result.pages_processed += 1

            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}", exc_info=True)
                continue

        # Update caches in result
        result.xref_cache = self.xref_cache.copy()
        result.hash_cache = self.hash_cache.copy()
        result.position_cache = self.position_cache.copy()

        # Calculate processing time
        result.processing_time = time.time() - start_time

        logger.info(
            f"Batch processing complete: {result.pages_processed} pages, "
            f"{result.images_found} images found, "
            f"{result.duplicates_skipped} duplicates skipped "
            f"({result.duplicates_skipped / max(1, result.images_found) * 100:.1f}%)"
        )

        return result

    def _process_single_page(
        self,
        page: fitz.Page,
        page_num: int,
        result: BatchProcessingResult
    ) -> None:
        """
        Process a single page, extracting and deduplicating images.

        Args:
            page: PyMuPDF Page object
            page_num: Page number (0-indexed)
            result: BatchProcessingResult to update
        """
        # Get image list
        image_list = page.get_images(full=True)

        if not image_list:
            logger.debug(f"Page {page_num}: No images found")
            return

        logger.debug(f"Page {page_num}: Found {len(image_list)} images")

        for img_info in image_list:
            # Extract xref (image reference number)
            xref = img_info[0]

            result.images_found += 1

            # Check xref deduplication
            if self.enable_xref_dedup and xref in self.xref_cache:
                result.duplicates_skipped += 1
                logger.debug(f"Page {page_num}: Skipped duplicate xref {xref}")
                continue

            # Extract image bytes
            try:
                image_bytes = self._extract_image_bytes(page.parent, xref)

                if not image_bytes:
                    logger.warning(f"Page {page_num}: No bytes for xref {xref}")
                    continue

                # Compute hash for duplicate detection
                image_hash = self._compute_image_hash(image_bytes)

                # Check hash deduplication
                if self.enable_hash_cache and image_hash in self.hash_cache:
                    result.duplicates_skipped += 1
                    logger.debug(
                        f"Page {page_num}: Skipped duplicate hash for xref {xref}"
                    )
                    # Still cache this xref → original xref mapping
                    self.xref_cache[xref] = image_bytes
                    continue

                # Extract position (bbox)
                bbox = self._extract_image_bbox(page, xref)

                # Cache everything
                self._cache_image(xref, image_bytes, image_hash, page_num, bbox)

                logger.debug(
                    f"Page {page_num}: Cached xref {xref} "
                    f"({len(image_bytes)} bytes, hash {image_hash[:8]}...)"
                )

            except Exception as e:
                logger.error(
                    f"Page {page_num}: Failed to process xref {xref}: {e}",
                    exc_info=True
                )
                continue

    def _extract_image_bytes(
        self,
        doc: fitz.Document,
        xref: int
    ) -> Optional[bytes]:
        """
        Extract raw image bytes from document by xref.

        Args:
            doc: PyMuPDF Document object
            xref: Image xref (reference number)

        Returns:
            Image bytes, or None if extraction failed
        """
        try:
            # Extract image using xref
            base_image = doc.extract_image(xref)

            if not base_image:
                return None

            return base_image.get('image', None)

        except Exception as e:
            logger.debug(f"Failed to extract xref {xref}: {e}")
            return None

    def _compute_image_hash(
        self,
        image_bytes: bytes
    ) -> str:
        """
        Compute perceptual hash for duplicate detection.

        Uses SHA-256 for simplicity. For true perceptual hashing
        (resistant to resizing/compression), would use algorithms like
        pHash or dHash, but SHA-256 is sufficient for exact duplicates.

        Args:
            image_bytes: Raw image bytes

        Returns:
            Hex digest of hash
        """
        return hashlib.sha256(image_bytes).hexdigest()

    def _extract_image_bbox(
        self,
        page: fitz.Page,
        xref: int
    ) -> Tuple[float, float, float, float]:
        """
        Extract bounding box for an image on a page.

        Args:
            page: PyMuPDF Page object
            xref: Image xref

        Returns:
            Tuple (x0, y0, x1, y1) or (0, 0, 0, 0) if not found
        """
        try:
            # Get image rectangles
            image_rects = page.get_image_rects(xref)

            if not image_rects:
                return (0, 0, 0, 0)

            # Use first rectangle (images can appear multiple times)
            rect = image_rects[0]
            return (rect.x0, rect.y0, rect.x1, rect.y1)

        except Exception as e:
            logger.debug(f"Failed to extract bbox for xref {xref}: {e}")
            return (0, 0, 0, 0)

    def _cache_image(
        self,
        xref: int,
        image_bytes: bytes,
        image_hash: str,
        page_num: int,
        bbox: Tuple[float, float, float, float]
    ) -> None:
        """
        Cache image data for subsequent retrieval.

        Args:
            xref: Image xref
            image_bytes: Raw image bytes
            image_hash: Perceptual hash
            page_num: Page number where image appears
            bbox: Image bounding box
        """
        # Cache bytes by xref
        self.xref_cache[xref] = image_bytes

        # Cache hash → xref mapping
        self.hash_cache[image_hash] = xref

        # Cache position information
        self.position_cache[xref] = (page_num, bbox)

    def clear_caches(self) -> None:
        """
        Clear all caches.

        Useful when processing multiple documents to avoid memory buildup.
        """
        self.xref_cache.clear()
        self.hash_cache.clear()
        self.position_cache.clear()
        logger.info("Batch processor caches cleared")

    def get_cache_statistics(self) -> dict:
        """
        Get current cache statistics.

        Returns:
            Dictionary with cache sizes and memory estimates
        """
        total_bytes = sum(len(img) for img in self.xref_cache.values())

        return {
            'xref_cache_size': len(self.xref_cache),
            'hash_cache_size': len(self.hash_cache),
            'position_cache_size': len(self.position_cache),
            'total_cached_bytes': total_bytes,
            'total_cached_mb': total_bytes / (1024 * 1024),
        }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'BatchProcessingResult',
    'BatchPageProcessor',
]
