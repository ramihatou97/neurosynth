"""PDF search engine components."""

from src.search.pdf_searcher import PDFSearcher
from src.search.result_model import (
    ChapterResult,
    MatchType,
    SearchResult,
    PageMatch,
    SearchProgress,
)
from src.search.search_strategy import SearchStrategy, get_strategy

# Study Package (BROAD mode enhancement)
from src.search.study_package import (
    enhance_broad_results,
    analyze_query,
    StudyModeReport,
    QueryAnalysis,
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
