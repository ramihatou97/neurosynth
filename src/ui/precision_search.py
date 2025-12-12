"""
Precision Search UI Component
=============================
Deep-DX Precision Search with ColBERT reranking, query classification,
and confidence scoring integrated into Streamlit UI.
"""

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


def _get_search_engine():
    """Lazy-load UnifiedSearchEngine singleton."""
    if "unified_engine" not in st.session_state:
        try:
            from src.index import Database
            from src.index.unified_search import UnifiedSearchEngine

            if "db" not in st.session_state:
                st.session_state.db = Database()

            st.session_state.unified_engine = UnifiedSearchEngine(st.session_state.db)
        except Exception as e:
            st.error(f"Failed to initialize Engine: {e}")
            return None
    return st.session_state.unified_engine


def render_precision_search_panel():
    """Render the Deep-DX Precision Search panel."""
    from src.index.unified_search import SearchMode

    st.markdown("### 🎯 Deep-DX Precision Search")
    st.caption("Hybrid Dense + BM25 → ColBERT Reranking | Authority-Boosted Scoring")

    # Search configuration
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Search Query",
            placeholder="e.g., 'What structures are anterior to the facial nerve?'",
            key="precision_search_query",
            label_visibility="collapsed",
        )
    with col2:
        search_clicked = st.button(
            "🔍 Search", key="precision_search_btn", width="stretch"
        )

    # Advanced options
    with st.expander("⚙️ Search Options", expanded=False):
        col_mode, col_k = st.columns([2, 1])
        with col_mode:
            # Search Mode Selector (Phase 1 Requirement)
            mode_options = {
                SearchMode.FAST: "⚡ FAST (Vector Only)",
                SearchMode.BALANCED: "⚖️ BALANCED (Hybrid)",
                SearchMode.DEEP: "🧠 DEEP (ColBERT Reranking)",
                SearchMode.REASONING: "🕸️ REASONING (Graph + RAPTOR)",
            }
            selected_mode_key = st.selectbox(
                "Search Mode",
                options=list(mode_options.keys()),
                format_func=lambda x: mode_options[x],
                index=2,  # Default to DEEP
                key="precision_search_mode",
            )

        with col_k:
            top_k = st.slider(
                "Results", min_value=5, max_value=50, value=20, key="precision_top_k"
            )

        # Subspecialty filter
        subspecialty = st.selectbox(
            "Filter by Subspecialty",
            [
                "All",
                "Vascular",
                "Oncology",
                "Spine",
                "Functional",
                "Pediatric",
                "Skull Base",
                "Trauma",
            ],
            key="precision_subspecialty",
        )

    if not query:
        st.info("Enter a query to search with Deep-DX precision retrieval")
        return

    if search_clicked or (
        "precision_last_query" in st.session_state
        and st.session_state.precision_last_query == query
    ):
        _execute_unified_search(
            query=query,
            mode=selected_mode_key,
            top_k=top_k,
            subspecialty=subspecialty if subspecialty != "All" else None,
        )


def _execute_unified_search(
    query: str, mode, top_k: int, subspecialty: str | None = None
):
    """Execute search using UnifiedSearchEngine."""
    engine = _get_search_engine()
    if not engine:
        return

    st.session_state.precision_last_query = query

    with st.spinner(f"🔍 Executing {mode.value.upper()} search..."):
        try:
            from src.neurosynth.llm.embeddings import EmbeddingClient

            embedding_client = EmbeddingClient()
            query_embedding = embedding_client.embed(query)

            # Execute search
            result = engine.search(
                query=query,
                query_embedding=query_embedding,
                mode=mode,
                top_k=top_k,
                filters={"specialty": subspecialty} if subspecialty else None,
            )

            st.session_state.precision_result = result

        except Exception as e:
            st.error(f"Search failed: {e}")
            return

    # Display results
    _render_unified_results()


def _render_unified_results():
    """Render unified search results."""
    if "precision_result" not in st.session_state:
        return

    result = st.session_state.precision_result

    # Header stats
    col_info1, col_info2 = st.columns([1, 1])

    with col_info1:
        st.markdown(f"**Latency:** {result.latency_ms:.0f}ms")

    with col_info2:
        # Confidence Badge
        conf = result.confidence
        if conf > 0.8:
            badge = "✅ HIGH"
            color = "#28a745"
        elif conf > 0.5:
            badge = "⚡ MEDIUM"
            color = "#ffc107"
        else:
            badge = "⚠️ LOW"
            color = "#dc3545"
        st.markdown(
            f"**Confidence:** <span style='color:{color}'>{badge} ({conf:.2f})</span>",
            unsafe_allow_html=True,
        )

    # Warnings
    if result.warnings:
        for warning in result.warnings:
            st.warning(warning)

    # Graph Context (Phase 6)
    if result.graph_context:
        with st.expander("🕸️ Knowledge Graph Context", expanded=True):
            for fact in result.graph_context:
                st.markdown(f"- {fact}")

    st.divider()

    # Results
    if not result.chunks:
        st.warning("No results found.")
        return

    st.markdown(f"### 📊 Results ({len(result.chunks)} found)")

    for i, item in enumerate(result.chunks):
        with st.container():
            # Unified result item is SearchResult(chunk, score)
            # Use score as final score.
            # Dense/ColBERT breakdown lost in unified generic object unless we hack it back.
            _render_unified_card(item, i, st.session_state.precision_last_query)


def _render_unified_card(item, index: int, query: str):
    """Render a single result card."""
    chunk = item.chunk
    score = item.score

    # Card header
    source_title = chunk.metadata.get(
        "source_title", chunk.source_title or "Unknown Source"
    )
    title = f"{source_title}"
    if chunk.section_title:
        title = f"{chunk.section_title} • {title}"

    with st.expander(
        f"**{title}** (p.{chunk.page_start}) | Score: {score:.3f}", expanded=(index < 3)
    ):
        # Content with highlighting
        content = chunk.content
        for term in query.lower().split():
            if len(term) > 2:
                import re

                pattern = re.compile(re.escape(term), re.IGNORECASE)
                content = pattern.sub(f"**:orange[{term}]**", content)

        st.markdown(content[:800] + "..." if len(content) > 800 else content)

        # Actions
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("📋 Copy Citation", key=f"cite_u_{index}"):
                st.toast("Copied citation")
        with col_act2:
            if st.button("➕ Add to Synthesis", key=f"add_u_{index}"):
                if "selected_chunks" not in st.session_state:
                    st.session_state.selected_chunks = []
                st.session_state.selected_chunks.append(chunk)
                st.toast("Added to synthesis context")


def _render_image_thumbnail(img):
    """Render an image thumbnail."""
    from pathlib import Path

    img_path = Path(img.file_path) if hasattr(img, "file_path") else None

    if img_path and img_path.exists():
        try:
            st.image(str(img_path), width="stretch")
        except Exception:
            st.markdown("🖼️ *Preview unavailable*")
    else:
        st.markdown("🖼️ *Image not found*")

    caption = getattr(img, "caption", "") or getattr(img, "llm_caption", "")
    if caption:
        st.caption(caption[:50] + "..." if len(caption) > 50 else caption)
