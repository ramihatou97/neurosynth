"""Panel for displaying newly detected PDFs in the library."""
import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from reference_library import config
from .styles import FONTS, PADDING


class NewFilesPanel(ctk.CTkFrame):
    """Panel showing newly detected PDF files that haven't been indexed."""

    def __init__(
        self,
        parent,
        on_index_file: Callable[[Path], None],
        on_index_all: Callable[[], None],
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_index_file = on_index_file
        self.on_index_all = on_index_all
        self.file_frames: dict[str, ctk.CTkFrame] = {}

        self._setup_ui()

    def _setup_ui(self):
        """Set up the panel UI."""
        # Header with badge
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        self.header_label = ctk.CTkLabel(
            header_frame,
            text="New Files",
            font=FONTS["subheading"]
        )
        self.header_label.pack(side="left")

        # Badge showing count
        self.count_badge = ctk.CTkLabel(
            header_frame,
            text="0",
            font=FONTS["small"],
            fg_color="#e74c3c",
            corner_radius=10,
            width=24,
            height=24
        )
        self.count_badge.pack(side="left", padx=PADDING["small"])

        # Index All button
        self.index_all_btn = ctk.CTkButton(
            header_frame,
            text="Index All",
            command=self._on_index_all,
            width=80,
            height=24,
            font=FONTS["small"],
            fg_color="#27ae60",
            hover_color="#1e8449"
        )
        self.index_all_btn.pack(side="right")

        # Scrollable frame for file list
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=300
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=PADDING["small"])

        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.scroll_frame,
            text="No new files detected.\nAdd PDFs to your library folder\nand they'll appear here.",
            font=FONTS["small"],
            text_color="gray",
            justify="center"
        )
        self.empty_label.pack(pady=PADDING["large"])

    def add_file(self, pdf_path: Path, book_series: str = "", chapter_title: str = "",
                 page_count: int = 0, first_seen: Optional[datetime] = None):
        """Add a new file to the panel."""
        path_str = str(pdf_path)

        # Hide empty state
        self.empty_label.pack_forget()

        # Don't add duplicates
        if path_str in self.file_frames:
            return

        # Create file entry frame
        file_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("gray90", "gray20"))
        file_frame.pack(fill="x", pady=2)

        # File info
        info_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=PADDING["small"], pady=PADDING["small"])

        # Filename
        name = chapter_title or pdf_path.stem
        if len(name) > 40:
            name = name[:37] + "..."
        ctk.CTkLabel(
            info_frame,
            text=name,
            font=FONTS["body"],
            anchor="w"
        ).pack(fill="x")

        # Series and metadata
        meta_parts = []
        if book_series:
            series_display = config.KNOWN_SERIES.get(book_series, book_series)
            if len(series_display) > 30:
                series_display = series_display[:27] + "..."
            meta_parts.append(series_display)
        if page_count > 0:
            meta_parts.append(f"{page_count} pages")
        if first_seen:
            meta_parts.append(first_seen.strftime("%Y-%m-%d"))

        if meta_parts:
            ctk.CTkLabel(
                info_frame,
                text=" | ".join(meta_parts),
                font=FONTS["small"],
                text_color="gray",
                anchor="w"
            ).pack(fill="x")

        # Index button
        def index_this_file():
            self.on_index_file(pdf_path)
            self.remove_file(pdf_path)

        ctk.CTkButton(
            file_frame,
            text="Index",
            command=index_this_file,
            width=60,
            height=28,
            font=FONTS["small"]
        ).pack(side="right", padx=PADDING["small"], pady=PADDING["small"])

        self.file_frames[path_str] = file_frame
        self._update_count()

    def remove_file(self, pdf_path: Path):
        """Remove a file from the panel (after indexing)."""
        path_str = str(pdf_path)
        if path_str in self.file_frames:
            self.file_frames[path_str].destroy()
            del self.file_frames[path_str]
            self._update_count()

            # Show empty state if no files left
            if not self.file_frames:
                self.empty_label.pack(pady=PADDING["large"])

    def clear(self):
        """Clear all files from the panel."""
        for frame in self.file_frames.values():
            frame.destroy()
        self.file_frames.clear()
        self._update_count()
        self.empty_label.pack(pady=PADDING["large"])

    def _update_count(self):
        """Update the badge count."""
        count = len(self.file_frames)
        self.count_badge.configure(text=str(count))

        if count == 0:
            self.count_badge.configure(fg_color="gray")
            self.index_all_btn.configure(state="disabled")
        else:
            self.count_badge.configure(fg_color="#e74c3c")
            self.index_all_btn.configure(state="normal")

    def _on_index_all(self):
        """Handle Index All button click."""
        self.on_index_all()
        self.clear()

    def get_file_count(self) -> int:
        """Get number of files in panel."""
        return len(self.file_frames)

    def load_from_database(self, unindexed_files: list[dict]):
        """Load unindexed files from database."""
        self.clear()
        for file_info in unindexed_files:
            pdf_path = Path(file_info['pdf_path'])
            if pdf_path.exists():
                first_seen = None
                if file_info.get('first_seen'):
                    try:
                        first_seen = datetime.fromisoformat(file_info['first_seen'])
                    except (ValueError, TypeError):
                        pass

                self.add_file(
                    pdf_path=pdf_path,
                    book_series=file_info.get('book_series', ''),
                    chapter_title=file_info.get('chapter_title', ''),
                    page_count=file_info.get('page_count', 0),
                    first_seen=first_seen
                )
