"""
Project Manager UI Component
============================
Project persistence with save/load synthesis projects.

Structure:
    ~/Documents/NeuroSynth/projects/{topic_name}/
    ├── sources/          # Extracted source PDFs
    ├── images/           # Filtered medical images
    ├── output/           # Generated chapters (PDF, LaTeX, Markdown)
    ├── manifest.json     # Metadata linking sources to synthesis
    └── project.json      # Project metadata
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import streamlit as st

# Ensure src is in path
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))


def _get_projects_base_dir() -> Path:
    """Get the base directory for projects."""
    return Path.home() / "Documents" / "NeuroSynth" / "projects"


def _get_all_projects() -> list[dict]:
    """Get all existing projects with metadata."""
    base_dir = _get_projects_base_dir()
    projects = []

    if not base_dir.exists():
        return projects

    for project_dir in base_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_json = project_dir / "project.json"
        manifest_json = project_dir / "manifest.json"

        project_data = {
            "path": project_dir,
            "name": project_dir.name,
            "topic": project_dir.name.replace("_", " ").title(),
            "created_at": None,
            "source_count": 0,
            "image_count": 0,
            "output_count": 0,
            "has_output": False,
            "template_type": None,
        }

        # Load project metadata
        if project_json.exists():
            try:
                with open(project_json) as f:
                    meta = json.load(f)
                project_data["topic"] = meta.get("topic", project_data["topic"])
                project_data["created_at"] = meta.get("created_at")
                project_data["template_type"] = meta.get("template_type")
            except Exception:
                pass

        # Count files
        sources_dir = project_dir / "sources"
        images_dir = project_dir / "images"
        output_dir = project_dir / "output"

        if sources_dir.exists():
            project_data["source_count"] = len(list(sources_dir.glob("*.pdf")))
        if images_dir.exists():
            project_data["image_count"] = len(list(images_dir.glob("*.*")))
        if output_dir.exists():
            outputs = list(output_dir.glob("*.*"))
            project_data["output_count"] = len(outputs)
            project_data["has_output"] = len(outputs) > 0

        projects.append(project_data)

    # Sort by creation date (newest first)
    projects.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return projects


def render_project_manager():
    """
    Render the Project Manager panel.

    Features:
    - Browse existing projects
    - Load project for continued synthesis
    - View project outputs (PDF, DOCX, MD)
    - Delete projects
    """
    st.markdown("### 📁 Project Manager")
    st.caption("Manage synthesis projects | Save & Load your work")

    # Tabs for different views
    tab1, tab2 = st.tabs(["📂 My Projects", "➕ New Project"])

    with tab1:
        _render_projects_list()

    with tab2:
        _render_new_project_form()


def _render_projects_list():
    """Render the list of existing projects."""
    projects = _get_all_projects()

    if not projects:
        st.info("No projects found. Create a new synthesis to get started!")
        return

    st.markdown(f"**{len(projects)} Projects Found**")

    for project in projects:
        _render_project_card(project)


def _render_project_card(project: dict):
    """Render a single project card."""
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            # Title with status indicator
            status_icon = "✅" if project["has_output"] else "🔄"
            st.markdown(f"#### {status_icon} {project['topic']}")

            # Metadata
            created = project.get("created_at")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    created_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    created_str = created[:16] if created else "Unknown"
            else:
                created_str = "Unknown"

            template = project.get("template_type") or "General"
            st.caption(f"📅 {created_str} | 📝 {template}")

        with col2:
            # File counts
            st.metric("Sources", project["source_count"])
            st.metric("Images", project["image_count"])

        with col3:
            # Actions
            if st.button("📂 Open", key=f"open_{project['path']}", width="stretch"):
                _load_project(project)

            if project["has_output"]:
                if st.button(
                    "📄 View Output",
                    key=f"view_{project['path']}",
                    width="stretch",
                ):
                    _view_project_output(project)

        st.divider()


def _load_project(project: dict):
    """Load a project into session state for continued work."""
    project_path = project["path"]

    # Load manifest
    manifest_path = project_path / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)

            st.session_state["loaded_project"] = {
                "path": project_path,
                "topic": project["topic"],
                "manifest": manifest,
                "sources": list((project_path / "sources").glob("*.pdf")),
                "images": list((project_path / "images").glob("*.*")),
                "outputs": list((project_path / "output").glob("*.*")),
            }

            # Also set in synthesis context
            st.session_state["syn_topic"] = project["topic"]

            st.success(f"✅ Loaded project: {project['topic']}")
            st.toast("Switch to Synthesis Studio to continue working")

        except Exception as e:
            st.error(f"Failed to load project: {e}")
    else:
        st.error("Project manifest not found")


def _view_project_output(project: dict):
    """Display project outputs."""
    output_dir = project["path"] / "output"

    if not output_dir.exists():
        st.warning("No output directory found")
        return

    outputs = list(output_dir.glob("*.*"))

    if not outputs:
        st.info("No output files generated yet")
        return

    st.markdown("### 📄 Project Outputs")

    for output_file in outputs:
        col1, col2 = st.columns([3, 1])

        with col1:
            ext = output_file.suffix.lower()
            icon = {"pdf": "📕", ".docx": "📘", ".md": "📝", ".tex": "📗"}.get(
                ext, "📄"
            )
            size_kb = output_file.stat().st_size / 1024
            st.markdown(f"{icon} **{output_file.name}** ({size_kb:.1f} KB)")

        with col2:
            # Download button
            with open(output_file, "rb") as f:
                st.download_button(
                    "⬇️ Download",
                    f,
                    file_name=output_file.name,
                    key=f"dl_{output_file.name}",
                    width="stretch",
                )


def _render_new_project_form():
    """Render form to create a new project."""
    st.markdown("### ➕ Create New Project")

    topic = st.text_input(
        "Project Topic",
        placeholder="e.g., 'Pterional Craniotomy', 'Vestibular Schwannoma'",
        key="new_project_topic",
    )

    template_type = st.selectbox(
        "Template Type",
        ["procedural", "theoretical", "anatomy", "imaging", "encyclopedia"],
        key="new_project_template",
    )

    if st.button("🚀 Create Project", key="create_project_btn"):
        if not topic:
            st.error("Please enter a topic")
            return

        try:
            from src.reference_library.integration.neurosynth_bridge import (
                _create_project_directory,
            )

            project = _create_project_directory(topic)
            project.save_project_meta(topic=topic, template_type=template_type)

            st.success(f"✅ Created project: {project.root.name}")
            st.session_state["syn_topic"] = topic
            st.toast("Switch to Synthesis Studio to begin")
            st.rerun()

        except Exception as e:
            st.error(f"Failed to create project: {e}")


def render_loaded_project_info():
    """Render info about the currently loaded project (for sidebar)."""
    if "loaded_project" not in st.session_state:
        return

    project = st.session_state.loaded_project

    st.markdown("---")
    st.markdown("### 📁 Active Project")
    st.markdown(f"**{project['topic']}**")
    st.caption(f"📄 {len(project.get('sources', []))} sources")
    st.caption(f"🖼️ {len(project.get('images', []))} images")

    if st.button("❌ Close Project", key="close_project"):
        del st.session_state["loaded_project"]
        st.rerun()
