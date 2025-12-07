"""
Query Analyzer for Study Package System
========================================

Analyzes search queries to extract:
1. Anatomical region (spine, cranial, vascular, etc.)
2. Subregion (lumbar, skull_base, etc.)
3. Knowledge domain (oncology, functional, etc.)
4. Implied knowledge categories

Universal design - works for any neurosurgical topic.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from src.search.study_package.taxonomy import (
    KNOWLEDGE_CATEGORIES,
    NEUROSURGICAL_REGIONS,
    PROCEDURE_TO_REGION,
    REGION_FOUNDATIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysis:
    """Result of query analysis."""

    original_query: str

    # Detected components
    primary_region: Optional[str] = None
    subregion: Optional[str] = None
    domain: Optional[str] = None  # oncology, vascular, functional

    # Detected categories
    detected_categories: set[str] = field(default_factory=set)

    # Confidence metrics
    confidence: float = 0.0
    match_count: int = 0

    @property
    def region_tags(self) -> set[str]:
        """Get all applicable region tags for foundation lookup."""
        tags = set()
        if self.primary_region:
            tags.add(self.primary_region)
        if self.subregion:
            tags.add(self.subregion)
        if self.domain:
            tags.add(self.domain)
        return tags

    @property
    def foundation_keys(self) -> list[str]:
        """Get ordered list of keys for foundation lookup."""
        # More specific first
        keys = []
        if self.subregion:
            keys.append(self.subregion)
        if self.primary_region:
            keys.append(self.primary_region)
        if self.domain:
            keys.append(self.domain)
        return keys

    def __repr__(self):
        return (
            f"QueryAnalysis(region={self.primary_region}, "
            f"subregion={self.subregion}, domain={self.domain}, "
            f"confidence={self.confidence:.2f})"
        )


class QueryAnalyzer:
    """
    Analyzes neurosurgical search queries to extract region and domain.

    Universal design principles:
    1. Pattern-based detection (not hardcoded topic lists)
    2. Hierarchical matching (spine → lumbar → L4-L5)
    3. Procedure-to-region inference
    4. Multi-signal confidence scoring

    Usage:
        analyzer = QueryAnalyzer()
        analysis = analyzer.analyze("lumbar discectomy")
        print(analysis.region_tags)  # {'spine', 'lumbar'}
    """

    def __init__(
        self,
        regions: Optional[dict] = None,
        categories: Optional[dict] = None,
        procedure_map: Optional[dict] = None,
    ):
        """
        Initialize analyzer with taxonomy data.

        Args:
            regions: Regional taxonomy (default: NEUROSURGICAL_REGIONS)
            categories: Knowledge categories (default: KNOWLEDGE_CATEGORIES)
            procedure_map: Procedure-to-region map (default: PROCEDURE_TO_REGION)
        """
        self.regions = regions or NEUROSURGICAL_REGIONS
        self.categories = categories or KNOWLEDGE_CATEGORIES
        self.procedure_map = procedure_map or PROCEDURE_TO_REGION

        # Pre-compile patterns for efficiency
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for region and category detection."""
        # Compile region keyword patterns
        self._region_keywords: dict[str, re.Pattern] = {}
        for region, data in self.regions.items():
            keywords = data.get("keywords", [])
            if keywords:
                # Create pattern that matches any keyword
                pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")"
                self._region_keywords[region] = re.compile(pattern, re.IGNORECASE)

        # Compile subregion patterns
        self._subregion_keywords: dict[str, dict] = {}
        for region, data in self.regions.items():
            for subregion, subdata in data.get("subregions", {}).items():
                keywords = subdata.get("keywords", [])
                if keywords:
                    pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")"
                    self._subregion_keywords[subregion] = {
                        "pattern": re.compile(pattern, re.IGNORECASE),
                        "parent": region,
                    }

        # Compile category patterns
        self._category_patterns: dict[str, re.Pattern] = {}
        for category, data in self.categories.items():
            patterns = data.get("patterns", [])
            if patterns:
                combined = "|".join(patterns)
                self._category_patterns[category] = re.compile(combined, re.IGNORECASE)

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze query to extract region, domain, and categories.

        Args:
            query: User's search query

        Returns:
            QueryAnalysis with detected components
        """
        query_lower = query.lower()

        # Step 1: Detect primary region
        primary_region, region_matches = self._detect_region(query_lower)

        # Step 2: Detect subregion
        subregion = self._detect_subregion(query_lower, primary_region)

        # Step 3: Detect domain (oncology, vascular, functional)
        domain = self._detect_domain(query_lower)

        # Step 4: If no region but have domain, use domain's parent region
        if not primary_region and domain:
            if domain in self.regions:
                primary_region = domain
                domain = None

        # Step 5: Infer region from procedure if still not detected
        if not primary_region:
            primary_region, subregion = self._infer_from_procedure(query_lower)

        # Step 6: Detect knowledge categories
        categories = self._detect_categories(query_lower)

        # Step 7: Calculate confidence
        confidence = self._calculate_confidence(
            primary_region, subregion, domain, categories, region_matches
        )

        analysis = QueryAnalysis(
            original_query=query,
            primary_region=primary_region,
            subregion=subregion,
            domain=domain,
            detected_categories=categories,
            confidence=confidence,
            match_count=region_matches,
        )

        logger.debug("Query analysis: %s", analysis)
        return analysis

    def _detect_region(self, query: str) -> tuple[Optional[str], int]:
        """
        Detect primary anatomical region from query.

        Returns:
            (region_name, match_count)
        """
        best_region = None
        best_count = 0

        for region, pattern in self._region_keywords.items():
            matches = pattern.findall(query)
            if len(matches) > best_count:
                best_region = region
                best_count = len(matches)

        return best_region, best_count

    def _detect_subregion(
        self, query: str, parent_region: Optional[str]
    ) -> Optional[str]:
        """Detect subregion within the primary region."""
        for subregion, data in self._subregion_keywords.items():
            # Only match subregions of the detected parent (or if no parent detected)
            if parent_region and data["parent"] != parent_region:
                continue

            if data["pattern"].search(query):
                return subregion

        return None

    def _detect_domain(self, query: str) -> Optional[str]:
        """Detect cross-cutting domain (oncology, vascular, functional)."""
        # Check for explicit domain indicators
        domain_indicators = {
            "oncology": [
                "tumor",
                "cancer",
                "neoplasm",
                "glioma",
                "meningioma",
                "schwannoma",
                "metastas",
            ],
            "vascular": ["aneurysm", "avm", "hemorrhage", "stroke", "ischemi"],
            "functional": [
                "dbs",
                "stimulat",
                "epilepsy",
                "seizure",
                "movement disorder",
            ],
        }

        for domain, indicators in domain_indicators.items():
            if any(ind in query for ind in indicators):
                return domain

        return None

    def _infer_from_procedure(self, query: str) -> tuple[Optional[str], Optional[str]]:
        """Infer region from procedure keywords."""
        for procedure, region in self.procedure_map.items():
            if procedure in query:
                # Check if this maps to a subregion
                if region in self._subregion_keywords:
                    parent = self._subregion_keywords[region]["parent"]
                    return parent, region
                else:
                    return region, None

        return None, None

    def _detect_categories(self, query: str) -> set[str]:
        """Detect implied knowledge categories from query."""
        categories: set[str] = set()

        for category, pattern in self._category_patterns.items():
            if pattern.search(query):
                categories.add(category)

        # Default: procedure queries imply surgical_technique
        procedure_indicators = [
            "surgery",
            "technique",
            "approach",
            "procedure",
            "ectomy",
            "otomy",
            "plasty",
            "pexy",
        ]
        if any(ind in query for ind in procedure_indicators):
            categories.add("surgical_technique")

        return categories

    def _calculate_confidence(
        self,
        region: Optional[str],
        subregion: Optional[str],
        domain: Optional[str],
        categories: set[str],
        match_count: int,
    ) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.0

        # Region detection is primary signal
        if region:
            score += 0.4
            if match_count > 1:
                score += 0.1  # Multiple keyword matches

        # Subregion adds specificity
        if subregion:
            score += 0.2

        # Domain detection
        if domain:
            score += 0.15

        # Categories
        if categories:
            score += min(0.15, len(categories) * 0.05)

        return min(1.0, score)

    def get_foundation_terms(self, analysis: QueryAnalysis) -> dict[str, list[str]]:
        """
        Get foundational search terms for the detected region.

        Args:
            analysis: QueryAnalysis from analyze()

        Returns:
            Dict mapping category to list of search terms
        """
        foundations: dict[str, list[str]] = {}

        for key in analysis.foundation_keys:
            if key in REGION_FOUNDATIONS:
                region_foundations = REGION_FOUNDATIONS[key]
                for category, terms in region_foundations.items():
                    if category not in foundations:
                        foundations[category] = []
                    foundations[category].extend(terms)

        # Deduplicate while preserving order
        for category in foundations:
            seen: set[str] = set()
            unique: list[str] = []
            for term in foundations[category]:
                if term not in seen:
                    seen.add(term)
                    unique.append(term)
            foundations[category] = unique

        return foundations


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_analyzer: Optional[QueryAnalyzer] = None


def get_analyzer() -> QueryAnalyzer:
    """Get singleton analyzer instance."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = QueryAnalyzer()
    return _default_analyzer


def analyze_query(query: str) -> QueryAnalysis:
    """Convenience function to analyze a query."""
    return get_analyzer().analyze(query)


def get_foundations_for_query(query: str) -> dict[str, list[str]]:
    """Convenience function to get foundational terms for a query."""
    analyzer = get_analyzer()
    analysis = analyzer.analyze(query)
    return analyzer.get_foundation_terms(analysis)
