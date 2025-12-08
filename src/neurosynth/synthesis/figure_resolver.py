"""Figure placeholder resolver for AI-generated text.

This module parses and resolves [FIGURE: ID] and [IMAGE: Type - Description]
placeholders from AI synthesis output to actual VisualElement references.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from neurosynth.synthesis.positioned_figure import MatchMethod, PlaceholderMatch

if TYPE_CHECKING:
    from neurosynth.models.visual import ImageType, VisualElement


@dataclass
class DescriptionMatchResult:
    """Result of matching an IMAGE description placeholder."""

    visual: "VisualElement"
    score: float
    matched_keywords: list[str] = field(default_factory=list)


class FigurePlaceholderResolver:
    """Parse and resolve figure placeholders from AI-generated text.

    Handles two placeholder formats:
    1. [FIGURE: ID] - Direct reference by figure ID
    2. [IMAGE: Type - Description] - Reference by type and description
    """

    # Regex patterns for placeholder detection
    FIGURE_ID_PATTERN = re.compile(r"\[FIGURE:\s*([a-zA-Z0-9_-]+)\]", re.IGNORECASE)
    IMAGE_DESC_PATTERN = re.compile(r"\[IMAGE:\s*(\w+)\s*-\s*([^\]]+)\]", re.IGNORECASE)

    def __init__(self, available_visuals: list["VisualElement"]):
        """Initialize resolver with available visual elements.

        Args:
            available_visuals: List of VisualElement objects to match against.
        """
        self.visuals = available_visuals
        self.visuals_by_id = {v.id: v for v in available_visuals}
        self.visuals_by_type = self._group_by_type(available_visuals)

    def _group_by_type(
        self, visuals: list["VisualElement"]
    ) -> dict[str, list["VisualElement"]]:
        """Group visuals by their image type."""
        grouped: dict[str, list[VisualElement]] = {}
        for v in visuals:
            type_key = v.image_type.value.lower()
            if type_key not in grouped:
                grouped[type_key] = []
            grouped[type_key].append(v)
        return grouped

    def resolve_placeholders(
        self,
        text: str,
    ) -> tuple[list[PlaceholderMatch], list[str]]:
        """Find all figure placeholders and resolve to actual images.

        Args:
            text: The synthesized text containing placeholders.

        Returns:
            Tuple of (matched placeholders, unresolved placeholder strings).
        """
        matches: list[PlaceholderMatch] = []
        unresolved: list[str] = []

        # 1. Find and resolve [FIGURE: ID] placeholders
        for match in self.FIGURE_ID_PATTERN.finditer(text):
            figure_id = match.group(1)
            position = match.start()
            paragraph_index = self._get_paragraph_index(text, position)

            if figure_id in self.visuals_by_id:
                matches.append(
                    PlaceholderMatch(
                        placeholder_text=match.group(0),
                        position=position,
                        paragraph_index=paragraph_index,
                        resolved_visual=self.visuals_by_id[figure_id],
                        match_method=MatchMethod.ID_MATCH,
                        confidence=1.0,
                    )
                )
            else:
                unresolved.append(match.group(0))

        # 2. Find and resolve [IMAGE: Type - Description] placeholders
        for match in self.IMAGE_DESC_PATTERN.finditer(text):
            image_type = match.group(1).lower()
            description = match.group(2).strip()
            position = match.start()
            paragraph_index = self._get_paragraph_index(text, position)

            best_match = self._find_best_match_by_description(image_type, description)

            if best_match and best_match.score >= 0.3:
                matches.append(
                    PlaceholderMatch(
                        placeholder_text=match.group(0),
                        position=position,
                        paragraph_index=paragraph_index,
                        resolved_visual=best_match.visual,
                        match_method=MatchMethod.SEMANTIC,
                        confidence=best_match.score,
                    )
                )
            else:
                unresolved.append(match.group(0))

        return matches, unresolved

    def _get_paragraph_index(self, text: str, position: int) -> int:
        """Convert character position to paragraph number (0-indexed)."""
        text_before = text[:position]
        # Count paragraph breaks (double newline or single newline with indent)
        paragraphs = re.split(r"\n\n+|\n(?=\s{2,})", text_before)
        return len(paragraphs) - 1

    def _find_best_match_by_description(
        self,
        image_type: str,
        description: str,
    ) -> DescriptionMatchResult | None:
        """Find the best matching image by type and description."""
        # Normalize type for matching
        type_mapping = {
            "overview": ["surgical_step", "anatomical", "photograph"],
            "detail": ["surgical_step", "anatomical"],
            "schematic": ["illustration", "anatomical", "flowchart"],
            "3d model": ["illustration", "anatomical"],
            "intraop": ["surgical_step", "photograph"],
            "danger zone": ["anatomical", "surgical_step"],
        }

        candidate_types = type_mapping.get(image_type, [image_type])
        candidates: list[VisualElement] = []

        for t in candidate_types:
            candidates.extend(self.visuals_by_type.get(t, []))

        if not candidates:
            candidates = self.visuals  # Fall back to all visuals

        return self._score_by_description(candidates, description)

    def _score_by_description(
        self,
        candidates: list["VisualElement"],
        description: str,
    ) -> DescriptionMatchResult | None:
        """Score candidates by keyword overlap with description."""
        if not candidates:
            return None

        # Extract keywords from description
        desc_words = set(self._normalize_text(description).split())
        if not desc_words:
            return None

        best_match: DescriptionMatchResult | None = None
        best_score = 0.0

        for visual in candidates:
            # Combine caption and context for matching
            visual_text = f"{visual.caption} {visual.context_text}"
            visual_words = set(self._normalize_text(visual_text).split())

            # Calculate Jaccard-like overlap
            if not visual_words:
                continue

            common = desc_words & visual_words
            union = desc_words | visual_words
            overlap_score = len(common) / len(union) if union else 0

            # Boost for matched keywords from extraction
            keyword_boost = 0.0
            matched_keywords: list[str] = []
            for kw in visual.keywords_matched:
                kw_lower = kw.lower()
                if kw_lower in description.lower():
                    keyword_boost += 0.1
                    matched_keywords.append(kw)

            total_score = min(overlap_score + keyword_boost, 1.0)

            if total_score > best_score:
                best_score = total_score
                best_match = DescriptionMatchResult(
                    visual=visual,
                    score=total_score,
                    matched_keywords=matched_keywords,
                )

        return best_match

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove punctuation)."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def strip_placeholders(self, text: str) -> str:
        """Remove all placeholder tags from text.

        Args:
            text: Text containing placeholders.

        Returns:
            Text with all [FIGURE:] and [IMAGE:] tags removed.
        """
        text = self.FIGURE_ID_PATTERN.sub("", text)
        text = self.IMAGE_DESC_PATTERN.sub("", text)
        # Clean up extra whitespace left by removal
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def get_placeholder_count(self, text: str) -> dict[str, int]:
        """Count placeholders by type in text.

        Args:
            text: Text to analyze.

        Returns:
            Dict with counts for 'figure_id' and 'image_desc' placeholders.
        """
        return {
            "figure_id": len(self.FIGURE_ID_PATTERN.findall(text)),
            "image_desc": len(self.IMAGE_DESC_PATTERN.findall(text)),
        }
