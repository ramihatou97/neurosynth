import fitz  # PyMuPDF

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

try:
    import imagehash
    from PIL import Image as PILImage

    IMAGEHASH_AVAILABLE = True
except ImportError:
    imagehash = None
    PILImage = None
    IMAGEHASH_AVAILABLE = False

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartExtractor")


@dataclass
class ExtractedFigure:
    """Extracted figure from a PDF with enhanced metadata."""

    source_pdf: str
    image_filename: str
    local_path: Path
    caption: str
    context: str
    page_num: int
    image_type: str = "unknown"

    # Enhanced caption parsing fields
    figure_number: str = ""  # e.g., "1", "2A", "S1", "1-3"
    figure_prefix: str = ""  # e.g., "Fig.", "Figure", "Supplementary Figure"
    parsed_caption: str = ""  # Full parsed caption text after figure reference

    # Deduplication fields
    perceptual_hash: str = ""  # pHash or dHash value
    is_duplicate: bool = False
    duplicate_of: str = ""  # Reference to original image filename if duplicate
    consecutive_occurrences: int = 1  # How many consecutive pages this appears on

    # Anatomical region tagging
    detected_regions: list = field(
        default_factory=list
    )  # Region IDs from region detector
    region_confidence: float = 0.0  # Average confidence of detected regions

    # OCR caption extraction
    ocr_caption: str = ""  # Caption extracted via OCR from image content
    caption_source: str = "proximity"  # "proximity", "ocr", "hybrid"


class SmartImageExtractor:
    def __init__(
        self,
        output_dir: str,
        min_entropy: float = 2.5,
        enable_vector_graphics: bool = False,
        enable_cross_references: bool = False,
    ):
        """
        Initialize the smart image extractor.

        Args:
            output_dir: Directory to save extracted images
            min_entropy: Minimum Shannon entropy threshold for image quality filtering.
                         Lower values (2.0-3.0) = more permissive, keep more images.
                         Higher values (5.0-7.0) = stricter, only high-detail images.
                         Default 4.5 is a good balance for medical figures.
            enable_vector_graphics: Enable Phase 4 vector graphics extraction
                                   (flowcharts, diagrams). Default False.
            enable_cross_references: Enable Phase 4 cross-reference tracking
                                    between figures. Default False.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_entropy = min_entropy
        self.enable_vector_graphics = enable_vector_graphics
        self.enable_cross_references = enable_cross_references

        # Phase 4 components - lazy loaded
        self._vector_extractor = None
        self._cross_ref_tracker = None

        if not pymupdf4llm:
            logger.warning(
                "pymupdf4llm not installed. Smart extraction will be limited."
            )

        if enable_vector_graphics:
            logger.info("🎨 Phase 4: Vector Graphics extraction ENABLED")
        if enable_cross_references:
            logger.info("🔗 Phase 4: Cross-Reference tracking ENABLED")

    def process_pdf(
        self,
        pdf_path: str,
        pages: list[int] | None = None,
        enable_caption_parsing: bool = True,
        enable_deduplication: bool = True,
        dedup_hash_threshold: int = 5,
        dedup_consecutive_threshold: int = 3,
        enable_region_detection: bool = True,
        region_min_confidence: float = 0.3,
        enable_ocr: bool = False,
        ocr_timeout_seconds: int = 5,
    ) -> list[ExtractedFigure]:
        """
        Process a PDF and extract figures with enhanced metadata.

        Args:
            pdf_path: Path to the PDF file
            pages: Optional list of page numbers to process
            enable_caption_parsing: Use enhanced caption parsing (default: True)
            enable_deduplication: Apply perceptual hash deduplication (default: True)
            dedup_hash_threshold: Hamming distance threshold for duplicates (default: 5)
            dedup_consecutive_threshold: Consecutive pages for header/footer (default: 3)
            enable_region_detection: Auto-tag anatomical regions (default: True)
            region_min_confidence: Minimum confidence for region tags (default: 0.3)
            enable_ocr: Extract captions via OCR (default: False)
            ocr_timeout_seconds: Timeout per image for OCR (default: 5)

        Returns:
            List of ExtractedFigure objects with enhanced metadata
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return []

        logger.info(f"Processing: {pdf_path.name}")

        # Temporary directory for pymupdf4llm image dump
        temp_img_dir = self.output_dir / ".temp_extraction"
        temp_img_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not pymupdf4llm:
                return []

            # pymupdf4llm converts PDF to markdown, preserving image placement
            # We use a temporary directory first to filter noise
            md_text = pymupdf4llm.to_markdown(
                doc=str(pdf_path),
                pages=pages,
                write_images=True,
                image_path=str(temp_img_dir),
                image_format="png",
            )
        except Exception as e:
            logger.error(f"Failed to convert PDF with pymupdf4llm: {e}")
            return []

        figures = self._parse_markdown_content(
            md_text,
            pdf_path,
            temp_img_dir,
            enable_caption_parsing=enable_caption_parsing,
            enable_dedup_hashing=enable_deduplication,
        )

        # Apply deduplication if enabled
        if enable_deduplication and figures:
            figures = self.deduplicate_figures(
                figures,
                hash_threshold=dedup_hash_threshold,
                consecutive_threshold=dedup_consecutive_threshold,
            )

        # Apply anatomical region detection if enabled
        if enable_region_detection and figures:
            figures = self._apply_region_detection(
                figures,
                min_confidence=region_min_confidence,
            )

        # Apply OCR caption extraction if enabled
        if enable_ocr and figures:
            figures = self._apply_ocr_extraction(
                figures,
                timeout_seconds=ocr_timeout_seconds,
            )

        # ------------------------------------------------------------------
        # Phase 4: Vector Graphics Extraction
        # ------------------------------------------------------------------
        if self.enable_vector_graphics:
            vector_figures = self._extract_vector_graphics(pdf_path)
            if vector_figures:
                logger.info(
                    f"🎨 Phase 4: Extracted {len(vector_figures)} vector graphics"
                )
                figures.extend(vector_figures)

        # ------------------------------------------------------------------
        # Phase 4: Cross-Reference Tracking
        # ------------------------------------------------------------------
        if self.enable_cross_references and figures:
            figures = self._apply_cross_reference_tracking(figures)

        # Cleanup temp dir (all valid images were moved/copied)
        try:
            shutil.rmtree(temp_img_dir)
        except Exception:
            pass

        return figures

    def _parse_markdown_content(
        self,
        md_text: str,
        source_pdf: Path,
        temp_img_dir: Path,
        enable_caption_parsing: bool = True,
        enable_dedup_hashing: bool = True,
    ) -> list[ExtractedFigure]:
        """
        Parse markdown content to extract figures with enhanced metadata.

        Args:
            md_text: Markdown text from pymupdf4llm
            source_pdf: Path to source PDF
            temp_img_dir: Temporary image directory
            enable_caption_parsing: Whether to use enhanced caption parsing
            enable_dedup_hashing: Whether to compute perceptual hashes
        """
        figures = []
        lines = md_text.split("\n")
        img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")

        for i, line in enumerate(lines):
            match = img_pattern.search(line)
            if match:
                alt_text, img_rel_path = match.groups()

                # The rel_path from pymupdf4llm is usually relative to the execution dir or absolute
                # We need to resolve to the actual file in temp_img_dir
                img_name = Path(img_rel_path).name
                temp_img_path = temp_img_dir / img_name

                if not temp_img_path.exists():
                    continue

                # Quality Gate: Entropy Filtering (using instance threshold)
                if not self._is_medically_relevant(temp_img_path, self.min_entropy):
                    continue

                # Move to final destination
                final_path = self.output_dir / img_name
                # Avoid collision / overwrite logic could be added here
                if final_path.exists():
                    # simple rename strategy
                    stem = final_path.stem
                    final_path = self.output_dir / f"{stem}_{i}.png"

                shutil.copy2(temp_img_path, final_path)

                # Smart Context: Grab lines surrounding the image tag
                # Look 5 lines up and 5 lines down
                start_idx = max(0, i - 5)
                end_idx = min(len(lines), i + 6)
                context_lines = lines[start_idx:i] + lines[i + 1 : end_idx]
                clean_context = " ".join(
                    [
                        ln.strip()
                        for ln in context_lines
                        if ln.strip() and not img_pattern.search(ln)
                    ]
                )

                # Enhanced caption parsing
                figure_prefix = ""
                figure_number = ""
                parsed_caption = ""
                final_caption = ""

                if enable_caption_parsing:
                    caption_result = self._extract_caption_enhanced(clean_context)
                    if caption_result:
                        figure_prefix = caption_result.get("prefix", "")
                        figure_number = caption_result.get("number", "")
                        parsed_caption = caption_result.get("caption_text", "")
                        final_caption = caption_result.get("full_match", "")

                # Fallback to legacy extraction or alt_text
                if not final_caption:
                    final_caption = alt_text or f"Image from {source_pdf.name}"

                # Compute perceptual hash for deduplication
                perceptual_hash = ""
                if enable_dedup_hashing:
                    perceptual_hash = self._compute_perceptual_hash(final_path)

                figures.append(
                    ExtractedFigure(
                        source_pdf=source_pdf.name,
                        image_filename=final_path.name,
                        local_path=final_path,
                        caption=final_caption,
                        context=clean_context,
                        page_num=0,  # pymupdf4llm doesn't give page nums easily
                        figure_prefix=figure_prefix,
                        figure_number=figure_number,
                        parsed_caption=parsed_caption,
                        perceptual_hash=perceptual_hash,
                    )
                )
        return figures

    def _is_medically_relevant(
        self, image_path: Path, min_entropy: float = 4.5
    ) -> bool:
        """Uses Shannon Entropy to filter low-info images (icons, spacers)."""
        try:
            # Read image as grayscale
            # We use cv2 for speed, but PIL could work too
            img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return False

            h, w = img.shape

            # Size Filter
            if h < 70 or w < 70:
                return False  # Too small (icons)

            # Aspect Ratio Filter (Keep 8:1 for panoramas, kill 10:1 lines)
            ratio = max(h, w) / min(h, w) if min(h, w) > 0 else 0
            if ratio > 10:
                return False  # Too thin (separator lines)

            # Entropy Calculation
            # Histogram
            hist = cv2.calcHist([img], [0], None, [256], [0, 256])
            hist_norm = hist.ravel() / hist.sum()

            # Shannon Entropy = -sum(p * log2(p))
            logs = np.log2(hist_norm + 1e-7)
            entropy = -(hist_norm * logs).sum()

            return entropy > min_entropy
        except Exception:
            return False

    def _extract_caption(self, text: str) -> str | None:
        """Legacy caption extraction - returns raw match."""
        result = self._extract_caption_enhanced(text)
        return result.get("full_match") if result else None

    def _extract_caption_enhanced(self, text: str) -> dict | None:
        """
        Enhanced caption extraction with structured figure reference parsing.

        Supports:
        - "Fig. 1", "Fig 1", "Figure 1", "Figure 1:", "Fig. 1A", "Figure 1a-c"
        - "Figs. 1-3", "Figures 1 and 2", "Figs 1, 2, 3"
        - "Supplementary Figure S1", "Supp. Fig. S1"
        - "Plate 1", "Panel A"

        Returns:
            dict with keys: prefix, number, caption_text, full_match
            or None if no match found
        """
        # Pattern components
        # Prefix patterns (case-insensitive)
        prefix_patterns = [
            r"Supplementary\s+Fig(?:ure)?s?\.?",
            r"Supp\.?\s+Fig(?:ure)?s?\.?",
            r"Fig(?:ure)?s?\.?",
            r"Plate",
            r"Panel",
        ]

        # Number patterns: "1", "1A", "1a", "1-3", "1a-c", "S1", "1 and 2", "1, 2, 3"
        number_pattern = r"[S]?\d+(?:[A-Za-z])?(?:\s*[-–]\s*[S]?\d*[A-Za-z]?)?(?:\s*(?:,|and)\s*\d+[A-Za-z]?)*"

        # Build full pattern
        full_pattern = (
            r"(" + "|".join(prefix_patterns) + r")"  # Group 1: prefix
            r"\s*"
            r"(" + number_pattern + r")"  # Group 2: number(s)
            r"\s*[:.\-–]?\s*"  # Optional separator
            r"(.*?)$"  # Group 3: caption text (greedy to end)
        )

        match = re.search(full_pattern, text, re.IGNORECASE | re.MULTILINE)

        if match:
            prefix = match.group(1).strip()
            number = match.group(2).strip()
            caption_text = match.group(3).strip() if match.group(3) else ""

            # Clean up caption text - take up to first period or 200 chars
            if caption_text:
                # Look for multi-line continuation
                # Caption often continues: "Figure 1. Title of the figure\nshowing something"
                first_sentence_end = caption_text.find(". ")
                if first_sentence_end > 0 and first_sentence_end < 200:
                    caption_text = caption_text[: first_sentence_end + 1]
                elif len(caption_text) > 200:
                    caption_text = caption_text[:200] + "..."

            return {
                "prefix": prefix,
                "number": number,
                "caption_text": caption_text,
                "full_match": match.group(0).strip(),
            }

        return None

    def _compute_perceptual_hash(self, image_path: Path) -> str:
        """
        Compute perceptual hash (pHash) for an image.

        Returns:
            Hex string of the hash, or empty string if failed
        """
        if not IMAGEHASH_AVAILABLE:
            return ""

        try:
            img = PILImage.open(image_path)
            # Use pHash (perceptual hash) - more robust than dHash
            phash = imagehash.phash(img)
            return str(phash)
        except Exception as e:
            logger.debug(f"Failed to compute pHash for {image_path}: {e}")
            return ""

    @staticmethod
    def _hamming_distance(hash1: str, hash2: str) -> int:
        """
        Compute Hamming distance between two hex hash strings.

        Returns:
            Number of differing bits, or -1 if invalid inputs
        """
        if not hash1 or not hash2 or len(hash1) != len(hash2):
            return -1

        try:
            # Convert hex to int and XOR
            xor = int(hash1, 16) ^ int(hash2, 16)
            # Count set bits
            return bin(xor).count("1")
        except ValueError:
            return -1

    def deduplicate_figures(
        self,
        figures: list[ExtractedFigure],
        hash_threshold: int = 5,
        consecutive_threshold: int = 3,
    ) -> list[ExtractedFigure]:
        """
        Deduplicate figures based on perceptual hashing.

        Args:
            figures: List of ExtractedFigure objects
            hash_threshold: Max Hamming distance to consider as duplicate (default: 5)
            consecutive_threshold: If image appears on N+ consecutive pages,
                                   classify as header/footer (default: 3)

        Returns:
            List of figures with is_duplicate and duplicate_of fields set
        """
        if not figures:
            return figures

        # Compute hashes for all figures
        for fig in figures:
            if not fig.perceptual_hash:
                fig.perceptual_hash = self._compute_perceptual_hash(fig.local_path)

        # Build hash-to-figures mapping
        hash_groups: dict[str, list[ExtractedFigure]] = {}
        for fig in figures:
            if fig.perceptual_hash:
                if fig.perceptual_hash not in hash_groups:
                    hash_groups[fig.perceptual_hash] = []
                hash_groups[fig.perceptual_hash].append(fig)

        # Track originals (first occurrence of each unique image)
        seen_hashes: dict[str, ExtractedFigure] = {}

        for fig in figures:
            if not fig.perceptual_hash:
                continue

            # Check for exact or near-duplicate
            is_dup = False
            dup_of = None

            for seen_hash, original in seen_hashes.items():
                distance = self._hamming_distance(fig.perceptual_hash, seen_hash)
                if 0 <= distance <= hash_threshold:
                    is_dup = True
                    dup_of = original
                    break

            if is_dup and dup_of:
                fig.is_duplicate = True
                fig.duplicate_of = dup_of.image_filename
                dup_of.consecutive_occurrences += 1
            else:
                # This is a new unique image
                seen_hashes[fig.perceptual_hash] = fig

        # Mark images that appear on 3+ consecutive pages as header/footer
        for fig in figures:
            if fig.consecutive_occurrences >= consecutive_threshold:
                # Mark all duplicates of this as header/footer type
                fig.image_type = "header_footer"
                for other in figures:
                    if other.duplicate_of == fig.image_filename:
                        other.image_type = "header_footer"

        # Log deduplication stats
        total = len(figures)
        duplicates = sum(1 for f in figures if f.is_duplicate)
        headers = sum(1 for f in figures if f.image_type == "header_footer")

        if duplicates > 0:
            logger.info(
                f"Deduplication: {duplicates}/{total} duplicates found, "
                f"{headers} classified as headers/footers"
            )

        return figures

    def _apply_region_detection(
        self,
        figures: list[ExtractedFigure],
        min_confidence: float = 0.3,
        enable_visual_detection: bool = True,
    ) -> list[ExtractedFigure]:
        """
        Apply hybrid anatomical region detection to extracted figures.

        Uses both keyword-based detection (from caption/context) and
        visual detection (from BiomedCLIP image embeddings) for improved coverage.

        Args:
            figures: List of ExtractedFigure objects
            min_confidence: Minimum confidence threshold for keyword-based tags
            enable_visual_detection: Also use visual similarity detection

        Returns:
            Updated list with detected_regions populated
        """
        # Initialize keyword detector
        keyword_detector = None
        try:
            from neurosynth.enhancements.region_detector import AnatomicalRegionDetector

            keyword_detector = AnatomicalRegionDetector(min_confidence=min_confidence)
        except ImportError as e:
            logger.warning(f"Keyword region detection unavailable: {e}")

        # Initialize visual detector (Priority 4 enhancement)
        visual_detector = None
        if enable_visual_detection:
            try:
                from pathlib import Path

                from neurosynth.enhancements.visual_region_detector import (
                    VisualRegionDetector,
                )

                exemplar_dir = Path("assets/region_exemplars")
                visual_detector = VisualRegionDetector(
                    exemplar_dir=exemplar_dir if exemplar_dir.exists() else None,
                    similarity_threshold=0.22,  # Lower threshold for text embeddings
                )
                visual_detector.initialize()
            except Exception as e:
                logger.warning(f"Visual region detection unavailable: {e}")

        if not keyword_detector and not visual_detector:
            return figures

        keyword_tagged = 0
        visual_tagged = 0
        hybrid_tagged = 0

        for fig in figures:
            # Skip header/footer images
            if fig.image_type == "header_footer":
                continue

            keyword_regions = set()
            visual_regions = set()
            confidence_sum = 0.0
            confidence_count = 0

            # Keyword-based detection from caption and context
            if keyword_detector:
                matches = keyword_detector.detect_regions_detailed(
                    caption=fig.caption,
                    context=fig.context,
                )
                if matches:
                    keyword_regions = {m.region_id for m in matches}
                    confidence_sum += sum(m.confidence for m in matches)
                    confidence_count += len(matches)

            # Visual detection from image embedding (Priority 4)
            if visual_detector and hasattr(fig, "local_path") and fig.local_path:
                try:
                    from pathlib import Path

                    img_path = Path(fig.local_path)
                    if img_path.exists():
                        visual_matches = visual_detector.detect_regions(
                            image_path=img_path
                        )
                        if visual_matches:
                            visual_regions = {m.region_id for m in visual_matches}
                            # Visual similarity scores need scaling (0.2-0.4 -> 0.3-0.9)
                            for m in visual_matches:
                                scaled_conf = min(0.9, (m.similarity - 0.15) * 3)
                                confidence_sum += max(0.3, scaled_conf)
                                confidence_count += 1
                except Exception as e:
                    logger.debug(f"Visual detection failed for {fig.file_path}: {e}")

            # Merge regions (union of keyword and visual)
            all_regions = keyword_regions | visual_regions

            if all_regions:
                fig.detected_regions = list(all_regions)[:5]  # Max 5 regions
                fig.region_confidence = (
                    confidence_sum / confidence_count if confidence_count > 0 else 0.0
                )

                # Track detection source for logging
                if keyword_regions and visual_regions:
                    hybrid_tagged += 1
                elif keyword_regions:
                    keyword_tagged += 1
                else:
                    visual_tagged += 1

        total_tagged = keyword_tagged + visual_tagged + hybrid_tagged
        if total_tagged > 0:
            logger.info(
                f"Region detection: {total_tagged}/{len(figures)} tagged "
                f"(keyword: {keyword_tagged}, visual: {visual_tagged}, hybrid: {hybrid_tagged})"
            )

        return figures

    def _apply_ocr_extraction(
        self,
        figures: list[ExtractedFigure],
        timeout_seconds: int = 5,
    ) -> list[ExtractedFigure]:
        """
        Apply OCR caption extraction to extracted figures.

        Args:
            figures: List of ExtractedFigure objects
            timeout_seconds: Timeout per image for OCR

        Returns:
            Updated list with ocr_caption populated
        """
        try:
            from ingest.ocr_caption_extractor import OCRCaptionExtractor

            extractor = OCRCaptionExtractor(timeout_seconds=timeout_seconds)
        except ImportError as e:
            logger.warning(f"OCR extraction unavailable: {e}")
            return figures

        ocr_count = 0
        for fig in figures:
            # Skip header/footer images
            if fig.image_type == "header_footer":
                continue

            # Extract text via OCR
            ocr_result = extractor.extract_caption(fig.local_path)

            if ocr_result and ocr_result.get("text"):
                fig.ocr_caption = ocr_result["text"]

                # Determine caption source
                if fig.parsed_caption and fig.ocr_caption:
                    fig.caption_source = "hybrid"
                elif fig.ocr_caption:
                    fig.caption_source = "ocr"
                    # Use OCR caption if proximity caption is just filename fallback
                    if "Image from" in fig.caption:
                        fig.caption = fig.ocr_caption

                ocr_count += 1

        if ocr_count > 0:
            logger.info(f"OCR extraction: {ocr_count}/{len(figures)} images processed")

        return figures

    # =========================================================================
    # PHASE 4: VECTOR GRAPHICS EXTRACTION
    # =========================================================================

    def _extract_vector_graphics(self, pdf_path: Path) -> list[ExtractedFigure]:
        """
        Extract vector graphics (flowcharts, diagrams) from PDF using PyMuPDF drawings.

        Uses VectorGraphicsExtractor from neurosynth.enhancements module.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of ExtractedFigure objects representing vector graphics
        """
        try:
            from src.neurosynth.enhancements.config import NeuroSynthEnhancedConfig
            from src.neurosynth.enhancements.vector_extractor import (
                VectorGraphicsExtractor,
            )
        except ImportError as e:
            logger.warning(f"🎨 Phase 4: Vector graphics extraction unavailable: {e}")
            return []

        vector_figures = []

        try:
            # Create config for vector extractor
            config = NeuroSynthEnhancedConfig(
                enable_vector_extraction=True,
                output_base_dir=str(self.output_dir.parent),
            )

            extractor = VectorGraphicsExtractor(config)

            # Open PDF and extract from each page
            doc = fitz.open(str(pdf_path))
            try:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_text = page.get_text()

                    graphics = extractor.extract_from_page(page, page_num, page_text)

                    for graphic in graphics:
                        # Render and save to output directory
                        if graphic.rendered_image:
                            img_filename = f"{graphic.graphic_id}.png"
                            img_path = self.output_dir / img_filename

                            with open(img_path, "wb") as f:
                                f.write(graphic.rendered_image)

                            # Convert VectorGraphic to ExtractedFigure
                            figure = ExtractedFigure(
                                source_pdf=str(pdf_path.name),
                                image_filename=img_filename,
                                local_path=img_path,
                                caption=f"Vector {graphic.graphic_type}: "
                                f"{', '.join(graphic.keywords_found) or 'diagram'}",
                                context=page_text[:500] if page_text else "",
                                page_num=page_num + 1,  # 1-indexed
                                image_type=f"vector_{graphic.graphic_type}",
                                figure_prefix="Vector",
                                figure_number=graphic.graphic_id,
                            )
                            vector_figures.append(figure)

                            logger.debug(
                                f"🎨 Extracted vector graphic: {img_filename} "
                                f"(type={graphic.graphic_type}, conf={graphic.confidence:.2f})"
                            )
            finally:
                doc.close()

        except Exception as e:
            logger.error(f"🎨 Phase 4: Vector graphics extraction failed: {e}")

        return vector_figures

    # =========================================================================
    # PHASE 4: CROSS-REFERENCE TRACKING
    # =========================================================================

    def _apply_cross_reference_tracking(
        self, figures: list[ExtractedFigure]
    ) -> list[ExtractedFigure]:
        """
        Track cross-references between figures (e.g., "see Figure 3").

        Uses CrossReferenceTracker from neurosynth.enhancements module.

        Args:
            figures: List of ExtractedFigure objects

        Returns:
            Updated list with cross-reference metadata
        """
        try:
            from src.neurosynth.enhancements.enhanced_caption_detector import (
                CrossReferenceTracker,
                DetectedCaption,
            )
        except ImportError as e:
            logger.warning(f"🔗 Phase 4: Cross-reference tracking unavailable: {e}")
            return figures

        tracker = CrossReferenceTracker()

        # Build DetectedCaption objects from figures and add to tracker
        for fig in figures:
            if fig.figure_number:
                # Create a DetectedCaption for tracker
                caption_obj = DetectedCaption(
                    text=fig.caption,
                    page_number=fig.page_num,
                    bbox=(0, 0, 0, 0),  # Bbox not tracked in ExtractedFigure
                    figure_id=fig.figure_number,
                    caption_type="figure",
                    confidence=1.0,
                )

                # Extract cross-references from caption text
                caption_obj.cross_references = self._extract_cross_refs(fig.caption)
                tracker.add_caption(caption_obj)

        # Build reference graph
        ref_graph = tracker.build_reference_graph()

        # Log summary
        total_refs = sum(len(refs) for refs in ref_graph.get("outgoing", {}).values())
        if total_refs > 0:
            logger.info(
                f"🔗 Phase 4: Found {total_refs} cross-references among "
                f"{len(figures)} figures"
            )

        return figures

    def _extract_cross_refs(self, caption: str) -> list[str]:
        """
        Extract cross-reference figure IDs from caption text.

        Looks for patterns like "see Figure 3", "cf. Fig. 2A", etc.

        Args:
            caption: Caption text to parse

        Returns:
            List of referenced figure IDs
        """
        import re

        refs = []

        # Pattern: "see Figure 3", "cf. Fig. 2A", "as shown in Figure 1-3"
        patterns = [
            r"see\s+(?:figure|fig\.?)\s*(\d+[A-Za-z]?(?:-\d+)?)",
            r"cf\.?\s+(?:figure|fig\.?)\s*(\d+[A-Za-z]?(?:-\d+)?)",
            r"as shown in\s+(?:figure|fig\.?)\s*(\d+[A-Za-z]?(?:-\d+)?)",
            r"\((?:figure|fig\.?)\s*(\d+[A-Za-z]?(?:-\d+)?)\)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, caption, re.IGNORECASE)
            refs.extend(matches)

        return list(set(refs))  # Deduplicate
