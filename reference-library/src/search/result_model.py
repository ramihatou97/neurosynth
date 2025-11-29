"""Data models for search results and library structure."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime


@dataclass
class PageMatch:
    """A single match on a specific page."""
    page_number: int
    match_text: str  # The matched text snippet
    context: str  # Surrounding text for AI categorization
    start_pos: int  # Character position in page


@dataclass
class SearchResult:
    """A search result from a PDF file."""
    pdf_path: Path
    book_series: str
    book_title: str
    chapter_number: Optional[int]
    chapter_title: str
    page_number: int
    match_text: str
    context: str
    category: Optional[str] = None
    category_group: Optional[str] = None  # "Surgical/Anatomical" or "Theoretical"
    category_confidence: Optional[float] = None
    category_reasoning: Optional[str] = None
    cached: bool = False

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
    """Progress tracking for search operations."""
    total_pdfs: int
    searched_pdfs: int = 0
    total_matches: int = 0
    current_file: str = ""
    categorized_count: int = 0

    @property
    def percent_complete(self) -> float:
        if self.total_pdfs == 0:
            return 0.0
        return (self.searched_pdfs / self.total_pdfs) * 100

    @property
    def status_text(self) -> str:
        return f"Searching {self.searched_pdfs}/{self.total_pdfs} PDFs... {self.total_matches} matches found"
