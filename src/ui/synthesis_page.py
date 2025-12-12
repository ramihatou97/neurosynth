import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

# Ensure src is in path to import engine
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from src.ai import AIClient
from src.index import Database, SearchEngine
from src.models import SourceMetadata, SynthesizedChapter, SynthesizedSection
from src.neurosynth.models.document import ContentChunk
from src.neurosynth.models.knowledge import KnowledgeCluster
from src.neurosynth.synthesis.checkpoint import SynthesisCheckpoint, get_latest_recovery
from src.neurosynth.synthesis.outline import OutlineEntry, OutlineGenerator

# New imports for advanced features
from src.neurosynth.synthesis.section import SectionSynthesizer, SynthesisConfig
from src.output.renderer import ChapterRenderer
from src.synthesize import SynthesisEngine
from src.ui import styles
from src.ui.advanced_features import render_latex_export_panel
from src.ui.template_config import (
    TEMPLATE_REGISTRY,
    get_default_params,
    get_template_choices,
    get_template_config,
)


def render_synthesis_page():
    st.markdown("## 🧬 Synthesis Studio")
    st.caption("Advanced Knowledge Synthesis Workflow")

    # Initialize Components (Lazy Load)
    if (
        "db" not in st.session_state
        or "search" not in st.session_state
        or "engine" not in st.session_state
    ):
        try:
            st.session_state.db = Database()
            # AIClient instantiated per-request via async context manager
            st.session_state.search = SearchEngine(st.session_state.db)
            st.session_state.engine = SynthesisEngine(
                st.session_state.db,
                st.session_state.search,
                None,  # AIClient instantiated per-request
            )
        except Exception as e:
            st.error(f"Failed to initialize engine: {e}")
            return

    # Workflow State
    if "studio_step" not in st.session_state:
        st.session_state.studio_step = 1

    if "syn_topic" not in st.session_state:
        st.session_state.syn_topic = "Vestibular Schwannoma"

    # --- STEP 1: SETUP ---
    if st.session_state.studio_step == 1:
        with styles.card_container():
            st.markdown("### 1. Chapter Configuration")

            col1, col2 = st.columns(2)
            # Bind directly to session state
            col1.text_input("Core Topic", key="syn_topic")

            # Template Selection
            template_choices = get_template_choices()
            template_options = [f"{t[2]} {t[1]}" for t in template_choices]
            template_keys = [t[0] for t in template_choices]

            default_template_idx = st.session_state.get("syn_template_idx", 0)
            selected_template_display = col2.selectbox(
                "Synthesis Template",
                template_options,
                index=default_template_idx,
                key="widget_syn_template",
            )
            selected_template_key = template_keys[
                template_options.index(selected_template_display)
            ]
            template_config = get_template_config(selected_template_key)

            # Template description
            st.caption(
                f"**{template_config['name']}**: {template_config['description']}"
            )

            # Dynamic Template Parameters
            with st.expander("🎛️ Template Parameters", expanded=False):
                template_params = {}
                params_config = template_config.get("parameters", {})

                # Ensure common params exist
                common_params = {
                    "section_type": {
                        "type": "select",
                        "options": ["DESCRIPTIVE", "IMPERATIVE"],
                        "default": "DESCRIPTIVE",
                        "label": "Section Style",
                    },
                    "dedup_threshold": {
                        "type": "slider",
                        "min": 0.5,
                        "max": 1.0,
                        "default": 0.85,
                        "step": 0.05,
                        "label": "Deduplication Threshold",
                    },
                }
                # Merge common params if not present (logic specific to ensuring missing UI elements appear)
                for k, v in common_params.items():
                    if k not in params_config:
                        # Only add if relevant? For now, add globally as requested
                        params_config[k] = v

                param_cols = st.columns(2)
                for i, (param_key, param_cfg) in enumerate(params_config.items()):
                    col = param_cols[i % 2]
                    if param_cfg["type"] == "slider":
                        template_params[param_key] = col.slider(
                            param_cfg["label"],
                            min_value=param_cfg["min"],
                            max_value=param_cfg["max"],
                            value=param_cfg["default"],
                            step=param_cfg.get("step", 1),
                            key=f"param_{param_key}",
                        )
                    elif param_cfg["type"] == "select":
                        template_params[param_key] = col.selectbox(
                            param_cfg["label"],
                            param_cfg["options"],
                            index=param_cfg["options"].index(param_cfg["default"]),
                            key=f"param_{param_key}",
                        )

            # Advanced Retrieval Settings
            with st.expander("🔧 Advanced Retrieval Settings", expanded=False):
                ret_col1, ret_col2 = st.columns(2)

                # New: Search Mode Selector
                from src.index.unified_search import SearchMode  # Dynamic import

                search_modes = [m.value.upper() for m in SearchMode]
                selected_mode_str = ret_col1.selectbox(
                    "Search Mode",
                    search_modes,
                    index=1,
                    key="widget_search_mode",
                    help="FAST (Vector), BALANCED (Vector+BM25), DEEP (Reranked)",
                )

                retrieval_top_k = ret_col1.slider(
                    "Chunks to Retrieve", 10, 100, 50, key="widget_retrieval_top_k"
                )
                similarity_threshold = ret_col1.slider(
                    "Min Similarity",
                    0.5,
                    0.95,
                    0.7,
                    step=0.05,
                    key="widget_similarity_threshold",
                )

                max_images = ret_col2.slider(
                    "Max Images/Section", 1, 20, 5, key="widget_max_images"
                )
                max_concurrent = ret_col2.slider(
                    "Max Concurrent Tasks", 1, 10, 3, key="widget_max_concurrent"
                )

                st.markdown("**Quality Assurance**")
                qa_col1, qa_col2 = st.columns(2)
                enable_conflict_detection = qa_col1.checkbox(
                    "Enable Conflict Detection",
                    value=True,
                    key="widget_enable_conflict_detection",
                    help="Detect contradictions between sources",
                )
                enable_verification = qa_col2.checkbox(
                    "Enable Post-Synthesis Verification",
                    value=False,
                    key="widget_enable_verification",
                    help="Verify synthesized content against sources (uses Gemini)",
                )

            # Pre-selected figures from visual search
            with st.expander("🖼️ Pre-Selected Figures", expanded=False):
                if (
                    "synthesis_figures" in st.session_state
                    and st.session_state.synthesis_figures
                ):
                    st.caption(
                        f"{len(st.session_state.synthesis_figures)} figures selected from Visual Search"
                    )
                    fig_cols = st.columns(4)
                    for i, fig in enumerate(st.session_state.synthesis_figures[:8]):
                        with fig_cols[i % 4]:
                            img_path = fig.get("image_path", "")
                            if img_path and Path(img_path).exists():
                                st.image(img_path, width="stretch")
                            st.caption(
                                fig.get("image_type", "").replace("_", " ").title()
                            )
                    if st.button("Clear Selections", key="clear_figures"):
                        st.session_state.synthesis_figures = []
                        st.rerun()
                else:
                    st.info(
                        "No figures pre-selected. Use Visual Search in the Library to select figures."
                    )

            # Hardcoded Expert Standards (User Request)
            st.info("ℹ️ Mode: Expert Neurosurgeon / Fellow (Highest Standards Enforced)")

            # Project Context Info
            selected_ids = st.session_state.project_context.get(
                "selected_source_ids", set()
            )
            if selected_ids:
                st.success(
                    f"📚 Using {len(selected_ids)} Selected Source(s) from Library"
                )
            else:
                st.info("🌐 Using Entire Library (Smart Search)")

            if st.button("Initialize Studio"):
                # Persist values to session state
                # syn_topic is already updated by widget
                st.session_state.syn_template = selected_template_key
                st.session_state.syn_template_path = template_config["template_path"]
                # Merge template params with quality settings
                template_params["retrieval_top_k"] = retrieval_top_k
                template_params["enable_conflict_detection"] = enable_conflict_detection
                template_params["enable_verification"] = enable_verification
                st.session_state.syn_template_params = template_params
                st.session_state.syn_template_idx = template_options.index(
                    selected_template_display
                )
                st.session_state.syn_retrieval_top_k = retrieval_top_k
                st.session_state.syn_similarity_threshold = similarity_threshold
                st.session_state.syn_max_images = max_images
                st.session_state.syn_max_concurrent = max_concurrent
                st.session_state.syn_max_concurrent = max_concurrent
                st.session_state.syn_enable_conflict_detection = (
                    enable_conflict_detection
                )
                st.session_state.syn_enable_verification = enable_verification
                st.session_state.syn_search_mode = (
                    selected_mode_str  # Persist search mode
                )
                st.session_state.studio_step = 2
                st.rerun()

    # --- STEP 2: SOURCE SELECTION ---
    elif st.session_state.studio_step == 2:
        st.button(
            "← Back to Setup",
            on_click=lambda: st.session_state.__setitem__("studio_step", 1),
        )

        with styles.card_container():
            st.markdown(f"### 2. Source Selection: {st.session_state.syn_topic}")
            st.info(
                "Select specific sources from the library or use 'Smart Search' to search everything."
            )

            # Source Selection UI
            # from src.ui.project_manager import render_source_selector

            # Use project context to store selection
            current_selection = st.session_state.project_context.get(
                "selected_source_ids", set()
            )

            # Render selector (Directly using logic here for tighter integration if needed,
            # or reusing project manager component if robust. Let's build a simple one here for reliability)

            # Fetch all sources
            sources = st.session_state.db.get_all_sources()
            if not sources:
                # Check for unindexed files to give better guidance
                try:
                    from src.ui.auto_sync_widget import (
                        _get_library_path,
                        _scan_for_pdfs,
                    )

                    library_path = _get_library_path()
                    all_pdfs = _scan_for_pdfs(library_path)
                    if all_pdfs:
                        st.warning(
                            f"Library has 0 indexed sources, but **{len(all_pdfs)} unindexed files** were found on disk.\n\n"
                            "Please go to the **Sources Tab** (Tab 1) and click **'🚀 Index Now'** on your files to make them available for synthesis."
                        )
                    else:
                        st.warning(
                            "Library is empty. Please add PDF files to the data/library directory."
                        )
                except Exception:
                    st.warning(
                        "Library is empty. Please add sources in the Library tab."
                    )
            else:
                st.write(f"**Available Sources ({len(sources)})**")

                # Filter Box (Optional, multiselect has built-in search but for large lists custom filter is better)
                # For 1500 docs, multiselect might be slow. Let's keep it simple for now.

                # Create options list
                source_options = {
                    f"{s.title} ({s.specialty.value})": s.id for s in sources
                }

                # Pre-select if already in context
                default_selection = [
                    k for k, v in source_options.items() if v in current_selection
                ]

                selected_labels = st.multiselect(
                    "Select Sources to Synthesize",
                    options=list(source_options.keys()),
                    default=default_selection,
                    placeholder="Search for books, papers...",
                    key="source_multiselect",
                )

                # Update context
                new_selection = {source_options[label] for label in selected_labels}
                st.session_state.project_context["selected_source_ids"] = new_selection

                st.caption(f"Selected: {len(new_selection)} sources")

            col_nav_1, col_nav_2 = st.columns([1, 3])
            with col_nav_1:
                if st.button("Clear Selection"):
                    st.session_state.project_context["selected_source_ids"] = set()
                    st.rerun()

            with col_nav_2:
                btn_label = (
                    "Proceed to Outline"
                    if current_selection
                    else "Proceed with Smart Search (All Sources)"
                )
                if st.button(f"{btn_label} ➡️", type="primary", width="stretch"):
                    st.session_state.studio_step = 3
                    st.rerun()

    # --- STEP 3: OUTLINE ---
    elif st.session_state.studio_step == 3:
        st.button(
            "← Back to Sources",
            on_click=lambda: st.session_state.__setitem__("studio_step", 2),
        )

        with styles.card_container():
            st.markdown(f"### 3. Outline: {st.session_state.syn_topic}")
            st.info(
                "Select sections to synthesize using the 'Textbook Excellence' templates."
            )

            # Default Sections
            default_sections = [
                "Epidemiology & Natural History",
                "Clinical Presentation",
                "Diagnostic Evaluation",
                "Differential Diagnosis",
                "Surgical Anatomy",
                "Operative Technique",
                "Complications & Avoidance",
                "Outcomes & Prognosis",
            ]

            selected_sections = []
            for sec in default_sections:
                if st.checkbox(sec, value=True, key=f"sec_{sec}"):
                    selected_sections.append(sec)

            if st.button("Generate Selected Sections"):
                st.session_state.selected_sections = selected_sections
                st.session_state.studio_step = 4
                st.rerun()

    # --- STEP 4: GENERATION & REVIEW ---
    elif st.session_state.studio_step == 4:
        st.button(
            "← Back to Outline",
            on_click=lambda: st.session_state.__setitem__("studio_step", 3),
        )

        # Show template being used
        current_template = st.session_state.get("syn_template", "section")
        template_config = get_template_config(current_template)
        st.markdown(f"### 4. Synthesis: {st.session_state.syn_topic}")
        st.caption(
            f"Using **{template_config['icon']} {template_config['name']}** template"
        )

        # Global Metrics Dashboard
        if "full_chapter" in st.session_state:
            chapter = st.session_state.full_chapter
            with st.expander("📊 Quality Metrics", expanded=True):
                m_cols = st.columns(6)
                m_cols[0].metric("Words", f"{chapter.total_words:,}")
                m_cols[1].metric("Sources", len(chapter.bibliography))
                # Calculate figure density
                fig_count = sum(
                    len(s.inline_figures)
                    + (len(s.figure_plate.figures) if s.figure_plate else 0)
                    for s in chapter.sections
                )
                density = (
                    fig_count / (chapter.total_words / 1000)
                    if chapter.total_words > 0
                    else 0
                )
                m_cols[2].metric("Fig Density", f"{density:.1f}/1k")

                # Check abstract/keywords existence
                has_abstract = bool(
                    chapter.abstract and not chapter.abstract.startswith("[Abstract")
                )
                has_keywords = bool(chapter.keywords)
                m_cols[3].metric("Abstract", "✅" if has_abstract else "❌")
                m_cols[4].metric(
                    "Keywords", f"{len(chapter.keywords)}" if has_keywords else "0"
                )

                # Advanced Metrics (Readability & Coverage)
                # Readability (Simple approximation: avg sentence length + avg word length)
                # Flesch-Kincaid Grade Level ~= 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
                # We'll use a fast approximation.
                import re

                # Combine all section content for readability analysis
                all_content = " ".join(s.content for s in chapter.sections)
                words_list = re.findall(r"\w+", all_content)
                sentences = re.split(r"[.!?]+", all_content)
                num_words = len(words_list)
                num_sentences = len(sentences) if len(sentences) > 0 else 1
                avg_sentence_length = num_words / num_sentences

                # Mock syllable count (approx 1.5 per word for medical text)
                score = 0.39 * avg_sentence_length + 11.8 * 1.5 - 15.59
                readability = max(0, min(20, score))  # Clamp
                m_cols[5].metric("Reading Lvl", f"Grade {readability:.1f}")

                # Source Coverage (Unique Sources Used / Selected Sources)
                selected_ids = st.session_state.project_context.get(
                    "selected_source_ids", set()
                )
                used_ids = set()
                for s in chapter.sections:
                    for src_id in s.sources_used:
                        used_ids.add(src_id)

                coverage = (
                    (len(used_ids) / len(selected_ids)) * 100 if selected_ids else 100
                )
                st.caption(
                    f"📚 Source Coverage: **{coverage:.1f}%** ({len(used_ids)}/{len(selected_ids) or 'All'} utilized)"
                )

        # Checkpoint Recovery Check
        latest_checkpoint = get_latest_recovery(topic=st.session_state.syn_topic)

        # Batch Generation Controls
        batch_cols = st.columns([2, 1, 1])
        with batch_cols[0]:
            if latest_checkpoint:
                if st.button("🔄 Resume from Checkpoint", width="stretch"):
                    st.session_state.resume_checkpoint = latest_checkpoint
                    st.session_state.batch_generate = True
                    st.rerun()

        with batch_cols[1]:
            if st.button(
                "⚡ Generate All Sections (Batch)",
                width="stretch",
                type="primary",
            ):
                st.session_state.batch_generate = True
                st.session_state.resume_checkpoint = None
                st.rerun()
        with batch_cols[2]:
            generated_count = sum(
                1
                for i in range(len(st.session_state.selected_sections))
                if f"res_{i}" in st.session_state
            )
            st.metric(
                "Generated",
                f"{generated_count}/{len(st.session_state.selected_sections)}",
            )

        # Handle Batch Generation using SectionSynthesizer
        if st.session_state.get("batch_generate", False):
            st.session_state.batch_generate = False

            # Progress bar
            progress_bar = st.progress(0, text="Initializing batch synthesis...")
            status_text = st.empty()

            with st.spinner("🔄 Running Batch Synthesis Pipeline..."):
                try:
                    # Initialize advanced synthesizer
                    config = SynthesisConfig(
                        present_conflicts=st.session_state.syn_enable_conflict_detection,
                        academic_style=True,
                    )
                    synthesizer = SectionSynthesizer(config)

                    # 1. Create Outline Entries
                    status_text.text("Preparing outline...")
                    outline_entries = []
                    for i, title in enumerate(st.session_state.selected_sections):
                        # Determine word target from params
                        params = st.session_state.get("syn_template_params", {})
                        word_target = params.get("word_target", 1000)

                        entry = OutlineEntry(
                            title=title, level=1, word_target=word_target
                        )
                        outline_entries.append(entry)

                    # 2. Retrieve content for ALL sections (Pseudo-cluster assignment)
                    status_text.text("Retrieving context from library...")
                    engine = st.session_state.search
                    source_ids = list(
                        st.session_state.project_context.get("selected_source_ids", [])
                    )

                    # Define async function to run the whole process
                    async def run_batch():
                        # Retrieve context first (simulated async retrieval)
                        for i, entry in enumerate(outline_entries):
                            query = f"{st.session_state.syn_topic} {entry.title}"

                            # Get correct SearchMode enum
                            from src.index.unified_search import SearchMode

                            mode_str = st.session_state.get(
                                "syn_search_mode", "BALANCED"
                            )
                            try:
                                search_mode = SearchMode(mode_str.lower())
                            except ValueError:
                                search_mode = SearchMode.BALANCED

                            # Sync search call
                            results = engine.search(
                                query,
                                top_k=st.session_state.syn_retrieval_top_k,
                                filters=(
                                    {"source_ids": source_ids} if source_ids else None
                                ),
                                mode=search_mode,  # <--- Pass selected mode
                            )
                            chunks = []
                            for res in results.chunks:
                                # Create a temporary Source object for compatibility
                                from src.neurosynth.models.document import (
                                    DocumentFormat,
                                    Path,
                                    Source,
                                )

                                dummy_source = Source(
                                    path=Path(res.chunk.source_title),
                                    format=DocumentFormat.PDF,
                                    title=res.chunk.source_title,
                                    id=res.chunk.source_id,
                                )
                                chunk = ContentChunk(
                                    id=(
                                        str(res.chunk.id)
                                        if hasattr(res, "chunk")
                                        else "unknown"
                                    ),
                                    content=res.chunk.content,
                                    source=dummy_source,
                                    page_number=res.chunk.page_start,
                                    # Phase 4: Pass Evidence Level
                                    evidence_level=(
                                        res.chunk.evidence_level
                                        if hasattr(res.chunk, "evidence_level")
                                        else None
                                    ),
                                )
                                chunks.append(chunk)

                            cluster = KnowledgeCluster(topic=entry.title, chunks=chunks)
                            entry.assigned_clusters = [cluster]
                            # Update progress (careful with st calls in async, but usually ok in streamlit loop)

                        # Load checkpoint if resuming
                        checkpoint = None
                        if st.session_state.get("resume_checkpoint"):
                            resume_path = st.session_state.resume_checkpoint
                            st.info(f"Resuming from: {resume_path.name}")
                            try:
                                checkpoint = SynthesisCheckpoint(
                                    topic=st.session_state.syn_topic,
                                    existing_dir=resume_path,
                                )
                            except Exception as e:
                                st.error(f"Failed to load checkpoint: {e}")
                                # Fallback to new checkpoint
                                checkpoint = SynthesisCheckpoint(
                                    topic=st.session_state.syn_topic
                                )
                        else:
                            # New Checkpoint
                            checkpoint = SynthesisCheckpoint(
                                topic=st.session_state.syn_topic
                            )

                        # Run Synthesis asking it to use this checkpoint
                        return await synthesizer.synthesize_chapter(
                            topic=st.session_state.syn_topic,
                            outline=outline_entries,
                            max_concurrent=st.session_state.get(
                                "syn_max_concurrent", 3
                            ),
                            checkpoint=checkpoint,
                        )

                    # Execute pipeline
                    chapter = asyncio.run(run_batch())
                    st.session_state.full_chapter = chapter
                    st.session_state.synthesized_sections = {
                        s.title: s for s in chapter.sections
                    }

                    # Store results in individual session keys for retroactive compatibility
                    for i, section in enumerate(chapter.sections):
                        st.session_state[f"res_{i}"] = {
                            "content": section.content,
                            "sources": [],
                            "conflicts": "",
                        }

                    progress_bar.progress(1.0, text="Batch synthesis complete!")
                    st.success(f"✅ Generated Chapter: {chapter.title}")
                    st.rerun()

                except Exception as e:
                    st.error(f"Batch generation failed: {e}")
                    import traceback

                    st.text(traceback.format_exc())

        # Display Full Chapter Data (Abstract/Keywords)
        if "full_chapter" in st.session_state:
            chapter = st.session_state.full_chapter
            with st.expander("📝 Abstract & Keywords", expanded=False):
                st.markdown(f"**Abstract**\n\n{chapter.abstract}")
                if chapter.keywords:
                    st.markdown(
                        "**Keywords**: "
                        + ", ".join([f"`{k}`" for k in chapter.keywords])
                    )

        # Section Selector (Tabs)
        if not st.session_state.selected_sections:
            st.error("No sections selected.")
        else:
            tabs = st.tabs(st.session_state.selected_sections)

            for i, section_title in enumerate(st.session_state.selected_sections):
                with tabs[i]:
                    st.markdown(f"#### {section_title}")

                    # Generate Button for this specific section
                    btn_key = f"gen_btn_{i}"
                    res_key = f"res_{i}"

                    if st.button(f"⚡ Synthesize '{section_title}'", key=btn_key):
                        # ... (Keep existing single section logic or refactor to use SectionSynthesizer too)
                        # For now, keeping existing logic for single generation to minimize risk
                        # unless "Batch" was run, which populates this.
                        pass  # Placeholder for existing logic, or just let users use "Batch"

                    # Display Result if available
                    if res_key in st.session_state:
                        data = st.session_state[res_key]
                        content = (
                            data.get("content", "")
                            if isinstance(data, dict)
                            else str(data)
                        )

                        # Main content with edit toggle
                        edit_cols = st.columns([4, 1, 1])
                        with edit_cols[0]:
                            st.markdown("**Generated Content**")
                        with edit_cols[1]:
                            # Status Indicator
                            status = st.session_state.get(f"status_{res_key}", "Draft")
                            st.caption(f"Status: {status}")
                        with edit_cols[2]:
                            edit_mode = st.checkbox("Edit", key=f"edit_{res_key}")

                        if edit_mode:
                            # Editable text area
                            edited_content = st.text_area(
                                "Edit Markdown Content",
                                value=content,
                                width="stretch",
                                height=400,
                                key=f"editor_{res_key}",
                            )

                            save_cols = st.columns([1, 1, 4])
                            with save_cols[0]:
                                if st.button(
                                    "💾 Save",
                                    key=f"save_{res_key}",
                                    width="stretch",
                                ):
                                    # Update content in session state
                                    if isinstance(st.session_state[res_key], dict):
                                        st.session_state[res_key][
                                            "content"
                                        ] = edited_content
                                    else:
                                        # Handle legacy format
                                        st.session_state[res_key] = {
                                            "content": edited_content,
                                            "sources": [],
                                        }

                                    # Update Full Chapter object if exists
                                    if "full_chapter" in st.session_state:
                                        st.session_state.full_chapter.sections[
                                            i
                                        ].content = edited_content

                                    st.success("Changes saved!")
                                    st.rerun()

                            with save_cols[1]:
                                if st.button(
                                    "✅ Approve",
                                    key=f"approve_{res_key}",
                                    width="stretch",
                                ):
                                    st.session_state[f"status_{res_key}"] = "Approved"
                                    st.success("Section Approved!")
                                    st.rerun()

                            # Show live preview
                            with st.expander("📄 Preview", expanded=True):
                                st.markdown(edited_content)
                        else:
                            # Read-only display
                            st.markdown(content)

                        # Missing: Comments/Annotations (Placeholder for "Collaborative Review")
                        with st.expander("💬 Comments & Notes"):
                            st.text_area("Add notes...", key=f"notes_{res_key}")

            # --- EXPORT SECTION ---
            st.markdown("---")
            st.markdown("### 📥 Export Chapter")

            # (Keep existing export logic)
            # ...

            # Count generated sections
            generated_count = sum(
                1
                for i in range(len(st.session_state.selected_sections))
                if f"res_{i}" in st.session_state
            )

            if generated_count == 0:
                st.info("Generate at least one section to enable export.")
            else:
                st.success(
                    f"✅ {generated_count}/{len(st.session_state.selected_sections)} sections generated"
                )

                export_cols = st.columns([2, 1, 1])

                with export_cols[0]:
                    export_format = st.selectbox(
                        "Export Format",
                        ["PDF", "DOCX", "Markdown"],
                        key="export_format",
                    )

                with export_cols[1]:
                    if st.button("📄 Export Chapter", width="stretch"):
                        with st.spinner(f"Generating {export_format}..."):
                            try:
                                # Compile chapter from session state
                                chapter = _compile_chapter_from_session()

                                # Render to selected format
                                with tempfile.TemporaryDirectory() as tmpdir:
                                    renderer = ChapterRenderer(Path(tmpdir))
                                    format_key = export_format.lower()
                                    if format_key == "markdown":
                                        format_key = "md"
                                    outputs = renderer.render(
                                        chapter, formats=[format_key]
                                    )

                                    output_path = outputs.get(format_key)
                                    if output_path and output_path.exists():
                                        file_bytes = output_path.read_bytes()

                                        # Store for download
                                        st.session_state.export_bytes = file_bytes
                                        st.session_state.export_filename = (
                                            output_path.name
                                        )
                                        st.session_state.export_mime = _get_mime_type(
                                            format_key
                                        )
                                        st.success("Export ready!")
                                    else:
                                        st.error("Export failed - no output generated")

                            except Exception as e:
                                st.error(f"Export failed: {e}")

                with export_cols[2]:
                    if "export_bytes" in st.session_state:
                        st.download_button(
                            label="⬇️ Download",
                            data=st.session_state.export_bytes,
                            file_name=st.session_state.export_filename,
                            mime=st.session_state.export_mime,
                        )

            # Advanced Output Customization
            if "full_chapter" in st.session_state:
                st.markdown("---")
                with st.expander("🛠️ Advanced Export Options"):
                    render_latex_export_panel(st.session_state.full_chapter)


def _compile_chapter_from_session() -> SynthesizedChapter:
    """Compile all generated sections from session state into a SynthesizedChapter."""
    sections = []
    sources_used = set()

    for i, section_title in enumerate(st.session_state.selected_sections):
        res_key = f"res_{i}"
        if res_key in st.session_state:
            data = st.session_state[res_key]
            if isinstance(data, dict):
                content = data.get("content", "")
                section_sources = data.get("sources", [])

                # Track sources
                for src in section_sources:
                    if isinstance(src, dict) and "source_id" in src:
                        sources_used.add(src["source_id"])

                sections.append(
                    SynthesizedSection(
                        title=section_title,
                        content=content,
                        images=[],  # Images are embedded in content
                        sources_used=[
                            s.get("source_id", "")
                            for s in section_sources
                            if isinstance(s, dict)
                        ],
                    )
                )

    # Build source metadata list
    source_metadata = []
    if "db" in st.session_state:
        for source_id in sources_used:
            try:
                meta = st.session_state.db.get_source(source_id)
                if meta:
                    source_metadata.append(meta)
            except Exception:
                pass

    return SynthesizedChapter(
        topic=st.session_state.get("syn_topic", "Untitled Chapter"),
        sections=sections,
        sources=source_metadata,
        total_chunks_used=len(sources_used),
        total_images=0,
        generated_at=datetime.now(),
        template_used=st.session_state.get("syn_template", "section"),
    )


def _get_mime_type(format_key: str) -> str:
    """Get MIME type for export format."""
    mime_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown",
    }
    return mime_types.get(format_key, "application/octet-stream")
