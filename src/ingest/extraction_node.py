"""
Extraction Node (Phase 3: Visual State-of-the-Art)
==================================================
Adaptive wrapper for PDF extraction.
Prioritizes `marker` (SOTA Layout Analysis) if available.
Falls back to `PyMuPDF` (Fast Regex) if not.

Usage:
    extractor = ExtractionNode()
    content = extractor.extract_content(pdf_path)
    # content is a dict {page_num: text}
"""

from pathlib import Path
from typing import Any, Dict, Optional

import fitz  # PyMuPDF

try:
    import torch
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models

    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False


class ExtractionNode:
    """
    Intelligent document extraction facade.
    """

    def __init__(self, force_legacy: bool = False):
        self.use_marker = MARKER_AVAILABLE and not force_legacy
        self._marker_models = None

        if self.use_marker:
            # Lazy load models? No, better to load on init if we are going to use them.
            # But let's keep it lazy for startup speed tests.
            pass

    def extract_content(
        self, pdf_path: Path, output_dir: Path = Path("data/extracted_images")
    ) -> tuple[dict[int, str], list[Any]]:
        """
        Extract text content and images from a PDF.
        Returns:
            Tuple(
                Dict mapping {page_num: text_content},
                List of ExtractedFigure objects
            )
        """
        images = []
        text_pages = {}

        # 1. Extract Images (Parallel independent step, usually)
        # We use SmartImageExtractor for high-quality figure extraction
        # regardless of text method (unless Marker does it better).
        try:
            from src.ingest.smart_extractor import SmartImageExtractor

            # Ensure output dir exists
            output_dir.mkdir(parents=True, exist_ok=True)

            img_extractor = SmartImageExtractor(output_dir=str(output_dir))
            images = img_extractor.process_pdf(str(pdf_path))
        except Exception as e:
            print(f"⚠️ Image extraction failed: {e}")

        # 2. Extract Text
        if self.use_marker:
            try:
                text_pages = self._extract_with_marker(pdf_path)
            except Exception as e:
                print(f"⚠️ Marker extraction failed for {pdf_path}: {e}")
                print("Falling back to PyMuPDF...")
                text_pages = self._extract_with_pymupdf(pdf_path)
        else:
            text_pages = self._extract_with_pymupdf(pdf_path)

        return text_pages, images

    def _extract_with_pymupdf(self, pdf_path: Path) -> dict[int, str]:
        """Legacy extraction (Fast, but loses layout structure)."""
        doc = fitz.open(pdf_path)
        pages = {}
        for page in doc:
            # 1-indexed for consistency with UI/Citation
            pages[page.number + 1] = page.get_text()
        return pages

    def _extract_with_marker(self, pdf_path: Path) -> dict[int, str]:
        """SOTA Extraction using Marker (Layout Analysis)."""
        if not self._marker_models:
            # Load models only when needed
            self._marker_models = load_all_models(limit_to=None)  # Load default

        # Marker processes the whole PDF
        full_text, images, out_meta = convert_single_pdf(
            str(pdf_path), self._marker_models, max_pages=None, batch_multiplier=2
        )

        # NOTE: Marker returns images too, but we are using SmartImageExtractor above
        # for consistency until we fully adopt Marker's image pipeline.

        # Return full text mapped to page 1 for now (Validation Refinement)
        return {1: full_text}
