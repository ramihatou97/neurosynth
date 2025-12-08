"""Data models for figure-text integration.

This module defines structures for representing positioned figures
after the figure resolution pipeline has matched images to text.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


class PlacementType(str, Enum):
    """Figure placement type in output document."""

    INLINE_AFTER = "inline_after"  # Insert after anchor paragraph
    FLOAT_TOP = "float_top"  # Float to top of column/page
    SUBFIGURE = "subfigure"  # Part of subfigure group
    PLATE = "plate"  # Section-end figure plate
    UNASSIGNED = "unassigned"  # Not yet assigned


class MatchMethod(str, Enum):
    """Method used to match figure to text."""

    ID_MATCH = "id_match"  # Matched via [FIGURE: ID] placeholder
    SEMANTIC = "semantic"  # Matched via embedding similarity
    PROCEDURAL = "procedural"  # Matched via step correlation
    KEYWORD = "keyword"  # Matched via keyword overlap
    PRIORITY = "priority"  # Default type-based priority assignment


@dataclass
class PlaceholderMatch:
    """Result of matching a placeholder tag to an image."""

    placeholder_text: str  # Original tag, e.g., "[FIGURE: abc123]"
    position: int  # Character position in text
    paragraph_index: int  # Paragraph number (0-indexed)
    resolved_visual: "VisualElement"  # Matched image
    match_method: MatchMethod  # How it was matched
    confidence: float  # 0-1 confidence score


@dataclass
class SemanticMatch:
    """Result of semantic paragraph-to-image matching."""

    paragraph_index: int  # Paragraph number (0-indexed)
    visual: "VisualElement"  # Matched image
    score: float  # Similarity score (0-1)
    match_signals: dict[str, float] = field(default_factory=dict)


@dataclass
class ProceduralMatch:
    """Result of correlating a text step with a procedural image."""

    step_number: int  # Step number in text (1-indexed)
    paragraph_index: int  # Paragraph containing the step
    visual: "VisualElement"  # Matched procedural image
    sequence_id: str | None = None  # Sequence the image belongs to
    confidence: float = 0.0


@dataclass
class PositionedFigure:
    """A figure with resolved placement in synthesized output.

    This wrapper holds a VisualElement along with output-time
    placement decisions (which paragraph to anchor to, how to display).
    """

    visual: "VisualElement"
    anchor_paragraph_index: int | None = None
    placement_type: PlacementType = PlacementType.PLATE
    match_method: MatchMethod = MatchMethod.PRIORITY
    match_confidence: float = 0.0
    resolved_placeholder: str | None = None

    # For subfigure grouping
    subfigure_group_id: str | None = None
    subfigure_label: str | None = None  # "(a)", "(b)", etc.


@dataclass
class SectionFigureResolution:
    """Complete figure resolution result for a section."""

    section_title: str
    raw_text: str  # Original AI output with placeholders
    resolved_text: str  # Text with placeholders removed
    positioned_figures: list[PositionedFigure] = field(default_factory=list)
    unmatched_placeholders: list[str] = field(default_factory=list)
    unused_figures: list["VisualElement"] = field(default_factory=list)

    @property
    def inline_count(self) -> int:
        """Number of figures placed inline."""
        return sum(
            1
            for pf in self.positioned_figures
            if pf.placement_type
            in (PlacementType.INLINE_AFTER, PlacementType.SUBFIGURE)
        )

    @property
    def plate_count(self) -> int:
        """Number of figures placed in plate."""
        return sum(
            1
            for pf in self.positioned_figures
            if pf.placement_type == PlacementType.PLATE
        )

    @property
    def total_positioned(self) -> int:
        """Total number of positioned figures."""
        return len(self.positioned_figures)


@dataclass
class FigureLibrary:
    """Library of all available figures, including unused ones.

    Preserves access to all extracted images even if they weren't
    placed in the final output, allowing users to browse and manually
    select additional figures.
    """

    all_figures: list["VisualElement"] = field(default_factory=list)
    used_figure_ids: set[str] = field(default_factory=set)

    @property
    def unused_figures(self) -> list["VisualElement"]:
        """Figures not placed in output."""
        return [f for f in self.all_figures if f.id not in self.used_figure_ids]

    @property
    def used_figures(self) -> list["VisualElement"]:
        """Figures placed in output."""
        return [f for f in self.all_figures if f.id in self.used_figure_ids]

    def mark_used(self, figure_id: str) -> None:
        """Mark a figure as used."""
        self.used_figure_ids.add(figure_id)

    def get_unused_by_type(self, image_type: str) -> list["VisualElement"]:
        """Get unused figures of a specific type."""
        return [f for f in self.unused_figures if f.image_type.value == image_type]

    @property
    def unused_count(self) -> int:
        """Number of unused figures."""
        return len(self.unused_figures)

    @property
    def used_count(self) -> int:
        """Number of used figures."""
        return len(self.used_figure_ids)
