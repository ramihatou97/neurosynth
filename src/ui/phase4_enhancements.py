"""
Phase 4 Enhancements UI Component
=================================
Toggle advanced extraction and processing features:
- Vector graphics extraction (flowcharts, diagrams)
- LaTeX figure code generation
- Unified 7-stage extraction pipeline
- Advanced batch processing with XRef deduplication
"""

import sys
from pathlib import Path

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


# Default Phase 4 feature flags
DEFAULT_PHASE4_FLAGS = {
    "vector_graphics": False,
    "latex_figures": False,
    "unified_pipeline": True,
    "xref_dedup": True,
    "cross_references": False,
    "exam_frequency_boost": True,
    "authority_ranking": True,
    "colbert_reranking": True,
}


def _get_phase4_flags() -> dict:
    """Get current Phase 4 feature flags from session state."""
    if "phase4_flags" not in st.session_state:
        st.session_state.phase4_flags = DEFAULT_PHASE4_FLAGS.copy()
    return st.session_state.phase4_flags


def _set_phase4_flag(key: str, value: bool):
    """Set a Phase 4 feature flag."""
    flags = _get_phase4_flags()
    flags[key] = value
    st.session_state.phase4_flags = flags


def render_phase4_enhancements_panel():
    """
    Render the Phase 4 Enhancements control panel.

    Features:
    - Vector graphics extraction toggle
    - LaTeX figure code generation toggle
    - Unified 7-stage pipeline toggle
    - XRef deduplication toggle
    - Cross-references toggle
    """
    st.markdown("### ⚡ Phase 4 Enhancements")
    st.caption("Advanced extraction and processing features")

    flags = _get_phase4_flags()

    # Extraction Features
    st.markdown("#### 📊 Extraction Features")

    col1, col2 = st.columns(2)

    with col1:
        vector_graphics = st.toggle(
            "🎨 Vector Graphics Extraction",
            value=flags.get("vector_graphics", False),
            key="p4_vector_graphics",
            help="Extract flowcharts, diagrams, and vector graphics from PDFs",
        )
        _set_phase4_flag("vector_graphics", vector_graphics)

        latex_figures = st.toggle(
            "📐 LaTeX Figure Code",
            value=flags.get("latex_figures", False),
            key="p4_latex_figures",
            help="Generate LaTeX code for extracted figures",
        )
        _set_phase4_flag("latex_figures", latex_figures)

    with col2:
        unified_pipeline = st.toggle(
            "🔧 Unified 7-Stage Pipeline",
            value=flags.get("unified_pipeline", True),
            key="p4_unified_pipeline",
            help="Use the unified extraction pipeline for all processing",
        )
        _set_phase4_flag("unified_pipeline", unified_pipeline)

        xref_dedup = st.toggle(
            "🔗 XRef Deduplication",
            value=flags.get("xref_dedup", True),
            key="p4_xref_dedup",
            help="Enable cross-reference deduplication in batch processing",
        )
        _set_phase4_flag("xref_dedup", xref_dedup)

    st.divider()

    # Ranking Features
    st.markdown("#### 📈 Ranking Features")

    col3, col4 = st.columns(2)

    with col3:
        authority = st.toggle(
            "🏛️ Authority Ranking",
            value=flags.get("authority_ranking", True),
            key="p4_authority",
            help="Boost results from high-authority sources (textbooks, guidelines)",
        )
        _set_phase4_flag("authority_ranking", authority)

        exam_boost = st.toggle(
            "📝 Exam Frequency Boost",
            value=flags.get("exam_frequency_boost", True),
            key="p4_exam_boost",
            help="Boost high-yield exam topics in search results",
        )
        _set_phase4_flag("exam_frequency_boost", exam_boost)

    with col4:
        colbert = st.toggle(
            "🎯 ColBERT Reranking",
            value=flags.get("colbert_reranking", True),
            key="p4_colbert",
            help="Use ColBERT for precision reranking of search results",
        )
        _set_phase4_flag("colbert_reranking", colbert)

        cross_refs = st.toggle(
            "🔗 Cross-References",
            value=flags.get("cross_references", False),
            key="p4_cross_refs",
            help="Enable cross-reference linking in synthesis output",
        )
        _set_phase4_flag("cross_references", cross_refs)

    st.divider()

    # Status summary
    _render_status_summary(flags)


def _render_status_summary(flags: dict):
    """Render a summary of enabled features."""
    enabled_count = sum(1 for v in flags.values() if v)
    total_count = len(flags)

    st.markdown("#### 📊 Status")
    st.progress(
        enabled_count / total_count,
        text=f"{enabled_count}/{total_count} features enabled",
    )

    # List enabled features
    enabled = [k.replace("_", " ").title() for k, v in flags.items() if v]
    disabled = [k.replace("_", " ").title() for k, v in flags.items() if not v]

    col_on, col_off = st.columns(2)

    with col_on:
        st.markdown("**✅ Enabled:**")
        for feat in enabled:
            st.caption(f"• {feat}")

    with col_off:
        st.markdown("**⬜ Disabled:**")
        for feat in disabled:
            st.caption(f"• {feat}")


def render_phase4_compact():
    """Render a compact Phase 4 status widget for sidebar."""
    flags = _get_phase4_flags()
    enabled = sum(1 for v in flags.values() if v)
    total = len(flags)

    st.caption(f"⚡ Phase 4: {enabled}/{total} active")


def get_phase4_config() -> dict:
    """
    Get Phase 4 configuration for use in synthesis engine.

    Returns:
        Dict with feature flags for passing to synthesis/extraction engines.
    """
    flags = _get_phase4_flags()

    return {
        "enable_vector_graphics": flags.get("vector_graphics", False),
        "enable_latex_figures": flags.get("latex_figures", False),
        "enable_unified_pipeline": flags.get("unified_pipeline", True),
        "enable_xref_dedup": flags.get("xref_dedup", True),
        "enable_cross_references": flags.get("cross_references", False),
        "enable_exam_boost": flags.get("exam_frequency_boost", True),
        "enable_authority_ranking": flags.get("authority_ranking", True),
        "enable_colbert": flags.get("colbert_reranking", True),
    }


def render_batch_processing_controls():
    """Render batch processing controls with Phase 4 features."""
    st.markdown("### 🔄 Batch Processing")
    st.caption("Process multiple PDFs with Phase 4 enhancements")

    flags = _get_phase4_flags()

    # Upload section
    uploaded_files = st.file_uploader(
        "Upload PDFs", type=["pdf"], accept_multiple_files=True, key="batch_upload"
    )

    if not uploaded_files:
        st.info("Upload PDFs to begin batch processing")
        return

    st.markdown(f"**{len(uploaded_files)} files selected**")

    # Processing options
    with st.expander("⚙️ Processing Options", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            extract_images = st.checkbox(
                "Extract Images", value=True, key="batch_images"
            )
            extract_text = st.checkbox("Extract Text", value=True, key="batch_text")
            generate_embeddings = st.checkbox(
                "Generate Embeddings", value=True, key="batch_embed"
            )

        with col2:
            use_ocr = st.checkbox("Use OCR", value=False, key="batch_ocr")
            if flags.get("vector_graphics"):
                st.checkbox("Extract Vector Graphics", value=True, key="batch_vectors")
            if flags.get("xref_dedup"):
                st.checkbox("Enable Deduplication", value=True, key="batch_dedup")

    # Process button
    if st.button("🚀 Start Processing", key="batch_start", width="stretch"):
        _run_batch_processing(
            files=uploaded_files,
            extract_images=extract_images,
            extract_text=extract_text,
            generate_embeddings=generate_embeddings,
            use_ocr=use_ocr,
            phase4_config=get_phase4_config(),
        )


def _run_batch_processing(
    files,
    extract_images,  # noqa: ARG001
    extract_text,  # noqa: ARG001
    generate_embeddings,  # noqa: ARG001
    use_ocr,  # noqa: ARG001
    phase4_config,  # noqa: ARG001
):
    """
    Run batch processing on uploaded files.

    Note: Parameters are placeholders for full pipeline integration.
    Currently simulates progress for UI demonstration.
    """
    _ = (
        extract_images,
        extract_text,
        generate_embeddings,
        use_ocr,
        phase4_config,
    )  # Suppress unused

    progress = st.progress(0, text="Starting...")

    total = len(files)
    for i, file in enumerate(files):
        progress.progress((i + 1) / total, text=f"Processing {file.name}...")

        # TODO: Integrate with actual extraction pipeline
        # For now, just simulate progress
        import time

        time.sleep(0.5)

    progress.progress(1.0, text="Complete!")
    st.success(f"✅ Processed {total} files")
