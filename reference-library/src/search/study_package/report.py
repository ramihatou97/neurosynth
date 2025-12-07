"""
Study Mode Report - Enhanced Implementation with Missing Topic Tracking
========================================================================

Addresses the "silent fail" problem when suggested topics don't match
library contents. Provides transparency about what was found vs. missing.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class TopicSource(Enum):
    """Source of the suggested topics."""

    TAXONOMY = auto()  # From predefined taxonomy (fast, reliable)
    AI = auto()  # From AI/LLM generation (dynamic, may fail)
    HYBRID = auto()  # Combination of both


@dataclass
class StudyModeReport:
    """
    Tracks what happened during Study Mode enhancement.

    Provides transparency about:
    - What topics were suggested (from taxonomy or AI)
    - Which topics were found in the library
    - Which topics are missing (library gaps)
    - Overall success rate

    Usage:
        report = StudyModeReport(query="lumbar discectomy")
        report.ai_suggested_topics = ["spinal anatomy", "biomechanics", "disc pathology"]
        report.matched_topics = {"spinal anatomy": "chapter_123"}
        report.missing_topics = ["biomechanics", "disc pathology"]

        print(report.success_rate)  # 0.33
        print(report.to_ui_summary())  # Human-readable summary
    """

    query: str
    topic_source: TopicSource = TopicSource.TAXONOMY

    # What was suggested
    ai_suggested_topics: list[str] = field(default_factory=list)

    # What was found - maps topic to chapter/result identifier
    matched_topics: dict[str, str] = field(default_factory=dict)

    # What's missing from library
    missing_topics: list[str] = field(default_factory=list)

    # Error tracking
    error: Optional[str] = None

    # Analysis metadata
    detected_region: Optional[str] = None
    detected_subregion: Optional[str] = None
    confidence: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate what percentage of suggested topics were found."""
        if not self.ai_suggested_topics:
            return 0.0
        return len(self.matched_topics) / len(self.ai_suggested_topics)

    @property
    def has_gaps(self) -> bool:
        """Check if there are any library gaps (missing topics)."""
        return len(self.missing_topics) > 0

    @property
    def has_error(self) -> bool:
        """Check if an error occurred during study mode."""
        return self.error is not None

    @property
    def topics_found_count(self) -> int:
        """Number of topics found in library."""
        return len(self.matched_topics)

    @property
    def topics_missing_count(self) -> int:
        """Number of topics NOT found in library."""
        return len(self.missing_topics)

    def to_ui_summary(self, detail_level: str = "standard") -> str:
        """
        Format for UI display.

        Args:
            detail_level: "minimal", "standard", or "verbose"

        Returns:
            Human-readable summary string
        """
        if detail_level == "minimal":
            if self.has_error:
                return f"⚠️ Study Mode: Error - {self.error}"
            if not self.ai_suggested_topics:
                return "📚 Study Mode: No foundational topics identified"
            return f"📚 Study Mode: {self.topics_found_count}/{len(self.ai_suggested_topics)} topics found"

        elif detail_level == "standard":
            lines = []

            # Header
            if self.has_error:
                lines.append(f"⚠️ Study Mode Error: {self.error}")
            elif not self.ai_suggested_topics:
                lines.append("📚 Study Mode: No foundational topics for this query")
            else:
                rate_pct = int(self.success_rate * 100)
                lines.append(
                    f"📚 Study Mode: {self.topics_found_count} of {len(self.ai_suggested_topics)} foundational topics ({rate_pct}%)"
                )

            # Region info
            if self.detected_region:
                region_str = self.detected_region
                if self.detected_subregion:
                    region_str = f"{self.detected_subregion} ({self.detected_region})"
                lines.append(f"   Region: {region_str}")

            # Missing topics (if any)
            if self.missing_topics and len(self.missing_topics) <= 3:
                lines.append(f"   Missing: {', '.join(self.missing_topics)}")
            elif self.missing_topics:
                lines.append(
                    f"   Missing: {len(self.missing_topics)} topics not in library"
                )

            return "\n".join(lines)

        else:  # verbose
            lines = [
                "=" * 50,
                "STUDY MODE REPORT",
                "=" * 50,
                f"Query: {self.query}",
                f"Source: {self.topic_source.name}",
                f"Region: {self.detected_region or 'Not detected'}",
                f"Subregion: {self.detected_subregion or 'Not detected'}",
                f"Confidence: {self.confidence:.2f}",
                "",
                f"Suggested Topics ({len(self.ai_suggested_topics)}):",
            ]

            for topic in self.ai_suggested_topics:
                if topic in self.matched_topics:
                    lines.append(f"  ✅ {topic} → {self.matched_topics[topic]}")
                else:
                    lines.append(f"  ❌ {topic} (not found)")

            lines.append("")
            lines.append(f"Success Rate: {int(self.success_rate * 100)}%")

            if self.error:
                lines.append(f"Error: {self.error}")

            lines.append("=" * 50)
            return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "topic_source": self.topic_source.name,
            "suggested_topics": self.ai_suggested_topics,
            "matched_topics": self.matched_topics,
            "missing_topics": self.missing_topics,
            "success_rate": self.success_rate,
            "detected_region": self.detected_region,
            "detected_subregion": self.detected_subregion,
            "confidence": self.confidence,
            "error": self.error,
        }
