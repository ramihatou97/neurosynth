"""Hierarchical results tree display."""

from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from reference_library import config

from ..search.result_model import SearchResult
from .styles import FONTS, PADDING


class ResultsTree(ctk.CTkFrame):
    """Hierarchical tree view for search results."""

    def __init__(
        self,
        parent,
        on_select: Callable[[SearchResult], None],
        on_selection_change: Optional[Callable[[list[SearchResult]], None]] = None,
        on_extract_images: Optional[Callable[[SearchResult], None]] = None,
        on_index_text: Optional[Callable[[SearchResult], None]] = None,
        database=None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.on_select = on_select
        self.on_selection_change = on_selection_change
        self.on_extract_images = on_extract_images
        self.on_index_text = on_index_text
        self.database = database
        self.results: dict[str, SearchResult] = {}  # item_id -> SearchResult
        self.series_items: dict[str, str] = {}  # series_name -> tree_item_id
        self.chapter_items: dict[str, str] = {}  # chapter_key -> tree_item_id
        self.selected_items: set[str] = set()  # Track checked items
        self._item_parents: dict[str, str] = {}  # item_id -> parent_id

        # Context menu
        self.context_menu = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the tree view UI."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        self.results_label = ctk.CTkLabel(
            header_frame, text="Results (0 matches)", font=FONTS["subheading"]
        )
        self.results_label.pack(side="left")

        # Selection count label
        self.selection_label = ctk.CTkLabel(
            header_frame, text="", font=FONTS["small"], text_color="gray"
        )
        self.selection_label.pack(side="left", padx=(10, 0))

        # Expand/Collapse buttons
        ctk.CTkButton(
            header_frame,
            text="Expand All",
            command=self._expand_all,
            width=80,
            height=24,
            font=FONTS["small"],
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            header_frame,
            text="Collapse",
            command=self._collapse_all,
            width=70,
            height=24,
            font=FONTS["small"],
        ).pack(side="right", padx=2)

        # Selection buttons
        ctk.CTkButton(
            header_frame,
            text="Clear",
            command=self._clear_selection,
            width=60,
            height=24,
            font=FONTS["small"],
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            header_frame,
            text="Select All",
            command=self._select_all,
            width=80,
            height=24,
            font=FONTS["small"],
        ).pack(side="right", padx=2)

        # Tree view with scrollbar
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=PADDING["small"])

        # Style the treeview for dark mode
        style = ttk.Style()
        style.configure(
            "Results.Treeview",
            font=FONTS["body"],
            rowheight=25,
            foreground="#FFFFFF",
            background="#2b2b2b",
            fieldbackground="#2b2b2b",
        )
        style.configure(
            "Results.Treeview.Heading",
            font=FONTS["body"],
            foreground="#FFFFFF",
            background="#1e1e1e",
        )

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")

        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("select", "page", "figs"),
            show="tree headings",
            yscrollcommand=scrollbar.set,
            style="Results.Treeview",
        )
        self.tree.pack(fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)

        # Configure columns
        self.tree.heading("#0", text="Source", anchor="w")
        self.tree.heading("select", text="✓")
        self.tree.heading("page", text="Page")
        self.tree.heading("figs", text="Figs")

        self.tree.column("#0", width=400, minwidth=200)
        self.tree.column("select", width=30, minwidth=30, anchor="center")
        self.tree.column("page", width=50, minwidth=40, anchor="center")
        self.tree.column("figs", width=40, minwidth=35, anchor="center")

        # Bind selection and checkbox toggle
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)

        # Bind right-click for context menu (macOS uses Button-2 or Button-3 depending on config)
        self.tree.bind("<Button-2>", self._show_context_menu)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Create context menu
        self._create_context_menu()

    def clear(self):
        """Clear all results from tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results.clear()
        self.series_items.clear()
        self.chapter_items.clear()
        self.selected_items.clear()
        self._item_parents.clear()
        self._update_count(0)
        self._update_selection_label()

    def add_result(self, result: SearchResult):
        """Add a search result to the tree."""
        # Get or create series node
        series_id = self._get_or_create_series(result.book_series)

        # Get or create chapter node
        chapter_key = f"{result.book_series}||{result.chapter_title}"
        chapter_id = self._get_or_create_chapter(series_id, chapter_key, result)

        # Get figure count for this page
        fig_count = self._get_figure_count(result)

        # Add match node with checkbox
        match_id = self.tree.insert(
            chapter_id,
            "end",
            text=f"p.{result.page_number}: {result.match_text[:50]}...",
            values=("☐", result.page_number, fig_count),  # Unchecked checkbox
        )

        self.results[match_id] = result
        self._item_parents[match_id] = chapter_id  # Track parent for filter reattach
        self._update_count(len(self.results))

    def _get_figure_count(self, result: SearchResult) -> str:
        """Get figure count for a result's page."""
        if not self.database:
            return "-"
        try:
            count = self.database.get_page_figure_count(
                result.pdf_path, result.page_number
            )
            return str(count) if count > 0 else "-"
        except Exception:
            return "-"

    def _get_or_create_series(self, series_name: str) -> str:
        """Get or create a series node in the tree."""
        if series_name not in self.series_items:
            display_name = config.KNOWN_SERIES.get(series_name, series_name)
            series_id = self.tree.insert("", "end", text=f"{display_name}", open=True)
            self.series_items[series_name] = series_id
        return self.series_items[series_name]

    def _get_or_create_chapter(
        self, series_id: str, chapter_key: str, result: SearchResult
    ) -> str:
        """Get or create a chapter node in the tree."""
        if chapter_key not in self.chapter_items:
            display_name = result.display_name
            chapter_id = self.tree.insert(
                series_id, "end", text=display_name, open=True
            )
            self.chapter_items[chapter_key] = chapter_id
        return self.chapter_items[chapter_key]

    def _update_count(self, count: int):
        """Update the results count label."""
        self.results_label.configure(text=f"Results ({count} matches)")

    def _update_series_counts(self):
        """Update match counts on series nodes."""
        for series_name, series_id in self.series_items.items():
            # Count matches in this series
            count = sum(
                1 for r in self.results.values() if r.book_series == series_name
            )
            current_text = self.tree.item(series_id, "text")
            # Extract base name without count
            base_name = current_text.split(" (")[0]
            self.tree.item(series_id, text=f"{base_name} ({count})")

    def _on_tree_select(self, event):
        """Handle tree selection."""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in self.results:
                self.on_select(self.results[item_id])

    def _on_double_click(self, event):
        """Handle double-click to open PDF."""
        item_id = self.tree.identify_row(event.y)
        if item_id in self.results:
            result = self.results[item_id]
            # Open PDF at page (macOS)
            import subprocess

            subprocess.run(["open", "-a", "Preview", str(result.pdf_path)])

    def _expand_all(self):
        """Expand all tree nodes."""

        def expand_children(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_children(child)

        for item in self.tree.get_children():
            expand_children(item)

    def _collapse_all(self):
        """Collapse all tree nodes."""
        for item in self.tree.get_children():
            self.tree.item(item, open=False)

    def get_all_results(self) -> list[SearchResult]:
        """Get all results."""
        return list(self.results.values())

    def _on_click(self, event):
        """Handle click to toggle checkbox."""
        # Identify which column was clicked
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)

        # Column #1 is the "select" column (after #0 which is tree column)
        if column == "#1" and item_id in self.results:
            self._toggle_selection(item_id)

    def _toggle_selection(self, item_id: str):
        """Toggle selection state of an item."""
        current_values = list(self.tree.item(item_id, "values"))
        if not current_values:
            return

        if item_id in self.selected_items:
            # Deselect
            self.selected_items.discard(item_id)
            current_values[0] = "☐"
        else:
            # Select
            self.selected_items.add(item_id)
            current_values[0] = "☑"

        self.tree.item(item_id, values=current_values)
        self._update_selection_label()
        self._notify_selection_change()

    def _select_all(self):
        """Select all result items."""
        for item_id in self.results:
            if item_id not in self.selected_items:
                self.selected_items.add(item_id)
                current_values = list(self.tree.item(item_id, "values"))
                if current_values:
                    current_values[0] = "☑"
                    self.tree.item(item_id, values=current_values)
        self._update_selection_label()
        self._notify_selection_change()

    def _clear_selection(self):
        """Clear all selections."""
        for item_id in list(self.selected_items):
            current_values = list(self.tree.item(item_id, "values"))
            if current_values:
                current_values[0] = "☐"
                self.tree.item(item_id, values=current_values)
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
            selected_results = self.get_selected_results()
            self.on_selection_change(selected_results)

    def get_selected_results(self) -> list[SearchResult]:
        """Get list of selected SearchResult objects."""
        return [
            self.results[item_id]
            for item_id in self.selected_items
            if item_id in self.results
        ]

    # ==================== Smart Selection Methods ====================

    def smart_select_balanced(self, target_per_group: int = 6) -> list[str]:
        """
        Auto-select first N results from each book series for balanced coverage.

        Args:
            target_per_group: Target number of results per book series

        Returns:
            List of selected item IDs
        """
        self._clear_selection()
        selected_ids = []

        # Group by book series
        by_series: dict[str, list[str]] = {}
        for item_id, result in self.results.items():
            series = result.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Select top N from each series
        for series, items in by_series.items():
            for item_id in items[:target_per_group]:
                self._select_item(item_id)
                selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def smart_select_high_confidence(self, threshold: float = 0.8) -> list[str]:
        """
        Select first 20 results (confidence-based selection removed).

        Returns:
            List of selected item IDs
        """
        self._clear_selection()
        selected_ids = []

        # Just select first 20 results
        for i, item_id in enumerate(self.results.keys()):
            if i >= 20:
                break
            self._select_item(item_id)
            selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def smart_select_diverse(self, max_per_source: int = 3) -> list[str]:
        """
        Select results from multiple book series for diversity.
        Limits results per source to ensure variety.

        Args:
            max_per_source: Maximum results per book series

        Returns:
            List of selected item IDs
        """
        self._clear_selection()
        selected_ids = []

        # Group by book series
        by_series: dict[str, list[str]] = {}
        for item_id, result in self.results.items():
            series = result.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append(item_id)

        # Take top N from each series
        for series, items in by_series.items():
            for item_id in items[:max_per_source]:
                self._select_item(item_id)
                selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def _select_item(self, item_id: str):
        """Select a single item (helper for smart selection)."""
        if item_id not in self.selected_items:
            self.selected_items.add(item_id)
            current_values = list(self.tree.item(item_id, "values"))
            if current_values:
                current_values[0] = "☑"
                self.tree.item(item_id, values=current_values)

    def _create_context_menu(self):
        """Create the right-click context menu."""
        import tkinter as tk

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Extract Images from PDF", command=self._handle_extract_images
        )
        self.context_menu.add_command(
            label="Index Text (Background)", command=self._handle_index_text
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open PDF", command=self._handle_open_pdf)

    def _show_context_menu(self, event):
        """Show context menu on right click."""
        item_id = self.tree.identify_row(event.y)
        if item_id in self.results:
            # Select the item first
            self.tree.selection_set(item_id)
            self._on_tree_select(None)

            # Show menu
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def _handle_extract_images(self):
        """Handle extract images menu action."""
        selection = self.tree.selection()
        if selection and self.on_extract_images:
            item_id = selection[0]
            if item_id in self.results:
                self.on_extract_images(self.results[item_id])

    def _handle_index_text(self):
        """Handle index text menu action."""
        selection = self.tree.selection()
        if selection and self.on_index_text:
            item_id = selection[0]
            if item_id in self.results:
                self.on_index_text(self.results[item_id])

    def _handle_open_pdf(self):
        """Handle open PDF menu action."""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in self.results:
                result = self.results[item_id]
                import subprocess

                subprocess.run(["open", "-a", "Preview", str(result.pdf_path)])
