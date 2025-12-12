"""
Auto-Sync Widget for Streamlit Dashboard
==========================================
Polling-based file detection for new PDFs in the library folder.
Uses session state to track sync status and detected files.
"""

import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.config import settings

logger = logging.getLogger(__name__)


def _get_library_path() -> Path:
    """Get the configured library path from session state or default."""
    path = st.session_state.get("library_path")
    if path:
        path = Path(path)
        if path.exists():
            return path
    return settings.library_path


def _scan_for_pdfs(library_path: Path) -> dict[str, dict]:
    """Scan library folder for all PDFs and return metadata."""
    pdfs = {}
    if not library_path.exists():
        return pdfs

    for pdf_path in library_path.rglob("*.pdf"):
        try:
            stat = pdf_path.stat()
            pdfs[str(pdf_path)] = {
                "path": pdf_path,
                "name": pdf_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "relative_path": str(pdf_path.relative_to(library_path)),
            }
        except (OSError, ValueError):
            continue

    return pdfs


def _get_indexed_sources() -> set[str]:
    """Get set of already indexed source filenames from database."""
    if "db" not in st.session_state:
        return set()

    try:
        sources = st.session_state.db.get_all_sources()
        # Extract filenames from source metadata
        indexed = set()
        for src in sources:
            if hasattr(src, "file_path") and src.file_path:
                indexed.add(Path(src.file_path).name)
            elif hasattr(src, "title"):
                indexed.add(src.title)
        return indexed
    except Exception:
        return set()


def _detect_new_files() -> list[dict]:
    """Detect new PDFs that haven't been indexed yet."""
    library_path = _get_library_path()
    all_pdfs = _scan_for_pdfs(library_path)
    indexed = _get_indexed_sources()

    new_files = []
    for path_str, meta in all_pdfs.items():
        if meta["name"] not in indexed:
            new_files.append(meta)

    # Sort by modified date (newest first)
    new_files.sort(key=lambda x: x["modified"], reverse=True)
    return new_files


def _process_single_file(pdf_path: Path) -> dict:
    """Process a single PDF file and return result info."""
    from src.index.chunker import SemanticChunker
    from src.ingest.processor import DocumentProcessor

    # Get config from session state
    chunk_size = st.session_state.get("ingest_chunk_size", 1500)
    chunk_overlap = st.session_state.get("ingest_chunk_overlap", 200)
    entropy_threshold = st.session_state.get("ingest_entropy_threshold", 2.0)

    # Get Phase 4 flags
    phase4_flags = st.session_state.get("phase4_flags", {})
    enable_vector_graphics = phase4_flags.get("vector_graphics", False)
    enable_cross_references = phase4_flags.get("cross_references", False)

    # Initialize processor
    processor = DocumentProcessor(
        entropy_threshold=entropy_threshold,
        enable_vector_graphics=enable_vector_graphics,
        enable_cross_references=enable_cross_references,
    )
    chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Process PDF
    result = processor.process(pdf_path)

    # Create chunks
    chunks = chunker.chunk_document(result)

    # Store in database
    st.session_state.db.insert_source(result.metadata)
    st.session_state.db.insert_chunks(chunks)

    # Store images
    for img in result.images:
        st.session_state.db.insert_image(img)

    # Update BM25 index for hybrid search
    if "precision_engine" in st.session_state and st.session_state.precision_engine:
        st.session_state.precision_engine.update_bm25_index(chunks)

    return {
        "file": pdf_path.name,
        "chunks": len(chunks),
        "images": len(result.images),
        "pages": result.metadata.total_pages if hasattr(result, "metadata") else 0,
    }


def render_auto_sync_widget():
    """Render the auto-sync status widget for the Dashboard."""
    st.markdown("### 🔄 Library Sync Status")

    # Check if we have a pending single file to index
    if "pending_index" in st.session_state and st.session_state.pending_index:
        pdf_path = st.session_state.pending_index
        st.session_state.pending_index = None  # Clear immediately

        with st.status(f"📥 Indexing {pdf_path.name}...", expanded=True) as status:
            try:
                st.write("🔄 Processing PDF...")
                result = _process_single_file(pdf_path)

                st.write(
                    f"✅ Extracted {result['chunks']} chunks, {result['images']} images"
                )
                status.update(label=f"✅ Indexed {pdf_path.name}", state="complete")
                st.success(
                    f"Successfully indexed: {result['chunks']} chunks, "
                    f"{result['images']} images from {result['pages']} pages"
                )
                st.rerun()  # Refresh to update the file list
            except Exception as e:
                logger.exception(f"Failed to index {pdf_path}")
                status.update(
                    label=f"❌ Failed to index {pdf_path.name}", state="error"
                )
                st.error(f"Indexing failed: {e}")
        return  # Don't render rest of widget while processing

    # Check for pending bulk index
    if "pending_bulk_index" in st.session_state and st.session_state.pending_bulk_index:
        pending = st.session_state.pending_bulk_index
        st.session_state.pending_bulk_index = None  # Clear immediately

        with st.status(f"📚 Indexing {len(pending)} files...", expanded=True) as status:
            progress_bar = st.progress(0)
            results = []

            for i, pdf_path in enumerate(pending):
                try:
                    st.write(f"📄 Processing {pdf_path.name}...")
                    result = _process_single_file(pdf_path)
                    results.append({"file": result["file"], "status": "✅", **result})
                except Exception as e:
                    logger.warning(f"Failed to index {pdf_path}: {e}")
                    results.append(
                        {"file": pdf_path.name, "status": "❌", "error": str(e)}
                    )

                progress_bar.progress((i + 1) / len(pending))

            success_count = sum(1 for r in results if r["status"] == "✅")
            status.update(
                label=f"✅ Indexed {success_count}/{len(pending)} files",
                state="complete" if success_count == len(pending) else "error",
            )

            # Show results summary
            if results:
                st.dataframe(
                    [
                        {
                            "File": r["file"],
                            "Status": r["status"],
                            "Chunks": r.get("chunks", 0),
                        }
                        for r in results
                    ],
                    hide_index=True,
                )
            st.rerun()  # Refresh to update the file list
        return

    library_path = _get_library_path()
    # Library path configuration
    with st.expander("⚙️ Library Settings", expanded=False):
        new_path = st.text_input(
            "Library Folder Path", value=str(library_path), key="widget_library_path"
        )
        if st.button("Update Path"):
            st.session_state.library_path = Path(new_path)
            st.rerun()

    # Scan for new files
    col1, col2 = st.columns([3, 1])

    with col2:
        if st.button("🔍 Scan Now", width="stretch"):
            st.session_state.last_scan = datetime.now()
            st.rerun()

    with col1:
        last_scan = st.session_state.get("last_scan")
        if last_scan:
            st.caption(f"Last scan: {last_scan.strftime('%H:%M:%S')}")
        else:
            st.caption("Click 'Scan Now' to check for new files")

    # Detect new files
    new_files = _detect_new_files()

    if not new_files:
        st.success("✅ All PDFs are indexed. Library is up to date.")
    else:
        st.warning(f"📥 **{len(new_files)} new PDF(s)** detected")

        # Show new files list
        with st.expander(f"View {len(new_files)} Unindexed Files", expanded=True):
            for i, file_meta in enumerate(new_files[:10]):  # Show max 10
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.text(f"📄 {file_meta['name'][:50]}...")
                    st.caption(
                        f"Modified: {file_meta['modified'].strftime('%Y-%m-%d %H:%M')}"
                    )
                with col_b:
                    # Clicking triggers immediate indexing on next rerun
                    if st.button("Index", key=f"idx_{i}", width="stretch"):
                        st.session_state.pending_index = file_meta["path"]
                        st.rerun()  # Immediately trigger processing

            if len(new_files) > 10:
                st.caption(f"... and {len(new_files) - 10} more files")

        # Bulk index button
        if st.button("📚 Index All New Files", width="stretch", type="primary"):
            st.session_state.pending_bulk_index = [f["path"] for f in new_files]
            st.rerun()  # Immediately trigger processing
