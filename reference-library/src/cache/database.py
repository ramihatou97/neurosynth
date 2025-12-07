"""SQLite database operations for caching."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import SCHEMA


class Database:
    """SQLite cache for search results and AI categorizations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with WAL mode for concurrent reads."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,  # Wait up to 30 seconds for locks (increased for large libraries)
            check_same_thread=False,
        )
        # Configure SQLite for better concurrency and reliability
        conn.execute(
            "PRAGMA busy_timeout=30000"
        )  # 30 second busy timeout (increased for large libraries)
        conn.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging
        conn.execute("PRAGMA foreign_keys=ON")  # Enforce foreign key constraints
        conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety and speed
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # PDF Text Cache Methods

    def get_file_checksum(self, pdf_path: Path) -> str:
        """Calculate MD5 checksum of entire file for cache invalidation.

        Streams the file in 64KB chunks to handle large PDFs without
        loading them entirely into memory.
        """
        hash_md5 = hashlib.md5()
        with open(pdf_path, "rb") as f:
            # Stream entire file in chunks for complete hash
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def get_fast_checksum(pdf_path: Path) -> str:
        """Fast pseudo-checksum using file size + mtime (no file reading).
        Use this for initial sync. Real checksum computed only when searching."""
        stat = pdf_path.stat()
        # Combine size and mtime for a fast "fingerprint"
        return f"{stat.st_size}_{int(stat.st_mtime)}"

    def get_cached_checksum(self, pdf_path: Path) -> Optional[str]:
        """Get checksum from tracked_files table (fast - no file reading)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT file_checksum FROM tracked_files WHERE pdf_path = ?",
                (str(pdf_path),),
            )
            row = cursor.fetchone()
            return row["file_checksum"] if row else None

    def cache_pdf_text(self, pdf_path: Path, page_num: int, text: str, checksum: str):
        """Cache extracted PDF text."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pdf_text_cache
                (pdf_path, page_number, text_content, file_checksum, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (str(pdf_path), page_num, text, checksum, datetime.now()),
            )
            conn.commit()

    def cache_pdf_text_batch(
        self, pdf_path: Path, pages: dict[int, str], checksum: str
    ):
        """Batch cache all pages of a PDF for efficiency.

        Uses a single transaction instead of one per page, significantly faster
        for PDFs with many pages.

        Args:
            pdf_path: Path to the PDF file
            pages: Dict mapping page_num -> text content
            checksum: File checksum for cache invalidation
        """
        if not pages:
            return

        now = datetime.now()
        path_str = str(pdf_path)

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO pdf_text_cache
                (pdf_path, page_number, text_content, file_checksum, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                [
                    (path_str, page_num, text, checksum, now)
                    for page_num, text in pages.items()
                ],
            )
            conn.commit()

    def get_cached_text(
        self, pdf_path: Path, page_num: int, checksum: str
    ) -> Optional[str]:
        """Retrieve cached text if PDF unchanged."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT text_content FROM pdf_text_cache
                WHERE pdf_path = ? AND page_number = ? AND file_checksum = ?
            """,
                (str(pdf_path), page_num, checksum),
            )
            row = cursor.fetchone()
            return row["text_content"] if row else None

    def get_all_cached_pages(
        self, pdf_path: Path, checksum: str = None
    ) -> dict[int, str]:
        """Get all cached pages for a PDF.

        Args:
            pdf_path: Path to PDF file
            checksum: Optional checksum to match. If None, returns any cached pages for path.
        """
        with self._get_connection() as conn:
            if checksum:
                cursor = conn.execute(
                    """
                    SELECT page_number, text_content FROM pdf_text_cache
                    WHERE pdf_path = ? AND file_checksum = ?
                """,
                    (str(pdf_path), checksum),
                )
            else:
                # Get any cached pages for this path (ignore checksum)
                cursor = conn.execute(
                    """
                    SELECT page_number, text_content FROM pdf_text_cache
                    WHERE pdf_path = ?
                """,
                    (str(pdf_path),),
                )
            return {row["page_number"]: row["text_content"] for row in cursor}

    def has_page_cache_for_library(self, library_path: Path) -> bool:
        """Check if text cache exists for PDFs in the current library.

        Returns True only if at least one tracked file has cached text.
        This prevents using stale cache from a different library.
        """
        with self._get_connection() as conn:
            try:
                # Check if any tracked file has matching text cache
                # tracked_files uses fast checksum, pdf_text_cache uses MD5
                # So we check by path prefix instead
                library_str = str(library_path)
                cursor = conn.execute(
                    """
                    SELECT 1 FROM pdf_text_cache
                    WHERE pdf_path LIKE ?
                    LIMIT 1
                """,
                    (f"{library_str}%",),
                )
                return cursor.fetchone() is not None
            except Exception:
                return False

    def has_page_cache(self) -> bool:
        """Check if any text has been cached (legacy - use has_page_cache_for_library)."""
        with self._get_connection() as conn:
            try:
                cursor = conn.execute("SELECT 1 FROM pdf_text_cache LIMIT 1")
                return cursor.fetchone() is not None
            except Exception:
                return False

    # Categorization Cache Methods

    @staticmethod
    def compute_context_hash(search_term: str, context: str) -> str:
        """Compute hash for categorization cache key."""
        content = f"{search_term.lower()}||{context}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def cache_categorization(
        self,
        context_hash: str,
        search_term: str,
        category_group: str,
        category: str,
        confidence: float,
        reasoning: str,
    ):
        """Cache AI categorization result with hierarchical group support."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO categorization_cache
                (context_hash, search_term, category_group, category, confidence, reasoning, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    context_hash,
                    search_term,
                    category_group,
                    category,
                    confidence,
                    reasoning,
                    datetime.now(),
                ),
            )
            conn.commit()

    def get_cached_categorization(self, context_hash: str) -> Optional[dict]:
        """Retrieve cached categorization if exists."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT category_group, category, confidence, reasoning FROM categorization_cache
                WHERE context_hash = ?
            """,
                (context_hash,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "group": row["category_group"],
                    "category": row["category"],
                    "confidence": row["confidence"],
                    "reasoning": row["reasoning"],
                }
            return None

    def clear_categorization_cache(self):
        """Clear all categorization cache (for migration to new taxonomy)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM categorization_cache")
            conn.commit()
        print("Categorization cache cleared for new taxonomy.")

    # Query Intent Cache Methods

    def cache_query_intent(
        self, query: str, intent: str, confidence: float, reasoning: str
    ):
        """Cache query intent classification result."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO query_intent_cache
                (query, intent, confidence, reasoning, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (query, intent, confidence, reasoning, datetime.now()),
            )
            conn.commit()

    def get_cached_query_intent(self, query: str) -> Optional[dict]:
        """Get cached query intent classification."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT intent, confidence, reasoning FROM query_intent_cache
                WHERE query = ?
            """,
                (query,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "intent": row["intent"],
                    "confidence": row["confidence"],
                    "reasoning": row["reasoning"],
                }
            return None

    def clear_query_intent_cache(self):
        """Clear all query intent cache."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM query_intent_cache")
            conn.commit()
        print("Query intent cache cleared.")

    # Search History Methods

    def save_search_history(
        self,
        query: str,
        result_count: int,
        surgical_count: int = 0,
        theoretical_count: int = 0,
        search_mode: str = "keyword",
    ):
        """Track search history for autocomplete with category information."""
        # Determine dominant category
        total_categorized = surgical_count + theoretical_count
        if total_categorized == 0:
            dominant = None
        elif surgical_count > theoretical_count * 1.5:
            dominant = "Surgical/Anatomical"
        elif theoretical_count > surgical_count * 1.5:
            dominant = "Theoretical"
        else:
            dominant = "Mixed"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_history
                (query, result_count, surgical_count, theoretical_count,
                 dominant_category, search_mode, searched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    query,
                    result_count,
                    surgical_count,
                    theoretical_count,
                    dominant,
                    search_mode,
                    datetime.now(),
                ),
            )
            conn.commit()

    def get_search_suggestions(
        self, prefix: str, limit: int = 10, category_filter: Optional[str] = None
    ) -> list[str]:
        """Return past searches matching prefix, optionally filtered by category."""
        with self._get_connection() as conn:
            if category_filter:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT query FROM search_history
                    WHERE query LIKE ? AND dominant_category = ?
                    ORDER BY searched_at DESC
                    LIMIT ?
                """,
                    (f"{prefix}%", category_filter, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT query FROM search_history
                    WHERE query LIKE ?
                    ORDER BY searched_at DESC
                    LIMIT ?
                """,
                    (f"{prefix}%", limit),
                )
            return [row["query"] for row in cursor]

    def get_recent_searches(self, limit: int = 20) -> list[dict]:
        """Get recent searches with result counts and category information."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT query, result_count, surgical_count, theoretical_count,
                       dominant_category, search_mode, searched_at
                FROM search_history
                ORDER BY searched_at DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor]

    # Library Structure Cache Methods

    def cache_library_structure(
        self,
        pdf_path: Path,
        book_series: str,
        book_title: str,
        chapter_number: Optional[int],
        chapter_title: str,
        file_size: int,
        page_count: int,
        checksum: str,
    ):
        """Cache library structure metadata."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO library_structure
                (pdf_path, book_series, book_title, chapter_number, chapter_title,
                 file_size, page_count, file_checksum, last_scanned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(pdf_path),
                    book_series,
                    book_title,
                    chapter_number,
                    chapter_title,
                    file_size,
                    page_count,
                    checksum,
                    datetime.now(),
                ),
            )
            conn.commit()

    def get_library_structure(self) -> list[dict]:
        """Get all cached library structure."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM library_structure ORDER BY book_series, chapter_number
            """
            )
            return [dict(row) for row in cursor]

    # Statistics

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with self._get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM pdf_text_cache")
            stats["cached_pages"] = cursor.fetchone()["count"]

            cursor = conn.execute("SELECT COUNT(*) as count FROM categorization_cache")
            stats["cached_categorizations"] = cursor.fetchone()["count"]

            cursor = conn.execute("SELECT COUNT(*) as count FROM query_intent_cache")
            stats["cached_query_intents"] = cursor.fetchone()["count"]

            cursor = conn.execute("SELECT COUNT(*) as count FROM search_history")
            stats["total_searches"] = cursor.fetchone()["count"]

            cursor = conn.execute("SELECT COUNT(*) as count FROM library_structure")
            stats["indexed_pdfs"] = cursor.fetchone()["count"]

            return stats

    def clear_cache(self, cache_type: str = "all"):
        """Clear specified cache or all caches."""
        with self._get_connection() as conn:
            if cache_type in ("all", "text"):
                conn.execute("DELETE FROM pdf_text_cache")
            if cache_type in ("all", "categorization"):
                conn.execute("DELETE FROM categorization_cache")
            if cache_type in ("all", "intent"):
                conn.execute("DELETE FROM query_intent_cache")
            if cache_type in ("all", "history"):
                conn.execute("DELETE FROM search_history")
            if cache_type in ("all", "structure"):
                conn.execute("DELETE FROM library_structure")
            conn.commit()

    # File Tracking Methods (for Auto-Update)

    def track_file(
        self,
        pdf_path: Path,
        checksum: str,
        file_size: int,
        book_series: str = "",
        chapter_title: str = "",
        page_count: int = 0,
        is_indexed: bool = False,
    ):
        """Add or update a tracked file."""
        with self._get_connection() as conn:
            # Check if file exists
            cursor = conn.execute(
                "SELECT id, file_checksum FROM tracked_files WHERE pdf_path = ?",
                (str(pdf_path),),
            )
            existing = cursor.fetchone()

            if existing:
                # Update if checksum changed
                if existing["file_checksum"] != checksum:
                    conn.execute(
                        """
                        UPDATE tracked_files
                        SET file_checksum = ?, file_size = ?, last_modified = ?,
                            book_series = ?, chapter_title = ?, page_count = ?
                        WHERE pdf_path = ?
                    """,
                        (
                            checksum,
                            file_size,
                            datetime.now(),
                            book_series,
                            chapter_title,
                            page_count,
                            str(pdf_path),
                        ),
                    )
            else:
                # Insert new file
                conn.execute(
                    """
                    INSERT INTO tracked_files
                    (pdf_path, file_checksum, file_size, book_series, chapter_title, page_count, is_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(pdf_path),
                        checksum,
                        file_size,
                        book_series,
                        chapter_title,
                        page_count,
                        1 if is_indexed else 0,
                    ),
                )
            conn.commit()

    def mark_file_indexed(self, pdf_path: Path):
        """Mark a file as indexed (included in search)."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tracked_files SET is_indexed = 1 WHERE pdf_path = ?",
                (str(pdf_path),),
            )
            conn.commit()

    def get_unindexed_files(self) -> list[dict]:
        """Get all files that haven't been indexed yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT pdf_path, file_checksum, file_size, first_seen,
                       book_series, chapter_title, page_count
                FROM tracked_files
                WHERE is_indexed = 0
                ORDER BY first_seen DESC
            """
            )
            return [dict(row) for row in cursor]

    def get_all_tracked_paths(self) -> set[str]:
        """Get set of all tracked file paths."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT pdf_path FROM tracked_files")
            return {row["pdf_path"] for row in cursor}

    def remove_tracked_file(self, pdf_path: Path):
        """Remove a file from tracking (e.g., if deleted)."""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM tracked_files WHERE pdf_path = ?", (str(pdf_path),)
            )
            conn.commit()

    def clear_tracked_files(self):
        """Clear all tracked files (use when changing library)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM tracked_files")
            conn.commit()

    def get_new_files_count(self) -> int:
        """Get count of unindexed files."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM tracked_files WHERE is_indexed = 0"
            )
            return cursor.fetchone()["count"]

    def track_files_batch(self, files_data: list[dict], is_indexed: bool = False):
        """Batch insert/update tracked files for fast sync."""
        if not files_data:
            return

        with self._get_connection() as conn:
            # Get existing paths in one query
            cursor = conn.execute("SELECT pdf_path, file_checksum FROM tracked_files")
            existing = {row["pdf_path"]: row["file_checksum"] for row in cursor}

            to_insert = []
            to_update = []

            for data in files_data:
                pdf_path = str(data["pdf_path"])
                if pdf_path in existing:
                    if existing[pdf_path] != data["checksum"]:
                        to_update.append(data)
                else:
                    to_insert.append(data)

            # Batch insert new files
            if to_insert:
                conn.executemany(
                    """
                    INSERT INTO tracked_files
                    (pdf_path, file_checksum, file_size, book_series, chapter_title, page_count, is_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        (
                            str(d["pdf_path"]),
                            d["checksum"],
                            d["file_size"],
                            d["book_series"],
                            d["chapter_title"],
                            d["page_count"],
                            1 if is_indexed else 0,
                        )
                        for d in to_insert
                    ],
                )

            # Batch update modified files
            if to_update:
                conn.executemany(
                    """
                    UPDATE tracked_files
                    SET file_checksum = ?, file_size = ?, last_modified = ?,
                        book_series = ?, chapter_title = ?, page_count = ?
                    WHERE pdf_path = ?
                """,
                    [
                        (
                            d["checksum"],
                            d["file_size"],
                            datetime.now(),
                            d["book_series"],
                            d["chapter_title"],
                            d["page_count"],
                            str(d["pdf_path"]),
                        )
                        for d in to_update
                    ],
                )

            conn.commit()

    # Semantic Index Tracking Methods

    def track_semantic_index(self, pdf_path: Path, page_number: int, checksum: str):
        """Mark a page as indexed in the vector store."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_index
                (pdf_path, page_number, file_checksum, indexed_at)
                VALUES (?, ?, ?, ?)
            """,
                (str(pdf_path), page_number, checksum, datetime.now()),
            )
            conn.commit()

    def is_page_indexed_semantically(
        self, pdf_path: Path, page_number: int, checksum: str
    ) -> bool:
        """Check if a page is already indexed with the current checksum."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id FROM semantic_index
                WHERE pdf_path = ? AND page_number = ? AND file_checksum = ?
            """,
                (str(pdf_path), page_number, checksum),
            )
            return cursor.fetchone() is not None

    def get_semantic_indexed_count(self) -> int:
        """Get total number of semantically indexed pages."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM semantic_index")
            return cursor.fetchone()["count"]

    def clear_semantic_index(self):
        """Clear all semantic index tracking (used when rebuilding)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM semantic_index")
            conn.commit()

    # Synthesis History Methods (for tracking NeuroSynth sessions)

    def log_synthesis(
        self,
        topic: str,
        search_query: str,
        search_mode: str,
        sources: list[dict[str, object]],
        template_used: Optional[str] = None,
        output_path: Optional[Path] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        manifest_json: Optional[str] = None,
    ) -> int:
        """
        Log a synthesis session to the history.

        Args:
            topic: Chapter topic
            search_query: Original search query
            search_mode: Search mode (keyword/semantic/hybrid)
            sources: List of source dicts with category_group, etc.
            template_used: Which outline template was used
            output_path: Path to the output file
            success: Whether synthesis succeeded
            error_message: Error message if failed
            manifest_json: Full manifest JSON for reference

        Returns:
            The synthesis ID
        """
        # Count sources by category
        surgical_count = sum(
            1 for s in sources if s.get("category_group") == "Surgical/Anatomical"
        )
        theoretical_count = sum(
            1 for s in sources if s.get("category_group") == "Theoretical"
        )

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO synthesis_history
                (topic, search_query, search_mode, source_count, surgical_count,
                 theoretical_count, template_used, output_path, success,
                 error_message, manifest_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    topic,
                    search_query,
                    search_mode,
                    len(sources),
                    surgical_count,
                    theoretical_count,
                    template_used,
                    str(output_path) if output_path else None,
                    1 if success else 0,
                    error_message,
                    manifest_json,
                    datetime.now(),
                ),
            )
            synthesis_id = cursor.lastrowid

            # Insert source details
            for source in sources:
                conn.execute(
                    """
                    INSERT INTO synthesis_sources
                    (synthesis_id, original_source, pdf_path, category_group,
                     category, pages)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        synthesis_id,
                        source.get("original_source", ""),
                        source.get("original_path", ""),
                        source.get("category_group", ""),
                        source.get("category", ""),
                        json.dumps(source.get("pages", [])),
                    ),
                )

            conn.commit()
            return synthesis_id

    def get_synthesis_history(self, limit: int = 20) -> list[dict]:
        """Get recent synthesis sessions."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, topic, search_query, search_mode, source_count,
                       surgical_count, theoretical_count, template_used,
                       output_path, success, error_message, created_at
                FROM synthesis_history
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor]

    def get_synthesis_detail(self, synthesis_id: int) -> Optional[dict]:
        """Get detailed info about a specific synthesis session."""
        with self._get_connection() as conn:
            # Get main record
            cursor = conn.execute(
                """
                SELECT * FROM synthesis_history WHERE id = ?
            """,
                (synthesis_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            result = dict(row)

            # Get sources
            cursor = conn.execute(
                """
                SELECT original_source, pdf_path, category_group, category, pages
                FROM synthesis_sources
                WHERE synthesis_id = ?
            """,
                (synthesis_id,),
            )
            result["sources"] = [
                {
                    "original_source": r["original_source"],
                    "pdf_path": r["pdf_path"],
                    "category_group": r["category_group"],
                    "category": r["category"],
                    "pages": json.loads(r["pages"]) if r["pages"] else [],
                }
                for r in cursor
            ]

            return result

    def get_synthesis_stats(self) -> dict:
        """Get synthesis statistics."""
        with self._get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM synthesis_history")
            stats["total_syntheses"] = cursor.fetchone()["count"]

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM synthesis_history WHERE success = 1"
            )
            stats["successful_syntheses"] = cursor.fetchone()["count"]

            cursor = conn.execute(
                """
                SELECT SUM(source_count) as total,
                       SUM(surgical_count) as surgical,
                       SUM(theoretical_count) as theoretical
                FROM synthesis_history
            """
            )
            row = cursor.fetchone()
            stats["total_sources_used"] = row["total"] or 0
            stats["surgical_sources_used"] = row["surgical"] or 0
            stats["theoretical_sources_used"] = row["theoretical"] or 0

            # Most common topics
            cursor = conn.execute(
                """
                SELECT topic, COUNT(*) as count
                FROM synthesis_history
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 5
            """
            )
            stats["common_topics"] = [
                {"topic": r["topic"], "count": r["count"]} for r in cursor
            ]

            return stats

    # Visual Elements Cache Methods (for image extraction)

    def cache_visual_element(
        self,
        element_id: str,
        pdf_path: Path,
        page_number: int,
        image_path: Optional[Path],
        checksum: str,
        format: str = "png",
        width: int = 0,
        height: int = 0,
        bbox: Optional[tuple] = None,
        caption: str = "",
        caption_confidence: float = 0.0,
        image_type: str = "unknown",
        type_confidence: float = 0.0,
        context_text: str = "",
        visual_hash: str = "",
    ):
        """Cache an extracted visual element."""
        with self._get_connection() as conn:
            bbox_json = json.dumps(list(bbox)) if bbox else None
            conn.execute(
                """
                INSERT OR REPLACE INTO visual_elements
                (id, pdf_path, page_number, image_path, format, width, height,
                 bbox, caption, caption_confidence, image_type, type_confidence,
                 context_text, visual_hash, file_checksum, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    element_id,
                    str(pdf_path),
                    page_number,
                    str(image_path) if image_path else None,
                    format,
                    width,
                    height,
                    bbox_json,
                    caption,
                    caption_confidence,
                    image_type,
                    type_confidence,
                    context_text[:500],  # Truncate context
                    visual_hash,
                    checksum,
                    datetime.now(),
                ),
            )
            conn.commit()

    def cache_visual_elements_batch(
        self, elements: list[dict], checksum: str, pdf_path: Path | None = None
    ):
        """Batch cache visual elements for efficiency."""
        with self._get_connection() as conn:
            if not elements and pdf_path:
                # Insert marker row for "0 figures extracted"
                # This ensures we don't re-extract PDFs with no figures
                conn.execute(
                    """
                    INSERT OR REPLACE INTO visual_elements
                    (id, pdf_path, page_number, format, caption, file_checksum, extracted_at)
                    VALUES (?, ?, 0, 'marker', 'ZERO_FIGURES', ?, ?)
                """,
                    (
                        f"{pdf_path.stem}_ZERO_FIGURES",
                        str(pdf_path),
                        checksum,
                        datetime.now(),
                    ),
                )
                conn.commit()
                return
            elif not elements:
                # No elements and no pdf_path - nothing to cache
                return

            rows = []
            for e in elements:
                bbox_json = (
                    json.dumps(list(e.get("bbox", []))) if e.get("bbox") else None
                )
                rows.append(
                    (
                        e.get("id", ""),
                        str(e.get("pdf_path", "")),
                        e.get("page_number", 0),
                        str(e.get("image_path")) if e.get("image_path") else None,
                        e.get("format", "png"),
                        e.get("width", 0),
                        e.get("height", 0),
                        bbox_json,
                        e.get("caption", ""),
                        e.get("caption_confidence", 0.0),
                        e.get("image_type", "unknown"),
                        e.get("type_confidence", 0.0),
                        (e.get("context_text", "") or "")[:500],
                        e.get("visual_hash", ""),
                        checksum,
                        datetime.now(),
                    )
                )

            conn.executemany(
                """
                INSERT OR REPLACE INTO visual_elements
                (id, pdf_path, page_number, image_path, format, width, height,
                 bbox, caption, caption_confidence, image_type, type_confidence,
                 context_text, visual_hash, file_checksum, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                rows,
            )
            conn.commit()

    def get_pdf_figures(
        self, pdf_path: Path, checksum: Optional[str] = None
    ) -> list[dict]:
        """Get all cached figures for a PDF.

        Args:
            pdf_path: Path to the PDF
            checksum: If provided, only return figures with matching checksum

        Returns:
            List of figure dictionaries
        """
        with self._get_connection() as conn:
            if checksum:
                cursor = conn.execute(
                    """
                    SELECT * FROM visual_elements
                    WHERE pdf_path = ? AND file_checksum = ?
                    ORDER BY page_number, id
                """,
                    (str(pdf_path), checksum),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM visual_elements
                    WHERE pdf_path = ?
                    ORDER BY page_number, id
                """,
                    (str(pdf_path),),
                )

            figures = []
            for row in cursor:
                fig = dict(row)
                # Parse bbox JSON
                if fig.get("bbox"):
                    try:
                        fig["bbox"] = tuple(json.loads(fig["bbox"]))
                    except (json.JSONDecodeError, TypeError):
                        fig["bbox"] = None
                figures.append(fig)
            return figures

    def get_page_figures(
        self, pdf_path: Path, page_number: int, checksum: Optional[str] = None
    ) -> list[dict]:
        """Get all figures for a specific page."""
        with self._get_connection() as conn:
            if checksum:
                cursor = conn.execute(
                    """
                    SELECT * FROM visual_elements
                    WHERE pdf_path = ? AND page_number = ? AND file_checksum = ?
                    ORDER BY id
                """,
                    (str(pdf_path), page_number, checksum),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM visual_elements
                    WHERE pdf_path = ? AND page_number = ?
                    ORDER BY id
                """,
                    (str(pdf_path), page_number),
                )

            figures = []
            for row in cursor:
                fig = dict(row)
                if fig.get("bbox"):
                    try:
                        fig["bbox"] = tuple(json.loads(fig["bbox"]))
                    except (json.JSONDecodeError, TypeError):
                        fig["bbox"] = None
                figures.append(fig)
            return figures

    def get_figure_by_id(self, element_id: str) -> Optional[dict]:
        """Get a specific figure by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM visual_elements WHERE id = ?", (element_id,)
            )
            row = cursor.fetchone()
            if row:
                fig = dict(row)
                if fig.get("bbox"):
                    try:
                        fig["bbox"] = tuple(json.loads(fig["bbox"]))
                    except (json.JSONDecodeError, TypeError):
                        fig["bbox"] = None
                return fig
            return None

    def get_figure_count(self, pdf_path: Path, checksum: Optional[str] = None) -> int:
        """Get count of figures for a PDF."""
        with self._get_connection() as conn:
            if checksum:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM visual_elements
                    WHERE pdf_path = ? AND file_checksum = ?
                """,
                    (str(pdf_path), checksum),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM visual_elements
                    WHERE pdf_path = ?
                """,
                    (str(pdf_path),),
                )
            return cursor.fetchone()["count"]

    def get_page_figure_count(self, pdf_path: Path, page_number: int) -> int:
        """Get count of figures for a specific page of a PDF."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count FROM visual_elements
                WHERE pdf_path = ? AND page_number = ?
            """,
                (str(pdf_path), page_number),
            )
            return cursor.fetchone()["count"]

    def is_pdf_figures_extracted(self, pdf_path: Path, checksum: str) -> bool:
        """Check if figures have been extracted for this PDF with current checksum."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count FROM visual_elements
                WHERE pdf_path = ? AND file_checksum = ?
            """,
                (str(pdf_path), checksum),
            )
            # Consider extracted if any figures exist (including PDFs with 0 figures)
            # Use a marker table entry or check for specific flag
            return cursor.fetchone()["count"] > 0

    def get_all_figure_ids_for_page(
        self, pdf_path: Path, page_number: int
    ) -> list[str]:
        """Get all figure IDs for a specific page (for search results)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id FROM visual_elements
                WHERE pdf_path = ? AND page_number = ?
            """,
                (str(pdf_path), page_number),
            )
            return [row["id"] for row in cursor]

    def get_visual_stats(self) -> dict:
        """Get visual extraction statistics."""
        with self._get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM visual_elements")
            stats["total_figures"] = cursor.fetchone()["count"]

            cursor = conn.execute(
                "SELECT COUNT(DISTINCT pdf_path) as count FROM visual_elements"
            )
            stats["pdfs_with_figures"] = cursor.fetchone()["count"]

            # Count by type
            cursor = conn.execute(
                """
                SELECT image_type, COUNT(*) as count
                FROM visual_elements
                GROUP BY image_type
            """
            )
            stats["by_type"] = {row["image_type"]: row["count"] for row in cursor}

            # Count by source (top 5)
            cursor = conn.execute(
                """
                SELECT pdf_path, COUNT(*) as count
                FROM visual_elements
                GROUP BY pdf_path
                ORDER BY count DESC
                LIMIT 5
            """
            )
            stats["top_sources"] = [
                {"pdf_path": row["pdf_path"], "count": row["count"]} for row in cursor
            ]

            return stats

    def clear_visual_cache(self, pdf_path: Optional[Path] = None):
        """Clear visual cache, optionally for a specific PDF."""
        with self._get_connection() as conn:
            if pdf_path:
                conn.execute(
                    "DELETE FROM visual_elements WHERE pdf_path = ?", (str(pdf_path),)
                )
                conn.execute(
                    """DELETE FROM visual_embeddings
                       WHERE element_id IN (
                           SELECT id FROM visual_elements WHERE pdf_path = ?
                       )""",
                    (str(pdf_path),),
                )
            else:
                conn.execute("DELETE FROM visual_elements")
                conn.execute("DELETE FROM visual_embeddings")
            conn.commit()

    # Visual Embedding Tracking Methods

    def track_visual_embedding(
        self, element_id: str, qdrant_point_id: str, embedding_model: str
    ):
        """Track that a visual element has been embedded in Qdrant."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO visual_embeddings
                (element_id, qdrant_point_id, embedding_model, indexed_at)
                VALUES (?, ?, ?, ?)
            """,
                (element_id, qdrant_point_id, embedding_model, datetime.now()),
            )
            conn.commit()

    def is_figure_embedded(self, element_id: str) -> bool:
        """Check if a figure has been embedded."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM visual_embeddings WHERE element_id = ?", (element_id,)
            )
            return cursor.fetchone() is not None

    def get_unembedded_figures(self, limit: int = 100) -> list[dict]:
        """Get figures that haven't been embedded yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT v.* FROM visual_elements v
                LEFT JOIN visual_embeddings e ON v.id = e.element_id
                WHERE e.id IS NULL
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor]

    def get_embedded_count(self) -> int:
        """Get count of embedded figures."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM visual_embeddings")
            return cursor.fetchone()["count"]

    def get_all_figures_with_captions(self) -> list[dict]:
        """Get all figures that have captions for indexing.

        Returns:
            List of figure dicts with id, caption, pdf_path, page_number, image_type
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, caption, pdf_path, page_number, image_type
                FROM visual_elements
                WHERE caption IS NOT NULL AND caption != ''
            """
            )
            return [dict(row) for row in cursor]
