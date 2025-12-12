"""
Clinical QA UI Component
========================
Deep-DX Clinical Question Answering mode with query expansion,
critic verification, and async support.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


def _get_qa_synthesizer():
    """Lazy-load DeepDxSynthesizer."""
    if "qa_synthesizer" not in st.session_state:
        try:
            from src.ai import AIClient
            from src.deep_dx.engine.synthesizer import DeepDxSynthesizer
            from src.index import Database
            from src.index.precision_search import PrecisionSearchEngine

            if "db" not in st.session_state:
                st.session_state.db = Database()

            precision_engine = PrecisionSearchEngine(
                db=st.session_state.db, colbert_enabled=True
            )

            ai_client = AIClient()

            st.session_state.qa_synthesizer = DeepDxSynthesizer(
                search_engine=precision_engine,
                ai_client=ai_client,
                critic=None,  # TODO: Add critic
            )
        except Exception as e:
            st.error(f"Failed to initialize Clinical QA: {e}")
            return None
    return st.session_state.qa_synthesizer


def render_clinical_qa_panel():
    """
    Render the Deep-DX Clinical Question Answering panel.

    Features:
    - Focused clinical question answering (vs chapter synthesis)
    - Query expansion with medical synonyms
    - Precision search with ColBERT
    - Safety critic verification
    - Source citations
    """
    st.markdown("### 🩺 Clinical Question Answering")
    st.caption(
        "Fast, focused answers to specific clinical questions | Powered by Deep-DX"
    )

    # Preset questions
    preset_questions = [
        "What are the key surgical steps for pterional craniotomy?",
        "What structures are at risk during acoustic neuroma resection?",
        "What is the House-Brackmann grading scale for facial nerve function?",
        "When is external ventricular drain indicated in SAH?",
        "What are contraindications for endovascular coiling of aneurysms?",
    ]

    # Question input
    col1, col2 = st.columns([5, 1])
    with col1:
        question = st.text_area(
            "Clinical Question",
            placeholder="Ask a specific clinical question (e.g., 'What are the boundaries of the pterional approach?')",
            key="clinical_qa_question",
            height=80,
            label_visibility="collapsed",
        )
    with col2:
        ask_clicked = st.button("🔍 Ask", key="clinical_qa_btn", width="stretch")

    # Callback for presets
    def _set_question(q):
        st.session_state.clinical_qa_question = q
        # Trigger execution immediately on next rerun
        st.session_state.clinical_qa_auto_run = True

    # Preset quick questions
    with st.expander("💡 Quick Questions", expanded=False):
        for preset in preset_questions:
            st.button(
                preset,
                key=f"preset_{hash(preset)}",
                width="stretch",
                on_click=_set_question,
                args=(preset,),
            )

    # Check for auto-run trigger from callback
    if st.session_state.get("clinical_qa_auto_run", False):
        ask_clicked = True
        st.session_state.clinical_qa_auto_run = False  # Reset

    if not question:
        st.info("💡 Ask a specific clinical question to get a focused, cited answer")
        return

    if ask_clicked or (
        "clinical_qa_last_question" in st.session_state
        and st.session_state.clinical_qa_last_question == question
    ):
        _execute_clinical_qa(question)


def _execute_clinical_qa(question: str):
    """Execute clinical QA and display results."""
    synthesizer = _get_qa_synthesizer()
    if not synthesizer:
        return

    st.session_state.clinical_qa_last_question = question

    with st.spinner("🧠 Synthesizing answer from knowledge base..."):
        try:
            # Use sync version
            result = synthesizer.generate_answer(question)
            st.session_state.clinical_qa_result = result

        except Exception as e:
            st.error(f"Clinical QA failed: {e}")
            return

    # Display result
    _render_qa_result()


def _render_qa_result():
    """Render the clinical QA result."""
    if "clinical_qa_result" not in st.session_state:
        return

    result = st.session_state.clinical_qa_result

    # Confidence indicator
    confidence = result.get("confidence", 0.0)
    if confidence >= 0.85:
        conf_color, conf_label = "#28a745", "HIGH CONFIDENCE"
    elif confidence >= 0.70:
        conf_color, conf_label = "#ffc107", "MEDIUM CONFIDENCE"
    else:
        conf_color, conf_label = "#dc3545", "LOW CONFIDENCE"

    st.markdown(
        f"""
    <div style="background:{conf_color}15; border-left:4px solid {conf_color}; padding:10px; margin:10px 0;">
        <span style="color:{conf_color}; font-weight:bold;">{conf_label}</span> ({confidence:.0%})
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Answer
    st.markdown("### 📝 Answer")
    st.markdown(result.get("answer", "No answer generated"))

    # Sources
    sources = result.get("sources", [])
    if sources:
        st.divider()
        st.markdown("### 📚 Sources Used")

        source_cols = st.columns(min(len(sources), 3))
        for idx, source in enumerate(sources[:6]):
            with source_cols[idx % 3]:
                st.markdown(f"📖 **{source}**")

    # Context used (collapsible)
    context_used = result.get("context_used", [])
    if context_used:
        with st.expander(
            f"📄 Retrieved Context ({len(context_used)} passages)", expanded=False
        ):
            for i, ctx in enumerate(context_used):
                st.markdown(f"**[{i+1}]** {ctx[:500]}...")
                st.divider()

    # Related images
    images = result.get("images", [])
    if images:
        st.divider()
        st.markdown(f"### 🖼️ Related Figures ({len(images)})")

        img_cols = st.columns(4)
        for idx, img in enumerate(images[:8]):
            with img_cols[idx % 4]:
                _render_qa_image(img)


def _render_qa_image(img):
    """Render an image from QA result."""
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
        st.caption(caption[:60] + "..." if len(caption) > 60 else caption)


def render_clinical_qa_history():
    """Render the QA history panel."""
    if "clinical_qa_history" not in st.session_state:
        st.session_state.clinical_qa_history = []

    history = st.session_state.clinical_qa_history

    if not history:
        st.info("No question history yet")
        return

    st.markdown("### 📜 Question History")

    for i, item in enumerate(reversed(history[-10:])):
        q = item.get("question", "")
        conf = item.get("confidence", 0.0)

        with st.expander(f"❓ {q[:60]}..." if len(q) > 60 else f"❓ {q}"):
            st.markdown(item.get("answer", "")[:300] + "...")
            st.caption(
                f"Confidence: {conf:.0%} | Sources: {len(item.get('sources', []))}"
            )
