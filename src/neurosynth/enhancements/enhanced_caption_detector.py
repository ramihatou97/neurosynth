"""
Enhanced Caption Detector with Multi-Directional Search
========================================================
Advanced caption detection that searches in all directions
around images, not just below.

Features:
- Multi-directional search (below, above, left, right)
- Direction priority based on image position
- Multi-line caption reconstruction
- Cross-reference extraction
- Confidence scoring with multiple factors

Version: 3.0
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import (
    CaptionDetectionConfig,
    CaptionPosition,
    NeuroSynthEnhancedConfig,
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
class DetectedCaption:
    """Complete caption data structure."""

    text: str
    figure_id: str | None = None
    subfigure_ids: list[str] = field(default_factory=list)
    caption_type: str = "figure"  # figure, table, plate, step, panel
    page_number: int = 0
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    position: CaptionPosition = CaptionPosition.UNKNOWN
    confidence: float = 0.0
    cross_references: list[str] = field(default_factory=list)

    # Formatting info
    is_italic: bool = False
    is_bold: bool = False
    font_size: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "figure_id": self.figure_id,
            "subfigure_ids": self.subfigure_ids,
            "caption_type": self.caption_type,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "position": self.position.value,
            "confidence": self.confidence,
            "cross_references": self.cross_references,
        }


@dataclass
class SearchRegion:
    """A region to search for captions."""

    rect: Any  # fitz.Rect
    position: CaptionPosition
    priority: int  # Lower = higher priority


@dataclass
class CaptionMatch:
    """Internal match result during detection."""

    caption: DetectedCaption
    distance: float  # Distance from image
    alignment_score: float  # How well aligned with image


# =============================================================================
# CAPTION PATTERN MATCHER
# =============================================================================


class CaptionPatternMatcher:
    """
    Pattern matching for caption text.
    Extracts figure IDs, subfigures, and cross-references.
    """

    def __init__(self, config: CaptionDetectionConfig = None):
        self.config = config or CaptionDetectionConfig()
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        # Figure patterns
        self.figure_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.figure_patterns
        ]

        # Table patterns
        self.table_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.table_patterns
        ]

        # Cross-reference patterns
        self.xref_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.cross_reference_patterns
        ]

        # Subfigure patterns
        self.subfig_pattern = re.compile(r"\(([a-zA-Z])\)", re.IGNORECASE)

        # Step number patterns
        self.step_patterns = [
            re.compile(r"(?i)step\s*(\d+)", re.IGNORECASE),
            re.compile(r"(?i)stage\s*(\d+)", re.IGNORECASE),
            re.compile(r"^(\d+)\.\s+", re.MULTILINE),
        ]

    def is_caption(self, text: str) -> bool:
        """Check if text looks like a caption."""
        if len(text) < 5 or len(text) > 2000:
            return False

        # Check figure patterns
        for pattern in self.figure_patterns:
            if pattern.search(text):
                return True

        # Check table patterns
        return any(pattern.search(text) for pattern in self.table_patterns)

    def extract_figure_id(self, text: str) -> tuple[str | None, str]:
        """
        Extract figure ID and type from caption.

        Returns:
            (figure_id, caption_type)
        """
        # Try figure patterns
        for pattern in self.figure_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groupdict()
                fig_id = groups.get("num") or groups.get("sub")
                cap_type = groups.get("type", "figure").lower()
                return fig_id, cap_type

        # Try table patterns
        for pattern in self.table_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groupdict()
                return groups.get("num"), "table"

        return None, "unknown"

    def extract_subfigures(self, text: str) -> list[str]:
        """Extract subfigure identifiers like (a), (b), (c)."""
        matches = self.subfig_pattern.findall(text)
        return [m.lower() for m in matches]

    def extract_cross_references(self, text: str) -> list[str]:
        """Extract cross-references to other figures."""
        refs = []
        for pattern in self.xref_patterns:
            matches = pattern.findall(text)
            refs.extend(matches)
        return list(set(refs))

    def extract_step_number(self, text: str) -> int | None:
        """Extract step number if present."""
        for pattern in self.step_patterns:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None


# =============================================================================
# MULTI-DIRECTIONAL CAPTION DETECTOR
# =============================================================================


class EnhancedCaptionDetector:
    """
    Advanced caption detector with multi-directional search.

    Searches in all directions around an image and selects
    the best match based on confidence scoring.

    Uses weights from CaptionConfidenceConfig:
    - pattern_weight:    0.40
    - proximity_weight:  0.30
    - formatting_weight: 0.20
    - length_weight:     0.10
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        full_config = config or NeuroSynthEnhancedConfig()
        self.config = full_config.caption_detection
        self.confidence_config = full_config.caption_confidence
        self.pattern_matcher = CaptionPatternMatcher(self.config)

    def detect_captions_on_page(
        self,
        page: "fitz.Page",
        image_bboxes: list[tuple[float, float, float, float]] = None,
    ) -> list[DetectedCaption]:
        """
        Detect all captions on a page.

        Args:
            page: PyMuPDF page object
            image_bboxes: Optional image bounding boxes for association

        Returns:
            List of DetectedCaption objects
        """
        captions = []

        # Get all text blocks
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block["type"] != 0:  # Text block only
                continue

            # Extract block text and metadata
            block_text, formatting = self._extract_block_info(block)

            if not self.pattern_matcher.is_caption(block_text):
                continue

            # Parse caption
            caption = self._parse_caption(
                block_text, block["bbox"], page.number, formatting
            )

            if caption:
                captions.append(caption)

        return captions

    def find_caption_for_image(
        self, page: "fitz.Page", image_bbox: tuple[float, float, float, float]
    ) -> DetectedCaption | None:
        """
        Find the best caption for a specific image.

        Searches in multiple directions based on image position.

        Args:
            page: PyMuPDF page object
            image_bbox: Image bounding box (x0, y0, x1, y1)

        Returns:
            Best matching caption or None
        """
        # Determine search regions based on image position
        search_regions = self._get_search_regions(page, image_bbox)

        # Find candidates in each region
        candidates = []

        for region in search_regions:
            text = page.get_text("text", clip=region.rect).strip()

            if not text or not self.pattern_matcher.is_caption(text):
                continue

            # Get detailed block info
            blocks = page.get_text("dict", clip=region.rect)["blocks"]
            for block in blocks:
                if block["type"] != 0:
                    continue

                block_text, formatting = self._extract_block_info(block)

                if not self.pattern_matcher.is_caption(block_text):
                    continue

                caption = self._parse_caption(
                    block_text, block["bbox"], page.number, formatting
                )

                if caption:
                    caption.position = region.position

                    # Calculate match quality
                    distance = self._calculate_distance(image_bbox, block["bbox"])
                    alignment = self._calculate_alignment(image_bbox, block["bbox"])

                    candidates.append(
                        CaptionMatch(
                            caption=caption,
                            distance=distance,
                            alignment_score=alignment,
                        )
                    )

        # Select best candidate
        if not candidates:
            return None

        best = self._select_best_caption(candidates, image_bbox)
        if best:
            # Calculate final confidence
            best.confidence = self._calculate_confidence(best, image_bbox, candidates)

        return best

    def _get_search_regions(
        self, page: "fitz.Page", image_bbox: tuple[float, float, float, float]
    ) -> list[SearchRegion]:
        """
        Get search regions prioritized by image position on page.
        """
        cfg = self.config
        x0, y0, x1, y1 = image_bbox
        page_height = page.rect.height

        # Determine image position category
        y_center = (y0 + y1) / 2
        if y_center < page_height * 0.25:
            position_key = "top"
        elif y_center > page_height * 0.75:
            position_key = "bottom"
        else:
            position_key = "middle"

        priorities = cfg.direction_priorities.get(
            position_key,
            [CaptionPosition.BELOW, CaptionPosition.ABOVE, CaptionPosition.RIGHT],
        )

        regions = []

        for priority, direction in enumerate(priorities):
            rect = self._create_search_rect(image_bbox, direction, page.rect, cfg)
            if rect:
                regions.append(
                    SearchRegion(rect=rect, position=direction, priority=priority)
                )

        return regions

    def _create_search_rect(
        self,
        image_bbox: tuple[float, float, float, float],
        direction: CaptionPosition,
        page_rect: "fitz.Rect",
        cfg: CaptionDetectionConfig,
    ) -> Optional["fitz.Rect"]:
        """Create search rectangle for a direction."""
        x0, y0, x1, y1 = image_bbox

        if direction == CaptionPosition.BELOW:
            rect = fitz.Rect(
                x0 - cfg.horizontal_tolerance,
                y1,
                x1 + cfg.horizontal_tolerance,
                min(y1 + cfg.search_radius_below, page_rect.height),
            )
        elif direction == CaptionPosition.ABOVE:
            rect = fitz.Rect(
                x0 - cfg.horizontal_tolerance,
                max(y0 - cfg.search_radius_above, 0),
                x1 + cfg.horizontal_tolerance,
                y0,
            )
        elif direction == CaptionPosition.RIGHT:
            rect = fitz.Rect(
                x1,
                y0 - cfg.horizontal_tolerance,
                min(x1 + cfg.search_radius_side, page_rect.width),
                y1 + cfg.horizontal_tolerance,
            )
        elif direction == CaptionPosition.LEFT:
            rect = fitz.Rect(
                max(x0 - cfg.search_radius_side, 0),
                y0 - cfg.horizontal_tolerance,
                x0,
                y1 + cfg.horizontal_tolerance,
            )
        else:
            return None

        # Ensure valid rect
        if rect.width <= 0 or rect.height <= 0:
            return None

        return rect

    def _extract_block_info(self, block: dict) -> tuple[str, dict]:
        """
        Extract text and formatting info from a text block.

        Returns:
            (text, formatting_dict)
        """
        lines = []
        is_italic = False
        is_bold = False
        font_sizes = []

        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
                font_sizes.append(span.get("size", 12))

                flags = span.get("flags", 0)
                if flags & 2:  # Italic
                    is_italic = True
                if flags & (2**4):  # Bold
                    is_bold = True

            lines.append(line_text.strip())

        text = " ".join(lines)
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12

        formatting = {
            "is_italic": is_italic,
            "is_bold": is_bold,
            "font_size": avg_font_size,
        }

        return text, formatting

    def _parse_caption(
        self, text: str, bbox: tuple, page_num: int, formatting: dict
    ) -> DetectedCaption | None:
        """Parse text into a DetectedCaption object."""
        figure_id, caption_type = self.pattern_matcher.extract_figure_id(text)
        subfigures = self.pattern_matcher.extract_subfigures(text)
        cross_refs = self.pattern_matcher.extract_cross_references(text)

        return DetectedCaption(
            text=text,
            figure_id=figure_id,
            subfigure_ids=subfigures,
            caption_type=caption_type,
            page_number=page_num,
            bbox=tuple(bbox),
            confidence=0.5,  # Base confidence, refined later
            cross_references=cross_refs,
            is_italic=formatting.get("is_italic", False),
            is_bold=formatting.get("is_bold", False),
            font_size=formatting.get("font_size", 12),
        )

    def _calculate_distance(
        self, image_bbox: tuple[float, float, float, float], caption_bbox: tuple
    ) -> float:
        """Calculate distance between image and caption."""
        ix0, iy0, ix1, iy1 = image_bbox
        cx0, cy0, cx1, cy1 = caption_bbox

        # Calculate closest points
        img_center_x = (ix0 + ix1) / 2
        img_center_y = (iy0 + iy1) / 2
        cap_center_x = (cx0 + cx1) / 2
        cap_center_y = (cy0 + cy1) / 2

        # Simple center-to-center distance
        import math

        return math.sqrt(
            (img_center_x - cap_center_x) ** 2 + (img_center_y - cap_center_y) ** 2
        )

    def _calculate_alignment(
        self, image_bbox: tuple[float, float, float, float], caption_bbox: tuple
    ) -> float:
        """
        Calculate horizontal alignment score.
        1.0 = perfectly aligned, 0.0 = not aligned
        """
        ix0, iy0, ix1, iy1 = image_bbox
        cx0, cy0, cx1, cy1 = caption_bbox

        img_center_x = (ix0 + ix1) / 2
        cap_center_x = (cx0 + cx1) / 2

        # How far off-center is the caption?
        img_width = ix1 - ix0
        offset = abs(img_center_x - cap_center_x)

        if img_width == 0:
            return 0.5

        # Normalize: offset / image_width
        normalized_offset = offset / img_width

        # Convert to score (0 offset = 1.0, large offset = 0.0)
        return max(0, 1.0 - normalized_offset)

    def _select_best_caption(
        self,
        candidates: list[CaptionMatch],
        image_bbox: tuple[float, float, float, float],
    ) -> DetectedCaption | None:
        """Select the best caption from candidates."""
        if not candidates:
            return None

        # Score each candidate
        scored = []
        for match in candidates:
            score = 0.0

            # Distance score (closer = better)
            # Normalize distance against image size
            img_height = image_bbox[3] - image_bbox[1]
            dist_score = max(0, 1.0 - (match.distance / (img_height * 3)))
            score += dist_score * 0.4

            # Alignment score
            score += match.alignment_score * 0.3

            # Pattern quality (has figure_id = better)
            if match.caption.figure_id:
                score += 0.2

            # Formatting (italic captions are common)
            if match.caption.is_italic:
                score += 0.1

            scored.append((score, match.caption))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return scored[0][1] if scored else None

    def _calculate_confidence(
        self,
        caption: DetectedCaption,
        image_bbox: tuple[float, float, float, float],
        all_candidates: list[CaptionMatch],
    ) -> float:
        """
        Calculate final confidence score using centralized weights.

        Formula:
        confidence = pattern_score × pattern_weight (0.40) +
                     proximity_score × proximity_weight (0.30) +
                     formatting_score × formatting_weight (0.20) +
                     length_score × length_weight (0.10)
        """
        cfg = self.confidence_config  # CaptionConfidenceConfig
        confidence = 0.0

        # 1. Pattern match quality (weight: 0.40)
        pattern_score = 0.0
        if caption.figure_id:
            pattern_score = 0.7
            if re.match(r"\d+([.\-]\d+)?", caption.figure_id or ""):
                pattern_score = 1.0  # Standard figure ID format
        confidence += pattern_score * cfg.pattern_weight

        # 2. Proximity (weight: 0.30)
        distance = self._calculate_distance(image_bbox, caption.bbox)
        img_height = image_bbox[3] - image_bbox[1]
        proximity_score = 0.0
        if distance < cfg.close_proximity_px:  # Very close (within 50px)
            proximity_score = 1.0
        elif distance < img_height * 0.5:
            proximity_score = 0.8
        elif distance < img_height:
            proximity_score = 0.5
        elif distance < img_height * 2:
            proximity_score = 0.3
        confidence += proximity_score * cfg.proximity_weight

        # 3. Formatting (weight: 0.20)
        formatting_score = 0.0
        if caption.is_italic:
            formatting_score += 0.6  # Italic is very common for captions
        if caption.is_bold:
            formatting_score += 0.3
        formatting_score = min(formatting_score, 1.0)
        confidence += formatting_score * cfg.formatting_weight

        # 4. Length (weight: 0.10)
        length_score = 0.0
        if len(caption.text) > cfg.adequate_length_chars:
            length_score = 1.0
        elif len(caption.text) > 20:
            length_score = 0.5
        confidence += length_score * cfg.length_weight

        # Competition penalty (multiple candidates = less certain)
        if len(all_candidates) > 3:
            confidence *= 0.85
        elif len(all_candidates) > 2:
            confidence *= 0.9

        return min(confidence, 1.0)

    def associate_captions_with_images(
        self, page: "fitz.Page", image_bboxes: list[tuple[float, float, float, float]]
    ) -> dict[int, DetectedCaption]:
        """
        Associate captions with images on a page.

        Args:
            page: PyMuPDF page
            image_bboxes: List of image bounding boxes

        Returns:
            Dict mapping image index to best matching caption
        """
        associations = {}
        used_captions = set()  # Track used captions to avoid duplicates

        for img_idx, img_bbox in enumerate(image_bboxes):
            caption = self.find_caption_for_image(page, img_bbox)

            if caption:
                # Check if this caption was already assigned
                caption_key = (caption.page_number, caption.bbox)
                if caption_key in used_captions:
                    # Try to find alternative
                    continue

                if caption.confidence >= self.config.min_confidence:
                    associations[img_idx] = caption
                    used_captions.add(caption_key)

        return associations


# =============================================================================
# BATCH CAPTION PROCESSOR
# =============================================================================


class BatchCaptionProcessor:
    """
    Process captions for multiple images efficiently.
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.detector = EnhancedCaptionDetector(config)

    def process_document(
        self, doc: "fitz.Document", image_info: list[dict]
    ) -> dict[str, DetectedCaption]:
        """
        Process all images in a document.

        Args:
            doc: PyMuPDF document
            image_info: List of image info dicts with 'page', 'bbox', 'id' keys

        Returns:
            Dict mapping image_id to caption
        """
        results = {}

        # Group images by page
        by_page = {}
        for img in image_info:
            page_num = img.get("page", 0)
            if page_num not in by_page:
                by_page[page_num] = []
            by_page[page_num].append(img)

        # Process each page
        for page_num, page_images in by_page.items():
            page = doc[page_num]

            bboxes = [img["bbox"] for img in page_images]
            associations = self.detector.associate_captions_with_images(page, bboxes)

            for idx, caption in associations.items():
                img_id = page_images[idx].get("id", f"p{page_num}_i{idx}")
                results[img_id] = caption

        return results


# =============================================================================
# CROSS-REFERENCE TRACKER
# =============================================================================


class CrossReferenceTracker:
    """
    Track cross-references between figures across a document.
    """

    def __init__(self):
        self.references = {}  # source_fig -> [target_figs]
        self.figure_locations = {}  # fig_id -> (page, bbox)

    def add_caption(self, caption: DetectedCaption):
        """Add a caption and track its references."""
        if caption.figure_id:
            self.figure_locations[caption.figure_id] = (
                caption.page_number,
                caption.bbox,
            )

            if caption.cross_references:
                self.references[caption.figure_id] = caption.cross_references

    def get_references_from(self, figure_id: str) -> list[str]:
        """Get figures referenced by a figure."""
        return self.references.get(figure_id, [])

    def get_references_to(self, figure_id: str) -> list[str]:
        """Get figures that reference a figure."""
        refs_to = []
        for source, targets in self.references.items():
            if figure_id in targets:
                refs_to.append(source)
        return refs_to

    def get_figure_location(self, figure_id: str) -> tuple[int, tuple] | None:
        """Get location of a figure."""
        return self.figure_locations.get(figure_id)

    def build_reference_graph(self) -> dict[str, dict[str, list[str]]]:
        """Build complete reference graph."""
        return {
            "outgoing": dict(self.references),
            "incoming": {
                fig_id: self.get_references_to(fig_id)
                for fig_id in self.figure_locations
            },
            "locations": dict(self.figure_locations),
        }
