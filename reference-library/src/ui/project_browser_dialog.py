"""Dialog for browsing and loading previous NeuroSynth projects."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from .styles import FONTS, PADDING


class ProjectBrowserDialog(ctk.CTkToplevel):
    """Dialog for browsing saved NeuroSynth projects."""

    PROJECTS_DIR = Path.home() / "Documents" / "NeuroSynth" / "projects"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Load Previous Project")
        self.selected_project: Optional[Path] = None

        # Set size and position
        width = 700
        height = 500
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._setup_ui()
        self._load_projects()

        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.wait_window()

    def _setup_ui(self):
        """Set up the dialog UI."""
        # Title
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])

        ctk.CTkLabel(
            header_frame,
            text="📂 Previous Projects",
            font=FONTS["heading"]
        ).pack(side="left")

        ctk.CTkButton(
            header_frame,
            text="Open Folder",
            command=self._open_projects_folder,
            width=100,
            font=FONTS["small"]
        ).pack(side="right")

        # Projects list (scrollable)
        self.projects_frame = ctk.CTkScrollableFrame(self)
        self.projects_frame.pack(fill="both", expand=True, padx=PADDING["medium"])

        # Details panel
        self.details_frame = ctk.CTkFrame(self)
        self.details_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        self.details_label = ctk.CTkLabel(
            self.details_frame,
            text="Select a project to view details",
            font=FONTS["small"],
            text_color="gray"
        )
        self.details_label.pack(pady=PADDING["small"])

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            width=100
        ).pack(side="right", padx=(PADDING["small"], 0))

        self.open_btn = ctk.CTkButton(
            btn_frame,
            text="Open Output",
            command=self._open_selected,
            width=120,
            state="disabled",
            fg_color="#27ae60",
            hover_color="#219a52"
        )
        self.open_btn.pack(side="right")

    def _load_projects(self):
        """Load and display available projects."""
        # Clear existing
        for widget in self.projects_frame.winfo_children():
            widget.destroy()

        if not self.PROJECTS_DIR.exists():
            ctk.CTkLabel(
                self.projects_frame,
                text="No projects found.\nSynthesize a chapter to create your first project.",
                font=FONTS["body"],
                text_color="gray"
            ).pack(pady=PADDING["large"])
            return

        projects = sorted(self.PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        projects = [p for p in projects if p.is_dir()]

        if not projects:
            ctk.CTkLabel(
                self.projects_frame,
                text="No projects found.\nSynthesize a chapter to create your first project.",
                font=FONTS["body"],
                text_color="gray"
            ).pack(pady=PADDING["large"])
            return

        for project_dir in projects:
            self._add_project_row(project_dir)

    def _add_project_row(self, project_dir: Path):
        """Add a project row to the list."""
        meta = self._load_project_meta(project_dir)
        
        row = ctk.CTkFrame(self.projects_frame, fg_color=("gray90", "gray20"))
        row.pack(fill="x", pady=2)
        row.bind("<Button-1>", lambda e, p=project_dir, m=meta: self._select_project(p, m))

        # Project name
        name = meta.get("topic", project_dir.name) if meta else project_dir.name
        ctk.CTkLabel(row, text=name, font=FONTS["body_bold"], anchor="w").pack(
            side="left", padx=PADDING["small"], pady=PADDING["small"]
        )

        # Date
        if meta and "created_at" in meta:
            try:
                dt = datetime.fromisoformat(meta["created_at"])
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date_str = "Unknown"
        else:
            date_str = datetime.fromtimestamp(project_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

        ctk.CTkLabel(row, text=date_str, font=FONTS["small"], text_color="gray").pack(
            side="right", padx=PADDING["small"]
        )

        # Make entire row clickable
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, p=project_dir, m=meta: self._select_project(p, m))

    def _load_project_meta(self, project_dir: Path) -> Optional[dict]:
        """Load project.json metadata."""
        meta_path = project_dir / "project.json"
        if not meta_path.exists():
            # Try manifest.json as fallback
            meta_path = project_dir / "manifest.json"

        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text())
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def _select_project(self, project_dir: Path, meta: Optional[dict]):
        """Handle project selection."""
        self.selected_project = project_dir
        self.open_btn.configure(state="normal")

        # Update details
        details_text = []
        if meta:
            if "topic" in meta:
                details_text.append(f"Topic: {meta['topic']}")
            if "search_query" in meta:
                details_text.append(f"Search: {meta['search_query']}")
            if "template_type" in meta:
                ttype = "Surgical" if meta["template_type"] == "procedural" else "Clinical"
                details_text.append(f"Type: {ttype}")

        # Count files
        sources_count = len(list((project_dir / "sources").glob("*.pdf"))) if (project_dir / "sources").exists() else 0
        images_count = len(list((project_dir / "images").glob("*"))) if (project_dir / "images").exists() else 0
        output_files = list((project_dir / "output").glob("*.pdf")) if (project_dir / "output").exists() else []

        details_text.append(f"Sources: {sources_count} PDFs | Images: {images_count}")
        if output_files:
            details_text.append(f"Output: {output_files[0].name}")

        self.details_label.configure(text=" | ".join(details_text) if details_text else "No details available")

    def _open_selected(self):
        """Open the selected project's output."""
        if not self.selected_project:
            return

        output_dir = self.selected_project / "output"
        if output_dir.exists():
            pdfs = list(output_dir.glob("*.pdf"))
            if pdfs:
                self._open_file(pdfs[0])
                self.destroy()
                return

        # Fallback: open project folder
        self._open_file(self.selected_project)
        self.destroy()

    def _open_projects_folder(self):
        """Open the projects folder in file manager."""
        if self.PROJECTS_DIR.exists():
            self._open_file(self.PROJECTS_DIR)
        else:
            self.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            self._open_file(self.PROJECTS_DIR)

    def _open_file(self, path: Path):
        """Open a file or folder with system default application."""
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def get_selected_project(self) -> Optional[Path]:
        """Get the selected project path."""
        return self.selected_project

