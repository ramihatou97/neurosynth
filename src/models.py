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
    authors: Optional[str] = None
    year: Optional[int] = None
    specialty: Specialty = Specialty.GENERAL
    total_pages: int = 0
    processed_at: Optional[datetime] = None


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
    embedding: Optional[list[float]] = None


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
    embedding: Optional[list[float]] = None
    image_ids: list[str] = field(default_factory=list)
    # For deduplication tracking
    also_in_sources: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """A search result with relevance score"""

    chunk: Chunk
    score: float
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
        ),
        SectionTemplate(
            name="Preoperative Planning",
            subsections=["Imaging", "Patient Selection", "Special Considerations"],
            chunk_types=[ChunkType.IMAGING, ChunkType.INDICATIONS],
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
        ),
        SectionTemplate(
            name="Complications",
            subsections=["Prevention", "Recognition", "Management"],
            chunk_types=[ChunkType.COMPLICATIONS],
        ),
        SectionTemplate(
            name="Outcomes",
            subsections=["Expected Results", "Evidence Base"],
            chunk_types=[ChunkType.OUTCOMES],
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
        ),
        SectionTemplate(
            name="Surface Anatomy",
            subsections=["Landmarks", "Surface Projections"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
        ),
        SectionTemplate(
            name="Structural Anatomy",
            subsections=["Bony Structures", "Soft Tissues", "Compartments"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
        ),
        SectionTemplate(
            name="Neurovascular Anatomy",
            subsections=["Arterial Supply", "Venous Drainage", "Neural Structures"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY],
        ),
        SectionTemplate(
            name="Surgical Corridors",
            subsections=["Approaches", "Safe Zones", "Danger Areas"],
            image_priority="high",
            chunk_types=[ChunkType.ANATOMY, ChunkType.PROCEDURE_STEP],
        ),
        SectionTemplate(
            name="Anatomic Variants",
            subsections=["Common Variations", "Clinical Significance"],
            chunk_types=[ChunkType.ANATOMY],
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
        ),
        SectionTemplate(
            name="Clinical Presentation",
            subsections=["Symptoms", "Signs", "Natural History"],
            chunk_types=[ChunkType.NARRATIVE],
        ),
        SectionTemplate(
            name="Diagnosis",
            subsections=["Imaging", "Laboratory Studies", "Differential Diagnosis"],
            image_priority="high",
            chunk_types=[ChunkType.IMAGING, ChunkType.NARRATIVE],
        ),
        SectionTemplate(
            name="Management",
            subsections=[
                "Conservative Treatment",
                "Surgical Treatment",
                "Decision Making",
            ],
            chunk_types=[ChunkType.NARRATIVE, ChunkType.PROCEDURE_STEP],
        ),
        SectionTemplate(
            name="Outcomes and Prognosis",
            subsections=["Expected Results", "Complications", "Long-term Follow-up"],
            chunk_types=[ChunkType.OUTCOMES, ChunkType.COMPLICATIONS],
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
