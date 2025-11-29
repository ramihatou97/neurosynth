"""Dialog for starting chapter synthesis."""
import customtkinter as ctk
from typing import Optional

from .styles import FONTS, PADDING


class SynthesisDialog(ctk.CTkToplevel):
    """Dialog to get synthesis options from user."""

    def __init__(
        self,
        parent,
        initial_topic: str = "",
        title: str = "Synthesize Chapter"
    ):
        super().__init__(parent)
        self.title(title)
        
        # Center the dialog
        width = 400
        height = 300
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.result: Optional[tuple[str, str]] = None
        
        self._setup_ui(initial_topic)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.wait_window()

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

        # Type Section
        ctk.CTkLabel(
            self,
            text="Chapter Type:",
            font=FONTS["body_bold"]
        ).pack(anchor="w", padx=PADDING["medium"], pady=(PADDING["medium"], PADDING["small"]))

        self.type_var = ctk.StringVar(value="procedural")

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
        return self.result
