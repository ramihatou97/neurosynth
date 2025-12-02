"""
Unified Extraction Pipeline
============================
Orchestrates all enhancement modules for comprehensive image extraction:
1. Resilient image filtering
2. Caption detection and association
3. Visual cluster building
4. Procedural sequence detection
5. Vector graphics extraction
6. LaTeX output generation

Version: 3.0
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field

from .async_wrappers import (
    get_executor_pool,
)
from .batch_processor import BatchPageProcessor
from .config import ImageCategory, NeuroSynthEnhancedConfig
from .enhanced_caption_detector import (
    DetectedCaption,
    EnhancedCaptionDetector,
)
from .latex_figure_generator import (
    EnhancedLaTeXFigureGenerator,
)
from .procedural_detector import ProceduralSequence, ProceduralSequenceDetector

# Import enhancement modules
from .resilient_filter import FilterResult, ResilientImageFilter
from .vector_extractor import VectorGraphic, VectorGraphicsExtractor
from .visual_cluster_associator import (
    EnhancedVisualClusterAssociator,
    ImageBlock,
    TextBlock,
)

logger = logging.getLogger(__name__)

try:
    import fitz

    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    logger.error("PyMuPDF not available")


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ExtractedImage:
    """Complete extracted image with all metadata."""

    image_id: str
    xref: int
    page_number: int
    bbox: tuple[float, float, float, float]

    # Image data
    image_bytes: bytes | None = None
    save_path: str | None = None
    width: int = 0
    height: int = 0
    extension: str = "png"

    # Classification
    category: ImageCategory = ImageCategory.UNKNOWN
    filter_confidence: float = 0.0
    filter_result: FilterResult | None = None

    # Caption
    caption: DetectedCaption | None = None
    figure_id: str | None = None

    # Associations
    associated_text: list[str] = field(default_factory=list)
    keywords: set[str] = field(default_factory=set)

    # Sequence membership
    sequence_id: str | None = None
    sequence_position: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.image_id,
            "xref": self.xref,
            "page": self.page_number,
            "bbox": self.bbox,
            "size": f"{self.width}x{self.height}",
            "category": self.category.value,
            "confidence": round(self.filter_confidence, 3),
            "caption": self.caption.text if self.caption else None,
            "figure_id": self.figure_id,
            "keywords": list(self.keywords)[:10],
            "sequence": self.sequence_id,
            "save_path": self.save_path,
        }


@dataclass
class ExtractionResult:
    """Complete result of document extraction."""

    # Counts
    pages_processed: int = 0
    images_found: int = 0
    images_extracted: int = 0
    duplicates_skipped: int = 0
    vectors_extracted: int = 0

    # Content
    images: list[ExtractedImage] = field(default_factory=list)
    vector_graphics: list[VectorGraphic] = field(default_factory=list)
    sequences: list[ProceduralSequence] = field(default_factory=list)

    # Outputs
    latex_figures: list[str] = field(default_factory=list)

    # Timing
    total_time: float = 0.0

    # Errors
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "pages": self.pages_processed,
                "images_found": self.images_found,
                "images_extracted": self.images_extracted,
                "duplicates_skipped": self.duplicates_skipped,
                "vectors": self.vectors_extracted,
                "sequences": len(self.sequences),
                "time": f"{self.total_time:.2f}s",
            },
            "images": [img.to_dict() for img in self.images],
            "vectors": [v.to_dict() for v in self.vector_graphics],
            "sequences": [s.to_dict() for s in self.sequences],
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def save_metadata(self, path: str):
        """Save extraction metadata to JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


# =============================================================================
# UNIFIED EXTRACTION PIPELINE
# =============================================================================


class UnifiedExtractionPipeline:
    """
    Orchestrates all enhancement modules for comprehensive extraction.

    Pipeline stages:
    1. Batch page processing with caching
    2. Resilient image filtering
    3. Caption detection
    4. Visual-text association
    5. Procedural sequence detection
    6. Vector graphics extraction
    7. LaTeX generation
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.config = config or NeuroSynthEnhancedConfig()

        # Initialize modules
        self.batch_processor = BatchPageProcessor(self.config)
        self.image_filter = ResilientImageFilter(self.config)
        self.caption_detector = EnhancedCaptionDetector(self.config)
        self.cluster_associator = EnhancedVisualClusterAssociator(self.config)
        self.sequence_detector = ProceduralSequenceDetector(self.config)
        self.vector_extractor = VectorGraphicsExtractor(self.config)
        self.latex_generator = EnhancedLaTeXFigureGenerator(self.config)

        # Processing state
        self._doc = None
        self._result = None

    def extract_from_pdf(
        self, pdf_path: str, pages: set[int] = None, output_dir: str = None
    ) -> ExtractionResult:
        """
        Extract all content from a PDF.

        Args:
            pdf_path: Path to PDF file
            pages: Set of page indices (None = all)
            output_dir: Directory for output files

        Returns:
            ExtractionResult with all extracted content
        """
        start_time = time.time()

        # Initialize result
        result = ExtractionResult()

        # Set up output directory
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            images_dir = os.path.join(output_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
        else:
            images_dir = None

        try:
            # Open document
            doc = fitz.open(pdf_path)
            self._doc = doc

            if pages is None:
                pages = set(range(len(doc)))

            result.pages_processed = len(pages)

            # Stage 1: Batch image extraction with filtering
            logger.info("Stage 1: Extracting images...")
            extracted_images = self._extract_and_filter_images(doc, pages, images_dir)
            result.images = extracted_images
            result.images_extracted = len(extracted_images)

            # Stage 2: Caption detection
            if self.config.enable_caption_detection:
                logger.info("Stage 2: Detecting captions...")
                self._detect_captions(doc, extracted_images)

            # Stage 3: Visual-text association
            if self.config.enable_cluster_association:
                logger.info("Stage 3: Building associations...")
                self._build_associations(doc, extracted_images, pages)

            # Stage 4: Procedural sequence detection
            if self.config.enable_procedural_detection:
                logger.info("Stage 4: Detecting sequences...")
                sequences = self._detect_sequences(extracted_images)
                result.sequences = sequences

            # Stage 5: Vector graphics extraction
            if self.config.enable_vector_extraction:
                logger.info("Stage 5: Extracting vectors...")
                vectors = self._extract_vectors(doc, pages, images_dir)
                result.vector_graphics = vectors
                result.vectors_extracted = len(vectors)

            # Stage 6: LaTeX generation
            logger.info("Stage 6: Generating LaTeX...")
            latex_code = self._generate_latex(extracted_images, result.sequences)
            result.latex_figures = latex_code

            # Save outputs
            if output_dir:
                self._save_outputs(output_dir, result)

            doc.close()

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))

        result.total_time = time.time() - start_time
        self._result = result

        return result

    def _extract_and_filter_images(
        self, doc: "fitz.Document", pages: set[int], output_dir: str = None
    ) -> list[ExtractedImage]:
        """Extract and filter images from document."""
        extracted = []
        seen_hashes = set()

        for page_num in pages:
            page = doc[page_num]
            image_list = page.get_images(full=True)

            # Get image positions
            try:
                image_info = page.get_image_info()
                pos_map = {info["xref"]: info.get("bbox") for info in image_info}
            except Exception:
                pos_map = {}

            for img_tuple in image_list:
                xref = img_tuple[0]

                try:
                    # Extract image
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    width = base_image["width"]
                    height = base_image["height"]
                    ext = base_image.get("ext", "png")

                    # Check for duplicates
                    import hashlib

                    img_hash = hashlib.md5(image_bytes).hexdigest()
                    if img_hash in seen_hashes:
                        continue
                    seen_hashes.add(img_hash)

                    # Apply filter
                    should_extract, filter_result = self.image_filter.should_extract(
                        image_bytes, width, height, doc, xref
                    )

                    if not should_extract:
                        continue

                    # Create ExtractedImage
                    image_id = f"img_p{page_num}_{xref}"
                    bbox = pos_map.get(xref, (0, 0, width, height))

                    extracted_img = ExtractedImage(
                        image_id=image_id,
                        xref=xref,
                        page_number=page_num,
                        bbox=bbox,
                        image_bytes=image_bytes,
                        width=width,
                        height=height,
                        extension=ext,
                        filter_confidence=filter_result.confidence,
                        filter_result=filter_result,
                        category=(
                            ImageCategory(filter_result.image_type)
                            if filter_result.image_type
                            in [e.value for e in ImageCategory]
                            else ImageCategory.UNKNOWN
                        ),
                    )

                    # Save to disk if output dir provided
                    if output_dir:
                        filename = f"{image_id}_{img_hash[:8]}.{ext}"
                        save_path = os.path.join(output_dir, filename)

                        with open(save_path, "wb") as f:
                            f.write(image_bytes)

                        extracted_img.save_path = save_path
                        extracted_img.image_bytes = None  # Free memory

                    extracted.append(extracted_img)

                except Exception as e:
                    logger.warning(f"Failed to extract xref {xref}: {e}")

        return extracted

    def _detect_captions(self, doc: "fitz.Document", images: list[ExtractedImage]):
        """Detect and associate captions with images."""
        # Group images by page
        by_page = {}
        for img in images:
            if img.page_number not in by_page:
                by_page[img.page_number] = []
            by_page[img.page_number].append(img)

        # Process each page
        for page_num, page_images in by_page.items():
            page = doc[page_num]

            bboxes = [img.bbox for img in page_images]
            associations = self.caption_detector.associate_captions_with_images(
                page, bboxes
            )

            for idx, caption in associations.items():
                if idx < len(page_images):
                    page_images[idx].caption = caption
                    page_images[idx].figure_id = caption.figure_id

    def _build_associations(
        self, doc: "fitz.Document", images: list[ExtractedImage], pages: set[int]
    ):
        """Build text associations for images."""
        for page_num in pages:
            page = doc[page_num]

            # Get page images
            page_images = [img for img in images if img.page_number == page_num]
            if not page_images:
                continue

            # Get text blocks
            text_dict = page.get_text("dict")
            text_blocks = []

            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue

                # Extract text
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "") + " "

                text = text.strip()
                if not text:
                    continue

                text_blocks.append(
                    TextBlock(
                        text=text, bbox=tuple(block["bbox"]), page_number=page_num
                    )
                )

            # Convert images to ImageBlocks
            image_blocks = [
                ImageBlock(
                    image_id=img.image_id,
                    bbox=img.bbox,
                    page_number=img.page_number,
                    category=img.category,
                    caption=img.caption.text if img.caption else None,
                    figure_id=img.figure_id,
                )
                for img in page_images
            ]

            # Associate
            for i, img_block in enumerate(image_blocks):
                associations = self.cluster_associator.associate_image_with_text(
                    img_block, text_blocks, top_n=3
                )

                for assoc in associations:
                    page_images[i].associated_text.append(assoc.text_block.text[:200])
                    page_images[i].keywords.update(assoc.score.keywords_matched)

    def _detect_sequences(
        self, images: list[ExtractedImage]
    ) -> list[ProceduralSequence]:
        """Detect procedural sequences in extracted images."""
        # Convert to format expected by detector
        image_dicts = []
        for img in images:
            image_dicts.append(
                {
                    "id": img.image_id,
                    "page": img.page_number,
                    "bbox": img.bbox,
                    "caption": img.caption.text if img.caption else "",
                    "figure_id": img.figure_id,
                    "context": " ".join(img.associated_text[:3]),
                }
            )

        sequences = self.sequence_detector.detect_sequences(image_dicts)

        # Update images with sequence info
        for seq in sequences:
            for elem in seq.elements:
                for img in images:
                    if img.image_id == elem.image_id:
                        img.sequence_id = seq.sequence_id
                        img.sequence_position = elem.sequence_number
                        break

        return sequences

    def _extract_vectors(
        self, doc: "fitz.Document", pages: set[int], output_dir: str = None
    ) -> list[VectorGraphic]:
        """Extract vector graphics from document."""
        all_vectors = []

        for page_num in pages:
            page = doc[page_num]
            context = page.get_text()[:500]

            vectors = self.vector_extractor.extract_from_page(page, page_num, context)

            # Save rendered images
            if output_dir and vectors:
                for vec in vectors:
                    if vec.rendered_image:
                        filename = f"{vec.graphic_id}.png"
                        save_path = os.path.join(output_dir, filename)

                        with open(save_path, "wb") as f:
                            f.write(vec.rendered_image)

            all_vectors.extend(vectors)

        return all_vectors

    def _generate_latex(
        self, images: list[ExtractedImage], sequences: list[ProceduralSequence]
    ) -> list[str]:
        """Generate LaTeX code for figures."""
        latex_outputs = []

        # Generate for sequences
        for seq in sequences:
            steps = []
            for elem in seq.elements:
                # Find corresponding image
                img = next((i for i in images if i.image_id == elem.image_id), None)
                if img and img.save_path:
                    steps.append(
                        {
                            "path": img.save_path,
                            "caption": elem.caption or "",
                            "step_number": elem.sequence_number,
                        }
                    )

            if len(steps) >= 2:
                result = self.latex_generator.generate_procedural_sequence(
                    steps, seq.title, f"fig:{seq.sequence_id}"
                )
                latex_outputs.append(result.latex_code)

        # Generate for standalone images
        for img in images:
            if img.sequence_id:  # Already in sequence
                continue

            if img.save_path and img.caption:
                result = self.latex_generator.generate_single(
                    img.save_path, img.caption.text, f"fig:{img.image_id}"
                )
                latex_outputs.append(result.latex_code)

        return latex_outputs

    def _save_outputs(self, output_dir: str, result: ExtractionResult):
        """Save all outputs to disk."""
        # Save metadata
        metadata_path = os.path.join(output_dir, "extraction_metadata.json")
        result.save_metadata(metadata_path)

        # Save LaTeX
        if result.latex_figures:
            latex_dir = os.path.join(output_dir, "latex")
            os.makedirs(latex_dir, exist_ok=True)

            # Combined file
            combined_path = os.path.join(latex_dir, "all_figures.tex")
            with open(combined_path, "w", encoding="utf-8") as f:
                f.write(self.latex_generator.generate_preamble())
                f.write("\n\n")
                f.write("\n\n".join(result.latex_figures))

            # Individual files
            for i, latex in enumerate(result.latex_figures):
                fig_path = os.path.join(latex_dir, f"figure_{i:03d}.tex")
                with open(fig_path, "w", encoding="utf-8") as f:
                    f.write(latex)

        # Save sequence info
        if result.sequences:
            seq_dir = os.path.join(output_dir, "sequences")
            os.makedirs(seq_dir, exist_ok=True)

            for seq in result.sequences:
                seq_path = os.path.join(seq_dir, f"{seq.sequence_id}.json")
                with open(seq_path, "w", encoding="utf-8") as f:
                    json.dump(seq.to_dict(), f, indent=2)


# =============================================================================
# ASYNC PIPELINE WRAPPER
# =============================================================================


class AsyncExtractionPipeline:
    """Async wrapper for the extraction pipeline."""

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.pipeline = UnifiedExtractionPipeline(config)

    async def extract_async(
        self, pdf_path: str, pages: set[int] = None, output_dir: str = None
    ) -> ExtractionResult:
        """Async extraction."""
        pool = get_executor_pool()
        return await pool.run_in_thread(
            self.pipeline.extract_from_pdf, pdf_path, pages, output_dir
        )

    async def extract_multiple_async(
        self, pdf_paths: list[str], output_base_dir: str
    ) -> list[ExtractionResult]:
        """Extract from multiple PDFs concurrently."""

        async def process_one(pdf_path: str) -> ExtractionResult:
            filename = os.path.basename(pdf_path)
            output_dir = os.path.join(output_base_dir, os.path.splitext(filename)[0])
            return await self.extract_async(pdf_path, output_dir=output_dir)

        tasks = [process_one(p) for p in pdf_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def extract_images_from_pdf(
    pdf_path: str, output_dir: str = None, config: NeuroSynthEnhancedConfig = None
) -> ExtractionResult:
    """
    Convenience function for extraction.

    Args:
        pdf_path: Path to PDF
        output_dir: Output directory
        config: Configuration (optional)

    Returns:
        ExtractionResult
    """
    pipeline = UnifiedExtractionPipeline(config)
    return pipeline.extract_from_pdf(pdf_path, output_dir=output_dir)


def quick_extract(
    pdf_path: str, output_dir: str = "./extraction_output"
) -> ExtractionResult:
    """Quick extraction with defaults."""
    return extract_images_from_pdf(pdf_path, output_dir)
