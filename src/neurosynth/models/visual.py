"""Visual content models for NeuroSynth.

This module defines data structures for representing visual elements
extracted from neurosurgical reference documents, including surgical
step images, anatomical diagrams, and imaging studies.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


class ImageType(str, Enum):
    """Image type classification for neurosurgical content.

    Priority order for display:
    1. SURGICAL_STEP - Intraoperative, procedural images
    2. ANATOMICAL - Diagrams, cross-sections, labeled anatomy
    3. IMAGING - MRI, CT, angiography with annotations
    4. ILLUSTRATION - General medical illustrations
    5. PHOTOGRAPH - Clinical photographs
    6. TABLE - Extracted tables as images
    7. FLOWCHART - Algorithm diagrams, decision trees, workflows
    8. UNKNOWN - Unclassified images
    """

    SURGICAL_STEP = "surgical_step"
    ANATOMICAL = "anatomical"
    IMAGING = "imaging"
    ILLUSTRATION = "illustration"
    PHOTOGRAPH = "photograph"
    TABLE = "table"
    FLOWCHART = "flowchart"
    UNKNOWN = "unknown"

    @classmethod
    def priority_order(cls) -> list["ImageType"]:
        """Return image types in priority order for display."""
        return [
            cls.SURGICAL_STEP,
            cls.ANATOMICAL,
            cls.IMAGING,
            cls.ILLUSTRATION,
            cls.PHOTOGRAPH,
            cls.TABLE,
            cls.FLOWCHART,
            cls.UNKNOWN,
        ]

    @property
    def is_high_priority(self) -> bool:
        """Whether this type should be shown inline (vs in plate)."""
        return self in (ImageType.SURGICAL_STEP, ImageType.ANATOMICAL)


@dataclass
class VisualElement:
    """A visual element extracted from a document.

    Represents a single image with its metadata, caption, classification,
    and embedding for semantic search.
    """

    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # Image data
    image_path: Path | None = None
    image_bytes: bytes | None = field(default=None, repr=False)
    format: str = "png"  # png, jpg, etc.
    width: int = 0
    height: int = 0

    # Source location
    source_pdf: Path | None = None
    page_number: int = 0
    bbox: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1

    # Caption (original only - no AI generation per user requirement)
    caption: str = ""
    caption_confidence: float = 0.0  # 0-1, how confident in caption match

    # Classification
    image_type: ImageType = ImageType.UNKNOWN
    type_confidence: float = 0.0

    # Embeddings (ColPali visual embeddings)
    visual_embedding: np.ndarray | None = field(default=None, repr=False)
    embedding_model: str = ""

    # Association with text chunks
    associated_chunk_ids: list[str] = field(default_factory=list)
    context_text: str = ""  # Surrounding text for context

    # Deduplication
    visual_hash: str = ""  # Perceptual hash for duplicate detection

    # Relevance scoring (set during visual association)
    relevance_score: float = 0.0

    # Keyword scoring (Phase 3.5 - neurosurgical keyword relevance)
    keyword_score: float = 0.0  # 0-1 score from 340+ keyword analysis
    keywords_matched: list[str] = field(default_factory=list)  # Matched keywords

    # Anatomical region tagging (Task 1 enhancement)
    anatomical_regions: list[str] = field(default_factory=list)  # Detected region IDs
    region_confidence: float = 0.0  # Average confidence of detected regions

    # OCR caption extraction (Task 2 enhancement)
    ocr_caption: str = ""  # Caption extracted via OCR from image content
    caption_source: str = "proximity"  # "proximity", "ocr", "hybrid"

    # Phase 3.6: Procedural Sequence Detection
    sequence_id: str | None = None  # Sequence identifier (e.g., "seq_001")
    sequence_position: int | None = None  # Position in sequence (1, 2, 3...)
    sequence_type: str | None = (
        None  # "numbered_steps", "subfigures", "lettered_panels", "staged_procedure", "implicit"
    )
    step_label: str | None = None  # Human-readable label: "Step 1", "(a)", "Stage 2"
    is_procedural: bool = False  # Whether part of procedural sequence
    procedural_confidence: float = 0.0  # 0-1 confidence score

    # Phase 4: Output Placement (set during figure resolution, not extraction)
    # These fields track where/how this image appears in synthesized output
    output_anchor_paragraph: int | None = None  # Paragraph index in synthesized text
    output_placement: str = (
        "unassigned"  # inline_after, float_top, subfigure, plate, unassigned
    )
    output_match_method: str | None = (
        None  # id_match, semantic, procedural, keyword, priority
    )
    output_match_confidence: float = 0.0  # 0-1 confidence in placement decision
    resolved_from_placeholder: str | None = None  # Original [FIGURE: X] tag if resolved
    paragraph_similarity: float = 0.0  # Embedding similarity to anchor paragraph
    subfigure_group_id: str | None = None  # Group ID for subfigure sets
    subfigure_label: str | None = None  # Label within group: "(a)", "(b)", etc.

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        if isinstance(self.image_path, str):
            self.image_path = Path(self.image_path)
        if isinstance(self.source_pdf, str):
            self.source_pdf = Path(self.source_pdf)
        if isinstance(self.image_type, str):
            self.image_type = ImageType(self.image_type)

    @property
    def has_embedding(self) -> bool:
        """Whether this element has a visual embedding."""
        return self.visual_embedding is not None

    @property
    def has_caption(self) -> bool:
        """Whether this element has a caption."""
        return bool(self.caption.strip())

    @property
    def aspect_ratio(self) -> float:
        """Width to height ratio."""
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def is_landscape(self) -> bool:
        """Whether image is wider than tall."""
        return self.aspect_ratio > 1.0

    def to_latex(self, width: str = "0.8\\textwidth") -> str:
        """Convert to LaTeX figure code."""
        if not self.image_path:
            return ""

        # Escape caption for LaTeX
        safe_caption = self.caption.replace("_", "\\_").replace("%", "\\%")

        return (
            "\\begin{figure}[h]\n"
            "\\centering\n"
            f"\\includegraphics[width={width}]{{{self.image_path}}}\n"
            f"\\caption{{{safe_caption}}}\n"
            f"\\label{{fig:{self.id}}}\n"
            "\\end{figure}"
        )

    @property
    def location_str(self) -> str:
        """Human-readable location string."""
        parts = []
        if self.source_pdf:
            parts.append(self.source_pdf.stem)
        if self.page_number:
            parts.append(f"p.{self.page_number}")
        return ", ".join(parts) if parts else "Unknown location"

    def to_dict(self, include_embedding: bool = True) -> dict:
        """Convert to dictionary for serialization.

        Args:
            include_embedding: Whether to include visual embedding (large).
        """
        data = {
            "id": self.id,
            "image_path": str(self.image_path) if self.image_path else None,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "source_pdf": str(self.source_pdf) if self.source_pdf else None,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "caption": self.caption,
            "caption_confidence": self.caption_confidence,
            "image_type": self.image_type.value,
            "type_confidence": self.type_confidence,
            "embedding_model": self.embedding_model,
            "associated_chunk_ids": self.associated_chunk_ids,
            "context_text": self.context_text[:200],  # Truncate for storage
            "visual_hash": self.visual_hash,
            "relevance_score": self.relevance_score,
            "keyword_score": self.keyword_score,
            "keywords_matched": self.keywords_matched,
            "sequence_id": self.sequence_id,
            "sequence_position": self.sequence_position,
            "sequence_type": self.sequence_type,
            "step_label": self.step_label,
            "is_procedural": self.is_procedural,
            "procedural_confidence": self.procedural_confidence,
            # Output placement fields
            "output_anchor_paragraph": self.output_anchor_paragraph,
            "output_placement": self.output_placement,
            "output_match_method": self.output_match_method,
            "output_match_confidence": self.output_match_confidence,
            "resolved_from_placeholder": self.resolved_from_placeholder,
            "paragraph_similarity": self.paragraph_similarity,
            "subfigure_group_id": self.subfigure_group_id,
            "subfigure_label": self.subfigure_label,
        }
        if include_embedding and self.visual_embedding is not None:
            data["visual_embedding"] = self.visual_embedding.tolist()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VisualElement":
        """Create from dictionary."""
        element = cls(
            id=data.get("id", ""),
            image_path=Path(data["image_path"]) if data.get("image_path") else None,
            format=data.get("format", "png"),
            width=data.get("width", 0),
            height=data.get("height", 0),
            source_pdf=Path(data["source_pdf"]) if data.get("source_pdf") else None,
            page_number=data.get("page_number", 0),
            bbox=tuple(data["bbox"]) if data.get("bbox") else None,
            caption=data.get("caption", ""),
            caption_confidence=data.get("caption_confidence", 0.0),
            image_type=ImageType(data.get("image_type", "unknown")),
            type_confidence=data.get("type_confidence", 0.0),
            embedding_model=data.get("embedding_model", ""),
            associated_chunk_ids=data.get("associated_chunk_ids", []),
            context_text=data.get("context_text", ""),
            visual_hash=data.get("visual_hash", ""),
            relevance_score=data.get("relevance_score", 0.0),
            keyword_score=data.get("keyword_score", 0.0),
            keywords_matched=data.get("keywords_matched", []),
            sequence_id=data.get("sequence_id"),
            sequence_position=data.get("sequence_position"),
            sequence_type=data.get("sequence_type"),
            step_label=data.get("step_label"),
            is_procedural=data.get("is_procedural", False),
            procedural_confidence=data.get("procedural_confidence", 0.0),
            # Output placement fields
            output_anchor_paragraph=data.get("output_anchor_paragraph"),
            output_placement=data.get("output_placement", "unassigned"),
            output_match_method=data.get("output_match_method"),
            output_match_confidence=data.get("output_match_confidence", 0.0),
            resolved_from_placeholder=data.get("resolved_from_placeholder"),
            paragraph_similarity=data.get("paragraph_similarity", 0.0),
            subfigure_group_id=data.get("subfigure_group_id"),
            subfigure_label=data.get("subfigure_label"),
        )
        # Restore visual embedding if present
        if "visual_embedding" in data and data["visual_embedding"] is not None:
            element.visual_embedding = np.array(data["visual_embedding"])
        return element


@dataclass
class FigurePlate:
    """A collection of related figures for section-end display.

    Figure plates group multiple images together, typically displayed
    at the end of a section for supplementary visual content.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    section_title: str = ""
    figures: list[VisualElement] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of figures in the plate."""
        return len(self.figures)

    @property
    def is_empty(self) -> bool:
        """Whether the plate has no figures."""
        return len(self.figures) == 0

    def add_figure(self, figure: VisualElement) -> None:
        """Add a figure to the plate."""
        self.figures.append(figure)

    def get_figures_by_type(self, image_type: ImageType) -> list[VisualElement]:
        """Get all figures of a specific type."""
        return [f for f in self.figures if f.image_type == image_type]

    def sort_by_priority(self) -> None:
        """Sort figures by image type priority."""
        priority_map = {t: i for i, t in enumerate(ImageType.priority_order())}
        self.figures.sort(key=lambda f: priority_map.get(f.image_type, 999))

    def sort_by_page(self) -> None:
        """Sort figures by page number."""
        self.figures.sort(key=lambda f: (f.page_number, f.id))


@dataclass
class VisualIndex:
    """Index of all visual elements for a project.

    Provides fast lookup and organization of visual content
    across all processed documents.
    """

    elements: list[VisualElement] = field(default_factory=list)
    by_id: dict[str, VisualElement] = field(default_factory=dict, repr=False)
    by_source: dict[str, list[VisualElement]] = field(default_factory=dict, repr=False)
    by_type: dict[ImageType, list[VisualElement]] = field(
        default_factory=dict, repr=False
    )

    def add(self, element: VisualElement) -> None:
        """Add an element to the index."""
        self.elements.append(element)
        self.by_id[element.id] = element

        # Index by source
        source_key = str(element.source_pdf) if element.source_pdf else "unknown"
        if source_key not in self.by_source:
            self.by_source[source_key] = []
        self.by_source[source_key].append(element)

        # Index by type
        if element.image_type not in self.by_type:
            self.by_type[element.image_type] = []
        self.by_type[element.image_type].append(element)

    def get(self, element_id: str) -> VisualElement | None:
        """Get element by ID."""
        return self.by_id.get(element_id)

    def get_by_source(self, source_path: Path | str) -> list[VisualElement]:
        """Get all elements from a source document."""
        return self.by_source.get(str(source_path), [])

    def get_by_type(self, image_type: ImageType) -> list[VisualElement]:
        """Get all elements of a specific type."""
        return self.by_type.get(image_type, [])

    def get_high_priority(self) -> list[VisualElement]:
        """Get all high-priority images (surgical steps, anatomical)."""
        result = []
        for img_type in [ImageType.SURGICAL_STEP, ImageType.ANATOMICAL]:
            result.extend(self.get_by_type(img_type))
        return result

    @property
    def total_count(self) -> int:
        """Total number of visual elements."""
        return len(self.elements)

    @property
    def type_counts(self) -> dict[str, int]:
        """Count of elements by type."""
        return {t.value: len(elems) for t, elems in self.by_type.items()}

    def find_duplicates(self, threshold: float = 0.95) -> list[tuple[str, str, float]]:
        """Find potential duplicate images by visual hash similarity.

        Note: This is a simple hash comparison. For more accurate
        duplicate detection, use the Qdrant store with ColPali embeddings.
        """
        duplicates = []
        elements_with_hash = [e for e in self.elements if e.visual_hash]

        for i, elem1 in enumerate(elements_with_hash):
            for elem2 in elements_with_hash[i + 1 :]:
                if elem1.visual_hash == elem2.visual_hash:
                    duplicates.append((elem1.id, elem2.id, 1.0))

        return duplicates
