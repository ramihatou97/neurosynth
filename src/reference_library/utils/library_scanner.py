"""Library directory structure scanner and parser."""
import re
from pathlib import Path
from typing import Optional, Callable
import fitz  # PyMuPDF

from ..search.result_model import ChapterMetadata, BookSeries, LibraryIndex
from ..cache.database import Database
from src import config

# Visual extraction imports (lazy loaded)
_visual_imports_loaded = False
_ImageExtractor = None
_VisualElement = None
_ImageType = None


class LibraryScanner:
    """Parse the neurosurgery reference library directory structure."""

    # Patterns for parsing chapter filenames
    CHAPTER_PATTERN = re.compile(r'^(\d+)\s+(.+)\.pdf$', re.IGNORECASE)
    CHAPTER_PATTERN_ALT = re.compile(r'^Chapter\s*(\d+)[_:\s]+(.+)\.pdf$', re.IGNORECASE)

    def __init__(self, library_path: Path, database: Optional[Database] = None):
        self.library_path = library_path
        self.database = database
        self._cancelled = False  # Extraction cancellation flag

    def scan_library(self, use_cache: bool = True) -> LibraryIndex:
        """Build complete library index from directory structure."""
        index = LibraryIndex(root_path=self.library_path)

        # Find Book chapters directory (may have trailing space)
        chapters_dir = self._find_subdir("Book chapters")
        if chapters_dir and chapters_dir.exists():
            for series_dir in chapters_dir.iterdir():
                if series_dir.is_dir() and not series_dir.name.startswith('.'):
                    series = self._scan_series(series_dir)
                    if series and series.chapters:
                        index.series[series.name] = series

        # Find Entire books directory
        books_dir = self._find_subdir("Entire books")
        if books_dir and books_dir.exists():
            for pdf_file in books_dir.glob("*.pdf"):
                metadata = self._parse_entire_book(pdf_file)
                if metadata:
                    index.entire_books.append(metadata)

        return index

    def _find_subdir(self, name_prefix: str) -> Optional[Path]:
        """Find subdirectory by prefix (handles trailing spaces)."""
        for item in self.library_path.iterdir():
            if item.is_dir() and item.name.strip().lower() == name_prefix.lower():
                return item
        return None

    def _scan_series(self, series_dir: Path) -> Optional[BookSeries]:
        """Scan a book series directory."""
        series_name = self._identify_series(series_dir.name)
        display_name = config.KNOWN_SERIES.get(series_name, series_name)

        series = BookSeries(
            name=series_name,
            display_name=display_name,
            path=series_dir
        )

        # Recursively find all PDFs in this series
        for pdf_file in series_dir.rglob("*.pdf"):
            metadata = self._parse_chapter(pdf_file, series_name, display_name)
            if metadata:
                series.chapters.append(metadata)

        # Sort chapters by chapter number
        series.chapters.sort(key=lambda c: (c.chapter_number or 9999, c.chapter_title))

        return series if series.chapters else None

    def _identify_series(self, dir_name: str) -> str:
        """Identify which book series a directory belongs to."""
        dir_lower = dir_name.lower()

        for key, display in config.KNOWN_SERIES.items():
            if key.lower() in dir_lower:
                return key

        return dir_name

    def _parse_chapter(self, pdf_path: Path, series_name: str, book_title: str, skip_page_count: bool = False) -> Optional[ChapterMetadata]:
        """Parse chapter metadata from PDF filename.

        Args:
            pdf_path: Path to PDF file
            series_name: Book series name
            book_title: Book title
            skip_page_count: If True, skip expensive PDF open for page count (FAST mode)
        """
        filename = pdf_path.stem

        # Try standard pattern: "26 Positioning for Peripheral Nerve Surgery"
        match = self.CHAPTER_PATTERN.match(pdf_path.name)
        if match:
            chapter_num = int(match.group(1))
            chapter_title = match.group(2).strip()
        else:
            # Try alternative pattern: "Chapter 3_ The Posterior Fossa Veins"
            match = self.CHAPTER_PATTERN_ALT.match(pdf_path.name)
            if match:
                chapter_num = int(match.group(1))
                chapter_title = match.group(2).strip()
            else:
                # No chapter number, use filename as title
                chapter_num = None
                chapter_title = filename

        # Get file stats (fast - just stat call)
        try:
            file_size = pdf_path.stat().st_size
        except Exception:
            file_size = 0

        # Get page count (SLOW - opens PDF) - skip in fast mode
        page_count = 0 if skip_page_count else self._get_page_count(pdf_path)

        return ChapterMetadata(
            pdf_path=pdf_path,
            book_series=series_name,
            book_title=book_title,
            chapter_number=chapter_num,
            chapter_title=chapter_title,
            page_count=page_count,
            file_size=file_size
        )

    def _parse_entire_book(self, pdf_path: Path, skip_page_count: bool = False) -> Optional[ChapterMetadata]:
        """Parse metadata for a complete book PDF."""
        filename = pdf_path.stem
        try:
            file_size = pdf_path.stat().st_size
        except Exception:
            file_size = 0
        page_count = 0 if skip_page_count else self._get_page_count(pdf_path)

        return ChapterMetadata(
            pdf_path=pdf_path,
            book_series="Entire Books",
            book_title=filename,
            chapter_number=None,
            chapter_title=filename,
            page_count=page_count,
            file_size=file_size
        )

    def _get_page_count(self, pdf_path: Path) -> int:
        """Get page count from PDF without full text extraction."""
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    def get_all_pdfs(self) -> list[Path]:
        """Get flat list of all PDF files in library."""
        pdfs = []

        # Legacy structure: Book chapters (handles trailing space)
        chapters_dir = self._find_subdir("Book chapters")
        if chapters_dir and chapters_dir.exists():
            pdfs.extend(chapters_dir.rglob("*.pdf"))

        # Legacy structure: Entire books (handles trailing space)
        books_dir = self._find_subdir("Entire books")
        if books_dir and books_dir.exists():
            pdfs.extend(books_dir.glob("*.pdf"))

        # New structure: Numbered directories (01_*, 02_*, etc.)
        # Handles: 01_COMPLETE_TEXTBOOKS, 02_MULTI_CHAPTER_BOOKS, 03_SINGLE_CHAPTERS,
        #          04_EVIDENCE_BASE_STUDIES, 05_EDUCATIONAL_MATERIALS, 06_CLINICAL_GUIDELINES, etc.
        for item in self.library_path.iterdir():
            if item.is_dir() and item.name[:2].isdigit() and item.name[2] == '_':
                pdfs.extend(item.rglob("*.pdf"))

        # Fallback: If no PDFs found yet, scan entire library recursively
        if not pdfs:
            pdfs.extend(self.library_path.rglob("*.pdf"))

        return sorted(set(pdfs))  # Remove duplicates and sort

    def get_pdf_metadata(self, pdf_path: Path, fast: bool = False) -> ChapterMetadata:
        """Get metadata for a specific PDF.

        Args:
            pdf_path: Path to PDF file
            fast: If True, skip expensive page count lookup (for search loops)
        """
        # Determine if it's a chapter or entire book (legacy structure)
        if "entire books" in str(pdf_path).lower():
            return self._parse_entire_book(pdf_path, skip_page_count=fast)

        # Try legacy structure first: Book chapters
        chapters_dir = self._find_subdir("Book chapters")
        if chapters_dir:
            try:
                relative = pdf_path.relative_to(chapters_dir)
                series_name = relative.parts[0].strip() if relative.parts else "Unknown"
                display_name = config.KNOWN_SERIES.get(series_name, series_name)
                return self._parse_chapter(pdf_path, series_name, display_name, skip_page_count=fast)
            except ValueError:
                pass  # Not in legacy structure, try new structure

        # New structure: Numbered directories (01_*, 02_*, etc.)
        try:
            relative = pdf_path.relative_to(self.library_path)
            parts = relative.parts
            if parts and len(parts[0]) > 3 and parts[0][:2].isdigit() and parts[0][2] == '_':
                # e.g., "01_COMPLETE_TEXTBOOKS" -> category
                category = parts[0]
                # Use parent folder name as series if available
                if len(parts) >= 2:
                    series_name = parts[1].strip()
                else:
                    series_name = category
                display_name = series_name
                return self._parse_chapter(pdf_path, series_name, display_name, skip_page_count=fast)
        except ValueError:
            pass

        # Fallback: use filename-based parsing
        series_name = "Unknown"
        display_name = config.KNOWN_SERIES.get(series_name, series_name)
        return self._parse_chapter(pdf_path, series_name, display_name, skip_page_count=fast)

    def detect_changes(self) -> dict:
        """
        Detect new, modified, and deleted files by comparing library to database.
        Returns dict with 'new', 'modified', 'deleted' lists of paths.
        """
        if not self.database:
            raise ValueError("Database required for change detection")

        changes = {
            'new': [],
            'modified': [],
            'deleted': []
        }

        # Get all current PDFs in library
        current_pdfs = set(str(p) for p in self.get_all_pdfs())

        # Get all tracked paths from database
        tracked_paths = self.database.get_all_tracked_paths()

        # Find new files (in library but not tracked)
        new_paths = current_pdfs - tracked_paths
        for path_str in new_paths:
            path = Path(path_str)
            if path.exists():
                changes['new'].append(path)
                # Track the new file (FAST: no PDF opening)
                metadata = self._get_metadata_fast(path)
                checksum = self.database.get_fast_checksum(path)
                self.database.track_file(
                    path,
                    checksum=checksum,
                    file_size=path.stat().st_size,
                    book_series=metadata.book_series,
                    chapter_title=metadata.chapter_title,
                    page_count=0  # Skip for fast detection
                )

        # Find deleted files (tracked but not in library)
        deleted_paths = tracked_paths - current_pdfs
        for path_str in deleted_paths:
            changes['deleted'].append(Path(path_str))
            self.database.remove_tracked_file(Path(path_str))

        return changes

    def sync_library(
        self,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        force: bool = False,
    ) -> dict:
        """
        ULTRA-FAST library sync: Just discover PDFs, no heavy processing.
        Uses simple filename parsing, no PDF file opening.
        """
        if not self.database:
            raise ValueError("Database required for sync")

        # Force mode: clear existing tracked files for clean slate
        if force:
            self.database.clear_tracked_files()

        tracked_paths = self.database.get_all_tracked_paths()

        # Skip if database already populated
        if len(tracked_paths) > 0:
            return {
                'total_files': len(tracked_paths),
                'new_files': 0,
                'unindexed': self.database.get_new_files_count()
            }

        # FAST: Discover all PDFs (just filesystem walk)
        all_pdfs = list(self.get_all_pdfs())
        total = len(all_pdfs)

        if not all_pdfs:
            return {'total_files': 0, 'new_files': 0, 'unindexed': 0}

        # ULTRA-FAST: Simple loop, no threading overhead
        files_data = []
        for idx, pdf_path in enumerate(all_pdfs):
            try:
                # INSTANT: Parse metadata from filename only
                chapter_title = pdf_path.stem.replace('-', ' ').replace('_', ' ')

                # Get series from parent folder
                try:
                    relative = pdf_path.relative_to(self.library_path)
                    parts = relative.parts
                    if len(parts) >= 2:
                        book_series = parts[1] if parts[0][:2].isdigit() else parts[0]
                    else:
                        book_series = parts[0] if parts else "Unknown"
                except ValueError:
                    book_series = "Unknown"

                # FAST checksum: size + mtime only
                stat = pdf_path.stat()
                checksum = f"{stat.st_size}_{int(stat.st_mtime)}"

                files_data.append({
                    "pdf_path": pdf_path,
                    "checksum": checksum,
                    "file_size": stat.st_size,
                    "book_series": str(book_series)[:100],
                    "chapter_title": chapter_title[:200],
                    "page_count": 0
                })
            except Exception:
                pass  # Skip problematic files

            # Progress every 100 files
            if progress_callback and idx % 100 == 0:
                progress_callback(idx + 1, total)

        # Final progress
        if progress_callback:
            progress_callback(total, total)

        # Batch insert
        if files_data:
            self.database.track_files_batch(files_data, is_indexed=True)

        return {
            'total_files': len(files_data),
            'new_files': len(files_data),
            'unindexed': 0
        }

    def cancel_extraction(self):
        """Cancel ongoing extraction."""
        self._cancelled = True

    def reset_extraction(self):
        """Reset cancellation flag for new extraction."""
        self._cancelled = False

    def _get_metadata_fast(self, pdf_path: Path) -> ChapterMetadata:
        """Get metadata without opening PDF (no page count)."""
        # Determine if it's a chapter or entire book
        if "entire books" in str(pdf_path).lower():
            return ChapterMetadata(
                pdf_path=pdf_path,
                book_series="Entire Books",
                book_title=pdf_path.stem,
                chapter_number=None,
                chapter_title=pdf_path.stem,
                page_count=0,
                file_size=pdf_path.stat().st_size
            )

        # Find the series from path
        chapters_dir = self._find_subdir("Book chapters")
        if chapters_dir:
            try:
                relative = pdf_path.relative_to(chapters_dir)
                series_name = relative.parts[0].strip() if relative.parts else "Unknown"
            except ValueError:
                series_name = "Unknown"
        else:
            series_name = "Unknown"

        display_name = config.KNOWN_SERIES.get(series_name, series_name)

        # Parse chapter info from filename without opening PDF
        filename = pdf_path.stem
        match = self.CHAPTER_PATTERN.match(pdf_path.name)
        if match:
            chapter_num = int(match.group(1))
            chapter_title = match.group(2).strip()
        else:
            match = self.CHAPTER_PATTERN_ALT.match(pdf_path.name)
            if match:
                chapter_num = int(match.group(1))
                chapter_title = match.group(2).strip()
            else:
                chapter_num = None
                chapter_title = filename

        return ChapterMetadata(
            pdf_path=pdf_path,
            book_series=series_name,
            book_title=display_name,
            chapter_number=chapter_num,
            chapter_title=chapter_title,
            page_count=0,  # Skip for fast sync
            file_size=pdf_path.stat().st_size
        )

    # Visual Extraction Methods

    def _load_visual_imports(self) -> bool:
        """Lazy load visual extraction modules."""
        global _visual_imports_loaded, _ImageExtractor, _VisualElement, _ImageType

        if _visual_imports_loaded:
            return _ImageExtractor is not None

        try:
            from .neurosynth_imports import (
                ImageExtractor,
                VisualElement,
                ImageType,
                NEUROSYNTH_AVAILABLE
            )
            if NEUROSYNTH_AVAILABLE:
                _ImageExtractor = ImageExtractor
                _VisualElement = VisualElement
                _ImageType = ImageType
                _visual_imports_loaded = True
                return True
            else:
                _visual_imports_loaded = True
                return False
        except ImportError as e:
            print(f"Warning: Could not load visual extraction modules: {e}")
            _visual_imports_loaded = True
            return False

    def extract_figures(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None,
        force: bool = False,
        hybrid: bool = True
    ) -> list[dict]:
        """Extract figures from a single PDF.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images (default: config.IMAGES_DIR)
            force: If True, re-extract even if already cached
            hybrid: If True, use hybrid extraction (raw + snapshot) for better accuracy

        Returns:
            List of figure dictionaries with metadata
        """
        if not self._load_visual_imports():
            print("Visual extraction not available")
            return []

        if not self.database:
            raise ValueError("Database required for figure extraction")

        # Check if already extracted (skip if not forcing)
        checksum = self.database.get_file_checksum(pdf_path)
        if not force and self.database.is_pdf_figures_extracted(pdf_path, checksum):
            # Return cached figures
            return self.database.get_pdf_figures(pdf_path, checksum)

        # Set up output directory
        if output_dir is None:
            output_dir = config.IMAGES_DIR / pdf_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create extractor with Reference Library's config
        extractor = _ImageExtractor(
            min_size=config.MIN_IMAGE_SIZE,
            max_size=config.MAX_IMAGE_SIZE
        )

        # Extract images synchronously (hybrid mode captures labels/arrows)
        try:
            if hybrid:
                elements = extractor.extract_images_hybrid_sync(pdf_path, output_dir)
            else:
                elements = extractor.extract_images_sync(pdf_path, output_dir)
        except Exception as e:
            print(f"Error extracting figures from {pdf_path.name}: {e}")
            return []

        # Convert to dicts and cache
        figures = []
        for elem in elements:
            fig_dict = {
                "id": elem.id,
                "pdf_path": str(pdf_path),
                "page_number": elem.page_number,
                "image_path": str(elem.image_path) if elem.image_path else None,
                "format": elem.format,
                "width": elem.width,
                "height": elem.height,
                "bbox": elem.bbox,
                "caption": elem.caption,
                "caption_confidence": elem.caption_confidence,
                "image_type": elem.image_type.value if hasattr(elem.image_type, 'value') else str(elem.image_type),
                "type_confidence": elem.type_confidence,
                "context_text": elem.context_text,
                "visual_hash": elem.visual_hash,
            }
            figures.append(fig_dict)

        # Batch cache to database (pass pdf_path for zero-figure marker)
        self.database.cache_visual_elements_batch(figures, checksum, pdf_path)

        # Generate thumbnails for extracted figures
        self._generate_thumbnails(figures)

        return figures

    def _generate_thumbnails(self, figures: list[dict]) -> int:
        """Generate thumbnails for a list of figures.

        Args:
            figures: List of figure dictionaries with image_path

        Returns:
            Number of thumbnails generated
        """
        from .thumbnail_cache import get_thumbnail_cache, THUMB_SIZE_SMALL

        thumb_cache = get_thumbnail_cache()
        generated = 0

        for fig in figures:
            image_path = fig.get("image_path")
            if image_path and Path(image_path).exists():
                thumb_path = thumb_cache.get_or_create_thumbnail(image_path, THUMB_SIZE_SMALL)
                if thumb_path:
                    generated += 1

        return generated

    def extract_figures_batch(
        self,
        pdf_paths: Optional[list[Path]] = None,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
        force: bool = False
    ) -> dict:
        """Extract figures from multiple PDFs with batch processing.

        Args:
            pdf_paths: List of PDFs to process (default: all library PDFs)
            on_progress: Callback(pdf_name, figures_extracted, total_processed)
            force: If True, re-extract even if already cached

        Returns:
            Dict with statistics: total_pdfs, total_figures, figures_by_type
        """
        if not self._load_visual_imports():
            return {"error": "Visual extraction not available"}

        if not self.database:
            raise ValueError("Database required for figure extraction")

        # Get PDFs to process
        if pdf_paths is None:
            pdf_paths = self.get_all_pdfs()

        stats = {
            "total_pdfs": len(pdf_paths),
            "pdfs_processed": 0,
            "pdfs_skipped": 0,
            "total_figures": 0,
            "figures_by_type": {}
        }

        for i, pdf_path in enumerate(pdf_paths):
            # Check if already extracted
            checksum = self.database.get_file_checksum(pdf_path)
            if not force and self.database.is_pdf_figures_extracted(pdf_path, checksum):
                stats["pdfs_skipped"] += 1
                if on_progress:
                    on_progress(pdf_path.name, 0, i + 1)
                continue

            # Extract figures
            try:
                figures = self.extract_figures(pdf_path, force=force)
                stats["pdfs_processed"] += 1
                stats["total_figures"] += len(figures)

                # Count by type
                for fig in figures:
                    fig_type = fig.get("image_type", "unknown")
                    stats["figures_by_type"][fig_type] = \
                        stats["figures_by_type"].get(fig_type, 0) + 1

                if on_progress:
                    on_progress(pdf_path.name, len(figures), i + 1)

            except Exception as e:
                print(f"Error processing {pdf_path.name}: {e}")
                if on_progress:
                    on_progress(pdf_path.name, -1, i + 1)

        return stats

    def get_pdf_figure_count(self, pdf_path: Path) -> int:
        """Get cached figure count for a PDF (fast lookup)."""
        if not self.database:
            return 0
        return self.database.get_figure_count(pdf_path)

    def get_page_figure_ids(self, pdf_path: Path, page_number: int) -> list[str]:
        """Get figure IDs for a specific page (for search result enrichment)."""
        if not self.database:
            return []
        return self.database.get_all_figure_ids_for_page(pdf_path, page_number)
