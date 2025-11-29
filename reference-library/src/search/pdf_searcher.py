"""PDF text extraction and search engine with semantic search support."""
import os
import re
from pathlib import Path
from typing import Generator, Optional, Callable
import fitz  # PyMuPDF

from .result_model import SearchResult, PageMatch, SearchProgress, ChapterMetadata
from .semantic_searcher import SemanticSearcher
from ..cache.database import Database
from ..utils.library_scanner import LibraryScanner
import config

# Prevent tokenizers deadlock when forking
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class PDFSearcher:
    """On-demand PDF text search using PyMuPDF with optional semantic search."""

    def __init__(self, library_path: Path, database: Database):
        self.library_path = library_path.resolve()
        self.database = database
        self.scanner = LibraryScanner(library_path, database)
        self.semantic = SemanticSearcher(database)
        self._cancelled = False

    def cancel(self):
        """Cancel ongoing search."""
        self._cancelled = True

    def reset(self):
        """Reset cancellation flag for new search."""
        self._cancelled = False

    def _validate_path(self, pdf_path: Path) -> None:
        """
        Ensure path is within library directory to prevent path traversal attacks.

        Args:
            pdf_path: Path to validate

        Raises:
            ValueError: If path is outside library directory
        """
        try:
            resolved = pdf_path.resolve()
            resolved.relative_to(self.library_path)
        except ValueError:
            raise ValueError(f"Path {pdf_path} is outside library directory")

    def search_library(
        self,
        query: str,
        mode: str = "keyword",
        progress_callback: Optional[Callable[[SearchProgress], None]] = None
    ) -> Generator[SearchResult, None, None]:
        """
        Search entire library for query.

        Args:
            query: Search term
            mode: "keyword", "semantic", or "hybrid"
            progress_callback: Optional callback for progress updates

        Yields:
            SearchResult objects as they are found (streaming)
        """
        self.reset()

        # Track seen pages to avoid duplicates in hybrid mode
        seen_pages: set[str] = set()

        # 1. Semantic Search Phase (instant, ranked by similarity)
        if mode in ["semantic", "hybrid"] and self.semantic.enabled:
            semantic_hits = self.semantic.search(query, n_results=30)

            # Report semantic search phase with progress
            if progress_callback:
                semantic_progress = SearchProgress(total_pdfs=0, searched_pdfs=0, total_matches=0)
                semantic_progress.current_file = "Semantic search..."
                progress_callback(semantic_progress)

            for i, hit in enumerate(semantic_hits):
                if self._cancelled:
                    break

                page_key = f"{hit['pdf_path']}:{hit['page_number']}"
                seen_pages.add(page_key)

                metadata = self.scanner.get_pdf_metadata(hit["pdf_path"])

                # Get context from SQLite cache (not ChromaDB)
                checksum = self.database.get_file_checksum(hit["pdf_path"])
                cached_text = self.database.get_cached_text(
                    hit["pdf_path"],
                    hit["page_number"] - 1,  # 0-indexed in cache
                    checksum
                )
                context = self._extract_context_from_text(cached_text or "", query)

                result = SearchResult(
                    pdf_path=hit["pdf_path"],
                    book_series=metadata.book_series,
                    book_title=metadata.book_title,
                    chapter_number=metadata.chapter_number,
                    chapter_title=metadata.chapter_title,
                    page_number=hit["page_number"],
                    match_text=f"[Semantic: {hit['score']:.0%}]",
                    context=context
                )
                yield result

                # Update semantic search progress
                if progress_callback:
                    semantic_progress.total_matches = i + 1
                    progress_callback(semantic_progress)

            if mode == "semantic":
                return

        # 2. Keyword Search Phase (linear scan, high recall)
        if mode in ["keyword", "hybrid"]:
            all_pdfs = self.scanner.get_all_pdfs()
            total_pdfs = len(all_pdfs)
            progress = SearchProgress(total_pdfs=total_pdfs)

            for pdf_path in all_pdfs:
                if self._cancelled:
                    break

                progress.current_file = pdf_path.name
                if progress_callback:
                    progress_callback(progress)

                metadata = self.scanner.get_pdf_metadata(pdf_path)
                matches = self.search_pdf(query, pdf_path)

                for match in matches:
                    if self._cancelled:
                        break

                    # Skip if already returned by semantic search
                    page_key = f"{pdf_path}:{match.page_number}"
                    if mode == "hybrid" and page_key in seen_pages:
                        continue

                    result = SearchResult(
                        pdf_path=pdf_path,
                        book_series=metadata.book_series,
                        book_title=metadata.book_title,
                        chapter_number=metadata.chapter_number,
                        chapter_title=metadata.chapter_title,
                        page_number=match.page_number,
                        match_text=match.match_text,
                        context=match.context
                    )
                    progress.total_matches += 1
                    yield result

                progress.searched_pdfs += 1
                if progress_callback:
                    progress_callback(progress)

    def search_pdf(self, query: str, pdf_path: Path) -> list[PageMatch]:
        """Search a single PDF for query, return matches with context."""
        matches = []

        try:
            # Validate path is within library directory
            self._validate_path(pdf_path)

            # Get file checksum for cache
            checksum = self.database.get_file_checksum(pdf_path)

            # Try to get all cached pages first
            cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)

            # Use context manager for proper resource cleanup
            with fitz.open(pdf_path) as doc:
                for page_num in range(len(doc)):
                    # Get page text (from cache or extract)
                    if page_num in cached_pages:
                        text = cached_pages[page_num]
                    else:
                        page = doc[page_num]
                        text = page.get_text()
                        # Cache the extracted text
                        self.database.cache_pdf_text(pdf_path, page_num, text, checksum)

                    # Search for query (case-insensitive)
                    page_matches = self._find_matches(query, text, page_num + 1)  # 1-indexed pages
                    matches.extend(page_matches)

        except ValueError as e:
            # Path validation error - log but don't expose internal paths
            print(f"Invalid PDF path: {e}")
        except (fitz.FileDataError, OSError) as e:
            # PDF-specific errors
            print(f"Error reading PDF {pdf_path.name}: {e}")
        except Exception as e:
            # Log error but don't fail entire search
            print(f"Error searching {pdf_path.name}: {type(e).__name__}")

        return matches

    def _find_matches(self, query: str, text: str, page_number: int) -> list[PageMatch]:
        """Find all occurrences of query in text with context."""
        matches = []

        # Case-insensitive search
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for match in pattern.finditer(text):
            start_pos = match.start()
            match_text = match.group()

            # Extract context window
            context = self._extract_context(text, start_pos, len(match_text))

            matches.append(PageMatch(
                page_number=page_number,
                match_text=match_text,
                context=context,
                start_pos=start_pos
            ))

        return matches

    def _extract_context(self, text: str, match_start: int, match_length: int) -> str:
        """Extract text window around match for preview and AI categorization."""
        window_size = config.CONTEXT_WINDOW_SIZE

        # Calculate window bounds
        context_start = max(0, match_start - window_size)
        context_end = min(len(text), match_start + match_length + window_size)

        context = text[context_start:context_end]

        # Clean up context (normalize whitespace, remove excessive newlines)
        context = ' '.join(context.split())

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context

    def extract_page_text(self, pdf_path: Path, page_number: int) -> str:
        """Extract text from a specific page."""
        try:
            # Validate path is within library directory
            self._validate_path(pdf_path)

            checksum = self.database.get_file_checksum(pdf_path)

            # Check cache first
            cached = self.database.get_cached_text(pdf_path, page_number - 1, checksum)
            if cached:
                return cached

            # Extract from PDF using context manager
            with fitz.open(pdf_path) as doc:
                if 0 <= page_number - 1 < len(doc):
                    text = doc[page_number - 1].get_text()

                    # Cache it
                    self.database.cache_pdf_text(pdf_path, page_number - 1, text, checksum)
                    return text

        except ValueError as e:
            print(f"Invalid PDF path: {e}")
        except (fitz.FileDataError, OSError) as e:
            print(f"Error reading PDF {pdf_path.name}: {e}")
        except Exception as e:
            print(f"Error extracting page {page_number} from {pdf_path.name}: {type(e).__name__}")

        return ""

    def get_page_count(self, pdf_path: Path) -> int:
        """Get total page count of a PDF."""
        try:
            self._validate_path(pdf_path)
            with fitz.open(pdf_path) as doc:
                return len(doc)
        except (ValueError, fitz.FileDataError, OSError):
            return 0

    def _extract_context_from_text(self, text: str, query: str) -> str:
        """Extract context window around query match in text (for semantic results)."""
        if not text:
            return ""

        # Try to find query in text and center on it
        match = re.search(re.escape(query), text, re.IGNORECASE)
        if match:
            return self._extract_context(text, match.start(), len(match.group()))

        # If query not found literally, return start of text
        return text[:config.CONTEXT_WINDOW_SIZE] + "..."

    def index_library_semantic(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> int:
        """
        Build semantic index for entire library.
        Should be run in background thread.

        Args:
            progress_callback: Optional callback (current_pdf, total_pdfs)

        Returns:
            Total number of pages indexed
        """
        import time

        if not self.semantic.enabled:
            return 0

        all_pdfs = self.scanner.get_all_pdfs()
        total = len(all_pdfs)
        indexed_pages = 0

        for i, pdf_path in enumerate(all_pdfs):
            if self._cancelled:
                break

            try:
                # Validate path is within library
                self._validate_path(pdf_path)

                checksum = self.database.get_file_checksum(pdf_path)
                cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)

                # If no cached pages, extract text first using context manager
                if not cached_pages:
                    with fitz.open(pdf_path) as doc:
                        for page_num in range(len(doc)):
                            text = doc[page_num].get_text()
                            self.database.cache_pdf_text(pdf_path, page_num, text, checksum)
                            cached_pages[page_num] = text

                # Batch encode all pages at once (more efficient, fewer GIL holds)
                batch_count = self.semantic.index_pages_batch(pdf_path, cached_pages, checksum)
                indexed_pages += batch_count

                # Yield GIL between PDFs to let UI thread run
                time.sleep(0.01)

                if progress_callback:
                    progress_callback(i + 1, total)

            except (ValueError, fitz.FileDataError, OSError) as e:
                print(f"Error indexing {pdf_path.name}: {e}")
            except Exception as e:
                print(f"Unexpected error indexing {pdf_path.name}: {type(e).__name__}")

        return indexed_pages

    def index_library_parallel(
        self,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> int:
        """
        Build semantic index using multiple CPU cores.
        Text extraction runs in parallel processes, DB writes in main thread.

        Args:
            max_workers: Number of parallel worker processes
            progress_callback: Optional callback (current_pdf, total_pdfs, current_file)

        Returns:
            Total number of pages indexed
        """
        if not self.semantic.enabled:
            return 0

        all_pdfs = self.scanner.get_all_pdfs()
        total = len(all_pdfs)
        indexed_pages = 0

        if total == 0:
            return 0

        # Convert to strings for multiprocessing (Path objects don't pickle well)
        pdf_paths = [str(p) for p in all_pdfs]

        # Lazy import to avoid tkinter/multiprocessing conflicts at module load
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from ..utils.parallel_workers import extract_text_worker

        # Use spawn context on macOS to avoid tokenizers/fork deadlock
        mp_context = multiprocessing.get_context("spawn")

        # Submit all extraction jobs to process pool
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp_context) as executor:
            # Map futures back to their paths
            future_to_path = {
                executor.submit(extract_text_worker, p): p
                for p in pdf_paths
            }

            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_path)):
                if self._cancelled:
                    # Cancel remaining futures
                    for f in future_to_path:
                        f.cancel()
                    break

                pdf_path_str = future_to_path[future]
                pdf_path = Path(pdf_path_str)

                try:
                    # Get extraction result from worker
                    result = future.result()

                    if result["error"]:
                        print(f"Worker error extracting {pdf_path.name}: {result['error']}")
                        continue

                    # Validate path is within library
                    self._validate_path(pdf_path)

                    # Calculate checksum in main process (database operation)
                    checksum = self.database.get_file_checksum(pdf_path)

                    # Cache text and index each page (main thread = safe for SQLite)
                    pages = result["pages"]
                    for page_num, text in pages.items():
                        # Cache the extracted text
                        self.database.cache_pdf_text(pdf_path, page_num, text, checksum)

                        # Index in semantic search
                        if self.semantic.index_page(pdf_path, page_num + 1, text, checksum):
                            indexed_pages += 1

                    if progress_callback:
                        progress_callback(i + 1, total, pdf_path.name)

                except ValueError as e:
                    print(f"Invalid path {pdf_path.name}: {e}")
                except Exception as e:
                    print(f"Error processing {pdf_path.name}: {type(e).__name__}: {e}")

        return indexed_pages
