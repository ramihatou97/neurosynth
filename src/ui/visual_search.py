"""
Visual Search Component
========================
ColPali-powered semantic image search with Qdrant vector store.
Supports text-to-image and image-to-image similarity search.
"""

import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st

# Visual search availability
VISUAL_SEARCH_AVAILABLE = False
VisualSearcher = None

try:
    from src.reference_library.search.visual_searcher import (
        VISUAL_SEARCH_AVAILABLE as VS_AVAILABLE,
    )
    from src.reference_library.search.visual_searcher import VisualSearcher as VS

    if VS_AVAILABLE:
        VISUAL_SEARCH_AVAILABLE = True
        VisualSearcher = VS
except ImportError:
    pass


def _get_visual_searcher():
    """Get or create visual searcher instance."""
    if not VISUAL_SEARCH_AVAILABLE:
        return None

    if "visual_searcher" not in st.session_state:
        if "db" not in st.session_state:
            return None
        try:
            st.session_state.visual_searcher = VisualSearcher(st.session_state.db)
        except Exception as e:
            st.warning(f"Visual search initialization failed: {e}")
            return None

    return st.session_state.visual_searcher


def render_visual_search_panel():
    """Render the visual search panel for the library."""
    st.markdown("### 🔍 Visual Search")

    searcher = _get_visual_searcher()

    if not searcher or not searcher.enabled:
        st.info("⚠️ Visual search requires ColPali and Qdrant. Enable in settings.")
        with st.expander("Setup Instructions"):
            st.markdown(
                """
            **Requirements:**
            1. Install: `pip install qdrant-client colpali-engine`
            2. Enable in config: `VISUAL_SEARCH_ENABLED=true`
            3. Run embedding pipeline: `neurosynth embed-visuals`
            """
            )
        return

    # Search mode tabs
    search_mode = st.radio(
        "Search Mode",
        ["Text Query", "Similar Images"],
        horizontal=True,
        key="visual_search_mode",
    )

    if search_mode == "Text Query":
        _render_text_search(searcher)
    else:
        _render_image_search(searcher)


def _render_text_search(searcher):
    """Render text-to-image search interface."""
    col1, col2 = st.columns([3, 1])

    with col1:
        query = st.text_input(
            "Describe the image you're looking for",
            placeholder="e.g., 'pterional craniotomy surgical steps' or 'MRI showing vestibular schwannoma'",
            key="visual_text_query",
        )

    with col2:
        n_results = st.selectbox(
            "Results", [5, 10, 20, 50], index=1, key="visual_n_results"
        )

    # Image type filter
    image_types = st.multiselect(
        "Filter by Type",
        ["surgical_step", "anatomical", "imaging", "table", "flowchart"],
        default=[],
        key="visual_type_filter",
    )

    if st.button("🔍 Search Images", width="stretch", key="visual_search_btn"):
        if not query:
            st.warning("Enter a search query")
            return

        with st.spinner("Searching visual embeddings..."):
            try:
                results = searcher.search_by_text(
                    query=query,
                    n_results=n_results,
                    image_types=image_types if image_types else None,
                )
                st.session_state.visual_search_results = results
            except Exception as e:
                st.error(f"Search failed: {e}")
                return

    # Display results
    _display_search_results()


def _render_image_search(searcher):
    """Render image-to-image similarity search interface."""
    st.markdown("Upload an image to find similar figures:")

    uploaded_file = st.file_uploader(
        "Drop image here", type=["png", "jpg", "jpeg"], key="visual_upload"
    )

    col1, col2 = st.columns(2)
    with col1:
        n_results = st.selectbox(
            "Results", [5, 10, 20], index=1, key="visual_sim_n_results"
        )
    with col2:
        image_types = st.multiselect(
            "Filter by Type",
            ["surgical_step", "anatomical", "imaging", "table"],
            default=[],
            key="visual_sim_type_filter",
        )

    if uploaded_file and st.button("🔍 Find Similar", width="stretch"):
        with st.spinner("Finding similar images..."):
            try:
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = Path(tmp.name)

                results = searcher.search_by_image(
                    image_path=tmp_path,
                    n_results=n_results,
                    image_types=image_types if image_types else None,
                )
                st.session_state.visual_search_results = results
                tmp_path.unlink()  # Clean up
            except Exception as e:
                st.error(f"Search failed: {e}")

    _display_search_results()


def _display_search_results():
    """Display visual search results in a gallery format."""
    if "visual_search_results" not in st.session_state:
        return

    results = st.session_state.visual_search_results

    if not results:
        st.info("No matching images found.")
        return

    st.markdown(f"**Found {len(results)} matching images**")
    st.markdown("---")

    # Gallery grid
    cols = st.columns(3)
    for i, result in enumerate(results):
        with cols[i % 3]:
            _render_figure_card(result, i)


def _render_figure_card(result: dict, index: int):
    """Render a single figure card with context."""
    image_path = result.get("image_path", "")

    # Try to display image
    if image_path and Path(image_path).exists():
        st.image(image_path, width="stretch")
    else:
        st.markdown("🖼️ *Image not available*")

    # Metadata
    score = result.get("score", 0)
    image_type = result.get("image_type", "unknown")
    page = result.get("page_number", "?")

    # Type badge color
    type_colors = {
        "surgical_step": "🔬",
        "anatomical": "🧠",
        "imaging": "📷",
        "table": "📊",
        "flowchart": "📋",
    }
    type_icon = type_colors.get(image_type, "🖼️")

    st.markdown(f"{type_icon} **{image_type.replace('_', ' ').title()}** • Page {page}")
    st.caption(f"Similarity: {score:.2%}")

    # Caption/context
    caption = result.get("caption", "")
    if caption:
        with st.expander("View Caption"):
            st.markdown(caption)

    # Source info
    pdf_path = result.get("pdf_path")
    if pdf_path:
        source_name = Path(pdf_path).stem[:30] if pdf_path else "Unknown"
        st.caption(f"📄 {source_name}...")

    # Action buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📋 Copy ID", key=f"copy_{index}", width="stretch"):
            st.session_state.copied_figure_id = result.get("figure_id")
            st.success("Copied!")
    with col_b:
        if st.button("➕ Add to Synthesis", key=f"add_{index}", width="stretch"):
            if "synthesis_figures" not in st.session_state:
                st.session_state.synthesis_figures = []
            st.session_state.synthesis_figures.append(result)
            st.success("Added!")


def render_enhanced_figure_gallery(images: list, source_id: str = ""):
    """Render an enhanced figure gallery with filtering and context."""
    if not images:
        st.info("No images extracted from this source.")
        return

    st.markdown("### 🖼️ Figure Gallery")

    # Gallery controls
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # Type filter
        image_types = list(set(getattr(img, "image_type", "unknown") for img in images))
        if hasattr(image_types[0], "value"):
            image_types = [t.value for t in image_types]
        selected_types = st.multiselect(
            "Filter by Type",
            image_types,
            default=image_types,
            key=f"gallery_filter_{source_id}",
        )

    with col2:
        # Sort order
        sort_by = st.selectbox(
            "Sort by",
            ["Page Number", "Type", "Caption Length"],
            key=f"gallery_sort_{source_id}",
        )

    with col3:
        # View mode
        view_mode = st.selectbox(
            "View", ["Grid", "List"], key=f"gallery_view_{source_id}"
        )

    # Filter images
    filtered = []
    for img in images:
        img_type = getattr(img, "image_type", "unknown")
        if hasattr(img_type, "value"):
            img_type = img_type.value
        if img_type in selected_types:
            filtered.append(img)

    # Sort images
    if sort_by == "Page Number":
        filtered.sort(key=lambda x: getattr(x, "page", 0))
    elif sort_by == "Type":
        filtered.sort(key=lambda x: str(getattr(x, "image_type", "")))
    elif sort_by == "Caption Length":
        filtered.sort(key=lambda x: len(getattr(x, "caption", "") or ""), reverse=True)

    st.caption(f"Showing {len(filtered)} of {len(images)} images")

    # Render gallery
    if view_mode == "Grid":
        _render_grid_gallery(filtered)
    else:
        _render_list_gallery(filtered)


def _render_grid_gallery(images: list):
    """Render images in a grid layout."""
    cols = st.columns(4)
    for i, img in enumerate(images):
        with cols[i % 4]:
            file_path = getattr(img, "file_path", None)
            if file_path and Path(file_path).exists():
                st.image(str(file_path), width="stretch")

            page = getattr(img, "page", "?")
            img_type = getattr(img, "image_type", "unknown")
            if hasattr(img_type, "value"):
                img_type = img_type.value

            st.caption(f"Page {page} • {img_type}")

            caption = getattr(img, "caption", "")
            if caption:
                with st.expander("Caption"):
                    st.markdown(
                        caption[:200] + "..." if len(caption) > 200 else caption
                    )


def _render_list_gallery(images: list):
    """Render images in a list layout with full context."""
    for i, img in enumerate(images):
        with st.container():
            col1, col2 = st.columns([1, 2])

            with col1:
                file_path = getattr(img, "file_path", None)
                if file_path and Path(file_path).exists():
                    st.image(str(file_path), width="stretch")

            with col2:
                page = getattr(img, "page", "?")
                img_type = getattr(img, "image_type", "unknown")
                if hasattr(img_type, "value"):
                    img_type = img_type.value

                st.markdown(f"**Figure {i+1}** • Page {page}")
                st.markdown(f"Type: `{img_type}`")

                caption = getattr(img, "caption", "")
                if caption:
                    st.markdown("**Caption:**")
                    st.markdown(caption)

                # Context if available
                context = getattr(img, "context", None) or getattr(
                    img, "surrounding_text", None
                )
                if context:
                    with st.expander("Surrounding Context"):
                        st.markdown(context[:500])

            st.divider()
