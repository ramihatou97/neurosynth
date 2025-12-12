"""
OCR Caption Extractor for NeuroSynth
=====================================
Extract text from medical images using OCR for caption enhancement.

Supports multiple backends with graceful fallback:
1. pytesseract (requires tesseract-ocr installed)
2. easyocr (pure Python, GPU-optional)

Version: 1.0
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("OCRCaptionExtractor")

# Try to import OCR backends
TESSERACT_AVAILABLE = False
EASYOCR_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    easyocr = None


class OCRCaptionExtractor:
    """
    Extract captions and text from medical images using OCR.

    Prioritizes pytesseract for speed, falls back to easyocr if unavailable.
    """

    # Caption patterns to look for in OCR text
    CAPTION_PATTERNS = [
        r"(?:Fig(?:ure)?\.?\s*(\d+[A-Za-z]?))[:\s\-\.]+(.+)",
        r"(?:Figure\s+(\d+[A-Za-z]?))[:\s\-\.]+(.+)",
        r"^([A-Z])\.\s+(.+)",  # Subfigure labels like "A. Description"
        r"^Step\s*(\d+)[:\s\-\.]+(.+)",
    ]

    def __init__(
        self,
        backend: str = "auto",
        timeout_seconds: int = 5,
        language: str = "eng",
    ):
        """
        Initialize the OCR extractor.

        Args:
            backend: OCR backend ("auto", "tesseract", "easyocr")
            timeout_seconds: Timeout per image (applies to tesseract)
            language: OCR language code
        """
        self.timeout_seconds = timeout_seconds
        self.language = language
        self.backend = self._select_backend(backend)
        self._easyocr_reader = None

        if not self.backend:
            logger.warning("No OCR backend available. Install pytesseract or easyocr.")

    def _select_backend(self, preference: str) -> str | None:
        """Select the best available OCR backend."""
        if preference == "tesseract" and TESSERACT_AVAILABLE:
            return "tesseract"
        elif preference == "easyocr" and EASYOCR_AVAILABLE:
            return "easyocr"
        elif preference == "auto":
            # Prefer tesseract for speed
            if TESSERACT_AVAILABLE:
                return "tesseract"
            elif EASYOCR_AVAILABLE:
                return "easyocr"
        return None

    def extract_text(self, image_path: Path) -> str:
        """
        Extract all text from an image using OCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text, or empty string if failed
        """
        if not self.backend:
            return ""

        image_path = Path(image_path)
        if not image_path.exists():
            return ""

        try:
            if self.backend == "tesseract":
                return self._extract_tesseract(image_path)
            elif self.backend == "easyocr":
                return self._extract_easyocr(image_path)
        except Exception as e:
            logger.debug(f"OCR extraction failed for {image_path}: {e}")

        return ""

    def _extract_tesseract(self, image_path: Path) -> str:
        """Extract text using pytesseract."""
        img = Image.open(image_path)
        # Use timeout config
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(
            img, lang=self.language, config=config, timeout=self.timeout_seconds
        )
        return text.strip()

    def _extract_easyocr(self, image_path: Path) -> str:
        """Extract text using easyocr."""
        if self._easyocr_reader is None:
            # Lazy initialization (slow first call)
            self._easyocr_reader = easyocr.Reader([self.language], gpu=False)

        results = self._easyocr_reader.readtext(str(image_path))
        # Combine all detected text blocks
        text_parts = [r[1] for r in results]
        return " ".join(text_parts).strip()

    def extract_caption(self, image_path: Path) -> dict | None:
        """
        Extract and parse caption from image OCR text.

        Args:
            image_path: Path to the image file

        Returns:
            Dict with 'text', 'figure_number', 'caption_text' if found
        """
        raw_text = self.extract_text(image_path)
        if not raw_text:
            return None

        result = {"text": raw_text, "figure_number": "", "caption_text": ""}

        # Try to parse structured caption
        for pattern in self.CAPTION_PATTERNS:
            match = re.search(pattern, raw_text, re.MULTILINE | re.IGNORECASE)
            if match:
                result["figure_number"] = match.group(1)
                result["caption_text"] = match.group(2).strip()
                break

        return result
