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

        # Confidence filter
        ctk.CTkLabel(
            self,
            text="Minimum Confidence:",
            font=FONTS["small"]
        ).pack(anchor="w", padx=PADDING["small"], pady=(PADDING["small"], 0))

        self.confidence_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=100,
            number_of_steps=10,
            command=self._on_confidence_change
        )
        self.confidence_slider.set(0)
        self.confidence_slider.pack(anchor="w", padx=PADDING["small"], pady=2)

        self.confidence_label = ctk.CTkLabel(
            self,
            text="0%",
            font=FONTS["small"]
        )
        self.confidence_label.pack(anchor="w", padx=PADDING["small"])

        # Uncategorized toggle
        self.show_uncategorized = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self,
            text="Show uncategorized",
            variable=self.show_uncategorized,
            command=self._on_filter_change,
            font=FONTS["small"]
        ).pack(anchor="w", padx=PADDING["small"], pady=PADDING["small"])

    def _on_series_change(self, value):
        """Handle series filter change."""
        if self.on_filter_change:
            self.on_filter_change()

    def _on_confidence_change(self, value):
        """Handle confidence slider change."""
        self.confidence_label.configure(text=f"{int(value)}%")
        if self.on_filter_change:
            self.on_filter_change()

    def _on_filter_change(self):
        """Handle any filter change."""
        if self.on_filter_change:
            self.on_filter_change()

    def get_series_filter(self) -> Optional[str]:
        """Get selected series filter."""
        value = self.series_var.get()
        if value == "All Series":
            return None
        return value

    def get_min_confidence(self) -> float:
        """Get minimum confidence threshold."""
        return self.confidence_slider.get() / 100.0

    def get_show_uncategorized(self) -> bool:
        """Get whether to show uncategorized results."""
        return self.show_uncategorized.get()
