"""Rich hierarchical results tree with inline thumbnails and expandable context."""
import customtkinter as ctk
from tkinter import ttk, Canvas
from typing import Callable, Optional
from pathlib import Path
from PIL import Image, ImageTk

from src import config
from ..search.result_model import SearchResult, ChapterResult, MatchType
from .styles import FONTS, PADDING, RICH_PREVIEW, RICH_PREVIEW_COLORS


class RichResultsTree(ctk.CTkFrame):
    """Enhanced tree view with inline thumbnails and expandable context."""

    def __init__(
        self,
        parent,
        on_select: Callable[[SearchResult], None],
        on_selection_change: Optional[Callable[[list[SearchResult | ChapterResult]], None]] = None,
        on_extract_images: Optional[Callable[[SearchResult], None]] = None,
        on_index_text: Optional[Callable[[SearchResult], None]] = None,
        database=None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_select = on_select
        self.on_selection_change = on_selection_change
        self.on_extract_images = on_extract_images
        self.on_index_text = on_index_text
        self.database = database

        # Result tracking (supports both SearchResult and ChapterResult)
        self.results: dict[str, SearchResult] = {}  # page-level results
        self.chapter_results: dict[str, ChapterResult] = {}  # chapter-level results
        self.series_items: dict[str, str] = {}
        self.chapter_items: dict[str, str] = {}
        self.selected_items: set[str] = set()
        self._item_parents: dict[str, str] = {}

        # Rich preview state
        self._rich_mode = True  # Start in rich mode
        self._expanded_items: set[str] = set()  # Track expanded context items
        self._thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}
        self._item_thumbnails: dict[str, list[ImageTk.PhotoImage]] = {}
        self._item_figures: dict[str, list[dict]] = {}  # item_id -> figures list

        # Context menu
        self.context_menu = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the rich tree view UI."""
        # Header with mode toggle
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        self.results_label = ctk.CTkLabel(
            header_frame,
            text="Results (0 matches)",
            font=FONTS["subheading"]
        )
        self.results_label.pack(side="left")

        # Selection count label
        self.selection_label = ctk.CTkLabel(
            header_frame,
            text="",
            font=FONTS["small"],
            text_color="gray"
        )
        self.selection_label.pack(side="left", padx=(10, 0))

        # Mode toggle button
        self.mode_toggle = ctk.CTkSwitch(
            header_frame,
            text="Rich View",
            font=FONTS["small"],
            command=self._toggle_mode,
            width=80
        )
        self.mode_toggle.pack(side="right", padx=PADDING["small"])
        self.mode_toggle.select()  # Start in rich mode

        # Expand/Collapse buttons
        ctk.CTkButton(
            header_frame,
            text="Expand All",
            command=self._expand_all,
            width=80,
            height=24,
            font=FONTS["small"]
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            header_frame,
            text="Collapse",
            command=self._collapse_all,
            width=70,
            height=24,
            font=FONTS["small"]
        ).pack(side="right", padx=2)

        # Selection buttons
        ctk.CTkButton(
            header_frame,
            text="Clear",
            command=self._clear_selection,
            width=60,
            height=24,
            font=FONTS["small"]
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            header_frame,
            text="Select All",
            command=self._select_all,
            width=80,
            height=24,
            font=FONTS["small"]
        ).pack(side="right", padx=2)

        # Create scrollable content area
        self._setup_results_area()
        self._create_context_menu()

    def _setup_results_area(self):
        """Set up the scrollable results area."""
        # Use a frame with canvas for custom scrolling
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=PADDING["small"])
        
        # Create canvas with scrollbar
        self.canvas = Canvas(
            container,
            bg="#2b2b2b",
            highlightthickness=0
        )
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        
        # Scrollable frame inside canvas
        self.results_frame = ctk.CTkFrame(self.canvas, fg_color="#2b2b2b")
        
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.results_frame,
            anchor="nw"
        )
        
        # Configure scrolling
        self.results_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Pack widgets
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Track result item widgets
        self._result_widgets: dict[str, ctk.CTkFrame] = {}
        self._series_widgets: dict[str, ctk.CTkFrame] = {}
        self._chapter_widgets: dict[str, ctk.CTkFrame] = {}

    def _on_frame_configure(self, _event):
        """Update scroll region when frame size changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, _event):
        """Update canvas window width when canvas is resized."""
        self.canvas.itemconfig(self.canvas_window, width=_event.width)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _toggle_mode(self):
        """Toggle between rich and compact view modes."""
        self._rich_mode = self.mode_toggle.get()
        self._refresh_all_items()

    def _refresh_all_items(self):
        """Refresh all result items to apply mode change."""
        # Refresh page-level results (thumbnails toggle)
        for item_id, widget in self._result_widgets.items():
            if item_id in self.results:
                self._update_result_widget(item_id, widget)

        # Note: Chapter results don't have thumbnails but could be extended
        # to show/hide context preview based on mode in the future

    def clear(self):
        """Clear all results."""
        # Clear widgets
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Clear tracking
        self.results.clear()
        self.chapter_results.clear()
        self.series_items.clear()
        self.chapter_items.clear()
        self.selected_items.clear()
        self._item_parents.clear()
        self._result_widgets.clear()
        self._series_widgets.clear()
        self._chapter_widgets.clear()
        self._expanded_items.clear()
        self._item_figures.clear()
        self._item_thumbnails.clear()

        self._update_count(0)
        self._update_selection_label()

    def add_chapter_result(self, chapter: ChapterResult):
        """Add a chapter-level search result to the tree.

        This displays the entire chapter as a single unit with:
        - Match type icon (📖 dedicated, 📑 section, 📝 reference)
        - Page count
        - Preview context
        """
        # Get or create series section
        series_frame = self._get_or_create_series(chapter.book_series)

        # Create unique chapter key
        chapter_key = f"{chapter.book_series}||{chapter.chapter_title}"

        # Create chapter item as a single expandable result
        item_id = f"chapter_{len(self.chapter_results)}"
        self.chapter_results[item_id] = chapter
        self._item_parents[item_id] = chapter.book_series

        # Create the chapter result widget (displayed directly under series)
        chapter_widget = self._create_chapter_result_widget(series_frame, item_id, chapter)
        self._result_widgets[item_id] = chapter_widget

        # Update count
        total = len(self.results) + len(self.chapter_results)
        self._update_count(total)

        # Update series count
        if chapter.book_series in self._series_widgets:
            series_frame = self._series_widgets[chapter.book_series]
            if hasattr(series_frame, '_count_label'):
                # Count chapters in this series
                count = sum(1 for c in self.chapter_results.values()
                           if c.book_series == chapter.book_series)
                series_frame._count_label.configure(text=f"({count} chapters)")

    def _create_chapter_result_widget(
        self, parent: ctk.CTkFrame, item_id: str, chapter: ChapterResult
    ) -> ctk.CTkFrame:
        """Create a widget displaying a chapter-level result."""
        # Get content frame from series
        content_frame = parent._content_frame if hasattr(parent, '_content_frame') else parent

        # Create chapter frame
        frame = ctk.CTkFrame(
            content_frame,
            fg_color=chapter.match_type.color if chapter.is_dedicated else "#2a2a2a",
            corner_radius=4
        )
        frame.pack(fill="x", padx=8, pady=2)

        # Header row
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=4)

        # Selection checkbox
        checkbox = ctk.CTkCheckBox(
            header,
            text="",
            width=20,
            checkbox_width=18,
            checkbox_height=18,
            command=lambda: self._toggle_selection(item_id, checkbox.get())
        )
        checkbox.pack(side="left")
        frame._checkbox = checkbox

        # Match type icon
        icon_label = ctk.CTkLabel(
            header,
            text=chapter.display_icon,
            font=("", 16)
        )
        icon_label.pack(side="left", padx=(4, 8))

        # Chapter title
        title_label = ctk.CTkLabel(
            header,
            text=chapter.display_name,
            font=FONTS["body_bold"],
            cursor="hand2"
        )
        title_label.pack(side="left", fill="x", expand=True, anchor="w")
        title_label.bind("<Button-1>", lambda e: self._on_chapter_click(item_id))

        # Match info badge
        if chapter.match_type == MatchType.DEDICATED_CHAPTER:
            badge_text = f"📖 {chapter.page_count} pages"
            badge_color = "#27ae60"
        elif chapter.match_type == MatchType.RELATED_SECTION:
            badge_text = f"📑 {len(chapter.matched_pages)} pages"
            badge_color = "#3498db"
        else:
            badge_text = f"📝 {chapter.total_occurrences}×"
            badge_color = "#95a5a6"

        badge = ctk.CTkLabel(
            header,
            text=badge_text,
            font=FONTS["small"],
            fg_color=badge_color,
            corner_radius=8,
            padx=6,
            pady=2
        )
        badge.pack(side="right", padx=4)

        # Authority badge (if from primary source)
        if hasattr(chapter, 'authority_score') and chapter.authority_score >= 80:
            source_text = f"⭐ {chapter.index_source}" if hasattr(chapter, 'index_source') and chapter.index_source else "⭐ Primary"
            authority_badge = ctk.CTkLabel(
                header,
                text=source_text,
                font=FONTS["small"],
                fg_color="#f39c12",
                corner_radius=8,
                padx=6,
                pady=2
            )
            authority_badge.pack(side="right", padx=2)

        # Section type badge (if section detected)
        if hasattr(chapter, 'matched_sections') and chapter.matched_sections:
            # Get the first matched section type
            first_section = chapter.matched_sections[0]
            section_type = first_section.section_type if hasattr(first_section, 'section_type') else str(first_section)
            section_badge = ctk.CTkLabel(
                header,
                text=f"📑 {section_type}",
                font=FONTS["small"],
                fg_color="#9b59b6",
                corner_radius=8,
                padx=6,
                pady=2
            )
            section_badge.pack(side="right", padx=2)

        # Expand button (for context preview)
        expand_btn = ctk.CTkButton(
            header,
            text="▶",
            width=24,
            height=24,
            font=FONTS["small"],
            command=lambda: self._toggle_chapter_expand(item_id, frame)
        )
        expand_btn.pack(side="right", padx=2)
        frame._expand_btn = expand_btn

        # Expandable context area (initially hidden)
        context_frame = ctk.CTkFrame(frame, fg_color="#1a1a1a", corner_radius=4)
        frame._context_frame = context_frame
        frame._is_expanded = False
        frame._chapter = chapter  # Store chapter for lazy loading

        return frame

    def _on_chapter_click(self, item_id: str):
        """Handle click on a chapter result."""
        if item_id in self.chapter_results:
            chapter = self.chapter_results[item_id]
            # Create a SearchResult for the first page to show in preview
            first_page = chapter.matched_pages[0] if chapter.matched_pages else 1
            result = SearchResult(
                pdf_path=chapter.pdf_path,
                book_series=chapter.book_series,
                book_title=chapter.book_title,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.chapter_title,
                page_number=first_page,
                match_text=chapter.match_summary,
                context=chapter.preview_context,
            )
            self.on_select(result)

    def add_result(self, result: SearchResult):
        """Add a search result to the rich tree."""
        # Get or create series section
        series_frame = self._get_or_create_series(result.book_series)

        # Get or create chapter section
        chapter_key = f"{result.book_series}||{result.chapter_title}"
        chapter_frame = self._get_or_create_chapter(series_frame, chapter_key, result)

        # Create result item
        item_id = f"result_{len(self.results)}"
        self.results[item_id] = result
        self._item_parents[item_id] = chapter_key

        # Load figures for this page
        figures = self._load_figures_for_result(result)
        self._item_figures[item_id] = figures

        # Create the result widget
        result_widget = self._create_result_widget(chapter_frame, item_id, result, figures)
        self._result_widgets[item_id] = result_widget

        self._update_count(len(self.results) + len(self.chapter_results))

    def _get_or_create_series(self, series_name: str) -> ctk.CTkFrame:
        """Get or create a series section."""
        if series_name in self._series_widgets:
            return self._series_widgets[series_name]

        display_name = config.KNOWN_SERIES.get(series_name, series_name)

        # Create series frame
        series_frame = ctk.CTkFrame(self.results_frame, fg_color="#1e1e1e", corner_radius=6)
        series_frame.pack(fill="x", pady=2, padx=2)

        # Series header
        header = ctk.CTkFrame(series_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=4)

        # Collapse button
        collapse_btn = ctk.CTkLabel(
            header,
            text="▼",
            font=FONTS["body"],
            cursor="hand2"
        )
        collapse_btn.pack(side="left")
        collapse_btn.bind("<Button-1>", lambda e, sf=series_frame: self._toggle_series(sf))

        # Series title
        ctk.CTkLabel(
            header,
            text=f"📚 {display_name}",
            font=FONTS["body_bold"]
        ).pack(side="left", padx=8)

        # Series count (updated later)
        count_label = ctk.CTkLabel(
            header,
            text="(0)",
            font=FONTS["small"],
            text_color="gray"
        )
        count_label.pack(side="left")
        series_frame._count_label = count_label
        series_frame._is_collapsed = False

        # Content frame (for chapters)
        content = ctk.CTkFrame(series_frame, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=2)
        series_frame._content_frame = content

        self._series_widgets[series_name] = series_frame
        self.series_items[series_name] = series_name

        return series_frame

    def _toggle_series(self, series_frame):
        """Toggle series collapse state."""
        if series_frame._is_collapsed:
            series_frame._content_frame.pack(fill="x", padx=16, pady=2)
            series_frame._is_collapsed = False
        else:
            series_frame._content_frame.pack_forget()
            series_frame._is_collapsed = True

    def _get_or_create_chapter(self, series_frame: ctk.CTkFrame, chapter_key: str, result: SearchResult) -> ctk.CTkFrame:
        """Get or create a chapter section within a series."""
        if chapter_key in self._chapter_widgets:
            return self._chapter_widgets[chapter_key]

        content = series_frame._content_frame

        # Chapter frame
        chapter_frame = ctk.CTkFrame(content, fg_color="#252525", corner_radius=4)
        chapter_frame.pack(fill="x", pady=2)

        # Chapter header
        header = ctk.CTkFrame(chapter_frame, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=3)

        ctk.CTkLabel(
            header,
            text=f"📄 {result.display_name}",
            font=FONTS["body"],
            anchor="w"
        ).pack(side="left", fill="x", expand=True)

        # Results content area
        results_content = ctk.CTkFrame(chapter_frame, fg_color="transparent")
        results_content.pack(fill="x", padx=8, pady=2)
        chapter_frame._results_content = results_content

        self._chapter_widgets[chapter_key] = chapter_frame
        self.chapter_items[chapter_key] = chapter_key

        return chapter_frame

    def _load_figures_for_result(self, result: SearchResult) -> list[dict]:
        """Load figures for a result's page from database."""
        if not self.database:
            return []
        try:
            figures = self.database.get_page_figures(result.pdf_path, result.page_number)
            return figures
        except Exception:
            return []

    def _create_result_widget(
        self,
        parent: ctk.CTkFrame,
        item_id: str,
        result: SearchResult,
        figures: list[dict]
    ) -> ctk.CTkFrame:
        """Create a result widget with thumbnails and expandable context."""
        results_content = parent._results_content

        # Main result frame
        result_frame = ctk.CTkFrame(results_content, fg_color="#2a2a2a", corner_radius=4)
        result_frame.pack(fill="x", pady=1)

        # Header row (always visible)
        header_row = ctk.CTkFrame(result_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=6, pady=4)

        # Checkbox
        check_var = ctk.BooleanVar(value=item_id in self.selected_items)
        checkbox = ctk.CTkCheckBox(
            header_row,
            text="",
            variable=check_var,
            width=20,
            command=lambda: self._toggle_selection(item_id, check_var.get())
        )
        checkbox.pack(side="left")
        result_frame._checkbox = checkbox
        result_frame._check_var = check_var

        # Location icon (shows where match was found)
        location_icon = result.location_icon if hasattr(result, 'location_icon') else "📄"
        ctk.CTkLabel(
            header_row,
            text=location_icon,
            font=FONTS["body"],
            width=24
        ).pack(side="left")

        # Page number
        ctk.CTkLabel(
            header_row,
            text=f"p.{result.page_number}",
            font=FONTS["body_bold"],
            width=45
        ).pack(side="left", padx=4)

        # Match count badge (if multiple matches on page)
        match_count = getattr(result, 'match_count', 1)
        if match_count > 1:
            ctk.CTkLabel(
                header_row,
                text=f"×{match_count}",
                font=FONTS["small"],
                fg_color="#6c5ce7",
                corner_radius=3,
                padx=4
            ).pack(side="left", padx=2)

        # Match text preview
        preview_text = result.match_text[:RICH_PREVIEW["context_preview_chars"]]
        text_label = ctk.CTkLabel(
            header_row,
            text=preview_text + "...",
            font=FONTS["body"],
            anchor="w"
        )
        text_label.pack(side="left", fill="x", expand=True)

        # Figure count badge
        fig_count = len(figures)
        if fig_count > 0:
            fig_badge = ctk.CTkLabel(
                header_row,
                text=f"🖼 {fig_count}",
                font=FONTS["small"],
                fg_color="#3498db",
                corner_radius=3,
                padx=6
            )
            fig_badge.pack(side="right", padx=4)

        # Expand button
        expand_btn = ctk.CTkButton(
            header_row,
            text="▶",
            width=24,
            height=24,
            font=FONTS["small"],
            command=lambda: self._toggle_expand(item_id, result_frame)
        )
        expand_btn.pack(side="right", padx=2)
        result_frame._expand_btn = expand_btn

        # Bind click to select
        header_row.bind("<Button-1>", lambda e: self._select_item(item_id))
        text_label.bind("<Button-1>", lambda e: self._select_item(item_id))

        # Rich content area (thumbnails + expanded context)
        if self._rich_mode and figures:
            self._add_thumbnail_row(result_frame, item_id, figures)

        # Expandable context area (initially hidden)
        context_frame = ctk.CTkFrame(result_frame, fg_color=RICH_PREVIEW_COLORS["context_bg"])
        result_frame._context_frame = context_frame
        result_frame._is_expanded = False

        return result_frame

    def _add_thumbnail_row(self, result_frame: ctk.CTkFrame, item_id: str, figures: list[dict]):
        """Add a row of inline thumbnails to a result."""
        thumb_row = ctk.CTkFrame(result_frame, fg_color="transparent")
        thumb_row.pack(fill="x", padx=50, pady=(0, 4))

        thumb_size = RICH_PREVIEW["thumb_size_small"]
        max_thumbs = RICH_PREVIEW["max_inline_thumbs"]

        thumbnails = []
        for fig in figures[:max_thumbs]:
            image_path = fig.get("image_path")
            if not image_path or not Path(image_path).exists():
                continue

            try:
                # Load and resize thumbnail
                img = Image.open(image_path)
                img.thumbnail(thumb_size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                thumbnails.append(photo)

                # Get border color by type
                img_type = fig.get("image_type", "unknown")
                border_color = config.IMAGE_TYPE_COLORS.get(img_type, "#444444")

                # Create thumbnail container
                thumb_container = ctk.CTkFrame(thumb_row, fg_color=border_color, corner_radius=3)
                thumb_container.pack(side="left", padx=2)

                # Thumbnail label
                thumb_label = ctk.CTkLabel(
                    thumb_container,
                    image=photo,
                    text="",
                    width=thumb_size[0] + 2,
                    height=thumb_size[1] + 2
                )
                thumb_label.pack(padx=1, pady=1)

                # Bind click to open full image
                thumb_label.bind("<Button-1>", lambda e, f=fig: self._open_figure(f))

            except Exception:
                continue

        # Store references to prevent garbage collection
        self._item_thumbnails[item_id] = thumbnails

        # Overflow indicator
        if len(figures) > max_thumbs:
            overflow = len(figures) - max_thumbs
            ctk.CTkLabel(
                thumb_row,
                text=f"+{overflow}",
                font=FONTS["small"],
                text_color="gray"
            ).pack(side="left", padx=4)

    def _toggle_expand(self, item_id: str, result_frame: ctk.CTkFrame):
        """Toggle expanded context view for a result."""
        if result_frame._is_expanded:
            # Collapse
            result_frame._context_frame.pack_forget()
            result_frame._expand_btn.configure(text="▶")
            result_frame._is_expanded = False
            self._expanded_items.discard(item_id)
        else:
            # Expand
            result = self.results.get(item_id)
            if result:
                self._populate_expanded_context(result_frame._context_frame, result)
            result_frame._context_frame.pack(fill="x", padx=6, pady=(0, 6))
            result_frame._expand_btn.configure(text="▼")
            result_frame._is_expanded = True
            self._expanded_items.add(item_id)

    def _toggle_chapter_expand(self, item_id: str, chapter_frame: ctk.CTkFrame):
        """Toggle expanded context view for a chapter result."""
        if chapter_frame._is_expanded:
            # Collapse
            chapter_frame._context_frame.pack_forget()
            chapter_frame._expand_btn.configure(text="▶")
            chapter_frame._is_expanded = False
            self._expanded_items.discard(item_id)
        else:
            # Expand
            chapter = chapter_frame._chapter if hasattr(chapter_frame, '_chapter') else self.chapter_results.get(item_id)
            if chapter:
                self._populate_chapter_context(chapter_frame._context_frame, chapter)
            chapter_frame._context_frame.pack(fill="x", padx=6, pady=(0, 4))
            chapter_frame._expand_btn.configure(text="▼")
            chapter_frame._is_expanded = True
            self._expanded_items.add(item_id)

    def _populate_chapter_context(self, context_frame: ctk.CTkFrame, chapter: ChapterResult):
        """Populate the expanded context area for a chapter result."""
        # Clear previous content
        for widget in context_frame.winfo_children():
            widget.destroy()

        # Context text
        context_text = ctk.CTkTextbox(
            context_frame,
            font=FONTS["context_preview"],
            wrap="word",
            height=80,
            fg_color="#1a1a1a"
        )
        context_text.pack(fill="x", padx=4, pady=4)

        # Build context with matched pages info
        text_parts = []
        if chapter.preview_context:
            text_parts.append(chapter.preview_context)
        if chapter.matched_pages:
            pages_str = ", ".join(str(p) for p in chapter.matched_pages[:10])
            if len(chapter.matched_pages) > 10:
                pages_str += f"... (+{len(chapter.matched_pages) - 10} more)"
            text_parts.append(f"\n📄 Matched pages: {pages_str}")

        text = "\n".join(text_parts) if text_parts else "No preview available"
        context_text.insert("1.0", text)
        context_text.configure(state="disabled")

    def _populate_expanded_context(self, context_frame: ctk.CTkFrame, result: SearchResult):
        """Populate the expanded context area with full text."""
        # Clear previous content
        for widget in context_frame.winfo_children():
            widget.destroy()

        # Full context text
        context_text = ctk.CTkTextbox(
            context_frame,
            font=FONTS["context_preview"],
            wrap="word",
            height=100,
            fg_color="#1a1a1a"
        )
        context_text.pack(fill="x", padx=4, pady=4)

        # Insert text with max chars limit
        max_chars = RICH_PREVIEW["context_expanded_chars"]
        text = result.context[:max_chars]
        if len(result.context) > max_chars:
            text += "..."

        context_text.insert("1.0", text)
        context_text.configure(state="disabled")

    def _open_figure(self, fig: dict):
        """Open a figure in the system image viewer."""
        import subprocess
        import sys

        image_path = fig.get("image_path")
        if not image_path or not Path(image_path).exists():
            return

        if sys.platform == "darwin":
            subprocess.run(["open", image_path])
        elif sys.platform == "win32":
            import os
            os.startfile(image_path)
        else:
            subprocess.run(["xdg-open", image_path])

    def _toggle_selection(self, item_id: str, selected: bool):
        """Toggle selection state of an item."""
        if selected:
            self.selected_items.add(item_id)
        else:
            self.selected_items.discard(item_id)

        self._update_selection_label()
        self._notify_selection_change()

    def _select_item(self, item_id: str):
        """Select an item and call the on_select callback."""
        if item_id in self.results:
            self.on_select(self.results[item_id])

    def _select_all(self):
        """Select all result items (both page-level and chapter-level)."""
        # Select page-level results
        for item_id in self.results:
            self.selected_items.add(item_id)
            if item_id in self._result_widgets:
                widget = self._result_widgets[item_id]
                if hasattr(widget, '_check_var'):
                    widget._check_var.set(True)

        # Select chapter-level results
        for item_id in self.chapter_results:
            self.selected_items.add(item_id)
            if item_id in self._result_widgets:
                widget = self._result_widgets[item_id]
                if hasattr(widget, '_checkbox'):
                    widget._checkbox.select()

        self._update_selection_label()
        self._notify_selection_change()

    def _clear_selection(self):
        """Clear all selections (both page-level and chapter-level)."""
        for item_id in list(self.selected_items):
            if item_id in self._result_widgets:
                widget = self._result_widgets[item_id]
                # Handle both page-level (_check_var) and chapter-level (_checkbox)
                if hasattr(widget, '_check_var'):
                    widget._check_var.set(False)
                if hasattr(widget, '_checkbox'):
                    widget._checkbox.deselect()

        self.selected_items.clear()
        self._update_selection_label()
        self._notify_selection_change()

    def _update_selection_label(self):
        """Update the selection count display."""
        count = len(self.selected_items)
        if count > 0:
            self.selection_label.configure(text=f"({count} selected)")
        else:
            self.selection_label.configure(text="")

    def _notify_selection_change(self):
        """Notify callback of selection change."""
        if self.on_selection_change:
            self.on_selection_change(self.get_selected_results())

    def _update_count(self, count: int):
        """Update the results count label."""
        self.results_label.configure(text=f"Results ({count} matches)")

    def _expand_all(self):
        """Expand all result contexts (page-level and chapter-level)."""
        for item_id, widget in self._result_widgets.items():
            if hasattr(widget, '_is_expanded') and not widget._is_expanded:
                # Use appropriate toggle based on result type
                if item_id in self.chapter_results:
                    self._toggle_chapter_expand(item_id, widget)
                else:
                    self._toggle_expand(item_id, widget)

    def _collapse_all(self):
        """Collapse all result contexts (page-level and chapter-level)."""
        for item_id, widget in self._result_widgets.items():
            if hasattr(widget, '_is_expanded') and widget._is_expanded:
                # Use appropriate toggle based on result type
                if item_id in self.chapter_results:
                    self._toggle_chapter_expand(item_id, widget)
                else:
                    self._toggle_expand(item_id, widget)

    def _update_result_widget(self, item_id: str, widget: ctk.CTkFrame):
        """Update a result widget when mode changes."""
        figures = self._item_figures.get(item_id, [])

        # Find and remove existing thumbnail row
        for child in widget.winfo_children():
            if hasattr(child, '_is_thumb_row'):
                child.destroy()
                break

        # Add thumbnails if in rich mode
        if self._rich_mode and figures:
            self._add_thumbnail_row(widget, item_id, figures)

    def get_all_results(self) -> list[SearchResult]:
        """Get all results."""
        return list(self.results.values())

    def get_selected_results(self) -> list[SearchResult | ChapterResult]:
        """Get list of selected results (both page-level and chapter-level)."""
        results = []
        for item_id in self.selected_items:
            if item_id in self.results:
                results.append(self.results[item_id])
            elif item_id in self.chapter_results:
                results.append(self.chapter_results[item_id])
        return results

    # ==================== Smart Selection Methods ====================

    def smart_select_balanced(self, target_per_group: int = 6) -> list[str]:
        """Auto-select first N results from each book series (includes chapters)."""
        self._clear_selection()
        selected_ids = []

        # Group by book series - include both page-level and chapter-level results
        by_series: dict[str, list[str]] = {}

        # Add page-level results
        for item_id, result in self.results.items():
            series = result.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Add chapter-level results
        for item_id, chapter in self.chapter_results.items():
            series = chapter.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Select top N from each series
        for items in by_series.values():
            for item_id in items[:target_per_group]:
                self._select_single_item(item_id)
                selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def smart_select_high_confidence(self, threshold: float = 0.8) -> list[str]:  # noqa: ARG002
        """Select first 20 results including chapters (threshold kept for API compatibility)."""
        self._clear_selection()
        selected_ids = []

        # Combine page-level and chapter-level result IDs
        all_item_ids = list(self.results.keys()) + list(self.chapter_results.keys())

        for i, item_id in enumerate(all_item_ids):
            if i >= 20:
                break
            self._select_single_item(item_id)
            selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def smart_select_diverse(self, max_per_source: int = 3) -> list[str]:
        """Select results from multiple book series for diversity (includes chapters)."""
        self._clear_selection()
        selected_ids = []

        # Group by book series - include both page-level and chapter-level results
        by_series: dict[str, list[str]] = {}

        # Add page-level results
        for item_id, result in self.results.items():
            series = result.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Add chapter-level results
        for item_id, chapter in self.chapter_results.items():
            series = chapter.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Take top N from each series
        for items in by_series.values():
            for item_id in items[:max_per_source]:
                self._select_single_item(item_id)
                selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def _select_single_item(self, item_id: str):
        """Select a single item (helper for smart selection, handles both types)."""
        if item_id not in self.selected_items:
            self.selected_items.add(item_id)
            if item_id in self._result_widgets:
                widget = self._result_widgets[item_id]
                # Handle page-level results (use _check_var)
                if hasattr(widget, '_check_var'):
                    widget._check_var.set(True)
                # Handle chapter-level results (use _checkbox)
                elif hasattr(widget, '_checkbox'):
                    widget._checkbox.select()

    # ==================== Context Menu ====================

    def _create_context_menu(self):
        """Create the right-click context menu."""
        import tkinter as tk
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Extract Images from PDF", command=self._handle_extract_images)
        self.context_menu.add_command(label="Index Text (Background)", command=self._handle_index_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open PDF", command=self._handle_open_pdf)

    def _handle_extract_images(self):
        """Handle extract images menu action."""
        if self.on_extract_images:
            # Get first selected result
            for item_id in self.selected_items:
                if item_id in self.results:
                    self.on_extract_images(self.results[item_id])
                    break

    def _handle_index_text(self):
        """Handle index text menu action."""
        if self.on_index_text:
            for item_id in self.selected_items:
                if item_id in self.results:
                    self.on_index_text(self.results[item_id])
                    break

    def _handle_open_pdf(self):
        """Handle open PDF menu action."""
        import subprocess
        import sys

        for item_id in self.selected_items:
            if item_id in self.results:
                result = self.results[item_id]
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Preview", str(result.pdf_path)])
                break

    def update(self):
        """Refresh the display (compatibility method)."""
        pass  # All updates are immediate in this implementation

