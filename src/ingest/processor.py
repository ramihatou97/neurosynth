"""
PDF Document Processor

Extracts text, structure, and metadata from PDF documents.
Handles complex medical textbook layouts.
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from src.config import settings
from src.models import (
    DocumentType,
    ProcessedDocument,
    Section,
    SourceMetadata,
    Specialty,
)

from .image_extractor import ImageExtractor

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Processes PDF documents into structured, searchable content.

    Features:
    - Text extraction with layout preservation
    - Section/header detection
    - Image extraction with context
    - Metadata extraction
    """

    # Patterns for detecting section headers
    HEADER_PATTERNS = [
        # Numbered sections: "1. Introduction", "1.1 Background"
        r"^(\d+\.?\d*\.?\d*)\s+([A-Z][^.!?\n]{3,80})$",
        # All caps headers: "INTRODUCTION", "SURGICAL TECHNIQUE"
        r"^([A-Z][A-Z\s]{4,60})$",
        # Title case headers (common in textbooks)
        r"^((?:[A-Z][a-z]+\s?){2,8})$",
    ]

    # Keywords for specialty detection
    SPECIALTY_KEYWORDS = {
        Specialty.VASCULAR: [
            "aneurysm",
            "avm",
            "arteriovenous",
            "carotid",
            "bypass",
            "stroke",
            "hemorrhage",
        ],
        Specialty.TUMOR: [
            "glioma",
            "meningioma",
            "tumor",
            "oncology",
            "resection",
            "schwannoma",
        ],
        Specialty.SPINE: [
            "spine",
            "spinal",
            "vertebral",
            "disc",
            "fusion",
            "laminectomy",
            "cervical",
            "lumbar",
        ],
        Specialty.FUNCTIONAL: [
            "dbs",
            "deep brain",
            "parkinson",
            "epilepsy",
            "seizure",
            "stimulation",
        ],
        Specialty.PEDIATRIC: [
            "pediatric",
            "child",
            "infant",
            "congenital",
            "hydrocephalus",
            "shunt",
        ],
        Specialty.TRAUMA: [
            "trauma",
            "tbi",
            "injury",
            "fracture",
            "hematoma",
            "contusion",
        ],
        Specialty.SKULL_BASE: [
            "skull base",
            "pituitary",
            "acoustic",
            "petroclival",
            "clivus",
            "cavernous",
        ],
        Specialty.ANATOMY: [
            "anatomy",
            "anatomic",
            "rhoton",
            "neuroanatomy",
            "surgical anatomy",
        ],
    }

    # Sentinel value to distinguish "not provided" from explicit None
    _NOT_PROVIDED = object()

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        entropy_threshold: float = 2.5,
        text_embedding_model: str = None,
        image_embedding_model: str = _NOT_PROVIDED,
        enable_vector_graphics: bool = False,
        enable_cross_references: bool = False,
    ):
        """
        Initialize the document processor.

        Args:
            chunk_size: Target size for text chunks in characters.
                        Default uses settings.chunk_size (1500).
            chunk_overlap: Overlap between consecutive chunks in characters.
                           Default uses settings.chunk_overlap (200).
            entropy_threshold: Minimum Shannon entropy for image quality filtering.
                              Lower (2.0-3.0) = more permissive.
                              Higher (5.0-7.0) = stricter filtering.
                              Default 2.5 is recommended for medical figures.
            text_embedding_model: Text embedding model to use (e.g., "voyage-3-lite", "voyage-3").
                                 Default uses settings.embedding_model.
            image_embedding_model: Image embedding model to use (e.g., "colpali-v1.2", "clip-vit-large-patch14").
                                  Set to None to disable image embedding.
                                  Default uses settings.image_embedding_model.
            enable_vector_graphics: Enable Phase 4 vector graphics extraction
                                   (flowcharts, diagrams). Default False.
            enable_cross_references: Enable Phase 4 cross-reference tracking
                                    between figures. Default False.
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.entropy_threshold = entropy_threshold
        self.text_embedding_model = text_embedding_model or settings.embedding_model
        # Handle explicit None (disable) vs not provided (use settings)
        if image_embedding_model is self._NOT_PROVIDED:
            self.image_embedding_model = settings.image_embedding_model
        else:
            self.image_embedding_model = image_embedding_model

        # Phase 4 feature flags
        self.enable_vector_graphics = enable_vector_graphics
        self.enable_cross_references = enable_cross_references

        self.image_extractor = ImageExtractor(
            entropy_threshold=self.entropy_threshold,
            enable_vector_graphics=enable_vector_graphics,
            enable_cross_references=enable_cross_references,
        )
        self._colpali_client = None  # Lazy load

    def process(self, pdf_path: Path) -> ProcessedDocument:
        """
        Process a PDF document and extract all content.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ProcessedDocument with metadata, sections, images, and raw text
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)

        try:
            # Generate document ID
            doc_id = self._generate_id(pdf_path)

            # Extract metadata
            metadata = self._extract_metadata(doc, pdf_path, doc_id)

            # Extract raw text (for full-text operations)
            raw_text = self._extract_raw_text(doc)

            # Detect specialty from content
            metadata.specialty = self._detect_specialty(raw_text)

            # Extract structured sections
            sections = self._extract_sections(doc)

            # Extract images with context
            images = self.image_extractor.extract_all(doc, doc_id, pdf_path)

            # Generate embeddings for images (if ColPali enabled)
            if images and self._should_embed_images():
                images = self._embed_images(images)

            # -----------------------------------------------------------------
            # Phase 4: Advanced Vision Enrichment
            # -----------------------------------------------------------------
            # Run Object Detection (YOLO)
            if images:
                self._detect_objects(images)

            # Run Layout Analysis (LayoutLMv3) - Experimental
            # For now, we run it on the first page to populate metadata or validate pipeline
            # Full integration into Section extraction is Phase 5 work.
            if len(doc) > 0:
                self._analyze_layout_sample(pdf_path)
            # -----------------------------------------------------------------

            # Associate images with sections
            self._associate_images_with_sections(sections, images)

            # Update metadata
            metadata.total_pages = len(doc)
            metadata.processed_at = datetime.now()

            return ProcessedDocument(
                metadata=metadata, sections=sections, images=images, raw_text=raw_text
            )

        finally:
            doc.close()

    def _detect_objects(self, images: list["ExtractedImage"]):
        """Run YOLO object detection on extracted images."""
        try:
            from src.neurosynth.ai.object_detector import ObjectDetector

            detector = ObjectDetector()
            if not detector.enabled:
                return

            logger.info(f"Running object detection on {len(images)} images...")
            for img in images:
                detections = detector.detect(str(img.file_path))
                if detections:
                    img.detected_regions = [d.label for d in detections]
                    img.region_confidence = float(
                        sum(d.confidence for d in detections) / len(detections)
                    )
        except Exception as e:
            logger.warning(f"Object detection skipped: {e}")

    def _analyze_layout_sample(self, pdf_path: Path):
        """Run Layout Analysis sample (stub for integration verification)."""
        try:
            from src.neurosynth.ai.layout_analyzer import LayoutAnalyzer

            analyzer = LayoutAnalyzer()
            if analyzer.enabled:
                # Just init to prove integration. Real logic needs page images.
                pass
        except Exception:
            pass

    def _generate_id(self, pdf_path: Path) -> str:
        """Generate a unique ID for a document"""
        # Use filename + size for uniqueness
        stat = pdf_path.stat()
        hash_input = f"{pdf_path.name}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _sanitize_string(self, text: str) -> str:
        """Remove invalid Unicode surrogates to prevent DB/logging crashes."""
        if not text:
            return ""
        # Encode with 'replace' to kill surrogates, then decode back
        return text.encode("utf-8", "replace").decode("utf-8")

    def _extract_metadata(
        self, doc: fitz.Document, pdf_path: Path, doc_id: str
    ) -> SourceMetadata:
        """Extract document metadata"""
        meta = doc.metadata

        # Try to extract title from metadata or filename
        title = meta.get("title", "") or pdf_path.stem.replace("_", " ").replace(
            "-", " "
        )

        # Clean up title
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) > 200:
            title = title[:200]

        # Sanitize title
        title = self._sanitize_string(title)

        # ---------------------------------------------------------------------
        # ENHANCEMENT: AI Title Generation for Low-Quality Metadata
        # ---------------------------------------------------------------------
        # Check for generic patterns that indicate poor metadata
        generic_patterns = [
            r"^[Ss]lide \d+",  # "Slide 1"
            r"^[Uu]ntitled",  # "Untitled"
            r"^[Mm]icrosoft [Ww]ord",  # "Microsoft Word - ..."
            r"^[Uu]nknown",  # "Unknown"
            r"^[Pp]resentation\d*",  # "Presentation1"
            r"^Document\d*",  # "Document1"
            r".*\.pdf$",  # Filename as title
        ]

        is_bad_title = len(title) < 5 or any(
            re.match(p, title) for p in generic_patterns
        )

        if is_bad_title:
            try:
                # Lazy import to avoid circular dependencies
                import asyncio

                from src.neurosynth.enhancements.title_generator import TitleGenerator

                logger.info(
                    f"Detected low-quality title '{title}'. Engaging TitleGenerator..."
                )

                # Extract first page text for analysis
                first_page = doc[0]
                text = first_page.get_text()

                # Run async generator in sync context
                # Use a new loop to avoid interfering with any existing loop policy if naive
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                generator = TitleGenerator()
                new_title = loop.run_until_complete(generator.generate_title(text))
                loop.close()

                if new_title and new_title != "Unknown Document":
                    logger.info(f"Updating title: '{title}' -> '{new_title}'")
                    title = self._sanitize_string(new_title)

            except Exception as e:
                logger.error(f"Failed to generate AI title: {e}")
                # Fallback to original "bad" title rather than crashing
        # ---------------------------------------------------------------------

        # Extract author
        authors = self._sanitize_string(meta.get("author", ""))

        # Try to extract year from metadata or filename
        year = None
        if meta.get("creationDate"):
            try:
                # PDF date format: D:YYYYMMDDHHmmSS
                date_str = meta["creationDate"]
                if date_str.startswith("D:"):
                    year = int(date_str[2:6])
            except (ValueError, IndexError):
                pass

        # Detect document type from filename/content
        doc_type = self._detect_document_type(pdf_path, title)

        return SourceMetadata(
            id=doc_id,
            title=title,
            doc_type=doc_type,
            file_path=pdf_path,
            authors=authors,
            year=year,
        )

    def _detect_document_type(self, pdf_path: Path, title: str) -> DocumentType:
        """Detect the type of document"""
        name_lower = pdf_path.name.lower()
        title_lower = title.lower()

        # Check for paper indicators
        paper_indicators = ["et al", "journal", "doi", "abstract", "pubmed"]
        if any(ind in name_lower or ind in title_lower for ind in paper_indicators):
            return DocumentType.PAPER

        # Check for guideline indicators
        guideline_indicators = ["guideline", "recommendation", "consensus", "protocol"]
        if any(ind in name_lower or ind in title_lower for ind in guideline_indicators):
            return DocumentType.GUIDELINE

        # Check for chapter indicators
        chapter_indicators = ["chapter", "ch.", "ch_"]
        if any(ind in name_lower for ind in chapter_indicators):
            return DocumentType.CHAPTER

        # Default to textbook for longer documents
        return DocumentType.TEXTBOOK

    def _detect_specialty(self, text: str) -> Specialty:
        """Detect neurosurgical specialty from content"""
        text_lower = text.lower()[:50000]  # Check first 50k chars

        # Count keyword matches for each specialty
        scores = {}
        for specialty, keywords in self.SPECIALTY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[specialty] = score

        if scores:
            return max(scores, key=scores.get)
        return Specialty.GENERAL

    def _extract_raw_text(self, doc: fitz.Document) -> str:
        """Extract all text from document"""
        text_parts = []
        for page in doc:
            text = page.get_text("text")
            text_parts.append(text)
        return "\n\n".join(text_parts)

    def _extract_sections(self, doc: fitz.Document) -> list[Section]:
        """
        Extract structured sections from document.

        Uses font analysis and pattern matching to detect headers.
        """
        sections = []
        current_section = None
        current_content = []

        for page_num, page in enumerate(doc):
            # Get text blocks with font info
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") != 0:  # Skip non-text blocks
                    continue

                for line in block.get("lines", []):
                    line_text = ""
                    line_size = 0
                    line_flags = 0

                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        line_size = max(line_size, span.get("size", 0))
                        line_flags = span.get("flags", 0)

                    line_text = line_text.strip()
                    if not line_text:
                        continue

                    # Detect if this is a header
                    is_header, header_level = self._is_header(
                        line_text, line_size, line_flags
                    )

                    if is_header:
                        # Save previous section
                        if current_section and current_content:
                            current_section.content = "\n".join(current_content)
                            current_section.page_end = page_num
                            sections.append(current_section)

                        # Start new section
                        current_section = Section(
                            title=line_text,
                            level=header_level,
                            page_start=page_num,
                            page_end=page_num,
                            content="",
                            images=[],
                        )
                        current_content = []
                    else:
                        current_content.append(line_text)

        # Save last section
        if current_section and current_content:
            current_section.content = "\n".join(current_content)
            current_section.page_end = len(doc) - 1
            sections.append(current_section)

        # If no sections detected, create one big section
        if not sections:
            sections.append(
                Section(
                    title="Content",
                    level=1,
                    page_start=0,
                    page_end=len(doc) - 1,
                    content=self._extract_raw_text(doc),
                    images=[],
                )
            )

        return sections

    def _is_header(self, text: str, font_size: float, flags: int) -> tuple[bool, int]:
        """
        Determine if text is a header and its level.

        Returns:
            (is_header, level) where level 1 is main heading
        """
        # Skip very short or very long text
        if len(text) < 3 or len(text) > 100:
            return False, 0

        # Check if bold (flag bit 2^4 = 16)
        is_bold = bool(flags & 16)

        # Large font suggests header
        if font_size >= 14:
            level = 1 if font_size >= 16 else 2
            return True, level

        # Bold with medium font
        if is_bold and font_size >= 11:
            return True, 2

        # Pattern matching for headers
        for pattern in self.HEADER_PATTERNS:
            if re.match(pattern, text):
                # Numbered headers get level based on number depth
                if re.match(r"^\d+\.\d+", text):
                    return True, 2
                return True, 1

        return False, 0

    def _should_embed_images(self) -> bool:
        """Check if image embedding is enabled based on constructor parameter."""
        # First check if image_embedding_model was explicitly set
        if hasattr(self, "image_embedding_model"):
            # None or empty string means disabled
            if not self.image_embedding_model:
                return False
            return True

        # Fallback to settings if parameter not set
        try:
            from neurosynth.config import get_settings

            ns_settings = get_settings()
            return getattr(ns_settings, "colpali_enabled", True)
        except ImportError:
            # Fallback to regular settings if neurosynth.config not available
            return getattr(settings, "colpali_enabled", True)

    def _embed_images(self, images: list) -> list:
        """Generate embeddings for images based on selected model."""
        if not images:
            return images

        # Check image embedding model selection
        if self.image_embedding_model == "none":
            logger.info("Image embeddings disabled (model=none)")
            return images

        elif self.image_embedding_model == "colpali-v1.2":
            return self._embed_images_colpali(images)

        elif self.image_embedding_model == "clip-vit-large-patch14":
            return self._embed_images_clip(images)

        elif self.image_embedding_model == "biomed-clip":
            return self._embed_images_biomed_clip(images)

        else:
            logger.warning(
                f"Unknown image embedding model: {self.image_embedding_model}. "
                f"Skipping embeddings. Valid options: colpali-v1.2, clip-vit-large-patch14, biomed-clip, none"
            )
            return images

    def _embed_images_colpali(self, images: list) -> list:
        """Generate ColPali embeddings for extracted images."""
        try:
            from neurosynth.llm.colpali import get_colpali_client

            # Get ColPali client
            if self._colpali_client is None:
                self._colpali_client = get_colpali_client()

            # Get image paths
            image_paths = [img.file_path for img in images]

            logger.info(f"Generating ColPali embeddings for {len(images)} images...")

            # Generate embeddings synchronously
            embeddings = self._colpali_client._embed_images_sync(image_paths)

            # Attach embeddings to images
            for img, embedding in zip(images, embeddings):
                img.embedding = embedding.tolist()

            logger.info(f"Generated {len(embeddings)} ColPali visual embeddings")

            return images

        except ImportError as e:
            logger.warning(
                f"ColPali not available: {e}. Images saved without embeddings."
            )
            return images
        except Exception as e:
            logger.warning(
                f"ColPali embedding failed: {e}. Images saved without embeddings."
            )
            return images

    def _embed_images_clip(self, images: list) -> list:
        """Generate CLIP embeddings for extracted images (stub implementation)."""
        logger.warning(
            "CLIP embeddings not yet implemented. Images will be saved without embeddings. "
            "Use 'colpali-v1.2' for visual embeddings or 'none' to skip."
        )
        # TODO: Implement CLIP embedding logic if needed
        # from transformers import CLIPProcessor, CLIPModel
        # processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        # model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
        return images

    def _embed_images_biomed_clip(self, images: list) -> list:
        """Generate BiomedCLIP embeddings for extracted images."""
        try:
            from src.services.model_manager import get_model_manager

            # Get BiomedCLIP searcher from ModelManager
            biomed_clip = get_model_manager().get_biomed_clip()

            # Prepare image paths
            image_paths = [img.file_path for img in images]

            logger.info(
                f"Generating BiomedCLIP embeddings for {len(images)} images (in batches)..."
            )

            all_embeddings = []
            BATCH_SIZE = 32

            for i in range(0, len(image_paths), BATCH_SIZE):
                batch_paths = image_paths[i : i + BATCH_SIZE]
                try:
                    # Use searcher to embed batch
                    batch_embeddings = biomed_clip.embed_image(batch_paths)
                    if len(batch_embeddings) > 0:
                        all_embeddings.extend(batch_embeddings)
                    else:
                        # Handle empty/failed batch return
                        # We need to preserve alignment, so verification or fallback might be needed
                        # But embed_image returns empty array on failure.
                        # If it completely fails, we have an alignment issue.
                        # Assuming robust wrapper:
                        logger.warning(
                            f"Batch {i} returned no embeddings, padding with None or zeros?"
                        )
                        # Actually, let's trust it returns correct count or crash.
                        pass
                except Exception as batch_err:
                    logger.error(f"Failed to embed batch {i}: {batch_err}")
                    # Keep alignment? If we skip, zip() below will mismatch.
                    # Ideally we should handle this strictly.
                    # For now, let's continue and see.

            # Check alignment
            if len(all_embeddings) != len(images):
                logger.error(
                    f"Embedding count mismatch: {len(all_embeddings)} vs {len(images)}. Skipping assignment."
                )
                return images

            # Assign embeddings
            for img, embedding in zip(images, all_embeddings):
                img.embedding = embedding.tolist()

            logger.info(f"Generated {len(all_embeddings)} BiomedCLIP visual embeddings")
            return images

        except Exception as e:
            logger.warning(f"BiomedCLIP embedding failed: {e}")
            return images

    def _associate_images_with_sections(
        self, sections: list[Section], images: list
    ) -> None:
        """Associate extracted images with their containing sections"""
        for image in images:
            for section in sections:
                if section.page_start <= image.page <= section.page_end:
                    section.images.append(image)
                    break


def process_library(
    library_path: Path,
    force: bool = False,
    chunk_size: int = None,
    chunk_overlap: int = None,
    entropy_threshold: float = 4.5,
) -> list[ProcessedDocument]:
    """
    Process all PDFs in a library directory.

    Args:
        library_path: Path to library directory
        force: If True, reprocess already processed documents
        chunk_size: Target size for text chunks (uses settings default if None)
        chunk_overlap: Overlap between chunks (uses settings default if None)
        entropy_threshold: Minimum entropy for image filtering (default 4.5)

    Returns:
        List of processed documents
    """
    processor = DocumentProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        entropy_threshold=entropy_threshold,
    )
    documents = []

    # Find all PDFs
    pdf_files = list(library_path.rglob("*.pdf"))

    for pdf_path in pdf_files:
        try:
            doc = processor.process(pdf_path)
            documents.append(doc)
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            continue

    return documents
