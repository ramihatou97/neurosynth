"""Data models for search results and library structure."""
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from reference_library.search.section_detector import DetectedSection
else:
    # Runtime import - handle potential circularity or path issues
    try:
        from reference_library.search.section_detector import DetectedSection
    except ImportError:
        # Fallback if src not in path (e.g. running tests directly)
        try:
            from .section_detector import DetectedSection
        except ImportError:
            DetectedSection = None


class MatchType(Enum):
    """Type of match - determines how the result should be displayed and used."""
    DEDICATED_CHAPTER = auto()  # Chapter is dedicated to this topic (title match)
    RELATED_SECTION = auto()    # Topic discussed in a section of another chapter
    REFERENCE = auto()          # Topic mentioned/referenced
    SEMANTIC = auto()           # Semantic similarity match
    FOUNDATIONAL = auto()       # Foundational knowledge (anatomy, biomechanics, etc.)

    @property
    def relevance_score(self) -> int:
        """Base relevance score for this match type."""
        scores = {
            MatchType.DEDICATED_CHAPTER: 100,  # Highest - entire chapter is about topic
            MatchType.RELATED_SECTION: 70,     # High - section dedicated to topic
            MatchType.FOUNDATIONAL: 65,        # Study mode - foundational knowledge
            MatchType.SEMANTIC: 60,            # Medium - semantic similarity
            MatchType.REFERENCE: 40,           # Lower - just a mention
        }
        return scores.get(self, 40)

    @property
    def display_icon(self) -> str:
        """Get icon for display in UI."""
        icons = {
            MatchType.DEDICATED_CHAPTER: "📖",  # Book - dedicated chapter
            MatchType.RELATED_SECTION: "📑",    # Section
            MatchType.REFERENCE: "📝",          # Reference/mention
            MatchType.SEMANTIC: "🔍",           # Semantic search
            MatchType.FOUNDATIONAL: "📚",       # Books - foundational knowledge
        }
        return icons.get(self, "📄")

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        names = {
            MatchType.DEDICATED_CHAPTER: "Dedicated Chapter",
            MatchType.RELATED_SECTION: "Related Section",
            MatchType.REFERENCE: "Reference",
            MatchType.SEMANTIC: "Semantic Match",
            MatchType.FOUNDATIONAL: "Foundational",
        }
        return names.get(self, "Unknown")

    @property
    def color(self) -> str:
        """Color for UI display."""
        colors = {
            MatchType.DEDICATED_CHAPTER: "#27ae60",  # Green - primary source
            MatchType.RELATED_SECTION: "#3498db",    # Blue - related
            MatchType.REFERENCE: "#95a5a6",          # Gray - reference
            MatchType.SEMANTIC: "#9b59b6",           # Purple - semantic
            MatchType.FOUNDATIONAL: "#e67e22",       # Orange - foundational knowledge
        }
        return colors.get(self, "#95a5a6")


class MatchLocation(Enum):
    """Where in the document the match was found."""
    CHAPTER_TITLE = auto()    # Match in chapter/PDF filename
    SECTION_HEADER = auto()   # Match in section/subsection header
    BODY_TEXT = auto()        # Match in main body text
    FOOTNOTE = auto()         # Match in footnotes/references
    SEMANTIC = auto()         # Match from semantic search

    @property
    def relevance_score(self) -> int:
        """Get relevance score for this location."""
        scores = {
            MatchLocation.CHAPTER_TITLE: 100,
            MatchLocation.SECTION_HEADER: 80,
            MatchLocation.BODY_TEXT: 50,
            MatchLocation.FOOTNOTE: 20,
            MatchLocation.SEMANTIC: 60,
        }
        return scores.get(self, 50)

    @property
    def display_icon(self) -> str:
        """Get icon for display in UI."""
        icons = {
            MatchLocation.CHAPTER_TITLE: "📖",
            MatchLocation.SECTION_HEADER: "📑",
            MatchLocation.BODY_TEXT: "📝",
            MatchLocation.FOOTNOTE: "📎",
            MatchLocation.SEMANTIC: "🔍",
        }
        return icons.get(self, "📄")

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        names = {
            MatchLocation.CHAPTER_TITLE: "Chapter Title",
            MatchLocation.SECTION_HEADER: "Section",
            MatchLocation.BODY_TEXT: "Body Text",
            MatchLocation.FOOTNOTE: "Footnote",
            MatchLocation.SEMANTIC: "Semantic Match",
        }
        return names.get(self, "Unknown")


@dataclass
class PageMatch:
    """A single match on a specific page."""
    page_number: int
    match_text: str  # The matched text snippet
    context: str  # Surrounding text for AI categorization
    start_pos: int  # Character position in page
    location: MatchLocation = MatchLocation.BODY_TEXT  # Where in doc match was found


@dataclass
class SearchResult:
    """A search result from a PDF file (one per page, aggregated)."""
    pdf_path: Path
    book_series: str
    book_title: str
    chapter_number: Optional[int]
    chapter_title: str
    page_number: int
    match_text: str
    context: str
    # New fields for hierarchical search
    match_count: int = 1  # Number of matches on this page
    match_locations: List[MatchLocation] = field(default_factory=list)
    relevance_score: float = 50.0  # Calculated from match locations
    is_title_match: bool = False  # True if query matches chapter title
    # Legacy fields (kept for compatibility)
    category: Optional[str] = None
    category_group: Optional[str] = None
    category_confidence: Optional[float] = None
    category_reasoning: Optional[str] = None
    cached: bool = False

    def __post_init__(self):
        """Calculate relevance score from match locations."""
        if self.match_locations:
            # Use highest relevance location as primary score
            max_score = max(loc.relevance_score for loc in self.match_locations)
            # Bonus for multiple matches (diminishing returns)
            count_bonus = min(10, (self.match_count - 1) * 2)
            self.relevance_score = max_score + count_bonus

    @property
    def primary_location(self) -> MatchLocation:
        """Get the most relevant match location."""
        if not self.match_locations:
            return MatchLocation.BODY_TEXT
        return max(self.match_locations, key=lambda loc: loc.relevance_score)

    @property
    def location_icon(self) -> str:
        """Get icon representing the primary match location."""
        return self.primary_location.display_icon

    @property
    def display_name(self) -> str:
        """Display name for UI."""
        if self.chapter_number:
            return f"Ch {self.chapter_number}: {self.chapter_title}"
        return self.chapter_title

    @property
    def reference(self) -> str:
        """Generate citation reference."""
        return f"{self.book_series}, {self.display_name}, p.{self.page_number}"

    @property
    def match_summary(self) -> str:
        """Summary of matches for display."""
        if self.match_count == 1:
            return self.primary_location.display_name
        return f"{self.match_count} matches ({self.primary_location.display_name})"


@dataclass
class ChapterResult:
    """
    A chapter-level search result representing comprehensive knowledge on a topic.

    This is the primary result type for knowledge retrieval:
    - DEDICATED_CHAPTER: The entire chapter is about the searched topic
    - RELATED_SECTION: The chapter has a section dedicated to the topic
    - REFERENCE: The topic is mentioned in the chapter
    """
    pdf_path: Path
    book_series: str
    book_title: str
    chapter_number: Optional[int]
    chapter_title: str
    match_type: MatchType
    page_count: int
    # Pages with actual matches (for REFERENCE type) or all pages (for DEDICATED)
    matched_pages: List[int] = field(default_factory=list)
    # Best context snippet for preview
    preview_context: str = ""
    # Total keyword occurrences across all pages
    total_occurrences: int = 0
    # Relevance score (higher = more relevant)
    relevance_score: float = 0.0
    # Individual page results (for drill-down)
    # Individual page results (for drill-down)
    page_results: List[SearchResult] = field(default_factory=list)
    
    # Enhanced Search Fields
    matched_sections: List['DetectedSection'] = field(default_factory=list)
    authority_score: int = 0  # 0-100 score from Master Index
    index_source: str = ""    # Source of authority (e.g., "L7")

    # Strategy Weights (set by searcher based on active strategy)
    # FIX 0.8: Updated comments to reflect corrected strategy weights
    authority_weight: float = 0.5  # How much authority affects score (STRICT=0.2, STANDARD=0.5, BROAD=0.3)
    section_weight: float = 1.0    # How much section matches boost score (STRICT=1.5, STANDARD=1.0, BROAD=0.5)

    def __post_init__(self):
        """Calculate relevance score using strategy weights."""
        base_score = self.match_type.relevance_score

        # Bonus for more occurrences (capped)
        occurrence_bonus = min(20, self.total_occurrences * 2)

        # Bonus for more matched pages
        page_bonus = min(10, len(self.matched_pages))

        # Authority Boost (weighted by strategy)
        # STRICT: authority_weight=0.2 -> section match is primary signal
        # STANDARD: authority_weight=0.5 -> balanced authority influence
        # BROAD: authority_weight=0.3 -> less emphasis on authority
        authority_bonus = self.authority_score * self.authority_weight  # Max 20-50 points depending on weight

        # Section Match Bonus (weighted by strategy)
        # STRICT: section_weight=1.5 -> strongly prioritize exact section matches
        # STANDARD: section_weight=1.0 -> full boost for section matches
        # BROAD: section_weight=0.5 -> moderate boost
        section_bonus = (100 if self.matched_sections else 0) * self.section_weight

        self.relevance_score = base_score + occurrence_bonus + page_bonus + authority_bonus + section_bonus


    @property
    def display_name(self) -> str:
        """Display name for UI."""
        if self.chapter_number:
            return f"Ch {self.chapter_number}: {self.chapter_title}"
        return self.chapter_title

    @property
    def display_icon(self) -> str:
        """Icon representing match type."""
        return self.match_type.display_icon

    @property
    def reference(self) -> str:
        """Generate citation reference."""
        if len(self.matched_pages) == 1:
            return f"{self.book_series}, {self.display_name}, p.{self.matched_pages[0]}"
        elif len(self.matched_pages) > 1:
            return f"{self.book_series}, {self.display_name}, pp.{min(self.matched_pages)}-{max(self.matched_pages)}"
        return f"{self.book_series}, {self.display_name}"

    @property
    def match_summary(self) -> str:
        """Summary for display."""
        if self.match_type == MatchType.DEDICATED_CHAPTER:
            return f"📖 Dedicated Chapter ({self.page_count} pages)"
        elif self.match_type == MatchType.RELATED_SECTION:
            return f"📑 Related Section ({len(self.matched_pages)} pages)"
        else:
            return f"📝 {self.total_occurrences} references across {len(self.matched_pages)} pages"

    @property
    def is_dedicated(self) -> bool:
        """True if this is a dedicated chapter about the topic."""
        return self.match_type == MatchType.DEDICATED_CHAPTER

    def get_all_pages(self) -> List[int]:
        """Get all pages to include when synthesizing."""
        if self.match_type == MatchType.DEDICATED_CHAPTER:
            # Include entire chapter
            return list(range(1, self.page_count + 1))
        else:
            # Only matched pages
            return sorted(self.matched_pages)


@dataclass
class ChapterMetadata:
    """Metadata for a single chapter/PDF file."""
    pdf_path: Path
    book_series: str
    book_title: str
    chapter_number: Optional[int]
    chapter_title: str
    page_count: int = 0
    file_size: int = 0


@dataclass
class BookSeries:
    """A book series containing multiple chapters."""
    name: str
    display_name: str
    path: Path
    chapters: list[ChapterMetadata] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return sum(ch.page_count for ch in self.chapters)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)


@dataclass
class LibraryIndex:
    """Complete index of the reference library."""
    root_path: Path
    series: dict[str, BookSeries] = field(default_factory=dict)
    entire_books: list[ChapterMetadata] = field(default_factory=list)
    last_scanned: Optional[datetime] = None

    @property
    def total_pdfs(self) -> int:
        count = len(self.entire_books)
        for series in self.series.values():
            count += series.chapter_count
        return count

    @property
    def total_pages(self) -> int:
        pages = sum(book.page_count for book in self.entire_books)
        for series in self.series.values():
            pages += series.total_pages
        return pages


@dataclass
class SearchProgress:
    """Progress tracking for search operations.

    With on-demand extraction, we distinguish between:
    - searched_pdfs: Total PDFs scanned (metadata check only, fast)
    - candidates_processed: PDFs with text actually extracted (slow)
    - total_matches: Results found from candidates
    """
    total_pdfs: int
    searched_pdfs: int = 0
    candidates_processed: int = 0  # PDFs that passed filter and had text extracted
    total_matches: int = 0
    current_file: str = ""
    categorized_count: int = 0
    phase: str = "scanning"  # "scanning" or "complete"

    @property
    def percent_complete(self) -> float:
        if self.total_pdfs == 0:
            return 0.0
        return (self.searched_pdfs / self.total_pdfs) * 100

    @property
    def status_text(self) -> str:
        """Human-readable status for the current search phase."""
        if self.phase == "scanning":
            if self.candidates_processed > 0:
                return f"Scanning {self.searched_pdfs}/{self.total_pdfs} | {self.candidates_processed} candidates | {self.total_matches} matches"
            return f"Scanning library: {self.searched_pdfs}/{self.total_pdfs} PDFs..."
        else:
            return f"Found {self.total_matches} matches from {self.candidates_processed} candidates (scanned {self.total_pdfs})"
