"""Extract relevant pages from PDFs based on search results."""
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any, Optional
from datetime import datetime
import json

from ..logger import get_logger

# Module logger
logger = get_logger("export.page_extractor")


@dataclass
class ExtractedSource:
    """Metadata for an extracted PDF source with full categorization."""
    extracted_path: Path
    original_path: Path
    original_source: str  # e.g., "Youmans Ch 26"
    pages: list[int]
    # Enhanced categorization fields
    category_group: Optional[str] = None  # "Surgical/Anatomical" or "Theoretical"
    category: Optional[str] = None        # Specific subcategory
    confidence: Optional[float] = None    # AI confidence score 0.0-1.0
    reasoning: Optional[str] = None       # AI categorization reasoning
    context_excerpts: list[str] = field(default_factory=list)
    full_text: str = ""                   # Full text content of extracted pages
    # Visual content fields
    figures: list[dict[str, Any]] = field(default_factory=list)  # Figures on extracted pages
    figure_count: int = 0
    # Enhanced Search Fields
    authority_score: int = 0
    index_source: str = ""
    matched_sections: list[str] = field(default_factory=list)
    intent: str = ""


def extract_relevant_pages(
    results: list[Any],  # list[SearchResult] - avoiding import for flexibility
    output_dir: Path,
    context_pages: int = 1,
    database: Any | None = None  # Optional database for figure lookup
) -> list[ExtractedSource]:
    """
    Extract only pages containing matches from source PDFs.

    Args:
        results: List of SearchResult objects with pdf_path, page_number, etc.
        output_dir: Directory to save extracted PDFs
        context_pages: Number of pages before/after match to include (default 1)
        database: Optional database instance for figure lookups

    Returns:
        List of ExtractedSource objects with paths to mini-PDFs
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group results by source PDF
    pdf_groups: dict[Path, list] = defaultdict(list)
    for result in results:
        pdf_groups[result.pdf_path].append(result)

    extracted_sources: list[ExtractedSource] = []

    for pdf_path, pdf_results in pdf_groups.items():
        if not pdf_path.exists():
            continue

        try:
            source = _extract_pages_from_pdf(
                pdf_path=pdf_path,
                results=pdf_results,
                output_dir=output_dir,
                context_pages=context_pages,
                database=database
            )
            if source:
                extracted_sources.append(source)
        except Exception as e:
            logger.warning("Error extracting from %s: %s", pdf_path, e)
            continue

    return extracted_sources


def _extract_pages_from_pdf(
    pdf_path: Path,
    results: list[Any],
    output_dir: Path,
    context_pages: int,
    database: Any | None = None
) -> Optional[ExtractedSource]:
    """Extract pages from a single PDF.

    Uses try-finally to ensure document handles are always closed,
    even if extraction fails partway through. Individual page failures
    are logged and skipped to allow partial extraction.
    """
    doc = None
    new_doc = None
    successfully_inserted_pages: list[int] = []

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Collect all relevant page numbers
        page_set: set[int] = set()
        
        # Check if we have ChapterResult objects (enhanced search)
        is_enhanced = hasattr(results[0], 'matched_pages') and hasattr(results[0], 'matched_sections')
        
        if is_enhanced:
            # Use pre-calculated matched pages from ChapterResult (includes Zero Data Loss window)
            for result in results:
                if hasattr(result, 'matched_pages'):
                    for p in result.matched_pages:
                        if 1 <= p <= total_pages:
                            page_set.add(p)
        else:
            # Legacy SearchResult: Add context pages around matches
            for result in results:
                page_num = result.page_number
                for offset in range(-context_pages, context_pages + 1):
                    p = page_num + offset
                    if 1 <= p <= total_pages:
                        page_set.add(p)

        pages = sorted(page_set)

        if not pages:
            return None

        # Create new PDF with selected pages and extract text
        new_doc = fitz.open()
        full_text_parts = []

        for page_num in pages:
            # fitz uses 0-indexed pages - wrap in try-except for resilience
            try:
                new_doc.insert_pdf(doc, from_page=page_num - 1, to_page=page_num - 1)
                successfully_inserted_pages.append(page_num)
            except Exception as e:
                logger.warning("Could not insert page %d from %s: %s", page_num, pdf_path.name, e)
                continue  # Skip problematic page, continue with others

            # Extract text from the original page
            try:
                page = doc.load_page(page_num - 1)
                text = page.get_text()
                if text.strip():
                    full_text_parts.append(f"--- Page {page_num} ---\n{text}")
            except Exception as e:
                logger.warning("Could not extract text from page %d: %s", page_num, e)

        # Check if we successfully inserted any pages
        if not successfully_inserted_pages:
            logger.warning("No pages could be extracted from %s", pdf_path.name)
            return None

        full_text = "\n\n".join(full_text_parts)

        # Generate output filename
        first_result = results[0]
        safe_name = _safe_filename(first_result.chapter_title or first_result.book_title)
        page_range = f"p{successfully_inserted_pages[0]}-{successfully_inserted_pages[-1]}" if len(successfully_inserted_pages) > 1 else f"p{successfully_inserted_pages[0]}"
        output_name = f"{safe_name}_{page_range}.pdf"
        output_path = output_dir / output_name

        # Handle filename collisions
        counter = 1
        while output_path.exists():
            output_name = f"{safe_name}_{page_range}_{counter}.pdf"
            output_path = output_dir / output_name
            counter += 1

        new_doc.save(str(output_path))

        # Build source reference
        source_ref = first_result.book_series
        if first_result.chapter_number:
            source_ref += f" Ch {first_result.chapter_number}"

        # Collect categorization with confidence weighting
        # Use the category with highest confidence if multiple exist
        best_category = None
        best_group = None
        best_confidence = 0.0
        best_reasoning = None

        for r in results:
            cat = getattr(r, 'category', None)
            conf = getattr(r, 'category_confidence', 0) or 0
            if cat and conf >= best_confidence:
                best_category = cat
                best_group = getattr(r, 'category_group', None)
                best_confidence = conf
                best_reasoning = getattr(r, 'category_reasoning', None)

        # Collect context excerpts
        excerpts = []
        for r in results:
            ctx = getattr(r, 'context', getattr(r, 'preview_context', None))
            if ctx:
                excerpts.append(ctx)
        excerpts = excerpts[:5]  # Limit to 5

        # Collect figures for extracted pages (use successfully_inserted_pages)
        figures = []
        if database:
            try:
                for page_num in successfully_inserted_pages:
                    page_figures = database.get_page_figures(pdf_path, page_num)
                    for fig in page_figures:
                        figures.append({
                            "id": fig.get("id"),
                            "page_number": fig.get("page_number"),
                            "image_path": fig.get("image_path"),
                            "image_type": fig.get("image_type"),
                            "caption": fig.get("caption"),
                            "caption_confidence": fig.get("caption_confidence"),
                        })
            except Exception as e:
                logger.warning("Could not load figures for %s: %s", pdf_path.name, e)

        return ExtractedSource(
            extracted_path=output_path,
            original_path=pdf_path,
            original_source=source_ref,
            pages=successfully_inserted_pages,  # Use actually extracted pages
            category_group=best_group,
            category=best_category,
            confidence=best_confidence if best_confidence > 0 else None,
            reasoning=best_reasoning,
            context_excerpts=excerpts,
            full_text=full_text,
            figures=figures,
            figure_count=len(figures),
            # Enhanced fields
            authority_score=getattr(first_result, 'authority_score', 0),
            index_source=getattr(first_result, 'index_source', ""),
            matched_sections=[s.title for s in getattr(first_result, 'matched_sections', [])],
            intent=getattr(first_result, 'match_type', "").name if hasattr(first_result, 'match_type') else ""
        )

    except Exception as e:
        logger.error("Error extracting from %s: %s", pdf_path.name, e)
        return None

    finally:
        # Always close document handles to prevent file descriptor leaks
        if new_doc:
            try:
                new_doc.close()
            except Exception:
                pass
        if doc:
            try:
                doc.close()
            except Exception:
                pass


def _safe_filename(name: str) -> str:
    """Convert name to safe filename."""
    # Remove/replace problematic characters
    unsafe = '<>:"/\\|?*'
    result = name
    for char in unsafe:
        result = result.replace(char, '_')
    # Limit length
    return result[:50].strip()


def _compute_category_summary(sources: list[ExtractedSource]) -> dict[str, int]:
    """Compute count of sources per category group."""
    summary = {"Surgical/Anatomical": 0, "Theoretical": 0}
    for source in sources:
        if source.category_group in summary:
            summary[source.category_group] += 1
    return summary


def _determine_template_type(sources: list[ExtractedSource]) -> str:
    """Determine recommended template type based on content analysis.

    Returns:
        'procedural' for surgical/anatomical dominant content
        'theoretical' for theoretical dominant content
        'mixed' for balanced content
    """
    category_summary = _compute_category_summary(sources)
    surgical = category_summary.get("Surgical/Anatomical", 0)
    theoretical = category_summary.get("Theoretical", 0)

    total = surgical + theoretical
    if total == 0:
        return "mixed"

    surgical_ratio = surgical / total

    if surgical_ratio >= 0.7:
        return "procedural"
    elif surgical_ratio <= 0.3:
        return "theoretical"
    else:
        return "mixed"


def _compute_figure_summary(sources: list[ExtractedSource]) -> dict:
    """Compute figure statistics across all sources."""
    total_figures = 0
    figures_by_type = {}

    for source in sources:
        total_figures += source.figure_count
        for fig in source.figures:
            img_type = fig.get("image_type", "unknown")
            figures_by_type[img_type] = figures_by_type.get(img_type, 0) + 1

    return {
        "total_figures": total_figures,
        "figures_by_type": figures_by_type
    }


def _compute_authority_summary(sources: list[ExtractedSource]) -> dict:
    """Compute authority statistics across all sources.

    Returns summary of authority scores and index sources for NeuroSynth
    to use in prioritizing content during synthesis.
    """
    if not sources:
        return {"avg_authority": 0, "max_authority": 0, "sources_by_tier": {}}

    scores = [s.authority_score for s in sources if s.authority_score > 0]

    # Tier classification
    tier_1 = sum(1 for s in scores if s >= 90)   # Specialized texts
    tier_2 = sum(1 for s in scores if 80 <= s < 90)  # Major references
    tier_3 = sum(1 for s in scores if s < 80)    # Standard texts

    # Unique index sources
    index_sources = list(set(s.index_source for s in sources if s.index_source))

    return {
        "avg_authority": round(sum(scores) / len(scores), 1) if scores else 0,
        "max_authority": max(scores) if scores else 0,
        "sources_by_tier": {
            "tier_1_specialized": tier_1,
            "tier_2_major": tier_2,
            "tier_3_standard": tier_3,
        },
        "index_sources": index_sources[:5],  # Top 5 unique sources
    }


def generate_manifest(
    topic: str,
    sources: list[ExtractedSource],
    output_path: Path,
    search_query: str = "",
    search_mode: str = "keyword",
    template_type: Optional[str] = None,  # Override auto-detection
    query_intent: Optional[str] = None,  # Detected intent (TECHNIQUE, COMPLICATION, etc.)
) -> Path:
    """
    Generate an enhanced manifest.json file for NeuroSynth import.

    Args:
        topic: The synthesis topic/title
        sources: List of ExtractedSource objects
        output_path: Path to write manifest.json
        search_query: Original search query from Reference Library
        search_mode: Search mode used (keyword/semantic/hybrid)
        template_type: Override template type (procedural/theoretical/mixed)
        query_intent: Detected query intent (TECHNIQUE, COMPLICATION, ANATOMY, etc.)

    Returns:
        Path to the generated manifest file
    """
    category_summary = _compute_category_summary(sources)
    figure_summary = _compute_figure_summary(sources)

    # Auto-detect template type if not specified
    detected_template = _determine_template_type(sources)
    final_template = template_type or detected_template

    # Compute authority summary from sources
    authority_summary = _compute_authority_summary(sources)

    manifest = {
        "topic": topic,
        "search_query": search_query,
        "search_mode": search_mode,
        "query_intent": query_intent,  # NEW: Top-level intent for NeuroSynth
        "generated_at": datetime.now().isoformat(),
        "template_type": final_template,
        "template_type_auto_detected": template_type is None,
        "category_summary": category_summary,
        "figure_summary": figure_summary,
        "authority_summary": authority_summary,  # NEW: Authority stats
        "sources": [
            {
                "pdf_path": str(source.extracted_path.name),
                "original_source": source.original_source,
                "original_path": str(source.original_path),
                "pages": source.pages,
                "category_group": source.category_group,
                "category": source.category,
                "confidence": source.confidence,
                "reasoning": source.reasoning,
                # Enhanced Search Metadata
                "authority_score": source.authority_score,
                "index_source": source.index_source,
                "matched_sections": source.matched_sections,
                "intent": source.intent,
                "context_excerpts": source.context_excerpts,
                "full_text": source.full_text,
                "figure_count": source.figure_count,
                "figures": [
                    {
                        "id": fig.get("id"),
                        "page_number": fig.get("page_number"),
                        "image_type": fig.get("image_type"),
                        "caption": fig.get("caption"),
                        "image_path": str(fig.get("image_path")) if fig.get("image_path") else None,
                        # Phase 4 fields
                        "caption_confidence": fig.get("caption_confidence"),
                        "keywords": fig.get("keywords"),
                        "is_procedural": fig.get("is_procedural"),
                        "sequence_id": fig.get("sequence_id"),
                    }
                    for fig in source.figures
                ]
            }
            for source in sources
        ]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return output_path
