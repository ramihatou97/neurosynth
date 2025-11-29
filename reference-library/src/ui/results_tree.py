"""Hierarchical results tree display."""
import customtkinter as ctk
from tkinter import ttk
from typing import Callable, Optional
from pathlib import Path

import config
from ..search.result_model import SearchResult
from ..ai.category_model import CategoryResult
from .styles import FONTS, PADDING


class ResultsTree(ctk.CTkFrame):
    """Hierarchical tree view for search results."""

    def __init__(
        self,
        parent,
        on_select: Callable[[SearchResult], None],
        on_selection_change: Optional[Callable[[list[SearchResult]], None]] = None,
        database=None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_select = on_select
        self.on_selection_change = on_selection_change  # Callback when checkbox selection changes
        self.database = database  # Database for figure count queries
        self.results: dict[str, SearchResult] = {}  # item_id -> SearchResult
        self.series_items: dict[str, str] = {}  # series_name -> tree_item_id
        self.chapter_items: dict[str, str] = {}  # chapter_key -> tree_item_id
        self.selected_items: set[str] = set()  # Track checked items

        # Filter state tracking
        self._detached_items: set[str] = set()  # Items currently hidden
        self._item_parents: dict[str, str] = {}  # item_id -> parent_id for reattach
        self._active_filter: list[str] = []  # Currently active category filter

        self._setup_ui()

    def _setup_ui(self):
        """Set up the tree view UI."""
        # Header
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
            fieldbackground="#2b2b2b"
        )
        style.configure(
            "Results.Treeview.Heading",
            font=FONTS["body"],
            foreground="#FFFFFF",
            background="#1e1e1e"
        )

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")

        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("select", "category", "page", "figs", "confidence"),
            show="tree headings",
            yscrollcommand=scrollbar.set,
            style="Results.Treeview"
        )
        self.tree.pack(fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)

        # Configure columns
        self.tree.heading("#0", text="Source", anchor="w")
        self.tree.heading("select", text="✓")
        self.tree.heading("category", text="Category")
        self.tree.heading("page", text="Page")
        self.tree.heading("figs", text="Figs")
        self.tree.heading("confidence", text="Conf.")

        self.tree.column("#0", width=300, minwidth=200)
        self.tree.column("select", width=30, minwidth=30, anchor="center")
        self.tree.column("category", width=100, minwidth=80, anchor="center")
        self.tree.column("page", width=50, minwidth=40, anchor="center")
        self.tree.column("figs", width=40, minwidth=35, anchor="center")
        self.tree.column("confidence", width=50, minwidth=40, anchor="center")

        # Bind selection and checkbox toggle
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)

        # Configure tag colors for categories
        for category, color in config.CATEGORY_COLORS.items():
            self.tree.tag_configure(category, foreground=color)
        # Configure uncategorized tag for results without category yet
        self.tree.tag_configure("uncategorized", foreground="#CCCCCC")

    def clear(self):
        """Clear all results from tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results.clear()
        self.series_items.clear()
        self.chapter_items.clear()
        self.selected_items.clear()
        self._detached_items.clear()
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
            values=(
                "☐",  # Unchecked checkbox
                result.category or "...",
                result.page_number,
                fig_count,
                f"{result.category_confidence:.0%}" if result.category_confidence else "..."
            ),
            tags=(result.category or "uncategorized",)
        )

        self.results[match_id] = result
        self._item_parents[match_id] = chapter_id  # Track parent for filter reattach

        # Apply current filter if active
        if self._active_filter:
            category = result.category or "Other"
            if category not in self._active_filter:
                self.tree.detach(match_id)
                self._detached_items.add(match_id)

        self._update_count(len(self.results) - len(self._detached_items))

    def _get_figure_count(self, result: SearchResult) -> str:
        """Get figure count for a result's page."""
        if not self.database:
            return "-"
        try:
            count = self.database.get_figure_count(result.pdf_path, result.page_number)
            return str(count) if count > 0 else "-"
        except Exception:
            return "-"

    def _get_or_create_series(self, series_name: str) -> str:
        """Get or create a series node in the tree."""
        if series_name not in self.series_items:
            display_name = config.KNOWN_SERIES.get(series_name, series_name)
            series_id = self.tree.insert(
                "",
                "end",
                text=f"{display_name}",
                open=True
            )
            self.series_items[series_name] = series_id
        return self.series_items[series_name]

    def _get_or_create_chapter(self, series_id: str, chapter_key: str, result: SearchResult) -> str:
        """Get or create a chapter node in the tree."""
        if chapter_key not in self.chapter_items:
            display_name = result.display_name
            chapter_id = self.tree.insert(
                series_id,
                "end",
                text=display_name,
                open=True
            )
            self.chapter_items[chapter_key] = chapter_id
        return self.chapter_items[chapter_key]

    def update_result_category(self, result: SearchResult, cat_result: CategoryResult):
        """Update a result's category in the tree."""
        # Find the tree item for this result
        for item_id, stored_result in self.results.items():
            if (stored_result.pdf_path == result.pdf_path and
                stored_result.page_number == result.page_number and
                stored_result.match_text == result.match_text):

                # Update the stored result
                stored_result.category = cat_result.category
                stored_result.category_group = cat_result.group
                stored_result.category_confidence = cat_result.confidence
                stored_result.category_reasoning = cat_result.reasoning

                # Format display: shortened group prefix + category
                group_prefix = "S" if cat_result.group == "Surgical/Anatomical" else "T"
                display_cat = f"{group_prefix}:{cat_result.category}"

                # Update tree display (preserve checkbox state and figs count)
                current_values = self.tree.item(item_id, "values")
                checkbox = current_values[0] if current_values else "☐"
                figs = current_values[3] if len(current_values) > 3 else "-"
                self.tree.item(
                    item_id,
                    values=(
                        checkbox,
                        display_cat,
                        stored_result.page_number,
                        figs,
                        f"{cat_result.confidence:.0%}"
                    ),
                    tags=(cat_result.category,)
                )
                break

    def _update_count(self, count: int):
        """Update the results count label."""
        self.results_label.configure(text=f"Results ({count} matches)")

    def _update_series_counts(self):
        """Update match counts on series nodes."""
        for series_name, series_id in self.series_items.items():
            # Count matches in this series
            count = sum(1 for r in self.results.values() if r.book_series == series_name)
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

    def filter_by_categories(self, categories: list[str]):
        """Show/hide results based on selected categories."""
        self._active_filter = categories

        # If all categories selected or empty list, show all
        show_all = not categories or len(categories) >= 22  # All subcategories

        for item_id, result in self.results.items():
            # Get result category, default to "Other" if uncategorized
            result_category = result.category or "Other"
            should_show = show_all or result_category in categories

            if should_show and item_id in self._detached_items:
                # Reattach item to its parent
                parent_id = self._item_parents.get(item_id, "")
                self.tree.reattach(item_id, parent_id, "end")
                self._detached_items.discard(item_id)
            elif not should_show and item_id not in self._detached_items:
                # Detach (hide) item
                self.tree.detach(item_id)
                self._detached_items.add(item_id)

        # Update visible count
        visible_count = len(self.results) - len(self._detached_items)
        self._update_count(visible_count)

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
        return [self.results[item_id] for item_id in self.selected_items if item_id in self.results]

    # ==================== Smart Selection Methods ====================

    def get_category_coverage(self) -> dict[str, int]:
        """Get count of results per category group."""
        coverage = {"Surgical/Anatomical": 0, "Theoretical": 0}
        for result in self.results.values():
            if result.category_group in coverage:
                coverage[result.category_group] += 1
        return coverage

    def get_selected_coverage(self) -> dict[str, int]:
        """Get count of selected results per category group."""
        coverage = {"Surgical/Anatomical": 0, "Theoretical": 0}
        for item_id in self.selected_items:
            if item_id in self.results:
                result = self.results[item_id]
                if result.category_group in coverage:
                    coverage[result.category_group] += 1
        return coverage

    def smart_select_balanced(self, target_per_group: int = 6) -> list[str]:
        """
        Auto-select results for balanced category coverage.
        Prioritizes high-confidence results from each group.

        Args:
            target_per_group: Target number of results per category group

        Returns:
            List of selected item IDs
        """
        self._clear_selection()

        # Group results by category group
        surgical = []
        theoretical = []
        for item_id, result in self.results.items():
            if result.category_group == "Surgical/Anatomical":
                surgical.append((item_id, result))
            elif result.category_group == "Theoretical":
                theoretical.append((item_id, result))

        # Sort each group by confidence (highest first)
        surgical.sort(key=lambda x: x[1].category_confidence or 0, reverse=True)
        theoretical.sort(key=lambda x: x[1].category_confidence or 0, reverse=True)

        # Select top N from each group
        selected_ids = []
        for item_id, _ in surgical[:target_per_group]:
            self._select_item(item_id)
            selected_ids.append(item_id)
        for item_id, _ in theoretical[:target_per_group]:
            self._select_item(item_id)
            selected_ids.append(item_id)

        self._update_selection_label()
        self._notify_selection_change()
        return selected_ids

    def smart_select_high_confidence(self, threshold: float = 0.8) -> list[str]:
        """
        Select all results with confidence above threshold.

        Args:
            threshold: Minimum confidence score (0.0-1.0)

        Returns:
            List of selected item IDs
        """
        self._clear_selection()
        selected_ids = []

        for item_id, result in self.results.items():
            if (result.category_confidence or 0) >= threshold:
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
        by_series: dict[str, list[tuple[str, SearchResult]]] = {}
        for item_id, result in self.results.items():
            series = result.book_series
            if series not in by_series:
                by_series[series] = []
            by_series[series].append((item_id, result))

        # Sort each series by confidence and take top N
        for series, items in by_series.items():
            items.sort(key=lambda x: x[1].category_confidence or 0, reverse=True)
            for item_id, _ in items[:max_per_source]:
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
