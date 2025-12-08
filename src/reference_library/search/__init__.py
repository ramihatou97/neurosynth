"""PDF search engine components."""

from reference_library.search.pdf_searcher import PDFSearcher
from reference_library.search.result_model import (
    ChapterResult,
    MatchType,
    PageMatch,
    SearchProgress,
    SearchResult,
)
from reference_library.search.search_strategy import SearchStrategy, get_strategy

# Study Package (BROAD mode enhancement)
from reference_library.search.study_package import (
    QueryAnalysis,
    StudyModeReport,
    analyze_query,
    enhance_broad_results,
)

__all__ = [
    # Core search
    "PDFSearcher",
    "ChapterResult",
    "MatchType",
    "SearchResult",
    "PageMatch",
    "SearchProgress",
    "SearchStrategy",
    "get_strategy",
    # Study Package
    "enhance_broad_results",
    "analyze_query",
    "StudyModeReport",
    "QueryAnalysis",
]
