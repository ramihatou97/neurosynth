"""
Batch PDF Indexing UI Component

Streamlit interface for selecting and indexing PDFs with progress tracking.
Supports concurrent PDF processing via async indexer.
"""

import asyncio
from pathlib import Path

import streamlit as st

from src.config import settings
from src.index import Database
from src.services.batch_indexer import BatchIndexer, BatchProgress, IndexingStage


def get_library_pdfs() -> list[Path]:
    """Get all PDFs from the library directory"""
    library_path = settings.library_path
    if not library_path.exists():
        return []
    return sorted(library_path.rglob("*.pdf"))


def get_pdf_categories() -> dict[str, list[Path]]:
    """Get PDFs organized by category folder"""
    library_path = settings.library_path
    if not library_path.exists():
        return {}

    categories = {}
    for subdir in sorted(library_path.iterdir()):
        if subdir.is_dir():
            pdfs = sorted(subdir.rglob("*.pdf"))
            if pdfs:
                categories[subdir.name] = pdfs
    return categories


def format_time(seconds: float) -> str:
    """Format seconds to human readable string"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = seconds / 60
        return f"{mins:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def get_stage_label(stage: IndexingStage) -> str:
    """Get human-readable stage label"""
    labels = {
        IndexingStage.PENDING: "⏳ Waiting",
        IndexingStage.TEXT_EXTRACTION: "📄 Extracting Text",
        IndexingStage.CHUNKING: "✂️ Chunking",
        IndexingStage.TEXT_EMBEDDING: "🔤 Text Embeddings",
        IndexingStage.IMAGE_EXTRACTION: "🖼️ Extracting Images",
        IndexingStage.IMAGE_EMBEDDING: "🧠 Image Embeddings",
        IndexingStage.RAPTOR: "🦖 RAPTOR Summaries",
        IndexingStage.GRAPH_RAG: "🕸️ Knowledge Graph",
        IndexingStage.STORAGE: "💾 Saving to Database",
        IndexingStage.COMPLETE: "✅ Complete",
        IndexingStage.FAILED: "❌ Failed",
    }
    return labels.get(stage, str(stage))


def get_indexed_paths(db: Database) -> dict[str, dict]:
    """Get all indexed file paths with their metadata"""
    indexed = {}
    try:
        for src in db.get_all_sources():
            if src.file_path:
                resolved = Path(src.file_path).resolve()
                indexed[str(resolved)] = {
                    "id": src.id,
                    "title": src.title,
                    "chunks": 0,  # Will be filled below
                    "images": 0,
                }

        # Get chunk and image counts
        chunk_counts = {}
        image_counts = db.get_image_counts_per_source()

        with db._get_conn() as conn:
            rows = conn.execute(
                "SELECT source_id, COUNT(*) as c FROM chunks GROUP BY source_id"
            ).fetchall()
            chunk_counts = {row["source_id"]: row["c"] for row in rows}

        for path, info in indexed.items():
            info["chunks"] = chunk_counts.get(info["id"], 0)
            info["images"] = image_counts.get(info["id"], 0)

    except Exception as e:
        st.warning(f"Could not load indexed paths: {e}")

    return indexed


def render_batch_indexing_panel():
    """Render the batch indexing UI"""
    st.header("📥 Batch PDF Indexing")
    st.caption("Index PDFs from your library with full progress tracking")

    # Initialize session state
    if "indexing_in_progress" not in st.session_state:
        st.session_state.indexing_in_progress = False
    if "selected_pdfs" not in st.session_state:
        st.session_state.selected_pdfs = []

    # Database stats
    db = Database()
    stats = db.get_stats()
    indexed_paths = get_indexed_paths(db)

    # Summary metrics
    all_pdfs = get_library_pdfs()
    indexed_count = sum(1 for p in all_pdfs if str(p.resolve()) in indexed_paths)
    unindexed_count = len(all_pdfs) - indexed_count

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 PDFs in Library", len(all_pdfs))
    with col2:
        st.metric("✅ Indexed", indexed_count)
    with col3:
        st.metric("⏳ Not Indexed", unindexed_count)
    with col4:
        st.metric("📊 Total Chunks", stats.get("chunks", 0))

    st.divider()

    # Database Reset Section
    with st.expander("🗑️ Database Management", expanded=False):
        st.warning("⚠️ This will permanently delete all indexed data!")
        col_reset, col_confirm = st.columns([3, 1])
        with col_reset:
            st.text("Clear all sources, chunks, and images from the database")
        with col_confirm:
            if st.button("🗑️ Reset Database", type="secondary"):
                result = db.reset_all_data()
                st.success(
                    f"Deleted: {result['sources_deleted']} sources, "
                    f"{result['chunks_deleted']} chunks, "
                    f"{result['images_deleted']} images"
                )
                st.rerun()

    st.divider()

    # PDF Selection
    st.subheader("📁 Select PDFs to Index")

    categories = get_pdf_categories()
    total_pdfs = sum(len(pdfs) for pdfs in categories.values())
    st.caption(f"Found {total_pdfs} PDFs in {len(categories)} categories")

    if not categories:
        st.warning(f"No PDFs found in {settings.library_path}")
        return

    # Batch size selector
    batch_size = st.select_slider(
        "Batch Size",
        options=[5, 10, 25, 50, 100, 250, 500],
        value=25,
        help="Number of PDFs to process in one batch",
    )

    # Category selection with expandable sections
    selected_files = []

    # Quick select buttons
    col_all, col_none, col_unindexed = st.columns(3)
    with col_all:
        select_all = st.button("Select All", width="stretch")
    with col_none:
        select_none = st.button("Clear Selection", width="stretch")
    with col_unindexed:
        select_unindexed = st.button("Select Unindexed Only", width="stretch")

    # Count indexed per category for display
    def count_indexed_in_category(pdfs: list[Path]) -> int:
        return sum(1 for p in pdfs if str(p.resolve()) in indexed_paths)

    for category, pdfs in categories.items():
        indexed_in_cat = count_indexed_in_category(pdfs)
        cat_label = f"📂 {category} ({len(pdfs)} files • ✅ {indexed_in_cat} indexed)"

        with st.expander(cat_label):
            # Category-level select all
            cat_key = f"cat_{category}"
            all_selected = st.checkbox(
                f"Select all in {category}",
                key=cat_key,
                value=select_all,
            )

            for pdf in pdfs:
                resolved = str(pdf.resolve())
                is_indexed = resolved in indexed_paths

                # Rich label with indexed status
                if is_indexed:
                    info = indexed_paths[resolved]
                    label = f"✅ {pdf.name} — {info['chunks']} chunks, {info['images']} images"
                else:
                    label = f"⏳ {pdf.name} — not indexed"

                # Determine default value
                default_val = False
                if select_none:
                    default_val = False
                elif select_all or select_unindexed and not is_indexed or all_selected:
                    default_val = True

                if st.checkbox(label, key=str(pdf), value=default_val):
                    selected_files.append(pdf)

    st.divider()

    # Show selection count
    st.info(f"📌 Selected: {len(selected_files)} PDFs")

    # Limit to batch size
    files_to_process = selected_files[:batch_size]
    if len(selected_files) > batch_size:
        st.warning(
            f"Only first {batch_size} files will be processed. "
            f"Increase batch size or run multiple batches."
        )

    # Start Indexing Button
    if st.button(
        f"🚀 Start Indexing ({len(files_to_process)} files)",
        type="primary",
        disabled=len(files_to_process) == 0 or st.session_state.indexing_in_progress,
        width="stretch",
    ):
        # Get Phase 4 flags from session state
        phase4_flags = st.session_state.get("phase4_flags", {})
        enable_vector_graphics = phase4_flags.get("vector_graphics", False)
        enable_cross_references = phase4_flags.get("cross_references", False)

        run_batch_indexing(
            db,
            files_to_process,
            enable_vector_graphics=enable_vector_graphics,
            enable_cross_references=enable_cross_references,
        )


async def _run_async_indexing(
    indexer: BatchIndexer,
    pdf_files: list[Path],
    overall_progress,
    file_progress,
    status_text,
    elapsed_metric,
    remaining_metric,
    success_metric,
    failed_metric,
    active_files_container,
    counts_container=None,
):
    """Run async batch indexing with progress updates."""
    final_progress = None

    async for progress in indexer.index_batch_async(pdf_files):
        final_progress = progress

        # Update overall progress
        pct = progress.percent_complete / 100
        overall_text = (
            f"Overall: {progress.completed_files}/{progress.total_files} files"
        )
        if progress.concurrent_mode and progress.active_count > 0:
            overall_text += f" (🔄 {progress.active_count} active)"
        overall_progress.progress(pct, text=overall_text)

        # Update current file progress
        if progress.current_file:
            cf = progress.current_file
            stage_label = get_stage_label(cf.stage)
            file_progress.progress(
                cf.stage_progress / 100,
                text=f"[{progress.current_file_index}/{progress.total_files}] {cf.file_name}: {stage_label}",
            )

        # Show active files in concurrent mode
        if progress.concurrent_mode and progress.active_files:
            active_text = "🔄 **Active:** " + ", ".join(
                f.file_name for f in progress.active_files[:5]
            )
            if len(progress.active_files) > 5:
                active_text += f" +{len(progress.active_files) - 5} more"
            active_files_container.markdown(active_text)
        else:
            active_files_container.empty()

        # Update status
        status_text.text(
            f"Processing: {progress.current_file.file_name if progress.current_file else 'N/A'}"
        )

        # Update metrics
        elapsed_metric.metric("Elapsed", format_time(progress.elapsed_time))
        remaining_metric.metric(
            "Est. Remaining", format_time(progress.estimated_remaining)
        )
        success_metric.metric("✅ Success", progress.success_count)
        failed_metric.metric("❌ Failed", progress.failed_files)

        # Update detailed counts (P0 fix: show embedding and Qdrant counts)
        if counts_container is not None:
            # Aggregate counts from all completed files
            total_chunks = sum(f.chunks_created for f in progress.file_results)
            total_images = sum(f.images_extracted for f in progress.file_results)
            total_chunks_embedded = sum(
                f.chunks_embedded for f in progress.file_results
            )
            total_images_embedded = sum(
                f.images_embedded for f in progress.file_results
            )
            total_chunks_qdrant = sum(
                f.chunks_pushed_qdrant for f in progress.file_results
            )
            total_images_qdrant = sum(
                f.images_pushed_qdrant for f in progress.file_results
            )
            total_raptor = sum(f.raptor_chunks_created for f in progress.file_results)

            # Build counts text
            counts_text = (
                f"📊 **Chunks:** {total_chunks_embedded}/{total_chunks} embedded"
                f" | **Images:** {total_images_embedded}/{total_images} embedded"
            )
            if total_chunks_qdrant or total_images_qdrant:
                counts_text += f" | **Qdrant:** {total_chunks_qdrant} chunks, {total_images_qdrant} images"
            if total_raptor:
                counts_text += f" | **RAPTOR:** {total_raptor} summaries"

            counts_container.markdown(counts_text)

    return final_progress


def run_batch_indexing(
    db: Database,
    pdf_files: list[Path],
    enable_vector_graphics: bool = False,
    enable_cross_references: bool = False,
):
    """
    Execute batch indexing with progress display.

    Args:
        db: Database instance for storage
        pdf_files: List of PDF file paths to index
        enable_vector_graphics: Enable Phase 4 vector graphics extraction
                               (flowcharts, diagrams). Default False.
        enable_cross_references: Enable Phase 4 cross-reference tracking
                                between figures. Default False.
    """
    st.session_state.indexing_in_progress = True

    st.subheader("⏳ Indexing Progress")

    # Show concurrent mode indicator
    max_concurrent = settings.max_concurrent_pdfs
    if max_concurrent > 1:
        st.info(
            f"🚀 **Concurrent Mode:** Processing up to {max_concurrent} PDFs in parallel"
        )

    # Show Phase 4 feature status
    if enable_vector_graphics or enable_cross_references:
        phase4_msg = "📐 **Phase 4 Enhancements:** "
        features = []
        if enable_vector_graphics:
            features.append("Vector Graphics 🎨")
        if enable_cross_references:
            features.append("Cross-References 🔗")
        phase4_msg += ", ".join(features)
        st.info(phase4_msg)

    # Progress containers
    overall_progress = st.progress(0, text="Starting...")
    file_progress = st.progress(0, text="")
    active_files_container = st.empty()
    status_text = st.empty()

    # Main metrics row
    metrics_cols = st.columns(4)
    elapsed_metric = metrics_cols[0].empty()
    remaining_metric = metrics_cols[1].empty()
    success_metric = metrics_cols[2].empty()
    failed_metric = metrics_cols[3].empty()

    # Detailed counts row (P0 fix: show embedding and Qdrant counts)
    counts_container = st.empty()

    # Results container
    results_container = st.container()

    # Initialize BatchIndexer with Phase 4 flags
    indexer = BatchIndexer(
        db,
        enable_vector_graphics=enable_vector_graphics,
        enable_cross_references=enable_cross_references,
    )

    try:
        # Run async indexer in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        final_progress = loop.run_until_complete(
            _run_async_indexing(
                indexer,
                pdf_files,
                overall_progress,
                file_progress,
                status_text,
                elapsed_metric,
                remaining_metric,
                success_metric,
                failed_metric,
                active_files_container,
                counts_container,
            )
        )

        # Final summary
        overall_progress.progress(1.0, text="✅ Complete!")
        file_progress.empty()
        active_files_container.empty()

        if final_progress:
            with results_container:
                st.success(
                    f"Batch indexing complete! "
                    f"{final_progress.success_count} succeeded, {final_progress.failed_files} failed "
                    f"in {format_time(final_progress.elapsed_time)}"
                )

                # Show detailed summary (P0 fix)
                total_chunks = sum(
                    f.chunks_created for f in final_progress.file_results
                )
                total_images = sum(
                    f.images_extracted for f in final_progress.file_results
                )
                total_chunks_embedded = sum(
                    f.chunks_embedded for f in final_progress.file_results
                )
                total_images_embedded = sum(
                    f.images_embedded for f in final_progress.file_results
                )
                total_chunks_qdrant = sum(
                    f.chunks_pushed_qdrant for f in final_progress.file_results
                )
                total_images_qdrant = sum(
                    f.images_pushed_qdrant for f in final_progress.file_results
                )
                total_raptor = sum(
                    f.raptor_chunks_created for f in final_progress.file_results
                )

                # Summary metrics in columns
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("📄 Chunks", f"{total_chunks_embedded}/{total_chunks}")
                col2.metric("🖼️ Images", f"{total_images_embedded}/{total_images}")
                col3.metric("☁️ Qdrant Chunks", total_chunks_qdrant)
                col4.metric("🖼️ Qdrant Images", total_images_qdrant)

                if total_raptor > 0:
                    st.info(
                        f"🦖 **RAPTOR Summaries:** {total_raptor} summary chunks generated"
                    )

                # Show failed files if any
                failed = [f for f in final_progress.file_results if not f.is_success]
                if failed:
                    with st.expander(f"❌ Failed Files ({len(failed)})", expanded=True):
                        for f in failed:
                            st.error(f"**{f.file_name}**: {f.error_message}")

    except Exception as e:
        st.error(f"Batch indexing error: {e}")

    finally:
        st.session_state.indexing_in_progress = False
