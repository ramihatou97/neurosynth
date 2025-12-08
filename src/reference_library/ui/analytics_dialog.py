"""Analytics dialog showing search patterns and statistics."""

from typing import Optional

import customtkinter as ctk

from ..cache.database import Database
from .styles import FONTS, PADDING


class AnalyticsDialog(ctk.CTkToplevel):
    """Dialog displaying search analytics and statistics."""

    def __init__(self, parent, database: Database):
        super().__init__(parent)
        self.title("Search Analytics")
        self.database = database

        # Set size and position
        width = 600
        height = 500
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self._setup_ui()

        # Make modal
        self.transient(parent)
        self.grab_set()

    def _setup_ui(self):
        """Set up the analytics UI."""
        # Title
        ctk.CTkLabel(self, text="📊 Search Analytics", font=FONTS["heading"]).pack(
            pady=PADDING["medium"]
        )

        # Create scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(
            fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["small"]
        )

        # Get analytics data
        cache_stats = self.database.get_cache_stats()
        recent_searches = self.database.get_recent_searches(limit=50)

        # Cache Statistics Section
        self._add_section(scroll_frame, "📦 Cache Statistics")
        self._add_stat(scroll_frame, "Cached Pages", cache_stats.get("cached_pages", 0))
        self._add_stat(
            scroll_frame, "Total Searches", cache_stats.get("total_searches", 0)
        )
        self._add_stat(scroll_frame, "Indexed PDFs", cache_stats.get("indexed_pdfs", 0))

        # Search Pattern Analysis
        if recent_searches:
            self._add_section(scroll_frame, "🔍 Search Patterns (Last 50 Searches)")

            # Calculate statistics
            total_searches = len(recent_searches)
            total_results = sum(s.get("result_count", 0) for s in recent_searches)
            avg_results = total_results / total_searches if total_searches > 0 else 0

            self._add_stat(
                scroll_frame, "Average Results per Search", f"{avg_results:.1f}"
            )
            self._add_stat(scroll_frame, "Total Results Found", total_results)

            # Search mode distribution
            mode_counts = {}
            for search in recent_searches:
                mode = search.get("search_mode", "unknown")
                mode_counts[mode] = mode_counts.get(mode, 0) + 1

            if mode_counts:
                self._add_section(scroll_frame, "🎯 Search Mode Usage")
                for mode, count in sorted(
                    mode_counts.items(), key=lambda x: x[1], reverse=True
                ):
                    pct = (count / total_searches) * 100
                    self._add_stat(
                        scroll_frame, mode.capitalize(), f"{count} ({pct:.1f}%)"
                    )

            # Top searches
            self._add_section(scroll_frame, "🔥 Recent Searches")
            for i, search in enumerate(recent_searches[:10], 1):
                query = search.get("query", "Unknown")
                result_count = search.get("result_count", 0)

                # Truncate long queries
                if len(query) > 40:
                    query = query[:37] + "..."

                ctk.CTkLabel(
                    scroll_frame,
                    text=f"{i}. {query} ({result_count} results)",
                    font=FONTS["small"],
                    anchor="w",
                ).pack(fill="x", padx=PADDING["medium"], pady=2)

        # Close button
        ctk.CTkButton(
            self, text="Close", command=self.destroy, font=FONTS["body"]
        ).pack(pady=PADDING["medium"])

    def _add_section(self, parent, title: str):
        """Add a section header."""
        ctk.CTkLabel(parent, text=title, font=FONTS["subheading"], anchor="w").pack(
            fill="x", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"])
        )

    def _add_stat(self, parent, label: str, value):
        """Add a statistic row."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=PADDING["medium"], pady=2)

        ctk.CTkLabel(frame, text=f"{label}:", font=FONTS["body"], anchor="w").pack(
            side="left"
        )

        ctk.CTkLabel(frame, text=str(value), font=FONTS["body_bold"], anchor="e").pack(
            side="right"
        )
