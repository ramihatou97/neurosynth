"""
Synthesis History Browser UI Component
======================================
Browse past synthesis sessions with query, sources, and output links.
Uses the Reference Library database for persistence.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


def _get_synthesis_database():
    """Get the Reference Library database for synthesis history."""
    if "synth_history_db" not in st.session_state:
        try:
            from src.reference_library.cache.database import Database
            from src.reference_library.config import DATABASE_PATH

            st.session_state.synth_history_db = Database(DATABASE_PATH)
        except Exception as e:
            st.error(f"Failed to initialize synthesis history database: {e}")
            return None
    return st.session_state.synth_history_db


def render_synthesis_history():
    """
    Render the Synthesis History browser.

    Features:
    - Browse past synthesis sessions
    - View query, mode, sources used
    - Open output files
    - View detailed manifest
    - Statistics dashboard
    """
    st.markdown("### 📜 Synthesis History")
    st.caption("Browse past synthesis sessions and their outputs")

    db = _get_synthesis_database()
    if not db:
        return

    # Tabs for history and stats
    tab1, tab2 = st.tabs(["📋 History", "📊 Statistics"])

    with tab1:
        _render_history_list(db)

    with tab2:
        _render_synthesis_stats(db)


def _render_history_list(db):
    """Render the history list."""
    try:
        history = db.get_synthesis_history(limit=50)
    except Exception as e:
        st.error(f"Failed to load history: {e}")
        return

    if not history:
        st.info("No synthesis history found. Create your first synthesis!")
        return

    # Filter controls
    col1, col2 = st.columns([3, 1])
    with col1:
        filter_text = st.text_input(
            "Filter",
            placeholder="Filter by topic or query...",
            key="history_filter",
            label_visibility="collapsed",
        )
    with col2:
        success_filter = st.selectbox(
            "Status",
            ["All", "Success", "Failed"],
            key="history_status_filter",
            label_visibility="collapsed",
        )

    # Apply filters
    filtered = history
    if filter_text:
        filter_lower = filter_text.lower()
        filtered = [
            h
            for h in filtered
            if filter_lower in h.get("topic", "").lower()
            or filter_lower in h.get("search_query", "").lower()
        ]
    if success_filter == "Success":
        filtered = [h for h in filtered if h.get("success")]
    elif success_filter == "Failed":
        filtered = [h for h in filtered if not h.get("success")]

    st.markdown(f"**{len(filtered)} sessions found**")

    for item in filtered:
        _render_history_item(item, db)


def _render_history_item(item: dict, db):
    """Render a single history item."""
    topic = item.get("topic", "Untitled")
    query = item.get("search_query", "")
    mode = item.get("search_mode", "hybrid")
    success = item.get("success", False)
    created_at = item.get("created_at")
    output_path = item.get("output_path")
    source_count = item.get("source_count", 0)
    surgical_count = item.get("surgical_count", 0)
    theoretical_count = item.get("theoretical_count", 0)

    # Format date
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at)
            else:
                dt = created_at
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(created_at)[:16]
    else:
        date_str = "Unknown"

    # Status icon
    status_icon = "✅" if success else "❌"

    with st.expander(f"{status_icon} **{topic}** | {date_str}", expanded=False):
        # Info columns
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"**Query:** {query or 'N/A'}")
            st.caption(f"Mode: {mode.upper()}")

        with col2:
            st.metric("Sources", source_count)
            st.caption(
                f"🔧 {surgical_count} surgical | 📖 {theoretical_count} clinical"
            )

        with col3:
            template = item.get("template_used") or "Auto"
            st.markdown(f"**Template:** {template}")

        # Output file
        if output_path:
            output_file = Path(output_path)
            if output_file.exists():
                st.divider()
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"📄 **Output:** `{output_file.name}`")
                with col_b:
                    with open(output_file, "rb") as f:
                        st.download_button(
                            "⬇️ Download",
                            f,
                            file_name=output_file.name,
                            key=f"dl_hist_{item.get('id')}",
                            width="stretch",
                        )
            else:
                st.caption(f"📄 Output: {output_path} (file not found)")

        # Error message
        if not success and item.get("error_message"):
            st.error(f"Error: {item.get('error_message')}")

        # View details button
        synthesis_id = item.get("id")
        if synthesis_id and st.button("📋 View Details", key=f"details_{synthesis_id}"):
            _show_synthesis_detail(db, synthesis_id)


def _show_synthesis_detail(db, synthesis_id: int):
    """Show detailed view of a synthesis session."""
    try:
        detail = db.get_synthesis_detail(synthesis_id)
    except Exception as e:
        st.error(f"Failed to load details: {e}")
        return

    if not detail:
        st.warning("Details not found")
        return

    st.markdown("---")
    st.markdown(f"### 📋 Details: {detail.get('topic', 'Unknown')}")

    # Sources used
    sources = detail.get("sources", [])
    if sources:
        st.markdown("#### 📚 Sources Used")

        for source in sources:
            original = source.get("original_source", "Unknown")
            category = source.get("category", "")
            pages = source.get("pages", [])

            if isinstance(pages, str):
                try:
                    pages = json.loads(pages)
                except Exception:
                    pages = []

            page_str = f"Pages: {pages}" if pages else ""
            st.markdown(f"- **{original}** ({category}) {page_str}")

    # Manifest
    manifest_json = detail.get("manifest_json")
    if manifest_json:
        with st.expander("📦 Full Manifest (JSON)", expanded=False):
            try:
                manifest = json.loads(manifest_json)
                st.json(manifest)
            except Exception:
                st.code(manifest_json)


def _render_synthesis_stats(db):
    """Render synthesis statistics dashboard."""
    try:
        stats = db.get_synthesis_stats()
    except Exception as e:
        st.error(f"Failed to load stats: {e}")
        return

    st.markdown("### 📊 Synthesis Statistics")

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Syntheses", stats.get("total_syntheses", 0))
    with col2:
        st.metric("Successful", stats.get("successful_syntheses", 0))
    with col3:
        st.metric("Sources Used", stats.get("total_sources_used", 0))
    with col4:
        total = stats.get("total_syntheses", 0)
        successful = stats.get("successful_syntheses", 0)
        rate = (successful / total * 100) if total > 0 else 0
        st.metric("Success Rate", f"{rate:.0f}%")

    st.divider()

    # Source breakdown
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Source Types")
        surgical = stats.get("surgical_sources_used", 0)
        theoretical = stats.get("theoretical_sources_used", 0)

        if surgical or theoretical:
            st.bar_chart({"Surgical": surgical, "Clinical": theoretical})
        else:
            st.info("No source data")

    with col_b:
        st.markdown("#### Common Topics")
        common_topics = stats.get("common_topics", [])

        if common_topics:
            for topic in common_topics[:5]:
                name = topic.get("topic", "Unknown")
                count = topic.get("count", 0)
                st.markdown(f"- **{name}** ({count} times)")
        else:
            st.info("No topic data")


def render_synthesis_history_summary():
    """Render a summary widget for the dashboard."""
    db = _get_synthesis_database()
    if not db:
        return

    try:
        history = db.get_synthesis_history(limit=3)
    except Exception:
        return

    st.markdown("### 📜 Recent Syntheses")

    if not history:
        st.caption("No synthesis history")
        return

    for item in history:
        status = "✅" if item.get("success") else "❌"
        topic = item.get("topic", "Untitled")[:30]
        st.caption(f"{status} {topic}")
