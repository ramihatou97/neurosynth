"""Document and chunk data models."""

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack

import numpy as np

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


class ChunkKwargs(TypedDict, total=False):
    """Optional keyword arguments for creating a ContentChunk."""

    page_number: int | None
    section_title: str | None
    chapter_title: str | None
    id: str
    word_count: int
    embedding: np.ndarray | None
    content_hash: str
    cluster_id: str | None
    evidence_level: str
    visual_elements: list["VisualElement"]


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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": str(self.path),
            "format": self.format.value,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "edition": self.edition,
            "publisher": self.publisher,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Source":
        """Create Source from dictionary."""
        return cls(
            path=Path(data["path"]),
            format=DocumentFormat(data["format"]),
            title=data.get("title", ""),
            authors=data.get("authors", []),
            year=data.get("year"),
            edition=data.get("edition"),
            publisher=data.get("publisher"),
            id=data.get("id", ""),
        )


@dataclass
class ContentChunk:
    """A chunk of content extracted from a document."""

    content: str
    source: Source

    # Location in source
    page_number: int | None = None  # Single page (legacy, kept for compatibility)
    page_start: int | None = None  # Start page of multi-page chunk
    page_end: int | None = None  # End page of multi-page chunk
    section_title: str | None = None
    chapter_title: str | None = None

    # Processing metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    embedding: np.ndarray | None = field(default=None, repr=False)
    cluster_id: str | None = None

    # Validation/Quality
    evidence_level: str = "unknown"

    # Internal
    _content_hash: str = field(init=False, repr=False)
    _word_count: int = field(init=False, repr=False)

    # Visual elements associated with this chunk (extracted from nearby pages)
    visual_elements: list["VisualElement"] = field(default_factory=list)

    def __post_init__(self):
        """Calculate derived fields."""
        self._content_hash = hashlib.md5(self.content.encode("utf-8")).hexdigest()
        self._word_count = len(self.content.split())

    @property
    def location_str(self) -> str:
        """Human-readable location string."""
        locs = []
        if self.page_number is not None:
            locs.append(f"p.{self.page_number}")
        elif self.page_start is not None:
            if self.page_end and self.page_end > self.page_start:
                locs.append(f"pp.{self.page_start}-{self.page_end}")
            else:
                locs.append(f"p.{self.page_start}")

        if self.section_title:
            locs.append(f"'{self.section_title}'")

        return ", ".join(locs) if locs else "Unknown Location"

    @property
    def source_reference(self) -> str:
        """Short reference combining source and location."""
        return f"{self.source.title} ({self.location_str})"

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
        if visual not in self.visual_elements:
            self.visual_elements.append(visual)
            visual.associated_chunk_ids.append(self.id)

    def to_dict(self, include_embedding: bool = True) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Args:
            include_embedding: Whether to include the embedding array (large).
                              Set to False for smaller serialization.
        """
        data = {
            "content": self.content,
            "source": self.source.to_dict(),
            "page_number": self.page_number,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_title": self.section_title,
            "chapter_title": self.chapter_title,
            "id": self.id,
            "word_count": self._word_count,
            "content_hash": self._content_hash,
            "cluster_id": self.cluster_id,
            "evidence_level": self.evidence_level,
            "visual_elements": [v.id for v in self.visual_elements],
        }

        if include_embedding and self.embedding is not None:
            data["embedding"] = self.embedding.tolist()

        return data

    @classmethod
    def from_dict(cls, data: dict, visual_lookup: dict | None = None) -> "ContentChunk":
        """Create ContentChunk from dictionary.

        Args:
            data: Dictionary with chunk data
            visual_lookup: Optional dict mapping visual IDs to VisualElement objects
        """
        chunk = cls(
            content=data["content"],
            source=Source.from_dict(data["source"]),
            page_number=data.get("page_number"),
            section_title=data.get("section_title"),
            chapter_title=data.get("chapter_title"),
            id=data.get("id", ""),
            cluster_id=data.get("cluster_id"),
        )
        # Restore embedding if present
        if "embedding" in data and data["embedding"] is not None:
            chunk.embedding = np.array(data["embedding"])
        # Restore visual elements if lookup provided
        if visual_lookup and "visual_element_ids" in data:
            for vid in data["visual_element_ids"]:
                if vid in visual_lookup:
                    chunk.visual_elements.append(visual_lookup[vid])
        return chunk


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

    def add_chunk(self, content: str, **kwargs: Unpack[ChunkKwargs]) -> ContentChunk:
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
