"""
Embedding Control Panel
=======================
Streamlit UI component for controlling the embedding pipeline.

Provides:
- Start/pause/resume controls
- Sample size selection for testing
- Progress monitoring with ETA
- Configuration options (image extraction toggle)
"""

from pathlib import Path

import streamlit as st


def render_embedding_control_panel():
    """Render the embedding control panel in Streamlit."""

    st.subheader("📊 Library Embedding Pipeline")

    # Import pipeline
    try:
        from src.bridges.controlled_embedding_pipeline import (
            ControlledEmbeddingPipeline,
            PipelineConfig,
        )
    except ImportError as e:
        st.error(f"Failed to import pipeline: {e}")
        return

    # Initialize session state
    if "embedding_pipeline" not in st.session_state:
        st.session_state.embedding_pipeline = ControlledEmbeddingPipeline()

    pipeline = st.session_state.embedding_pipeline
    status = pipeline.get_status()

    # Status display
    col1, col2, col3 = st.columns(3)
    with col1:
        status_emoji = {
            "not_started": "⚪",
            "in_progress": "🟢",
            "paused": "🟡",
            "completed": "✅",
            "failed": "🔴",
        }
        st.metric(
            "Status",
            f"{status_emoji.get(status['status'], '❓')} {status['status'].title()}",
        )
    with col2:
        st.metric("Progress", f"{status['progress_percent']}%")
    with col3:
        st.metric(
            "ETA",
            f"{status['eta_minutes']:.1f} min" if status["eta_minutes"] > 0 else "—",
        )

    # Progress bar
    if status["total"] > 0:
        st.progress(status["progress_percent"] / 100)
        st.caption(
            f"Processed: {status['processed']}/{status['total']} documents | "
            f"Chunks: {status['chunks_created']} | Vectors: {status['vectors_stored']}"
        )

    st.divider()

    # Configuration section
    with st.expander("⚙️ Configuration", expanded=status["status"] == "not_started"):
        col1, col2 = st.columns(2)

        with col1:
            sample_size = st.number_input(
                "Sample Size (for testing)",
                min_value=1,
                max_value=100,
                value=10,
                help="Process this many documents first to verify everything works",
            )

        with col2:
            batch_size = st.number_input(
                "Batch Size",
                min_value=10,
                max_value=200,
                value=50,
                help="Documents to process in each batch",
            )

        enable_images = st.checkbox(
            "Enable Image Extraction",
            value=False,
            help="Extract and embed images from PDFs (slower, uses more resources)",
        )

        if enable_images:
            st.warning(
                "⚠️ Image extraction is resource-intensive. Consider testing on a sample first."
            )

            # Sub-options for image extraction
            st.markdown("**Image Enhancement Options:**")
            col_img1, col_img2 = st.columns(2)

            with col_img1:
                enable_region_detection = st.checkbox(
                    "🏷️ Anatomical Region Tagging",
                    value=True,
                    help="Auto-detect anatomical regions (MCA, brainstem, etc.)",
                )

            with col_img2:
                enable_ocr = st.checkbox(
                    "📝 OCR Caption Extraction",
                    value=False,
                    help="Extract text from images via OCR (slower, optional)",
                )
        else:
            enable_region_detection = False
            enable_ocr = False

    st.divider()

    # Control buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if status["status"] in ("not_started", "completed", "failed"):
            if st.button("🧪 Test Sample", type="secondary", width="stretch"):
                with st.spinner(f"Processing {sample_size} documents..."):
                    config = PipelineConfig(
                        batch_size=batch_size,
                        enable_image_extraction=enable_images,
                        enable_region_detection=enable_region_detection,
                        enable_ocr=enable_ocr,
                    )
                    pipeline = ControlledEmbeddingPipeline(config)
                    st.session_state.embedding_pipeline = pipeline
                    result = pipeline.run_sample(sample_size=sample_size)
                    st.success(
                        f"Sample complete: {result['vectors_stored']} vectors stored"
                    )
                    st.rerun()

    with col2:
        if status["status"] in ("not_started", "completed", "failed"):
            if st.button("🚀 Start Full Run", type="primary", width="stretch"):
                st.warning("⚠️ This will process ALL documents. Are you sure?")
                if st.button("Confirm Full Run"):
                    config = PipelineConfig(
                        batch_size=batch_size,
                        enable_image_extraction=enable_images,
                        enable_region_detection=enable_region_detection,
                        enable_ocr=enable_ocr,
                    )
                    pipeline = ControlledEmbeddingPipeline(config)
                    st.session_state.embedding_pipeline = pipeline
                    # Note: Full run should be done in background, not blocking UI
                    st.info(
                        "Full run would be started in background. (Not implemented yet)"
                    )

    with col3:
        if status["status"] == "in_progress":
            if st.button("⏸️ Pause", type="secondary", width="stretch"):
                pipeline.pause()
                st.info("Pipeline will pause after current batch")
                st.rerun()
        elif status["status"] == "paused":
            if st.button("▶️ Resume", type="primary", width="stretch"):
                with st.spinner("Resuming..."):
                    result = pipeline.resume()
                st.rerun()

    with col4:
        if status["status"] != "not_started":
            if st.button("🔄 Reset", type="secondary", width="stretch"):
                pipeline.reset()
                st.session_state.embedding_pipeline = ControlledEmbeddingPipeline()
                st.success("Pipeline reset")
                st.rerun()

    # Error display
    if status["errors"] > 0:
        with st.expander(f"⚠️ Errors ({status['errors']})", expanded=False):
            for err in pipeline.checkpoint.errors[-10:]:
                st.text(err)
