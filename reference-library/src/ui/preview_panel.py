"""Preview panel for displaying selected result details."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src import config

from ..search.result_model import SearchResult
from .styles import FONTS, PADDING

# Thumbnail settings
THUMB_SIZE = (80, 80)
MAX_THUMBS_DISPLAY = 12  # Show more figures per page


class PreviewPanel(ctk.CTkFrame):
    """Panel displaying detailed preview of selected result."""

    def __init__(self, parent, database=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.current_result: Optional[SearchResult] = None
        self.database = database
        self._thumbnail_images: list = []  # Keep references to prevent GC
        self._current_figures: list[dict] = []

        self._setup_ui()

    def _setup_ui(self):
        """Set up the preview panel UI."""
        # Header
        ctk.CTkLabel(self, text="Preview", font=FONTS["subheading"]).pack(
            anchor="w", padx=PADDING["medium"], pady=PADDING["small"]
        )

        # Safety Alert Frame (Hidden by default)
        self.safety_frame = ctk.CTkFrame(self, fg_color="#c0392b", corner_radius=6)
        self.safety_label = ctk.CTkLabel(
            self.safety_frame,
            text="",
            font=FONTS["body_bold"],
            text_color="white",
            justify="left",
            wraplength=350,
        )
        self.safety_label.pack(padx=PADDING["medium"], pady=PADDING["small"], fill="x")
        # Don't pack safety_frame yet

        # Metadata section
        self.metadata_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.metadata_frame.pack(
            fill="x", padx=PADDING["medium"], pady=PADDING["small"]
        )

        # Confidence Gauge (Hidden by default)
        self.confidence_label = ctk.CTkLabel(
            self.metadata_frame, text="", font=FONTS["small_bold"], text_color="#27ae60"
        )
        # Pack order handled in show_result

        # Book info
        self.book_label = ctk.CTkLabel(
            self.metadata_frame, text="Book: -", font=FONTS["body"], anchor="w"
        )
        self.book_label.pack(fill="x")

        # Chapter info
        self.chapter_label = ctk.CTkLabel(
            self.metadata_frame, text="Chapter: -", font=FONTS["body"], anchor="w"
        )
        self.chapter_label.pack(fill="x")

        # Page info
        self.page_label = ctk.CTkLabel(
            self.metadata_frame, text="Page: -", font=FONTS["body"], anchor="w"
        )
        self.page_label.pack(fill="x")

        # Match location info (where in document the match was found)
        self.location_label = ctk.CTkLabel(
            self.metadata_frame,
            text="",
            font=FONTS["body"],
            anchor="w",
            text_color="#6c5ce7",
        )
        self.location_label.pack(fill="x")

        # Separator
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(
            fill="x", padx=PADDING["medium"], pady=PADDING["small"]
        )

        # Context text
        ctk.CTkLabel(self, text="Context:", font=FONTS["body"]).pack(
            anchor="w", padx=PADDING["medium"]
        )

        # Text box for context
        self.context_text = ctk.CTkTextbox(
            self, font=FONTS["mono"], wrap="word", height=200
        )
        self.context_text.pack(
            fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["small"]
        )

        # Figures section
        self.figures_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.figures_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        self.figures_header = ctk.CTkLabel(
            self.figures_frame, text="Figures (0):", font=FONTS["body"]
        )
        self.figures_header.pack(anchor="w")

        # Thumbnail gallery frame
        self.thumbnail_frame = ctk.CTkFrame(self.figures_frame, fg_color="transparent")
        self.thumbnail_frame.pack(fill="x", pady=PADDING["small"])

        # Caption display
        self.caption_label = ctk.CTkLabel(
            self.figures_frame,
            text="",
            font=FONTS["small"],
            text_color="gray",
            wraplength=350,
            anchor="w",
        )
        self.caption_label.pack(fill="x")

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])

        self.open_btn = ctk.CTkButton(
            btn_frame,
            text="Open PDF",
            command=self._open_pdf,
            width=100,
            font=FONTS["body"],
            state="disabled",
        )
        self.open_btn.pack(side="left", padx=(0, PADDING["small"]))

        self.copy_btn = ctk.CTkButton(
            btn_frame,
            text="Copy Reference",
            command=self._copy_reference,
            width=120,
            font=FONTS["body"],
            state="disabled",
        )
        self.copy_btn.pack(side="left")

    def show_result(self, result: SearchResult):
        """Display a search result in the preview panel."""
        self.current_result = result

        # Check if this is a Deep-DX synthesis result
        extra_data = getattr(result, "extra_data", {})
        is_synthesis = extra_data.get("is_synthesis", False)

        # Reset UI
        self.safety_frame.pack_forget()
        self.confidence_label.pack_forget()
        self.location_label.configure(text="")

        if is_synthesis:
            # --- DEEP-DX VIEW ---
            self.book_label.configure(text="Source: Deep-DX Engine")
            self.chapter_label.configure(text="Synthesized Answer")
            self.page_label.configure(text="AI Generated")

            # Show Confidence
            conf = extra_data.get("confidence", 0.0)
            self.confidence_label.configure(
                text=f"Confidence Score: {int(conf*100)}%",
                text_color="#27ae60" if conf > 0.7 else "#e67e22",
            )
            self.confidence_label.pack(anchor="w")

            # Show Safety Warnings
            warnings = extra_data.get("critic_warnings", [])
            if warnings:
                warning_text = "⚠️ SAFETY WARNING:\n• " + "\n• ".join(warnings)
                self.safety_label.configure(text=warning_text)
                self.safety_frame.pack(
                    fill="x",
                    padx=PADDING["medium"],
                    pady=PADDING["small"],
                    before=self.metadata_frame,
                )

            # Show Answer Content
            self.context_text.configure(state="normal")
            self.context_text.delete("1.0", "end")
            self.context_text.insert("1.0", result.context)  # The answer

            # Append Citations
            citations = extra_data.get("citations", [])
            if citations:
                self.context_text.insert("end", "\n\n📚 SOURCES:\n")
                for c in citations:
                    ref = f"• {c['file_name']} (Page {c['page_number']})\n"
                    self.context_text.insert("end", ref)

            self.context_text.configure(state="disabled")

            # Disable PDF buttons for synthesis
            self.open_btn.configure(state="disabled")
            self.copy_btn.configure(state="normal")

            # Hide figures for synthesis (for now)
            self._clear_thumbnails()
            self.figures_header.configure(text="Figures (N/A):")

        else:
            # --- STANDARD VIEW ---
            display_series = config.KNOWN_SERIES.get(
                result.book_series, result.book_series
            )
            self.book_label.configure(text=f"Book: {display_series}")
            self.chapter_label.configure(text=f"Chapter: {result.display_name}")
            self.page_label.configure(text=f"Page: {result.page_number}")

            # Update match location info
            match_count = getattr(result, "match_count", 1)
            location_icon = getattr(result, "location_icon", "📄")
            match_summary = getattr(result, "match_summary", "")
            if match_summary:
                self.location_label.configure(text=f"{location_icon} {match_summary}")
            else:
                self.location_label.configure(text="")

            # Update context text
            self.context_text.configure(state="normal")
            self.context_text.delete("1.0", "end")

            # Highlight the search term in context
            context = result.context
            self.context_text.insert("1.0", context)
            self.context_text.configure(state="disabled")

            # Load and display figures for this page
            self._load_figures(result)

            # Enable buttons
            self.open_btn.configure(state="normal")
            self.copy_btn.configure(state="normal")

    def _load_figures(self, result: SearchResult):
        """Load figures for the current result's page."""
        # Clear existing thumbnails
        self._clear_thumbnails()

        if not self.database:
            self.figures_header.configure(text="Figures (N/A):")
            return

        # Get figures for this page
        try:
            figures = self.database.get_page_figures(
                result.pdf_path, result.page_number
            )
        except Exception as e:
            print(f"Error loading figures: {e}")
            figures = []

        self._current_figures = figures
        self.figures_header.configure(text=f"Figures ({len(figures)}):")

        if not figures:
            self.caption_label.configure(text="No figures on this page")
            return

        self.caption_label.configure(text="Hover over thumbnails to see captions")

        # Create thumbnails (limit display)
        for i, fig in enumerate(figures[:MAX_THUMBS_DISPLAY]):
            self._create_thumbnail(fig, i)

        # Show overflow indicator if needed
        if len(figures) > MAX_THUMBS_DISPLAY:
            overflow = len(figures) - MAX_THUMBS_DISPLAY
            overflow_label = ctk.CTkLabel(
                self.thumbnail_frame,
                text=f"+{overflow}",
                font=FONTS["body"],
                text_color="gray",
            )
            overflow_label.pack(side="left", padx=PADDING["small"])

    def _create_thumbnail(self, fig: dict, index: int):
        """Create a thumbnail widget for a figure."""
        image_path = fig.get("image_path")
        if not image_path or not Path(image_path).exists():
            return

        try:
            # Use cached thumbnail if available
            from ..utils.thumbnail_cache import get_thumbnail_cache

            thumb_cache = get_thumbnail_cache()
            thumb_path = thumb_cache.get_or_create_thumbnail(image_path, THUMB_SIZE)

            # Load from cache or original
            if thumb_path and thumb_path.exists():
                img = Image.open(thumb_path)
            else:
                # Fallback to on-the-fly generation
                img = Image.open(image_path)
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            self._thumbnail_images.append(photo)  # Keep reference

            # Get border color based on image type
            img_type = fig.get("image_type", "unknown")
            border_color = config.IMAGE_TYPE_COLORS.get(img_type, "#95a5a6")

            # Create thumbnail container with border
            thumb_container = ctk.CTkFrame(
                self.thumbnail_frame, fg_color=border_color, corner_radius=4
            )
            thumb_container.pack(side="left", padx=2, pady=2)

            # Create label with image
            thumb_label = ctk.CTkLabel(
                thumb_container,
                image=photo,
                text="",
                width=THUMB_SIZE[0] + 4,
                height=THUMB_SIZE[1] + 4,
            )
            thumb_label.pack(padx=2, pady=2)

            # Bind events
            thumb_label.bind("<Enter>", lambda e, f=fig: self._on_thumb_hover(f))
            thumb_label.bind("<Leave>", lambda e: self._on_thumb_leave())
            thumb_label.bind("<Button-1>", lambda e, f=fig: self._on_thumb_click(f))

        except Exception as e:
            print(f"Error creating thumbnail: {e}")

    def _clear_thumbnails(self):
        """Clear all thumbnail widgets."""
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self._thumbnail_images.clear()
        self._current_figures.clear()
        self.caption_label.configure(text="")

    def _on_thumb_hover(self, fig: dict):
        """Handle thumbnail hover - show caption."""
        caption = fig.get("caption", "")
        img_type = fig.get("image_type", "unknown")

        if caption:
            display_text = f"[{img_type}] {caption[:150]}..."
        else:
            display_text = f"[{img_type}] No caption"

        self.caption_label.configure(text=display_text)

    def _on_thumb_leave(self):
        """Handle thumbnail hover leave."""
        if self._current_figures:
            self.caption_label.configure(text="Hover over thumbnails to see captions")
        else:
            self.caption_label.configure(text="")

    def _on_thumb_click(self, fig: dict):
        """Handle thumbnail click - open full image."""
        image_path = fig.get("image_path")
        if not image_path or not Path(image_path).exists():
            return

        # Open with system default image viewer
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", image_path])
        elif sys.platform == "win32":  # Windows
            import os

            os.startfile(image_path)
        else:  # Linux
            subprocess.run(["xdg-open", image_path])

    def clear(self):
        """Clear the preview panel."""
        self.current_result = None
        self.book_label.configure(text="Book: -")
        self.chapter_label.configure(text="Chapter: -")
        self.page_label.configure(text="Page: -")
        self.location_label.configure(text="")
        self.context_text.configure(state="normal")
        self.context_text.delete("1.0", "end")
        self.context_text.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.copy_btn.configure(state="disabled")

        # Clear thumbnails
        self._clear_thumbnails()
        self.figures_header.configure(text="Figures (0):")

    def _open_pdf(self):
        """Open the PDF at the specific page."""
        if not self.current_result:
            return

        pdf_path = self.current_result.pdf_path

        if not pdf_path.exists():
            self.caption_label.configure(
                text=f"Error: PDF not found at {pdf_path}", text_color="red"
            )
            return

        try:
            if sys.platform == "darwin":  # macOS
                # Open with Preview at specific page
                subprocess.run(["open", "-a", "Preview", str(pdf_path)])
            elif sys.platform == "win32":  # Windows
                import os

                os.startfile(str(pdf_path))
            else:  # Linux
                subprocess.run(["xdg-open", str(pdf_path)])
        except Exception as e:
            self.caption_label.configure(
                text=f"Error opening PDF: {e}", text_color="red"
            )

    def _copy_reference(self):
        """Copy citation reference to clipboard."""
        if not self.current_result:
            return

        reference = self.current_result.reference
        self.clipboard_clear()
        self.clipboard_append(reference)

        # Visual feedback
        original_text = self.copy_btn.cget("text")
        self.copy_btn.configure(text="Copied!")
        self.after(1500, lambda: self.copy_btn.configure(text=original_text))
