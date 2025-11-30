"""
Async Wrappers for NeuroSynth
===============================
Provides async utilities and thread pool management for PDF processing.

Key components:
- Global thread pool for concurrent operations
- Async wrappers for synchronous functions
- Batch processing with concurrency control
- Async PDF document context manager

Version: 1.0
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar, List, Dict, Any, Optional
from functools import wraps

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

logger = logging.getLogger(__name__)

# Type variable for generic async wrapping
T = TypeVar('T')


# =============================================================================
# GLOBAL THREAD POOL
# =============================================================================

# Singleton thread pool (initialized on first access)
_EXECUTOR_POOL: Optional['ExecutorPool'] = None
_MAX_WORKERS = 4  # Default thread pool size


class ExecutorPool:
    """
    Wrapper around ThreadPoolExecutor with async interface.

    Provides:
    - Global singleton pattern for resource efficiency
    - run_in_thread() method for easy async execution
    - Graceful shutdown management
    """

    def __init__(self, max_workers: int = _MAX_WORKERS):
        """
        Initialize executor pool.

        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"ExecutorPool initialized with {max_workers} workers")

    async def run_in_thread(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Run a synchronous function in the thread pool.

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: func(*args, **kwargs)
        )

    def shutdown(self, wait: bool = True):
        """
        Shutdown the executor pool.

        Args:
            wait: If True, wait for all tasks to complete
        """
        self._executor.shutdown(wait=wait)
        logger.info("ExecutorPool shut down")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


def get_executor_pool() -> ExecutorPool:
    """
    Get or create the global executor pool (singleton pattern).

    Returns:
        ExecutorPool instance with run_in_thread() method
    """
    global _EXECUTOR_POOL

    if _EXECUTOR_POOL is None:
        _EXECUTOR_POOL = ExecutorPool(max_workers=_MAX_WORKERS)
        logger.debug("Created global executor pool")

    return _EXECUTOR_POOL


def shutdown_executor_pool():
    """
    Shutdown the global executor pool.

    Useful for cleanup in testing or application shutdown.
    """
    global _EXECUTOR_POOL

    if _EXECUTOR_POOL is not None:
        _EXECUTOR_POOL.shutdown()
        _EXECUTOR_POOL = None
        logger.debug("Global executor pool shut down")


# =============================================================================
# ASYNC FUNCTION WRAPPERS
# =============================================================================

async def async_wrap(
    func: Callable[..., T],
    *args,
    **kwargs
) -> T:
    """
    Wrap a synchronous function for async execution.

    Executes the function in the global thread pool to avoid blocking
    the event loop.

    Args:
        func: Synchronous function to execute
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Example:
        result = await async_wrap(expensive_computation, arg1, arg2)
    """
    pool = get_executor_pool()
    return await pool.run_in_thread(func, *args, **kwargs)


def async_wrapper(func: Callable[..., T]) -> Callable[..., asyncio.Future]:
    """
    Decorator to convert a synchronous function to async.

    Args:
        func: Synchronous function to wrap

    Returns:
        Async version of func

    Example:
        @async_wrapper
        def process_data(x):
            return x * 2

        result = await process_data(5)  # Returns 10
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await async_wrap(func, *args, **kwargs)

    return wrapper


# =============================================================================
# BATCH PROCESSING
# =============================================================================

async def process_batch(
    items: List[Any],
    processor: Callable[[Any], T],
    batch_size: int = 20,
    max_concurrent: int = 4
) -> List[T]:
    """
    Process items in batches with concurrency control.

    Useful for processing large lists while controlling parallelism
    to avoid overwhelming system resources.

    Args:
        items: List of items to process
        processor: Function to apply to each item
        batch_size: Number of items per batch
        max_concurrent: Maximum concurrent batches

    Returns:
        List of results in the same order as items

    Example:
        pages = [1, 2, 3, ..., 100]
        results = await process_batch(
            pages,
            extract_page,
            batch_size=20,
            max_concurrent=4
        )
    """
    if not items:
        return []

    results = []
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(item):
        async with semaphore:
            return await async_wrap(processor, item)

    # Split into batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        # Process batch concurrently
        batch_results = await asyncio.gather(
            *[process_one(item) for item in batch],
            return_exceptions=True
        )

        results.extend(batch_results)

    return results


async def process_batch_with_progress(
    items: List[Any],
    processor: Callable[[Any], T],
    batch_size: int = 20,
    max_concurrent: int = 4,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[T]:
    """
    Process items in batches with progress callbacks.

    Similar to process_batch but calls progress_callback after each batch.

    Args:
        items: List of items to process
        processor: Function to apply to each item
        batch_size: Number of items per batch
        max_concurrent: Maximum concurrent batches
        progress_callback: Function called with (completed, total) after each batch

    Returns:
        List of results in the same order as items

    Example:
        def on_progress(completed, total):
            print(f"Progress: {completed}/{total}")

        results = await process_batch_with_progress(
            pages,
            extract_page,
            progress_callback=on_progress
        )
    """
    if not items:
        return []

    total = len(items)
    completed = 0
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(item):
        nonlocal completed
        async with semaphore:
            result = await async_wrap(processor, item)
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            return result

    # Split into batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        # Process batch concurrently
        batch_results = await asyncio.gather(
            *[process_one(item) for item in batch],
            return_exceptions=True
        )

        results.extend(batch_results)

    return results


# =============================================================================
# ASYNC PDF DOCUMENT
# =============================================================================

class AsyncPDFDocument:
    """
    Async context manager for PDF document operations.

    Wraps PyMuPDF Document for async usage, ensuring proper resource
    management and thread-safe operations.

    Example:
        async with AsyncPDFDocument(pdf_path) as doc:
            page = await doc.extract_page(0)
            text = await doc.extract_text(0)
    """

    def __init__(self, pdf_path: str):
        """
        Initialize async PDF document.

        Args:
            pdf_path: Path to PDF file
        """
        if not HAS_FITZ:
            raise ImportError("PyMuPDF (fitz) required for async PDF operations")

        self.pdf_path = pdf_path
        self.doc: Optional[fitz.Document] = None

    async def __aenter__(self):
        """Open PDF document asynchronously."""
        loop = asyncio.get_event_loop()
        pool = get_executor_pool()

        # Open document in thread pool (file I/O)
        self.doc = await loop.run_in_executor(
            pool._executor,
            fitz.open,
            self.pdf_path
        )

        logger.debug(f"Opened PDF document: {self.pdf_path}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close PDF document asynchronously."""
        if self.doc:
            await async_wrap(self.doc.close)
            self.doc = None
            logger.debug(f"Closed PDF document: {self.pdf_path}")

    async def extract_page(self, page_num: int) -> Optional[fitz.Page]:
        """
        Extract a page from the document.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            PyMuPDF Page object or None if page doesn't exist
        """
        if not self.doc:
            raise RuntimeError("Document not opened")

        def get_page():
            if 0 <= page_num < len(self.doc):
                return self.doc[page_num]
            return None

        return await async_wrap(get_page)

    async def extract_text(self, page_num: int) -> str:
        """
        Extract text from a page.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            Text content of the page
        """
        page = await self.extract_page(page_num)
        if not page:
            return ""

        return await async_wrap(page.get_text)

    async def get_page_count(self) -> int:
        """
        Get total number of pages in document.

        Returns:
            Page count
        """
        if not self.doc:
            raise RuntimeError("Document not opened")

        return await async_wrap(lambda: len(self.doc))

    async def extract_images(self, page_num: int) -> List[Dict]:
        """
        Extract image list from a page.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            List of image info dictionaries
        """
        page = await self.extract_page(page_num)
        if not page:
            return []

        return await async_wrap(page.get_images, full=True)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'ExecutorPool',
    'get_executor_pool',
    'shutdown_executor_pool',
    'async_wrap',
    'async_wrapper',
    'process_batch',
    'process_batch_with_progress',
    'AsyncPDFDocument',
]
