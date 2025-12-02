"""Search panel component with input and filters."""
import customtkinter as ctk
from typing import Callable

from src import config
from .styles import FONTS, PADDING


class SearchPanel(ctk.CTkFrame):
    """Search input panel with filters."""

    def __init__(
        self,
        parent,
        on_search: Callable[[str], None],  # (query)
        on_cancel: Callable[[], None],
        database=None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_search = on_search
        self.on_cancel = on_cancel
        self.database = database

        # Autocomplete state
        self._autocomplete_popup = None
        self._autocomplete_after_id = None
        self._selected_suggestion_idx = -1

        self._setup_ui()

    def _setup_ui(self):
        """Set up the search panel UI."""
        # Search row
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["medium"]))

        # Search label
        ctk.CTkLabel(
            search_frame,
            text="Search Subject:",
            font=FONTS["body"]
        ).pack(side="left", padx=(0, PADDING["small"]))

        # Search entry
        self.search_entry = ctk.CTkEntry(
            search_frame,
            width=300,
            placeholder_text="Enter neurosurgical topic (e.g., vestibular schwannoma)",
            font=FONTS["body"]
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=PADDING["small"])
        self.search_entry.bind("<Return>", lambda e: self._do_search())
        self.search_entry.bind("<KeyRelease>", self._on_key_release)
        self.search_entry.bind("<Down>", self._on_arrow_down)
        self.search_entry.bind("<Up>", self._on_arrow_up)
        self.search_entry.bind("<Escape>", lambda e: self._hide_autocomplete())
        self.search_entry.bind("<FocusOut>", lambda e: self.after(100, self._hide_autocomplete))

        # History button (recent searches)
        self.history_btn = ctk.CTkButton(
            search_frame,
            text="History",
            command=self._show_history_menu,
            width=60,
            font=FONTS["small"]
        )
        self.history_btn.pack(side="left", padx=(0, PADDING["small"]))

        # Strategy Selector (STRICT/STANDARD/BROAD)
        self.strategy_var = ctk.StringVar(value="standard")
        self.strategy_selector = ctk.CTkOptionMenu(
            search_frame,
            values=["🎯 Strict", "⚖️ Standard", "🌐 Broad"],
            variable=self.strategy_var,
            width=110,
            font=FONTS["small"],
            command=self._on_strategy_change
        )
        self.strategy_selector.pack(side="left", padx=(0, PADDING["small"]))
        # Set default display
        self.strategy_var.set("⚖️ Standard")

        # Search button
        self.search_btn = ctk.CTkButton(
            search_frame,
            text="Search",
            command=self._do_search,
            width=80,
            font=FONTS["body"]
        )
        self.search_btn.pack(side="left", padx=PADDING["small"])

        # Cancel button (hidden by default)
        self.cancel_btn = ctk.CTkButton(
            search_frame,
            text="Cancel",
            command=self.on_cancel,
            width=80,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            font=FONTS["body"]
        )
        # Don't pack yet - will show when searching

        # Related Terms Suggestion Row (hidden by default)
        self.related_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Don't pack initially - shown when related terms found

        self.related_label = ctk.CTkLabel(
            self.related_frame,
            text="Also try:",
            font=FONTS["small"],
            text_color="gray"
        )
        self.related_label.pack(side="left", padx=(PADDING["medium"], PADDING["small"]))

        # Frame to hold clickable term buttons
        self.related_terms_frame = ctk.CTkFrame(self.related_frame, fg_color="transparent")
        self.related_terms_frame.pack(side="left", fill="x")

        self._related_term_buttons = []

    def _do_search(self):
        """Trigger search callback."""
        # If autocomplete is open and a suggestion is selected, use it
        if (self._autocomplete_popup and
            hasattr(self, '_suggestion_buttons') and
            self._selected_suggestion_idx >= 0 and
            self._selected_suggestion_idx < len(self._suggestion_buttons)):
            suggestion = self._suggestion_buttons[self._selected_suggestion_idx].cget("text")
            self._hide_autocomplete()
            self.set_query(suggestion)

        query = self.search_entry.get().strip()
        if query:
            self._hide_autocomplete()
            self.on_search(query)

    def get_strategy(self) -> str:
        """Get current search strategy name.

        Returns:
            Strategy name: 'strict', 'standard', or 'broad'
        """
        display = self.strategy_var.get()
        # Map display name to strategy name
        if "Strict" in display:
            return "strict"
        elif "Broad" in display:
            return "broad"
        return "standard"

    def _on_strategy_change(self, value: str):
        """Handle strategy change - show brief description."""
        descriptions = {
            "🎯 Strict": "Exact matches only, high authority sources",
            "⚖️ Standard": "Balanced search with query expansion",
            "🌐 Broad": "Maximum coverage, all sources included"
        }
        desc = descriptions.get(value, "")
        if desc:
            self._show_strategy_hint(desc)

    def _show_strategy_hint(self, text: str):
        """Show a temporary hint below the search bar."""
        # Create hint label if not exists
        if not hasattr(self, '_strategy_hint'):
            self._strategy_hint = ctk.CTkLabel(
                self,
                text="",
                font=FONTS["small"],
                text_color="#3498db"
            )

        self._strategy_hint.configure(text=text)
        self._strategy_hint.pack(fill="x", padx=PADDING["medium"], pady=(0, 4))

        # Auto-hide after 2 seconds
        if hasattr(self, '_hint_after_id') and self._hint_after_id:
            self.after_cancel(self._hint_after_id)
        self._hint_after_id = self.after(2000, self._hide_strategy_hint)

    def _hide_strategy_hint(self):
        """Hide the strategy hint."""
        if hasattr(self, '_strategy_hint'):
            self._strategy_hint.pack_forget()

    def set_searching(self, is_searching: bool):
        """Update UI for searching state."""
        if is_searching:
            self.search_btn.configure(state="disabled")
            self.search_entry.configure(state="disabled")
            self.cancel_btn.pack(side="left", padx=PADDING["small"])
        else:
            self.search_btn.configure(state="normal")
            self.search_entry.configure(state="normal")
            self.cancel_btn.pack_forget()

    def get_query(self) -> str:
        """Get current search query."""
        return self.search_entry.get().strip()

    def set_query(self, query: str):
        """Set search query programmatically."""
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)

    # ==================== Related Terms Methods ====================

    def show_related_terms(self, terms: list[str]):
        """Show related term suggestions below search bar.

        Args:
            terms: List of related term strings to display
        """
        # Clear existing buttons
        self.hide_related_terms()

        if not terms:
            return

        # Create clickable buttons for each term
        for term in terms[:5]:  # Limit to 5 terms
            btn = ctk.CTkButton(
                self.related_terms_frame,
                text=term,
                font=FONTS["small"],
                fg_color="transparent",
                text_color="#3498db",
                hover_color="#2c3e50",
                height=24,
                command=lambda t=term: self._on_related_term_click(t)
            )
            btn.pack(side="left", padx=2)
            self._related_term_buttons.append(btn)

        # Show the related terms frame
        self.related_frame.pack(fill="x", pady=(0, PADDING["small"]))

    def hide_related_terms(self):
        """Hide related terms suggestions."""
        # Destroy existing buttons
        for btn in self._related_term_buttons:
            btn.destroy()
        self._related_term_buttons = []

        # Hide the frame
        self.related_frame.pack_forget()

    def _on_related_term_click(self, term: str):
        """Handle click on a related term - search for it."""
        self.set_query(term)
        self._do_search()

    # ==================== Search History Methods ====================

    def _show_history_menu(self):
        """Show recent searches popup menu."""
        if not self.database:
            return

        # Get recent searches
        recent = self.database.get_recent_searches(limit=10)
        if not recent:
            return

        # Create popup window
        popup = ctk.CTkToplevel(self)
        popup.title("")
        popup.overrideredirect(True)  # No window decorations
        popup.attributes("-topmost", True)

        # Position below history button
        x = self.history_btn.winfo_rootx()
        y = self.history_btn.winfo_rooty() + self.history_btn.winfo_height()
        popup.geometry(f"+{x}+{y}")

        # Frame for items
        frame = ctk.CTkFrame(popup, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Header
        ctk.CTkLabel(
            frame,
            text="Recent Searches",
            font=FONTS["small"],
            text_color="gray"
        ).pack(padx=PADDING["small"], pady=(PADDING["small"], 0))

        # Add each recent search
        for item in recent:
            query = item["query"]
            count = item["result_count"]
            btn = ctk.CTkButton(
                frame,
                text=f"{query} ({count})",
                font=FONTS["small"],
                fg_color="transparent",
                hover_color=("gray80", "gray30"),
                anchor="w",
                command=lambda q=query, p=popup: self._select_history_item(q, p)
            )
            btn.pack(fill="x", padx=PADDING["small"], pady=2)

        # Close on click outside
        popup.bind("<FocusOut>", lambda e: popup.destroy())

    def _select_history_item(self, query: str, popup):
        """Select a history item and trigger search."""
        popup.destroy()
        self.set_query(query)
        self._do_search()

    # ==================== Autocomplete Methods ====================

    def _on_key_release(self, event):
        """Handle key release for autocomplete."""
        # Ignore navigation keys
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        # Cancel any pending autocomplete
        if self._autocomplete_after_id:
            self.after_cancel(self._autocomplete_after_id)

        # Debounce: wait 150ms before showing suggestions
        self._autocomplete_after_id = self.after(150, self._show_autocomplete)

    def _show_autocomplete(self):
        """Show autocomplete suggestions."""
        if not self.database:
            return

        query = self.search_entry.get().strip()
        if len(query) < 2:
            self._hide_autocomplete()
            return

        # Get suggestions
        suggestions = self.database.get_search_suggestions(
            query,
            limit=7
        )
        if not suggestions:
            self._hide_autocomplete()
            return

        # Hide existing popup
        self._hide_autocomplete()

        # Create popup
        self._autocomplete_popup = ctk.CTkToplevel(self)
        self._autocomplete_popup.title("")
        self._autocomplete_popup.overrideredirect(True)
        self._autocomplete_popup.attributes("-topmost", True)

        # Position below search entry
        x = self.search_entry.winfo_rootx()
        y = self.search_entry.winfo_rooty() + self.search_entry.winfo_height()
        width = self.search_entry.winfo_width()
        self._autocomplete_popup.geometry(f"{width}x{len(suggestions) * 30 + 10}+{x}+{y}")

        # Frame
        frame = ctk.CTkFrame(self._autocomplete_popup, corner_radius=4)
        frame.pack(fill="both", expand=True)

        # Store suggestion buttons for navigation
        self._suggestion_buttons = []
        self._selected_suggestion_idx = -1

        for i, suggestion in enumerate(suggestions):
            btn = ctk.CTkButton(
                frame,
                text=suggestion,
                font=FONTS["small"],
                fg_color="transparent",
                hover_color=("gray80", "gray30"),
                anchor="w",
                height=28,
                command=lambda s=suggestion: self._select_suggestion(s)
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._suggestion_buttons.append(btn)

    def _hide_autocomplete(self):
        """Hide autocomplete popup."""
        if self._autocomplete_popup:
            self._autocomplete_popup.destroy()
            self._autocomplete_popup = None
            self._suggestion_buttons = []
            self._selected_suggestion_idx = -1

    def _on_arrow_down(self, event):
        """Navigate down in suggestions."""
        if not self._autocomplete_popup or not self._suggestion_buttons:
            return "break"

        # Unhighlight current
        if self._selected_suggestion_idx >= 0:
            self._suggestion_buttons[self._selected_suggestion_idx].configure(fg_color="transparent")

        # Move down
        self._selected_suggestion_idx = min(
            self._selected_suggestion_idx + 1,
            len(self._suggestion_buttons) - 1
        )

        # Highlight new
        self._suggestion_buttons[self._selected_suggestion_idx].configure(fg_color=("gray80", "gray30"))
        return "break"

    def _on_arrow_up(self, event):
        """Navigate up in suggestions."""
        if not self._autocomplete_popup or not self._suggestion_buttons:
            return "break"

        # Unhighlight current
        if self._selected_suggestion_idx >= 0:
            self._suggestion_buttons[self._selected_suggestion_idx].configure(fg_color="transparent")

        # Move up
        self._selected_suggestion_idx = max(self._selected_suggestion_idx - 1, 0)

        # Highlight new
        self._suggestion_buttons[self._selected_suggestion_idx].configure(fg_color=("gray80", "gray30"))
        return "break"

    def _select_suggestion(self, suggestion: str):
        """Select a suggestion and trigger search."""
        self._hide_autocomplete()
        self.set_query(suggestion)
        self._do_search()
