import re
from pathlib import Path
from typing import Optional

import streamlit as st
from rapidfuzz import fuzz

from src.index import Database
from src.ui import styles
from src.ui.search_results import (
    add_to_search_history,
    get_search_history,
    group_results_hierarchically,
    init_search_history,
    render_advanced_search_panel,
    render_hierarchical_results,
    render_sort_controls,
    sort_results,
)
from src.ui.visual_search import (
    render_enhanced_figure_gallery,
    render_visual_search_panel,
)


def _normalize_text(text: str) -> str:
    """
    Normalize text for fuzzy matching.
    Removes symbols, normalizes whitespace, lowercases.
    """
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Replace common separators with spaces
    text = re.sub(r"[-_.,;:()[\]{}'\"/\\]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fuzzy_match_source(
    query: str,
    title: str,
    authors: str | None = None,
    threshold: int = 60,
) -> tuple[bool, float]:
    """
    Check if query fuzzy-matches title or authors.

    Args:
        query: Search query (already normalized)
        title: Source title
        authors: Optional authors string
        threshold: Minimum score to consider a match (0-100)

    Returns:
        Tuple of (is_match, best_score)
    """
    norm_title = _normalize_text(title)
    norm_authors = _normalize_text(authors) if authors else ""

    # Combine title and authors for matching
    combined = f"{norm_title} {norm_authors}".strip()

    # Split into words for word-level matching
    title_words = norm_title.split()
    query_words = query.split()

    scores = []

    # 1. Exact substring match - highest priority
    if query in norm_title:
        scores.append(100.0)
    if query in norm_authors:
        scores.append(100.0)

    # 2. Word prefix matching - important for short queries
    for qword in query_words:
        for tword in title_words:
            if tword.startswith(qword):
                # Longer match = higher score
                match_ratio = len(qword) / max(len(tword), 1)
                scores.append(85.0 + 15.0 * match_ratio)

    # 3. For multi-word queries, use token-based matching
    if len(query_words) > 1:
        scores.append(fuzz.token_set_ratio(query, norm_title))
        scores.append(fuzz.token_set_ratio(query, combined))
        scores.append(fuzz.token_sort_ratio(query, norm_title))

    # 4. Partial ratio for longer queries (>=4 chars) - allows typo tolerance
    if len(query) >= 4:
        scores.append(fuzz.partial_ratio(query, norm_title) * 0.9)  # Slightly discount
        scores.append(fuzz.partial_ratio(query, combined) * 0.9)

    # 5. Full fuzzy ratio for longer queries - good for typos
    if len(query) >= 5:
        # Use ratio for fuzzy matching with typo tolerance
        scores.append(fuzz.ratio(query, norm_title) * 0.85)
        # Author matching
        if norm_authors:
            scores.append(fuzz.partial_ratio(query, norm_authors))

    best_score = max(scores) if scores else 0.0
    return best_score >= threshold, best_score


def render_library():
    """
    Renders the Reference Library module.
    Features: Source Grid, Search/Filter, Detail View, Visual Search.
    """
    st.markdown("## 📚 Reference Library")

    # Initialize DB
    try:
        if "db" not in st.session_state:
            st.session_state.db = Database()
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return

    # Handle re-indexing request
    if "reindex_source" in st.session_state:
        source_id = st.session_state.reindex_source
        del st.session_state.reindex_source

        source = st.session_state.db.get_source(source_id)
        if source and source.file_path:
            with st.spinner(f"Re-indexing {source.title}..."):
                try:
                    from pathlib import Path

                    from src.ingest.processor import DocumentProcessor

                    processor = DocumentProcessor(
                        chunk_size=st.session_state.get("ingest_chunk_size", 1500),
                        chunk_overlap=st.session_state.get("ingest_chunk_overlap", 200),
                        entropy_threshold=st.session_state.get(
                            "ingest_entropy_threshold", 4.5
                        ),
                        text_embedding_model=st.session_state.get(
                            "ingest_text_model", "voyage-3-lite"
                        ),
                        image_embedding_model=st.session_state.get(
                            "ingest_image_model", "colpali-v1.2"
                        ),
                    )
                    # Process to reprocess existing document
                    result = processor.process(Path(source.file_path))

                    if result:
                        st.success(
                            f"✅ Re-indexed successfully! Processed {result.get('chunks', 0)} chunks and {result.get('images', 0)} images."
                        )
                    else:
                        st.warning("Re-indexing completed but no result returned")

                except Exception as e:
                    st.error(f"Re-indexing failed: {e}")
                    import traceback

                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
        else:
            st.error("Source file not found")

    # Handle detail view (outside tabs)
    if "selected_source" in st.session_state and st.session_state.selected_source:
        render_detail_view(st.session_state.selected_source)
        return

    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📖 Sources",
            "🔍 Text Search",
            "🎯 Precision Search",
            "🖼️ Visual Search",
            "📥 Ingestion",
            "🔬 Inspector",
        ]
    )

    with tab1:
        _render_sources_tab()

    with tab2:
        _render_text_search_tab()

    with tab3:
        _render_precision_search_tab()

    with tab4:
        render_visual_search_panel()

    with tab5:
        _render_ingestion_dashboard()

    with tab6:
        _render_inspector_panel()


def _render_precision_search_tab():
    """Render the Deep-DX precision search tab."""
    from src.ui.precision_search import render_precision_search_panel

    render_precision_search_panel()


def _render_inspector_panel():
    """Render the chunk and image inspector panel (P2 implementation)."""
    st.markdown("### 🔬 Content Inspector")
    st.caption("Inspect indexed chunks and images with embedding/Qdrant status")

    db = st.session_state.get("db")
    if not db:
        st.warning("Database not initialized")
        return

    # Sub-tabs for chunks vs images
    chunk_tab, image_tab, sync_tab = st.tabs(
        ["📄 Text Chunks", "🖼️ Images", "☁️ Qdrant Sync"]
    )

    with chunk_tab:
        _render_chunk_inspector(db)

    with image_tab:
        _render_image_inspector(db)

    with sync_tab:
        _render_qdrant_sync_inspector(db)


def _render_chunk_inspector(db):
    """Render the text chunk inspector."""
    st.markdown("#### 📄 Text Chunk Inspector")

    # Get all sources for filtering
    sources = db.get_all_sources() or []
    source_options = {"All Sources": None}
    source_options.update({s.title: s.id for s in sources})

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        selected_source = st.selectbox(
            "Filter by Source",
            options=list(source_options.keys()),
            key="chunk_inspector_source",
        )

    with col2:
        show_embedded = st.selectbox(
            "Embedding Status",
            options=["All", "Embedded ✅", "Not Embedded ❌"],
            key="chunk_inspector_embed",
        )

    with col3:
        page_size = st.selectbox(
            "Items per page", [10, 25, 50, 100], index=1, key="chunk_page_size"
        )

    # Search chunks
    search_query = st.text_input("🔍 Search content", key="chunk_inspector_search")

    # Get chunks with filters
    source_id = source_options.get(selected_source)
    all_chunks = (
        db.get_chunks_by_source(source_id) if source_id else db.get_all_chunks()
    )

    if not all_chunks:
        st.info("No chunks found. Index some PDFs first.")
        return

    # Apply filters
    filtered_chunks = all_chunks
    if search_query:
        filtered_chunks = [
            c for c in filtered_chunks if search_query.lower() in c.content.lower()
        ]

    if show_embedded == "Embedded ✅":
        filtered_chunks = [c for c in filtered_chunks if c.embedding]
    elif show_embedded == "Not Embedded ❌":
        filtered_chunks = [c for c in filtered_chunks if not c.embedding]

    # Stats
    total = len(all_chunks)
    embedded = sum(1 for c in all_chunks if c.embedding)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Chunks", total)
    col2.metric(
        "Embedded",
        f"{embedded}/{total}",
        f"{(embedded/total*100) if total else 0:.1f}%",
    )
    col3.metric("Filtered", len(filtered_chunks))

    # Pagination
    total_pages = max(1, (len(filtered_chunks) + page_size - 1) // page_size)
    page = st.number_input(
        "Page", min_value=1, max_value=total_pages, value=1, key="chunk_page"
    )
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_chunks = filtered_chunks[start_idx:end_idx]

    # Display chunks
    for chunk in page_chunks:
        embed_icon = "✅" if chunk.embedding else "❌"
        dim_info = f" ({len(chunk.embedding)}d)" if chunk.embedding else ""
        with st.expander(
            f"{embed_icon} Chunk {chunk.id[:8]}...{dim_info} - {chunk.content[:60]}..."
        ):
            st.markdown(f"**Source:** {chunk.source_id}")
            st.markdown(f"**Type:** {chunk.chunk_type}")
            st.markdown(f"**Embedding:** {embed_icon} {dim_info}")
            st.text_area(
                "Content",
                chunk.content,
                height=150,
                disabled=True,
                key=f"chunk_{chunk.id}",
            )


def _render_image_inspector(db):
    """Render the image inspector."""
    st.markdown("#### 🖼️ Image Inspector")

    # Get all sources for filtering
    sources = db.get_all_sources() or []
    source_options = {"All Sources": None}
    source_options.update({s.title: s.id for s in sources})

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        selected_source = st.selectbox(
            "Filter by Source",
            options=list(source_options.keys()),
            key="image_inspector_source",
        )

    with col2:
        show_embedded = st.selectbox(
            "Embedding Status",
            options=["All", "Embedded ✅", "Not Embedded ❌"],
            key="image_inspector_embed",
        )

    with col3:
        page_size = st.selectbox(
            "Items per page", [6, 12, 24, 48], index=1, key="image_page_size"
        )

    # Get images with filters
    source_id = source_options.get(selected_source)
    all_images = (
        db.get_images_by_source(source_id) if source_id else db.get_all_images()
    )

    if not all_images:
        st.info("No images found. Index some PDFs with image extraction first.")
        return

    # Apply filters
    filtered_images = all_images
    if show_embedded == "Embedded ✅":
        filtered_images = [img for img in filtered_images if img.embedding]
    elif show_embedded == "Not Embedded ❌":
        filtered_images = [img for img in filtered_images if not img.embedding]

    # Stats
    total = len(all_images)
    embedded = sum(1 for img in all_images if img.embedding)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Images", total)
    col2.metric(
        "Embedded (BiomedCLIP)",
        f"{embedded}/{total}",
        f"{(embedded/total*100) if total else 0:.1f}%",
    )
    col3.metric("Filtered", len(filtered_images))

    # Pagination
    total_pages = max(1, (len(filtered_images) + page_size - 1) // page_size)
    page = st.number_input(
        "Page", min_value=1, max_value=total_pages, value=1, key="image_page"
    )
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_images = filtered_images[start_idx:end_idx]

    # Display images in grid (3 per row)
    cols_per_row = 3
    for i in range(0, len(page_images), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(page_images):
                img = page_images[i + j]
                with col:
                    embed_icon = "✅" if img.embedding else "❌"
                    dim_info = f" ({len(img.embedding)}d)" if img.embedding else ""

                    # Show thumbnail if path exists
                    if img.file_path and Path(img.file_path).exists():
                        st.image(str(img.file_path), width="stretch")
                    else:
                        st.info("🖼️ No image file")

                    st.caption(f"{embed_icon}{dim_info} Page {img.page}")
                    if img.caption:
                        st.caption(f"📝 {img.caption[:50]}...")


def _render_qdrant_sync_inspector(db):
    """Render the Qdrant sync verification panel."""
    from src.config import settings

    st.markdown("#### ☁️ Qdrant Sync Verification")
    st.caption("Compare SQLite counts with Qdrant vector store counts")

    # Get SQLite counts
    all_chunks = db.get_all_chunks()
    all_images = db.get_all_images()

    sqlite_chunks_total = len(all_chunks) if all_chunks else 0
    sqlite_chunks_embedded = (
        sum(1 for c in all_chunks if c.embedding) if all_chunks else 0
    )
    sqlite_images_total = len(all_images) if all_images else 0
    sqlite_images_embedded = (
        sum(1 for img in all_images if img.embedding) if all_images else 0
    )

    # Get Qdrant counts
    qdrant_chunks = 0
    qdrant_images = 0
    qdrant_error = None

    try:
        from qdrant_client import QdrantClient

        if settings.qdrant_url:
            client = QdrantClient(url=str(settings.qdrant_url))
        else:
            qdrant_path = (
                str(settings.qdrant_path) if settings.qdrant_path else "./.qdrant_data"
            )
            client = QdrantClient(path=qdrant_path)

        # Text chunks collection
        try:
            text_info = client.get_collection(settings.qdrant_collection_name)
            qdrant_chunks = text_info.points_count
        except Exception:
            pass

        # Image collection
        try:
            image_info = client.get_collection(settings.image_qdrant_collection)
            qdrant_images = image_info.points_count
        except Exception:
            pass

    except Exception as e:
        qdrant_error = str(e)

    if qdrant_error:
        st.error(f"Qdrant connection error: {qdrant_error}")
        return

    # Display comparison
    st.markdown("##### 📊 Sync Status")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📄 Text Chunks**")
        chunks_synced = sqlite_chunks_embedded == qdrant_chunks

        st.metric("SQLite Total", sqlite_chunks_total)
        st.metric("SQLite (embedded)", sqlite_chunks_embedded)
        st.metric("Qdrant Points", qdrant_chunks)

        if chunks_synced:
            st.success("✅ Text chunks in sync")
        else:
            diff = sqlite_chunks_embedded - qdrant_chunks
            if diff > 0:
                st.warning(f"⚠️ {diff} chunks not pushed to Qdrant")
            else:
                st.warning(f"⚠️ Qdrant has {-diff} extra points (stale data?)")

    with col2:
        st.markdown("**🖼️ Images**")
        images_synced = sqlite_images_embedded == qdrant_images

        st.metric("SQLite Total", sqlite_images_total)
        st.metric("SQLite (embedded)", sqlite_images_embedded)
        st.metric("Qdrant Points", qdrant_images)

        if images_synced:
            st.success("✅ Images in sync")
        else:
            diff = sqlite_images_embedded - qdrant_images
            if diff > 0:
                st.warning(f"⚠️ {diff} images not pushed to Qdrant")
            else:
                st.warning(f"⚠️ Qdrant has {-diff} extra points (stale data?)")

    # Collection info
    st.markdown("##### 📁 Collection Info")
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            f"**Text Collection:** `{settings.qdrant_collection_name}`\n\nVector dim: 1024 (VoyageAI)"
        )
    with col2:
        st.info(
            f"**Image Collection:** `{settings.image_qdrant_collection}`\n\nVector dim: 512 (BiomedCLIP)"
        )


def _render_text_search_tab():
    """Render the advanced text search tab with hierarchical results."""
    st.markdown("### 🔍 Advanced Text Search")
    st.caption("Search across all indexed content with hierarchical results")

    init_search_history()

    # Search input
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input(
            "Search",
            placeholder="Enter search term (e.g., 'pterional craniotomy', 'middle cerebral artery')",
            key="library_search_query",
            label_visibility="collapsed",
        )
    with col2:
        search_clicked = st.button(
            "🔍 Search", key="library_search_btn", width="stretch"
        )

    # Search history
    history = get_search_history()
    if history:
        with st.expander("📜 Recent Searches", expanded=False):
            selected = st.selectbox(
                "Select from history",
                options=[""] + history[:10],
                key="library_history_select",
                label_visibility="collapsed",
            )
            if selected:
                query = selected

    if not query:
        st.info("Enter a search term to find relevant content across all sources")
        return

    # Perform search
    if search_clicked or query:
        add_to_search_history(query)

        with st.spinner("Searching..."):
            try:
                from src.index import SearchEngine
                from src.neurosynth.llm.embeddings import EmbeddingClient

                db = st.session_state.db
                search_engine = SearchEngine(db)
                embedding_client = EmbeddingClient()

                # Generate embedding and search
                query_embedding = embedding_client.embed(query)
                results = search_engine.search_chunks(
                    query_embedding=query_embedding, top_k=50
                )

                if not results:
                    st.warning("No results found. Try different search terms.")
                    return

                st.session_state["library_search_results"] = results
                st.session_state["library_search_query"] = query

            except Exception as e:
                st.error(f"Search failed: {e}")
                return

    # Display results
    results = st.session_state.get("library_search_results", [])
    current_query = st.session_state.get("library_search_query", query)

    if not results:
        return

    # Sort controls
    sort_by, ascending, tree_view = render_sort_controls()

    # Sort results
    sorted_results = sort_results(results, sort_by, ascending)

    # Render based on view mode
    if tree_view:
        hierarchy = group_results_hierarchically(sorted_results, st.session_state.db)
        render_hierarchical_results(
            hierarchy,
            query=current_query,
            on_select=_on_result_select,
            show_thumbnails=True,
        )
    else:
        from src.ui.search_results import render_flat_results

        render_flat_results(
            sorted_results, query=current_query, on_select=_on_result_select
        )


def _render_ingestion_dashboard():
    """Render the document ingestion dashboard with advanced configuration."""
    st.markdown("### 📥 Document Ingestion")
    st.caption("Process new documents and monitor ingestion status")

    # Check for pending bulk indexing from auto-sync
    if "pending_bulk_index" in st.session_state and st.session_state.pending_bulk_index:
        pending_files = st.session_state.pending_bulk_index
        st.warning(f"📥 {len(pending_files)} new file(s) detected by auto-sync daemon")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("**Files ready for indexing:**")
            for pdf_path in pending_files[:5]:  # Show first 5
                st.text(f"  • {pdf_path.name}")
            if len(pending_files) > 5:
                st.text(f"  ... and {len(pending_files) - 5} more")

        with col2:
            if st.button("🚀 Index All Now", type="primary", width="stretch"):
                st.session_state.auto_index_in_progress = True
                st.rerun()

        if st.button("Clear Queue"):
            st.session_state.pending_bulk_index = []
            st.success("Queue cleared")
            st.rerun()

        st.divider()

    # Handle actual indexing from auto-sync queue
    if st.session_state.get("auto_index_in_progress", False):
        _process_pending_bulk_index()
        st.session_state.auto_index_in_progress = False
        st.session_state.pending_bulk_index = []
        st.rerun()

    # Advanced Configuration in Expander
    with st.expander("⚙️ Ingestion Configuration", expanded=False):
        _render_ingestion_config()

    st.divider()

    # Ingestion Controls
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info("Place PDF files in the `data/library` directory to be detected.")

    with col2:
        if st.button("🚀 Process New Files", type="primary", width="stretch"):
            _run_ingestion_with_config()

    st.divider()

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Status", "🔧 Index Health", "📈 API Health", "🖼️ Captions"]
    )

    with tab1:
        _render_library_status()

    with tab2:
        _render_index_health_dashboard()

    with tab3:
        _render_api_health_dashboard()

    with tab4:
        _render_caption_preview()


def _render_ingestion_config():
    """Render chunking and entropy configuration sliders."""
    from src.config import settings

    st.markdown("##### 📄 Chunking Configuration")
    col1, col2 = st.columns(2)

    with col1:
        chunk_size = st.slider(
            "Chunk Size (characters)",
            min_value=500,
            max_value=4000,
            value=st.session_state.get("ingest_chunk_size", settings.chunk_size),
            step=100,
            help="Target size for each text chunk. Larger = more context, fewer chunks.",
        )
        st.session_state["ingest_chunk_size"] = chunk_size

    with col2:
        chunk_overlap = st.slider(
            "Chunk Overlap (characters)",
            min_value=0,
            max_value=500,
            value=st.session_state.get("ingest_chunk_overlap", settings.chunk_overlap),
            step=25,
            help="Overlap between consecutive chunks. Higher = better continuity.",
        )
        st.session_state["ingest_chunk_overlap"] = chunk_overlap

    st.markdown("##### 🖼️ Image Entropy Threshold")
    entropy_threshold = st.slider(
        "Minimum Entropy (Shannon)",
        min_value=2.0,
        max_value=7.0,
        value=st.session_state.get("ingest_entropy_threshold", 3.0),
        step=0.1,
        help="Images below this entropy are filtered out (icons, spacers). Range: 4.0-5.0 recommended.",
    )
    st.session_state["ingest_entropy_threshold"] = entropy_threshold

    st.markdown("##### 🧠 Embedding Model Selection")
    col1, col2 = st.columns(2)

    with col1:
        text_model = st.selectbox(
            "Text Embedding Model",
            options=["voyage-3-lite", "voyage-3", "voyage-code-3", "all-MiniLM-L6-v2"],
            index=0,
            help="voyage-3-lite: Fast, good quality | voyage-3: Best quality | SBERT: Local, no API",
        )
        st.session_state["ingest_text_model"] = text_model

    with col2:
        image_model = st.selectbox(
            "Image Embedding Model",
            options=["biomedclip", "colpali-v1.2", "clip-vit-large-patch14", "none"],
            index=0,
            help="BiomedCLIP: Medical images (512-dim) | ColPali: Documents | CLIP: General | None: Skip",
        )
        st.session_state["ingest_image_model"] = image_model

    st.markdown("##### 🦖 Advanced RAG Configuration (Phase 2+)")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        enable_prop = st.checkbox(
            "Use Proposition Chunker",
            value=st.session_state.get(
                "ingest_enable_proposition", settings.enable_proposition_chunker
            ),
            help="Small-to-Big retrieval: Splits by sentence, returns full usage context.",
        )
        st.session_state["ingest_enable_proposition"] = enable_prop

    with col_b:
        enable_raptor = st.checkbox(
            "Enable RAPTOR Summaries",
            value=st.session_state.get("ingest_enable_raptor", settings.enable_raptor),
            help="Recursive Summarization: Creates tree of summaries for high-level reasoning. (Slow)",
        )
        st.session_state["ingest_enable_raptor"] = enable_raptor

    with col_c:
        enable_graph = st.checkbox(
            "Enable GraphRAG",
            value=st.session_state.get(
                "ingest_enable_graph", settings.enable_graph_rag
            ),
            help="Knowledge Graph: Extracts entities and relations. (Slow)",
        )
        st.session_state["ingest_enable_graph"] = enable_graph

    st.markdown("##### ☁️ Qdrant Vector Store")
    col_q1, col_q2 = st.columns(2)

    with col_q1:
        enable_qdrant_push = st.checkbox(
            "Push Text Chunks to Qdrant",
            value=st.session_state.get(
                "ingest_enable_qdrant_push", settings.enable_qdrant_push
            ),
            help="Enable to push text chunks to Qdrant for vector search.",
        )
        st.session_state["ingest_enable_qdrant_push"] = enable_qdrant_push

    with col_q2:
        enable_image_qdrant_push = st.checkbox(
            "Push Images to Qdrant",
            value=st.session_state.get(
                "ingest_enable_image_qdrant_push", settings.enable_image_qdrant_push
            ),
            help="Enable to push BiomedCLIP image embeddings to Qdrant.",
        )
        st.session_state["ingest_enable_image_qdrant_push"] = enable_image_qdrant_push

    st.markdown("##### 👁️ Advanced Vision Configuration (Refinement)")
    col_x, col_y, col_z = st.columns(3)

    with col_x:
        enable_yolo = st.checkbox(
            "Enable Object Detection",
            value=st.session_state.get(
                "ingest_enable_yolo", settings.enable_object_detection
            ),
            help="YOLOv8: Detects scans, instruments, and diagrams in figures.",
        )
        st.session_state["ingest_enable_yolo"] = enable_yolo

    with col_y:
        enable_layout = st.checkbox(
            "Enable Layout Analysis",
            value=st.session_state.get(
                "ingest_enable_layout", settings.enable_layout_analysis
            ),
            help="LayoutLMv3: Analyzes page structure (tables, sidebars).",
        )
        st.session_state["ingest_enable_layout"] = enable_layout

    with col_z:
        enable_vlm = st.checkbox(
            "Enable VLM Verification",
            value=st.session_state.get(
                "ingest_enable_vlm", settings.enable_vlm_verification
            ),
            help="Claude 3.5: Verifies image-caption consistency.",
        )
        st.session_state["ingest_enable_vlm"] = enable_vlm

    st.markdown("##### ⚡ Phase 4: Integrated Content Extraction")
    col_p4_1, col_p4_2 = st.columns(2)

    with col_p4_1:
        enable_vector = st.checkbox(
            "Extract Vector Graphics",
            value=st.session_state.get("ingest_enable_vector", False),
            help="Extract flowcharts, diagrams, and other vector graphics from PDFs.",
        )
        st.session_state["ingest_enable_vector"] = enable_vector

    with col_p4_2:
        enable_xrefs = st.checkbox(
            "Track Cross-References",
            value=st.session_state.get("ingest_enable_xrefs", False),
            help="Track 'see Figure 3' references to link chunks with images.",
        )
        st.session_state["ingest_enable_xrefs"] = enable_xrefs


def _run_ingestion_with_config():
    """Run ingestion with configured parameters."""
    with st.status("Processing Documents...", expanded=True) as status:
        try:
            from pathlib import Path

            from src.ingest.processor import DocumentProcessor

            # Get config from session state
            chunk_size = st.session_state.get("ingest_chunk_size", 1500)
            chunk_overlap = st.session_state.get("ingest_chunk_overlap", 200)
            entropy_threshold = st.session_state.get("ingest_entropy_threshold", 4.5)
            text_model = st.session_state.get("ingest_text_model", "voyage-3-lite")
            image_model = st.session_state.get("ingest_image_model", "colpali-v1.2")

            # Advanced Config
            use_proposition = st.session_state.get("ingest_enable_proposition", True)
            use_raptor = st.session_state.get("ingest_enable_raptor", False)
            use_graph = st.session_state.get("ingest_enable_graph", False)

            # Refinement Config
            use_yolo = st.session_state.get("ingest_enable_yolo", False)
            use_layout = st.session_state.get("ingest_enable_layout", False)
            use_vlm = st.session_state.get("ingest_enable_vlm", False)
            use_vector = st.session_state.get("ingest_enable_vector", False)
            use_xrefs = st.session_state.get("ingest_enable_xrefs", False)

            # HACK: Patch global settings temporarily for ingestion run because Processor reads from settings in sub-modules
            # Ideally Processor should take these as init args.
            from src import config

            old_yolo = config.settings.enable_object_detection
            old_layout = config.settings.enable_layout_analysis
            old_vlm = config.settings.enable_vlm_verification

            config.settings.enable_object_detection = use_yolo
            config.settings.enable_layout_analysis = use_layout
            config.settings.enable_vlm_verification = use_vlm

            # Initialize processor with configured values
            processor = DocumentProcessor(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                entropy_threshold=entropy_threshold,
                text_embedding_model=text_model,
                image_embedding_model=image_model,
                enable_vector_graphics=use_vector,
                enable_cross_references=use_xrefs,
            )

            st.write(f"📐 Chunk size: {chunk_size}, overlap: {chunk_overlap}")
            st.write(f"🖼️ Entropy threshold: {entropy_threshold}")
            st.write(f"📝 Text embeddings: {text_model}")
            st.write(f"🎨 Image embeddings: {image_model}")

            library_path = Path(
                st.session_state.get("library_path", settings.library_path)
            )
            if not library_path.exists():
                library_path.mkdir(parents=True, exist_ok=True)
                st.warning(f"Created {library_path}. Please add PDFs there.")

            pdf_files = list(library_path.glob("*.pdf"))
            if not pdf_files:
                st.warning("No PDFs found in data/library")
                status.update(label="⚠️ No files found", state="complete")
                return

            progress_bar = st.progress(0)
            results_table = []

            # Initialize chunker
            if use_proposition:
                from src.index.proposition_chunker import PropositionChunker

                chunker = PropositionChunker()
            else:
                from src.index.chunker import SemanticChunker

                chunker = SemanticChunker(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )

            # Initialize Advanced RAG Components
            raptor = None
            graph_builder = None
            ai_client = None

            if use_raptor or use_graph:
                from src.ai.client import AIClient

                ai_client = AIClient()

            if use_raptor:

                from src.index.raptor import RecursiveSummarizer

                raptor = RecursiveSummarizer(ai_client, st.session_state.db)

            if use_graph:
                from src.index.graph import KnowledgeGraphBuilder

                graph_builder = KnowledgeGraphBuilder(ai_client)

            progress_bar = st.progress(0)
            results_table = []

            import asyncio

            for i, pdf_path in enumerate(pdf_files):
                st.write(f"📄 Processing {pdf_path.name}...")

                try:
                    # Process PDF (extract text, sections, images)
                    result = processor.process(pdf_path)

                    # Create chunks
                    if use_proposition:
                        # PropositionChunker expects Section objects or logic
                        # But loop creates chunks from result (Document).
                        # Need adapter logic if chunk interfaces differ.
                        # PropositionChunker.chunk_document IS available?
                        # Let's check PropositionChunker definition. assuming generic interface match for query
                        # If not, we might need to iterate pages/sections like Bridge does.
                        # processor.process returns a Document object with .sections and .pages
                        # PropositionChunker has chunk_section() but maybe not chunk_document?
                        # Bridge iterates manually. Let's do same or rely on method if exists.
                        # Let's assume we iterate if needed.

                        # Bridge logic:
                        chunks = []
                        # Create a pseudo-section for the whole doc or per-page if sections missing
                        # DocumentProcessor usually returns sections if Layout extraction worked.
                        # If not, result.pages is a dict.

                        # Let's try to leverage existing chunks or pages
                        # The simplest path for UI quick win:
                        # If result has sections, chunk them. If not, chunk pages.

                        if hasattr(result, "sections") and result.sections:
                            for section in result.sections:
                                chunks.extend(
                                    chunker.chunk_section(
                                        section,
                                        result.metadata.id,
                                        result.metadata.title,
                                    )
                                )
                        else:
                            # Fallback to page iteration
                            from src.models import Section

                            for page_num, text in result.pages.items():
                                if len(text) > 50:
                                    sec = Section(
                                        title=result.metadata.title,
                                        level=1,
                                        page_start=page_num,
                                        page_end=page_num,
                                        content=text,
                                        images=[],
                                    )
                                    chunks.extend(
                                        chunker.chunk_section(
                                            sec,
                                            result.metadata.id,
                                            result.metadata.title,
                                        )
                                    )
                    else:
                        # Standard Semantic Chunker
                        chunks = chunker.chunk_document(result)

                    # Store in database
                    st.session_state.db.insert_source(result.metadata)
                    st.session_state.db.insert_chunks(chunks)

                    # Store images
                    for img in result.images:
                        st.session_state.db.insert_image(img)

                    # ---------------------------------------------------------
                    # Advanced RAG Execution
                    # ---------------------------------------------------------
                    async def run_advanced_rag():
                        nonlocal chunks
                        # RAPTOR
                        if use_raptor and raptor:
                            st.write("  🦖 Running RAPTOR...")
                            summaries = await raptor.generate_tree(chunks)
                            if summaries:
                                st.session_state.db.insert_chunks(summaries)
                                chunks.extend(
                                    summaries
                                )  # Add to chunks for BM25/Vector updates?
                                # Maybe don't extend if we don't want summaries in standard index
                                # But usually we do.

                        # GraphRAG
                        if use_graph and graph_builder:
                            st.write("  🕸️ Building Knowledge Graph...")
                            await graph_builder.process_chunks(chunks)
                            # Save graph immediately? Or at end?
                            # UI is per-file. We should load/save graph incrementally?
                            # Simple approach: Load global graph, update, save.
                            # For now, just process. Persistence might need explicit save call.

                    if use_raptor or use_graph:
                        asyncio.run(run_advanced_rag())

                    # ---------------------------------------------------------

                    # Update BM25 index for hybrid search
                    if (
                        "precision_engine" in st.session_state
                        and st.session_state.precision_engine
                    ):
                        st.session_state.precision_engine.update_bm25_index(chunks)

                    results_table.append(
                        {
                            "File": pdf_path.name,
                            "Status": "✅ Success",
                            "Pages": (
                                result.metadata.total_pages
                                if hasattr(result, "metadata")
                                else "?"
                            ),
                            "Chunks": len(chunks),
                        }
                    )
                except Exception as e:
                    results_table.append(
                        {
                            "File": pdf_path.name,
                            "Status": f"❌ Failed: {str(e)[:30]}",
                            "Pages": "-",
                            "Chunks": "-",
                        }
                    )

                progress_bar.progress((i + 1) / len(pdf_files))

            # Store results for display
            st.session_state["last_ingestion_results"] = results_table
            status.update(
                label=f"✅ Processed {len(pdf_files)} documents!", state="complete"
            )
            st.balloons()
            st.rerun()

        except Exception as e:
            st.error(f"Ingestion failed: {e}")
            status.update(label="❌ Ingestion Failed", state="error")


def _process_pending_bulk_index():
    """Process files from auto-sync queue."""
    pending = st.session_state.get("pending_bulk_index", [])
    if not pending:
        return

    with st.status("Processing Auto-Sync Queue...", expanded=True) as status:
        try:
            from pathlib import Path

            from src.index.chunker import SemanticChunker
            from src.ingest.processor import DocumentProcessor

            # Get config from session state
            chunk_size = st.session_state.get("ingest_chunk_size", 1500)
            chunk_overlap = st.session_state.get("ingest_chunk_overlap", 200)
            entropy_threshold = st.session_state.get("ingest_entropy_threshold", 4.5)
            text_model = st.session_state.get("ingest_text_model", "voyage-3-lite")
            image_model = st.session_state.get("ingest_image_model", "colpali-v1.2")

            # Initialize processor with configured values
            processor = DocumentProcessor(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                entropy_threshold=entropy_threshold,
                text_embedding_model=text_model,
                image_embedding_model=image_model,
            )

            # Initialize chunker
            chunker = SemanticChunker(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )

            progress_bar = st.progress(0)
            results_table = []

            for i, pdf_path in enumerate(pending):
                st.write(f"📄 Processing {pdf_path.name}...")

                try:
                    # Process PDF
                    result = processor.process(Path(pdf_path))

                    # Create chunks
                    chunks = chunker.chunk_document(result)

                    # Store in database
                    st.session_state.db.insert_source(result.metadata)
                    st.session_state.db.insert_chunks(chunks)

                    # Update BM25 index for hybrid search
                    if (
                        "precision_engine" in st.session_state
                        and st.session_state.precision_engine
                    ):
                        st.session_state.precision_engine.update_bm25_index(chunks)

                    # Store images
                    for img in result.images:
                        st.session_state.db.insert_image(img)

                    results_table.append(
                        {
                            "File": pdf_path.name,
                            "Status": "✅ Success",
                            "Pages": (
                                result.metadata.total_pages
                                if hasattr(result, "metadata")
                                else "?"
                            ),
                            "Chunks": len(chunks),
                        }
                    )

                except Exception as e:
                    results_table.append(
                        {
                            "File": pdf_path.name,
                            "Status": f"❌ Failed: {str(e)[:50]}",
                            "Pages": "-",
                            "Chunks": "-",
                        }
                    )

                progress_bar.progress((i + 1) / len(pending))

            # Store results
            st.session_state["last_ingestion_results"] = results_table
            status.update(
                label=f"✅ Processed {len(pending)} document(s) from auto-sync queue!",
                state="complete",
            )
            st.success(
                f"Indexed {len([r for r in results_table if '✅' in r['Status']])} of {len(pending)} files"
            )

        except Exception as e:
            st.error(f"Auto-sync processing failed: {e}")
            status.update(label="❌ Auto-Sync Failed", state="error")


def _render_library_status():
    """Render library status with per-document ingestion status."""
    st.markdown("#### 📊 Library Status")

    try:
        sources = st.session_state.db.get_all_sources()

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", len(sources))
        with col2:
            total_pages = sum(s.total_pages for s in sources)
            st.metric("Total Pages", total_pages)
        with col3:
            stats = st.session_state.db.get_stats()
            st.metric("Total Chunks", stats.get("chunks", 0))

        # Per-document status table with success/failure icons
        st.markdown("##### 📋 Per-Document Status")
        data = []
        for s in sources:
            # Check if has embeddings
            chunks_with_emb = _count_source_embeddings(s.id)
            total_chunks = _count_source_chunks(s.id)

            if total_chunks == 0:
                embed_status = "⚠️ No chunks"
            elif chunks_with_emb == total_chunks:
                embed_status = "✅ Complete"
            elif chunks_with_emb > 0:
                embed_status = f"🟡 Partial ({chunks_with_emb}/{total_chunks})"
            else:
                embed_status = "❌ No embeddings"

            data.append(
                {
                    "Title": s.title[:40] + "..." if len(s.title) > 40 else s.title,
                    "Pages": s.total_pages,
                    "Specialty": s.specialty.value,
                    "Embed Status": embed_status,
                    "Added": (
                        s.created_at.strftime("%Y-%m-%d")
                        if hasattr(s, "created_at") and s.created_at
                        else "N/A"
                    ),
                }
            )

        if data:
            st.dataframe(data, width="stretch", hide_index=True)

        # Show last ingestion results if available
        if "last_ingestion_results" in st.session_state:
            with st.expander("📋 Last Ingestion Results"):
                st.dataframe(
                    st.session_state["last_ingestion_results"],
                    width="stretch",
                    hide_index=True,
                )

    except Exception as e:
        st.error(f"Failed to load status: {e}")


def _count_source_embeddings(source_id: str) -> int:
    """Count chunks with embeddings for a source."""
    try:
        with st.session_state.db._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM chunks WHERE source_id = ? AND embedding IS NOT NULL",
                (source_id,),
            ).fetchone()
            return row["c"] if row else 0
    except:
        return 0


def _count_source_chunks(source_id: str) -> int:
    """Count total chunks for a source."""
    try:
        with st.session_state.db._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM chunks WHERE source_id = ?", (source_id,)
            ).fetchone()
            return row["c"] if row else 0
    except:
        return 0


def _render_index_health_dashboard():
    """Render multi-index status dashboard (SQLite, FAISS, Qdrant)."""
    st.markdown("#### 🔧 Index Health Dashboard")

    # SQLite Stats
    st.markdown("##### 📦 SQLite Database")
    try:
        stats = st.session_state.db.get_stats()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sources", stats.get("sources", 0))
        with col2:
            st.metric("Chunks", stats.get("chunks", 0))
        with col3:
            st.metric("Images", stats.get("images", 0))

        # DB file size
        from pathlib import Path

        from src.config import settings

        db_path = settings.database_path
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            st.caption(f"Database size: {size_mb:.2f} MB")
    except Exception as e:
        st.error(f"SQLite stats failed: {e}")

    st.divider()

    # FAISS Stats (if available)
    st.markdown("##### 🔍 FAISS Index Statistics")
    try:
        faiss_stats = _get_faiss_stats()
        if faiss_stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Vectors (ntotal)", faiss_stats.get("ntotal", 0))
            with col2:
                st.metric("Dimension", faiss_stats.get("dimension", 0))
            with col3:
                st.metric("Index Type", faiss_stats.get("index_type", "N/A"))

            if faiss_stats.get("is_trained"):
                st.success("✅ Index is trained and ready")
            else:
                st.warning("⚠️ Index not trained")
        else:
            st.info("FAISS index not initialized or not in use")
    except Exception as e:
        st.caption(f"FAISS stats unavailable: {e}")

    st.divider()

    # Qdrant Stats (if available)
    st.markdown("##### 🔮 Qdrant Vector Store")
    try:
        qdrant_stats = _get_qdrant_stats()
        if qdrant_stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Points Count", qdrant_stats.get("points_count", 0))
            with col2:
                st.metric("Segments", qdrant_stats.get("segments_count", 0))
            with col3:
                st.metric("Status", qdrant_stats.get("status", "Unknown"))
        else:
            st.info("Qdrant not configured or not in use")
    except Exception as e:
        st.caption(f"Qdrant stats unavailable: {e}")

    st.divider()

    # BM25 Sparse Index Stats
    st.markdown("##### 📊 BM25 Sparse Index (Hybrid Search)")
    try:
        bm25_count = 0
        if "precision_engine" in st.session_state and st.session_state.precision_engine:
            bm25_count = st.session_state.precision_engine.get_bm25_count()

        if bm25_count > 0:
            st.metric("Indexed Documents", bm25_count)
            st.success("✅ BM25 index ready for hybrid search")
        else:
            st.warning("⚠️ BM25 index empty - ingest documents to populate")
            st.caption(
                "The BM25 index is populated during document ingestion and enables hybrid (dense + sparse) search"
            )
    except Exception as e:
        st.caption(f"BM25 stats unavailable: {e}")


def _get_faiss_stats() -> dict | None:
    """Get FAISS index statistics."""
    try:
        from pathlib import Path

        import faiss

        from src.config import settings

        # Check for FAISS index file
        index_path = settings.processed_path / "faiss_index.bin"
        if not index_path.exists():
            return None

        index = faiss.read_index(str(index_path))
        return {
            "ntotal": index.ntotal,
            "dimension": index.d,
            "index_type": type(index).__name__,
            "is_trained": index.is_trained,
        }
    except ImportError:
        return None
    except Exception:
        return None


def _get_qdrant_stats() -> dict | None:
    """Get Qdrant collection statistics."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(path="./.qdrant_data")
        collections = client.get_collections().collections

        if not collections:
            return None

        # Get first collection stats
        collection = collections[0]
        info = client.get_collection(collection.name)

        return {
            "collection_name": collection.name,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
            "status": info.status.value if info.status else "Unknown",
        }
    except ImportError:
        return None
    except Exception:
        return None


def _render_api_health_dashboard():
    """Render embedding API health metrics."""
    st.markdown("#### 📈 Embedding API Health")

    # Initialize API health tracking in session state
    if "api_health" not in st.session_state:
        st.session_state["api_health"] = {
            "voyage": {
                "requests": 0,
                "errors": 0,
                "avg_latency_ms": 0,
                "last_error": None,
            },
            "anthropic": {
                "requests": 0,
                "errors": 0,
                "avg_latency_ms": 0,
                "last_error": None,
            },
        }

    health = st.session_state["api_health"]

    # Voyage AI Stats
    st.markdown("##### 🚀 Voyage AI (Embeddings)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Requests", health["voyage"]["requests"])
    with col2:
        st.metric("Errors", health["voyage"]["errors"])
    with col3:
        error_rate = (
            health["voyage"]["errors"] / max(health["voyage"]["requests"], 1)
        ) * 100
        st.metric("Error Rate", f"{error_rate:.1f}%")
    with col4:
        st.metric("Avg Latency", f"{health['voyage']['avg_latency_ms']:.0f}ms")

    if health["voyage"]["last_error"]:
        st.error(f"Last error: {health['voyage']['last_error']}")

    st.divider()

    # Anthropic Stats
    st.markdown("##### 🤖 Anthropic (Claude)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Requests", health["anthropic"]["requests"])
    with col2:
        st.metric("Errors", health["anthropic"]["errors"])
    with col3:
        error_rate = (
            health["anthropic"]["errors"] / max(health["anthropic"]["requests"], 1)
        ) * 100
        st.metric("Error Rate", f"{error_rate:.1f}%")
    with col4:
        st.metric("Avg Latency", f"{health['anthropic']['avg_latency_ms']:.0f}ms")

    if health["anthropic"]["last_error"]:
        st.error(f"Last error: {health['anthropic']['last_error']}")

    # Test Connection Buttons
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Test Voyage Connection", width="stretch"):
            _test_voyage_connection()
    with col2:
        if st.button("🔌 Test Anthropic Connection", width="stretch"):
            _test_anthropic_connection()


def _test_voyage_connection():
    """Test Voyage AI API connection."""
    import time

    try:
        import voyageai

        from src.config import settings

        start = time.time()
        client = voyageai.Client(api_key=settings.voyage_api_key)
        result = client.embed(["test"], model="voyage-3-lite")
        latency = (time.time() - start) * 1000

        st.success(
            f"✅ Voyage AI connected! Latency: {latency:.0f}ms, Dimension: {len(result.embeddings[0])}"
        )

        # Update health
        st.session_state["api_health"]["voyage"]["requests"] += 1
        st.session_state["api_health"]["voyage"]["avg_latency_ms"] = latency
    except Exception as e:
        st.error(f"❌ Voyage AI connection failed: {e}")
        st.session_state["api_health"]["voyage"]["errors"] += 1
        st.session_state["api_health"]["voyage"]["last_error"] = str(e)[:100]


def _test_anthropic_connection():
    """Test Anthropic API connection."""
    import time

    try:
        import anthropic

        from src.config import settings

        start = time.time()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        # Simple ping - count tokens
        _ = client.count_tokens("test")
        latency = (time.time() - start) * 1000

        st.success(f"✅ Anthropic connected! Latency: {latency:.0f}ms")

        st.session_state["api_health"]["anthropic"]["requests"] += 1
        st.session_state["api_health"]["anthropic"]["avg_latency_ms"] = latency
    except Exception as e:
        st.error(f"❌ Anthropic connection failed: {e}")
        st.session_state["api_health"]["anthropic"]["errors"] += 1
        st.session_state["api_health"]["anthropic"]["last_error"] = str(e)[:100]


def _render_caption_preview():
    """Render caption extraction preview and edit UI."""
    st.markdown("#### 🖼️ Caption Extraction Preview")
    st.caption("Review and edit extracted figure captions")

    try:
        sources = st.session_state.db.get_all_sources()

        if not sources:
            st.info("No sources indexed yet")
            return

        # Source selector
        source_titles = [s.title for s in sources]
        selected_title = st.selectbox(
            "Select Source", source_titles, key="caption_source_select"
        )

        # Get selected source
        selected_source = next((s for s in sources if s.title == selected_title), None)
        if not selected_source:
            return

        # Get images for this source
        images = st.session_state.db.get_images_by_source(selected_source.id)

        if not images:
            st.info(f"No images extracted from {selected_title}")
            return

        st.markdown(f"**Found {len(images)} images**")

        # Display images with editable captions
        for i, img in enumerate(images):
            with st.container():
                col1, col2 = st.columns([1, 2])

                with col1:
                    # Display thumbnail if exists
                    if img.file_path and Path(img.file_path).exists():
                        st.image(str(img.file_path), width=150)
                    else:
                        st.markdown("🖼️ *Image not found*")

                with col2:
                    st.markdown(f"**Page {img.page}** | Type: `{img.image_type.value}`")

                    # Editable caption
                    new_caption = st.text_area(
                        "Caption",
                        value=img.caption or "",
                        key=f"caption_{img.id}",
                        height=80,
                        label_visibility="collapsed",
                    )

                    # Save button
                    if st.button("💾 Save Caption", key=f"save_caption_{img.id}"):
                        try:
                            _update_image_caption(img.id, new_caption)
                            st.success("Caption updated!")
                        except Exception as e:
                            st.error(f"Failed to update: {e}")

                st.divider()

    except Exception as e:
        st.error(f"Failed to load captions: {e}")


def _update_image_caption(image_id: str, caption: str):
    """Update image caption in database."""
    with st.session_state.db._get_conn() as conn:
        conn.execute("UPDATE images SET caption = ? WHERE id = ?", (caption, image_id))
        conn.commit()


def _on_result_select(result):
    """Handle result selection - show in detail view."""
    st.session_state["selected_search_result"] = result
    st.info(
        f"Selected: {result.chunk.metadata.get('chapter_title', 'Unknown')} - Page {result.chunk.metadata.get('page_number', '?')}"
    )


def _render_sources_tab():
    """Render the sources grid tab."""
    try:
        from src.ui.auto_sync_widget import _get_library_path, _scan_for_pdfs

        # Get all sources and image counts
        sources = st.session_state.db.get_all_sources()
        image_counts = st.session_state.db.get_image_counts_per_source()

        # Get unindexed files
        try:
            library_path = _get_library_path()
            all_pdfs = _scan_for_pdfs(library_path)

            # Filter out already indexed files
            indexed_paths = set()
            for s in sources:
                if s.file_path:
                    indexed_paths.add(Path(s.file_path).name)
                # Also check title match as fallback
                indexed_paths.add(s.title)

            unindexed_files = [
                meta for meta in all_pdfs.values() if meta["name"] not in indexed_paths
            ]
        except Exception as e:
            st.error(f"Failed to scan library: {e}")
            unindexed_files = []

        # Create Virtual Sources for unindexed files
        from dataclasses import dataclass
        from datetime import datetime

        from src.models import DocumentType, Specialty

        @dataclass
        class VirtualSource:
            id: str
            title: str
            file_path: str
            authors: list = None
            year: int = None
            specialty: Specialty = Specialty.GENERAL
            doc_type: DocumentType = DocumentType.PAPER
            created_at: datetime = None
            total_pages: int = 0
            is_virtual: bool = True

        virtual_sources = []
        for f in unindexed_files:
            virtual_sources.append(
                VirtualSource(
                    id=f"virtual_{f['name']}",
                    title=f["name"].replace(".pdf", "").replace("_", " "),
                    file_path=str(f["path"]),
                    created_at=f["modified"],
                    year=f["modified"].year,
                )
            )

        # Merge sources
        all_sources = sources + virtual_sources

        # Get chunk counts per source for indexation status
        chunk_counts = {}
        try:
            with st.session_state.db._get_conn() as conn:
                rows = conn.execute(
                    "SELECT source_id, COUNT(*) as c FROM chunks GROUP BY source_id"
                ).fetchall()
                chunk_counts = {row["source_id"]: row["c"] for row in rows}
        except Exception:
            pass

        # Filter Controls
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            search_term = st.text_input(
                "Search Library",
                placeholder="Search by title or author (scans disk & database)...",
                label_visibility="collapsed",
                key="library_source_search",
            )
        with col2:
            specialties = sorted(
                list(set(s.specialty.value for s in sources))
            )  # Only use real specialties
            specialty_filter = st.selectbox(
                "All Specialties", ["All"] + specialties, label_visibility="collapsed"
            )
        with col3:
            # Fuzzy threshold slider (hidden by default, can expose for power users)
            fuzzy_threshold = 55  # Good default for typo tolerance

        # Apply Filters with Fuzzy Search
        filtered_sources = all_sources
        if search_term:
            # Normalize the search query
            normalized_query = _normalize_text(search_term)

            # Perform fuzzy matching and collect scores
            matches_with_scores = []
            for s in filtered_sources:
                # Authors might be None for virtual sources
                authors_str = " ".join(s.authors) if s.authors else ""

                is_match, score = _fuzzy_match_source(
                    normalized_query,
                    s.title,
                    authors_str,
                    threshold=fuzzy_threshold,
                )
                if is_match:
                    matches_with_scores.append((s, score))

            # Sort by score (highest first) for relevance ranking
            matches_with_scores.sort(key=lambda x: x[1], reverse=True)
            filtered_sources = [s for s, _ in matches_with_scores]

            # Show search feedback
            if not filtered_sources and search_term:
                st.warning(
                    f"No matches found for '{search_term}'. "
                    "Try a different spelling or fewer words."
                )

        if specialty_filter != "All":
            filtered_sources = [
                s for s in filtered_sources if s.specialty.value == specialty_filter
            ]

        # Summary stats
        total_chunks = sum(
            chunk_counts.get(s.id, 0)
            for s in filtered_sources
            if not getattr(s, "is_virtual", False)
        )
        total_images = sum(
            image_counts.get(s.id, 0)
            for s in filtered_sources
            if not getattr(s, "is_virtual", False)
        )

        real_count = sum(
            1 for s in filtered_sources if not getattr(s, "is_virtual", False)
        )
        virtual_count = sum(
            1 for s in filtered_sources if getattr(s, "is_virtual", False)
        )

        st.markdown(
            f"**📚 {real_count} indexed, {virtual_count} unindexed** — {total_chunks} chunks, {total_images} images"
        )

        # Grid Layout
        cols = st.columns(3)
        for i, source in enumerate(filtered_sources):
            with cols[i % 3]:
                with styles.card_container():
                    is_virtual = getattr(source, "is_virtual", False)

                    st.markdown(f"### 📄 {source.title}")

                    if is_virtual:
                        st.caption(f"Unindexed File • {source.year}")
                        status_color = "#d29922"  # yellow/orange
                        status_icon = "⚠️"
                        status_text = "Not Indexed"
                    else:
                        st.caption(f"{source.specialty.value} • {source.year}")
                        if source.authors:
                            st.markdown(f"*{source.authors[0]} et al.*")

                        src_chunks = chunk_counts.get(source.id, 0)
                        if src_chunks > 0:
                            status_color = "#238636"  # green
                            status_icon = "✅"
                            status_text = f"{src_chunks} Chunks"
                        else:
                            status_color = "#8b949e"  # gray
                            status_icon = "⏳"
                            status_text = "Indexing..."

                    # Metadata Badges
                    if is_virtual:
                        st.markdown(
                            f"""
                        <div style="display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px;">
                            <span style="background: {status_color}; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; color: black;">{status_icon} {status_text}</span>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    else:
                        src_images = image_counts.get(source.id, 0)
                        st.markdown(
                            f"""
                        <div style="display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px;">
                            <span style="background: {status_color}; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">{status_icon} {status_text}</span>
                            <span style="background: #21262d; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">📄 {source.total_pages} Pages</span>
                            <span style="background: #21262d; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">🖼️ {src_images} Images</span>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )

                    # Actions
                    if is_virtual:
                        # Index Button
                        st.markdown("")  # Spacer
                        if st.button(
                            "🚀 Index Now",
                            key=f"idx_virt_{i}",  # Use index as virtual IDs might overlap or differ
                            width="stretch",
                            type="primary",
                        ):
                            st.session_state.pending_index = Path(source.file_path)
                            st.rerun()
                    else:
                        col_a, col_b = st.columns(2)
                        is_selected = (
                            source.id
                            in st.session_state.project_context["selected_source_ids"]
                        )

                        with col_a:
                            if st.button(
                                "View Details",
                                key=f"view_{source.id}",
                                width="stretch",
                            ):
                                st.session_state.selected_source = source.id
                                st.rerun()

                        with col_b:
                            if is_selected:
                                if st.button(
                                    "✅ Selected",
                                    key=f"sel_{source.id}",
                                    width="stretch",
                                ):
                                    st.session_state.project_context[
                                        "selected_source_ids"
                                    ].remove(source.id)
                                    st.rerun()
                            else:
                                if st.button(
                                    "Select",
                                    key=f"sel_{source.id}",
                                    width="stretch",
                                ):
                                    st.session_state.project_context[
                                        "selected_source_ids"
                                    ].add(source.id)
                                    st.rerun()

    except Exception as e:
        st.error(f"Failed to load library: {e}")
        import traceback

        st.code(traceback.format_exc())


def render_detail_view(source_id):
    """Renders the detailed view for a single source."""
    if st.button("← Back to Library"):
        del st.session_state.selected_source
        st.rerun()

    source = st.session_state.db.get_source(source_id)
    if not source:
        st.error("Source not found.")
        return

    st.markdown(f"## {source.title}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Metadata")
        st.write(f"**Authors:** {source.authors}")
        st.write(f"**Year:** {source.year}")
        st.write(f"**Total Pages:** {source.total_pages}")

        # Specialty Classification Override
        st.markdown("---")
        st.markdown("**🏥 Specialty Classification**")
        from src.models import DocumentType, Specialty

        specialty_col1, specialty_col2 = st.columns([3, 1])
        with specialty_col1:
            specialty_options = [s.value for s in Specialty]
            current_specialty_idx = specialty_options.index(source.specialty.value)
            new_specialty = st.selectbox(
                "Detected Specialty",
                specialty_options,
                index=current_specialty_idx,
                key=f"specialty_{source_id}",
            )
        with specialty_col2:
            if st.button("💾 Update", key=f"update_specialty_{source_id}"):
                try:
                    st.session_state.db.update_source_specialty(
                        source_id, Specialty(new_specialty)
                    )
                    st.success("Specialty updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

        # Document Type Override
        st.markdown("**📄 Document Type**")
        doctype_col1, doctype_col2 = st.columns([3, 1])
        with doctype_col1:
            doctype_options = [d.value for d in DocumentType]
            current_doctype_idx = doctype_options.index(source.doc_type.value)
            new_doctype = st.selectbox(
                "Detected Type",
                doctype_options,
                index=current_doctype_idx,
                key=f"doctype_{source_id}",
            )
        with doctype_col2:
            if st.button("💾 Update", key=f"update_doctype_{source_id}"):
                try:
                    st.session_state.db.update_source_doctype(
                        source_id, DocumentType(new_doctype)
                    )
                    st.success("Document type updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

        # Force Re-indexing
        st.markdown("---")
        st.markdown("**🔄 Re-index Document**")
        st.caption("Reprocess this document to update chunks and embeddings")

        reindex_col1, reindex_col2 = st.columns([1, 1])
        with reindex_col1:
            if st.button(
                "🔄 Force Re-index",
                key=f"reindex_{source_id}",
                width="stretch",
                type="secondary",
            ):
                st.session_state.reindex_source = source_id
                st.rerun()

        with reindex_col2:
            if st.button("🗑️ Delete Source", key=f"delete_{source_id}", width="stretch"):
                if st.session_state.get(f"confirm_delete_{source_id}", False):
                    try:
                        st.session_state.db.delete_source(source_id)
                        st.success("Source deleted!")
                        del st.session_state.selected_source
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
                else:
                    st.session_state[f"confirm_delete_{source_id}"] = True
                    st.warning("Click again to confirm deletion")

    with col2:
        st.markdown("### Images")
        images = st.session_state.db.get_images_by_source(source_id)
        st.write(f"**Total Extracted:** {len(images)}")

    st.divider()

    # Use enhanced figure gallery
    if images:
        render_enhanced_figure_gallery(images, source_id)
