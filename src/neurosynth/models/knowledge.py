"""Knowledge representation models for synthesis."""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from neurosynth.models.document import ContentChunk, Source

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


class ConflictType(str, Enum):
    """Types of conflicts between sources."""

    QUANTITATIVE = "quantitative"  # Different numbers/percentages
    CONTRADICTORY = "contradictory"  # Opposite claims
    APPROACH = "approach"  # Different surgical/treatment approaches
    TEMPORAL = "temporal"  # Older vs newer evidence
    TERMINOLOGY = "terminology"  # Different terms for same concept
    EMPHASIS = "emphasis"  # Different emphasis on importance


@dataclass
class Perspective:
    """A specific viewpoint from a source on a topic."""

    claim: str
    source: Source
    chunk: ContentChunk
    confidence: float = 1.0  # 0-1, derived from source quality/recency

    @property
    def citation(self) -> str:
        """Formatted citation for this perspective."""
        return f"({self.source.citation_key})"


@dataclass
class Conflict:
    """A detected conflict between sources."""

    type: ConflictType
    description: str
    perspectives: list[Perspective] = field(default_factory=list)

    # Resolution suggestion (if any)
    suggested_resolution: str | None = None

    def to_academic_text(self) -> str:
        """Generate academic-style conflict presentation."""
        if len(self.perspectives) < 2:
            return self.perspectives[0].claim if self.perspectives else ""

        # Sort by year (most recent last for emphasis)
        sorted_persp = sorted(
            self.perspectives,
            key=lambda p: p.source.year or 0,
        )

        if self.type == ConflictType.TEMPORAL:
            older = sorted_persp[0]
            newer = sorted_persp[-1]
            return (
                f"Classic teaching suggests {older.claim} {older.citation}, "
                f"though recent evidence indicates {newer.claim} {newer.citation}."
            )
        elif self.type == ConflictType.APPROACH:
            approaches = [f"{p.claim} {p.citation}" for p in sorted_persp]
            return f"Different approaches have been advocated: {'; '.join(approaches)}."
        elif self.type == ConflictType.QUANTITATIVE:
            values = [f"{p.claim} {p.citation}" for p in sorted_persp]
            return f"Reported values vary: {'; '.join(values)}."
        else:
            # Generic conflict presentation
            views = [f"{p.claim} {p.citation}" for p in sorted_persp]
            return f"Perspectives differ: {' However, '.join(views)}."


@dataclass
class KnowledgeCluster:
    """A cluster of semantically similar content from multiple sources."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Original chunks that were clustered
    chunks: list[ContentChunk] = field(default_factory=list)

    # Merged/synthesized content
    merged_content: str = ""

    # Detected conflicts within this cluster
    conflicts: list[Conflict] = field(default_factory=list)

    # Topic/concept this cluster represents
    topic: str = ""
    subtopic: str = ""

    # Section mapping (set during outline generation)
    target_section: str | None = None

    # Visual elements aggregated from chunks (comprehensive - not deduplicated)
    visual_elements: list["VisualElement"] = field(default_factory=list)

    # Quality metrics
    source_count: int = 0
    similarity_score: float = 0.0  # Average pairwise similarity

    def __post_init__(self):
        """Calculate derived fields."""
        self.source_count = len(set(c.source.id for c in self.chunks))

    @property
    def sources(self) -> list[Source]:
        """Unique sources contributing to this cluster."""
        seen = set()
        sources = []
        for chunk in self.chunks:
            if chunk.source.id not in seen:
                seen.add(chunk.source.id)
                sources.append(chunk.source)
        return sources

    @property
    def has_conflicts(self) -> bool:
        """Whether this cluster has detected conflicts."""
        return len(self.conflicts) > 0

    @property
    def word_count(self) -> int:
        """Word count of merged content."""
        return len(self.merged_content.split())

    def get_citations(self) -> str:
        """Generate combined citation string for all sources."""
        citations = [s.citation_key for s in self.sources]
        return f"({', '.join(sorted(set(citations)))})"

    @property
    def has_visuals(self) -> bool:
        """Whether this cluster has visual elements."""
        return len(self.visual_elements) > 0

    @property
    def visual_count(self) -> int:
        """Number of visual elements in this cluster."""
        return len(self.visual_elements)

    def collect_visuals(self) -> None:
        """Aggregate visual elements from all chunks.

        This collects ALL unique visual elements from member chunks,
        ensuring comprehensive visual coverage (no deduplication).
        """
        seen_ids: set[str] = set()
        for chunk in self.chunks:
            for visual in chunk.visual_elements:
                if visual.id not in seen_ids:
                    seen_ids.add(visual.id)
                    self.visual_elements.append(visual)

    def get_visuals_by_type(self, image_type: str) -> list["VisualElement"]:
        """Get all visual elements of a specific type."""
        return [v for v in self.visual_elements if v.image_type.value == image_type]

    def get_high_priority_visuals(self) -> list["VisualElement"]:
        """Get surgical steps and anatomical diagrams (for inline display)."""
        from neurosynth.models.visual import ImageType
        return [
            v for v in self.visual_elements
            if v.image_type in (ImageType.SURGICAL_STEP, ImageType.ANATOMICAL)
        ]


@dataclass
class KnowledgeBase:
    """Complete knowledge base for a topic."""

    topic: str
    clusters: list[KnowledgeCluster] = field(default_factory=list)

    # Statistics
    total_chunks_processed: int = 0
    total_sources: int = 0
    dedup_ratio: float = 0.0  # Original chunks / clusters

    # All unique sources
    sources: list[Source] = field(default_factory=list)

    @property
    def total_conflicts(self) -> int:
        """Total conflicts across all clusters."""
        return sum(len(c.conflicts) for c in self.clusters)

    @property
    def coverage_by_section(self) -> dict[str, int]:
        """Count of clusters per target section."""
        coverage: dict[str, int] = {}
        for cluster in self.clusters:
            section = cluster.target_section or "Unassigned"
            coverage[section] = coverage.get(section, 0) + 1
        return coverage
