"""Main application window for the Neurosurgery Reference Library."""
import customtkinter as ctk
from pathlib import Path
import threading
from typing import Optional
import asyncio

from reference_library import config
from ..cache.database import Database
from ..search.pdf_searcher import PDFSearcher
from ..search.result_model import SearchResult, SearchProgress, ChapterResult
from ..search.master_index import get_master_index

from ..utils.library_scanner import LibraryScanner
from ..utils.file_watcher import FileWatcher
from ..integration.neurosynth_bridge import NeuroSynthBridge
from .search_panel import SearchPanel
from .results_tree import ResultsTree
from .rich_results_tree import RichResultsTree
from .preview_panel import PreviewPanel
from .new_files_panel import NewFilesPanel
from .synthesis_dialog import SynthesisDialog
from .analytics_dialog import AnalyticsDialog
from .styles import FONTS, PADDING


class NeurosurgeryLibraryApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Neurosurgery Reference Library")
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")

        # Set appearance mode
        ctk.set_appearance_mode(config.APPEARANCE_MODE)
        ctk.set_default_color_theme("blue")

        # Initialize components
        self.database = Database(config.DATABASE_PATH)
        self.searcher = PDFSearcher(config.LIBRARY_PATH, self.database)
        self.semantic_searcher = self.searcher.semantic  # Reference to SemanticSearcher for indexing

        self.scanner = LibraryScanner(config.LIBRARY_PATH, self.database)
        self.file_watcher: Optional[FileWatcher] = None
        self.neurosynth = NeuroSynthBridge(
            neurosynth_path=config.NEUROSYNTH_PATH,
            neurosynth_venv=config.NEUROSYNTH_VENV,
            database=self.database
        )

        # State
        self.current_query = ""
        self.search_thread: Optional[threading.Thread] = None
        self.extraction_thread: Optional[threading.Thread] = None

        self.pending_results: list[SearchResult] = []
        self.selected_results: list[SearchResult | ChapterResult] = []

        # Batch and throttle settings
        self.RESULT_BATCH_SIZE = 50


        # Set up UI
        self._setup_ui()
        self._setup_menu()

        # Check library (don't auto-sync on startup - user clicks Rescan)
        self._verify_library()
        self._start_file_watcher()

        # Show ready status
        self._show_status("Ready. Click 🔄 Rescan to index library.")

        # Clean up on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        """Set up the main UI layout."""
        # Search panel at top
        self.search_panel = SearchPanel(
            self,
            on_search=self._start_search,
            on_cancel=self._cancel_search,
            database=self.database
        )
        self.search_panel.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        # Main content area with three columns
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=PADDING["small"])

        # New Files panel (left sidebar) - collapsible
        self.new_files_panel = NewFilesPanel(
            content_frame,
            on_index_file=self._index_single_file,
            on_index_all=self._index_all_new_files
        )
        self.new_files_panel.pack(side="left", fill="y", padx=(0, PADDING["small"]))
        self.new_files_panel.configure(width=280)

        # Results tree (center) - Use RichResultsTree for inline thumbnails and expandable context
        # Set use_rich_tree=True to enable rich preview mode
        use_rich_tree = config.USE_RICH_RESULTS_TREE if hasattr(config, 'USE_RICH_RESULTS_TREE') else True

        if use_rich_tree:
            self.results_tree = RichResultsTree(
                content_frame,
                on_select=self._on_result_select,
                on_selection_change=self._on_selection_change,
                on_extract_images=self._extract_images_from_result,
                on_index_text=self._index_text_from_result,
                database=self.database
            )
        else:
            self.results_tree = ResultsTree(
                content_frame,
                on_select=self._on_result_select,
                on_selection_change=self._on_selection_change,
                on_extract_images=self._extract_images_from_result,
                on_index_text=self._index_text_from_result,
                database=self.database
            )
        self.results_tree.pack(side="left", fill="both", expand=True, padx=(0, PADDING["small"]))

        # Preview panel (right)
        self.preview_panel = PreviewPanel(content_frame, database=self.database)
        self.preview_panel.pack(side="right", fill="both", expand=False, ipadx=PADDING["medium"])
        self.preview_panel.configure(width=400)

        # Status bar at bottom
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(fill="x", side="bottom", padx=PADDING["small"], pady=PADDING["small"])

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            font=FONTS["small"],
            anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.progress_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=FONTS["small"]
        )
        self.progress_label.pack(side="right")

        # Synthesis progress bar (hidden by default)
        self.synthesis_progress = ctk.CTkProgressBar(
            self.status_frame,
            width=150,
            height=12,
            mode="indeterminate"
        )
        # Don't pack yet - shown only during synthesis

        # Export button in status bar
        self.export_btn = ctk.CTkButton(
            self.status_frame,
            text="Export Index",
            command=self._export_index,
            width=100,
            height=24,
            font=FONTS["small"],
            state="disabled"
        )
        self.export_btn.pack(side="right", padx=PADDING["small"])

        # Synthesize button (NeuroSynth integration)
        self.synthesize_btn = ctk.CTkButton(
            self.status_frame,
            text="Synthesize Chapter",
            command=self._synthesize_chapter,
            width=130,
            height=24,
            font=FONTS["small"],
            state="disabled",
            fg_color="#27ae60",
            hover_color="#219a52"
        )
        self.synthesize_btn.pack(side="right", padx=PADDING["small"])



        # Smart selection dropdown
        self.smart_select_var = ctk.StringVar(value="Smart Select")
        self.smart_select_menu = ctk.CTkOptionMenu(
            self.status_frame,
            values=["Balanced", "High Confidence", "Diverse"],
            command=self._on_smart_select,
            variable=self.smart_select_var,
            width=120,
            height=24,
            font=FONTS["small"],
            fg_color="#3498db",
            button_color="#2980b9",
            button_hover_color="#1a5276"
        )
        self.smart_select_menu.pack(side="right", padx=PADDING["small"])
        self.smart_select_menu.set("Smart Select")

        # Build Semantic Index button (text only, fast)
        self.index_btn = ctk.CTkButton(
            self.status_frame,
            text="Index Text",
            command=self._build_semantic_index,
            width=90,
            height=24,
            font=FONTS["small"],
            fg_color="#9b59b6",
            hover_color="#8e44ad"
        )
        self.index_btn.pack(side="right", padx=PADDING["small"])

        # Extract Figures button (separate, slower)
        self.extract_btn = ctk.CTkButton(
            self.status_frame,
            text="Extract Figures",
            command=self._extract_figures_slow,
            width=100,
            height=24,
            font=FONTS["small"],
            fg_color="#e67e22",
            hover_color="#d35400"
        )
        self.extract_btn.pack(side="right", padx=PADDING["small"])

        # Analytics button
        self.analytics_btn = ctk.CTkButton(
            self.status_frame,
            text="📊",
            command=self._show_analytics,
            width=40,
            height=24,
            font=FONTS["small"],
            fg_color="#34495e",
            hover_color="#2c3e50"
        )
        self.analytics_btn.pack(side="right", padx=PADDING["small"])

        # Sync Library button
        self.sync_btn = ctk.CTkButton(
            self.status_frame,
            text="🔄 Rescan",
            command=lambda: self._sync_library(force=True),
            width=80,
            height=24,
            font=FONTS["small"],
            fg_color="#3498db",
            hover_color="#2980b9"
        )
        self.sync_btn.pack(side="right", padx=PADDING["small"])

        # Library Settings button (⚙️)
        self.settings_btn = ctk.CTkButton(
            self.status_frame,
            text="⚙️ Library",
            command=self._show_library_info,
            width=80,
            height=24,
            font=FONTS["small"],
            fg_color="#34495e",
            hover_color="#2c3e50"
        )
        self.settings_btn.pack(side="right", padx=PADDING["small"])

    def _setup_menu(self):
        """Set up the application menu."""
        import tkinter as tk

        # Create native macOS menu
        menubar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Change Library...", command=self._change_library)
        file_menu.add_command(label="Show Library Info", command=self._show_library_info)
        file_menu.add_separator()
        file_menu.add_command(label="Lock Library Path", command=self._lock_library)
        file_menu.add_command(label="Unlock Library Path", command=self._unlock_library)
        file_menu.add_separator()
        file_menu.add_command(label="Refresh Library", command=self._sync_library)
        menubar.add_cascade(label="File", menu=file_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Show New Files Panel", command=lambda: self.new_files_panel.pack(side="left", fill="y", padx=(0, 5)))
        menubar.add_cascade(label="View", menu=view_menu)

        self.config(menu=menubar)

    def _change_library(self):
        """Change the library path."""
        from tkinter import messagebox

        # Confirm if locked
        if config.is_library_locked():
            if not messagebox.askyesno(
                "Library Locked",
                f"Current library is locked to:\n{config.LIBRARY_PATH}\n\n"
                "Do you want to change it anyway?"
            ):
                return

        # Prompt for new path
        new_path = config.prompt_for_library_path(lock=True)
        if new_path:
            # Restart required
            messagebox.showinfo(
                "Library Changed",
                f"Library changed to:\n{new_path}\n\n"
                "Please restart the application for changes to take effect."
            )

    def _show_library_info(self):
        """Show information about the current library."""
        from tkinter import messagebox

        # Count PDFs
        pdfs = self.scanner.get_all_pdfs()
        pdf_count = len(pdfs)

        # Check if locked
        locked_status = "🔒 Locked" if config.is_library_locked() else "🔓 Unlocked"

        # Get tracked/indexed counts from database
        tracked = len(self.database.get_all_tracked_paths())

        messagebox.showinfo(
            "Library Information",
            f"📁 Library Path:\n{config.LIBRARY_PATH}\n\n"
            f"📊 Status: {locked_status}\n\n"
            f"📚 PDFs in folder: {pdf_count}\n"
            f"📑 PDFs indexed: {tracked}\n\n"
            f"Expected folder structure:\n"
            f"  📁 Book chapters/\n"
            f"    📁 Series folders...\n"
            f"  📁 Entire books/"
        )

    def _lock_library(self):
        """Lock the current library path."""
        config.lock_library_path(config.LIBRARY_PATH)
        self._show_status(f"Library locked to: {config.LIBRARY_PATH}", "success")

    def _unlock_library(self):
        """Unlock the library path."""
        config.unlock_library_path()
        self._show_status("Library unlocked - will prompt on next restart", "info")

    def _verify_library(self):
        """Verify the reference library exists."""
        if not config.LIBRARY_PATH.exists():
            self._show_status(
                f"Library not found at: {config.LIBRARY_PATH}",
                "error"
            )
        else:
            # Use database count (fast) instead of filesystem scan (slow)
            tracked = len(self.database.get_all_tracked_paths())
            if tracked > 0:
                self._show_status(f"Library loaded: {tracked} PDFs indexed")
            else:
                self._show_status("Library found. Indexing...")

    def _start_search(self, query: str):
        """Start a search for the given query."""
        if not query:
            return

        # Cancel any existing search
        self._cancel_search()

        self.current_query = query
        self.pending_results = []

        # Clear previous results
        self.results_tree.clear()
        self.preview_panel.clear()

        # Get strategy from search panel
        strategy = self.search_panel.get_strategy()

        # Update UI state
        self.search_panel.set_searching(True)
        strategy_display = strategy.capitalize()
        self._show_status(f"Searching for '{query}' ({strategy_display})...")
        self.export_btn.configure(state="disabled")

        # Hide any previous related terms
        self.search_panel.hide_related_terms()

        # Start search in background thread
        self.search_thread = threading.Thread(
            target=self._search_thread,
            args=(query, strategy),
            daemon=True
        )
        self.search_thread.start()

    def _search_thread(self, query: str, strategy: str = "standard"):
        """Background thread for searching - uses chapter-level knowledge retrieval."""
        try:
            batch = []

            # Use chapter-level search for knowledge retrieval
            for chapter_result in self.searcher.search_library_chapters(
                query,
                strategy=strategy,
                progress_callback=self._on_search_progress
            ):
                batch.append(chapter_result)
                self.pending_results.append(chapter_result)

                # Send batch to UI when full
                if len(batch) >= self.RESULT_BATCH_SIZE:
                    self.after(0, self._add_chapter_results_batch, batch.copy())
                    batch.clear()

            # Send remaining results
            if batch:
                self.after(0, self._add_chapter_results_batch, batch)

            # Search complete
            self.after(0, self._on_search_complete)

        except Exception as e:
            error_msg = f"Search error: {e}"
            self.after(0, lambda msg=error_msg: self._show_status(msg, "error"))
            self.after(0, self._on_search_complete)

    def _on_search_progress(self, progress: SearchProgress):
        """Update progress display with on-demand extraction awareness.

        Shows two-phase progress:
        - Scanning: Quick metadata check of all PDFs
        - Candidates: PDFs that passed filter and are being processed
        """
        # Capture values by value to avoid threading race condition
        searched = progress.searched_pdfs
        total = progress.total_pdfs
        candidates = progress.candidates_processed
        matches = progress.total_matches
        phase = progress.phase

        if phase == "scanning":
            if candidates > 0:
                # Show candidates being processed
                text = f"Scanning {searched}/{total} | {candidates} candidates | {matches} matches"
            else:
                # Still in initial scan phase
                text = f"Scanning {searched}/{total} PDFs..."
        else:
            # Search complete
            text = f"Processed {candidates} of {total} PDFs | {matches} matches"

        self.after(0, lambda t=text: self.progress_label.configure(text=t))

    def _add_results_batch(self, results: list):
        """Add a batch of page-level results to the tree (called from main thread)."""
        for result in results:
            self.results_tree.add_result(result)

    def _add_chapter_results_batch(self, results: list):
        """Add a batch of chapter-level results to the tree (called from main thread)."""
        for chapter_result in results:
            self.results_tree.add_chapter_result(chapter_result)

    def _on_search_complete(self):
        """Handle search completion."""
        self.search_panel.set_searching(False)

        # Count both page-level and chapter-level results
        page_count = len(self.results_tree.results)
        chapter_count = len(self.results_tree.chapter_results)
        result_count = page_count + chapter_count

        # Show appropriate message based on result type
        if chapter_count > 0:
            dedicated = sum(1 for c in self.results_tree.chapter_results.values()
                          if c.match_type.name == "DEDICATED_CHAPTER")
            if dedicated > 0:
                self._show_status(f"Found {chapter_count} chapters ({dedicated} dedicated to topic)")
            else:
                self._show_status(f"Found {chapter_count} chapters with references")
        else:
            self._show_status(f"Search complete: {result_count} matches found")

        if result_count > 0:
            self.export_btn.configure(state="normal")

        # Show related terms suggestions (especially useful when few results)
        if result_count < 10 and self.current_query:
            try:
                master_index = get_master_index()
                related_terms = master_index.get_related_terms(self.current_query, max_terms=5)
                if related_terms:
                    self.search_panel.show_related_terms(related_terms)
            except Exception:
                pass  # Don't fail if related terms lookup fails

        # Save to search history
        search_strategy = self.search_panel.get_strategy()
        self.database.save_search_history(
            self.current_query,
            result_count,
            search_mode=search_strategy  # Use strategy name instead of removed mode
        )

    def _cancel_search(self):
        """Cancel the current search."""
        self.searcher.cancel()
        self.search_panel.set_searching(False)
        self._show_status("Search cancelled")

    def _cancel_extraction(self):
        """Cancel the current extraction."""
        self.scanner.cancel_extraction()
        self.extract_btn.configure(state="normal", text="Extract Figures")
        self._show_status("Extraction cancelled")

    def _on_result_select(self, result: SearchResult):
        """Handle result selection in tree."""
        self.preview_panel.show_result(result)



    def _export_index(self):
        """Export search results as index."""
        from ..export.html_exporter import HTMLExporter
        from ..export.pdf_exporter import PDFExporter

        results = self.results_tree.get_all_results()
        if not results:
            return

        # Ask for save location
        from tkinter import filedialog

        save_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[
                ("HTML files", "*.html"),
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ],
            initialfile=f"index_{self.current_query.replace(' ', '_')}"
        )

        if not save_path:
            return

        save_path = Path(save_path)

        try:
            if save_path.suffix.lower() == ".pdf":
                exporter = PDFExporter()
                exporter.export(results, self.current_query, save_path)
            else:
                exporter = HTMLExporter()
                exporter.export(results, self.current_query, save_path)

            self._show_status(f"Exported to {save_path.name}")

            # Also export the other format
            if save_path.suffix.lower() == ".html":
                pdf_path = save_path.with_suffix(".pdf")
                pdf_exporter = PDFExporter()
                pdf_exporter.export(results, self.current_query, pdf_path)
            else:
                html_path = save_path.with_suffix(".html")
                html_exporter = HTMLExporter()
                html_exporter.export(results, self.current_query, html_path)

        except Exception as e:
            self._show_status(f"Export error: {e}", "error")

    def _show_status(self, message: str, level: str = "info"):
        """Show status message."""
        self.status_label.configure(text=message)

        # Color based on level
        colors = {
            "info": ("gray", None),
            "success": ("#27ae60", None),
            "warning": ("#f39c12", None),
            "error": ("#e74c3c", None)
        }
        text_color, bg_color = colors.get(level, colors["info"])
        self.status_label.configure(text_color=text_color)

    def _show_synthesis_progress(self, visible: bool):
        """Show or hide the synthesis progress bar."""
        if visible:
            self.synthesis_progress.pack(side="right", padx=PADDING["small"])
            self.synthesis_progress.start()
        else:
            self.synthesis_progress.stop()
            self.synthesis_progress.pack_forget()

    # Auto-Update Methods

    def _sync_library(self, force: bool = False):
        """Sync library on startup to detect new files."""
        def _do_sync():
            try:
                # Progress callback for real-time updates
                def on_progress(current: int, total: int):
                    self.after(0, lambda c=current, t=total: self._show_status(
                        f"Scanning library: {c}/{t} PDFs processed"
                    ))

                result = self.scanner.sync_library(
                    max_workers=8,
                    progress_callback=on_progress,
                    force=force
                )
                self.after(0, lambda: self._on_sync_complete(result))
            except Exception as e:
                self.after(0, lambda: self._show_status(f"Sync error: {e}", "error"))

        thread = threading.Thread(target=_do_sync, daemon=True)
        thread.start()

    def _on_sync_complete(self, result: dict):
        """Handle library sync completion."""
        unindexed = self.database.get_unindexed_files()
        self.new_files_panel.load_from_database(unindexed)

        if result['new_files'] > 0:
            self._show_status(
                f"Library synced: {result['new_files']} new files detected",
                "success"
            )
        else:
            self._show_status(f"Library synced: {result['total_files']} files")

    def _start_file_watcher(self):
        """Start watching for new files."""
        if not config.LIBRARY_PATH.exists():
            return

        self.file_watcher = FileWatcher(
            library_path=config.LIBRARY_PATH,
            on_new_file=self._on_new_file_detected,
            on_modified_file=self._on_file_modified,
            on_deleted_file=self._on_file_deleted
        )
        self.file_watcher.start()

    def _on_new_file_detected(self, pdf_path: Path):
        """Handle new file detected by watcher."""
        def _process():
            try:
                metadata = self.scanner.get_pdf_metadata(pdf_path)
                checksum = self.database.get_file_checksum(pdf_path)
                self.database.track_file(
                    pdf_path,
                    checksum=checksum,
                    file_size=pdf_path.stat().st_size,
                    book_series=metadata.book_series,
                    chapter_title=metadata.chapter_title,
                    page_count=metadata.page_count
                )
                # Update UI
                self.after(0, lambda: self.new_files_panel.add_file(
                    pdf_path,
                    book_series=metadata.book_series,
                    chapter_title=metadata.chapter_title,
                    page_count=metadata.page_count
                ))
                self.after(0, lambda: self._show_status(
                    f"New file detected: {pdf_path.name}",
                    "success"
                ))
            except Exception as e:
                print(f"Error processing new file: {e}")

        threading.Thread(target=_process, daemon=True).start()

    def _on_file_modified(self, pdf_path: Path):
        """Handle file modification."""
        # Re-process the file
        self._on_new_file_detected(pdf_path)

    def _on_file_deleted(self, pdf_path: Path):
        """Handle file deletion."""
        self.database.remove_tracked_file(pdf_path)
        self.after(0, lambda: self.new_files_panel.remove_file(pdf_path))

    def _index_single_file(self, pdf_path: Path):
        """Index a single new file (make it searchable)."""
        self.database.mark_file_indexed(pdf_path)
        self._show_status(f"Indexed: {pdf_path.name}", "success")

    def _index_all_new_files(self):
        """Index all new files."""
        unindexed = self.database.get_unindexed_files()
        for file_info in unindexed:
            pdf_path = Path(file_info['pdf_path'])
            self.database.mark_file_indexed(pdf_path)

        count = len(unindexed)
        self._show_status(f"Indexed {count} new files", "success")

    def _on_close(self):
        """Clean up on window close."""
        if self.file_watcher:
            self.file_watcher.stop()
        self.destroy()

    # Semantic Index Methods

    def _build_semantic_index(self):
        """Build semantic search index (text only)."""
        self.index_btn.configure(state="disabled", text="Indexing...")
        self._show_status("Building text index...")

        def _do_index():
            import time

            def text_progress(current, total):
                self.after(0, lambda c=current, t=total: self._show_status(
                    f"Text indexing: {c}/{t} PDFs"
                ))
                # Yield to UI thread every PDF to prevent freezing
                time.sleep(0.01)

            # Use sequential indexing (runs in background thread to keep UI responsive)
            text_count = self.searcher.index_library_semantic(progress_callback=text_progress)
            self.after(0, lambda: self._on_text_index_complete(text_count))

        threading.Thread(target=_do_index, daemon=True).start()

    def _on_text_index_complete(self, text_count: int):
        """Handle text indexing completion."""
        self.index_btn.configure(state="normal", text="Index Text")
        self._show_status(f"Text indexed: {text_count} pages", "success")

    def _extract_figures_slow(self):
        """Extract figures from PDFs in parallel (4 concurrent)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from ..utils.neurosynth_imports import NEUROSYNTH_AVAILABLE

        if not NEUROSYNTH_AVAILABLE:
            self._show_status("Figure extraction unavailable (install NeuroSynth dependencies)", "error")
            return

        # Reset cancellation flag for new extraction
        self.scanner.reset_extraction()

        self.extract_btn.configure(state="disabled", text="Extracting...")
        self._show_status("Starting parallel figure extraction...")

        def _do_extract():
            from pathlib import Path

            # Get all PDFs
            pdfs = list(config.LIBRARY_PATH.rglob("*.pdf"))
            total = len(pdfs)
            total_figures = 0
            processed = 0

            # Worker function for each PDF
            def extract_single_pdf(pdf_path: Path) -> tuple[Path, int]:
                try:
                    figures = self.scanner.extract_figures(pdf_path, force=False)
                    return (pdf_path, len(figures))
                except Exception as e:
                    print(f"Error extracting from {pdf_path.name}: {e}")
                    return (pdf_path, 0)

            # Parallel extraction with ThreadPoolExecutor (4 workers)
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit all tasks
                future_to_path = {
                    executor.submit(extract_single_pdf, pdf): pdf
                    for pdf in pdfs
                }

                # Process results as they complete
                for future in as_completed(future_to_path):
                    # Check cancellation flag
                    if self.scanner._cancelled:
                        # Cancel all pending futures
                        for f in future_to_path:
                            f.cancel()
                        self.after(0, lambda: self._show_status("Extraction cancelled", "warning"))
                        self.after(0, lambda: self.extract_btn.configure(state="normal", text="Extract Figures"))
                        return  # Exit early

                    pdf_path, fig_count = future.result()
                    total_figures += fig_count
                    processed += 1

                    # Update progress
                    self.after(0, lambda p=pdf_path.name, idx=processed, t=total, fc=fig_count:
                        self._show_status(
                            f"Extracting {idx}/{t}: {p[:30]}... ({fc} figs)"
                        )
                    )

            self.after(0, lambda: self._on_extract_complete(total, total_figures))

        self.extraction_thread = threading.Thread(target=_do_extract, daemon=True)
        self.extraction_thread.start()

    def _on_extract_complete(self, pdfs_processed: int, figures_extracted: int):
        """Handle figure extraction completion."""
        self.extract_btn.configure(state="normal", text="Extract Figures")
        self._show_status(f"Extracted {figures_extracted} figures from {pdfs_processed} PDFs", "success")

    def _extract_images_from_result(self, result: SearchResult):
        """Extract images from a single PDF (context menu action)."""
        from ..utils.neurosynth_imports import NEUROSYNTH_AVAILABLE
        if not NEUROSYNTH_AVAILABLE:
            self._show_status("Extraction unavailable (missing dependencies)", "error")
            return

        pdf_path = result.pdf_path
        self._show_status(f"Extracting images from {pdf_path.name}...")

        def _do_single_extract():
            try:
                figures = self.scanner.extract_figures(pdf_path, force=True)
                count = len(figures)
                self.after(0, lambda: self._show_status(
                    f"Extracted {count} figures from {pdf_path.name}", 
                    "success" if count > 0 else "info"
                ))
                # Refresh tree to show new figure count
                self.after(0, lambda: self.results_tree.update())
            except Exception as e:
                self.after(0, lambda: self._show_status(f"Extraction error: {e}", "error"))

        threading.Thread(target=_do_single_extract, daemon=True).start()

    def _index_text_from_result(self, result: SearchResult):
        """Index text for a single PDF (context menu action)."""
        pdf_path = result.pdf_path
        self._show_status(f"Indexing text for {pdf_path.name}...")

        def _do_single_index():
            try:
                pages = self.searcher.index_pdf_semantic(pdf_path)
                self.after(0, lambda: self._show_status(
                    f"Indexed {pages} pages from {pdf_path.name}", 
                    "success" if pages > 0 else "info"
                ))
            except Exception as e:
                self.after(0, lambda: self._show_status(f"Indexing error: {e}", "error"))

        threading.Thread(target=_do_single_index, daemon=True).start()

    def _on_index_complete(self, text_count: int, figure_stats: dict = None, captions_indexed: int = 0, extraction_warning: str = None):
        """Handle semantic indexing completion (legacy, kept for compatibility)."""
        self.index_btn.configure(state="normal", text="Index Text")

        # Build status message
        msg = f"Index built: {text_count} pages"
        status_type = "success"

        if figure_stats and figure_stats.get("total_figures", 0) > 0:
            total_figs = figure_stats.get("total_figures", 0)
            msg += f", {total_figs} figures"
            if captions_indexed > 0:
                msg += f" ({captions_indexed} captions indexed)"
        elif extraction_warning:
            msg += f" | {extraction_warning}"
            status_type = "warning"

        self._show_status(msg, status_type)

    # NeuroSynth Integration Methods

    def _convert_to_search_results(self, items: list[SearchResult | ChapterResult]) -> list[SearchResult]:
        """Convert mixed results to SearchResult list for synthesis compatibility."""
        search_results = []
        for item in items:
            if isinstance(item, SearchResult):
                search_results.append(item)
            elif isinstance(item, ChapterResult):
                # Convert ChapterResult to SearchResult
                first_page = item.matched_pages[0] if item.matched_pages else 1
                search_result = SearchResult(
                    pdf_path=item.pdf_path,
                    book_series=item.book_series,
                    book_title=item.book_title,
                    chapter_number=item.chapter_number,
                    chapter_title=item.chapter_title,
                    page_number=first_page,
                    match_text=f"[{item.match_type.display_name}]",  # Use display_name
                    context=item.preview_context or "",
                    match_count=item.total_occurrences,
                    is_title_match=item.is_dedicated,
                    relevance_score=item.relevance_score
                )
                search_results.append(search_result)
        return search_results

    def _on_selection_change(self, selected_results: list[SearchResult | ChapterResult]):
        """Handle selection change in results tree."""
        self.selected_results = selected_results

        # Enable/disable synthesize button based on selection
        if selected_results:
            self.synthesize_btn.configure(state="normal")
        else:
            self.synthesize_btn.configure(state="disabled")


    def _on_smart_select(self, choice: str):
        """Handle smart selection dropdown choice."""
        if choice == "Balanced":
            self.results_tree.smart_select_balanced(target_per_group=6)
            self._show_status("Auto-selected balanced results (6 per book)", "success")
        elif choice == "High Confidence":
            self.results_tree.smart_select_high_confidence(threshold=0.8)
            self._show_status("Selected high-confidence results (>=80%)", "success")
        elif choice == "Diverse":
            self.results_tree.smart_select_diverse(max_per_source=3)
            self._show_status("Selected diverse sources (max 3 per book)", "success")

        # Reset the dropdown text
        self.smart_select_menu.set("Smart Select")

    def _synthesize_chapter(self):
        """Synthesize a chapter from selected results using NeuroSynth."""
        if not self.selected_results:
            self._show_status("No results selected for synthesis", "warning")
            return

        # Check if NeuroSynth is available
        available, version_or_error = self.neurosynth.check_available()
        if not available:
            self._show_status(f"NeuroSynth not available: {version_or_error}", "error")
            return

        # Use current query as default topic
        topic = self.current_query if self.current_query else "Neurosurgical Chapter"

        # Get selected results (mixed SearchResult and ChapterResult)
        # Pass original objects to preserve matched_pages for ChapterResult
        selected_results = self.results_tree.get_selected_results()

        # Get options from dialog (works with any list type)
        dialog = SynthesisDialog(
            self,
            initial_topic=topic,
            selected_results=selected_results  # Pass original mixed results
        )
        result = dialog.get_input()

        if not result:
            return

        topic, template_type = result

        # Disable button during synthesis and show progress bar
        self.synthesize_btn.configure(state="disabled")
        self._show_synthesis_progress(True)
        self._show_status(f"Starting synthesis for '{topic}'...")

        # Get search context
        search_query = self.current_query
        search_mode = self.search_panel.get_strategy()

        # Run synthesis in background - page_extractor handles both result types
        def _do_synthesis():
            result = self.neurosynth.synthesize(
                topic=topic,
                results=selected_results,  # Pass original (extractor handles ChapterResult)
                on_progress=lambda msg: self.after(0, lambda: self._show_status(msg)),
                search_query=search_query,
                search_mode=search_mode,
                template_type=template_type
            )

            self.after(0, lambda: self._on_synthesis_complete(result))

        thread = threading.Thread(target=_do_synthesis, daemon=True)
        thread.start()

    def _on_synthesis_complete(self, result):
        """Handle synthesis completion."""
        from ..integration.neurosynth_bridge import SynthesisResult

        # Hide progress bar and re-enable button
        self._show_synthesis_progress(False)
        if self.selected_results:
            self.synthesize_btn.configure(state="normal")

        if result.success:
            self._show_status(f"Chapter synthesized: {result.output_path.name}", "success")

            # Offer to open the file
            from tkinter import messagebox
            if messagebox.askyesno(
                "Synthesis Complete",
                f"Chapter saved to:\n{result.output_path}\n\nOpen the file now?"
            ):
                import subprocess
                subprocess.run(["open", str(result.output_path)])
        else:
            self._show_status(f"Synthesis failed: {result.error}", "error")
            if result.log:
                print(f"NeuroSynth log:\n{result.log}")

    def _show_analytics(self):
        """Show search analytics dialog."""
        AnalyticsDialog(self, self.database)


def run_app():
    """Run the application."""
    app = NeurosurgeryLibraryApp()
    app.mainloop()
