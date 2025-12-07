"""
Image Extractor

Extracts images from PDFs with their context (captions, surrounding text).
Classifies images by type for intelligent selection.
"""

import hashlib
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from config import settings
from models import ExtractedImage, ImageType
from PIL import Image


class ImageExtractor:
    """
    Extracts and processes images from PDF documents.

    Features:
    - Extract images with surrounding context
    - Classify image types (anatomy, surgical, imaging, etc.)
    - Filter out noise (logos, icons, decorations)
    - Preserve image quality
    """

    # Minimum dimensions to consider an image meaningful
    # Relaxed for neuroanatomy: narrow strips (spinal tracts) can be 70px
    MIN_WIDTH = 70
    MIN_HEIGHT = 70

    # Keywords for image type classification (found in captions/surrounding text)
    TYPE_KEYWORDS = {
        ImageType.ANATOMY_DIAGRAM: [
            "anatomy",
            "anatomic",
            "nerve",
            "artery",
            "vein",
            "muscle",
            "bone",
            "structure",
            "relationship",
            "course",
            "origin",
            "insertion",
        ],
        ImageType.SURGICAL_PHOTO: [
            "intraoperative",
            "operative",
            "surgical field",
            "exposure",
            "dissection",
            "retraction",
            "microsurgical",
            "view of",
        ],
        ImageType.IMAGING_MRI: [
            "mri",
            "magnetic resonance",
            "t1",
            "t2",
            "flair",
            "weighted",
        ],
        ImageType.IMAGING_CT: [
            "ct",
            "computed tomography",
            "scan",
            "axial",
            "coronal",
            "sagittal",
        ],
        ImageType.IMAGING_ANGIO: [
            "angiogram",
            "angiography",
            "arteriogram",
            "dsa",
            "catheter",
        ],
        ImageType.DIAGRAM: [
            "diagram",
            "schematic",
            "algorithm",
            "flowchart",
            "decision",
        ],
        ImageType.HISTOLOGY: [
            "histology",
            "pathology",
            "h&e",
            "stain",
            "microscopy",
            "specimen",
        ],
    }

    # Caption patterns to find figure labels
    CAPTION_PATTERNS = [
        r"(?:Figure|Fig\.?|FIGURE)\s*(\d+[\.\-]?\d*)",
        r"(?:Plate|PLATE)\s*(\d+[\.\-]?\d*)",
    ]

    def extract_all(
        self, doc: fitz.Document, source_id: str, pdf_path: Path
    ) -> list[ExtractedImage]:
        """
        Extract all meaningful images from a document.

        Args:
            doc: PyMuPDF document object
            source_id: ID of the source document
            pdf_path: Path to original PDF (for output directory naming)

        Returns:
            List of ExtractedImage objects
        """
        images = []
        output_dir = settings.processed_path / source_id / "images"
        output_dir.mkdir(parents=True, exist_ok=True)

        for page_num, page in enumerate(doc):
            page_images = self._extract_from_page(
                page=page,
                page_num=page_num,
                doc=doc,
                source_id=source_id,
                output_dir=output_dir,
            )
            images.extend(page_images)

        return images

    def _extract_from_page(
        self,
        page: fitz.Page,
        page_num: int,
        doc: fitz.Document,
        source_id: str,
        output_dir: Path,
    ) -> list[ExtractedImage]:
        """Extract images from a single page"""
        images = []
        page_text = page.get_text("text")

        # Get all images on the page
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            try:
                extracted = self._process_image(
                    page=page,
                    page_num=page_num,
                    img_info=img_info,
                    img_index=img_index,
                    page_text=page_text,
                    source_id=source_id,
                    output_dir=output_dir,
                    doc=doc,
                )
                if extracted:
                    images.append(extracted)
            except Exception as e:
                # Skip problematic images
                continue

        return images

    def _process_image(
        self,
        page: fitz.Page,
        page_num: int,
        img_info: tuple,
        img_index: int,
        page_text: str,
        source_id: str,
        output_dir: Path,
        doc: fitz.Document,
    ) -> Optional[ExtractedImage]:
        """Process a single image"""
        xref = img_info[0]

        # Extract image data
        base_image = doc.extract_image(xref)
        if not base_image:
            return None

        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        width = base_image["width"]
        height = base_image["height"]

        # Filter out small images (likely icons/decorations)
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            return None

        # Filter out very thin images (likely lines/borders)
        # Relaxed to 8:1 for panoramic surgical views
        aspect_ratio = width / height if height > 0 else 0
        if aspect_ratio > 8 or aspect_ratio < 0.125:
            return None

        # Generate image ID
        image_hash = hashlib.md5(image_bytes).hexdigest()[:8]
        image_id = f"{source_id}_p{page_num}_i{img_index}_{image_hash}"

        # Save image
        image_filename = f"{image_id}.{image_ext}"
        image_path = output_dir / image_filename

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Get context (caption and surrounding text)
        caption, surrounding = self._get_image_context(page, page_text, img_index)

        # Classify image type
        image_type = self._classify_image(caption, surrounding)

        return ExtractedImage(
            id=image_id,
            source_id=source_id,
            page=page_num,
            file_path=image_path,
            caption=caption,
            surrounding_text=surrounding,
            image_type=image_type,
            width=width,
            height=height,
        )

    def _get_image_context(
        self, page: fitz.Page, page_text: str, img_index: int
    ) -> tuple[str, str]:
        """
        Extract caption and surrounding text for an image.

        Returns:
            (caption, surrounding_text)
        """
        # Try to find figure caption
        caption = ""
        for pattern in self.CAPTION_PATTERNS:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                # Get text following the figure reference
                start = match.start()
                end = min(start + 500, len(page_text))
                potential_caption = page_text[start:end]

                # Clean up caption (take until next paragraph or figure reference)
                lines = potential_caption.split("\n")
                caption_lines = []
                for line in lines[:5]:  # Max 5 lines
                    line = line.strip()
                    if line and not re.match(r"^(?:Figure|Fig|FIGURE)", line):
                        caption_lines.append(line)
                    elif caption_lines:
                        break

                if caption_lines:
                    caption = f"{match.group(0)}: " + " ".join(caption_lines)
                    break
            if caption:
                break

        # Get surrounding text (context for relevance matching)
        # Take ~500 chars around the middle of the page
        mid_point = len(page_text) // 2
        start = max(0, mid_point - 250)
        end = min(len(page_text), mid_point + 250)
        surrounding = page_text[start:end].strip()

        return caption, surrounding

    def _classify_image(self, caption: str, surrounding: str) -> ImageType:
        """
        Classify image type based on caption and surrounding text.
        """
        context = (caption + " " + surrounding).lower()

        # Score each type
        scores = {}
        for img_type, keywords in self.TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in context)
            if score > 0:
                scores[img_type] = score

        if scores:
            return max(scores, key=scores.get)

        # Default to illustration
        return ImageType.ILLUSTRATION

    def filter_images(
        self,
        images: list[ExtractedImage],
        preferred_types: Optional[list[ImageType]] = None,
        min_size: int = 200,
    ) -> list[ExtractedImage]:
        """
        Filter images based on criteria.

        Args:
            images: List of images to filter
            preferred_types: Only include these types
            min_size: Minimum dimension (width or height)

        Returns:
            Filtered list of images
        """
        filtered = []

        for img in images:
            # Size filter
            if img.width < min_size and img.height < min_size:
                continue

            # Type filter
            if preferred_types and img.image_type not in preferred_types:
                continue

            filtered.append(img)

        return filtered
