"""Output document models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from neurosynth.models.document import Source
from neurosynth.models.knowledge import KnowledgeCluster

if TYPE_CHECKING:
    from neurosynth.models.visual import FigurePlate, VisualElement


@dataclass
class Section:
    """A section in the output chapter."""

    title: str
    level: int = 1  # 1 = main section, 2 = subsection, etc.

    # Content
    content: str = ""
    clusters: list[KnowledgeCluster] = field(default_factory=list)

    # Subsections
    subsections: list["Section"] = field(default_factory=list)

    # Visual content
    inline_figures: list["VisualElement"] = field(default_factory=list)
    figure_plate: "FigurePlate | None" = None

    # Metadata
    word_count: int = 0
    citation_count: int = 0
    has_conflicts: bool = False

    def __post_init__(self):
        """Calculate derived fields."""
        self.word_count = len(self.content.split())
        self.has_conflicts = any(c.has_conflicts for c in self.clusters)

    @property
    def all_sources(self) -> list[Source]:
        """All sources referenced in this section."""
        sources = []
        seen = set()
        for cluster in self.clusters:
            for source in cluster.sources:
                if source.id not in seen:
                    seen.add(source.id)
                    sources.append(source)
        return sources

    @property
    def all_visuals(self) -> list["VisualElement"]:
        """All visual elements from this section's clusters."""
        visuals: list["VisualElement"] = []
        seen: set[str] = set()
        for cluster in self.clusters:
            for visual in cluster.visual_elements:
                if visual.id not in seen:
                    seen.add(visual.id)
                    visuals.append(visual)
        return visuals

    @property
    def has_visuals(self) -> bool:
        """Whether this section has any visual content."""
        return bool(self.inline_figures or self.figure_plate or self.all_visuals)

    @property
    def total_figures(self) -> int:
        """Total number of figures in this section."""
        count = len(self.inline_figures)
        if self.figure_plate:
            count += len(self.figure_plate.figures)
        return count

    def collect_visuals_from_clusters(self, max_inline: int = 3) -> None:
        """Populate inline_figures and figure_plate from cluster visuals.

        Args:
            max_inline: Maximum figures to show inline (rest go to plate)
        """
        from neurosynth.models.visual import FigurePlate, ImageType

        all_visuals = self.all_visuals
        if not all_visuals:
            return

        # Priority: surgical_step > anatomical > imaging
        type_priority = {
            ImageType.SURGICAL_STEP: 100,
            ImageType.ANATOMICAL: 80,
            ImageType.IMAGING: 60,
            ImageType.TABLE: 40,
            ImageType.FLOWCHART: 30,
            ImageType.UNKNOWN: 10,
        }

        # Sort by type priority and confidence
        sorted_visuals = sorted(
            all_visuals,
            key=lambda v: (-type_priority.get(v.image_type, 0), -v.type_confidence),
        )

        # Select inline figures (prioritize surgical/anatomical, include others)
        # Include images that are either:
        # 1. High-confidence surgical/anatomical (best for inline)
        # 2. Any classified type with reasonable confidence (useful images)
        # 3. Unknown type but with some confidence (worth showing)
        self.inline_figures = [
            v for v in sorted_visuals[:max_inline]
            if (v.image_type in (ImageType.SURGICAL_STEP, ImageType.ANATOMICAL) and v.type_confidence >= 0.3)
            or (v.image_type not in (ImageType.UNKNOWN,) and v.type_confidence >= 0.2)
            or v.type_confidence >= 0.5  # High confidence for any type
        ]

        # Remaining go to figure plate
        inline_ids = {v.id for v in self.inline_figures}
        plate_visuals = [v for v in sorted_visuals if v.id not in inline_ids]

        if plate_visuals:
            self.figure_plate = FigurePlate(
                section_title=f"{self.title} - Visual References",
                figures=plate_visuals,
            )

    def to_latex(self, level_offset: int = 0) -> str:
        """Convert section to LaTeX format."""
        actual_level = self.level + level_offset
        commands = {
            1: "section",
            2: "subsection",
            3: "subsubsection",
            4: "paragraph",
        }
        cmd = commands.get(actual_level, "paragraph")

        lines = [f"\\{cmd}{{{self.title}}}"]
        if self.content:
            lines.append(self.content)

        for subsection in self.subsections:
            lines.append(subsection.to_latex(level_offset))

        return "\n\n".join(lines)


@dataclass
class Chapter:
    """A complete synthesized chapter."""

    title: str
    topic: str

    # Content structure
    sections: list[Section] = field(default_factory=list)

    # Front matter
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)

    # Back matter
    bibliography: list[Source] = field(default_factory=list)

    # Metadata
    total_words: int = 0
    total_sources: int = 0
    conflict_count: int = 0

    # Quality metrics
    source_coverage: float = 0.0  # % of source chunks used
    dedup_ratio: float = 0.0

    def __post_init__(self):
        """Calculate summary statistics."""
        self._calculate_stats()

    def _calculate_stats(self):
        """Recalculate all statistics."""
        self.total_words = sum(s.word_count for s in self.sections)
        self.total_sources = len(self.bibliography)
        self.conflict_count = sum(len(c.conflicts) for s in self.sections for c in s.clusters)

    def add_section(self, title: str, level: int = 1) -> Section:
        """Add a new section to the chapter."""
        section = Section(title=title, level=level)
        self.sections.append(section)
        return section

    @property
    def standard_sections(self) -> list[str]:
        """Standard neurosurgical chapter section order."""
        return [
            "Introduction",
            "Historical Background",
            "Epidemiology",
            "Anatomy and Neuroanatomy",
            "Pathophysiology",
            "Clinical Presentation",
            "Diagnostic Workup",
            "Classification",
            "Treatment Options",
            "Surgical Indications",
            "Surgical Technique",
            "Complications and Management",
            "Outcomes and Prognosis",
            "Controversies and Emerging Trends",
            "Conclusions",
        ]

    def to_latex(self) -> str:
        """Convert entire chapter to LaTeX document."""
        lines = [
            "\\documentclass[12pt,a4paper]{article}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{amsmath,amssymb}",
            "\\usepackage{graphicx}",
            "\\usepackage{hyperref}",
            "\\usepackage{natbib}",
            "\\usepackage{geometry}",
            "\\geometry{margin=1in}",
            "",
            f"\\title{{{self.title}}}",
            "\\author{NeuroSynth - Automated Knowledge Synthesis}",
            "\\date{\\today}",
            "",
            "\\begin{document}",
            "\\maketitle",
        ]

        # Abstract
        if self.abstract:
            lines.extend(
                [
                    "",
                    "\\begin{abstract}",
                    self.abstract,
                    "\\end{abstract}",
                ]
            )

        # Keywords
        if self.keywords:
            lines.extend(
                [
                    "",
                    f"\\textbf{{Keywords:}} {', '.join(self.keywords)}",
                ]
            )

        # Sections
        for section in self.sections:
            lines.extend(["", section.to_latex()])

        # Bibliography
        if self.bibliography:
            lines.extend(
                [
                    "",
                    "\\section*{References}",
                    "\\begin{enumerate}",
                ]
            )
            for source in sorted(self.bibliography, key=lambda s: s.citation_key):
                lines.append(f"\\item {source.to_citation()}")
            lines.append("\\end{enumerate}")

        lines.extend(["", "\\end{document}"])

        return "\n".join(lines)

    @property
    def total_figures(self) -> int:
        """Total number of figures across all sections."""
        return sum(s.total_figures for s in self.sections)

    @property
    def all_visuals(self) -> list["VisualElement"]:
        """All visual elements across all sections."""
        visuals: list["VisualElement"] = []
        seen: set[str] = set()
        for section in self.sections:
            for visual in section.all_visuals:
                if visual.id not in seen:
                    seen.add(visual.id)
                    visuals.append(visual)
        return visuals

    def collect_all_visuals(self, max_inline_per_section: int = 3) -> None:
        """Collect and organize visuals for all sections.

        Args:
            max_inline_per_section: Maximum inline figures per section
        """
        for section in self.sections:
            section.collect_visuals_from_clusters(max_inline_per_section)
            for subsection in section.subsections:
                subsection.collect_visuals_from_clusters(max_inline_per_section)

    def get_quality_report(self) -> dict[str, Any]:
        """Generate a quality report for the chapter."""
        return {
            "title": self.title,
            "total_words": self.total_words,
            "total_sources": self.total_sources,
            "total_figures": self.total_figures,
            "sections": len(self.sections),
            "conflicts_detected": self.conflict_count,
            "source_coverage": f"{self.source_coverage:.1%}",
            "deduplication_ratio": f"{self.dedup_ratio:.1f}:1",
            "words_per_source": self.total_words / max(1, self.total_sources),
            "meets_minimum_words": self.total_words >= 8000,
            "meets_citation_density": self.total_sources >= 15,
        }
