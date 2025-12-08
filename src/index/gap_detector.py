"""Coverage gap detection for search results.

This module detects gaps in library coverage and generates warnings
to alert users when search results may be incomplete or low-quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

# Import QueryType at runtime since we use it in comparisons
# Import PrecisionResult only for type checking to avoid circular import
if TYPE_CHECKING:
    from .precision_search import PrecisionResult

# This is safe because precision_search doesn't import gap_detector during QueryType definition
from .precision_search import QueryType


class GapSeverity(Enum):
    """Severity levels for coverage gaps."""

    CRITICAL = "critical"  # Missing essential sources (safety-critical queries)
    HIGH = "high"  # Missing important coverage
    MEDIUM = "medium"  # Minor gaps
    LOW = "low"  # Suggestions/tips


class GapType(Enum):
    """Types of coverage gaps."""

    AUTHORITY = "authority"  # Low authority scores
    GUIDELINE = "guideline"  # No clinical guidelines
    DIVERSITY = "diversity"  # Low subspecialty/source diversity
    CATEGORY = "category"  # Missing knowledge categories
    FOUNDATION = "foundation"  # Missing anatomy/fundamentals
    EXAM_ADEQUACY = "exam_adequacy"  # High-yield topic under-indexed
    SOURCE_COUNT = "source_count"  # Too few total sources


@dataclass
class GapWarning:
    """Represents a detected coverage gap."""

    gap_type: GapType
    severity: GapSeverity
    message: str  # User-facing warning text
    suggestion: str | None = None  # Actionable suggestion
    metrics: dict | None = None  # Supporting data


class GapDetector:
    """Detects coverage gaps in search results."""

    # Configuration thresholds
    MIN_AUTHORITY_THRESHOLD = 85  # MEDIUM warning if avg < 85
    MIN_GUIDELINE_AUTHORITY = 100  # HIGH warning if no guideline for safety queries
    CRITICAL_AUTHORITY_THRESHOLD = 90  # CRITICAL if safety query and max < 90
    MIN_SUBSPECIALTY_DIVERSITY = 2  # HIGH warning if only 1 subspecialty
    MIN_SOURCE_COUNT = 3  # General minimum
    MIN_EXAM_SOURCES = 3  # For high-yield topics (exam_freq ≥7)
    HIGH_YIELD_THRESHOLD = 7  # Exam frequency requiring extra scrutiny

    def __init__(self, database=None):
        """Initialize gap detector.

        Args:
            database: Optional database connection for additional lookups
        """
        self.database = database

    def detect_gaps(
        self,
        query: str,
        query_type: QueryType,
        results: list[PrecisionResult],
        top_k: int = 10,
    ) -> list[GapWarning]:
        """Detect coverage gaps in search results.

        Args:
            query: Original search query
            query_type: Classified query intent
            results: Search results to analyze
            top_k: Number of top results to analyze

        Returns:
            List of GapWarning objects ordered by severity (CRITICAL first)
        """
        warnings = []

        # Handle empty results
        if not results:
            warnings.append(
                GapWarning(
                    gap_type=GapType.SOURCE_COUNT,
                    severity=GapSeverity.CRITICAL,
                    message="⚠️ No results found for this query",
                    suggestion="Try broader search terms or different phrasing",
                )
            )
            return warnings

        # Analyze top results only
        analyzed_results = results[:top_k]

        # Run all gap checks
        warnings.extend(self._check_authority_coverage(analyzed_results, query_type))
        warnings.extend(self._check_source_diversity(analyzed_results))
        warnings.extend(self._check_category_coverage(analyzed_results, query_type))
        warnings.extend(
            self._check_foundation_coverage(analyzed_results, query, query_type)
        )
        warnings.extend(self._check_exam_adequacy(analyzed_results))

        # Sort by severity (CRITICAL → HIGH → MEDIUM → LOW)
        severity_order = {
            GapSeverity.CRITICAL: 0,
            GapSeverity.HIGH: 1,
            GapSeverity.MEDIUM: 2,
            GapSeverity.LOW: 3,
        }
        warnings.sort(key=lambda w: severity_order[w.severity])

        return warnings

    def _check_authority_coverage(
        self, results: list[PrecisionResult], query_type: QueryType
    ) -> list[GapWarning]:
        """Check for low authority scores or missing guidelines.

        Args:
            results: Search results to analyze
            query_type: Query type to determine severity

        Returns:
            List of authority-related gap warnings
        """
        warnings = []

        authority_scores = [r.authority_score for r in results]
        max_authority = max(authority_scores)
        avg_authority = sum(authority_scores) / len(authority_scores)

        # Check for guidelines (authority=100)
        has_guideline = any(
            r.authority_score >= self.MIN_GUIDELINE_AUTHORITY for r in results
        )

        # CRITICAL: No high-authority sources for safety-critical queries
        if (
            query_type == QueryType.CONTRAINDICATION
            and max_authority < self.CRITICAL_AUTHORITY_THRESHOLD
        ):
            warnings.append(
                GapWarning(
                    gap_type=GapType.AUTHORITY,
                    severity=GapSeverity.CRITICAL,
                    message=f"⚠️ Safety-critical query with low authority (max: {max_authority}/100)",
                    suggestion="Verify information with clinical guidelines or primary sources",
                    metrics={
                        "max_authority": max_authority,
                        "avg_authority": avg_authority,
                    },
                )
            )

        # HIGH: No guidelines for contraindication queries
        if query_type == QueryType.CONTRAINDICATION and not has_guideline:
            warnings.append(
                GapWarning(
                    gap_type=GapType.GUIDELINE,
                    severity=GapSeverity.HIGH,
                    message="⚠️ No clinical guidelines found for this safety-critical query",
                    suggestion="Search for '[condition] guidelines' or '[procedure] contraindications guideline'",
                    metrics={"has_guideline": False},
                )
            )

        # MEDIUM: Low average authority for clinical queries
        if avg_authority < self.MIN_AUTHORITY_THRESHOLD and query_type in [
            QueryType.FACTUAL,
            QueryType.PROCEDURAL,
        ]:
            warnings.append(
                GapWarning(
                    gap_type=GapType.AUTHORITY,
                    severity=GapSeverity.MEDIUM,
                    message=f"ℹ️ Lower authority sources (avg: {avg_authority:.0f}/100) - verify information",
                    suggestion="Consider searching for textbook chapters or specialized references",
                    metrics={"avg_authority": avg_authority},
                )
            )

        return warnings

    def _check_source_diversity(
        self, results: list[PrecisionResult]
    ) -> list[GapWarning]:
        """Check for low subspecialty or collection diversity.

        Args:
            results: Search results to analyze

        Returns:
            List of diversity-related gap warnings
        """
        warnings = []

        # Subspecialty diversity
        subspecialties = [
            r.chunk.metadata.get("subspecialty", "General") for r in results
        ]
        unique_subspecialties = set(subspecialties)

        # Collection type diversity
        collections = [r.chunk.metadata.get("collection", "Unknown") for r in results]
        unique_collections = set(collections)

        # HIGH: All results from single subspecialty (low diversity)
        if len(unique_subspecialties) == 1 and len(results) >= 5:
            subspecialty = list(unique_subspecialties)[0]
            warnings.append(
                GapWarning(
                    gap_type=GapType.DIVERSITY,
                    severity=GapSeverity.HIGH,
                    message=f"ℹ️ Low diversity - all results from {subspecialty} subspecialty",
                    suggestion="Consider cross-subspecialty perspectives or broader search terms",
                    metrics={
                        "subspecialty_count": 1,
                        "dominant_subspecialty": subspecialty,
                    },
                )
            )

        # MEDIUM: Missing textbook coverage
        if "Textbooks" not in collections and len(results) >= 10:
            warnings.append(
                GapWarning(
                    gap_type=GapType.DIVERSITY,
                    severity=GapSeverity.MEDIUM,
                    message="ℹ️ No comprehensive textbook coverage found",
                    suggestion="Search for '[topic] Youmans' or '[topic] textbook'",
                    metrics={"missing_collection": "Textbooks"},
                )
            )

        return warnings

    def _check_category_coverage(
        self, results: list[PrecisionResult], query_type: QueryType
    ) -> list[GapWarning]:
        """Check for missing knowledge categories based on query type.

        Args:
            results: Search results to analyze
            query_type: Query type to determine required categories

        Returns:
            List of category-related gap warnings
        """
        warnings = []

        # Extract content snippets for keyword analysis
        all_content = " ".join([r.chunk.content.lower() for r in results[:10]])

        # Required categories per query type
        if query_type == QueryType.PROCEDURAL:
            # Technique queries should have anatomy and complications
            has_anatomy = any(
                word in all_content for word in ["anatomy", "anatomical", "landmark"]
            )
            has_complications = any(
                word in all_content for word in ["complication", "risk", "adverse"]
            )

            if not has_anatomy:
                warnings.append(
                    GapWarning(
                        gap_type=GapType.FOUNDATION,
                        severity=GapSeverity.MEDIUM,
                        message="💡 No anatomical context found in results",
                        suggestion="Search 'anatomy of [region]' for foundational knowledge",
                        metrics={"has_anatomy": False},
                    )
                )

            if not has_complications:
                warnings.append(
                    GapWarning(
                        gap_type=GapType.CATEGORY,
                        severity=GapSeverity.LOW,
                        message="ℹ️ No complications/risks discussed in top results",
                        suggestion="Search '[procedure] complications' for safety information",
                        metrics={"has_complications": False},
                    )
                )

        elif query_type == QueryType.FACTUAL:
            # Factual queries should have pathophysiology or clinical presentation
            has_pathophys = any(
                word in all_content
                for word in ["pathophysiology", "mechanism", "etiology"]
            )
            has_clinical = any(
                word in all_content for word in ["presentation", "symptom", "clinical"]
            )

            if not has_pathophys and not has_clinical:
                warnings.append(
                    GapWarning(
                        gap_type=GapType.CATEGORY,
                        severity=GapSeverity.LOW,
                        message="💡 Limited clinical or pathophysiological context",
                        suggestion="Search '[condition] pathophysiology' or '[condition] presentation'",
                        metrics={"has_pathophys": False, "has_clinical": False},
                    )
                )

        return warnings

    def _check_foundation_coverage(
        self, results: list[PrecisionResult], query: str, query_type: QueryType
    ) -> list[GapWarning]:
        """Check for missing foundational knowledge (anatomy, biomechanics, etc.).

        Args:
            results: Search results to analyze
            query: Original search query
            query_type: Query type

        Returns:
            List of foundation-related gap warnings
        """
        warnings = []

        # Only for technique/procedural queries
        if query_type != QueryType.PROCEDURAL:
            return warnings

        # Extract all content
        all_content = " ".join([r.chunk.content.lower() for r in results[:15]])

        # Foundational keywords
        foundation_checks = {
            "anatomy": ["anatomy", "anatomical", "landmark", "structure"],
            "approach": ["approach", "exposure", "positioning", "access"],
            "technique": ["technique", "step", "procedure", "method"],
        }

        missing_foundations = []
        for foundation, keywords in foundation_checks.items():
            if not any(kw in all_content for kw in keywords):
                missing_foundations.append(foundation)

        # Warn if missing multiple foundations
        if len(missing_foundations) >= 2:
            warnings.append(
                GapWarning(
                    gap_type=GapType.FOUNDATION,
                    severity=GapSeverity.MEDIUM,
                    message=f"ℹ️ Limited foundational coverage (missing: {', '.join(missing_foundations)})",
                    suggestion="Search for comprehensive surgical technique chapters or operative atlases",
                    metrics={"missing_foundations": missing_foundations},
                )
            )

        return warnings

    def _check_exam_adequacy(self, results: list[PrecisionResult]) -> list[GapWarning]:
        """Check if high-yield topics have adequate coverage.

        Args:
            results: Search results to analyze

        Returns:
            List of exam adequacy-related gap warnings
        """
        warnings = []

        # Extract exam frequencies
        exam_frequencies = [r.exam_frequency for r in results if r.exam_frequency > 0]

        if not exam_frequencies:
            return warnings  # No exam tracking data

        max_exam_freq = max(exam_frequencies)

        # HIGH: High-yield topic (≥7) with few sources or low authority
        if max_exam_freq >= self.HIGH_YIELD_THRESHOLD:
            high_yield_sources = [
                r for r in results if r.exam_frequency >= self.HIGH_YIELD_THRESHOLD
            ]
            max_authority = max(r.authority_score for r in high_yield_sources)

            if len(high_yield_sources) < self.MIN_EXAM_SOURCES:
                warnings.append(
                    GapWarning(
                        gap_type=GapType.EXAM_ADEQUACY,
                        severity=GapSeverity.HIGH,
                        message=f"⚠️ High-yield topic (exam freq: {max_exam_freq}) under-indexed ({len(high_yield_sources)} sources)",
                        suggestion="Enable Exam Mode or search for board review materials",
                        metrics={
                            "exam_frequency": max_exam_freq,
                            "source_count": len(high_yield_sources),
                        },
                    )
                )

            if max_authority < 90:
                warnings.append(
                    GapWarning(
                        gap_type=GapType.EXAM_ADEQUACY,
                        severity=GapSeverity.MEDIUM,
                        message=f"ℹ️ High-yield topic lacks high-authority sources (max: {max_authority})",
                        suggestion="Search for specialized texts or clinical guidelines on this topic",
                        metrics={
                            "exam_frequency": max_exam_freq,
                            "max_authority": max_authority,
                        },
                    )
                )

        return warnings
