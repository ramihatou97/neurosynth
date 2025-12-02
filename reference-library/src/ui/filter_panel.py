"""Additional filter controls panel."""
import customtkinter as ctk
from typing import Callable, Optional

from src import config
from .styles import FONTS, PADDING


class FilterPanel(ctk.CTkFrame):
    """Advanced filtering options panel."""

    def __init__(
        self,
        parent,
        on_filter_change: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_filter_change = on_filter_change

        self._setup_ui()

    def _setup_ui(self):
        """Set up the filter panel UI."""
        # Series filter
        ctk.CTkLabel(
            self,
            text="Filter by Book Series:",
            font=FONTS["small"]
        ).pack(anchor="w", padx=PADDING["small"], pady=(PADDING["small"], 0))

        self.series_var = ctk.StringVar(value="All Series")
        self.series_menu = ctk.CTkOptionMenu(
            self,
            variable=self.series_var,
            values=["All Series"] + list(config.KNOWN_SERIES.values()),
            command=self._on_series_change,
            width=200
        )
        self.series_menu.pack(anchor="w", padx=PADDING["small"], pady=PADDING["small"])

    def _on_series_change(self, _value):
        """Handle series filter change."""
        if self.on_filter_change:
            self.on_filter_change()

    def get_series_filter(self) -> Optional[str]:
        """Get selected series filter."""
        value = self.series_var.get()
        if value == "All Series":
            return None
        return value
