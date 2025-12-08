"""Semantic image matcher for paragraph-level figure matching.

This module uses embedding similarity and keyword analysis to match
synthesized paragraphs to available images when explicit placeholders
are not present.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from neurosynth.synthesis.positioned_figure import SemanticMatch

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


@dataclass
class ScoredCandidate:
    """A candidate image with scoring details."""

    visual: "VisualElement"
    score: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class SemanticMatcherConfig:
    """Configuration for semantic matching."""

    similarity_threshold: float = 0.4  # Minimum score to consider a match
    caption_weight: float = 0.40  # Weight for caption similarity
    keyword_weight: float = 0.35  # Weight for keyword overlap
    type_weight: float = 0.15  # Weight for type relevance
    context_weight: float = 0.10  # Weight for context similarity
    min_paragraph_words: int = 15  # Minimum words to consider for matching


class SemanticImageMatcher:
    """Match synthesized paragraphs to images using semantic similarity.

    Uses multiple signals:
    1. Caption text similarity (keyword overlap)
    2. Matched neurosurgical keywords
    3. Image type relevance to paragraph content
    4. Context text similarity
    """

    def __init__(self, config: SemanticMatcherConfig | None = None):
        """Initialize the semantic matcher.

        Args:
            config: Configuration options for matching behavior.
        """
        self.config = config or SemanticMatcherConfig()

    def match_paragraphs_to_images(
        self,
        paragraphs: list[str],
        available_visuals: list["VisualElement"],
        already_matched_ids: set[str] | None = None,
    ) -> list[SemanticMatch]:
        """Match paragraphs to semantically similar images.

        Args:
            paragraphs: List of paragraph strings from synthesized text.
            available_visuals: Available VisualElement objects.
            already_matched_ids: Set of visual IDs already matched (excluded).

        Returns:
            List of SemanticMatch objects for matched paragraphs.
        """
        if already_matched_ids is None:
            already_matched_ids = set()

        matches: list[SemanticMatch] = []
        used_ids = set(already_matched_ids)

        for para_idx, paragraph in enumerate(paragraphs):
            # Skip short paragraphs
            word_count = len(paragraph.split())
            if word_count < self.config.min_paragraph_words:
                continue

            # Score all available candidates
            candidates = self._score_candidates(
                paragraph,
                [v for v in available_visuals if v.id not in used_ids],
            )

            # Take best match above threshold
            if candidates and candidates[0].score >= self.config.similarity_threshold:
                best = candidates[0]
                matches.append(
                    SemanticMatch(
                        paragraph_index=para_idx,
                        visual=best.visual,
                        score=best.score,
                        match_signals=best.signals,
                    )
                )
                used_ids.add(best.visual.id)

        return matches

    def _score_candidates(
        self,
        paragraph: str,
        visuals: list["VisualElement"],
    ) -> list[ScoredCandidate]:
        """Score all available images against a paragraph.

        Returns candidates sorted by score (highest first).
        """
        candidates: list[ScoredCandidate] = []
        para_lower = paragraph.lower()
        para_words = set(self._extract_words(paragraph))

        for visual in visuals:
            signals: dict[str, float] = {}

            # 1. Caption similarity (word overlap)
            signals["caption"] = self._text_similarity(para_words, visual.caption)

            # 2. Keyword match score
            signals["keyword"] = self._keyword_score(para_lower, visual)

            # 3. Type relevance
            signals["type"] = self._type_relevance(para_lower, visual)

            # 4. Context similarity
            signals["context"] = self._text_similarity(para_words, visual.context_text)

            # Weighted total score
            score = (
                signals["caption"] * self.config.caption_weight
                + signals["keyword"] * self.config.keyword_weight
                + signals["type"] * self.config.type_weight
                + signals["context"] * self.config.context_weight
            )

            candidates.append(
                ScoredCandidate(visual=visual, score=score, signals=signals)
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _text_similarity(self, para_words: set[str], text: str) -> float:
        """Calculate word overlap similarity between paragraph and text."""
        if not text:
            return 0.0

        text_words = set(self._extract_words(text))
        if not text_words or not para_words:
            return 0.0

        # Jaccard similarity
        intersection = para_words & text_words
        union = para_words | text_words
        return len(intersection) / len(union) if union else 0.0

    def _keyword_score(self, para_lower: str, visual: "VisualElement") -> float:
        """Score based on matched neurosurgical keywords."""
        if not visual.keywords_matched:
            return 0.0

        matched = 0
        for keyword in visual.keywords_matched:
            if keyword.lower() in para_lower:
                matched += 1

        # Normalize by number of keywords (max 1.0)
        return min(matched / max(len(visual.keywords_matched), 1), 1.0)

    def _type_relevance(self, para_lower: str, visual: "VisualElement") -> float:
        """Score type relevance based on paragraph content hints."""
        type_indicators = {
            "surgical_step": [
                "incision",
                "dissect",
                "retract",
                "insert",
                "remove",
                "step",
                "procedure",
                "technique",
                "approach",
                "expose",
                "resect",
            ],
            "anatomical": [
                "anatomy",
                "nerve",
                "artery",
                "vein",
                "muscle",
                "bone",
                "ligament",
                "structure",
                "landmark",
                "relationship",
            ],
            "imaging": [
                "mri",
                "ct",
                "scan",
                "image",
                "radiograph",
                "angiography",
                "fluoroscopy",
                "x-ray",
                "t1",
                "t2",
                "flair",
            ],
            "illustration": [
                "diagram",
                "schematic",
                "illustration",
                "drawing",
                "model",
                "representation",
            ],
            "flowchart": [
                "algorithm",
                "decision",
                "pathway",
                "protocol",
                "workflow",
                "criteria",
            ],
        }

        visual_type = visual.image_type.value
        indicators = type_indicators.get(visual_type, [])

        if not indicators:
            return 0.3  # Neutral score for unknown types

        matched = sum(1 for ind in indicators if ind in para_lower)
        return min(matched / 3, 1.0)  # Cap at 3 matches for full score

    def _extract_words(self, text: str) -> list[str]:
        """Extract significant words from text (lowercase, filtered)."""
        # Common stopwords to filter
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "of",
            "to",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "and",
            "or",
            "but",
            "if",
            "then",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
        }

        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        return [w for w in words if w not in stopwords]
