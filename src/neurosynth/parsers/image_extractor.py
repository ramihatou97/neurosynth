"""Image extraction from PDF documents using PyMuPDF.

This module extracts images from neurosurgical reference PDFs,
detects captions, and classifies image types (surgical steps,
anatomical diagrams, imaging studies, etc.).
"""

import asyncio
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.models.visual import ImageType, VisualElement

console = Console()


@dataclass
class ImageFilterResult:
    """Result of medical image filtering."""

    is_valid: bool
    rejection_reason: str = ""
    confidence: float = 1.0


def _is_medical_image(
    width: int,
    height: int,
    file_size_bytes: int = 0,
    image_type: ImageType = ImageType.UNKNOWN,
) -> ImageFilterResult:
    """Filter out logos, separators, and non-medical decorative images.

    This heuristic analyzes image properties to distinguish meaningful
    medical/anatomical figures from junk images like:
    - Publisher logos
    - Separator bars/lines
    - Tiny icons
    - Solid color blocks

    Args:
        width: Image width in pixels
        height: Image height in pixels
        file_size_bytes: Size of image data (0 to skip this check)
        image_type: Classified image type (for context-aware filtering)

    Returns:
        ImageFilterResult with is_valid flag and rejection reason
    """
    # Calculate metrics
    aspect_ratio = width / height if height > 0 else 0
    area = width * height

    # Rule 1: Reject if BOTH dimensions are too small (tiny icons)
    # Single dimension can be small for panoramic surgical views
    if width < 150 and height < 150:
        return ImageFilterResult(
            is_valid=False,
            rejection_reason=f"Too small: {width}x{height}px (both dims < 150px)",
            confidence=0.95,
        )

    # Rule 2: Reject extreme aspect ratios (separator bars, banners, lines)
    # Medical images rarely exceed 4:1 aspect ratio
    if aspect_ratio > 6.0:
        return ImageFilterResult(
            is_valid=False,
            rejection_reason=f"Horizontal bar: aspect ratio {aspect_ratio:.1f}:1 (> 6:1)",
            confidence=0.90,
        )
    if aspect_ratio < (1 / 6):
        return ImageFilterResult(
            is_valid=False,
            rejection_reason=f"Vertical bar: aspect ratio 1:{1/aspect_ratio:.1f} (> 6:1)",
            confidence=0.90,
        )

    # Rule 3: Reject very small total area (decorative elements)
    # A meaningful figure should be at least ~170x170 equivalent
    if area < 30_000:
        return ImageFilterResult(
            is_valid=False,
            rejection_reason=f"Small area: {width}x{height} = {area:,}px² (< 30,000)",
            confidence=0.85,
        )

    # Rule 4: Reject suspiciously small file sizes (solid color blocks, simple shapes)
    # A real medical image with detail should be > 5KB
    if file_size_bytes > 0 and file_size_bytes < 5_000:
        # Exception: very small images that passed other checks might be valid thumbnails
        if area > 50_000:
            return ImageFilterResult(
                is_valid=False,
                rejection_reason=f"Low complexity: {file_size_bytes:,} bytes for {area:,}px²",
                confidence=0.80,
            )

    # Rule 5: Reject typical logo dimensions (common publisher logo sizes)
    # Many logos are exactly these dimensions or close to them
    logo_dimensions = [
        (300, 100),
        (200, 50),
        (150, 50),
        (100, 30),  # Horizontal logos
        (50, 50),
        (100, 100),
        (64, 64),
        (32, 32),  # Square icons
    ]
    for logo_w, logo_h in logo_dimensions:
        if abs(width - logo_w) < 20 and abs(height - logo_h) < 20:
            # Could be a logo, but check if it's classified as medical
            if image_type in (ImageType.UNKNOWN, ImageType.ILLUSTRATION):
                return ImageFilterResult(
                    is_valid=False,
                    rejection_reason=f"Logo-like dimensions: {width}x{height}px",
                    confidence=0.70,
                )

    # Rule 6: Accept images classified as medical imaging with relaxed constraints
    # MRI/CT/X-ray images should pass even if they're borderline on other metrics
    if image_type in (ImageType.IMAGING, ImageType.SURGICAL_STEP, ImageType.ANATOMICAL):
        return ImageFilterResult(is_valid=True, rejection_reason="", confidence=0.95)

    # Default: Accept the image
    return ImageFilterResult(is_valid=True, rejection_reason="", confidence=0.80)


@dataclass
class CaptionCandidate:
    """A potential caption found near an image."""

    text: str
    distance: float  # Distance from image bbox
    is_numbered: bool  # Contains "Figure X" pattern
    confidence: float


class ImageExtractor:
    """Extract images and their captions from PDF documents.

    This extractor:
    1. Uses PyMuPDF to extract all embedded images from PDFs
    2. Detects figure captions (prioritizing numbered figures)
    3. Classifies image types based on surrounding text
    4. Computes perceptual hashes for duplicate detection
    """

    # Patterns for identifying figure captions (prioritize numbered)
    FIGURE_PATTERNS = [
        re.compile(
            r"^(?:Figure|Fig\.?)\s*(\d+(?:\.\d+)?)[:\.\-]?\s*(.*)$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^(?:Plate|Image|Panel)\s*(\d+(?:\.\d+)?)[:\.\-]?\s*(.*)$",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]

    # Patterns for image type classification based on surrounding text
    TYPE_PATTERNS: dict[ImageType, list[str]] = {
        ImageType.SURGICAL_STEP: [
            r"step\s*\d+",
            r"intraoperative",
            r"surgical\s+approach",
            r"incision",
            r"dissection",
            r"exposure",
            r"retraction",
            r"instrument",
            r"operative\s+view",
            r"positioning",
            r"draping",
            r"craniotomy",
            r"laminectomy",
            r"resection",
            r"closure",
        ],
        ImageType.ANATOMICAL: [
            r"anatomy",
            r"anatomical",
            r"cross.?section",
            r"sagittal",
            r"coronal",
            r"axial",
            r"nerve",
            r"artery",
            r"vein",
            r"muscle",
            r"bone",
            r"ventricle",
            r"sulcus",
            r"gyrus",
            r"fissure",
            r"nucleus",
            r"tract",
            r"pathway",
            r"foramen",
        ],
        ImageType.IMAGING: [
            r"MRI",
            r"CT\s",
            r"computed\s+tomography",
            r"magnetic\s+resonance",
            r"T1.?weighted",
            r"T2.?weighted",
            r"FLAIR",
            r"angiograph",
            r"radiograph",
            r"X.?ray",
            r"PET",
            r"SPECT",
            r"DSA",
            r"fluoroscop",
            r"ultrasound",
        ],
        ImageType.TABLE: [
            r"table\s*\d+",
            r"classification",
            r"grading\s+scale",
            r"staging\s+system",
        ],
        ImageType.ILLUSTRATION: [
            r"illustration",
            r"diagram",
            r"schematic",
            r"drawing",
            r"artwork",
            r"artist",
            r"rendered",
            r"depict",
        ],
        ImageType.PHOTOGRAPH: [
            r"photograph",
            r"photo",
            r"clinical\s+image",
            r"patient\s+image",
            r"gross\s+specimen",
            r"macroscopic",
            r"microscopic",
            r"histolog",
            r"patholog",
            r"cadaver",
            r"specimen",
        ],
    }

    def __init__(self):
        """Initialize the image extractor."""
        self.settings = get_settings()
        self.min_size = self.settings.min_image_size
        self.max_size = self.settings.max_image_size

    async def extract_images(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Extract all suitable images from a PDF.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images (default: alongside PDF)

        Returns:
            List of VisualElement objects with extracted images
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._extract_images_sync(pdf_path, output_dir)
        )

    def _extract_images_sync(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Synchronous image extraction implementation."""
        visual_elements: list[VisualElement] = []

        # Create output directory for images
        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with fitz.open(pdf_path) as pdf:
                for page_num in range(len(pdf)):
                    page = pdf[page_num]
                    page_images = self._extract_page_images(
                        page, page_num, pdf_path, output_dir, pdf
                    )
                    visual_elements.extend(page_images)
        except Exception as e:
            console.print(f"[red]Error opening PDF {pdf_path.name}: {e}[/red]")
            return []

        if visual_elements:
            console.print(
                f"  [green]Extracted {len(visual_elements)} images from {pdf_path.name}[/green]"
            )

        return visual_elements

    def _extract_page_images(
        self,
        page: fitz.Page,
        page_num: int,
        pdf_path: Path,
        output_dir: Path,
        pdf: fitz.Document,
    ) -> list[VisualElement]:
        """Extract images from a single page with caption detection."""
        elements: list[VisualElement] = []
        page_text = page.get_text("text")

        # Get text blocks for caption detection
        try:
            text_dict = page.get_text("dict")
            text_blocks = text_dict.get("blocks", [])
        except Exception:
            text_blocks = []

        # Get all images on the page
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                # Extract image
                base_image = pdf.extract_image(xref)
                if not base_image:
                    continue

                image_bytes = base_image.get("image")
                if not image_bytes:
                    continue

                image_ext = base_image.get("ext", "png")

                # Load with PIL to check dimensions and process
                try:
                    pil_image = Image.open(io.BytesIO(image_bytes))
                except Exception:
                    continue

                width, height = pil_image.size

                # Skip small images (likely icons/decorations)
                if width < self.min_size or height < self.min_size:
                    continue

                # Convert CMYK and other modes to RGB for compatibility
                if pil_image.mode not in ("RGB", "L"):
                    pil_image = pil_image.convert("RGB")
                    buf = io.BytesIO()
                    pil_image.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
                    image_ext = "png"

                # Resize if too large
                if width > self.max_size or height > self.max_size:
                    pil_image.thumbnail((self.max_size, self.max_size), Image.LANCZOS)
                    buf = io.BytesIO()
                    pil_image.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
                    image_ext = "png"
                    width, height = pil_image.size

                # Get image bounding box (approximate from page layout)
                bbox = self._get_image_bbox(page, xref, img_info)

                # Find caption using priority: numbered first, then proximity
                caption, confidence = self._find_caption(
                    page, bbox, page_text, text_blocks
                )

                # Get context text for classification
                context_text = self._get_context_text(page, bbox, text_blocks)

                # Classify image type
                image_type, type_conf = self._classify_image_type(caption, context_text)

                # Apply medical image filter BEFORE saving
                # This filters out logos, separator bars, and decorative elements
                filter_result = _is_medical_image(
                    width=width,
                    height=height,
                    file_size_bytes=len(image_bytes),
                    image_type=image_type,
                )
                if not filter_result.is_valid:
                    console.print(
                        f"    [dim]Filtered: {pdf_path.stem} p{page_num + 1} i{img_index + 1} - "
                        f"{filter_result.rejection_reason}[/dim]"
                    )
                    continue

                # Generate perceptual hash for deduplication
                visual_hash = self._compute_visual_hash(pil_image)

                # Save image file
                image_filename = (
                    f"{pdf_path.stem}_p{page_num + 1}_i{img_index + 1}.{image_ext}"
                )
                image_path = output_dir / image_filename

                # Handle filename collisions
                counter = 1
                while image_path.exists():
                    image_filename = f"{pdf_path.stem}_p{page_num + 1}_i{img_index + 1}_{counter}.{image_ext}"
                    image_path = output_dir / image_filename
                    counter += 1

                image_path.write_bytes(image_bytes)

                # Create VisualElement
                element = VisualElement(
                    image_path=image_path,
                    format=image_ext,
                    width=width,
                    height=height,
                    source_pdf=pdf_path,
                    page_number=page_num + 1,
                    bbox=bbox,
                    caption=caption,
                    caption_confidence=confidence,
                    image_type=image_type,
                    type_confidence=type_conf,
                    context_text=context_text[:500],  # Limit context length
                    visual_hash=visual_hash,
                )
                elements.append(element)

            except Exception as e:
                console.print(
                    f"    [yellow]Warning: Failed to extract image {img_index} "
                    f"from page {page_num + 1}: {e}[/yellow]"
                )

        return elements

    def _get_image_bbox(
        self,
        page: fitz.Page,
        xref: int,
        img_info: tuple,
    ) -> tuple[float, float, float, float] | None:
        """Get bounding box of image on page.

        Note: PyMuPDF doesn't directly give us the image position,
        so we try to find it from the page's image list or blocks.
        """
        try:
            # Try to get from page blocks
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") == 1:  # Image block
                    bbox = block.get("bbox")
                    if bbox:
                        return tuple(bbox)

            # Fallback: estimate from image dimensions and page size
            page_rect = page.rect
            return (
                page_rect.x0,
                page_rect.y0,
                page_rect.x1,
                page_rect.y1 / 2,
            )  # Top half estimate

        except Exception:
            return None

    def _find_caption(
        self,
        page: fitz.Page,
        image_bbox: tuple | None,
        page_text: str,
        text_blocks: list,
    ) -> tuple[str, float]:
        """Find caption for image, prioritizing numbered figures.

        Strategy:
        1. First look for "Figure X:" patterns in the page text
        2. If multiple found, pick the one closest to the image
        3. If none found, look for text blocks below the image
        """
        candidates: list[CaptionCandidate] = []

        # First, look for numbered figure references
        for pattern in self.FIGURE_PATTERNS:
            for match in pattern.finditer(page_text):
                fig_num = match.group(1)
                caption_text = match.group(2) if match.lastindex >= 2 else ""

                # Clean up the caption text (get rest of sentence/paragraph)
                start_pos = match.end()
                end_pos = min(start_pos + 500, len(page_text))
                remaining = page_text[start_pos:end_pos]

                # Take text until double newline or period followed by newline
                end_match = re.search(r"\n\n|\.\s*\n", remaining)
                if end_match:
                    caption_text = caption_text + remaining[: end_match.start()]
                else:
                    caption_text = caption_text + remaining

                caption_text = caption_text.strip()
                full_caption = f"Figure {fig_num}: {caption_text}".strip()

                # Estimate distance from image
                distance = 50.0  # Default reasonable distance for matched patterns

                candidates.append(
                    CaptionCandidate(
                        text=full_caption[:500],  # Limit length
                        distance=distance,
                        is_numbered=True,
                        confidence=0.9 if len(caption_text) > 10 else 0.7,
                    )
                )

        # If no numbered captions, try proximity-based detection
        if not candidates and image_bbox:
            proximity_caption = self._find_proximity_caption(
                page, image_bbox, text_blocks
            )
            if proximity_caption:
                candidates.append(proximity_caption)

        # Sort: prioritize numbered, then by distance
        candidates.sort(key=lambda c: (not c.is_numbered, c.distance))

        if candidates:
            best = candidates[0]
            return best.text, best.confidence

        return "", 0.0

    def _find_proximity_caption(
        self,
        page: fitz.Page,
        image_bbox: tuple,
        text_blocks: list,
    ) -> CaptionCandidate | None:
        """Find caption based on spatial proximity to image.

        Searches both ABOVE and BELOW the image for captions,
        since many journals place captions above figures.
        """
        if not image_bbox:
            return None

        img_top = image_bbox[1]
        img_bottom = image_bbox[3]
        img_center_x = (image_bbox[0] + image_bbox[2]) / 2

        best_candidate: CaptionCandidate | None = None
        min_distance = float("inf")

        for block in text_blocks:
            if block.get("type") != 0:  # Not a text block
                continue

            block_bbox = block.get("bbox")
            if not block_bbox:
                continue

            # Check horizontal alignment
            block_center_x = (block_bbox[0] + block_bbox[2]) / 2
            horizontal_offset = abs(block_center_x - img_center_x)

            # Must be within 200 points horizontally
            if horizontal_offset > 200:
                continue

            distance = None

            # Look for text blocks BELOW the image
            if block_bbox[1] > img_bottom:
                distance = block_bbox[1] - img_bottom
            # Also look for text blocks ABOVE the image
            elif block_bbox[3] < img_top:
                distance = img_top - block_bbox[3]

            # Must be within 100 points vertically
            if distance is not None and distance < 100:
                # Extract text from block
                text_parts = []
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))
                text = " ".join(text_parts).strip()

                # Must have meaningful text
                if len(text) > 10 and distance < min_distance:
                    min_distance = distance
                    best_candidate = CaptionCandidate(
                        text=text[:500],  # Limit caption length
                        distance=distance,
                        is_numbered=False,
                        confidence=max(0.3, 0.8 - distance / 200),
                    )

        return best_candidate

    def _get_context_text(
        self,
        page: fitz.Page,
        image_bbox: tuple | None,
        text_blocks: list,
    ) -> str:
        """Get surrounding text for context and classification."""
        if not image_bbox:
            return page.get_text("text")[:1000]

        context_parts = []
        img_center_y = (image_bbox[1] + image_bbox[3]) / 2

        for block in text_blocks:
            if block.get("type") != 0:
                continue

            block_bbox = block.get("bbox")
            if not block_bbox:
                continue

            block_center_y = (block_bbox[1] + block_bbox[3]) / 2

            # Get text blocks within 200 points vertically
            if abs(block_center_y - img_center_y) < 200:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        context_parts.append(span.get("text", ""))

        return " ".join(context_parts)

    def _classify_image_type(
        self,
        caption: str,
        context_text: str,
    ) -> tuple[ImageType, float]:
        """Classify image type based on caption and context.

        Returns the detected type and confidence score.
        """
        combined_text = f"{caption} {context_text}".lower()

        scores: dict[ImageType, int] = {}
        for img_type, patterns in self.TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    score += 1
            if score > 0:
                scores[img_type] = score

        if not scores:
            return ImageType.UNKNOWN, 0.0

        best_type = max(scores, key=lambda t: scores[t])
        # Confidence based on number of matching patterns (logarithmic scale)
        # 1 match = 0.48, 2 = 0.63, 3 = 0.73, 4 = 0.81, 5+ = 0.87+
        confidence = min(1.0, 0.3 + 0.35 * math.log(scores[best_type] + 1))

        return best_type, confidence

    def _compute_visual_hash(self, image: Image.Image) -> str:
        """Compute perceptual hash for image deduplication.

        Uses average hash algorithm:
        1. Resize to 8x8
        2. Convert to grayscale
        3. Compare each pixel to average
        4. Generate 64-bit hash
        """
        try:
            # Resize to 8x8, convert to grayscale
            small = image.resize((8, 8), Image.LANCZOS).convert("L")
            pixels = list(small.getdata())
            avg = sum(pixels) / len(pixels)

            # Create hash based on pixels above/below average
            bits = "".join("1" if p > avg else "0" for p in pixels)
            return hex(int(bits, 2))[2:].zfill(16)
        except Exception:
            return ""

    def extract_figure_as_snapshot(
        self,
        page: fitz.Page,
        caption_rect: fitz.Rect,
        page_rect: fitz.Rect,
        zoom: float = 3.0,
        max_height: float = 400.0,
    ) -> bytes | None:
        """Render figure region as high-res PNG snapshot.

        This captures labels, arrows, and annotations that raw image
        extraction misses. The approach:
        1. Define clip region above the caption
        2. Render at high DPI using get_pixmap()
        3. Return PNG bytes

        Args:
            page: PyMuPDF page object
            caption_rect: Bounding box of the figure caption
            page_rect: Full page rectangle
            zoom: Render zoom factor (3.0 = 216 DPI)
            max_height: Maximum height above caption to capture

        Returns:
            PNG image bytes or None if extraction fails
        """
        try:
            # Define clip area: from caption top, scan upward
            clip_rect = fitz.Rect(
                page_rect.x0,
                max(0, caption_rect.y0 - max_height),  # Up to max_height above caption
                page_rect.x1,
                caption_rect.y0,  # Stop at caption top
            )

            # Render to pixmap at high resolution
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, clip=clip_rect)

            # Skip if too small (likely false positive)
            if pix.width < 100 or pix.height < 50:
                return None

            # Convert to PNG bytes
            return pix.tobytes("png")

        except Exception as e:
            console.print(f"    [yellow]Snapshot extraction failed: {e}[/yellow]")
            return None

    async def extract_images_hybrid(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Extract images using hybrid approach: raw + snapshot.

        Combines:
        1. Raw image extraction (fast, catches embedded images)
        2. Snapshot rendering (accurate, captures labels/arrows)

        Deduplicates using perceptual hashing.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images

        Returns:
            Combined list of VisualElement objects
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._extract_images_hybrid_sync(pdf_path, output_dir)
        )

    def _extract_images_hybrid_sync(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> list[VisualElement]:
        """Synchronous hybrid extraction implementation."""
        visual_elements: list[VisualElement] = []
        seen_hashes: set[str] = set()

        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with fitz.open(pdf_path) as pdf:
                for page_num in range(len(pdf)):
                    page = pdf[page_num]

                    # 1. Raw extraction (existing method)
                    raw_images = self._extract_page_images(
                        page, page_num, pdf_path, output_dir, pdf
                    )

                    # Track hashes to avoid duplicates
                    for elem in raw_images:
                        if elem.visual_hash:
                            seen_hashes.add(elem.visual_hash)
                    visual_elements.extend(raw_images)

                    # 2. Snapshot extraction for figure captions
                    snapshot_images = self._extract_page_snapshots(
                        page, page_num, pdf_path, output_dir, seen_hashes
                    )
                    visual_elements.extend(snapshot_images)

        except Exception as e:
            console.print(f"[red]Error in hybrid extraction {pdf_path.name}: {e}[/red]")
            return []

        if visual_elements:
            console.print(
                f"  [green]Hybrid extracted {len(visual_elements)} images from {pdf_path.name}[/green]"
            )

        return visual_elements

    def _extract_page_snapshots(
        self,
        page: fitz.Page,
        page_num: int,
        pdf_path: Path,
        output_dir: Path,
        seen_hashes: set[str],
    ) -> list[VisualElement]:
        """Extract figure snapshots by rendering regions above captions."""
        elements: list[VisualElement] = []
        page_text = page.get_text("text")
        page_rect = page.rect

        # Find figure captions
        for pattern in self.FIGURE_PATTERNS:
            for match in pattern.finditer(page_text):
                fig_num = match.group(1)
                caption_text = match.group(2) if match.lastindex >= 2 else ""

                # Find caption location on page
                search_text = match.group(0)[:50]  # First 50 chars
                caption_instances = page.search_for(search_text)
                if not caption_instances:
                    continue

                caption_rect = caption_instances[0]

                # Render snapshot
                png_bytes = self.extract_figure_as_snapshot(
                    page, caption_rect, page_rect, zoom=3.0, max_height=400.0
                )
                if not png_bytes:
                    continue

                # Check for duplicates via perceptual hash
                try:
                    pil_img = Image.open(io.BytesIO(png_bytes))
                    visual_hash = self._compute_visual_hash(pil_img)
                    width, height = pil_img.size

                    # Skip if already seen (from raw extraction)
                    if visual_hash in seen_hashes:
                        continue
                    seen_hashes.add(visual_hash)

                except Exception:
                    continue

                # Save snapshot image
                image_filename = f"{pdf_path.stem}_fig{fig_num}_p{page_num + 1}.png"
                image_path = output_dir / image_filename

                counter = 1
                while image_path.exists():
                    image_filename = (
                        f"{pdf_path.stem}_fig{fig_num}_p{page_num + 1}_{counter}.png"
                    )
                    image_path = output_dir / image_filename
                    counter += 1

                image_path.write_bytes(png_bytes)

                # Get context and classify
                context_text = page_text[:500]
                full_caption = f"Figure {fig_num}: {caption_text}".strip()
                image_type, type_conf = self._classify_image_type(
                    full_caption, context_text
                )

                element = VisualElement(
                    image_path=image_path,
                    format="png",
                    width=width,
                    height=height,
                    source_pdf=pdf_path,
                    page_number=page_num + 1,
                    bbox=(
                        caption_rect.x0,
                        caption_rect.y0 - 400,
                        caption_rect.x1,
                        caption_rect.y0,
                    ),
                    caption=full_caption[:500],
                    caption_confidence=0.95,  # High confidence (found by pattern)
                    image_type=image_type,
                    type_confidence=type_conf,
                    context_text=context_text,
                    visual_hash=visual_hash,
                )
                elements.append(element)

        return elements


async def extract_images_from_pdf(
    pdf_path: Path,
    output_dir: Path | None = None,
) -> list[VisualElement]:
    """Convenience function to extract images from a PDF.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Optional directory to save extracted images

    Returns:
        List of VisualElement objects
    """
    extractor = ImageExtractor()
    return await extractor.extract_images(pdf_path, output_dir)


async def extract_images_hybrid(
    pdf_path: Path,
    output_dir: Path | None = None,
) -> list[VisualElement]:
    """Extract images using hybrid approach (raw + snapshot).

    This provides better accuracy by combining:
    1. Raw image extraction (fast, catches embedded images)
    2. Snapshot rendering (captures labels, arrows, annotations)

    Args:
        pdf_path: Path to the PDF file
        output_dir: Optional directory to save extracted images

    Returns:
        List of VisualElement objects (deduplicated)
    """
    extractor = ImageExtractor()
    return await extractor.extract_images_hybrid(pdf_path, output_dir)
