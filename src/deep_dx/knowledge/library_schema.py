from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class CollectionType(Enum):
    """Type of library collection."""

    COMPLETE_TEXTBOOKS = "complete_textbooks"
    MULTI_CHAPTER_BOOKS = "multi_chapter_books"
    SINGLE_CHAPTERS = "single_chapters"
    EVIDENCE_STUDIES = "evidence_studies"
    EDUCATIONAL_MATERIALS = "educational_materials"
    CLINICAL_GUIDELINES = "clinical_guidelines"


class SubspecialtyColor(Enum):
    """10-color subspecialty system."""

    RED = ("🔴", "#e74c3c", "Vascular")
    ORANGE = ("🟠", "#e67e22", "Neuro-Oncology")
    YELLOW = ("🟡", "#f39c12", "Trauma")
    GREEN = ("🟢", "#27ae60", "Spine")
    BLUE = ("🔵", "#3498db", "Functional")
    PURPLE = ("🟣", "#9b59b6", "Pediatric")
    BLACK = ("⚫", "#2c3e50", "Skull Base")
    GREY = ("⚪", "#95a5a6", "Anatomy/General")
    BROWN = ("🟤", "#8b4513", "Peripheral Nerve")
    PINK = ("🩷", "#ff69b4", "Infection")

    def __init__(self, emoji: str, hex_color: str, name: str):
        self.emoji = emoji
        self.hex_color = hex_color
        self.subspecialty_name = name


@dataclass
class Document:
    """Individual PDF document."""

    path: Path
    filename: str
    size_mb: float
    page_count: int | None = None
    has_toc: bool = False
    is_text_based: bool = True

    # Enriched Metadata (not in original schema but useful for Deep Search)
    subspecialty: str | None = None
    condition: str | None = None
    authority_score: int = 80


@dataclass
class Condition:
    """Medical condition folder within a subspecialty."""

    name: str
    path: Path
    documents: list[Document] = field(default_factory=list)
    landmark_trials: list[str] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return len(self.documents)


@dataclass
class Subcollection:
    """Subspecialty-organized folder (e.g., 01_Vascular)."""

    id: str
    name: str
    path: Path
    color: SubspecialtyColor | None = None
    conditions: list[Condition] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return sum(c.document_count for c in self.conditions)


@dataclass
class BookSeries:
    """Multi-chapter book series."""

    name: str
    path: Path
    chapter_count: int
    authority_score: int = 85
    color: SubspecialtyColor | None = None


@dataclass
class Collection:
    """Top-level library collection."""

    id: str
    name: str
    path: Path
    type: CollectionType
    subcollections: list[Subcollection] = field(default_factory=list)
    book_series: list[BookSeries] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        direct = len(self.documents)
        sub = sum(s.document_count for s in self.subcollections)
        series = sum(s.chapter_count for s in self.book_series)
        return direct + sub + series


@dataclass
class LandmarkPaper:
    """Landmark trial/paper from index."""

    acronym: str
    full_name: str
    location: str
    key_finding: str
    authority_score: int = 100
    subspecialty: str | None = None


@dataclass
class ColorSystem:
    """10-color subspecialty classification."""

    colors: dict[str, SubspecialtyColor] = field(default_factory=dict)


@dataclass
class LibrarySchema:
    """Complete library schema."""

    name: str
    root: Path
    version: str
    collections: list[Collection]
    color_system: ColorSystem
    landmark_papers: list[LandmarkPaper] = field(default_factory=list)
