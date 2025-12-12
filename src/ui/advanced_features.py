"""
Advanced Features UI Component
==============================
Comprehensive UI for advanced synthesis and processing features:
1. Coverage Gap Detection
2. Knowledge Clustering & Merger
3. Procedural Step Correlation
4. Figure Integration Pipeline
5. Image Modality Classification
6. Synthesis Checkpoint/Recovery
7. LaTeX Export with Figures
"""

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


# ═══════════════════════════════════════════════════════════════════════════
# 1. COVERAGE GAP DETECTION
# ═══════════════════════════════════════════════════════════════════════════


def render_gap_detection_panel(
    search_results: list[Any] | None = None, query: str = "", query_type: Any = None
):
    """
    Render gap detection warnings for search results.

    Args:
        search_results: List of PrecisionResult objects from search
        query: Original search query
        query_type: QueryType enum value
    """
    st.markdown("### 🔍 Coverage Gap Analysis")

    if not search_results:
        st.info("Run a search to analyze coverage gaps")
        return

    try:
        from src.index.gap_detector import GapDetector, GapSeverity, GapType
        from src.index.precision_search import QueryType as QT

        # Default to FACTUAL if no query_type
        if query_type is None:
            query_type = QT.FACTUAL

        detector = GapDetector()
        warnings = detector.detect_gaps(query, query_type, search_results)

        if not warnings:
            st.success("✅ No significant coverage gaps detected")
            return

        # Group by severity
        severity_groups = {
            GapSeverity.CRITICAL: [],
            GapSeverity.HIGH: [],
            GapSeverity.MEDIUM: [],
            GapSeverity.LOW: [],
        }

        for warning in warnings:
            severity_groups[warning.severity].append(warning)

        # Render by severity
        if severity_groups[GapSeverity.CRITICAL]:
            st.error("### ⚠️ CRITICAL Gaps")
            for w in severity_groups[GapSeverity.CRITICAL]:
                _render_gap_warning(w, "🚨")

        if severity_groups[GapSeverity.HIGH]:
            st.warning("### ⚡ HIGH Priority Gaps")
            for w in severity_groups[GapSeverity.HIGH]:
                _render_gap_warning(w, "⚠️")

        if severity_groups[GapSeverity.MEDIUM]:
            with st.expander("ℹ️ MEDIUM Priority Gaps", expanded=False):
                for w in severity_groups[GapSeverity.MEDIUM]:
                    _render_gap_warning(w, "💡")

        if severity_groups[GapSeverity.LOW]:
            with st.expander("💡 Suggestions", expanded=False):
                for w in severity_groups[GapSeverity.LOW]:
                    _render_gap_warning(w, "✨")

        # Summary metrics
        _render_gap_summary(warnings, search_results)

    except Exception as e:
        st.error(f"Gap detection failed: {e}")


def _render_gap_warning(warning, icon: str):
    """Render a single gap warning."""
    gap_type_icons = {
        "authority": "📊",
        "guideline": "📋",
        "diversity": "🔀",
        "category": "📁",
        "foundation": "🏛️",
        "exam_adequacy": "📝",
        "source_count": "📚",
    }

    type_icon = gap_type_icons.get(warning.gap_type.value, "❓")

    with st.container():
        st.markdown(
            f"{icon} **{type_icon} {warning.gap_type.value.upper()}:** {warning.message}"
        )

        if warning.suggestion:
            st.caption(f"💡 *Suggestion:* {warning.suggestion}")

        if warning.metrics:
            cols = st.columns(len(warning.metrics))
            for i, (key, value) in enumerate(warning.metrics.items()):
                with cols[i]:
                    st.metric(key.replace("_", " ").title(), str(value)[:20])


def _render_gap_summary(warnings: list, results: list):
    """Render summary metrics for gap analysis."""
    st.divider()
    st.markdown("#### 📊 Coverage Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        critical_count = len([w for w in warnings if w.severity.value == "critical"])
        st.metric("Critical", critical_count, delta_color="inverse")

    with col2:
        high_count = len([w for w in warnings if w.severity.value == "high"])
        st.metric("High", high_count, delta_color="inverse")

    with col3:
        # Calculate average authority
        if results:
            avg_auth = sum(r.authority_score for r in results) / len(results)
            st.metric("Avg Authority", f"{avg_auth:.0f}/100")
        else:
            st.metric("Avg Authority", "N/A")

    with col4:
        # Calculate diversity
        if results:
            subspecialties = set(
                r.chunk.metadata.get("subspecialty", "General") for r in results
            )
            st.metric("Subspecialties", len(subspecialties))
        else:
            st.metric("Subspecialties", 0)


def render_gap_detection_compact(search_results: list | None = None):
    """Render compact gap detection badge for integration in other panels."""
    if not search_results:
        return

    try:
        from src.index.gap_detector import GapDetector, GapSeverity
        from src.index.precision_search import QueryType

        detector = GapDetector()
        warnings = detector.detect_gaps("", QueryType.FACTUAL, search_results)

        critical = len([w for w in warnings if w.severity == GapSeverity.CRITICAL])
        high = len([w for w in warnings if w.severity == GapSeverity.HIGH])

        if critical > 0:
            st.error(f"⚠️ {critical} Critical Gap{'s' if critical > 1 else ''}")
        elif high > 0:
            st.warning(f"⚡ {high} High-Priority Gap{'s' if high > 1 else ''}")
        else:
            st.success("✅ Coverage OK")

    except Exception:
        pass  # Silent fail for compact mode


# ═══════════════════════════════════════════════════════════════════════════
# 2. KNOWLEDGE CLUSTERING & MERGER VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════


def render_clustering_panel():
    """
    Render knowledge clustering and merger visualization.

    Shows:
    - Semantic clusters from retrieval
    - Cluster merger results
    - Conflict detection within clusters
    - Visual-text associations
    """
    st.markdown("### 🔮 Knowledge Clustering")
    st.caption("Semantic clustering with conflict detection and multi-source merging")

    # Cluster configuration
    with st.expander("⚙️ Clustering Configuration", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            similarity_threshold = st.slider(
                "Similarity Threshold",
                min_value=0.5,
                max_value=0.95,
                value=0.75,
                step=0.05,
                key="cluster_similarity",
            )
        with col2:
            min_cluster_size = st.number_input(
                "Min Cluster Size",
                min_value=1,
                max_value=10,
                value=2,
                key="cluster_min_size",
            )

        detect_conflicts = st.checkbox(
            "Enable Conflict Detection", value=True, key="cluster_conflicts"
        )
        associate_visuals = st.checkbox(
            "Associate Visual Elements", value=True, key="cluster_visuals"
        )

    # Input: chunks from session state or manual input
    if "selected_chunks" in st.session_state and st.session_state.selected_chunks:
        chunks = st.session_state.selected_chunks
        st.info(f"📚 {len(chunks)} chunks available for clustering")
    else:
        st.warning(
            "No chunks selected. Run a search and add results to synthesis context first."
        )
        return

    if st.button("🔮 Run Clustering", key="run_clustering", width="stretch"):
        _execute_clustering(
            chunks=chunks,
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size,
            detect_conflicts=detect_conflicts,
            associate_visuals=associate_visuals,
        )

    # Display results
    if "cluster_results" in st.session_state:
        _render_cluster_results()


def _execute_clustering(
    chunks: list,
    similarity_threshold: float,
    min_cluster_size: int,
    detect_conflicts: bool,
    associate_visuals: bool,
):
    """Execute semantic clustering on chunks."""
    import asyncio

    with st.spinner("🔮 Clustering chunks semantically..."):
        try:
            from src.neurosynth.dedup.clustering import SemanticClusterer
            from src.neurosynth.dedup.merger import ClusterMerger
            from src.neurosynth.models.document import ContentChunk

            # Convert UI chunks to ContentChunk if needed
            content_chunks = []
            for chunk in chunks:
                if hasattr(chunk, "content"):
                    # Create ContentChunk from Chunk
                    content_chunks.append(chunk)

            if not content_chunks:
                st.error("No valid chunks to cluster")
                return

            # Run semantic clustering
            clusterer = SemanticClusterer(
                similarity_threshold=similarity_threshold,
                min_cluster_size=min_cluster_size,
            )

            result = asyncio.run(clusterer.cluster_chunks(content_chunks))

            # Merge clusters if conflicts enabled
            merge_results = []
            if detect_conflicts and result.clusters:
                merger = ClusterMerger()
                merge_results = asyncio.run(
                    merger.merge_all_clusters(result.clusters, detect_conflicts=True)
                )

            # Store results
            st.session_state.cluster_results = {
                "clusters": result.clusters,
                "total_chunks": result.total_chunks,
                "num_clusters": result.num_clusters,
                "dedup_ratio": result.dedup_ratio,
                "merge_results": merge_results,
                "conflicts_detected": sum(len(c.conflicts) for c in result.clusters),
            }

            st.success(
                f"✅ Created {result.num_clusters} clusters from {result.total_chunks} chunks"
            )

        except Exception as e:
            st.error(f"Clustering failed: {e}")


def _render_cluster_results():
    """Render clustering results visualization."""
    results = st.session_state.cluster_results

    # Summary metrics
    st.markdown("#### 📊 Clustering Summary")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Clusters", results["num_clusters"])
    with col2:
        st.metric("Total Chunks", results["total_chunks"])
    with col3:
        st.metric("Dedup Ratio", f"{results['dedup_ratio']:.1%}")
    with col4:
        st.metric("Conflicts", results["conflicts_detected"])

    st.divider()

    # Individual clusters
    st.markdown("#### 🔮 Clusters")

    for i, cluster in enumerate(results["clusters"]):
        # Determine cluster status
        has_conflict = (
            len(cluster.conflicts) > 0 if hasattr(cluster, "conflicts") else False
        )
        status_icon = "⚡" if has_conflict else "✅"

        # Cluster header
        cluster_title = (
            cluster.topic
            if hasattr(cluster, "topic") and cluster.topic
            else f"Cluster {i+1}"
        )
        chunk_count = len(cluster.chunks) if hasattr(cluster, "chunks") else 0

        with st.expander(
            f"{status_icon} **{cluster_title}** ({chunk_count} chunks)",
            expanded=(i < 3),
        ):
            # Merged content preview
            if hasattr(cluster, "merged_content") and cluster.merged_content:
                st.markdown("**📝 Merged Content:**")
                st.markdown(
                    cluster.merged_content[:500] + "..."
                    if len(cluster.merged_content) > 500
                    else cluster.merged_content
                )

            # Source chunks
            st.markdown("**📚 Source Chunks:**")
            for j, chunk in enumerate(cluster.chunks[:5]):
                source_name = (
                    getattr(chunk, "source_title", "Unknown")
                    or getattr(chunk.source, "title", "Unknown")
                    if hasattr(chunk, "source")
                    else "Unknown"
                )
                st.caption(f"• {source_name}: {chunk.content[:100]}...")

            if chunk_count > 5:
                st.caption(f"*...and {chunk_count - 5} more chunks*")

            # Conflicts
            if has_conflict:
                st.markdown("**⚡ Conflicts Detected:**")
                for conflict in cluster.conflicts[:3]:
                    conflict_type = (
                        conflict.type.value if hasattr(conflict, "type") else "unknown"
                    )
                    st.warning(
                        f"**{conflict_type.upper()}:** {conflict.description if hasattr(conflict, 'description') else str(conflict)}"
                    )


def render_clustering_compact():
    """Render compact clustering status badge."""
    if "cluster_results" not in st.session_state:
        st.caption("🔮 No clusters")
        return

    results = st.session_state.cluster_results
    conflicts = results.get("conflicts_detected", 0)

    if conflicts > 0:
        st.warning(f"⚡ {results['num_clusters']} clusters ({conflicts} conflicts)")
    else:
        st.success(f"✅ {results['num_clusters']} clusters")


# ═══════════════════════════════════════════════════════════════════════════
# 3. PROCEDURAL STEP CORRELATION
# ═══════════════════════════════════════════════════════════════════════════


def render_procedural_correlation_panel():
    """
    Render procedural step-to-image correlation visualization.

    Shows:
    - Text steps extracted from synthesized content
    - Image sequence matching results
    - Confidence scores for each match
    - Manual override controls
    """
    st.markdown("### 🔧 Procedural Step Correlation")
    st.caption("Match surgical technique steps to procedural image sequences")

    # Input text area for testing
    col1, col2 = st.columns([3, 1])
    with col1:
        test_text = st.text_area(
            "Synthesized Text (with steps)",
            placeholder="Enter surgical technique text with numbered steps...\n\nStep 1: Position the patient...\nStep 2: Make the incision...",
            height=150,
            key="procedural_text",
        )

    with col2:
        st.markdown("**Step Patterns:**")
        st.caption("• Step 1:, Step 2:")
        st.caption("• 1., 2., 3.")
        st.caption("• Stage I:, Stage II:")
        st.caption("• First,, Second,")

    # Get procedural images from session
    procedural_images = []
    if "retrieved_images" in st.session_state:
        procedural_images = [
            img
            for img in st.session_state.retrieved_images
            if getattr(img, "is_procedural", False)
        ]

    st.info(f"📸 {len(procedural_images)} procedural images available for matching")

    if st.button("🔗 Correlate Steps", key="correlate_steps", width="stretch"):
        if not test_text:
            st.warning("Enter synthesized text with numbered steps")
            return
        _execute_step_correlation(test_text, procedural_images)

    # Display results
    if "step_correlations" in st.session_state:
        _render_step_correlations()


def _execute_step_correlation(text: str, images: list):
    """Execute procedural step correlation."""
    with st.spinner("🔗 Correlating steps with images..."):
        try:
            from neurosynth.synthesis.procedural_correlator import (
                ProceduralStepCorrelator,
            )

            correlator = ProceduralStepCorrelator()
            matches = correlator.correlate_steps(text, images)

            # Extract text steps for display
            text_steps = correlator._extract_text_steps(text)

            st.session_state.step_correlations = {
                "matches": matches,
                "text_steps": text_steps,
                "total_steps": len(text_steps),
                "matched_steps": len(matches),
            }

            st.success(f"✅ Matched {len(matches)}/{len(text_steps)} steps to images")

        except Exception as e:
            st.error(f"Correlation failed: {e}")


def _render_step_correlations():
    """Render step correlation results."""
    results = st.session_state.step_correlations

    # Summary
    st.markdown("#### 📊 Correlation Results")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Steps", results["total_steps"])
    with col2:
        st.metric("Matched", results["matched_steps"])
    with col3:
        match_rate = results["matched_steps"] / max(results["total_steps"], 1)
        st.metric("Match Rate", f"{match_rate:.0%}")

    st.divider()

    # Step-by-step visualization
    st.markdown("#### 🔗 Step Matches")

    for match in results["matches"]:
        confidence_color = (
            "🟢" if match.confidence > 0.8 else "🟡" if match.confidence > 0.5 else "🔴"
        )

        with st.expander(
            f"{confidence_color} Step {match.step_number} → Image (Confidence: {match.confidence:.0%})",
            expanded=True,
        ):
            col_step, col_img = st.columns([2, 1])

            with col_step:
                st.markdown(
                    f"**Step {match.step_number}** (Paragraph {match.paragraph_index})"
                )
                # Find corresponding text step
                for ts in results["text_steps"]:
                    if ts.number == match.step_number:
                        st.caption(f"*{ts.label}*: {ts.content[:150]}...")
                        break

            with col_img:
                visual = match.visual
                if hasattr(visual, "file_path") and Path(visual.file_path).exists():
                    st.image(visual.file_path, width=150)
                else:
                    st.markdown("🖼️ *Preview unavailable*")

                if hasattr(visual, "caption") and visual.caption:
                    st.caption(visual.caption[:80])

    # Unmatched steps
    matched_nums = {m.step_number for m in results["matches"]}
    unmatched = [ts for ts in results["text_steps"] if ts.number not in matched_nums]

    if unmatched:
        st.markdown("#### ⚠️ Unmatched Steps")
        for ts in unmatched:
            st.caption(f"• Step {ts.number}: {ts.content[:100]}...")


# ═══════════════════════════════════════════════════════════════════════════
# 4. FIGURE INTEGRATION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════


def render_figure_integration_panel():
    """
    Render figure integration pipeline controls and visualization.

    Shows:
    - Pipeline configuration (semantic matching, procedural correlation, etc.)
    - Figure library with used/unused tracking
    - Position optimization controls
    - Integration preview
    """
    st.markdown("### 🖼️ Figure Integration Pipeline")
    st.caption(
        "Orchestrate semantic matching, placeholder resolution, and position optimization"
    )

    # Pipeline configuration
    with st.expander("⚙️ Pipeline Configuration", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            semantic_threshold = st.slider(
                "Semantic Matching Threshold",
                min_value=0.2,
                max_value=0.9,
                value=0.4,
                step=0.05,
                key="fig_semantic_threshold",
            )
            enable_semantic = st.checkbox(
                "Enable Semantic Matching", value=True, key="fig_enable_semantic"
            )

        with col2:
            enable_procedural = st.checkbox(
                "Enable Procedural Correlation", value=True, key="fig_enable_procedural"
            )
            enable_placeholders = st.checkbox(
                "Enable Placeholder Resolution",
                value=True,
                key="fig_enable_placeholders",
            )

        st.markdown("**Position Optimizer Settings:**")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            max_inline = st.number_input(
                "Max Inline per 1000 words",
                min_value=1,
                max_value=10,
                value=3,
                key="fig_max_inline",
            )
        with col_b:
            max_plate = st.number_input(
                "Max Plate Figures",
                min_value=1,
                max_value=20,
                value=6,
                key="fig_max_plate",
            )
        with col_c:
            min_spacing = st.number_input(
                "Min Paragraph Spacing",
                min_value=1,
                max_value=10,
                value=2,
                key="fig_min_spacing",
            )

    # Figure Library Status
    st.markdown("#### 📚 Figure Library")

    if "available_visuals" in st.session_state:
        visuals = st.session_state.available_visuals
        st.info(f"📸 {len(visuals)} visuals available")

        # Show preview
        if visuals:
            cols = st.columns(6)
            for idx, visual in enumerate(visuals[:12]):
                with cols[idx % 6]:
                    if hasattr(visual, "file_path") and Path(visual.file_path).exists():
                        st.image(visual.file_path, width=80)
                    else:
                        st.markdown("🖼️")

                    is_used = getattr(visual, "is_used", False)
                    st.caption("✅ Used" if is_used else "⏳ Available")
    else:
        st.warning("No visuals loaded. Run synthesis first to load figure library.")

    # Run pipeline button
    if st.button(
        "🚀 Run Integration Pipeline", key="run_fig_pipeline", width="stretch"
    ):
        _execute_figure_integration(
            semantic_threshold=semantic_threshold,
            enable_semantic=enable_semantic,
            enable_procedural=enable_procedural,
            enable_placeholders=enable_placeholders,
            max_inline=max_inline,
            max_plate=max_plate,
            min_spacing=min_spacing,
        )

    # Results
    if "figure_integration_results" in st.session_state:
        _render_figure_integration_results()


def _execute_figure_integration(
    semantic_threshold: float,
    enable_semantic: bool,
    enable_procedural: bool,
    enable_placeholders: bool,
    max_inline: int,
    max_plate: int,
    min_spacing: int,
):
    """Execute figure integration pipeline."""
    with st.spinner("🖼️ Running figure integration pipeline..."):
        try:
            from neurosynth.synthesis.figure_integration import (
                FigureIntegrationConfig,
                FigureIntegrationPipeline,
            )
            from neurosynth.synthesis.position_optimizer import PositionOptimizerConfig

            # Get visuals and synthesized content from session
            visuals = st.session_state.get("available_visuals", [])
            chapter = st.session_state.get("synthesized_chapter")

            if not visuals:
                st.error("No visuals available. Load source documents first.")
                return

            if not chapter:
                st.error("No synthesized chapter. Run synthesis first.")
                return

            # Configure pipeline
            optimizer_config = PositionOptimizerConfig(
                max_inline_per_1000_words=max_inline,
                max_plate_figures=max_plate,
                min_paragraph_spacing=min_spacing,
            )

            config = FigureIntegrationConfig(
                semantic_threshold=semantic_threshold,
                optimizer_config=optimizer_config,
                enable_semantic_matching=enable_semantic,
                enable_procedural_correlation=enable_procedural,
                enable_placeholder_resolution=enable_placeholders,
            )

            pipeline = FigureIntegrationPipeline(visuals, config)
            resolution = pipeline.resolve_chapter(chapter)

            st.session_state.figure_integration_results = {
                "total_positioned": resolution.total_positioned,
                "unresolved_placeholders": resolution.total_unresolved_placeholders,
                "unused_count": resolution.unused_count,
                "section_resolutions": resolution.section_resolutions,
                "library": pipeline.get_figure_library(),
            }

            st.success(
                f"✅ Positioned {resolution.total_positioned} figures, {resolution.unused_count} remaining in library"
            )

        except Exception as e:
            st.error(f"Figure integration failed: {e}")


def _render_figure_integration_results():
    """Render figure integration results."""
    results = st.session_state.figure_integration_results

    # Summary
    st.markdown("#### 📊 Integration Summary")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Positioned", results["total_positioned"])
    with col2:
        st.metric("Unused", results["unused_count"])
    with col3:
        st.metric("Unresolved", results["unresolved_placeholders"])
    with col4:
        total = results["total_positioned"] + results["unused_count"]
        usage_rate = results["total_positioned"] / max(total, 1)
        st.metric("Usage Rate", f"{usage_rate:.0%}")

    st.divider()

    # Per-section breakdown
    st.markdown("#### 📑 Section Breakdown")

    for section_title, resolution in results["section_resolutions"].items():
        inline_count = getattr(resolution, "inline_count", 0)
        plate_count = getattr(resolution, "plate_count", 0)

        with st.expander(
            f"📄 {section_title} ({inline_count} inline, {plate_count} plate)",
            expanded=False,
        ):
            # Show positioned figures
            if hasattr(resolution, "positioned_figures"):
                for pf in resolution.positioned_figures[:5]:
                    placement = (
                        pf.placement_type.value
                        if hasattr(pf.placement_type, "value")
                        else str(pf.placement_type)
                    )
                    st.caption(f"• {placement}: Para {pf.paragraph_index}")

            # Unmatched placeholders
            if (
                hasattr(resolution, "unmatched_placeholders")
                and resolution.unmatched_placeholders
            ):
                st.warning(
                    f"⚠️ {len(resolution.unmatched_placeholders)} unmatched placeholders"
                )


# ═══════════════════════════════════════════════════════════════════════════
# 5. IMAGE MODALITY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def render_modality_classification_panel():
    """
    Render image modality classification panel.

    Uses zero-shot CLIP classification to categorize medical images:
    - Radiology (MRI, CT, X-ray)
    - Surgical (intraoperative photos)
    - Microscopic (histology slides)
    - Diagram (illustrations, schematics)
    - Graph (charts, tables)
    - Equipment (instruments)
    """
    st.markdown("### 🏷️ Image Modality Classification")
    st.caption("Zero-shot CLIP-based medical image classification")

    # Show available categories
    categories = {
        "radiology": "📡 Radiological scan (MRI, CT, X-ray)",
        "surgical": "🔪 Intraoperative photograph",
        "microscopic": "🔬 Histology/microscopic view",
        "diagram": "📐 Medical illustration/diagram",
        "graph": "📊 Chart/graph/table",
        "equipment": "🛠️ Medical equipment/instruments",
    }

    with st.expander("📂 Classification Categories", expanded=False):
        for cat, desc in categories.items():
            st.caption(f"{desc}")

    # Get images from session state
    images = st.session_state.get("retrieved_images", [])

    if not images:
        st.warning("No images available. Run search or load a project first.")
        return

    st.info(f"📸 {len(images)} images available for classification")

    # Classification controls
    col1, col2 = st.columns([3, 1])
    with col1:
        batch_size = st.slider(
            "Batch Size", min_value=1, max_value=50, value=10, key="classify_batch"
        )
    with col2:
        if st.button("🏷️ Classify All", key="classify_all", width="stretch"):
            _execute_modality_classification(images[:batch_size])

    # Results
    if "modality_classifications" in st.session_state:
        _render_modality_classifications()


def _execute_modality_classification(images: list):
    """Execute modality classification on images."""
    import numpy as np

    with st.spinner("🏷️ Classifying image modalities..."):
        try:
            from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
            from neurosynth.ai.classifier import ModalityClassifier

            # Initialize classifier
            searcher = BiomedCLIPSearcher()
            classifier = ModalityClassifier(searcher)

            # Collect image vectors
            results = []
            for img in images:
                if (
                    hasattr(img, "colpali_embedding")
                    and img.colpali_embedding is not None
                ):
                    vector = np.array(img.colpali_embedding)
                    label, confidence = classifier.classify(vector)
                    results.append(
                        {"image": img, "label": label, "confidence": confidence}
                    )

            st.session_state.modality_classifications = results
            st.success(f"✅ Classified {len(results)} images")

        except Exception as e:
            st.error(f"Classification failed: {e}")


def _render_modality_classifications():
    """Render modality classification results."""
    results = st.session_state.modality_classifications

    if not results:
        st.info("No classification results yet")
        return

    # Category icons
    icons = {
        "radiology": "📡",
        "surgical": "🔪",
        "microscopic": "🔬",
        "diagram": "📐",
        "graph": "📊",
        "equipment": "🛠️",
    }

    # Summary by category
    st.markdown("#### 📊 Classification Summary")

    category_counts = {}
    for r in results:
        label = r["label"]
        category_counts[label] = category_counts.get(label, 0) + 1

    cols = st.columns(len(category_counts) if category_counts else 1)
    for idx, (label, count) in enumerate(category_counts.items()):
        with cols[idx % len(cols)]:
            icon = icons.get(label, "❓")
            st.metric(f"{icon} {label.title()}", count)

    st.divider()

    # Individual results
    st.markdown("#### 🖼️ Classification Results")

    # Filter by category
    filter_cat = st.selectbox(
        "Filter by Category", ["All"] + list(icons.keys()), key="modality_filter"
    )

    filtered = (
        results
        if filter_cat == "All"
        else [r for r in results if r["label"] == filter_cat]
    )

    # Display in grid
    cols = st.columns(4)
    for idx, r in enumerate(filtered[:16]):
        with cols[idx % 4]:
            img = r["image"]
            if hasattr(img, "file_path") and Path(img.file_path).exists():
                st.image(img.file_path, width="stretch")
            else:
                st.markdown("🖼️ *Preview unavailable*")

            icon = icons.get(r["label"], "❓")
            confidence_pct = r["confidence"] * 100
            st.caption(f"{icon} **{r['label'].title()}** ({confidence_pct:.0f}%)")


# ═══════════════════════════════════════════════════════════════════════════
# 6. SYNTHESIS CHECKPOINT/RECOVERY
# ═══════════════════════════════════════════════════════════════════════════


def render_checkpoint_recovery_panel():
    """
    Render synthesis checkpoint and recovery UI.

    Shows:
    - Active checkpoints with stage status
    - Recovery directory browser
    - Resume from checkpoint controls
    - Artifact viewer (sections, figures, LaTeX)
    """
    st.markdown("### 💾 Synthesis Checkpoint/Recovery")
    st.caption("Automatic state saving and recovery for long-running synthesis jobs")

    # Get recovery base directory
    recovery_base = Path.home() / ".neurosynth" / "recovery"

    if not recovery_base.exists():
        st.info(
            "No recovery checkpoints found. Checkpoints are created automatically during synthesis."
        )
        return

    # List available checkpoints
    checkpoints = (
        sorted(recovery_base.iterdir(), reverse=True) if recovery_base.exists() else []
    )
    checkpoints = [d for d in checkpoints if d.is_dir()]

    if not checkpoints:
        st.info("No recovery checkpoints available")
        return

    st.success(f"📂 {len(checkpoints)} recovery checkpoints found")

    # Checkpoint selector
    selected_checkpoint = st.selectbox(
        "Select Checkpoint",
        checkpoints,
        format_func=lambda x: f"{x.name}",
        key="selected_checkpoint",
    )

    if selected_checkpoint:
        _render_checkpoint_details(selected_checkpoint)


def _render_checkpoint_details(checkpoint_dir: Path):
    """Render details for a specific checkpoint."""
    st.markdown(f"#### 📁 {checkpoint_dir.name}")

    # Stage status
    stage_status_file = checkpoint_dir / "stage_status.json"
    if stage_status_file.exists():
        import json

        with open(stage_status_file) as f:
            stage_status = json.load(f)

        st.markdown("**Pipeline Stages:**")
        cols = st.columns(5)

        stages = ["initialized", "parsed", "outline", "synthesis", "latex"]
        for idx, stage in enumerate(stages):
            with cols[idx % 5]:
                status = stage_status.get(stage, "pending")
                icon = (
                    "✅"
                    if status == "completed"
                    else "⏳" if status == "in_progress" else "⏹️"
                )
                st.caption(f"{icon} {stage.title()}")

    st.divider()

    # Artifacts tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📄 Sections", "🖼️ Figures", "📝 LaTeX", "⚠️ Errors"]
    )

    with tab1:
        _render_checkpoint_sections(checkpoint_dir)

    with tab2:
        _render_checkpoint_figures(checkpoint_dir)

    with tab3:
        _render_checkpoint_latex(checkpoint_dir)

    with tab4:
        _render_checkpoint_errors(checkpoint_dir)

    # Recovery actions
    st.divider()
    st.markdown("#### 🔧 Recovery Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📥 Load Checkpoint", key="load_checkpoint", width="stretch"):
            _load_checkpoint(checkpoint_dir)

    with col2:
        if st.button("▶️ Resume Synthesis", key="resume_synthesis", width="stretch"):
            _resume_from_checkpoint(checkpoint_dir)

    with col3:
        if st.button("🗑️ Delete Checkpoint", key="delete_checkpoint", width="stretch"):
            import shutil

            shutil.rmtree(checkpoint_dir)
            st.rerun()


def _render_checkpoint_sections(checkpoint_dir: Path):
    """Render recovered sections."""
    sections_dir = checkpoint_dir / "sections"

    if not sections_dir.exists():
        st.info("No sections saved yet")
        return

    section_files = sorted(sections_dir.glob("*.md"))

    if not section_files:
        st.info("No sections found")
        return

    st.success(f"📄 {len(section_files)} sections recovered")

    for section_file in section_files[:10]:
        with st.expander(f"📄 {section_file.stem}", expanded=False):
            content = section_file.read_text(encoding="utf-8")
            st.markdown(content[:500] + "..." if len(content) > 500 else content)


def _render_checkpoint_figures(checkpoint_dir: Path):
    """Render recovered figures."""
    figures_dir = checkpoint_dir / "figures"

    if not figures_dir.exists():
        st.info("No figures saved yet")
        return

    figure_files = list(figures_dir.glob("*.*"))

    if not figure_files:
        st.info("No figures found")
        return

    st.success(f"🖼️ {len(figure_files)} figures recovered")

    cols = st.columns(4)
    for idx, fig_file in enumerate(figure_files[:12]):
        with cols[idx % 4]:
            try:
                st.image(str(fig_file), width="stretch")
                st.caption(fig_file.name)
            except Exception:
                st.caption(f"📎 {fig_file.name}")


def _render_checkpoint_latex(checkpoint_dir: Path):
    """Render recovered LaTeX."""
    tex_file = checkpoint_dir / "chapter.tex"

    if not tex_file.exists():
        st.info("No LaTeX generated yet")
        return

    content = tex_file.read_text(encoding="utf-8")

    st.success(f"📝 LaTeX recovered ({len(content)} characters)")

    with st.expander("📝 View LaTeX Source", expanded=False):
        st.code(
            content[:2000] + "\n\n... (truncated)" if len(content) > 2000 else content,
            language="latex",
        )

    # PDF status
    pdf_file = checkpoint_dir / "chapter.pdf"
    if pdf_file.exists():
        st.success("📕 PDF compiled successfully")

        with open(pdf_file, "rb") as f:
            st.download_button(
                "📥 Download PDF",
                f.read(),
                file_name=f"{checkpoint_dir.name}.pdf",
                mime="application/pdf",
            )
    else:
        st.warning("⚠️ PDF not compiled or compilation failed")


def _render_checkpoint_errors(checkpoint_dir: Path):
    """Render error log if present."""
    error_file = checkpoint_dir / "error.log"

    if not error_file.exists():
        st.success("✅ No errors logged")
        return

    content = error_file.read_text(encoding="utf-8")

    if content.strip():
        st.error("⚠️ Errors occurred during synthesis:")
        st.code(content, language="text")
    else:
        st.success("✅ No errors logged")


def _load_checkpoint(checkpoint_dir: Path):
    """Load checkpoint data into session state."""
    import json
    import pickle

    try:
        # Load outline if present
        outline_file = checkpoint_dir / "outline.json"
        if outline_file.exists():
            with open(outline_file) as f:
                st.session_state.loaded_outline = json.load(f)

        # Load clusters if present
        clusters_file = checkpoint_dir / "clusters.pkl"
        if clusters_file.exists():
            with open(clusters_file, "rb") as f:
                st.session_state.loaded_clusters = pickle.load(f)

        st.success(f"✅ Loaded checkpoint: {checkpoint_dir.name}")

    except Exception as e:
        st.error(f"Failed to load checkpoint: {e}")


def _resume_from_checkpoint(
    checkpoint_dir: Path,
):  # noqa: ARG001 - checkpoint_dir reserved for future use
    """Resume synthesis from checkpoint."""
    st.info(
        "🔄 Resume functionality requires active synthesis engine. Use the Synthesis Studio with loaded checkpoint."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7. LATEX EXPORT WITH FIGURES
# ═══════════════════════════════════════════════════════════════════════════


def render_latex_export_panel():
    """
    Render LaTeX export with figures panel.

    Shows:
    - LaTeX generation configuration
    - Template selection
    - Figure handling options
    - PDF compilation controls
    - Download buttons
    """
    st.markdown("### 📄 LaTeX Export with Figures")
    st.caption("Generate publication-ready LaTeX documents with integrated figures")

    # Check for synthesized chapter
    chapter = st.session_state.get("synthesized_chapter")

    if not chapter:
        st.warning("No synthesized chapter available. Run synthesis first.")
        return

    st.info(
        f"📕 Chapter: **{chapter.title}** ({chapter.total_words} words, {chapter.total_figures} figures)"
    )

    # Export configuration
    with st.expander("⚙️ Export Configuration", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            output_format = st.selectbox(
                "Output Format",
                ["LaTeX + PDF", "LaTeX Only", "PDF Only"],
                key="latex_output_format",
            )

            paper_size = st.selectbox(
                "Paper Size", ["A4", "Letter", "A5"], key="latex_paper_size"
            )

        with col2:
            include_toc = st.checkbox(
                "Include Table of Contents", value=True, key="latex_toc"
            )
            include_figures = st.checkbox(
                "Include Figures", value=True, key="latex_include_figs"
            )
            include_bibliography = st.checkbox(
                "Include Bibliography", value=True, key="latex_bib"
            )

        st.markdown("**Figure Options:**")
        col_a, col_b = st.columns(2)
        with col_a:
            figure_position = st.selectbox(
                "Default Figure Position",
                [
                    "Here if possible (h)",
                    "Top of page (t)",
                    "Bottom (b)",
                    "Float page (p)",
                ],
                key="latex_fig_pos",
            )
        with col_b:
            max_figure_width = st.slider(
                "Max Figure Width (\\textwidth)",
                min_value=0.3,
                max_value=1.0,
                value=0.8,
                step=0.1,
                key="latex_fig_width",
            )

    # Generate buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📝 Generate LaTeX", key="gen_latex", width="stretch"):
            _generate_latex(
                chapter=chapter,
                include_toc=include_toc,
                include_figures=include_figures,
                include_bibliography=include_bibliography,
                paper_size=paper_size,
            )

    with col2:
        if st.button("📕 Compile to PDF", key="compile_pdf", width="stretch"):
            _compile_latex_to_pdf()

    with col3:
        if st.button("📦 Export Package", key="export_pkg", width="stretch"):
            _export_latex_package()

    # Results
    if "generated_latex" in st.session_state:
        _render_latex_preview()


def _generate_latex(
    chapter,
    include_toc: bool,  # noqa: ARG001 - reserved for template customization
    include_figures: bool,  # noqa: ARG001 - reserved for template customization
    include_bibliography: bool,  # noqa: ARG001 - reserved for template customization
    paper_size: str,  # noqa: ARG001 - reserved for template customization
):
    """Generate LaTeX from chapter.

    Note: include_toc, include_figures, include_bibliography, paper_size are
    reserved for future template customization. Currently uses default template.
    """
    with st.spinner("📝 Generating LaTeX..."):
        try:
            from neurosynth.latex.generator import LaTeXGenerator

            # Create temporary output directory
            output_dir = Path.home() / ".neurosynth" / "exports"
            output_dir.mkdir(parents=True, exist_ok=True)

            generator = LaTeXGenerator(images_dir=output_dir / "figures")

            # Generate LaTeX
            latex_content = generator.generate_latex(chapter, output_dir=output_dir)

            # Save to file
            safe_title = chapter.title.lower().replace(" ", "_")[:30]
            tex_path = output_dir / f"{safe_title}.tex"
            tex_path.write_text(latex_content, encoding="utf-8")

            st.session_state.generated_latex = {
                "content": latex_content,
                "path": tex_path,
                "output_dir": output_dir,
                "title": chapter.title,
            }

            st.success(f"✅ LaTeX generated: {len(latex_content)} characters")

        except Exception as e:
            st.error(f"LaTeX generation failed: {e}")


def _compile_latex_to_pdf():
    """Compile generated LaTeX to PDF."""
    if "generated_latex" not in st.session_state:
        st.warning("Generate LaTeX first")
        return

    latex_data = st.session_state.generated_latex
    tex_path = latex_data["path"]
    output_dir = latex_data["output_dir"]

    with st.spinner("📕 Compiling PDF (this may take a minute)..."):
        try:
            from neurosynth.latex.generator import LaTeXGenerator

            generator = LaTeXGenerator()
            pdf_path = generator.compile_to_pdf(tex_path, output_dir, validate=True)

            st.session_state.generated_latex["pdf_path"] = pdf_path
            st.success(f"✅ PDF compiled: {pdf_path.name}")

        except FileNotFoundError:
            st.error(
                "❌ pdflatex not found. Install a TeX distribution (TeX Live, MiKTeX) to compile PDFs."
            )
        except Exception as e:
            st.error(f"PDF compilation failed: {e}")


def _export_latex_package():
    """Create a downloadable ZIP with LaTeX source and figures."""
    if "generated_latex" not in st.session_state:
        st.warning("Generate LaTeX first")
        return

    import io
    import zipfile

    latex_data = st.session_state.generated_latex
    output_dir = latex_data["output_dir"]

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add LaTeX file
        tex_path = latex_data["path"]
        if tex_path.exists():
            zf.write(tex_path, tex_path.name)

        # Add figures
        figures_dir = output_dir / "figures"
        if figures_dir.exists():
            for fig_file in figures_dir.iterdir():
                zf.write(fig_file, f"figures/{fig_file.name}")

        # Add PDF if exists
        if "pdf_path" in latex_data and latex_data["pdf_path"].exists():
            zf.write(latex_data["pdf_path"], latex_data["pdf_path"].name)

    zip_buffer.seek(0)

    st.download_button(
        "📦 Download LaTeX Package",
        zip_buffer.getvalue(),
        file_name=f"{latex_data['title'].replace(' ', '_')[:30]}_latex_package.zip",
        mime="application/zip",
    )


def _render_latex_preview():
    """Render LaTeX preview and download options."""
    latex_data = st.session_state.generated_latex

    st.divider()
    st.markdown("#### 📄 Generated Output")

    # LaTeX preview
    with st.expander("📝 LaTeX Source Preview", expanded=False):
        content = latex_data["content"]
        st.code(
            content[:3000] + "\n\n... (truncated)" if len(content) > 3000 else content,
            language="latex",
        )

    # Download buttons
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "📥 Download .tex",
            latex_data["content"],
            file_name=latex_data["path"].name,
            mime="text/plain",
        )

    with col2:
        if "pdf_path" in latex_data and latex_data["pdf_path"].exists():
            with open(latex_data["pdf_path"], "rb") as f:
                st.download_button(
                    "📕 Download PDF",
                    f.read(),
                    file_name=latex_data["pdf_path"].name,
                    mime="application/pdf",
                )
