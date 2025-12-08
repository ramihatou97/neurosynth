"""
Image Extractor (Legacy Adapter)

Connects the legacy pipeline to the new SmartImageExtractor.
"""

from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

from config import settings
from ingest.smart_extractor import ExtractedFigure, SmartImageExtractor
from models import ExtractedImage, ImageType


class ImageExtractor:
    """
    Adapter class that maps the old ImageExtractor API to the new SmartImageExtractor.
    """

    def __init__(self):
        # We initialized the smart extractor with a default path,
        # or we can defer it to extract_all
        pass

    def extract_all(
        self, doc: fitz.Document, source_id: str, pdf_path: Path
    ) -> list[ExtractedImage]:
        """
        Extract all meaningful images from a document.

        Args:
            doc: PyMuPDF document object (Unused in smart, needed for signature)
            source_id: ID of the source document
            pdf_path: Path to original PDF (for output directory naming)

        Returns:
            List of ExtractedImage objects
        """
        output_dir = settings.processed_path / source_id / "images"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Instantiate Smart Extractor
        smart_extractor = SmartImageExtractor(str(output_dir))

        # Run process
        # Note: SmartExtractor opens the PDF itself, doesn't use the `doc` object
        figures = smart_extractor.process_pdf(str(pdf_path))

        # Convert ExtractedFigure (Smart) -> ExtractedImage (Legacy Model)
        images = []
        for fig in figures:
            images.append(self._to_legacy_model(fig, source_id))

        return images

    def _to_legacy_model(self, fig: ExtractedFigure, source_id: str) -> ExtractedImage:
        """Convert new figure model to old DB model."""
        # Simple heuristic mapping for image type if unknown
        img_type = ImageType.ILLUSTRATION
        if "mri" in fig.caption.lower() or "ct" in fig.caption.lower():
            img_type = ImageType.IMAGING_MRI
        elif "intraoperative" in fig.caption.lower() or "view" in fig.caption.lower():
            img_type = ImageType.SURGICAL_PHOTO
        elif "anatomy" in fig.caption.lower():
            img_type = ImageType.ANATOMICAL_DIAGRAM

        return ExtractedImage(
            id=fig.image_filename,  # Use filename as ID or gen new one
            source_id=source_id,
            page=fig.page_num,
            file_path=fig.local_path,
            caption=fig.caption,
            surrounding_text=fig.context,
            image_type=img_type,
            width=0,  # Dimensions not readily available unless we read image again
            height=0,
        )
