"""
Data models for the synthesis engine
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DocumentType(str, Enum):
    """Types of source documents"""

    TEXTBOOK = "textbook"
    CHAPTER = "chapter"
    PAPER = "paper"
    GUIDELINE = "guideline"


class Specialty(str, Enum):
    """Neurosurgical subspecialties"""

    VASCULAR = "vascular"
    TUMOR = "tumor"
    SPINE = "spine"
    FUNCTIONAL = "functional"
    PEDIATRIC = "pediatric"
    TRAUMA = "trauma"
    SKULL_BASE = "skull_base"
    PERIPHERAL_NERVE = "peripheral_nerve"
    ANATOMY = "anatomy"
    GENERAL = "general"


class ChunkType(str, Enum):
    """Types of content chunks"""

    NARRATIVE = "narrative"
    ANATOMY = "anatomy"
    PROCEDURE_STEP = "procedure_step"
    POSITIONING = "positioning"
    COMPLICATIONS = "complications"
    OUTCOMES = "outcomes"
    INDICATIONS = "indications"
    IMAGING = "imaging"
    SUMMARY = "summary"  # For RAPTOR/recursive summaries


class ImageType(str, Enum):
    """Types of medical images"""

    ANATOMY_DIAGRAM = "anatomy_diagram"
    SURGICAL_PHOTO = "surgical_photo"
    IMAGING_MRI = "imaging_mri"
    IMAGING_CT = "imaging_ct"
    IMAGING_ANGIO = "imaging_angio"
    DIAGRAM = "diagram"
    HISTOLOGY = "histology"
    ILLUSTRATION = "illustration"


# ============================================================================
# Source Documents
# ============================================================================


@dataclass
class SourceMetadata:
    """Metadata for a source document"""

    id: str
    title: str
    doc_type: DocumentType
    file_path: Path
    authors: str | None = None
    year: int | None = None
    specialty: Specialty = Specialty.GENERAL
    total_pages: int = 0
    processed_at: datetime | None = None


@dataclass
class ExtractedImage:
    """An image extracted from a PDF with context"""

    id: str
    source_id: str
    page: int
    file_path: Path
    caption: str
    surrounding_text: str
    image_type: ImageType
    width: int = 0
    height: int = 0
    embedding: list[float] | None = None

    # Enhanced metadata for LLM context (Priority 1 enhancement)
    modality: str = (
        "unknown"  # Zero-shot classification result (radiology, surgical, etc.)
    )
    detected_regions: list[str] = field(default_factory=list)  # Anatomical region IDs
    region_confidence: float = 0.0  # Average confidence of detected regions
    ocr_caption: str = ""  # Caption extracted via OCR from image content
    caption_source: str = "proximity"  # "proximity", "ocr", "hybrid", "parsed"

    @classmethod
    def from_figure(cls, fig: Any, source_id: str) -> "ExtractedImage":
        """Convert a SmartExtractor ExtractedFigure to ExtractedImage."""
        # Simple heuristic mapping for image type
        caption_lower = fig.caption.lower()
        img_type = ImageType.ILLUSTRATION

        # Basic keyword matching for type
        if "mri" in caption_lower or "t1" in caption_lower or "t2" in caption_lower:
            img_type = ImageType.IMAGING_MRI
        elif "ct " in caption_lower or "computed tomography" in caption_lower:
            img_type = ImageType.IMAGING_CT
        elif "angiogram" in caption_lower or "dsa" in caption_lower:
            img_type = ImageType.IMAGING_ANGIO
        elif "intraoperative" in caption_lower or "surgical view" in caption_lower:
            img_type = ImageType.SURGICAL_PHOTO
        elif "anatomy" in caption_lower or "schematic" in caption_lower:
            img_type = ImageType.ANATOMY_DIAGRAM
        elif "histology" in caption_lower or "stain" in caption_lower:
            img_type = ImageType.HISTOLOGY

        return cls(
            id=fig.image_filename,
            source_id=source_id,
            page=fig.page_num or 0,
            file_path=fig.local_path,
            caption=fig.caption,
            surrounding_text=fig.context,
            image_type=img_type,
            # Phase 4 Extra Metadata
            detected_regions=getattr(fig, "detected_regions", []),
            region_confidence=getattr(fig, "region_confidence", 0.0),
            ocr_caption=getattr(fig, "ocr_caption", ""),
            caption_source=getattr(fig, "caption_source", "proximity"),
        )


@dataclass
class Section:
    """A section within a document"""

    title: str
    level: int  # 1 = main heading, 2 = subheading, etc.
    page_start: int
    page_end: int
    content: str
    images: list[ExtractedImage] = field(default_factory=list)


@dataclass
class ProcessedDocument:
    """A fully processed document"""

    metadata: SourceMetadata
    sections: list[Section]
    images: list[ExtractedImage]
    raw_text: str


# ============================================================================
# Chunks and Index
# ============================================================================


@dataclass
class Chunk:
    """A searchable chunk of content"""

    id: str
    source_id: str
    source_title: str
    section_title: str
    content: str
    chunk_type: ChunkType
    page_start: int
    page_end: int
    embedding: list[float] | None = None
    image_ids: list[str] = field(default_factory=list)
    # For deduplication tracking
    also_in_sources: list[str] = field(default_factory=list)
    # Dynamic metadata (e.g. NeuroLi enrichment)
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_level: str = "unknown"
    # Phase 2: Contextual Intelligence
    parent_context: str | None = None  # Full section text (retrieval context)
    is_proposition: bool = False  # True if this is a "Small" proposition chunk


@dataclass
class SearchResult:
    """A search result with relevance score"""

    chunk: Chunk
    score: float
    evidence_level: str = "unknown"
    images: list[ExtractedImage] = field(default_factory=list)


# ============================================================================
# Synthesis
# ============================================================================


class SectionTemplate(BaseModel):
    """Template for a chapter section"""

    name: str
    subsections: list[str] = []
    format: str = "prose"  # "prose" or "step_by_step"
    image_priority: str = "normal"  # "high", "normal", "low"
    chunk_types: list[ChunkType] = []  # Which chunk types are relevant
    # Priority 3: Configurable image type preferences per section
    preferred_image_types: list[str] = []  # e.g., ["anatomy_diagram", "surgical_photo"]


class ChapterTemplate(BaseModel):
    """Template for a complete chapter"""

    name: str
    sections: list[SectionTemplate]


@dataclass
class SynthesizedSection:
    """A synthesized section of a chapter"""

    title: str
    content: str
    images: list[ExtractedImage] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    subsections: dict[str, str] = field(default_factory=dict)


@dataclass
class SynthesizedChapter:
    """A complete synthesized chapter"""

    topic: str
    sections: list[SynthesizedSection]
    sources: list[SourceMetadata]
    total_chunks_used: int
    total_images: int
    generated_at: datetime
    template_used: str


# ============================================================================
# Chapter Templates
# ============================================================================

SURGICAL_PROCEDURE_TEMPLATE = ChapterTemplate(
    name="surgical_procedure",
    sections=[
        SectionTemplate(
            name="Overview",
            subsections=["Definition", "History", "Indications", "Contraindications"],
            chunk_types=[ChunkType.NARRATIVE, ChunkType.INDICATIONS],
            preferred_image_types=["illustration", "diagram"],
        ),
        SectionTemplate(
            name="Surgical Anatomy",
            subsections=[
                "Surface Anatomy",
                "Deep Structures",
                "Neurovascular Relationships",
                "Anatomic Variants",
            ],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
            preferred_image_types=["anatomy_diagram", "illustration", "diagram"],
        ),
        SectionTemplate(
            name="Preoperative Planning",
            subsections=["Imaging", "Patient Selection", "Special Considerations"],
            chunk_types=[ChunkType.IMAGING, ChunkType.INDICATIONS],
            preferred_image_types=[
                "imaging_mri",
                "imaging_ct",
                "imaging_angio",
                "diagram",
            ],
        ),
        SectionTemplate(
            name="Operative Technique",
            subsections=[
                "Positioning",
                "Incision and Exposure",
                "Key Steps",
                "Closure",
            ],
            format="step_by_step",
            image_priority="high",
            chunk_types=[ChunkType.PROCEDURE_STEP, ChunkType.POSITIONING],
            preferred_image_types=["surgical_photo", "anatomy_diagram", "illustration"],
        ),
        SectionTemplate(
            name="Complications",
            subsections=["Prevention", "Recognition", "Management"],
            chunk_types=[ChunkType.COMPLICATIONS],
            preferred_image_types=["surgical_photo", "imaging_ct", "imaging_mri"],
        ),
        SectionTemplate(
            name="Outcomes",
            subsections=["Expected Results", "Evidence Base"],
            chunk_types=[ChunkType.OUTCOMES],
            preferred_image_types=["diagram", "illustration"],
        ),
    ],
)

ANATOMY_TEMPLATE = ChapterTemplate(
    name="anatomy",
    sections=[
        SectionTemplate(
            name="Overview",
            subsections=["Introduction", "Clinical Relevance"],
            chunk_types=[ChunkType.NARRATIVE],
            preferred_image_types=["illustration", "diagram"],
        ),
        SectionTemplate(
            name="Surface Anatomy",
            subsections=["Landmarks", "Surface Projections"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
            preferred_image_types=["anatomy_diagram", "illustration", "surgical_photo"],
        ),
        SectionTemplate(
            name="Structural Anatomy",
            subsections=["Bony Structures", "Soft Tissues", "Compartments"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
            preferred_image_types=["anatomy_diagram", "imaging_ct", "illustration"],
        ),
        SectionTemplate(
            name="Neurovascular Anatomy",
            subsections=["Arterial Supply", "Venous Drainage", "Neural Structures"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
            preferred_image_types=["anatomy_diagram", "imaging_angio", "illustration"],
        ),
        SectionTemplate(
            name="Surgical Corridors",
            subsections=["Approaches", "Safe Zones", "Danger Areas"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY, ChunkType.PROCEDURE_STEP],
            preferred_image_types=["anatomy_diagram", "surgical_photo", "illustration"],
        ),
        SectionTemplate(
            name="Anatomic Variants",
            subsections=["Common Variations", "Clinical Significance"],
            chunk_types=[ChunkType.ANATOMY],
            preferred_image_types=["anatomy_diagram", "imaging_mri", "imaging_ct"],
        ),
    ],
)

CLINICAL_TOPIC_TEMPLATE = ChapterTemplate(
    name="clinical_topic",
    sections=[
        SectionTemplate(
            name="Overview",
            subsections=["Definition", "Epidemiology", "Etiology"],
            chunk_types=[ChunkType.NARRATIVE],
            preferred_image_types=["illustration", "diagram"],
        ),
        SectionTemplate(
            name="Clinical Presentation",
            subsections=["Symptoms", "Signs", "Natural History"],
            chunk_types=[ChunkType.NARRATIVE],
            preferred_image_types=["illustration", "diagram", "anatomy_diagram"],
        ),
        SectionTemplate(
            name="Diagnosis",
            subsections=["Imaging", "Laboratory Studies", "Differential Diagnosis"],
            image_priority="high",
            chunk_types=[ChunkType.IMAGING, ChunkType.NARRATIVE],
            preferred_image_types=[
                "imaging_mri",
                "imaging_ct",
                "imaging_angio",
                "diagram",
            ],
        ),
        SectionTemplate(
            name="Management",
            subsections=[
                "Conservative Treatment",
                "Surgical Treatment",
                "Decision Making",
            ],
            chunk_types=[ChunkType.NARRATIVE, ChunkType.PROCEDURE_STEP],
            preferred_image_types=["surgical_photo", "anatomy_diagram", "illustration"],
        ),
        SectionTemplate(
            name="Outcomes and Prognosis",
            subsections=["Expected Results", "Complications", "Long-term Follow-up"],
            chunk_types=[ChunkType.OUTCOMES, ChunkType.COMPLICATIONS],
            preferred_image_types=["diagram", "imaging_mri", "imaging_ct"],
        ),
    ],
)

# Template selection helper
TEMPLATES = {
    "surgical_procedure": SURGICAL_PROCEDURE_TEMPLATE,
    "anatomy": ANATOMY_TEMPLATE,
    "clinical_topic": CLINICAL_TOPIC_TEMPLATE,
}


def get_template(template_name: str) -> ChapterTemplate:
    """Get a chapter template by name"""
    return TEMPLATES.get(template_name, SURGICAL_PROCEDURE_TEMPLATE)
