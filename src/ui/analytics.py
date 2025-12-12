"""
Analytics Dashboard for Streamlit

Features:
- Cache statistics (indexed PDFs, chunks, images)
- Search patterns and history
- Synthesis usage metrics
- Embedding status
"""

import streamlit as st


def render_analytics_dashboard(db=None, search_history: list[str] = None):
    """
    Render the analytics dashboard with all metrics.

    Args:
        db: Database instance for cache stats
        search_history: List of recent search queries
    """
    st.header("📊 Analytics Dashboard")

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    # Get stats from database if available
    cache_stats = _get_cache_stats(db)

    with col1:
        st.metric(
            label="📚 Indexed Sources", value=cache_stats.get("indexed_sources", 0)
        )

    with col2:
        st.metric(label="📄 Total Chunks", value=cache_stats.get("total_chunks", 0))

    with col3:
        st.metric(label="🖼️ Extracted Images", value=cache_stats.get("total_images", 0))

    with col4:
        st.metric(
            label="🔍 Total Searches",
            value=len(search_history) if search_history else 0,
        )

    st.divider()

    # Two-column layout for detailed stats
    left_col, right_col = st.columns(2)

    with left_col:
        _render_cache_stats(cache_stats)
        _render_embedding_status(db)

    with right_col:
        _render_search_patterns(search_history)
        _render_synthesis_stats()


def _get_cache_stats(db) -> dict:
    """Get cache statistics from database."""
    if not db:
        return {}

    try:
        # Get source count
        sources = db.get_all_sources() if hasattr(db, "get_all_sources") else []

        # Get chunk count (total vs embedded)
        total_chunks = db.count_chunks() if hasattr(db, "count_chunks") else 0

        # Get embedded chunks for accurate "embedded" metric
        chunks_with_emb = []
        if hasattr(db, "get_all_chunks_with_embeddings"):
            chunks_with_emb = db.get_all_chunks_with_embeddings()

        # Get image count
        images = []
        if hasattr(db, "get_all_images_with_embeddings"):
            images = db.get_all_images_with_embeddings()

        total_images = db.count_images() if hasattr(db, "count_images") else len(images)

        return {
            "indexed_sources": len(sources),
            "total_chunks": total_chunks,
            "total_images": total_images,
            "chunks_with_embeddings": len(chunks_with_emb),
            "images_with_embeddings": len(images),
        }
    except Exception as e:
        st.warning(f"Could not load cache stats: {e}")
        return {}


def _render_cache_stats(stats: dict):
    """Render cache statistics section."""
    st.subheader("📦 Cache Statistics")

    if not stats:
        st.info("No cache data available")
        return

    # Create a nice table
    data = [
        ("Indexed Sources", stats.get("indexed_sources", 0)),
        ("Total Chunks", stats.get("total_chunks", 0)),
        ("Chunks with Embeddings", stats.get("chunks_with_embeddings", 0)),
        ("Total Images", stats.get("total_images", 0)),
        ("Images with Embeddings", stats.get("images_with_embeddings", 0)),
    ]

    for label, value in data:
        cols = st.columns([3, 1])
        with cols[0]:
            st.text(label)
        with cols[1]:
            st.text(str(value))


def _render_embedding_status(db):
    """Render embedding status section."""
    st.subheader("🧠 Embedding Status")

    if not db:
        st.info("Database not connected")
        return

    try:
        # Calculate embedding coverage
        chunks = (
            db.get_all_chunks_with_embeddings()
            if hasattr(db, "get_all_chunks_with_embeddings")
            else []
        )
        total = len(chunks)
        embedded = sum(1 for _, emb in chunks if emb)

        if total > 0:
            coverage = (embedded / total) * 100
            st.progress(
                coverage / 100, text=f"Text: {embedded}/{total} ({coverage:.1f}%)"
            )
        else:
            st.info("No chunks indexed yet")

        # Image embeddings (ColPali)
        images = []
        if hasattr(db, "get_all_images_with_embeddings"):
            images = db.get_all_images_with_embeddings()

        if images:
            img_total = len(images)
            img_embedded = sum(1 for _, emb in images if emb)
            img_coverage = (img_embedded / img_total) * 100 if img_total > 0 else 0
            st.progress(
                img_coverage / 100,
                text=f"Images: {img_embedded}/{img_total} ({img_coverage:.1f}%)",
            )

    except Exception as e:
        st.warning(f"Could not load embedding status: {e}")


def _render_search_patterns(search_history: list[str]):
    """Render search patterns section."""
    st.subheader("🔍 Search Patterns")

    if not search_history:
        st.info("No search history yet")
        return

    # Recent searches
    st.markdown("**Recent Searches:**")
    for i, query in enumerate(search_history[:10], 1):
        display_query = query[:40] + "..." if len(query) > 40 else query
        st.text(f"{i}. {display_query}")


def _render_synthesis_stats():
    """Render synthesis usage statistics."""
    st.subheader("✍️ Synthesis Stats")

    # Get synthesis history from session state
    synthesis_history = st.session_state.get("synthesis_history", [])

    if not synthesis_history:
        st.info("No synthesis history yet")
        return

    st.metric("Total Syntheses", len(synthesis_history))

    # Template usage
    template_counts = {}
    for entry in synthesis_history:
        template = entry.get("template", "unknown")
        template_counts[template] = template_counts.get(template, 0) + 1

    if template_counts:
        st.markdown("**Template Usage:**")
        for template, count in sorted(
            template_counts.items(), key=lambda x: x[1], reverse=True
        ):
            st.text(f"  {template}: {count}")


# ==================== Manual Embedding Controls ====================


def render_embedding_controls(db, embedding_client=None, colpali_client=None):
    """
    Render controls for manual/selective embedding.

    Args:
        db: Database instance
        embedding_client: Text embedding client
        colpali_client: ColPali visual embedding client
    """
    st.subheader("🧠 Embedding Controls")

    if not db:
        st.warning("Database not connected")
        return

    # Get sources
    sources = db.get_all_sources() if hasattr(db, "get_all_sources") else []

    if not sources:
        st.info("No sources indexed yet")
        return

    # Source selection
    source_options = [s.title if hasattr(s, "title") else str(s) for s in sources]
    selected_sources = st.multiselect(
        "Select sources to embed", options=source_options, key="embed_source_select"
    )

    col1, col2 = st.columns(2)

    with col1:
        embed_text = st.checkbox(
            "📝 Text Embeddings", value=True, key="embed_text_check"
        )

    with col2:
        embed_images = st.checkbox(
            "🖼️ Image Embeddings (ColPali)", value=False, key="embed_images_check"
        )

    # Embedding options
    with st.expander("⚙️ Options", expanded=False):
        force_reembed = st.checkbox("Force re-embed (overwrite existing)", value=False)
        batch_size = st.slider("Batch size", min_value=1, max_value=50, value=10)

    # Start embedding button
    if st.button("🚀 Start Embedding", type="primary", disabled=not selected_sources):
        _run_embedding(
            db=db,
            sources=selected_sources,
            embed_text=embed_text,
            embed_images=embed_images,
            embedding_client=embedding_client,
            colpali_client=colpali_client,
            force_reembed=force_reembed,
            batch_size=batch_size,
        )


def _run_embedding(
    db,
    sources: list[str],
    embed_text: bool,
    embed_images: bool,
    embedding_client,
    colpali_client,
    force_reembed: bool,
    batch_size: int,
):
    """Run the embedding process."""
    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()

    total_steps = len(sources) * (1 if embed_text else 0) + len(sources) * (
        1 if embed_images else 0
    )
    current_step = 0

    for source in sources:
        if embed_text and embedding_client:
            status_text.text(f"Embedding text for: {source}")
            try:
                # Get chunks for this source
                chunks = [
                    c
                    for c, _ in db.get_all_chunks_with_embeddings()
                    if c.source_id == source
                ]

                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    for chunk in batch:
                        # Check if already embedded
                        existing = (
                            db.get_chunk_embedding(chunk.id)
                            if hasattr(db, "get_chunk_embedding")
                            else None
                        )
                        if existing and not force_reembed:
                            continue

                        # Generate embedding
                        embedding = embedding_client.embed(chunk.text)
                        if hasattr(db, "store_chunk_embedding"):
                            db.store_chunk_embedding(chunk.id, embedding)

                    progress = (current_step + (i / len(chunks))) / total_steps
                    progress_bar.progress(progress)

            except Exception as e:
                st.error(f"Text embedding failed for {source}: {e}")

            current_step += 1

        if embed_images and colpali_client:
            status_text.text(f"Embedding images for: {source}")
            try:
                # Get images for this source
                images = (
                    db.get_images_by_source(source)
                    if hasattr(db, "get_images_by_source")
                    else []
                )

                for i, image in enumerate(images):
                    # Generate ColPali embedding
                    if hasattr(colpali_client, "embed_image"):
                        embedding = colpali_client.embed_image(image.path)
                        if hasattr(db, "store_image_embedding"):
                            db.store_image_embedding(image.id, embedding)

                    progress = (current_step + (i / len(images))) / total_steps
                    progress_bar.progress(progress)

            except Exception as e:
                st.error(f"Image embedding failed for {source}: {e}")

            current_step += 1

    progress_bar.progress(1.0, text="Complete!")
    status_text.text("✅ Embedding complete!")
    st.success(f"Processed {len(sources)} sources")
