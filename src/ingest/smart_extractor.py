import fitz  # PyMuPDF

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartExtractor")


@dataclass
class ExtractedFigure:
    source_pdf: str
    image_filename: str
    local_path: Path
    caption: str
    context: str
    page_num: int
    image_type: str = "unknown"


class SmartImageExtractor:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not pymupdf4llm:
            logger.warning(
                "pymupdf4llm not installed. Smart extraction will be limited."
            )

    def process_pdf(
        self, pdf_path: str, pages: Optional[list[int]] = None
    ) -> list[ExtractedFigure]:
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

        figures = self._parse_markdown_content(md_text, pdf_path, temp_img_dir)

        # Cleanup temp dir (all valid images were moved/copied)
        try:
            shutil.rmtree(temp_img_dir)
        except Exception:
            pass

        return figures

    def _parse_markdown_content(
        self, md_text: str, source_pdf: Path, temp_img_dir: Path
    ) -> list[ExtractedFigure]:
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

                # Quality Gate: Entropy Filtering
                if not self._is_medically_relevant(temp_img_path):
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
                        l.strip()
                        for l in context_lines
                        if l.strip() and not img_pattern.search(l)
                    ]
                )

                # Attempt to find a real caption in the context (Figure 1: ...)
                caption = self._extract_caption(clean_context)

                # Fallback to alt_text or generic
                final_caption = caption or alt_text or f"Image from {source_pdf.name}"

                figures.append(
                    ExtractedFigure(
                        source_pdf=source_pdf.name,
                        image_filename=final_path.name,
                        local_path=final_path,
                        caption=final_caption,
                        context=clean_context,
                        page_num=0,  # pymupdf4llm doesn't give page nums easily, would need mapping
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

    def _extract_caption(self, text: str) -> Optional[str]:
        # Regex to find "Fig. 1", "Figure 2", "Plate 3"
        match = re.search(r"(Fig(ure)?\.?\s?\d+[:.]?.*?)(\.|$)", text, re.IGNORECASE)
        return match.group(0) if match else None
