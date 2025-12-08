"""Procedural step correlator for surgical technique sections.

This module correlates numbered/labeled steps in synthesized text
with procedural image sequences detected during extraction.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from neurosynth.synthesis.positioned_figure import ProceduralMatch

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement


@dataclass
class TextStep:
    """A step extracted from synthesized text."""

    number: int  # Step number (1-indexed)
    paragraph_index: int  # Paragraph containing the step
    label: str  # Original label text (e.g., "Step 1", "1.")
    content: str  # Step content text


@dataclass
class SequenceMatch:
    """Result of matching a step to an image sequence."""

    visual: "VisualElement"
    sequence_id: str | None
    confidence: float


class ProceduralStepCorrelator:
    """Correlate text steps with procedural image sequences.

    Matches numbered steps in synthesized surgical technique text
    to images that are part of detected procedural sequences.
    """

    # Patterns to detect steps in synthesized text
    STEP_PATTERNS = [
        # "Step 1:", "Step 2.", etc.
        re.compile(r"^(?:Step|STEP)\s+(\d+)[.:\s](.+?)(?=\n|$)", re.MULTILINE),
        # "1. ", "2. " at start of line
        re.compile(r"^(\d+)\.\s+(.+?)(?=\n|$)", re.MULTILINE),
        # "Stage I:", "Stage 2:", etc.
        re.compile(
            r"^(?:Stage|STAGE)\s+(I{1,4}|IV|V|\d+)[.:\s](.+?)(?=\n|$)",
            re.MULTILINE | re.IGNORECASE,
        ),
        # "First,", "Second,", "Third," etc.
        re.compile(
            r"^(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)[,:\s]+(.+?)(?=\n|$)",
            re.MULTILINE | re.IGNORECASE,
        ),
    ]

    # Ordinal to number mapping
    ORDINAL_MAP = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }

    # Roman numeral conversion
    ROMAN_MAP = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}

    def correlate_steps(
        self,
        text: str,
        procedural_visuals: list["VisualElement"],
    ) -> list[ProceduralMatch]:
        """Match text steps to procedural image sequences.

        Args:
            text: Synthesized text containing surgical steps.
            procedural_visuals: VisualElements with is_procedural=True.

        Returns:
            List of ProceduralMatch objects linking steps to images.
        """
        if not procedural_visuals:
            return []

        # Extract steps from text
        text_steps = self._extract_text_steps(text)
        if not text_steps:
            return []

        # Group images by sequence
        sequences = self._group_by_sequence(procedural_visuals)

        matches: list[ProceduralMatch] = []
        used_visual_ids: set[str] = set()

        for text_step in text_steps:
            best_match = self._find_matching_image(
                text_step, sequences, used_visual_ids
            )

            if best_match:
                matches.append(
                    ProceduralMatch(
                        step_number=text_step.number,
                        paragraph_index=text_step.paragraph_index,
                        visual=best_match.visual,
                        sequence_id=best_match.sequence_id,
                        confidence=best_match.confidence,
                    )
                )
                used_visual_ids.add(best_match.visual.id)

        return matches

    def _extract_text_steps(self, text: str) -> list[TextStep]:
        """Extract numbered/labeled steps from text."""
        steps: list[TextStep] = []
        paragraphs = text.split("\n\n")

        for para_idx, paragraph in enumerate(paragraphs):
            for pattern in self.STEP_PATTERNS:
                for match in pattern.finditer(paragraph):
                    step_num = self._parse_step_number(match.group(1))
                    if step_num:
                        steps.append(
                            TextStep(
                                number=step_num,
                                paragraph_index=para_idx,
                                label=match.group(0)[:50],
                                content=match.group(2) if match.lastindex >= 2 else "",
                            )
                        )
                        break  # One step per paragraph max

        # Sort by step number
        steps.sort(key=lambda s: s.number)
        return steps

    def _parse_step_number(self, label: str) -> int | None:
        """Parse step number from various formats."""
        label_lower = label.lower().strip()

        # Direct number
        if label.isdigit():
            return int(label)

        # Ordinal word
        if label_lower in self.ORDINAL_MAP:
            return self.ORDINAL_MAP[label_lower]

        # Roman numeral
        if label_lower in self.ROMAN_MAP:
            return self.ROMAN_MAP[label_lower]

        return None

    def _group_by_sequence(
        self,
        visuals: list["VisualElement"],
    ) -> dict[str, list["VisualElement"]]:
        """Group visuals by their sequence_id."""
        sequences: dict[str, list[VisualElement]] = {}

        for visual in visuals:
            seq_id = visual.sequence_id or "ungrouped"
            if seq_id not in sequences:
                sequences[seq_id] = []
            sequences[seq_id].append(visual)

        # Sort each sequence by position
        for seq_id in sequences:
            sequences[seq_id].sort(
                key=lambda v: (v.sequence_position or 0, v.page_number)
            )

        return sequences

    def _find_matching_image(
        self,
        text_step: TextStep,
        sequences: dict[str, list["VisualElement"]],
        used_ids: set[str],
    ) -> SequenceMatch | None:
        """Find the best image match for a text step.

        Matching strategies (in priority order):
        1. Exact step label match
        2. Sequence position match
        3. Keyword overlap in step content
        """
        candidates: list[SequenceMatch] = []

        for seq_id, images in sequences.items():
            for img in images:
                if img.id in used_ids:
                    continue

                confidence = 0.0

                # Strategy 1: Exact label match
                if img.step_label:
                    normalized_img_label = self._normalize_label(img.step_label)
                    normalized_step_label = self._normalize_label(
                        f"Step {text_step.number}"
                    )
                    if normalized_img_label == normalized_step_label:
                        confidence = 0.95
                    elif str(text_step.number) in img.step_label:
                        confidence = 0.85

                # Strategy 2: Position match
                if confidence < 0.7 and img.sequence_position == text_step.number:
                    confidence = max(confidence, 0.80)

                # Strategy 3: Caption keyword overlap
                if confidence < 0.5:
                    overlap = self._keyword_overlap(text_step.content, img.caption)
                    if overlap > 0.3:
                        confidence = max(confidence, 0.5 + overlap * 0.3)

                if confidence > 0.4:
                    candidates.append(
                        SequenceMatch(
                            visual=img,
                            sequence_id=seq_id if seq_id != "ungrouped" else None,
                            confidence=confidence,
                        )
                    )

        if not candidates:
            return None

        # Return highest confidence match
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[0]

    def _normalize_label(self, label: str) -> str:
        """Normalize a step label for comparison."""
        label = label.lower().strip()
        label = re.sub(r"[.:\s]+", " ", label)
        label = re.sub(r"\s+", " ", label)
        return label.strip()

    def _keyword_overlap(self, text1: str, text2: str) -> float:
        """Calculate keyword overlap between two texts."""
        if not text1 or not text2:
            return 0.0

        words1 = set(re.findall(r"\b[a-z]{3,}\b", text1.lower()))
        words2 = set(re.findall(r"\b[a-z]{3,}\b", text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)
