"""Document and chunk data models."""

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


class DocumentFormat(str, Enum):
    """Supported document formats."""

    PDF = "pdf"
    EPUB = "epub"
    DOCX = "docx"
    TXT = "txt"

    @classmethod
    def from_path(cls, path: Path) -> "DocumentFormat":
        """Detect format from file extension."""
        suffix = path.suffix.lower().lstrip(".")
        mapping = {
            "pdf": cls.PDF,
            "epub": cls.EPUB,
            "docx": cls.DOCX,
            "doc": cls.DOCX,
            "txt": cls.TXT,
            "text": cls.TXT,
            "md": cls.TXT,
        }
        if suffix not in mapping:
            raise ValueError(f"Unsupported file format: {suffix}")
        return mapping[suffix]


@dataclass
class Source:
    """Represents a source document with metadata."""

    path: Path
    format: DocumentFormat
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    edition: str | None = None
    publisher: str | None = None

    # Internal tracking
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __post_init__(self):
        """Derive title from filename if not provided."""
        if not self.title:
            self.title = self.path.stem.replace("_", " ").replace("-", " ")

    @property
    def citation_key(self) -> str:
        """Generate a citation key for this source."""
        author_part = self.authors[0].split()[-1] if self.authors else "Unknown"
        year_part = str(self.year) if self.year else "nd"
        return f"{author_part}{year_part}"

    def to_citation(self) -> str:
        """Generate a formatted citation string."""
        parts = []
        if self.authors:
            parts.append(", ".join(self.authors))
        if self.year:
            parts.append(f"({self.year})")
        if self.title:
            parts.append(f"*{self.title}*")
        if self.publisher:
            parts.append(self.publisher)
        return ". ".join(parts)


@dataclass
class ContentChunk:
    """A chunk of content extracted from a document."""

    content: str
    source: Source

    # Location in source
    page_number: int | None = None
    section_title: str | None = None
    chapter_title: str | None = None

    # Processing metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    word_count: int = 0
    embedding: np.ndarray | None = field(default=None, repr=False)

    # Content hash for exact deduplication
    content_hash: str = field(default="", repr=False)

    # Cluster assignment (set during deduplication)
    cluster_id: str | None = None

    # Visual elements associated with this chunk (extracted from nearby pages)
    visual_elements: list["VisualElement"] = field(default_factory=list)

    def __post_init__(self):
        """Calculate derived fields."""
        self.word_count = len(self.content.split())
        self.content_hash = hashlib.sha256(self.content.strip().lower().encode()).hexdigest()[:16]

    @property
    def location_str(self) -> str:
        """Human-readable location string."""
        parts = []
        if self.chapter_title:
            parts.append(f"Ch: {self.chapter_title}")
        if self.section_title:
            parts.append(f"Sec: {self.section_title}")
        if self.page_number:
            parts.append(f"p. {self.page_number}")
        return ", ".join(parts) if parts else "Unknown location"

    @property
    def source_reference(self) -> str:
        """Short reference combining source and location."""
        return f"{self.source.citation_key}, {self.location_str}"

    @property
    def has_visuals(self) -> bool:
        """Whether this chunk has associated visual elements."""
        return len(self.visual_elements) > 0

    @property
    def visual_count(self) -> int:
        """Number of associated visual elements."""
        return len(self.visual_elements)

    def add_visual(self, visual: "VisualElement") -> None:
        """Add a visual element to this chunk."""
        self.visual_elements.append(visual)
        visual.associated_chunk_ids.append(self.id)


@dataclass
class Document:
    """A fully parsed document with all its chunks."""

    source: Source
    chunks: list[ContentChunk] = field(default_factory=list)

    # Document-level metadata extracted during parsing
    toc: list[dict[str, Any]] = field(default_factory=list)
    total_pages: int = 0
    raw_text: str = field(default="", repr=False)

    # Processing state
    is_parsed: bool = False
    is_chunked: bool = False
    parse_errors: list[str] = field(default_factory=list)

    # Visual content extracted from document
    visual_elements: list["VisualElement"] = field(default_factory=list)

    @property
    def total_words(self) -> int:
        """Total word count across all chunks."""
        return sum(c.word_count for c in self.chunks)

    @property
    def chunk_count(self) -> int:
        """Number of chunks."""
        return len(self.chunks)

    def add_chunk(self, content: str, **kwargs) -> ContentChunk:
        """Create and add a new chunk to this document."""
        chunk = ContentChunk(
            content=content,
            source=self.source,
            **kwargs,
        )
        self.chunks.append(chunk)
        return chunk

    @property
    def has_visuals(self) -> bool:
        """Whether this document has visual elements."""
        return len(self.visual_elements) > 0

    @property
    def visual_count(self) -> int:
        """Number of visual elements in this document."""
        return len(self.visual_elements)

    def add_visual(self, visual: "VisualElement") -> None:
        """Add a visual element to this document."""
        self.visual_elements.append(visual)

    def get_visuals_for_page(self, page_number: int) -> list["VisualElement"]:
        """Get all visual elements from a specific page."""
        return [v for v in self.visual_elements if v.page_number == page_number]
