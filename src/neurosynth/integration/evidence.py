"""Evidence Level Detection for Medical Literature.

Detects evidence levels in medical text based on the Oxford CEBM
(Centre for Evidence-Based Medicine) levels of evidence.

Levels:
1a - Systematic reviews of RCTs
1b - Individual RCTs
1c - "All or none" case series
2a - Systematic reviews of cohort studies
2b - Individual cohort studies / low-quality RCTs
2c - Outcomes research / ecological studies
3a - Systematic reviews of case-control studies
3b - Individual case-control studies
4  - Case series / poor-quality cohort/case-control
5  - Expert opinion

This module helps prioritize high-quality evidence during synthesis
and flag claims that rely on lower-quality evidence.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console

from neurosynth import get_logger

console = Console()
logger = get_logger("integration.evidence")


class EvidenceLevel(str, Enum):
    """Oxford CEBM Evidence Levels."""

    LEVEL_1A = "1a"  # Systematic reviews of RCTs
    LEVEL_1B = "1b"  # Individual RCTs
    LEVEL_1C = "1c"  # All or none case series
    LEVEL_2A = "2a"  # Systematic reviews of cohort studies
    LEVEL_2B = "2b"  # Individual cohort studies
    LEVEL_2C = "2c"  # Outcomes research
    LEVEL_3A = "3a"  # Systematic reviews of case-control
    LEVEL_3B = "3b"  # Individual case-control studies
    LEVEL_4 = "4"  # Case series
    LEVEL_5 = "5"  # Expert opinion
    UNKNOWN = "unknown"

    @property
    def numeric_rank(self) -> int:
        """Get numeric rank (lower = stronger evidence)."""
        ranks = {
            "1a": 1,
            "1b": 2,
            "1c": 3,
            "2a": 4,
            "2b": 5,
            "2c": 6,
            "3a": 7,
            "3b": 8,
            "4": 9,
            "5": 10,
            "unknown": 11,
        }
        return ranks.get(self.value, 11)

    @property
    def description(self) -> str:
        """Get human-readable description."""
        descriptions = {
            "1a": "Systematic review of RCTs",
            "1b": "Individual RCT",
            "1c": "All-or-none case series",
            "2a": "Systematic review of cohort studies",
            "2b": "Individual cohort study",
            "2c": "Outcomes research",
            "3a": "Systematic review of case-control studies",
            "3b": "Individual case-control study",
            "4": "Case series",
            "5": "Expert opinion",
            "unknown": "Unknown evidence level",
        }
        return descriptions.get(self.value, "Unknown")

    @property
    def is_high_quality(self) -> bool:
        """Check if this is high-quality evidence (Level 1-2)."""
        return self.numeric_rank <= 6


@dataclass
class EvidenceDetection:
    """Result of evidence level detection."""

    level: EvidenceLevel
    confidence: float  # 0.0 to 1.0
    indicators: list[str]  # Phrases that triggered detection
    text_excerpt: str | None = None


# Detection patterns for evidence levels
EVIDENCE_PATTERNS = {
    EvidenceLevel.LEVEL_1A: [
        r"\b(systematic\s+review|meta-analysis)\s+(of\s+)?(randomized|randomised)",
        r"\bcochrane\s+(review|database|systematic)",
        r"\bprisma\b",
        r"\bforest\s+plot\b",
        r"\bpooled\s+(analysis|data|results)",
        r"\bheterogeneity\s+I\s*[²2]",
    ],
    EvidenceLevel.LEVEL_1B: [
        r"\b(randomized|randomised)\s+controlled\s+trial\b",
        r"\bRCT\b",
        r"\bdouble[- ]blind(ed)?\b",
        r"\bplacebo[- ]controlled\b",
        r"\brandomization\b",
        r"\bintention[- ]to[- ]treat\b",
        r"\bpower\s+calculation\b",
        r"\bprimary\s+endpoint\b",
    ],
    EvidenceLevel.LEVEL_1C: [
        r"\ball\s+or\s+none\b",
        r"\b100%\s+(mortality|survival|cure)\b",
        r"\buniversal\s+(outcome|response)\b",
    ],
    EvidenceLevel.LEVEL_2A: [
        r"\bsystematic\s+review\s+(of\s+)?cohort",
        r"\bmeta-analysis\s+(of\s+)?cohort",
        r"\bpooled\s+cohort\b",
    ],
    EvidenceLevel.LEVEL_2B: [
        r"\bprospective\s+cohort\b",
        r"\bretrospective\s+cohort\b",
        r"\blongitudinal\s+study\b",
        r"\bfollow[- ]up\s+study\b",
        r"\bcohort\s+study\b",
        r"\bincidence\s+rate\b",
        r"\bhazard\s+ratio\b",
        r"\bsurvival\s+analysis\b",
        r"\bkaplan[- ]meier\b",
    ],
    EvidenceLevel.LEVEL_2C: [
        r"\boutcomes\s+research\b",
        r"\becological\s+study\b",
        r"\bpopulation[- ]based\b",
        r"\bregistry\s+(study|data|analysis)\b",
        r"\bdatabase\s+study\b",
    ],
    EvidenceLevel.LEVEL_3A: [
        r"\bsystematic\s+review\s+(of\s+)?case[- ]control",
        r"\bmeta-analysis\s+(of\s+)?case[- ]control",
    ],
    EvidenceLevel.LEVEL_3B: [
        r"\bcase[- ]control\s+study\b",
        r"\bodds\s+ratio\b",
        r"\bmatched\s+(controls?|cases?)\b",
        r"\bretrospective\s+analysis\b",
    ],
    EvidenceLevel.LEVEL_4: [
        r"\bcase\s+series\b",
        r"\bcase\s+report\b",
        r"\bour\s+(experience|series)\b",
        r"\bconsecutive\s+patients?\b",
        r"\bdescriptive\s+study\b",
        r"\bsingle[- ](center|centre|institution)\b",
    ],
    EvidenceLevel.LEVEL_5: [
        r"\bexpert\s+(opinion|consensus|panel)\b",
        r"\bconsensus\s+(statement|guidelines?)\b",
        r"\bin\s+our\s+(opinion|experience)\b",
        r"\bwe\s+(believe|recommend|suggest)\b",
        r"\bclinical\s+(judgment|judgement|experience)\b",
        r"\bauthoritative\s+sources?\b",
    ],
}


class EvidenceDetector:
    """Detect evidence levels in medical text."""

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        context_window: int = 200,
    ):
        """Initialize the evidence detector.

        Args:
            confidence_threshold: Minimum confidence to report detection
            context_window: Characters of context to include in excerpts
        """
        self.confidence_threshold = confidence_threshold
        self.context_window = context_window

        # Compile regex patterns
        self.patterns = {
            level: [re.compile(p, re.IGNORECASE) for p in patterns]
            for level, patterns in EVIDENCE_PATTERNS.items()
        }

    def detect(self, text: str) -> EvidenceDetection:
        """Detect the primary evidence level in text.

        Args:
            text: Text to analyze

        Returns:
            EvidenceDetection with detected level and confidence
        """
        if not text:
            return EvidenceDetection(
                level=EvidenceLevel.UNKNOWN,
                confidence=0.0,
                indicators=[],
            )

        text_lower = text.lower()
        detections = []

        # Check each evidence level
        for level, patterns in self.patterns.items():
            matches = []
            for pattern in patterns:
                for match in pattern.finditer(text_lower):
                    matches.append(match.group())

            if matches:
                # Calculate confidence based on number and variety of matches
                unique_patterns = len(set(matches))
                total_matches = len(matches)
                confidence = min(1.0, (unique_patterns * 0.3) + (total_matches * 0.1))

                detections.append((level, confidence, matches))

        if not detections:
            return EvidenceDetection(
                level=EvidenceLevel.UNKNOWN,
                confidence=0.0,
                indicators=[],
            )

        # Return highest-confidence detection that meets threshold
        # Prefer higher evidence levels in case of ties
        detections.sort(key=lambda x: (-x[1], x[0].numeric_rank))

        best_level, best_confidence, best_matches = detections[0]

        if best_confidence < self.confidence_threshold:
            return EvidenceDetection(
                level=EvidenceLevel.UNKNOWN,
                confidence=best_confidence,
                indicators=best_matches,
            )

        return EvidenceDetection(
            level=best_level,
            confidence=best_confidence,
            indicators=list(set(best_matches))[:5],  # Top 5 unique indicators
        )

    def detect_all(self, text: str) -> list[EvidenceDetection]:
        """Detect all evidence levels present in text.

        Args:
            text: Text to analyze

        Returns:
            List of all EvidenceDetections found
        """
        if not text:
            return []

        text_lower = text.lower()
        detections = []

        for level, patterns in self.patterns.items():
            matches = []
            for pattern in patterns:
                for match in pattern.finditer(text_lower):
                    matches.append(match.group())

            if matches:
                unique_patterns = len(set(matches))
                total_matches = len(matches)
                confidence = min(1.0, (unique_patterns * 0.3) + (total_matches * 0.1))

                if confidence >= self.confidence_threshold:
                    detections.append(
                        EvidenceDetection(
                            level=level,
                            confidence=confidence,
                            indicators=list(set(matches))[:5],
                        )
                    )

        return sorted(detections, key=lambda x: x.level.numeric_rank)

    def annotate_text(self, text: str) -> str:
        """Annotate text with evidence level markers.

        Args:
            text: Text to annotate

        Returns:
            Text with [Level X] annotations
        """
        text_lower = text.lower()
        annotations = []

        for level, patterns in self.patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text_lower):
                    annotations.append((match.start(), match.end(), level))

        # Sort by position and annotate (reverse to preserve positions)
        annotations.sort(key=lambda x: x[0], reverse=True)

        annotated = text
        for _start, end, level in annotations:
            marker = f" [Evidence: {level.value}]"
            annotated = annotated[:end] + marker + annotated[end:]

        return annotated

    def get_evidence_summary(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize evidence levels across multiple chunks.

        Args:
            chunks: List of chunk dicts with 'content' field

        Returns:
            Summary dict with counts and distributions
        """
        level_counts: dict[EvidenceLevel, int] = dict.fromkeys(EvidenceLevel, 0)
        high_quality_chunks = []
        low_quality_chunks = []

        for chunk in chunks:
            content = chunk.get("content", "")
            detection = self.detect(content)

            level_counts[detection.level] += 1

            if detection.level.is_high_quality:
                high_quality_chunks.append(chunk)
            elif detection.level != EvidenceLevel.UNKNOWN:
                low_quality_chunks.append(chunk)

        total = len(chunks)
        high_quality_count = sum(
            count
            for level, count in level_counts.items()
            if level != EvidenceLevel.UNKNOWN and level.is_high_quality
        )

        return {
            "total_chunks": total,
            "level_counts": {
                level.value: count for level, count in level_counts.items()
            },
            "high_quality_percentage": (
                (high_quality_count / total * 100) if total > 0 else 0
            ),
            "strongest_evidence": min(
                (
                    level
                    for level, count in level_counts.items()
                    if count > 0 and level != EvidenceLevel.UNKNOWN
                ),
                key=lambda x: x.numeric_rank,
                default=EvidenceLevel.UNKNOWN,
            ).value,
            "high_quality_chunk_indices": [
                i for i, c in enumerate(chunks) if c in high_quality_chunks
            ],
        }


def detect_evidence_level(text: str) -> EvidenceDetection:
    """Convenience function to detect evidence level in text.

    Args:
        text: Text to analyze

    Returns:
        EvidenceDetection
    """
    detector = EvidenceDetector()
    return detector.detect(text)


def get_evidence_summary(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Convenience function to get evidence summary for chunks.

    Args:
        chunks: List of content chunks

    Returns:
        Evidence summary dict
    """
    detector = EvidenceDetector()
    return detector.get_evidence_summary(chunks)
