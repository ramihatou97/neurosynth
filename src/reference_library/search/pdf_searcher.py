"""PDF text extraction and search engine with semantic search support."""
import os
import re
from pathlib import Path
from typing import Generator, Optional, Callable, Dict, List, Tuple, TYPE_CHECKING
import fitz  # PyMuPDF

if TYPE_CHECKING:
    from reference_library.search.study_package.report import StudyModeReport

from .result_model import (
    SearchResult, PageMatch, SearchProgress, ChapterMetadata,
    MatchLocation, MatchType, ChapterResult
)
from .semantic_searcher import SemanticSearcher
from .neurosurgical_synonyms import expand_query, get_all_terms_for_query
from ..cache.database import Database
from ..utils.library_scanner import LibraryScanner
from reference_library import config
from .master_index import get_master_index
from .query_intent_lean import get_intent_detector, QueryIntent
from .section_detector import get_section_detector, MatchConfidence
from .search_strategy import SearchStrategy, STRATEGIES, get_strategy
from .intent_classifier import get_hybrid_classifier, HybridIntentClassifier
from ..logger import get_logger

# Prevent tokenizers deadlock when forking
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Module logger
logger = get_logger("search.pdf_searcher")

# Patterns for detecting document structure
SECTION_HEADER_PATTERNS = [
    # Numbered sections: "1. Introduction", "2.1 Methods", "III. Results"
    r'^(?:\d+\.)+\s+[A-Z]',
    r'^[IVX]+\.\s+[A-Z]',
    # All-caps headers: "INTRODUCTION", "METHODS"
    r'^[A-Z][A-Z\s]{4,}$',
    # Bold-style headers (often extracted with special chars)
    r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}\s*$',
]

FOOTNOTE_PATTERNS = [
    # Numbered references: "1.", "23.", "[1]", "(1)"
    r'^\s*\[\d+\]',
    r'^\s*\(\d+\)',
    r'^\s*\d+\.\s+[A-Z][a-z]+\s+[A-Z]',  # "1. Author Name..."
    # Reference section markers
    r'(?i)^references?\s*$',
    r'(?i)^bibliography\s*$',
    r'(?i)^notes?\s*$',
]


class PDFSearcher:
    """On-demand PDF text search using PyMuPDF with optional semantic search."""

    def __init__(self, library_path: Path, database: Database, enable_query_expansion: bool = True):
        self.library_path = library_path.resolve()
        self.database = database
        self.scanner = LibraryScanner(library_path, database)
        self._semantic: Optional[SemanticSearcher] = None  # Lazy-loaded
        self.enable_query_expansion = enable_query_expansion
        self._cancelled = False

        # Enhanced Search Components (lazy-loaded for fast startup)
        self._master_index = None
        self._intent_detector = None
        self._section_detector = None

        # Active search strategy (set per-search for strategy-aware behavior)
        self._active_strategy: Optional[SearchStrategy] = None

        # Study Mode report (populated after BROAD mode search)
        self._last_study_report: Optional['StudyModeReport'] = None

    @property
    def semantic(self) -> SemanticSearcher:
        """Lazy-load semantic searcher (heavy - loads embedding model)."""
        if self._semantic is None:
            self._semantic = SemanticSearcher(self.database)
        return self._semantic

    @property
    def master_index(self):
        """Lazy-load master index."""
        if self._master_index is None:
            self._master_index = get_master_index()
        return self._master_index

    @property
    def intent_detector(self):
        """Lazy-load intent detector."""
        if self._intent_detector is None:
            self._intent_detector = get_intent_detector()
        return self._intent_detector

    @property
    def section_detector(self):
        """Lazy-load section detector."""
        if self._section_detector is None:
            self._section_detector = get_section_detector()
        return self._section_detector

    def _should_expand_query(self) -> bool:
        """
        Determine if query expansion should be used.

        Priority:
        1. If active strategy is set, use strategy's expansion settings
        2. Otherwise fall back to instance's enable_query_expansion setting

        This ensures STRICT mode disables expansion even when instance default is True.
        """
        if self._active_strategy is not None:
            return self._active_strategy.expand_synonyms or self._active_strategy.expand_orthographic
        return self.enable_query_expansion

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
        progress_callback: Optional[Callable[[SearchProgress], None]] = None,
        category_filter: Optional[str] = None
    ) -> Generator[SearchResult, None, None]:
        """
        Search entire library for query with page-level deduplication.

        Results are yielded in order of relevance:
        1. Chapter title matches (topic is the main subject)
        2. Section header matches (topic discussed in dedicated section)
        3. Body text matches (topic mentioned in context)
        4. Footnote matches (topic referenced)

        Args:
            query: Search term
            mode: "keyword", "semantic", or "hybrid"
            progress_callback: Optional callback for progress updates
            category_filter: Optional filter for semantic search

        Yields:
            SearchResult objects (one per page, aggregated and sorted by relevance)
        """
        self.reset()

        # Collect all results for sorting by relevance
        all_results: list[SearchResult] = []
        seen_pages: set[str] = set()

        # 1. Semantic Search Phase (instant, ranked by similarity)
        if mode in ["semantic", "hybrid"] and self.semantic.enabled:
            semantic_hits = self.semantic.search(
                query, n_results=30, category_filter=category_filter
            )

            if progress_callback:
                semantic_progress = SearchProgress(total_pdfs=0, searched_pdfs=0, total_matches=0)
                semantic_progress.current_file = "Semantic search..."
                progress_callback(semantic_progress)

            for i, hit in enumerate(semantic_hits):
                if self._cancelled:
                    break

                try:
                    page_key = f"{hit['pdf_path']}:{hit['page_number']}"
                    if page_key in seen_pages:
                        continue
                    seen_pages.add(page_key)

                    metadata = self.scanner.get_pdf_metadata(hit["pdf_path"])
                    checksum = self.database.get_file_checksum(hit["pdf_path"])
                    cached_text = self.database.get_cached_text(
                        hit["pdf_path"], hit["page_number"] - 1, checksum
                    )
                    context = self._extract_context_from_text(cached_text or "", query)

                    # Check if title matches
                    is_title = self._check_title_match(query, metadata.chapter_title)

                    result = SearchResult(
                        pdf_path=hit["pdf_path"],
                        book_series=metadata.book_series,
                        book_title=metadata.book_title,
                        chapter_number=metadata.chapter_number,
                        chapter_title=metadata.chapter_title,
                        page_number=hit["page_number"],
                        match_text=f"[Semantic: {hit['score']:.0%}]",
                        context=context,
                        match_count=1,
                        match_locations=[MatchLocation.SEMANTIC],
                        is_title_match=is_title,
                        relevance_score=MatchLocation.SEMANTIC.relevance_score + (30 if is_title else 0)
                    )
                    all_results.append(result)

                    if progress_callback:
                        semantic_progress.total_matches = len(all_results)
                        progress_callback(semantic_progress)

                except Exception as e:
                    logger.warning("Error processing semantic hit: %s: %s", type(e).__name__, e)

            if mode == "semantic":
                # Sort and yield semantic results
                all_results.sort(key=lambda r: r.relevance_score, reverse=True)
                for result in all_results:
                    yield result
                return

        # 2. Keyword Search Phase with page aggregation
        if mode in ["keyword", "hybrid"]:
            all_pdfs = self.scanner.get_all_pdfs()
            total_pdfs = len(all_pdfs)
            progress = SearchProgress(total_pdfs=total_pdfs)

            logger.debug("Starting keyword search across %d PDFs", total_pdfs)

            for idx, pdf_path in enumerate(all_pdfs):
                if self._cancelled:
                    break

                progress.current_file = pdf_path.name
                if progress_callback:
                    progress_callback(progress)

                if idx % 100 == 0:
                    logger.debug("Processing PDF %d/%d: %s", idx, total_pdfs, pdf_path.name)

                try:
                    metadata = self.scanner.get_pdf_metadata(pdf_path)

                    # Use aggregated search (one result per page)
                    page_results = self.search_pdf_aggregated(
                        query, pdf_path, metadata.chapter_title
                    )

                    if idx % 100 == 0 and page_results:
                        logger.debug("  Found %d pages with matches", len(page_results))

                    for page_num, page_data in page_results.items():
                        if self._cancelled:
                            break

                        page_key = f"{pdf_path}:{page_num}"
                        if mode == "hybrid" and page_key in seen_pages:
                            continue
                        seen_pages.add(page_key)

                        result = SearchResult(
                            pdf_path=pdf_path,
                            book_series=metadata.book_series,
                            book_title=metadata.book_title,
                            chapter_number=metadata.chapter_number,
                            chapter_title=metadata.chapter_title,
                            page_number=page_num,
                            match_text=page_data['best_match_text'],
                            context=page_data['best_context'],
                            match_count=page_data['match_count'],
                            match_locations=page_data['locations'],
                            is_title_match=page_data['is_title_match'],
                        )
                        all_results.append(result)
                        progress.total_matches = len(all_results)

                except Exception as e:
                    logger.error("Error at PDF %d: %s: %s", idx, type(e).__name__, e)

                progress.searched_pdfs += 1
                if progress_callback:
                    progress_callback(progress)

        # Sort all results by relevance score (highest first)
        all_results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Log search statistics
        unique_series = set(r.book_series for r in all_results)
        logger.debug("Yielding %d results sorted by relevance", len(all_results))
        logger.debug("Found in %d book series: %s", len(unique_series), unique_series)

        # Yield sorted results
        for result in all_results:
            if self._cancelled:
                break
            yield result

    def search_library_chapters(
        self,
        query: str,
        strategy: str = "standard",
        progress_callback: Optional[Callable[[SearchProgress], None]] = None,
        skip_study_mode: bool = False,
    ) -> Generator[ChapterResult, None, None]:
        """
        Knowledge retrieval search - returns chapter-level results.

        Enhanced with:
        1. Intent Detection (Technique vs Complication vs Anatomy)
        2. Master Index Lookup (Authority Boosting)
        3. Robust Section Detection (Zero Data Loss)
        4. Search Strategy (STRICT/STANDARD/BROAD)
        5. Study Mode (BROAD only) - adds foundational knowledge

        Args:
            query: Search query string
            strategy: Search strategy ('strict', 'standard', 'broad')
            progress_callback: Optional callback for progress updates
            skip_study_mode: If True, skip Study Mode enhancement (used internally)
        """
        self.reset()
        logger.info("Starting search for: '%s' with strategy: %s", query, strategy)

        # Load strategy configuration and store for strategy-aware methods
        strat = get_strategy(strategy)
        self._active_strategy = strat  # FIX 0.2: Store for _should_expand_query() and _check_title_match()

        # 1. Detect Intent (using hybrid classifier if AI enabled)
        if strat.use_intent_detection:
            hybrid_classifier = get_hybrid_classifier()
            hybrid_result = hybrid_classifier.classify(
                query,
                use_ai=strat.use_ai_intent,
                confidence_threshold=strat.intent_confidence_threshold
            )
            intent_result = self.intent_detector.detect(query)  # Still use lean for sections
            logger.debug("Intent: %s (source: %s, confidence: %.2f)",
                        hybrid_result.intent.name, hybrid_result.source, hybrid_result.confidence)
        else:
            intent_result = self.intent_detector.detect(query)
            logger.debug("Intent detection disabled (STRICT mode)")

        # 2. Master Index Lookup
        index_matches = self.master_index.find_term(intent_result.cleaned_query)
        primary_sources = set()
        if index_matches:
            top_match = index_matches[0]
            primary_sources = set(top_match.primary_sources)
            logger.debug("Master Index Match: '%s' (Auth: %d)", top_match.term, top_match.authority)

        # 3. STRATEGY: Query Expansion (STANDARD/BROAD only)
        search_terms = [intent_result.cleaned_query]
        if strat.expand_synonyms or strat.expand_orthographic:
            expanded = self.master_index.expand_query(
                intent_result.cleaned_query,
                expand_synonyms=strat.expand_synonyms,
                expand_orthographic=strat.expand_orthographic,
                max_expansions=strat.max_expansions
            )
            search_terms = expanded
            if len(expanded) > 1:
                logger.debug("Query expansion: %s -> %s", intent_result.cleaned_query, expanded)

        # Collect chapter-level results
        chapter_results: dict[str, ChapterResult] = {}  # pdf_path -> ChapterResult

        all_pdfs = self.scanner.get_all_pdfs()
        total_pdfs = len(all_pdfs)
        progress = SearchProgress(total_pdfs=total_pdfs)

        # FAST MODE: Check if text cache exists FOR THIS LIBRARY - if not, use title-only search
        has_text_cache = self.database.has_page_cache_for_library(self.library_path)
        if not has_text_cache:
            logger.info("FAST MODE: No text cache for current library - using title-only search")

        logger.debug("Knowledge search across %d PDFs for: '%s'", total_pdfs, query)

        for idx, pdf_path in enumerate(all_pdfs):
            if self._cancelled:
                logger.info("Search cancelled at PDF %d/%d", idx, total_pdfs)
                break

            progress.current_file = pdf_path.name
            progress.searched_pdfs = idx + 1
            if progress_callback:
                progress_callback(progress)

            try:
                # FAST: Skip page count lookup during search loop
                metadata = self.scanner.get_pdf_metadata(pdf_path, fast=True)

                # Get Authority Boost (from master index, no extraction needed)
                authority_boost = self.master_index.get_authority_boost(pdf_path)

                # Check if ANY search term matches chapter title (= DEDICATED CHAPTER)
                # With query expansion, we check all expanded terms
                is_dedicated = any(
                    self._check_title_match(term, metadata.chapter_title)
                    for term in search_terms
                )

                # FAST MODE: Only return title matches when no text cache
                if not has_text_cache:
                    if is_dedicated:
                        chapter_result = ChapterResult(
                            pdf_path=pdf_path,
                            book_series=metadata.book_series,
                            book_title=metadata.book_title,
                            chapter_number=metadata.chapter_number,
                            chapter_title=metadata.chapter_title,
                            match_type=MatchType.DEDICATED_CHAPTER,
                            page_count=0,  # Unknown without extraction
                            matched_pages=[],
                            preview_context="",
                            total_occurrences=0,
                            matched_sections=[],
                            authority_score=authority_boost,
                            index_source="Title Match (Fast)",
                            authority_weight=strat.authority_boost_weight,
                            section_weight=strat.section_boost_weight
                        )
                        chapter_results[str(pdf_path)] = chapter_result
                        progress.total_matches += 1
                    continue  # Skip text extraction in fast mode

                # FULL MODE: Has text cache, do complete search
                is_primary_source = metadata.book_series in primary_sources

                # PERFORMANCE: Skip non-matches early (before expensive operations)
                if not is_dedicated and not is_primary_source:
                    continue  # Skip - not a title match and not a primary source

                # This PDF is a candidate - track it
                progress.candidates_processed += 1

                # FAST: Use cached checksum from tracked_files (no file reading)
                checksum = self.database.get_cached_checksum(pdf_path)
                if not checksum:
                    # Fallback: compute checksum (slow but necessary for untracked files)
                    checksum = self.database.get_file_checksum(pdf_path)

                # Update progress with candidate info
                if progress_callback:
                    progress_callback(progress)

                # Log candidates being processed
                logger.debug("Candidate PDF %d: %s (dedicated=%s, primary=%s, auth=%d)",
                            idx, pdf_path.name, is_dedicated, is_primary_source, authority_boost)

                if is_dedicated:
                    # DEDICATED CHAPTER - include ALL pages
                    # PERFORMANCE: Skip expensive text extraction - just use title match
                    # Get page count from cache only (fast) or use default
                    cached_pages = self.database.get_all_cached_pages(pdf_path)
                    if cached_pages:
                        page_count = max(cached_pages.keys()) + 1
                        preview_context = next(iter(cached_pages.values()), "")[:200]
                    else:
                        page_count = 1  # Default - will be updated when opened
                        preview_context = f"Dedicated chapter on {intent_result.cleaned_query}"

                    chapter_result = ChapterResult(
                        pdf_path=pdf_path,
                        book_series=metadata.book_series,
                        book_title=metadata.book_title,
                        chapter_number=metadata.chapter_number,
                        chapter_title=metadata.chapter_title,
                        match_type=MatchType.DEDICATED_CHAPTER,
                        page_count=page_count,
                        matched_pages=list(range(1, page_count + 1)),  # All pages
                        preview_context=preview_context,
                        total_occurrences=1,  # Skip counting - expensive
                        matched_sections=[],  # Skip section detection - expensive
                        authority_score=authority_boost,
                        index_source="Title Match",
                        # Strategy weights for scoring
                        authority_weight=strat.authority_boost_weight,
                        section_weight=strat.section_boost_weight
                    )
                    chapter_results[str(pdf_path)] = chapter_result
                    progress.total_matches += 1

                else:
                    # Not a dedicated chapter - check for section matches or references
                    # PERFORMANCE: For non-dedicated chapters, only do quick title check first
                    # Skip expensive page-by-page search unless it's a primary source
                    if not is_primary_source:
                        # Non-primary source + not dedicated = skip entirely
                        continue

                    # PERFORMANCE: Limit section/reference search to avoid freezing
                    # Only search if we haven't found too many candidates already
                    if len(chapter_results) >= strat.max_results * 2:
                        # Already have enough candidates, skip further searching
                        continue

                    # Search using all expanded terms (STRATEGY: Query Expansion)
                    page_matches = {}
                    for term in search_terms:
                        term_matches = self.search_pdf_aggregated(term, pdf_path, metadata.chapter_title)
                        # Merge matches (avoid duplicates)
                        for page_num, page_data in term_matches.items():
                            if page_num not in page_matches:
                                page_matches[page_num] = page_data
                            else:
                                # Merge match counts and locations
                                page_matches[page_num]['match_count'] += page_data['match_count']
                                page_matches[page_num]['locations'].extend(page_data['locations'])

                    if page_matches:
                        # Analyze sections on matched pages
                        matched_sections = []
                        matched_pages_set = set()
                        
                        # Get all cached text for section detection
                        cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)
                        
                        # Identify pages with matches
                        pages_with_hits = sorted(page_matches.keys())
                        
                        # Run section detector on pages with hits
                        for page_num in pages_with_hits:
                            text = cached_pages.get(page_num - 1, "")
                            if not text:
                                # print(f"[DEBUG] No text for page {page_num} in {pdf_path.name}")
                                continue
                                
                            sections = self.section_detector.detect_section_headers(text, page_num)
                            
                            # Filter sections by intent
                            for section in sections:
                                # Check if section type matches intent
                                # e.g. Intent=TECHNIQUE, Section="Technique"
                                if section.section_type.upper() == intent_result.intent.name:
                                    matched_sections.append(section)
                                    
                                    # Get safe extraction window (Zero Data Loss)
                                    # We need all sections on page to calculate window
                                    start, end = self.section_detector.get_safe_extraction_window(
                                        section, sections, page_count
                                    )
                                    # Add pages to set
                                    for p in range(start, end + 1):
                                        if 1 <= p <= page_count:
                                            matched_pages_set.add(p)

                        # Determine Match Type
                        if matched_sections:
                            match_type = MatchType.RELATED_SECTION
                            final_matched_pages = sorted(list(matched_pages_set))
                        else:
                            match_type = MatchType.REFERENCE
                            # Fallback: just use pages with keyword hits
                            # Or apply fallback window around best hit?
                            # For REFERENCE, usually just the page is enough, 
                            # but let's add context window (-1, +1)
                            for p in pages_with_hits:
                                matched_pages_set.add(p)
                                if p > 1: matched_pages_set.add(p - 1)
                                if p < page_count: matched_pages_set.add(p + 1)
                            final_matched_pages = sorted(list(matched_pages_set))

                        # Get best context for preview
                        best_context = ""
                        best_score = 0
                        for page_data in page_matches.values():
                            for loc in page_data['locations']:
                                if loc.relevance_score > best_score:
                                    best_score = loc.relevance_score
                                    best_context = page_data['best_context']

                        total_occurrences = sum(p['match_count'] for p in page_matches.values())

                        chapter_result = ChapterResult(
                            pdf_path=pdf_path,
                            book_series=metadata.book_series,
                            book_title=metadata.book_title,
                            chapter_number=metadata.chapter_number,
                            chapter_title=metadata.chapter_title,
                            match_type=match_type,
                            page_count=page_count,
                            matched_pages=final_matched_pages,
                            preview_context=best_context,
                            total_occurrences=total_occurrences,
                            matched_sections=matched_sections,
                            authority_score=authority_boost,
                            index_source="Master Index" if authority_boost > 70 else "",
                            # Strategy weights for scoring
                            authority_weight=strat.authority_boost_weight,
                            section_weight=strat.section_boost_weight
                        )
                        chapter_results[str(pdf_path)] = chapter_result
                        progress.total_matches += 1

            except Exception as e:
                logger.error("Error at PDF %d: %s: %s", idx, type(e).__name__, e)

        # Mark search complete and send final progress
        progress.phase = "complete"
        if progress_callback:
            progress_callback(progress)

        # Log search statistics
        logger.info("Scanned %d PDFs, processed %d candidates, found %d matches",
                    total_pdfs, progress.candidates_processed, progress.total_matches)

        # Sort by relevance (DEDICATED first, then SECTION, then REFERENCE)
        sorted_results = sorted(
            chapter_results.values(),
            key=lambda r: r.relevance_score,
            reverse=True
        )

        # STRATEGY: Apply min_relevance_score filter
        if strat.min_relevance_score > 0:
            filtered_results = [r for r in sorted_results if r.relevance_score >= strat.min_relevance_score]
            logger.debug("Score filter: %d -> %d results (min=%.1f)",
                        len(sorted_results), len(filtered_results), strat.min_relevance_score)
            sorted_results = filtered_results

        # STRATEGY: Apply max_results limit
        if strat.max_results > 0 and len(sorted_results) > strat.max_results:
            logger.debug("Result limit: %d -> %d results (max=%d)",
                        len(sorted_results), strat.max_results, strat.max_results)
            sorted_results = sorted_results[:strat.max_results]

        # Update progress with final filtered count
        progress.total_matches = len(sorted_results)
        if progress_callback:
            progress_callback(progress)

        # Log detailed breakdown
        dedicated = sum(1 for r in sorted_results if r.match_type == MatchType.DEDICATED_CHAPTER)
        sections = sum(1 for r in sorted_results if r.match_type == MatchType.RELATED_SECTION)
        refs = sum(1 for r in sorted_results if r.match_type == MatchType.REFERENCE)
        unique_series = set(r.book_series for r in sorted_results)

        logger.info("Strategy '%s': %d results (dedicated=%d, sections=%d, refs=%d) from %d series",
                    strat.name, len(sorted_results), dedicated, sections, refs, len(unique_series))

        # =====================================================================
        # STUDY MODE ENHANCEMENT (BROAD mode only)
        # =====================================================================
        # For BROAD mode, enhance results with foundational knowledge chapters
        # (anatomy, biomechanics, pathophysiology) based on detected region.
        # This is skipped when called recursively from foundation searches.
        # =====================================================================
        if strategy.lower() == "broad" and not skip_study_mode:
            try:
                from reference_library.search.study_package import enhance_broad_results

                enhanced_results, study_report = enhance_broad_results(
                    searcher=self,
                    query=query,
                    direct_results=sorted_results,
                    semantic_results=None,  # TODO: Add semantic results when available
                    max_foundational=15,
                )

                # Log study mode results
                foundational_count = sum(
                    1 for r in enhanced_results
                    if r.match_type == MatchType.FOUNDATIONAL
                )
                logger.info(
                    "Study Mode: added %d foundational chapters (region=%s, gaps=%d)",
                    foundational_count,
                    study_report.detected_region or "unknown",
                    len(study_report.missing_topics),
                )

                # Store report for potential UI access
                self._last_study_report = study_report

                # Use enhanced results
                sorted_results = enhanced_results

            except ImportError as e:
                logger.warning("Study Mode unavailable: %s", e)
            except Exception as e:
                logger.error("Study Mode failed: %s", e)
                # Continue with original results on error

        for result in sorted_results:
            if self._cancelled:
                break
            yield result


    def _get_pdf_page_count(self, pdf_path: Path, checksum: str = None) -> int:
        """Get total page count for a PDF from cache or by opening file."""
        # Try cache first (ignore checksum for speed - path is unique enough)
        cached_pages = self.database.get_all_cached_pages(pdf_path)
        if cached_pages:
            return len(cached_pages)
        # Fallback: open PDF to get page count
        try:
            with fitz.open(pdf_path) as doc:
                return len(doc)
        except Exception:
            return 0

    def _get_chapter_preview(self, pdf_path: Path, query: str, checksum: str) -> str:
        """Get preview context from the first page containing the query."""
        cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)
        if not cached_pages:
            return ""

        for page_num in sorted(cached_pages.keys()):
            text = cached_pages[page_num]
            matches = self._find_matches_with_location(query, text, page_num + 1, page_num == 0)
            if matches:
                return matches[0].context
        return ""

    def _count_occurrences(self, pdf_path: Path, query: str, checksum: str) -> int:
        """Count total occurrences of query across all pages."""
        cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)
        if not cached_pages:
            return 0

        count = 0
        query_variations = [query]
        # FIX 0.4a: Use strategy-aware expansion check
        if self._should_expand_query():
            query_variations = expand_query(query, max_expansions=5)

        for text in cached_pages.values():
            for variant in query_variations:
                count += len(re.findall(re.escape(variant), text, re.IGNORECASE))
        return count

    def _ensure_text_extracted(self, pdf_path: Path, checksum: str) -> dict[int, str]:
        """Get text from cache or extract and cache it."""
        cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)
        if cached_pages:
            return cached_pages

        # Extract and cache with timeout protection
        pages = {}
        try:
            logger.debug("Extracting text from %s", pdf_path.name)
            doc = fitz.open(pdf_path)
            try:
                page_count = len(doc)
                for i in range(page_count):
                    if self._cancelled:
                        logger.debug("Extraction cancelled at page %d of %s", i, pdf_path.name)
                        break
                    try:
                        page = doc[i]
                        text = page.get_text()
                        if text.strip():
                            pages[i] = text
                    except Exception as page_err:
                        logger.warning("Error extracting page %d from %s: %s", i, pdf_path.name, page_err)
                        continue
            finally:
                doc.close()

            # Batch cache
            if pages:
                self.database.cache_pdf_text_batch(pdf_path, pages, checksum)
                logger.debug("Cached %d pages from %s", len(pages), pdf_path.name)

        except Exception as e:
            logger.error("Failed to extract text from %s: %s", pdf_path.name, e)

        return pages

    def search_pdf_aggregated(
        self, query: str, pdf_path: Path, chapter_title: str = ""
    ) -> dict[int, dict]:
        """
        Search a PDF and aggregate matches by page with location detection.

        Returns:
            Dict mapping page_number to aggregated match info:
            {
                page_num: {
                    'matches': [PageMatch, ...],
                    'locations': [MatchLocation, ...],
                    'best_context': str,
                    'match_count': int,
                    'is_title_match': bool,
                }
            }
        """
        page_results: dict[int, dict] = {}

        try:
            self._validate_path(pdf_path)
            checksum = self.database.get_file_checksum(pdf_path)
            cached_pages = self._ensure_text_extracted(pdf_path, checksum)

            if not cached_pages:
                return page_results

            # Check if query matches chapter title (highest priority)
            title_match = self._check_title_match(query, chapter_title)

            for page_num, text in cached_pages.items():
                page_matches = self._find_matches_with_location(
                    query, text, page_num + 1, is_first_page=(page_num == 0)
                )

                if page_matches:
                    # Aggregate matches for this page
                    locations = [m.location for m in page_matches]
                    # Use the most relevant match's context as primary
                    best_match = max(page_matches, key=lambda m: m.location.relevance_score)

                    page_results[page_num + 1] = {
                        'matches': page_matches,
                        'locations': list(set(locations)),  # Unique locations
                        'best_context': best_match.context,
                        'best_match_text': best_match.match_text,
                        'match_count': len(page_matches),
                        'is_title_match': title_match and page_num == 0,
                    }

            return page_results

        except (ValueError, fitz.FileDataError, OSError) as e:
            logger.warning("Error searching %s: %s", pdf_path.name, e)
        except Exception as e:
            logger.warning("Error searching %s: %s", pdf_path.name, type(e).__name__)

        return page_results

    def search_pdf(self, query: str, pdf_path: Path) -> list[PageMatch]:
        """Search a single PDF for query, return matches with context.

        Legacy method - returns all matches (not aggregated by page).
        For new code, prefer search_pdf_aggregated().
        """
        matches = []

        try:
            self._validate_path(pdf_path)
            checksum = self.database.get_file_checksum(pdf_path)
            cached_pages = self.database.get_all_cached_pages(pdf_path, checksum)

            if cached_pages:
                for page_num, text in cached_pages.items():
                    page_matches = self._find_matches_with_location(
                        query, text, page_num + 1, is_first_page=(page_num == 0)
                    )
                    matches.extend(page_matches)

            return matches

        except (ValueError, fitz.FileDataError, OSError) as e:
            logger.warning("Error reading PDF %s: %s", pdf_path.name, e)
        except Exception as e:
            logger.warning("Error searching %s: %s", pdf_path.name, type(e).__name__)

        return matches

    def _is_phrase_match(self, query: str, title: str) -> bool:
        """
        FIX 0.7+0.8: Check if multi-word query appears as a phrase in title.

        Used for STRICT mode to require exact phrase matching, not just word overlap.
        Now includes orthographic variant handling (disc/disk, tumour/tumor).

        Example: "lumbar discectomy" should match "Lumbar Microdiskectomy"
                 but NOT match "Cervical Discectomy" (wrong region)

        Args:
            query: Search query (e.g., "lumbar discectomy")
            title: Chapter title to check against

        Returns:
            True if query (or orthographic variant) appears as phrase in title
        """
        if not query or not title:
            return False

        query_lower = query.lower().strip()
        title_lower = title.lower()

        # Helper function to check phrase match for a given query variant
        def _check_phrase(q_lower: str, t_lower: str) -> bool:
            # Direct phrase containment
            if q_lower in t_lower:
                return True

            # Check if words appear adjacent/near each other
            q_words = q_lower.split()
            if len(q_words) >= 2:
                # Check if all query words exist in title (fast pre-check)
                if not all(w in t_lower for w in q_words):
                    return False
                # Check if words appear in order within title (limited gap)
                # Pattern: word1.{0,30}word2 (max 30 chars between words)
                pattern = r'.{0,30}'.join(re.escape(w) for w in q_words)
                if re.search(pattern, t_lower):
                    return True
            return False

        # Check original query
        if _check_phrase(query_lower, title_lower):
            return True

        # FIX 0.8: Also check orthographic variants (disc/disk, tumour/tumor)
        from .neurosurgical_synonyms import get_orthographic_expansion
        for variant in get_orthographic_expansion(query):
            variant_lower = variant.lower().strip()
            if variant_lower != query_lower:  # Skip original (already checked)
                if _check_phrase(variant_lower, title_lower):
                    return True

        return False

    def _check_title_match(self, query: str, chapter_title: str) -> bool:
        """
        Check if the query matches the chapter title.

        Strategy-aware matching:
        - STRICT mode: Requires phrase match or exact containment
        - STANDARD/BROAD: Uses multiple strategies including root word matching

        Strategies (applied based on mode):
        1. Direct containment (full query in title) - ALL modes
        2. Word overlap (each query word in title) - ALL modes
        3. Root word matching (discectomy → disc) - STANDARD/BROAD only
        4. Synonym expansion - STANDARD/BROAD only (via _should_expand_query)
        """
        if not chapter_title:
            return False
        query_lower = query.lower().strip()
        title_lower = chapter_title.lower()

        # Determine if we're in STRICT mode
        is_strict = (self._active_strategy is not None and
                     self._active_strategy.name == "strict")

        # FIX 0.7: STRICT mode requires phrase match for multi-word queries
        if is_strict and len(query_lower.split()) >= 2:
            return self._is_phrase_match(query, chapter_title)

        # Strategy 1: Direct containment
        if query_lower in title_lower:
            return True

        # Strategy 2: Check if primary query words are in title
        # Split query into words, filter short words
        query_words = [w for w in query_lower.split() if len(w) >= 3]
        if query_words:
            # Check if ALL significant words are in the title
            words_in_title = sum(1 for w in query_words if w in title_lower)
            if words_in_title == len(query_words):
                return True
            # Check if MOST words are in title (for longer queries)
            if len(query_words) >= 2 and words_in_title >= len(query_words) - 1:
                return True

        # FIX 0.5+0.9: Skip root word matching for STRICT mode
        # Root word matching causes false positives like "lumbar discectomy" → "thoracic disc"
        if not is_strict:
            # Strategy 3: Root word matching (strip common suffixes)
            # e.g., "discectomy" → check for "disc" in title
            # FIX 0.9: REQUIRE all other query words to match (anatomical region)
            for word in query_words:
                # Common surgical suffixes
                for suffix in ['ectomy', 'otomy', 'plasty', 'pexy', 'rraphy', 'ation', 'ion', 'ing', 'ed']:
                    if word.endswith(suffix) and len(word) > len(suffix) + 2:
                        root = word[:-len(suffix)]
                        if len(root) >= 3 and root in title_lower:
                            # Found root match - now check other words
                            other_words = [w for w in query_words if w != word]
                            # FIX 0.9: MUST have other words AND they MUST all match
                            # This prevents "lumbar discectomy" → root "disc" → matching "Thoracic Disc"
                            # because "lumbar" must also be in the title
                            if other_words and all(w in title_lower for w in other_words):
                                return True
                            # Single-word query with root match (e.g., just "discectomy")
                            # Don't match based on root alone - too imprecise
                            # Skip to synonym expansion instead

        # Strategy 4: Check query variations (synonyms)
        # FIX 0.4b: Use strategy-aware expansion check (disabled for STRICT)
        if self._should_expand_query():
            for variant in expand_query(query, max_expansions=5):
                variant_lower = variant.lower()
                if variant_lower in title_lower:
                    return True
                # Also check individual words of the variant
                variant_words = [w for w in variant_lower.split() if len(w) >= 3]
                if variant_words and all(w in title_lower for w in variant_words):
                    return True

        return False

    def _detect_match_location(
        self, text: str, match_start: int, is_first_page: bool
    ) -> MatchLocation:
        """
        Detect where in the document structure a match is located.

        Args:
            text: Full page text
            match_start: Character position of match
            page_number: Page number (1-indexed)
            is_first_page: Whether this is the first page of the PDF

        Returns:
            MatchLocation indicating the document structure context
        """
        # Get the line containing the match
        line_start = text.rfind('\n', 0, match_start) + 1
        line_end = text.find('\n', match_start)
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].strip()

        # Check for footnote/reference patterns
        for pattern in FOOTNOTE_PATTERNS:
            if re.match(pattern, line):
                return MatchLocation.FOOTNOTE

        # Check if it's near the start of the page (potential section header)
        # First 500 chars of a page often contain headers
        if match_start < 500:
            # Check for section header patterns
            for pattern in SECTION_HEADER_PATTERNS:
                if re.match(pattern, line):
                    return MatchLocation.SECTION_HEADER

            # First page, early text = likely chapter title area
            if is_first_page and match_start < 200:
                return MatchLocation.CHAPTER_TITLE

        # Check for section header anywhere
        for pattern in SECTION_HEADER_PATTERNS:
            if re.match(pattern, line):
                return MatchLocation.SECTION_HEADER

        # Default to body text
        return MatchLocation.BODY_TEXT

    def _find_matches_with_location(
        self, query: str, text: str, page_number: int, is_first_page: bool = False
    ) -> list[PageMatch]:
        """Find all occurrences of query with location detection."""
        matches = []
        seen_positions = set()

        # Get query variations
        # FIX 0.4c: Use strategy-aware expansion check
        if self._should_expand_query():
            query_variations = expand_query(query, max_expansions=3)
        else:
            query_variations = [query]

        for query_variant in query_variations:
            pattern = re.compile(re.escape(query_variant), re.IGNORECASE)

            for match in pattern.finditer(text):
                start_pos = match.start()

                if start_pos in seen_positions:
                    continue
                seen_positions.add(start_pos)

                match_text = match.group()
                context = self._extract_context(text, start_pos, len(match_text))
                location = self._detect_match_location(
                    text, start_pos, is_first_page
                )

                matches.append(PageMatch(
                    page_number=page_number,
                    match_text=match_text,
                    context=context,
                    start_pos=start_pos,
                    location=location
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
            logger.warning("Invalid PDF path: %s", e)
        except (fitz.FileDataError, OSError) as e:
            logger.warning("Error reading PDF %s: %s", pdf_path.name, e)
        except Exception as e:
            logger.warning("Error extracting page %d from %s: %s", page_number, pdf_path.name, type(e).__name__)

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

    def index_pdf_semantic(self, pdf_path: Path) -> int:
        """
        Build semantic index for a single PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of pages indexed
        """
        import time
        
        if not self.semantic.enabled:
            return 0

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
                        cached_pages[page_num] = text
                # Batch cache all pages at once (single transaction)
                self.database.cache_pdf_text_batch(pdf_path, cached_pages, checksum)

            # Batch encode all pages at once (more efficient, fewer GIL holds)
            batch_count = self.semantic.index_pages_batch(pdf_path, cached_pages, checksum)
            return batch_count

        except (ValueError, fitz.FileDataError, OSError) as e:
            logger.warning("Error indexing %s: %s", pdf_path.name, e)
            return 0
        except Exception as e:
            logger.warning("Unexpected error indexing %s: %s", pdf_path.name, type(e).__name__)
            return 0

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

            # Index single PDF
            batch_count = self.index_pdf_semantic(pdf_path)
            indexed_pages += batch_count

            # Yield GIL between PDFs to let UI thread run
            time.sleep(0.01)

            if progress_callback:
                progress_callback(i + 1, total)

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
                        logger.warning("Worker error extracting %s: %s", pdf_path.name, result['error'])
                        continue

                    # Validate path is within library
                    self._validate_path(pdf_path)

                    # Calculate checksum in main process (database operation)
                    checksum = self.database.get_file_checksum(pdf_path)

                    # Cache text in batch (single transaction = much faster)
                    pages = result["pages"]
                    self.database.cache_pdf_text_batch(pdf_path, pages, checksum)

                    # Index each page in semantic search
                    for page_num, text in pages.items():
                        if self.semantic.index_page(pdf_path, page_num + 1, text, checksum):
                            indexed_pages += 1

                    if progress_callback:
                        progress_callback(i + 1, total, pdf_path.name)

                except ValueError as e:
                    logger.warning("Invalid path %s: %s", pdf_path.name, e)
                except Exception as e:
                    logger.warning("Error processing %s: %s: %s", pdf_path.name, type(e).__name__, e)

        return indexed_pages
