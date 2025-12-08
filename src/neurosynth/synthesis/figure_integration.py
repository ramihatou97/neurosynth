"""Figure integration pipeline for synthesized chapters.

This module orchestrates the complete figure-text integration process,
coordinating placeholder resolution, semantic matching, procedural
correlation, and position optimization.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console

from neurosynth.synthesis.figure_resolver import FigurePlaceholderResolver
from neurosynth.synthesis.position_optimizer import (
    PositionOptimizer,
    PositionOptimizerConfig,
)
from neurosynth.synthesis.positioned_figure import (
    FigureLibrary,
    PlacementType,
    PositionedFigure,
    SectionFigureResolution,
)
from neurosynth.synthesis.procedural_correlator import ProceduralStepCorrelator
from neurosynth.synthesis.semantic_matcher import (
    SemanticImageMatcher,
    SemanticMatcherConfig,
)

if TYPE_CHECKING:
    from neurosynth.models.output import Chapter, Section
    from neurosynth.models.visual import FigurePlate, VisualElement

console = Console()


@dataclass
class FigureIntegrationConfig:
    """Configuration for the figure integration pipeline."""

    semantic_threshold: float = 0.4
    optimizer_config: PositionOptimizerConfig = field(
        default_factory=PositionOptimizerConfig
    )
    enable_semantic_matching: bool = True
    enable_procedural_correlation: bool = True
    enable_placeholder_resolution: bool = True


@dataclass
class ChapterFigureResolution:
    """Complete figure resolution results for a chapter."""

    section_resolutions: dict[str, SectionFigureResolution] = field(
        default_factory=dict
    )
    figure_library: FigureLibrary = field(default_factory=FigureLibrary)
    total_positioned: int = 0
    total_unresolved_placeholders: int = 0

    @property
    def unused_count(self) -> int:
        """Number of unused figures in the library."""
        return self.figure_library.unused_count


class FigureIntegrationPipeline:
    """Master orchestrator for figure-text integration.

    Coordinates all resolution components to produce positioned figures
    for each section of a synthesized chapter.
    """

    def __init__(
        self,
        available_visuals: list["VisualElement"],
        config: FigureIntegrationConfig | None = None,
    ):
        """Initialize the pipeline.

        Args:
            available_visuals: All VisualElement objects available for matching.
            config: Configuration options for the pipeline.
        """
        self.visuals = available_visuals
        self.config = config or FigureIntegrationConfig()

        # Initialize sub-components
        self.placeholder_resolver = FigurePlaceholderResolver(available_visuals)
        self.semantic_matcher = SemanticImageMatcher(
            SemanticMatcherConfig(similarity_threshold=self.config.semantic_threshold)
        )
        self.procedural_correlator = ProceduralStepCorrelator()
        self.position_optimizer = PositionOptimizer(self.config.optimizer_config)

        # Initialize figure library
        self.figure_library = FigureLibrary(all_figures=list(available_visuals))

    def resolve_section(
        self,
        section: "Section",
        used_figure_ids: set[str],
    ) -> SectionFigureResolution:
        """Resolve all figure placements for a single section.

        Args:
            section: The Section to process.
            used_figure_ids: Set of figure IDs already used (excluded).

        Returns:
            SectionFigureResolution with positioned figures.
        """
        raw_text = section.content
        if not raw_text:
            return SectionFigureResolution(
                section_title=section.title,
                raw_text="",
                resolved_text="",
            )

        # Filter to unused visuals
        available = [v for v in self.visuals if v.id not in used_figure_ids]

        # 1. Resolve explicit placeholders
        placeholder_matches = []
        unresolved = []
        if self.config.enable_placeholder_resolution:
            placeholder_matches, unresolved = (
                self.placeholder_resolver.resolve_placeholders(raw_text)
            )

        matched_ids = {m.resolved_visual.id for m in placeholder_matches}

        # 2. Split into paragraphs for semantic matching
        paragraphs = self._split_paragraphs(raw_text)

        # 3. Semantic matching
        semantic_matches = []
        if self.config.enable_semantic_matching:
            semantic_matches = self.semantic_matcher.match_paragraphs_to_images(
                paragraphs,
                [v for v in available if v.id not in matched_ids],
                matched_ids,
            )

        # 4. Procedural step correlation
        procedural_matches = []
        if self.config.enable_procedural_correlation:
            procedural_visuals = [
                v for v in available if v.is_procedural and v.id not in matched_ids
            ]
            procedural_matches = self.procedural_correlator.correlate_steps(
                raw_text,
                procedural_visuals,
            )

        # 5. Optimize positions
        positioned = self.position_optimizer.optimize(
            placeholder_matches,
            semantic_matches,
            procedural_matches,
            section.word_count,
            available,
        )

        # 6. Strip placeholders from text
        resolved_text = self.placeholder_resolver.strip_placeholders(raw_text)

        # 7. Mark used figures in library
        for pf in positioned:
            self.figure_library.mark_used(pf.visual.id)
            used_figure_ids.add(pf.visual.id)

        return SectionFigureResolution(
            section_title=section.title,
            raw_text=raw_text,
            resolved_text=resolved_text,
            positioned_figures=positioned,
            unmatched_placeholders=unresolved,
            unused_figures=[v for v in available if v.id not in used_figure_ids],
        )

    def resolve_chapter(
        self,
        chapter: "Chapter",
    ) -> ChapterFigureResolution:
        """Resolve figures for an entire chapter.

        Processes all sections, tracking figure usage across sections
        to prevent duplicates. Updates section content and figure lists.

        Args:
            chapter: The Chapter to process.

        Returns:
            ChapterFigureResolution with all section results and library.
        """
        from neurosynth.models.visual import FigurePlate

        results = ChapterFigureResolution(figure_library=self.figure_library)
        used_ids: set[str] = set()

        console.print(
            f"[dim]  Resolving figures for {len(chapter.sections)} sections...[/dim]"
        )

        for section in chapter.sections:
            resolution = self.resolve_section(section, used_ids)
            results.section_resolutions[section.title] = resolution

            # Update section content (placeholders removed)
            section.content = resolution.resolved_text

            # Separate inline and plate figures
            inline_figures: list[VisualElement] = []
            plate_figures: list[VisualElement] = []

            for pf in resolution.positioned_figures:
                if pf.placement_type in (
                    PlacementType.INLINE_AFTER,
                    PlacementType.SUBFIGURE,
                ):
                    inline_figures.append(pf.visual)
                else:
                    plate_figures.append(pf.visual)

            section.inline_figures = inline_figures

            if plate_figures:
                section.figure_plate = FigurePlate(
                    section_title=f"{section.title} - Additional Figures",
                    figures=plate_figures,
                )

            # Log progress
            if resolution.positioned_figures:
                console.print(
                    f"[dim]    {section.title}: "
                    f"{resolution.inline_count} inline, "
                    f"{resolution.plate_count} in plate[/dim]"
                )

            results.total_positioned += resolution.total_positioned
            results.total_unresolved_placeholders += len(
                resolution.unmatched_placeholders
            )

            # Process subsections recursively
            for subsection in section.subsections:
                sub_resolution = self.resolve_section(subsection, used_ids)
                results.section_resolutions[subsection.title] = sub_resolution
                subsection.content = sub_resolution.resolved_text

                sub_inline = [
                    pf.visual
                    for pf in sub_resolution.positioned_figures
                    if pf.placement_type
                    in (PlacementType.INLINE_AFTER, PlacementType.SUBFIGURE)
                ]
                subsection.inline_figures = sub_inline

                results.total_positioned += sub_resolution.total_positioned

        # Log summary
        console.print(
            f"[dim]  Total: {results.total_positioned} figures positioned, "
            f"{results.figure_library.unused_count} in library[/dim]"
        )

        return results

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs."""
        # Split on double newlines or significant whitespace
        paragraphs = re.split(r"\n\n+", text)
        # Filter empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def get_figure_library(self) -> FigureLibrary:
        """Get the figure library with used/unused tracking.

        Returns:
            FigureLibrary with all figures and usage status.
        """
        return self.figure_library
