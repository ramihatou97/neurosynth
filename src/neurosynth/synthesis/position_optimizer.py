"""Position optimizer for figure placement.

This module optimizes figure placement across sections, balancing
proximity to relevant text, visual density limits, and subfigure grouping.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from neurosynth.synthesis.positioned_figure import (
    MatchMethod,
    PlaceholderMatch,
    PlacementType,
    PositionedFigure,
    ProceduralMatch,
    SemanticMatch,
)

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


@dataclass
class PositionOptimizerConfig:
    """Configuration for figure position optimization."""

    max_inline_per_section: int = 5  # Maximum inline figures per section
    max_inline_per_paragraph: int = 2  # Maximum figures after same paragraph
    min_words_between_figures: int = 80  # Minimum spacing (words)
    prefer_procedural_inline: bool = True  # Prioritize procedural images inline
    group_subfigures: bool = True  # Group consecutive procedural as subfigures
    min_subfigure_group_size: int = 2  # Minimum images to form subfigure group
    include_high_priority_unused: bool = True  # Put unused high-priority in plate


class PositionOptimizer:
    """Optimize figure placement across a section.

    Combines matches from placeholder resolver, semantic matcher,
    and procedural correlator, then determines final placement
    respecting density limits and grouping preferences.
    """

    def __init__(self, config: PositionOptimizerConfig | None = None):
        """Initialize optimizer with configuration.

        Args:
            config: Optimization configuration options.
        """
        self.config = config or PositionOptimizerConfig()

    def optimize(
        self,
        placeholder_matches: list[PlaceholderMatch],
        semantic_matches: list[SemanticMatch],
        procedural_matches: list[ProceduralMatch],
        section_word_count: int,
        available_visuals: list["VisualElement"],
    ) -> list[PositionedFigure]:
        """Combine all match sources and optimize placement.

        Priority order:
        1. ID matches (explicit placeholders) - highest priority
        2. Procedural matches (surgical steps) - high priority
        3. Semantic matches - medium priority
        4. Type-priority unmatched images - low priority (to plate)

        Args:
            placeholder_matches: Results from FigurePlaceholderResolver.
            semantic_matches: Results from SemanticImageMatcher.
            procedural_matches: Results from ProceduralStepCorrelator.
            section_word_count: Total words in section (for density calc).
            available_visuals: All available VisualElement objects.

        Returns:
            List of PositionedFigure with optimized placements.
        """
        positioned: list[PositionedFigure] = []
        used_ids: set[str] = set()
        paragraphs_with_figures: dict[int, int] = {}  # para_idx -> figure count

        # 1. Process placeholder matches (highest priority - explicit references)
        for match in placeholder_matches:
            if match.resolved_visual.id in used_ids:
                continue

            if self._can_place_inline(match.paragraph_index, paragraphs_with_figures):
                positioned.append(
                    self._create_positioned(
                        visual=match.resolved_visual,
                        anchor_paragraph=match.paragraph_index,
                        placement_type=PlacementType.INLINE_AFTER,
                        match_method=MatchMethod.ID_MATCH,
                        confidence=match.confidence,
                        placeholder=match.placeholder_text,
                    )
                )
                used_ids.add(match.resolved_visual.id)
                self._increment_para_count(
                    paragraphs_with_figures, match.paragraph_index
                )

        # 2. Process procedural matches (group consecutive as subfigures)
        procedural_groups = self._group_consecutive_procedural(procedural_matches)
        for group in procedural_groups:
            self._process_procedural_group(
                group, positioned, used_ids, paragraphs_with_figures
            )

        # 3. Process semantic matches (fill remaining inline slots)
        inline_count = sum(
            1 for p in positioned if p.placement_type != PlacementType.PLATE
        )
        remaining_inline = self.config.max_inline_per_section - inline_count

        sorted_semantic = sorted(semantic_matches, key=lambda m: m.score, reverse=True)
        for match in sorted_semantic:
            if remaining_inline <= 0:
                break
            if match.visual.id in used_ids:
                continue
            if self._can_place_inline(match.paragraph_index, paragraphs_with_figures):
                positioned.append(
                    self._create_positioned(
                        visual=match.visual,
                        anchor_paragraph=match.paragraph_index,
                        placement_type=PlacementType.INLINE_AFTER,
                        match_method=MatchMethod.SEMANTIC,
                        confidence=match.score,
                    )
                )
                used_ids.add(match.visual.id)
                self._increment_para_count(
                    paragraphs_with_figures, match.paragraph_index
                )
                remaining_inline -= 1

        # 4. Add high-priority unused images to plate
        if self.config.include_high_priority_unused:
            for visual in available_visuals:
                if visual.id in used_ids:
                    continue
                if visual.image_type.is_high_priority:
                    positioned.append(
                        self._create_positioned(
                            visual=visual,
                            anchor_paragraph=None,
                            placement_type=PlacementType.PLATE,
                            match_method=MatchMethod.PRIORITY,
                            confidence=0.5,
                        )
                    )
                    used_ids.add(visual.id)

        return positioned

    def _can_place_inline(
        self,
        paragraph_index: int,
        paragraphs_with_figures: dict[int, int],
    ) -> bool:
        """Check if we can place another figure after this paragraph."""
        current_count = paragraphs_with_figures.get(paragraph_index, 0)
        return current_count < self.config.max_inline_per_paragraph

    def _increment_para_count(
        self,
        paragraphs_with_figures: dict[int, int],
        paragraph_index: int,
    ) -> None:
        """Increment figure count for a paragraph."""
        paragraphs_with_figures[paragraph_index] = (
            paragraphs_with_figures.get(paragraph_index, 0) + 1
        )

    def _create_positioned(
        self,
        visual: "VisualElement",
        anchor_paragraph: int | None,
        placement_type: PlacementType,
        match_method: MatchMethod,
        confidence: float,
        placeholder: str | None = None,
        subfigure_group_id: str | None = None,
        subfigure_label: str | None = None,
    ) -> PositionedFigure:
        """Create a PositionedFigure and update the visual's output fields."""
        # Update visual's output placement fields
        visual.output_anchor_paragraph = anchor_paragraph
        visual.output_placement = placement_type.value
        visual.output_match_method = match_method.value
        visual.output_match_confidence = confidence
        visual.resolved_from_placeholder = placeholder
        visual.subfigure_group_id = subfigure_group_id
        visual.subfigure_label = subfigure_label

        return PositionedFigure(
            visual=visual,
            anchor_paragraph_index=anchor_paragraph,
            placement_type=placement_type,
            match_method=match_method,
            match_confidence=confidence,
            resolved_placeholder=placeholder,
            subfigure_group_id=subfigure_group_id,
            subfigure_label=subfigure_label,
        )

    def _group_consecutive_procedural(
        self,
        matches: list[ProceduralMatch],
    ) -> list[list[ProceduralMatch]]:
        """Group consecutive procedural matches by sequence and adjacency."""
        if not matches:
            return []

        # Sort by sequence_id then step_number
        sorted_matches = sorted(
            matches, key=lambda m: (m.sequence_id or "", m.step_number)
        )

        groups: list[list[ProceduralMatch]] = []
        current_group: list[ProceduralMatch] = []
        prev_seq_id: str | None = None
        prev_step: int | None = None

        for match in sorted_matches:
            # Start new group if sequence changed or step not consecutive
            if current_group:
                seq_changed = match.sequence_id != prev_seq_id
                not_consecutive = (
                    prev_step is not None and match.step_number != prev_step + 1
                )
                if seq_changed or not_consecutive:
                    groups.append(current_group)
                    current_group = []

            current_group.append(match)
            prev_seq_id = match.sequence_id
            prev_step = match.step_number

        if current_group:
            groups.append(current_group)

        return groups

    def _process_procedural_group(
        self,
        group: list[ProceduralMatch],
        positioned: list[PositionedFigure],
        used_ids: set[str],
        paragraphs_with_figures: dict[int, int],
    ) -> None:
        """Process a group of procedural matches."""
        if not group:
            return

        # Determine if we should create a subfigure group
        should_group = (
            self.config.group_subfigures
            and len(group) >= self.config.min_subfigure_group_size
        )

        if should_group:
            # Create subfigure group anchored to first step's paragraph
            anchor_para = group[0].paragraph_index
            group_id = f"proc_{group[0].step_number}_{group[-1].step_number}"

            for i, match in enumerate(group):
                if match.visual.id in used_ids:
                    continue

                positioned.append(
                    self._create_positioned(
                        visual=match.visual,
                        anchor_paragraph=anchor_para,
                        placement_type=PlacementType.SUBFIGURE,
                        match_method=MatchMethod.PROCEDURAL,
                        confidence=match.confidence,
                        subfigure_group_id=group_id,
                        subfigure_label=chr(ord("a") + i),
                    )
                )
                used_ids.add(match.visual.id)
        else:
            # Place individually
            for match in group:
                if match.visual.id in used_ids:
                    continue

                if self._can_place_inline(
                    match.paragraph_index, paragraphs_with_figures
                ):
                    positioned.append(
                        self._create_positioned(
                            visual=match.visual,
                            anchor_paragraph=match.paragraph_index,
                            placement_type=PlacementType.INLINE_AFTER,
                            match_method=MatchMethod.PROCEDURAL,
                            confidence=match.confidence,
                        )
                    )
                    used_ids.add(match.visual.id)
                    self._increment_para_count(
                        paragraphs_with_figures, match.paragraph_index
                    )
