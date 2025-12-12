import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="NeuroSynth",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Project Context (Shared State)
if "project_context" not in st.session_state:
    st.session_state.project_context = {"selected_source_ids": set()}

import sys
from pathlib import Path

# 1. IMPORT THE MODULES
from study_suite import gui as study_gui

# Add src to path to allow importing from src
sys.path.append(str(Path(__file__).parent))

from src.index import Database
from src.ui import library, styles, synthesis_page
from src.ui.advanced_features import (
    render_checkpoint_recovery_panel,
    render_clustering_panel,
    render_figure_integration_panel,
    render_gap_detection_panel,
    render_latex_export_panel,
    render_modality_classification_panel,
    render_procedural_correlation_panel,
)
from src.ui.analytics import render_analytics_dashboard, render_embedding_controls
from src.ui.auto_sync_widget import render_auto_sync_widget
from src.ui.batch_indexing import render_batch_indexing_panel
from src.ui.clinical_qa import render_clinical_qa_panel
from src.ui.embedding_control_panel import render_embedding_control_panel
from src.ui.phase4_enhancements import (
    render_batch_processing_controls,
    render_phase4_compact,
    render_phase4_enhancements_panel,
)
from src.ui.precision_search import render_precision_search_panel
from src.ui.project_manager import render_loaded_project_info, render_project_manager
from src.ui.search_results import get_search_history
from src.ui.synthesis_history import (
    render_synthesis_history,
    render_synthesis_history_summary,
)


@st.cache_resource
def get_db_connection():
    return Database()


# 2. APPLY GLOBAL STYLES
styles.apply_styles()

# 3. SIDEBAR NAVIGATION
st.sidebar.title("NeuroSynth")
st.sidebar.caption("v1.0.0 | Textbook Excellence Engine")

# Show active project in sidebar
render_loaded_project_info()

# Phase 4 compact status
render_phase4_compact()

mode = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Reference Library",
        "Deep Search",
        "Clinical QA",
        "Synthesis Studio",
        "Projects",
        "History",
        "Advanced",
        "Analytics",
        "📥 Index PDFs",
        "Settings",
        "Resident Core",
    ],
    index=0,
    key="navigation",
)

# 4. DASHBOARD (HOME)
if mode == "Dashboard":
    st.title("Command Center")
    st.markdown("### System Status")

    # Live Metrics
    try:
        db = get_db_connection()
        stats = db.get_stats()

        col1, col2, col3 = st.columns(3)
        with col1:
            styles.metric_card("Indexed Documents", stats.get("sources", 0))
        with col2:
            styles.metric_card("Knowledge Chunks", stats.get("chunks", 0))
        with col3:
            styles.metric_card("Extracted Images", stats.get("images", 0))

    except Exception as e:
        st.error(f"Database Connection Failed: {e}")

    st.markdown("---")
    st.markdown("### Quick Actions")

    def navigate_to(page):
        st.session_state.navigation = page
        if page == "Synthesis Studio":
            st.session_state.studio_step = 1

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.button(
            "✨ New Synthesis",
            width="stretch",
            on_click=navigate_to,
            args=("Synthesis Studio",),
        )
    with c2:
        st.button(
            "📚 Browse Library",
            width="stretch",
            on_click=navigate_to,
            args=("Reference Library",),
        )
    with c3:
        st.button(
            "🎯 Deep Search",
            width="stretch",
            on_click=navigate_to,
            args=("Deep Search",),
        )
    with c4:
        st.button(
            "🩺 Clinical QA",
            width="stretch",
            on_click=navigate_to,
            args=("Clinical QA",),
        )

    # Auto-Sync Widget and History Summary
    st.markdown("---")
    col_sync, col_history = st.columns(2)

    with col_sync:
        render_auto_sync_widget()

    with col_history:
        render_synthesis_history_summary()

elif mode == "Reference Library":
    library.render_library()

elif mode == "Deep Search":
    # Deep-DX Precision Search with ColBERT
    st.title("🎯 Deep-DX Precision Search")
    st.caption("Hybrid Dense + BM25 → ColBERT Reranking | Authority-Boosted")
    render_precision_search_panel()

elif mode == "Clinical QA":
    # Clinical Question Answering
    st.title("🩺 Clinical Question Answering")
    st.caption("Fast, focused answers to clinical questions")
    render_clinical_qa_panel()

elif mode == "Synthesis Studio":
    synthesis_page.render_synthesis_page()

elif mode == "Projects":
    # Project Manager
    st.title("📁 Project Manager")
    st.caption("Manage synthesis projects")
    render_project_manager()

elif mode == "History":
    # Synthesis History
    st.title("📜 Synthesis History")
    st.caption("Browse past synthesis sessions")
    render_synthesis_history()

elif mode == "Advanced":
    # Advanced Features Hub
    st.title("🔬 Advanced Features")
    st.caption("Power tools for synthesis pipeline control")

    adv_tab = st.tabs(
        [
            "🔍 Gap Detection",
            "🧬 Clustering",
            "📋 Procedural",
            "🖼️ Figures",
            "🏷️ Modality",
            "💾 Checkpoints",
            "📄 LaTeX Export",
        ]
    )

    with adv_tab[0]:
        render_gap_detection_panel()

    with adv_tab[1]:
        render_clustering_panel()

    with adv_tab[2]:
        render_procedural_correlation_panel()

    with adv_tab[3]:
        render_figure_integration_panel()

    with adv_tab[4]:
        render_modality_classification_panel()

    with adv_tab[5]:
        render_checkpoint_recovery_panel()

    with adv_tab[6]:
        render_latex_export_panel()

elif mode == "Analytics":
    # Analytics Dashboard with embedding controls
    try:
        db = Database()
        render_analytics_dashboard(db=db, search_history=get_search_history())

        st.divider()

        # Embedding controls section
        render_embedding_controls(db=db)

    except Exception as e:
        st.error(f"Analytics Error: {e}")
        render_analytics_dashboard(db=None, search_history=get_search_history())

elif mode == "📥 Index PDFs":
    # Batch PDF Indexing
    render_batch_indexing_panel()

elif mode == "Settings":
    # Phase 4 Enhancements and Settings
    st.title("⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(
        ["⚡ Phase 4 Enhancements", "🔄 Batch Processing", "📊 Embedding Pipeline"]
    )

    with tab1:
        render_phase4_enhancements_panel()

    with tab2:
        render_batch_processing_controls()

    with tab3:
        render_embedding_control_panel()

elif mode == "Resident Core":
    study_gui.render_study_suite()
