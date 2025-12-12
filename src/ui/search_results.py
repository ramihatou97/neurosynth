"""
Advanced Search Results UI for Streamlit

Features:
- Hierarchical result tree (series → chapter → page)
- Thumbnail gallery per result (up to 12 figures)
- Sorting by relevance/date/title
- Context preview with search term highlighting
- Search history and autocomplete
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

from src.models import SearchResult


@dataclass
class GroupedResult:
    """Result grouped by series and chapter."""

    series: str
    chapter_title: str
    chapter_number: int | None
    results: list[SearchResult]
    figures: list[dict]
    total_score: float


def render_search_controls(
    search_history: list[str], on_search: callable, on_clear_history: callable = None
) -> str:
    """Render search input with autocomplete and history."""
    col1, col2 = st.columns([5, 1])

    with col1:
        # Search input with datalist for autocomplete
        query = st.text_input(
            "🔍 Search",
            placeholder="Enter search term...",
            key="search_query_input",
            label_visibility="collapsed",
        )

    with col2:
        if st.button("🔍", key="search_btn", width="stretch"):
            if query:
                on_search(query)

    # Search history dropdown
    if search_history:
        with st.expander("📜 Recent Searches", expanded=False):
            cols = st.columns([4, 1])
            with cols[0]:
                selected = st.selectbox(
                    "History",
                    options=[""] + search_history[:10],
                    label_visibility="collapsed",
                    key="search_history_select",
                )
                if selected:
                    st.session_state["search_query_input"] = selected
            with cols[1]:
                if on_clear_history and st.button("🗑️", key="clear_history"):
                    on_clear_history()

    return query


def render_sort_controls() -> tuple[str, bool]:
    """Render sorting controls. Returns (sort_by, ascending)."""
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        sort_by = st.selectbox(
            "Sort by", options=["relevance", "title", "chapter"], index=0, key="sort_by"
        )

    with col2:
        order = st.selectbox(
            "Order", options=["Descending", "Ascending"], index=0, key="sort_order"
        )

    with col3:
        view_mode = st.radio(
            "View",
            options=["🌳", "📋"],
            horizontal=True,
            key="result_view_mode",
            label_visibility="collapsed",
        )

    return sort_by, order == "Ascending", view_mode == "🌳"


def group_results_hierarchically(
    results: list[SearchResult], db=None
) -> dict[str, dict[str, GroupedResult]]:
    """Group results into series → chapter → results hierarchy."""
    hierarchy: dict[str, dict[str, GroupedResult]] = {}

    for result in results:
        series = (
            result.chunk.source_id.split("/")[0]
            if "/" in result.chunk.source_id
            else "Unknown"
        )
        chapter_title = result.chunk.metadata.get("chapter_title", "Unknown Chapter")
        chapter_num = result.chunk.metadata.get("chapter_number")

        if series not in hierarchy:
            hierarchy[series] = {}

        chapter_key = f"{chapter_num or 0}_{chapter_title}"
        if chapter_key not in hierarchy[series]:
            hierarchy[series][chapter_key] = GroupedResult(
                series=series,
                chapter_title=chapter_title,
                chapter_number=chapter_num,
                results=[],
                figures=[],
                total_score=0.0,
            )

        hierarchy[series][chapter_key].results.append(result)
        hierarchy[series][chapter_key].total_score += result.score

        # Load figures for this result if db available
        if db:
            try:
                page_num = result.chunk.metadata.get("page_number")
                if page_num:
                    figs = db.get_images_by_source(result.chunk.source_id)
                    for fig in figs[:12]:  # Max 12 figures
                        if fig not in hierarchy[series][chapter_key].figures:
                            hierarchy[series][chapter_key].figures.append(fig)
            except Exception:
                pass

    return hierarchy


def highlight_text(text: str, query: str, max_length: int = 300) -> str:
    """Highlight search terms in text with markdown."""
    if not query or not text:
        return text[:max_length] + ("..." if len(text) > max_length else "")

    # Find match position
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    match = pattern.search(text)

    if match:
        # Center context around match
        start = max(0, match.start() - max_length // 2)
        end = min(len(text), match.end() + max_length // 2)
        excerpt = text[start:end]

        # Add ellipsis
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."

        # Highlight matches
        highlighted = pattern.sub(lambda m: f"**:orange[{m.group()}]**", excerpt)
        return highlighted

    return text[:max_length] + ("..." if len(text) > max_length else "")


def render_thumbnail_gallery(figures: list, max_thumbs: int = 12):
    """Render a grid of figure thumbnails."""
    if not figures:
        return

    # Display up to max_thumbs figures in a grid
    display_figs = figures[:max_thumbs]
    cols_per_row = 4

    for i in range(0, len(display_figs), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(display_figs):
                fig = display_figs[idx]
                with col:
                    _render_thumbnail(fig)

    # Overflow indicator
    if len(figures) > max_thumbs:
        st.caption(f"+{len(figures) - max_thumbs} more figures")


def _render_thumbnail(fig):
    """Render a single thumbnail with type indicator."""
    image_path = fig.path if hasattr(fig, "path") else fig.get("path", "")
    image_type = (
        fig.image_type.value
        if hasattr(fig, "image_type")
        else fig.get("image_type", "unknown")
    )
    caption = fig.caption if hasattr(fig, "caption") else fig.get("caption", "")

    # Type icons
    type_icons = {
        "surgical_step": "🔪",
        "anatomical": "🧠",
        "imaging": "📷",
        "table": "📊",
        "flowchart": "📈",
        "diagram": "📐",
        "unknown": "🖼️",
    }
    icon = type_icons.get(image_type, "🖼️")

    if image_path and Path(image_path).exists():
        st.image(image_path, width="stretch")
        st.caption(
            f"{icon} {caption[:30]}..." if len(caption) > 30 else f"{icon} {caption}"
        )
    else:
        st.info(f"{icon} Image unavailable")


def render_hierarchical_results(
    hierarchy: dict[str, dict[str, GroupedResult]],
    query: str = "",
    on_select: callable = None,
    show_thumbnails: bool = True,
):
    """Render results in hierarchical tree view."""
    if not hierarchy:
        st.info("No results to display")
        return

    total_results = sum(
        len(group.results)
        for chapters in hierarchy.values()
        for group in chapters.values()
    )
    st.markdown(f"**{total_results} results** across {len(hierarchy)} series")

    # Render each series
    for series_name, chapters in hierarchy.items():
        series_count = sum(len(g.results) for g in chapters.values())

        with st.expander(
            f"📚 **{series_name}** ({series_count} matches)", expanded=True
        ):
            # Render each chapter
            for chapter_key, group in sorted(chapters.items()):
                _render_chapter_group(group, query, on_select, show_thumbnails)


def _render_chapter_group(
    group: GroupedResult, query: str, on_select: callable, show_thumbnails: bool
):
    """Render a chapter group with its results."""
    chapter_label = f"📄 {group.chapter_title}"
    if group.chapter_number:
        chapter_label = f"📄 Ch.{group.chapter_number}: {group.chapter_title}"

    avg_score = group.total_score / len(group.results) if group.results else 0

    with st.container():
        # Chapter header
        cols = st.columns([4, 1, 1])
        with cols[0]:
            st.markdown(f"**{chapter_label}**")
        with cols[1]:
            st.caption(f"{len(group.results)} pages")
        with cols[2]:
            st.caption(f"Score: {avg_score:.2f}")

        # Thumbnail gallery (if enabled and figures exist)
        if show_thumbnails and group.figures:
            with st.container():
                render_thumbnail_gallery(group.figures, max_thumbs=6)

        # Individual results
        for result in group.results:
            _render_result_item(result, query, on_select)

        st.divider()


def _render_result_item(result: SearchResult, query: str, on_select: callable):
    """Render a single result item with context preview."""
    page_num = result.chunk.metadata.get("page_number", "?")
    text = result.chunk.text

    cols = st.columns([1, 6, 1])

    with cols[0]:
        st.markdown(f"**p.{page_num}**")

    with cols[1]:
        # Highlighted context preview
        highlighted = highlight_text(text, query, max_length=200)
        st.markdown(highlighted, unsafe_allow_html=False)

    with cols[2]:
        st.caption(f"{result.score:.2f}")
        if on_select:
            if st.button("📖", key=f"select_{id(result)}", help="View details"):
                on_select(result)


def render_flat_results(
    results: list[SearchResult], query: str = "", on_select: callable = None
):
    """Render results in flat list view (non-hierarchical)."""
    if not results:
        st.info("No results to display")
        return

    st.markdown(f"**{len(results)} results**")

    for i, result in enumerate(results):
        with st.container():
            _render_result_item(result, query, on_select)
            if i < len(results) - 1:
                st.divider()


def sort_results(
    results: list[SearchResult], sort_by: str = "relevance", ascending: bool = False
) -> list[SearchResult]:
    """Sort results by specified criteria."""
    if sort_by == "relevance":
        return sorted(results, key=lambda r: r.score, reverse=not ascending)
    elif sort_by == "title":
        return sorted(
            results,
            key=lambda r: r.chunk.metadata.get("chapter_title", ""),
            reverse=not ascending,
        )
    elif sort_by == "chapter":
        return sorted(
            results,
            key=lambda r: (r.chunk.metadata.get("chapter_number", 0) or 0),
            reverse=not ascending,
        )
    return results


# ==================== Search History Management ====================


def init_search_history():
    """Initialize search history in session state."""
    if "search_history" not in st.session_state:
        st.session_state["search_history"] = []


def add_to_search_history(query: str):
    """Add a query to search history."""
    init_search_history()
    history = st.session_state["search_history"]

    # Remove if already exists (to move to front)
    if query in history:
        history.remove(query)

    # Add to front
    history.insert(0, query)

    # Keep only last 20
    st.session_state["search_history"] = history[:20]


def clear_search_history():
    """Clear search history."""
    st.session_state["search_history"] = []


def get_search_history() -> list[str]:
    """Get search history."""
    init_search_history()
    return st.session_state["search_history"]


# ==================== Main Search Panel ====================


def render_advanced_search_panel(
    search_engine, embedding_client, db=None, on_result_select: callable = None
):
    """
    Render the complete advanced search panel with all features.

    Args:
        search_engine: SearchEngine instance
        embedding_client: Client for generating embeddings
        db: Database for loading figures
        on_result_select: Callback when a result is selected
    """
    st.subheader("🔍 Advanced Search")

    init_search_history()

    # Search input with history
    def handle_search(query: str):
        if query:
            add_to_search_history(query)
            st.session_state["current_search_query"] = query

    query = render_search_controls(
        search_history=get_search_history(),
        on_search=handle_search,
        on_clear_history=clear_search_history,
    )

    # Get current query
    current_query = st.session_state.get("current_search_query", query)

    if not current_query:
        st.info("Enter a search term to find relevant content")
        return

    # Perform search
    with st.spinner("Searching..."):
        try:
            # Generate embedding
            query_embedding = embedding_client.embed(current_query)

            # Search
            results = search_engine.search_chunks(
                query_embedding=query_embedding, top_k=50
            )

            if not results:
                st.warning("No results found")
                return

            # Store results
            st.session_state["search_results"] = results

        except Exception as e:
            st.error(f"Search failed: {e}")
            return

    # Get results from session
    results = st.session_state.get("search_results", [])

    if not results:
        return

    # Sort and view controls
    sort_by, ascending, tree_view = render_sort_controls()

    # Sort results
    sorted_results = sort_results(results, sort_by, ascending)

    # Render results
    if tree_view:
        # Hierarchical view
        hierarchy = group_results_hierarchically(sorted_results, db)
        render_hierarchical_results(
            hierarchy,
            query=current_query,
            on_select=on_result_select,
            show_thumbnails=True,
        )
    else:
        # Flat list view
        render_flat_results(
            sorted_results, query=current_query, on_select=on_result_select
        )
