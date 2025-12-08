"""Auto-Sync configuration dialog.

Provides GUI settings for automated PDF indexing and Deep-DX synchronization.
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from reference_library import config

from .styles import FONTS, PADDING


class AutoSyncDialog(ctk.CTkToplevel):
    """Dialog for configuring auto-sync settings.

    Features:
    - Toggle auto-indexing on/off
    - Toggle auto-sync to Deep-DX on/off
    - Adjust index debounce period (5-300s)
    - Adjust sync debounce period (10-600s)
    - Validation (auto-sync requires auto-index)
    - Settings persistence to user_config.json
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Auto-Sync Configuration")
        self.settings_changed = False

        # Set size and position
        width = 550
        height = 550
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Load current settings
        self.auto_index_enabled = tk.BooleanVar(value=config.get_auto_index_enabled())
        self.auto_sync_enabled = tk.BooleanVar(value=config.get_auto_sync_enabled())
        self.index_debounce = tk.IntVar(value=config.get_auto_index_debounce_seconds())
        self.sync_debounce = tk.IntVar(value=config.get_auto_sync_debounce_seconds())

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(
            self, text="⚙️ Auto-Sync Configuration", font=FONTS["heading"]
        )
        title_label.pack(pady=(PADDING["large"], PADDING["medium"]))

        # Subtitle
        subtitle = ctk.CTkLabel(
            self,
            text="Configure automated PDF indexing and Deep-DX synchronization",
            font=FONTS["small"],
            text_color="gray60",
        )
        subtitle.pack(pady=(0, PADDING["large"]))

        # Content container
        content = ctk.CTkFrame(self)
        content.pack(
            fill="both", expand=True, padx=PADDING["large"], pady=(0, PADDING["medium"])
        )

        # Auto-Index Section
        self._create_index_section(content)

        # Separator
        separator1 = ctk.CTkFrame(content, height=2, fg_color="gray30")
        separator1.pack(fill="x", pady=PADDING["large"])

        # Auto-Sync Section
        self._create_sync_section(content)

        # Separator
        separator2 = ctk.CTkFrame(content, height=2, fg_color="gray30")
        separator2.pack(fill="x", pady=PADDING["large"])

        # Help Text
        help_frame = ctk.CTkFrame(content, fg_color="transparent")
        help_frame.pack(fill="x", pady=PADDING["small"])

        help_text = ctk.CTkLabel(
            help_frame,
            text=(
                "💡 Tips:\n"
                "• Auto-sync requires auto-indexing to be enabled\n"
                "• Debounce = wait time for batch processing\n"
                "• Lower values = faster response, higher values = fewer API calls\n"
                "• Settings take effect immediately after saving"
            ),
            font=FONTS["small"],
            text_color="gray60",
            justify="left",
        )
        help_text.pack(anchor="w", padx=PADDING["small"])

        # Buttons
        self._create_button_bar()

    def _create_index_section(self, parent):
        """Create auto-index configuration section."""
        index_frame = ctk.CTkFrame(parent, fg_color="transparent")
        index_frame.pack(fill="x", pady=PADDING["small"])

        # Toggle
        index_toggle = ctk.CTkCheckBox(
            index_frame,
            text="Enable Auto-Indexing",
            variable=self.auto_index_enabled,
            command=self._on_index_toggle,
            font=FONTS["body_bold"],
        )
        index_toggle.pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        # Description
        index_desc = ctk.CTkLabel(
            index_frame,
            text="Automatically index new PDFs when added to the library",
            font=FONTS["small"],
            text_color="gray60",
        )
        index_desc.pack(anchor="w", padx=(PADDING["large"] + 20, PADDING["medium"]))

        # Debounce slider
        debounce_frame = ctk.CTkFrame(index_frame, fg_color="transparent")
        debounce_frame.pack(
            fill="x",
            padx=(PADDING["large"] + 20, PADDING["medium"]),
            pady=PADDING["small"],
        )

        self.index_debounce_label = ctk.CTkLabel(
            debounce_frame,
            text=f"Index debounce: {self.index_debounce.get()}s",
            font=FONTS["small"],
        )
        self.index_debounce_label.pack(anchor="w")

        index_slider = ctk.CTkSlider(
            debounce_frame,
            from_=5,
            to=300,
            variable=self.index_debounce,
            command=self._on_index_debounce_changed,
        )
        index_slider.pack(fill="x", pady=PADDING["small"])

        slider_hint = ctk.CTkLabel(
            debounce_frame,
            text="5s (fast) ← → 300s (fewer API calls)",
            font=("Arial", 9),
            text_color="gray50",
        )
        slider_hint.pack(anchor="w")

    def _create_sync_section(self, parent):
        """Create auto-sync configuration section."""
        sync_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sync_frame.pack(fill="x", pady=PADDING["small"])

        # Toggle
        sync_toggle = ctk.CTkCheckBox(
            sync_frame,
            text="Enable Auto-Sync to Deep-DX",
            variable=self.auto_sync_enabled,
            command=self._on_sync_toggle,
            font=FONTS["body_bold"],
        )
        sync_toggle.pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        # Description
        sync_desc = ctk.CTkLabel(
            sync_frame,
            text="Automatically sync indexed PDFs to Deep-DX search engine",
            font=FONTS["small"],
            text_color="gray60",
        )
        sync_desc.pack(anchor="w", padx=(PADDING["large"] + 20, PADDING["medium"]))

        # Debounce slider
        debounce_frame = ctk.CTkFrame(sync_frame, fg_color="transparent")
        debounce_frame.pack(
            fill="x",
            padx=(PADDING["large"] + 20, PADDING["medium"]),
            pady=PADDING["small"],
        )

        self.sync_debounce_label = ctk.CTkLabel(
            debounce_frame,
            text=f"Sync debounce: {self.sync_debounce.get()}s",
            font=FONTS["small"],
        )
        self.sync_debounce_label.pack(anchor="w")

        sync_slider = ctk.CTkSlider(
            debounce_frame,
            from_=10,
            to=600,
            variable=self.sync_debounce,
            command=self._on_sync_debounce_changed,
        )
        sync_slider.pack(fill="x", pady=PADDING["small"])

        slider_hint = ctk.CTkLabel(
            debounce_frame,
            text="10s (fast) ← → 600s (fewer operations)",
            font=("Arial", 9),
            text_color="gray50",
        )
        slider_hint.pack(anchor="w")

    def _create_button_bar(self):
        """Create button bar at bottom."""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=PADDING["large"], pady=PADDING["medium"])

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.destroy,
            width=100,
            fg_color="gray40",
            hover_color="gray50",
        )
        cancel_btn.pack(side="right", padx=(PADDING["small"], 0))

        # Save button
        save_btn = ctk.CTkButton(
            button_frame, text="Save Settings", command=self._on_save, width=120
        )
        save_btn.pack(side="right", padx=PADDING["small"])

    # Event Handlers

    def _on_index_toggle(self):
        """Handle auto-index toggle change.

        Validate: Can't disable index if sync is enabled.
        """
        if not self.auto_index_enabled.get() and self.auto_sync_enabled.get():
            messagebox.showwarning(
                "Invalid Configuration",
                "Auto-sync requires auto-indexing to be enabled.\n\n"
                "Auto-sync has been disabled.",
                parent=self,
            )
            self.auto_sync_enabled.set(False)

    def _on_sync_toggle(self):
        """Handle auto-sync toggle change.

        Auto-enable index if sync is enabled.
        """
        if self.auto_sync_enabled.get() and not self.auto_index_enabled.get():
            self.auto_index_enabled.set(True)
            messagebox.showinfo(
                "Auto-Index Enabled",
                "Auto-indexing has been automatically enabled\n"
                "because it's required for auto-sync.",
                parent=self,
            )

    def _on_index_debounce_changed(self, value):
        """Update index debounce label when slider moves."""
        seconds = int(value)
        self.index_debounce_label.configure(text=f"Index debounce: {seconds}s")

    def _on_sync_debounce_changed(self, value):
        """Update sync debounce label when slider moves."""
        seconds = int(value)
        self.sync_debounce_label.configure(text=f"Sync debounce: {seconds}s")

    def _on_save(self):
        """Save settings to config and close dialog."""
        # Get final values
        index_enabled = self.auto_index_enabled.get()
        sync_enabled = self.auto_sync_enabled.get()
        index_debounce = self.index_debounce.get()
        sync_debounce = self.sync_debounce.get()

        # Final validation
        if sync_enabled and not index_enabled:
            messagebox.showerror(
                "Invalid Configuration",
                "Auto-sync requires auto-indexing to be enabled.\n\n"
                "Please enable auto-indexing or disable auto-sync.",
                parent=self,
            )
            return

        # Save to config
        config.set_auto_index_enabled(index_enabled)
        config.set_auto_sync_enabled(sync_enabled)
        config.set_auto_index_debounce_seconds(index_debounce)
        config.set_auto_sync_debounce_seconds(sync_debounce)

        self.settings_changed = True

        # Show confirmation
        status = []
        if index_enabled:
            status.append(f"Auto-indexing enabled ({index_debounce}s debounce)")
        else:
            status.append("Auto-indexing disabled")

        if sync_enabled:
            status.append(f"Auto-sync enabled ({sync_debounce}s debounce)")
        else:
            status.append("Auto-sync disabled")

        messagebox.showinfo(
            "Settings Saved",
            "Auto-sync settings saved successfully!\n\n"
            + "\n".join(status)
            + "\n\nSettings will take effect after restarting the application.",
            parent=self,
        )

        self.destroy()
