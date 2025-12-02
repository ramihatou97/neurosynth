"""
Procedural Sequence Detector
=============================
Detects and orders surgical procedural step sequences from images.

Features:
- Identifies step sequences from captions (Step 1, 2, 3...)
- Detects subfigure sequences (Fig 3a, 3b, 3c...)
- Orders images into coherent procedural sequences
- Validates sequence continuity
- Groups related procedures

Version: 3.0
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .config import NeuroSynthEnhancedConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class SequenceType(Enum):
    """Type of procedural sequence."""

    NUMBERED_STEPS = "numbered_steps"  # Step 1, Step 2...
    SUBFIGURES = "subfigures"  # Fig 3a, 3b, 3c...
    LETTERED_PANELS = "lettered_panels"  # (A), (B), (C)...
    STAGED_PROCEDURE = "staged_procedure"  # Stage 1, Phase 2...
    IMPLICIT = "implicit"  # Inferred from context
    UNKNOWN = "unknown"


@dataclass
class SequenceElement:
    """Single element in a procedural sequence."""

    image_id: str
    page_number: int
    position: tuple[float, float, float, float]  # bbox

    # Sequence info
    sequence_number: int | None = None
    subfigure_id: str | None = None
    step_label: str | None = None

    # Content
    caption: str | None = None
    description: str | None = None

    # Classification
    sequence_type: SequenceType = SequenceType.UNKNOWN
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "page": self.page_number,
            "position": self.position,
            "sequence_number": self.sequence_number,
            "subfigure_id": self.subfigure_id,
            "step_label": self.step_label,
            "caption": self.caption,
            "sequence_type": self.sequence_type.value,
            "confidence": self.confidence,
        }


@dataclass
class ProceduralSequence:
    """A complete procedural sequence."""

    sequence_id: str
    title: str
    sequence_type: SequenceType
    elements: list[SequenceElement] = field(default_factory=list)

    # Metadata
    procedure_keywords: list[str] = field(default_factory=list)
    chapter: str | None = None
    start_page: int = 0
    end_page: int = 0

    # Quality metrics
    completeness: float = 0.0  # 0-1, are there gaps?
    confidence: float = 0.0

    @property
    def length(self) -> int:
        return len(self.elements)

    @property
    def is_complete(self) -> bool:
        """Check if sequence has no gaps."""
        return self.completeness >= 0.9

    def to_dict(self) -> dict:
        return {
            "sequence_id": self.sequence_id,
            "title": self.title,
            "sequence_type": self.sequence_type.value,
            "length": self.length,
            "elements": [e.to_dict() for e in self.elements],
            "procedure_keywords": self.procedure_keywords,
            "chapter": self.chapter,
            "pages": f"{self.start_page}-{self.end_page}",
            "completeness": self.completeness,
            "confidence": self.confidence,
        }


# =============================================================================
# STEP NUMBER EXTRACTOR
# =============================================================================


class StepNumberExtractor:
    """
    Extract step/sequence numbers from various formats.
    """

    # Patterns for step extraction
    PATTERNS = {
        "step": [
            (r"(?i)\bstep\s*(\d+)", 1.0),
            (r"(?i)\bstage\s*(\d+)", 0.9),
            (r"(?i)\bphase\s*(\d+)", 0.9),
            (r"(?i)\bpart\s*(\d+)", 0.8),
        ],
        "figure_subfig": [
            (r"(?i)fig(?:ure)?\.?\s*\d+([a-z])", 0.95),
            (r"(?i)fig(?:ure)?\.?\s*\d+\.(\d+)", 0.9),
        ],
        "panel": [
            (r"\(([A-Z])\)", 0.85),
            (r"\(([a-z])\)", 0.85),
            (r"(?i)\bpanel\s*([A-Za-z])", 0.9),
        ],
        "numbered": [
            (r"^(\d+)\.\s+", 0.7),
            (r"^\((\d+)\)\s+", 0.75),
        ],
    }

    def extract(self, text: str) -> tuple[int, SequenceType, float] | None:
        """
        Extract sequence number from text.

        Returns:
            Tuple of (number, sequence_type, confidence) or None
        """
        if not text:
            return None

        # Try each pattern category
        for category, patterns in self.PATTERNS.items():
            for pattern, confidence in patterns:
                match = re.search(pattern, text)
                if match:
                    value = match.group(1)

                    # Convert to integer
                    if value.isdigit():
                        num = int(value)
                    elif value.isalpha() and len(value) == 1:
                        # Convert letter to number (a=1, b=2, etc.)
                        num = ord(value.lower()) - ord("a") + 1
                    else:
                        continue

                    # Determine sequence type
                    if category == "step":
                        seq_type = SequenceType.NUMBERED_STEPS
                    elif category == "figure_subfig":
                        seq_type = SequenceType.SUBFIGURES
                    elif category == "panel":
                        seq_type = SequenceType.LETTERED_PANELS
                    else:
                        seq_type = SequenceType.NUMBERED_STEPS

                    return (num, seq_type, confidence)

        return None

    def extract_all(self, text: str) -> list[tuple[int, SequenceType, float]]:
        """Extract all sequence numbers from text."""
        results = []

        for category, patterns in self.PATTERNS.items():
            for pattern, confidence in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    value = match.group(1)

                    if value.isdigit():
                        num = int(value)
                    elif value.isalpha() and len(value) == 1:
                        num = ord(value.lower()) - ord("a") + 1
                    else:
                        continue

                    if category == "step":
                        seq_type = SequenceType.NUMBERED_STEPS
                    elif category == "figure_subfig":
                        seq_type = SequenceType.SUBFIGURES
                    elif category == "panel":
                        seq_type = SequenceType.LETTERED_PANELS
                    else:
                        seq_type = SequenceType.NUMBERED_STEPS

                    results.append((num, seq_type, confidence))

        return results


# =============================================================================
# PROCEDURE KEYWORD DETECTOR
# =============================================================================


class ProcedureKeywordDetector:
    """
    Detect procedural keywords to identify surgical sequences.
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        keywords = (config or NeuroSynthEnhancedConfig()).keywords
        self.procedure_keywords = {kw.lower() for kw in keywords.procedure}
        self.anatomy_keywords = {kw.lower() for kw in keywords.anatomy}

        # Additional sequence-specific keywords
        self.sequence_indicators = {
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
            "initial",
            "final",
            "next",
            "then",
            "subsequently",
            "followed by",
            "after",
            "before",
            "during",
            "beginning",
            "completion",
            "completed",
        }

    def detect(self, text: str) -> dict[str, Any]:
        """
        Detect procedural keywords in text.

        Returns:
            Dict with 'procedure_keywords', 'anatomy_keywords',
            'sequence_indicators', 'is_procedural'
        """
        if not text:
            return {
                "procedure_keywords": [],
                "anatomy_keywords": [],
                "sequence_indicators": [],
                "is_procedural": False,
                "procedural_score": 0.0,
            }

        text_lower = text.lower()

        # Find matches
        proc_found = [kw for kw in self.procedure_keywords if kw in text_lower]
        anat_found = [kw for kw in self.anatomy_keywords if kw in text_lower]
        seq_found = [kw for kw in self.sequence_indicators if kw in text_lower]

        # Calculate score
        score = 0.0
        score += len(proc_found) * 0.3
        score += len(seq_found) * 0.2
        score += min(len(anat_found) * 0.1, 0.3)

        return {
            "procedure_keywords": proc_found,
            "anatomy_keywords": anat_found,
            "sequence_indicators": seq_found,
            "is_procedural": score >= 0.3,
            "procedural_score": min(score, 1.0),
        }


# =============================================================================
# SEQUENCE DETECTOR
# =============================================================================


class ProceduralSequenceDetector:
    """
    Detect and order surgical procedural sequences.

    Works by:
    1. Extracting step numbers from image captions/context
    2. Grouping images by figure number prefix
    3. Detecting implicit sequences from page/position ordering
    4. Validating sequence continuity
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.config = config or NeuroSynthEnhancedConfig()
        self.step_extractor = StepNumberExtractor()
        self.keyword_detector = ProcedureKeywordDetector(config)

    def detect_sequences(
        self, images: list[dict[str, Any]]
    ) -> list[ProceduralSequence]:
        """
        Detect procedural sequences from a list of images.

        Args:
            images: List of image dicts with keys:
                - 'id': Image identifier
                - 'page': Page number
                - 'bbox': Bounding box (x0, y0, x1, y1)
                - 'caption': Caption text (optional)
                - 'figure_id': Figure identifier (optional)
                - 'context': Surrounding text (optional)
                - 'chapter': Chapter name (optional)

        Returns:
            List of ProceduralSequence objects
        """
        # Extract sequence elements
        elements = self._extract_elements(images)

        # Group into candidate sequences
        candidates = self._group_into_sequences(elements)

        # Validate and filter sequences
        sequences = self._validate_sequences(candidates)

        # Sort elements within each sequence
        for seq in sequences:
            self._sort_sequence_elements(seq)
            self._calculate_sequence_metrics(seq)

        return sequences

    def _extract_elements(self, images: list[dict[str, Any]]) -> list[SequenceElement]:
        """Extract sequence elements from images."""
        elements = []

        for img in images:
            # Try to extract step number
            caption = img.get("caption", "")
            figure_id = img.get("figure_id", "")
            context = img.get("context", "")

            # Combine text for analysis
            combined_text = f"{caption} {figure_id} {context}"

            extraction = self.step_extractor.extract(combined_text)
            keywords = self.keyword_detector.detect(combined_text)

            element = SequenceElement(
                image_id=img.get("id", ""),
                page_number=img.get("page", 0),
                position=img.get("bbox", (0, 0, 0, 0)),
                caption=caption,
                description=context[:200] if context else None,
            )

            if extraction:
                num, seq_type, confidence = extraction
                element.sequence_number = num
                element.sequence_type = seq_type
                element.confidence = confidence

                # Extract step label
                if seq_type == SequenceType.NUMBERED_STEPS:
                    element.step_label = f"Step {num}"
                elif seq_type == SequenceType.SUBFIGURES:
                    element.subfigure_id = chr(ord("a") + num - 1)
                    element.step_label = f"({element.subfigure_id})"
                elif seq_type == SequenceType.LETTERED_PANELS:
                    letter = chr(ord("A") + num - 1)
                    element.step_label = f"({letter})"

            # If no explicit number but procedural keywords present
            elif keywords["is_procedural"]:
                element.sequence_type = SequenceType.IMPLICIT
                element.confidence = keywords["procedural_score"] * 0.5

            elements.append(element)

        return elements

    def _group_into_sequences(
        self, elements: list[SequenceElement]
    ) -> list[list[SequenceElement]]:
        """Group elements into candidate sequences."""
        # Strategy 1: Group by figure number prefix (e.g., Fig 3a, 3b, 3c)
        by_figure_prefix = defaultdict(list)

        for elem in elements:
            if elem.caption:
                # Extract figure number prefix
                match = re.search(r"(?i)fig(?:ure)?\.?\s*(\d+)", elem.caption)
                if match:
                    prefix = match.group(1)
                    by_figure_prefix[prefix].append(elem)

        # Strategy 2: Group consecutive numbered steps
        numbered_steps = [
            e for e in elements if e.sequence_type == SequenceType.NUMBERED_STEPS
        ]
        step_groups = self._group_consecutive(numbered_steps)

        # Strategy 3: Group by chapter
        by_chapter = defaultdict(list)
        for elem in elements:
            # Infer chapter from page if not explicit
            # For now, group by page proximity
            page_group = elem.page_number // 5  # Group every 5 pages
            by_chapter[page_group].append(elem)

        # Combine strategies
        candidates = []

        # Add figure-prefix groups (highest quality)
        for prefix, group in by_figure_prefix.items():
            if len(group) >= 2:
                candidates.append(group)

        # Add consecutive step groups
        for group in step_groups:
            if len(group) >= 2:
                # Check for overlap with existing candidates
                if not self._overlaps_with_existing(group, candidates):
                    candidates.append(group)

        # Add implicit sequences from page groups
        for page_group, group in by_chapter.items():
            procedural = [e for e in group if e.sequence_type == SequenceType.IMPLICIT]
            if len(procedural) >= 3:
                if not self._overlaps_with_existing(procedural, candidates):
                    candidates.append(procedural)

        return candidates

    def _group_consecutive(
        self, elements: list[SequenceElement]
    ) -> list[list[SequenceElement]]:
        """Group elements with consecutive sequence numbers."""
        if not elements:
            return []

        # Sort by sequence number
        sorted_elems = sorted(
            [e for e in elements if e.sequence_number is not None],
            key=lambda x: (x.page_number, x.sequence_number),
        )

        if not sorted_elems:
            return []

        groups = []
        current_group = [sorted_elems[0]]

        for elem in sorted_elems[1:]:
            last = current_group[-1]

            # Check if consecutive
            is_consecutive = (
                elem.sequence_number is not None
                and last.sequence_number is not None
                and elem.sequence_number == last.sequence_number + 1
                and abs(elem.page_number - last.page_number) <= 2
            )

            if is_consecutive:
                current_group.append(elem)
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [elem]

        if len(current_group) >= 2:
            groups.append(current_group)

        return groups

    def _overlaps_with_existing(
        self, group: list[SequenceElement], existing: list[list[SequenceElement]]
    ) -> bool:
        """Check if a group overlaps with existing candidates."""
        group_ids = {e.image_id for e in group}

        for existing_group in existing:
            existing_ids = {e.image_id for e in existing_group}
            overlap = group_ids & existing_ids
            if len(overlap) > len(group) * 0.5:  # >50% overlap
                return True

        return False

    def _validate_sequences(
        self, candidates: list[list[SequenceElement]]
    ) -> list[ProceduralSequence]:
        """Validate and convert candidate groups to sequences."""
        sequences = []

        for i, candidate in enumerate(candidates):
            if len(candidate) < 2:
                continue

            # Determine sequence type from elements
            type_counts: dict[SequenceType, int] = defaultdict(int)
            for elem in candidate:
                type_counts[elem.sequence_type] += 1

            primary_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]

            # Calculate confidence
            confidence = sum(e.confidence for e in candidate) / len(candidate)

            # Generate title from context
            title = self._generate_sequence_title(candidate)

            sequence = ProceduralSequence(
                sequence_id=f"seq_{i:03d}",
                title=title,
                sequence_type=primary_type,
                elements=candidate,
                start_page=min(e.page_number for e in candidate),
                end_page=max(e.page_number for e in candidate),
                confidence=confidence,
            )

            # Extract procedure keywords from all captions
            all_text = " ".join(e.caption or "" for e in candidate)
            keywords = self.keyword_detector.detect(all_text)
            sequence.procedure_keywords = keywords["procedure_keywords"]

            sequences.append(sequence)

        return sequences

    def _generate_sequence_title(self, elements: list[SequenceElement]) -> str:
        """Generate a title for a sequence from its elements."""
        # Look for procedure keywords in captions
        all_text = " ".join(e.caption or "" for e in elements)
        keywords = self.keyword_detector.detect(all_text)

        if keywords["procedure_keywords"]:
            # Use most common procedure keyword
            return f"Procedural Sequence: {keywords['procedure_keywords'][0].title()}"

        # Fall back to generic title
        first_elem = elements[0]
        if first_elem.caption:
            # Extract first few words
            words = first_elem.caption.split()[:5]
            return " ".join(words) + "..."

        return f"Sequence (Page {first_elem.page_number})"

    def _sort_sequence_elements(self, sequence: ProceduralSequence):
        """Sort elements within a sequence."""
        if sequence.sequence_type in (
            SequenceType.NUMBERED_STEPS,
            SequenceType.SUBFIGURES,
            SequenceType.LETTERED_PANELS,
        ):
            # Sort by sequence number
            sequence.elements.sort(
                key=lambda e: (e.sequence_number or 999, e.page_number)
            )
        else:
            # Sort by page and position
            sequence.elements.sort(
                key=lambda e: (e.page_number, e.position[1])  # y-position
            )

        # Update sequence numbers if not present
        for i, elem in enumerate(sequence.elements):
            if elem.sequence_number is None:
                elem.sequence_number = i + 1
                elem.step_label = f"Step {i + 1}"

    def _calculate_sequence_metrics(self, sequence: ProceduralSequence):
        """Calculate quality metrics for a sequence."""
        elements = sequence.elements

        if len(elements) < 2:
            sequence.completeness = 0.0
            return

        # Check for gaps in numbering
        numbers = [e.sequence_number for e in elements if e.sequence_number]

        if not numbers:
            sequence.completeness = 0.5  # Unknown
            return

        min_num = min(numbers)
        max_num = max(numbers)
        expected_count = max_num - min_num + 1
        actual_count = len(set(numbers))

        sequence.completeness = (
            actual_count / expected_count if expected_count > 0 else 0
        )


# =============================================================================
# SEQUENCE VALIDATOR
# =============================================================================


class SequenceValidator:
    """
    Validate procedural sequences for quality and completeness.
    """

    def validate(self, sequence: ProceduralSequence) -> dict[str, Any]:
        """
        Validate a sequence and return quality report.

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        # Check minimum length
        if sequence.length < 2:
            issues.append("Sequence too short (< 2 elements)")

        # Check for gaps
        if sequence.completeness < 0.8:
            warnings.append(
                f"Sequence has gaps (completeness: {sequence.completeness:.0%})"
            )

        # Check for duplicate numbers
        numbers = [e.sequence_number for e in sequence.elements if e.sequence_number]
        if len(numbers) != len(set(numbers)):
            issues.append("Sequence has duplicate step numbers")

        # Check page span (very large spans are suspicious)
        page_span = sequence.end_page - sequence.start_page
        if page_span > 20:
            warnings.append(f"Large page span ({page_span} pages)")

        # Check confidence
        if sequence.confidence < 0.3:
            warnings.append(f"Low confidence ({sequence.confidence:.0%})")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "completeness": sequence.completeness,
            "confidence": sequence.confidence,
        }


# =============================================================================
# SEQUENCE EXPORTER
# =============================================================================


class SequenceExporter:
    """
    Export procedural sequences to various formats.
    """

    def to_markdown(self, sequence: ProceduralSequence) -> str:
        """Export sequence to markdown."""
        lines = [
            f"## {sequence.title}",
            "",
            f"**Type:** {sequence.sequence_type.value}",
            f"**Steps:** {sequence.length}",
            f"**Pages:** {sequence.start_page}-{sequence.end_page}",
            "",
        ]

        if sequence.procedure_keywords:
            lines.append(f"**Keywords:** {', '.join(sequence.procedure_keywords)}")
            lines.append("")

        lines.append("### Steps")
        lines.append("")

        for elem in sequence.elements:
            label = elem.step_label or f"Step {elem.sequence_number}"
            lines.append(f"#### {label}")
            if elem.caption:
                lines.append(f"*{elem.caption}*")
            lines.append(f"- Image: `{elem.image_id}`")
            lines.append(f"- Page: {elem.page_number}")
            lines.append("")

        return "\n".join(lines)

    def to_json(self, sequence: ProceduralSequence) -> dict:
        """Export sequence to JSON-compatible dict."""
        return sequence.to_dict()

    def to_latex_sequence(
        self, sequence: ProceduralSequence, image_path_prefix: str = "figures/"
    ) -> str:
        """Export sequence to LaTeX subfigure format."""
        lines = [
            "\\begin{figure}[p]",
            "    \\centering",
        ]

        for i, elem in enumerate(sequence.elements):
            lines.append("    \\begin{subfigure}[b]{0.45\\textwidth}")
            lines.append("        \\centering")
            lines.append(
                f"        \\includegraphics[width=\\textwidth]{{{image_path_prefix}{elem.image_id}}}"
            )

            caption = elem.step_label or f"Step {i+1}"
            if elem.caption:
                caption += f": {elem.caption[:50]}"

            lines.append(f"        \\caption{{{caption}}}")
            lines.append("    \\end{subfigure}")

            # Add spacing
            if (i + 1) % 2 == 0 and i < len(sequence.elements) - 1:
                lines.append("    \\\\[1ex]")
            elif i < len(sequence.elements) - 1:
                lines.append("    \\hfill")

        # Main caption
        lines.append(f"    \\caption{{{sequence.title}}}")
        lines.append(f"    \\label{{fig:{sequence.sequence_id}}}")
        lines.append("\\end{figure}")

        return "\n".join(lines)
