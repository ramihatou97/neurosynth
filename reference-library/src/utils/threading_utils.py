"""Threading utilities for background task management."""
import threading
from typing import Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, Empty
import time


class BackgroundTaskManager:
    """Manage background search and categorization tasks."""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_futures: list[Future] = []
        self._shutdown = False

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Submit a task to run in background."""
        future = self.executor.submit(fn, *args, **kwargs)
        self.active_futures.append(future)
        return future

    def cancel_all(self):
        """Cancel all pending tasks."""
        for future in self.active_futures:
            future.cancel()
        self.active_futures.clear()

    def shutdown(self, wait: bool = True):
        """Shutdown the executor."""
        self._shutdown = True
        self.executor.shutdown(wait=wait)


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self.lock = threading.Lock()

    def wait(self):
        """Wait until next call is allowed."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


class TaskQueue:
    """Thread-safe task queue with callbacks."""

    def __init__(self):
        self.queue = Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start(self, callback: Callable[[Any], None]):
        """Start processing queue with callback."""
        self._running = True
        self._callback = callback
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Stop processing queue."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)

    def put(self, item: Any):
        """Add item to queue."""
        self.queue.put(item)

    def _process_queue(self):
        """Process items from queue."""
        while self._running:
            try:
                item = self.queue.get(timeout=0.1)
                if item is not None:
                    self._callback(item)
            except Empty:
                # Queue empty or timeout - this is expected, continue polling
                continue
