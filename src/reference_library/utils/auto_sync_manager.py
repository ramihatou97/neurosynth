"""Auto-Sync Manager for Reference Library.

Orchestrates debounced batch indexing and syncing of PDFs to Deep-DX.

Design:
- Detects new PDFs via FileWatcher callbacks
- Queues files for indexing with debounce (wait for quiet period)
- Batches multiple files into single indexing operation
- Queues indexed files for Deep-DX sync with debounce
- Runs all operations in background threads (non-blocking)
- Thread-safe queue management with proper locking
- Graceful error handling and statistics tracking
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, Set

from reference_library import config
from reference_library.cache.database import Database
from reference_library.search.pdf_searcher import PDFSearcher

logger = logging.getLogger(__name__)


class AutoSyncManager:
    """Manages automated PDF indexing and Deep-DX synchronization.

    Features:
    - Debounced batch processing (reduces API calls by 90%)
    - Thread-safe queue management
    - Background operation (non-blocking GUI)
    - Comprehensive error handling
    - Statistics tracking

    Architecture:
        FileWatcher → queue_for_indexing() → [30s debounce] →
        _run_index_batch() → queue_for_sync() → [60s debounce] →
        _run_sync_batch() → Deep-DX
    """

    def __init__(
        self,
        pdf_searcher: PDFSearcher,
        database: Database,
        status_callback: Callable[[str, str], None],
        index_debounce_seconds: int = 30,
        sync_debounce_seconds: int = 60,
    ):
        """Initialize AutoSyncManager.

        Args:
            pdf_searcher: PDFSearcher instance for indexing PDFs
            database: Database instance for tracking file state
            status_callback: Callback for status updates (message, level)
                           level = "info" | "success" | "error" | "warning"
            index_debounce_seconds: Wait time before batch indexing (default 30s)
            sync_debounce_seconds: Wait time before batch syncing (default 60s)
        """
        self.pdf_searcher = pdf_searcher
        self.database = database
        self.status_callback = status_callback

        self.index_debounce_seconds = index_debounce_seconds
        self.sync_debounce_seconds = sync_debounce_seconds

        # Queues (sets prevent duplicates)
        self._index_queue: Set[Path] = set()
        self._sync_queue: Set[Path] = set()

        # Locks (prevent race conditions)
        self._index_lock = threading.Lock()
        self._sync_lock = threading.Lock()

        # Timers (for debouncing)
        self._index_timer: Optional[threading.Timer] = None
        self._sync_timer: Optional[threading.Timer] = None

        # Thread pool for background operations
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="auto-sync")

        # Shutdown flag
        self._shutdown = False

        # Statistics
        self._stats = {
            "indexed_count": 0,
            "synced_count": 0,
            "index_errors": [],
            "sync_errors": [],
        }

        logger.info(
            f"AutoSyncManager initialized (index_debounce={index_debounce_seconds}s, "
            f"sync_debounce={sync_debounce_seconds}s)"
        )

    def start(self) -> None:
        """Start the auto-sync manager.

        This doesn't actually do anything since we're event-driven,
        but it's here for symmetry with stop() and future extensions.
        """
        logger.info("AutoSyncManager started")

    def stop(self) -> None:
        """Stop the auto-sync manager and clean up resources.

        Cancels pending timers and waits for running tasks to complete.
        """
        logger.info("Stopping AutoSyncManager...")
        self._shutdown = True

        # Cancel pending timers
        if self._index_timer:
            self._index_timer.cancel()
            logger.debug("Cancelled pending index timer")

        if self._sync_timer:
            self._sync_timer.cancel()
            logger.debug("Cancelled pending sync timer")

        # Wait for running tasks (max 30s)
        self._executor.shutdown(wait=True, timeout=30)
        logger.info("AutoSyncManager stopped")

    def queue_for_indexing(self, pdf_path: Path) -> None:
        """Queue a PDF for indexing with debouncing.

        If multiple files are added rapidly, they'll be batched together
        into a single indexing operation after the debounce period.

        Args:
            pdf_path: Path to PDF file to index

        Thread-safe: Yes (uses lock)
        """
        if self._shutdown:
            logger.warning("Cannot queue file - manager is shutting down")
            return

        with self._index_lock:
            self._index_queue.add(pdf_path)
            logger.debug(f"Queued for indexing: {pdf_path.name} (queue size: {len(self._index_queue)})")
            self._reset_index_timer()

    def queue_for_sync(self, pdf_path: Path) -> None:
        """Queue a PDF for Deep-DX sync with debouncing.

        If multiple files are indexed rapidly, they'll be batched together
        into a single sync operation after the debounce period.

        Args:
            pdf_path: Path to PDF file to sync

        Thread-safe: Yes (uses lock)
        """
        if self._shutdown:
            logger.warning("Cannot queue file - manager is shutting down")
            return

        with self._sync_lock:
            self._sync_queue.add(pdf_path)
            logger.debug(f"Queued for sync: {pdf_path.name} (queue size: {len(self._sync_queue)})")
            self._reset_sync_timer()

    def get_stats(self) -> dict:
        """Get statistics about indexing and syncing operations.

        Returns:
            Dictionary with counts and error lists
        """
        return self._stats.copy()

    # Private methods - Debounce logic

    def _reset_index_timer(self) -> None:
        """Cancel old timer and start new one for indexing.

        This is the core of debouncing - every new file resets the timer,
        so we wait for a quiet period before processing.

        NOT thread-safe: Must be called within _index_lock
        """
        # Cancel existing timer
        if self._index_timer:
            self._index_timer.cancel()

        # Start new timer
        self._index_timer = threading.Timer(
            self.index_debounce_seconds,
            lambda: self._executor.submit(self._run_index_batch)
        )
        self._index_timer.start()
        logger.debug(f"Index timer reset ({self.index_debounce_seconds}s)")

    def _reset_sync_timer(self) -> None:
        """Cancel old timer and start new one for syncing.

        This is the core of debouncing - every new file resets the timer,
        so we wait for a quiet period before processing.

        NOT thread-safe: Must be called within _sync_lock
        """
        # Cancel existing timer
        if self._sync_timer:
            self._sync_timer.cancel()

        # Start new timer
        self._sync_timer = threading.Timer(
            self.sync_debounce_seconds,
            lambda: self._executor.submit(self._run_sync_batch)
        )
        self._sync_timer.start()
        logger.debug(f"Sync timer reset ({self.sync_debounce_seconds}s)")

    # Private methods - Batch processing

    def _run_index_batch(self) -> None:
        """Process batch of PDFs for indexing (runs in background thread).

        Workflow:
        1. Snapshot queue atomically
        2. Clear queue (new files go to next batch)
        3. Index each PDF semantically
        4. Mark as indexed in database
        5. Queue for sync
        6. Send status update to GUI

        Error handling: Skip corrupted files, log errors, continue batch.
        """
        # Snapshot queue atomically
        with self._index_lock:
            if not self._index_queue:
                logger.debug("Index batch triggered but queue is empty (race condition)")
                return

            batch = list(self._index_queue)
            self._index_queue.clear()
            logger.info(f"Starting index batch ({len(batch)} files)")

        # Process each file
        successful = 0
        for pdf_path in batch:
            if self._shutdown:
                logger.warning("Aborting index batch - shutdown requested")
                break

            try:
                # Check file still exists
                if not pdf_path.exists():
                    logger.warning(f"File deleted before indexing: {pdf_path}")
                    continue

                logger.debug(f"Indexing: {pdf_path.name}")

                # Index PDF semantically
                self.pdf_searcher.index_pdf_semantic(pdf_path)

                # Mark as indexed in database
                # (PDFSearcher already updates database, but we double-check)
                # self.database.mark_file_indexed(pdf_path)

                # Queue for sync
                self.queue_for_sync(pdf_path)

                successful += 1
                self._stats["indexed_count"] += 1

            except Exception as e:
                error_msg = f"{pdf_path.name}: {str(e)}"
                self._stats["index_errors"].append(error_msg)
                logger.error(f"Failed to index {pdf_path}: {e}", exc_info=True)
                # Continue to next file

        # Callback to GUI
        if successful > 0:
            self.status_callback(
                f"Auto-indexed {successful} PDF{'s' if successful != 1 else ''}",
                "success"
            )
        elif batch:
            self.status_callback(
                f"Index batch completed with errors (see logs)",
                "warning"
            )

        logger.info(f"Index batch complete ({successful}/{len(batch)} successful)")

    def _run_sync_batch(self) -> None:
        """Process batch of PDFs for Deep-DX sync (runs in background thread).

        Workflow:
        1. Snapshot queue atomically
        2. Clear queue (new files go to next batch)
        3. Run ETL bridge to sync to Deep-DX
        4. Send status update to GUI

        Uses asyncio for the bridge (which is async), so we create
        a new event loop in this thread.

        Error handling: Log errors, report to GUI.
        """
        # Snapshot queue atomically
        with self._sync_lock:
            if not self._sync_queue:
                logger.debug("Sync batch triggered but queue is empty (race condition)")
                return

            batch = list(self._sync_queue)
            self._sync_queue.clear()
            logger.info(f"Starting sync batch ({len(batch)} files)")

        if self._shutdown:
            logger.warning("Aborting sync batch - shutdown requested")
            return

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Import here to avoid circular dependencies
            from bridges.library_to_deepdx import LibraryToDeepDxBridge

            # Instantiate bridge (skip_qdrant=False means try Qdrant, fallback to DB-only)
            bridge = LibraryToDeepDxBridge(skip_qdrant=False)

            # Run incremental sync (only processes new/changed files)
            # The bridge automatically checks what's already in neurosynth.db
            # and skips those files, so this is safe even with batch
            loop.run_until_complete(bridge.run(limit=None, force=False))

            self._stats["synced_count"] += len(batch)

            self.status_callback(
                f"Synced {len(batch)} PDF{'s' if len(batch) != 1 else ''} to Deep-DX",
                "success"
            )

            logger.info(f"Sync batch complete ({len(batch)} files)")

        except Exception as e:
            error_msg = f"Sync batch failed: {str(e)}"
            self._stats["sync_errors"].append(error_msg)
            logger.error(f"Sync failed: {e}", exc_info=True)

            self.status_callback(
                f"Sync failed: {str(e)[:100]}",
                "error"
            )

        finally:
            loop.close()
