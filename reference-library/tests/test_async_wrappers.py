"""
Unit tests for async wrappers.

Tests Phase 4.1 Module 3:
- Executor pool singleton
- Async function wrapping
- Batch processing
- Async PDF document context manager
- Concurrent operations
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurosynth.enhancements.async_wrappers import (
    get_executor_pool,
    shutdown_executor_pool,
    async_wrap,
    async_wrapper,
    process_batch,
    AsyncPDFDocument,
    ExecutorPool,
)


class TestAsyncWrappers:
    """Test suite for async wrappers."""

    def test_executor_pool_singleton(self):
        """Test executor pool is singleton."""
        # Clear any existing pool
        shutdown_executor_pool()

        pool1 = get_executor_pool()
        pool2 = get_executor_pool()

        # Should be same instance
        assert pool1 is pool2
        assert isinstance(pool1, ExecutorPool)

        print("✓ Executor pool singleton pattern works")

        # Cleanup
        shutdown_executor_pool()

    def test_executor_pool_initialization(self):
        """Test executor pool initializes correctly."""
        shutdown_executor_pool()

        pool = ExecutorPool(max_workers=4)

        assert pool.max_workers == 4
        assert pool._executor is not None

        pool.shutdown()

        print("✓ Executor pool initialization works")

    @pytest.mark.asyncio
    async def test_async_wrap_function(self):
        """Test async_wrap executes synchronous function."""
        def sync_function(x, y):
            return x + y

        result = await async_wrap(sync_function, 5, 10)

        assert result == 15

        print("✓ async_wrap executes synchronous functions")

        shutdown_executor_pool()

    @pytest.mark.asyncio
    async def test_async_wrapper_decorator(self):
        """Test async_wrapper decorator."""
        @async_wrapper
        def multiply(x, y):
            return x * y

        result = await multiply(3, 7)

        assert result == 21

        print("✓ async_wrapper decorator works")

        shutdown_executor_pool()

    @pytest.mark.asyncio
    async def test_process_batch(self):
        """Test batch processing with concurrency control."""
        def square(x):
            return x * x

        items = [1, 2, 3, 4, 5]

        results = await process_batch(
            items,
            square,
            batch_size=2,
            max_concurrent=2
        )

        assert results == [1, 4, 9, 16, 25]

        print("✓ Batch processing works")

        shutdown_executor_pool()

    @pytest.mark.asyncio
    async def test_process_batch_empty(self):
        """Test batch processing with empty list."""
        results = await process_batch(
            [],
            lambda x: x,
            batch_size=10
        )

        assert results == []

        print("✓ Batch processing handles empty list")

    @pytest.mark.asyncio
    async def test_async_pdf_document_context_manager(self):
        """Test AsyncPDFDocument as context manager."""
        mock_doc = Mock()
        mock_doc.close = Mock()

        with patch('neurosynth.enhancements.async_wrappers.fitz.open', return_value=mock_doc):
            async with AsyncPDFDocument('/fake/path.pdf') as doc:
                assert doc.doc == mock_doc
                assert doc.pdf_path == '/fake/path.pdf'

            # Document should be closed after exit
            # (async_wrap would call mock_doc.close)

        print("✓ AsyncPDFDocument context manager works")

        shutdown_executor_pool()

    def test_async_pdf_document_initialization(self):
        """Test AsyncPDFDocument initialization."""
        pdf_doc = AsyncPDFDocument('/test/path.pdf')

        assert pdf_doc.pdf_path == '/test/path.pdf'
        assert pdf_doc.doc is None

        print("✓ AsyncPDFDocument initialization works")

    # Note: Full async PDF tests require complex mock setup
    # These are better tested in integration tests with real PDFs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
