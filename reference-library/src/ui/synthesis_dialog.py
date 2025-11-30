"""Dialog for starting chapter synthesis."""
import customtkinter as ctk
from typing import Optional, List

from .styles import FONTS, PADDING
from ..search.result_model import SearchResult


class SynthesisDialog(ctk.CTkToplevel):
    """Dialog to get synthesis options from user."""

    def __init__(
        self,
        parent,
        initial_topic: str = "",
        title: str = "Synthesize Chapter",
        selected_results: Optional[List[SearchResult]] = None
    ):
        super().__init__(parent)
        self.title(title)

        # Center the dialog
        width = 450
        height = 350
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.result: Optional[tuple[str, str]] = None
        self.selected_results = selected_results or []
        self._setup_failed = False  # Track setup status

        # Setup UI with error handling - print errors BEFORE grab_set blocks
        try:
            self._setup_ui(initial_topic)
        except Exception as e:
            print(f"ERROR: Failed to create synthesis dialog: {e}")
            import traceback
            traceback.print_exc()
            self._setup_failed = True
            self._show_error_ui(str(e))

        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.wait_window()

    def _show_error_ui(self, error_msg: str):
        """Show error message when dialog fails to initialize."""
        try:
            ctk.CTkLabel(
                self,
                text="Dialog Error",
                font=("Helvetica", 14, "bold")
            ).pack(pady=20)

            ctk.CTkLabel(
                self,
                text=f"Could not create synthesis dialog:\n{error_msg}",
                font=("Helvetica", 11),
                wraplength=400
            ).pack(pady=10, padx=20)

            ctk.CTkButton(
                self,
                text="Close",
                command=self.destroy,
                width=100
            ).pack(pady=20)
        except Exception:
            # If even error UI fails, just close
            self.after(100, self.destroy)

    def _setup_ui(self, initial_topic: str):
        """Set up the dialog UI."""
        # Topic Section
        ctk.CTkLabel(
            self,
            text="Chapter Topic:",
            font=FONTS["body_bold"]
        ).pack(anchor="w", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"]))

        self.topic_entry = ctk.CTkEntry(
            self,
            width=300,
            font=FONTS["body"]
        )
        self.topic_entry.pack(fill="x", padx=PADDING["medium"])
        self.topic_entry.insert(0, initial_topic)
        self.topic_entry.focus_set()

        # Analyze selected results to recommend template
        recommended_type, recommendation_text = self._analyze_selection()

        # Type Section
        ctk.CTkLabel(
            self,
            text="Chapter Type:",
            font=FONTS["body_bold"]
        ).pack(anchor="w", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"]))

        # Show recommendation if available
        if recommendation_text:
            ctk.CTkLabel(
                self,
                text=f"💡 {recommendation_text}",
                font=FONTS["small"],
                text_color="#95a5a6"
            ).pack(anchor="w", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        self.type_var = ctk.StringVar(value=recommended_type)

        ctk.CTkRadioButton(
            self,
            text="Surgical",
            variable=self.type_var,
            value="procedural",
            font=FONTS["body"]
        ).pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        ctk.CTkRadioButton(
            self,
            text="Clinical",
            variable=self.type_var,
            value="theoretical",
            font=FONTS["body"]
        ).pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["large"], side="bottom")

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self._on_cancel,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            width=100
        ).pack(side="right", padx=(PADDING["small"], 0))

        ctk.CTkButton(
            btn_frame,
            text="Synthesize",
            command=self._on_submit,
            width=100,
            fg_color="#27ae60",
            hover_color="#219a52"
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._on_submit())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _analyze_selection(self) -> tuple[str, str]:
        """
        Get default template type and optional recommendation text.

        Category is a "lens" for generation - the user decides how to interpret
        sources, not the system. The same source can be used for different chapter types.

        Returns:
            Tuple of (default_type, recommendation_text)
        """
        source_count = len(self.selected_results)
        if source_count > 0:
            return ("procedural", f"{source_count} sources selected")
        return ("procedural", "")

    def _on_submit(self):
        """Handle submit."""
        topic = self.topic_entry.get().strip()
        if not topic:
            return
            
        template_type = self.type_var.get()
        self.result = (topic, template_type)
        self.destroy()

    def _on_cancel(self):
        """Handle cancel."""
        self.destroy()

    def get_input(self) -> Optional[tuple[str, str]]:
        """Get the dialog result."""
        if self._setup_failed:
            return None
        return self.result
