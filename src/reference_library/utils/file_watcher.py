"""File system watcher for detecting new PDFs in the library."""

import threading
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from reference_library import config


class PDFEventHandler(FileSystemEventHandler):
    """Handle file system events for PDF files."""

    def __init__(
        self,
        on_new_file: Callable[[Path], None],
        on_modified_file: Callable[[Path], None],
        on_deleted_file: Callable[[Path], None],
    ):
        super().__init__()
        self.on_new_file = on_new_file
        self.on_modified_file = on_modified_file
        self.on_deleted_file = on_deleted_file

    def _is_pdf(self, path: str) -> bool:
        """Check if path is a PDF file."""
        return path.lower().endswith(".pdf")

    def on_created(self, event):
        """Handle file creation event."""
        if not event.is_directory and self._is_pdf(event.src_path):
            self.on_new_file(Path(event.src_path))

    def on_modified(self, event):
        """Handle file modification event."""
        if not event.is_directory and self._is_pdf(event.src_path):
            self.on_modified_file(Path(event.src_path))

    def on_deleted(self, event):
        """Handle file deletion event."""
        if not event.is_directory and self._is_pdf(event.src_path):
            self.on_deleted_file(Path(event.src_path))


class FileWatcher:
    """Watch library folder for new/changed PDF files."""

    def __init__(
        self,
        library_path: Path,
        on_new_file: Optional[Callable[[Path], None]] = None,
        on_modified_file: Optional[Callable[[Path], None]] = None,
        on_deleted_file: Optional[Callable[[Path], None]] = None,
    ):
        self.library_path = library_path
        self.on_new_file = on_new_file or (lambda p: None)
        self.on_modified_file = on_modified_file or (lambda p: None)
        self.on_deleted_file = on_deleted_file or (lambda p: None)

        self._observer: Optional[Observer] = None
        self._running = False

    def start(self):
        """Start watching the library folder."""
        if self._running:
            return

        self._observer = Observer()
        event_handler = PDFEventHandler(
            on_new_file=self._handle_new_file,
            on_modified_file=self._handle_modified_file,
            on_deleted_file=self._handle_deleted_file,
        )

        # Watch recursively
        self._observer.schedule(event_handler, str(self.library_path), recursive=True)

        self._observer.start()
        self._running = True
        print(f"FileWatcher: Monitoring {self.library_path}")

    def stop(self):
        """Stop watching."""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._running = False
            print("FileWatcher: Stopped")

    def _handle_new_file(self, path: Path):
        """Handle new file detected."""
        print(f"FileWatcher: New PDF detected - {path.name}")
        self.on_new_file(path)

    def _handle_modified_file(self, path: Path):
        """Handle modified file detected."""
        print(f"FileWatcher: PDF modified - {path.name}")
        self.on_modified_file(path)

    def _handle_deleted_file(self, path: Path):
        """Handle deleted file detected."""
        print(f"FileWatcher: PDF deleted - {path.name}")
        self.on_deleted_file(path)

    @property
    def is_running(self) -> bool:
        return self._running
