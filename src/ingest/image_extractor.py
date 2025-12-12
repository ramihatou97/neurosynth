"""
Image Extractor (Legacy Adapter)

Connects the legacy pipeline to the new SmartImageExtractor.
Supports Phase 4 features: Vector Graphics and Cross-References.
"""

import logging
from pathlib import Path

import fitz  # PyMuPDF

from ingest.smart_extractor import ExtractedFigure, SmartImageExtractor
from src.config import settings
from src.models import ExtractedImage, ImageType

logger = logging.getLogger(__name__)


class ImageExtractor:
    """
    Adapter class that maps the old ImageExtractor API to the new SmartImageExtractor.
    Supports Phase 4 feature flags for vector graphics and cross-reference extraction.
    """

    def __init__(
        self,
        entropy_threshold: float = 4.5,
        enable_vector_graphics: bool = False,
        enable_cross_references: bool = False,
    ):
        """
        Initialize the image extractor.

        Args:
            entropy_threshold: Minimum Shannon entropy for image quality filtering.
                              Lower (2.0-3.0) = more permissive.
                              Higher (5.0-7.0) = stricter filtering.
                              Default 4.5 is recommended for medical figures.
            enable_vector_graphics: Enable Phase 4 vector graphics extraction
                                   (flowcharts, diagrams). Default False.
            enable_cross_references: Enable Phase 4 cross-reference tracking
                                    between figures. Default False.
        """
        self.entropy_threshold = entropy_threshold
        self.enable_vector_graphics = enable_vector_graphics
        self.enable_cross_references = enable_cross_references

        if enable_vector_graphics:
            logger.info("🎨 Phase 4: Vector Graphics extraction ENABLED")
        if enable_cross_references:
            logger.info("🔗 Phase 4: Cross-Reference tracking ENABLED")

    def extract_all(
        self, doc: fitz.Document, source_id: str, pdf_path: Path  # noqa: ARG002
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

        # Instantiate Smart Extractor with configured entropy threshold and Phase 4 flags
        smart_extractor = SmartImageExtractor(
            str(output_dir),
            min_entropy=self.entropy_threshold,
            enable_vector_graphics=self.enable_vector_graphics,
            enable_cross_references=self.enable_cross_references,
        )

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
            img_type = ImageType.ANATOMY_DIAGRAM

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
            # Phase 4 Extra Metadata
            detected_regions=getattr(fig, "detected_regions", []),
            region_confidence=getattr(fig, "region_confidence", 0.0),
        )
