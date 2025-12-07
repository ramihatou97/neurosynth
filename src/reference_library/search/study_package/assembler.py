"""
Study Package Assembler
=======================

Assembles comprehensive search results for BROAD mode by combining:
1. Direct title matches (existing behavior)
2. Foundational chapters for detected region
3. Categorized and prioritized results

This is the main integration point for enhancing BROAD mode.
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from reference_library.search.study_package.analyzer import QueryAnalyzer, QueryAnalysis, get_analyzer
from reference_library.search.study_package.taxonomy import KNOWLEDGE_CATEGORIES
from reference_library.search.study_package.report import StudyModeReport, TopicSource
from reference_library.search.result_model import ChapterResult, MatchType

if TYPE_CHECKING:
    from reference_library.search.pdf_searcher import PDFSearcher

logger = logging.getLogger(__name__)


@dataclass
class StudyPackageResult:
    """A result in the study package with category metadata."""
    title: str
    source: str
    page_number: int
    relevance_score: float
    category: str  # anatomy, biomechanics, surgical_technique, etc.
    match_type: MatchType
    region_match: bool = False

    # Priority for sorting (lower = higher priority)
    priority: int = 50

    # Original result data (ChapterResult or Dict)
    original_result: Optional[ChapterResult] = None
    original_dict: Dict = field(default_factory=dict)

    def to_chapter_result(self) -> Optional[ChapterResult]:
        """Convert to ChapterResult if possible."""
        if self.original_result:
            return self.original_result
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for compatibility."""
        result = {
            "title": self.title,
            "source": self.source,
            "page_number": self.page_number,
            "relevance_score": self.relevance_score,
            "category": self.category,
            "match_type": self.match_type.name,
            "region_match": self.region_match,
            "priority": self.priority,
        }
        result.update(self.original_dict)
        return result


@dataclass
class StudyPackage:
    """Complete study package for a query."""
    query: str
    analysis: QueryAnalysis
    report: StudyModeReport

    # Categorized results
    direct_results: List[StudyPackageResult] = field(default_factory=list)
    foundational_results: List[StudyPackageResult] = field(default_factory=list)
    semantic_results: List[StudyPackageResult] = field(default_factory=list)

    @property
    def all_results(self) -> List[StudyPackageResult]:
        """Get all results in priority order."""
        all_r = self.direct_results + self.foundational_results + self.semantic_results
        # Sort by priority (lower first), then by relevance (higher first)
        return sorted(all_r, key=lambda x: (x.priority, -x.relevance_score))

    @property
    def total_count(self) -> int:
        return len(self.direct_results) + len(self.foundational_results) + len(self.semantic_results)

    def get_by_category(self, category: str) -> List[StudyPackageResult]:
        """Get results filtered by knowledge category."""
        return [r for r in self.all_results if r.category == category]

    def to_chapter_results(self, max_results: int = 100) -> List[ChapterResult]:
        """Convert to list of ChapterResult objects."""
        results = []
        for spr in self.all_results[:max_results]:
            if spr.original_result:
                results.append(spr.original_result)
        return results

    def to_result_list(self, max_results: int = 100) -> List[Dict]:
        """Convert to list of result dictionaries."""
        return [r.to_dict() for r in self.all_results[:max_results]]


class StudyPackageAssembler:
    """
    Assembles comprehensive study packages for BROAD mode.

    Algorithm:
    1. Run standard search (title matching + semantic)
    2. Analyze query to detect region/domain
    3. Search for foundational chapters using region-specific terms
    4. Categorize and rank all results
    5. Return unified study package with report

    Usage:
        assembler = StudyPackageAssembler(searcher)
        package = assembler.assemble("lumbar discectomy", direct_results)
        results = package.to_chapter_results()
        print(package.report.to_ui_summary())
    """

    def __init__(
        self,
        searcher: Optional['PDFSearcher'] = None,
        analyzer: Optional[QueryAnalyzer] = None,
        categories: Optional[Dict] = None,
    ):
        """
        Initialize assembler.

        Args:
            searcher: PDFSearcher instance for running foundation searches
            analyzer: QueryAnalyzer instance (default: singleton)
            categories: Knowledge categories (default: KNOWLEDGE_CATEGORIES)
        """
        self.searcher = searcher
        self.analyzer = analyzer or get_analyzer()
        self.categories = categories or KNOWLEDGE_CATEGORIES

    def assemble(
        self,
        query: str,
        direct_results: List[ChapterResult],
        semantic_results: Optional[List[ChapterResult]] = None,
        max_foundational: int = 15,
        foundational_searches_per_category: int = 2,
    ) -> StudyPackage:
        """
        Assemble complete study package.

        Args:
            query: Original search query
            direct_results: ChapterResults from title/keyword matching
            semantic_results: ChapterResults from semantic search (optional)
            max_foundational: Maximum foundational chapters to add
            foundational_searches_per_category: Max searches per foundation category

        Returns:
            StudyPackage with categorized results and report
        """
        # Analyze query
        analysis = self.analyzer.analyze(query)
        logger.info(
            "Study package: query='%s' -> region=%s, subregion=%s, confidence=%.2f",
            query, analysis.primary_region, analysis.subregion, analysis.confidence
        )

        # Initialize report
        report = StudyModeReport(
            query=query,
            topic_source=TopicSource.TAXONOMY,
            detected_region=analysis.primary_region,
            detected_subregion=analysis.subregion,
            confidence=analysis.confidence,
        )

        # Create package
        package = StudyPackage(query=query, analysis=analysis, report=report)

        # Track seen titles to avoid duplicates
        seen_titles: Set[str] = set()

        # Process direct results first (highest priority)
        for result in direct_results:
            processed = self._process_chapter_result(result, analysis, MatchType.DEDICATED_CHAPTER)
            if processed and processed.title.lower() not in seen_titles:
                seen_titles.add(processed.title.lower())
                package.direct_results.append(processed)

        # Add foundational chapters if confidence is sufficient
        if analysis.confidence >= 0.3 and analysis.region_tags:
            foundation_terms = self.analyzer.get_foundation_terms(analysis)

            # Track suggested topics for report
            for category, terms in foundation_terms.items():
                report.ai_suggested_topics.extend(terms)

            foundational = self._search_foundations(
                foundation_terms,
                seen_titles,
                max_foundational,
                foundational_searches_per_category,
                report,
            )
            # _search_foundations already handles deduplication via seen_titles
            package.foundational_results.extend(foundational)

        # Process semantic results (excluding duplicates)
        if semantic_results:
            for result in semantic_results:
                processed = self._process_chapter_result(result, analysis, MatchType.SEMANTIC)
                if processed and processed.title.lower() not in seen_titles:
                    seen_titles.add(processed.title.lower())
                    package.semantic_results.append(processed)

        # Sort each category
        package.direct_results.sort(key=lambda x: -x.relevance_score)
        package.foundational_results.sort(key=lambda x: (x.priority, -x.relevance_score))
        package.semantic_results.sort(key=lambda x: -x.relevance_score)

        logger.info(
            "Study package assembled: direct=%d, foundational=%d, semantic=%d, gaps=%d",
            len(package.direct_results),
            len(package.foundational_results),
            len(package.semantic_results),
            len(report.missing_topics),
        )

        return package

    def _process_chapter_result(
        self,
        result: ChapterResult,
        analysis: QueryAnalysis,
        default_match_type: MatchType,
    ) -> Optional[StudyPackageResult]:
        """Process a ChapterResult into StudyPackageResult."""
        title = result.chapter_title
        if not title:
            return None

        # Detect category from title
        category = self._detect_category(title)

        # Use existing match type or default
        match_type = result.match_type if result.match_type else default_match_type

        # Check region match
        region_match = self._check_region_match(title, analysis)

        # Determine priority
        priority = self._get_priority(category, match_type)

        return StudyPackageResult(
            title=title,
            source=result.book_title,
            page_number=result.matched_pages[0] if result.matched_pages else 0,
            relevance_score=result.relevance_score,
            category=category,
            match_type=match_type,
            region_match=region_match,
            priority=priority,
            original_result=result,
        )

    def _detect_category(self, title: str) -> str:
        """Detect knowledge category from title."""
        title_lower = title.lower()

        for category, data in self.categories.items():
            patterns = data.get("patterns", [])
            for pattern in patterns:
                if re.search(pattern, title_lower, re.IGNORECASE):
                    return category

        return "general"

    def _check_region_match(self, title: str, analysis: QueryAnalysis) -> bool:
        """Check if result matches detected region."""
        if not analysis.region_tags:
            return False

        title_lower = title.lower()

        # Check for region keywords in title
        for tag in analysis.region_tags:
            if tag in title_lower:
                return True

            # Check region data for keywords
            if tag in self.analyzer.regions:
                keywords = self.analyzer.regions[tag].get("keywords", [])
                if any(kw in title_lower for kw in keywords[:10]):  # Check first 10
                    return True

        return False

    def _get_priority(self, category: str, match_type: MatchType) -> int:
        """
        Get sorting priority (lower = higher priority).

        Priority order:
        1. Direct surgical technique matches
        2. Direct anatomy matches
        3. Foundational anatomy
        4. Foundational biomechanics/pathophysiology
        5. Other foundational
        6. Semantic matches
        """
        if match_type in (MatchType.DEDICATED_CHAPTER, MatchType.RELATED_SECTION):
            if category == "surgical_technique":
                return 10
            elif category == "anatomy":
                return 15
            else:
                return 20
        elif match_type == MatchType.FOUNDATIONAL:
            cat_priority = self.categories.get(category, {}).get("priority", 3)
            return 30 + cat_priority * 5  # Range: 35-55
        else:  # semantic
            return 60

    def _search_foundations(
        self,
        foundation_terms: Dict[str, List[str]],
        seen_titles: Set[str],
        max_total: int,
        max_per_category: int,
        report: StudyModeReport,
    ) -> List[StudyPackageResult]:
        """
        Search for foundational chapters using region-specific terms.

        Args:
            foundation_terms: Dict mapping category to search terms
            seen_titles: Set of already-seen titles (lowercase)
            max_total: Maximum total foundational results
            max_per_category: Maximum searches per category
            report: StudyModeReport to track matched/missing

        Returns:
            List of foundational StudyPackageResults
        """
        if not self.searcher:
            logger.warning("No searcher available for foundation searches")
            return []

        results: List[StudyPackageResult] = []

        # Priority order for categories
        category_order = ["anatomy", "biomechanics", "pathophysiology", "diagnostic", "approaches"]

        for category in category_order:
            if len(results) >= max_total:
                break

            terms = foundation_terms.get(category, [])[:max_per_category]

            for term in terms:
                if len(results) >= max_total:
                    break

                try:
                    # Run a simple search for this foundational term
                    search_results = self._run_foundation_search(term)

                    if not search_results:
                        # Track as missing topic
                        report.missing_topics.append(term)
                        continue

                    for sr in search_results[:3]:  # Top 3 per search
                        title = sr.chapter_title.lower() if hasattr(sr, 'chapter_title') else ""
                        if title and title not in seen_titles:
                            seen_titles.add(title)

                            # Track as matched topic
                            report.matched_topics[term] = sr.chapter_title if hasattr(sr, 'chapter_title') else title

                            # Create a new ChapterResult with FOUNDATIONAL match type
                            foundational_result = ChapterResult(
                                pdf_path=sr.pdf_path,
                                book_series=sr.book_series,
                                book_title=sr.book_title,
                                chapter_number=sr.chapter_number,
                                chapter_title=sr.chapter_title,
                                match_type=MatchType.FOUNDATIONAL,
                                page_count=sr.page_count,
                                matched_pages=sr.matched_pages,
                                preview_context=sr.preview_context,
                                total_occurrences=sr.total_occurrences,
                                relevance_score=MatchType.FOUNDATIONAL.relevance_score,
                                page_results=sr.page_results,
                                matched_sections=sr.matched_sections,
                                authority_score=sr.authority_score,
                                index_source=sr.index_source,
                            )

                            processed = StudyPackageResult(
                                title=sr.chapter_title,
                                source=sr.book_title,
                                page_number=sr.matched_pages[0] if sr.matched_pages else 0,
                                relevance_score=MatchType.FOUNDATIONAL.relevance_score,
                                category=category,
                                match_type=MatchType.FOUNDATIONAL,
                                region_match=True,
                                priority=self._get_priority(category, MatchType.FOUNDATIONAL),
                                original_result=foundational_result,
                            )
                            results.append(processed)

                            if len(results) >= max_total:
                                break

                except Exception as e:
                    logger.warning("Foundation search failed for '%s': %s", term, e)
                    report.missing_topics.append(term)

        return results

    def _run_foundation_search(self, term: str) -> List[ChapterResult]:
        """
        Run a FAST title-only search for foundational content.

        Uses simple title matching instead of full search for speed.
        """
        if not self.searcher:
            return []

        try:
            # FAST: Title-only search (no full search_library_chapters)
            results = []
            term_lower = term.lower()
            term_words = set(term_lower.split())

            for pdf_path in self.searcher.scanner.get_all_pdfs():
                meta = self.searcher.scanner.get_pdf_metadata(pdf_path, fast=True)
                title_lower = meta.chapter_title.lower()

                # Check if any term word matches title
                if any(word in title_lower for word in term_words if len(word) > 3):
                    result = ChapterResult(
                        pdf_path=pdf_path,
                        book_series=meta.book_series,
                        book_title=meta.book_title,
                        chapter_number=meta.chapter_number,
                        chapter_title=meta.chapter_title,
                        match_type=MatchType.FOUNDATIONAL,
                        page_count=1,
                        matched_pages=[1],
                        preview_context=f"Foundational: {term}",
                        total_occurrences=1,
                        matched_sections=[],
                        authority_score=50,
                        index_source="Foundation",
                    )
                    results.append(result)
                    if len(results) >= 5:
                        break

            return results
        except Exception as e:
            logger.warning("Foundation search error for '%s': %s", term, e)
            return []


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def enhance_broad_results(
    searcher: 'PDFSearcher',
    query: str,
    direct_results: List[ChapterResult],
    semantic_results: Optional[List[ChapterResult]] = None,
    max_foundational: int = 15,
) -> Tuple[List[ChapterResult], StudyModeReport]:
    """
    Enhance BROAD mode results with Study Package.

    Drop-in function to enhance existing BROAD mode search.

    Args:
        searcher: PDFSearcher instance
        query: Original search query
        direct_results: ChapterResults from keyword/title matching
        semantic_results: ChapterResults from semantic search
        max_foundational: Maximum foundational chapters to add

    Returns:
        Tuple of (enhanced ChapterResults, StudyModeReport)
    """
    assembler = StudyPackageAssembler(searcher=searcher)

    package = assembler.assemble(
        query=query,
        direct_results=direct_results,
        semantic_results=semantic_results,
        max_foundational=max_foundational,
    )

    return package.to_chapter_results(), package.report
