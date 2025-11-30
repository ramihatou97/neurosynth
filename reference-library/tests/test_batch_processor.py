"""
Unit tests for BatchPageProcessor.

Tests Phase 4.1 Module 2:
- Initialization
- XRef deduplication
- Hash-based duplicate detection
- Cache management
- Batch statistics
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurosynth.enhancements.batch_processor import (
    BatchPageProcessor,
    BatchProcessingResult,
)
from neurosynth.enhancements.config import NeuroSynthEnhancedConfig


class TestBatchPageProcessor:
    """Test suite for BatchPageProcessor."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return NeuroSynthEnhancedConfig()

    @pytest.fixture
    def processor(self, config):
        """Create BatchPageProcessor instance."""
        return BatchPageProcessor(config)

    def test_initialization(self, config):
        """Test processor initializes with configuration."""
        processor = BatchPageProcessor(config)

        assert processor.config == config
        assert processor.perf_config == config.performance
        assert isinstance(processor.xref_cache, dict)
        assert isinstance(processor.hash_cache, dict)
        assert isinstance(processor.position_cache, dict)
        assert len(processor.xref_cache) == 0

        print("✓ BatchPageProcessor initialization verified")

    def test_compute_image_hash(self, processor):
        """Test hash computation is deterministic."""
        image_bytes_1 = b"fake_image_data"
        image_bytes_2 = b"fake_image_data"  # Identical
        image_bytes_3 = b"different_image"

        hash_1 = processor._compute_image_hash(image_bytes_1)
        hash_2 = processor._compute_image_hash(image_bytes_2)
        hash_3 = processor._compute_image_hash(image_bytes_3)

        # Same data → same hash
        assert hash_1 == hash_2

        # Different data → different hash
        assert hash_1 != hash_3

        # Hash should be hex string
        assert isinstance(hash_1, str)
        assert len(hash_1) == 64  # SHA-256 produces 64 hex chars

        print("✓ Image hash computation is deterministic")

    def test_extract_image_bytes(self, processor):
        """Test image extraction by xref."""
        mock_doc = Mock()
        mock_doc.extract_image.return_value = {
            'image': b'test_image_bytes',
            'ext': 'png',
        }

        result = processor._extract_image_bytes(mock_doc, xref=123)

        assert result == b'test_image_bytes'
        mock_doc.extract_image.assert_called_once_with(123)

        print("✓ Image extraction by xref works")

    def test_extract_image_bytes_failure(self, processor):
        """Test image extraction returns None on failure."""
        mock_doc = Mock()
        mock_doc.extract_image.side_effect = Exception("Extract failed")

        result = processor._extract_image_bytes(mock_doc, xref=999)

        assert result is None

        print("✓ Image extraction failure handled gracefully")

    def test_extract_image_bbox(self, processor):
        """Test bbox extraction for image."""
        import fitz

        mock_page = Mock()
        rect = fitz.Rect(50, 100, 250, 300)
        mock_page.get_image_rects.return_value = [rect]

        bbox = processor._extract_image_bbox(mock_page, xref=123)

        assert bbox == (50, 100, 250, 300)

        print("✓ Bounding box extraction works")

    def test_extract_image_bbox_not_found(self, processor):
        """Test bbox extraction returns zeros when not found."""
        mock_page = Mock()
        mock_page.get_image_rects.return_value = []

        bbox = processor._extract_image_bbox(mock_page, xref=123)

        assert bbox == (0, 0, 0, 0)

        print("✓ Missing bbox returns zeros")

    def test_cache_image(self, processor):
        """Test image caching stores all data correctly."""
        xref = 100
        image_bytes = b'test_image'
        image_hash = processor._compute_image_hash(image_bytes)
        page_num = 5
        bbox = (10, 20, 100, 200)

        processor._cache_image(xref, image_bytes, image_hash, page_num, bbox)

        # Verify all caches updated
        assert processor.xref_cache[xref] == image_bytes
        assert processor.hash_cache[image_hash] == xref
        assert processor.position_cache[xref] == (page_num, bbox)

        print("✓ Image caching stores data correctly")

    def test_xref_deduplication(self, processor):
        """Test xref deduplication skips already processed images."""
        # Setup: pre-populate xref cache
        processor.xref_cache[100] = b'existing_image'

        mock_doc = Mock()
        mock_page = Mock()
        mock_page.parent = mock_doc
        mock_page.get_images.return_value = [
            (100, 0, 800, 600, 8, "DeviceRGB", "", "Im1", "FlateDecode"),  # Duplicate xref
        ]

        result = BatchProcessingResult()
        processor._process_single_page(mock_page, page_num=0, result=result)

        # Should skip extraction
        assert result.images_found == 1
        assert result.duplicates_skipped == 1

        print("✓ XRef deduplication works")

    def test_hash_deduplication(self, processor):
        """Test hash-based duplicate detection."""
        image_bytes = b'duplicate_image'
        image_hash = processor._compute_image_hash(image_bytes)

        # Setup: pre-populate hash cache
        processor.hash_cache[image_hash] = 50  # Original xref

        mock_doc = Mock()
        mock_doc.extract_image.return_value = {'image': image_bytes}

        mock_page = Mock()
        mock_page.parent = mock_doc
        mock_page.get_images.return_value = [
            (100, 0, 800, 600, 8, "DeviceRGB", "", "Im1", "FlateDecode"),  # New xref, duplicate hash
        ]
        mock_page.get_image_rects.return_value = []

        result = BatchProcessingResult()
        processor._process_single_page(mock_page, page_num=0, result=result)

        # Should detect duplicate by hash
        assert result.images_found == 1
        assert result.duplicates_skipped == 1

        print("✓ Hash-based deduplication works")

    def test_clear_caches(self, processor):
        """Test cache clearing."""
        # Populate caches
        processor.xref_cache[100] = b'data'
        processor.hash_cache['abc123'] = 100
        processor.position_cache[100] = (0, (0, 0, 100, 100))

        processor.clear_caches()

        assert len(processor.xref_cache) == 0
        assert len(processor.hash_cache) == 0
        assert len(processor.position_cache) == 0

        print("✓ Cache clearing works")

    def test_get_cache_statistics(self, processor):
        """Test cache statistics calculation."""
        # Populate with test data
        processor.xref_cache[1] = b'x' * 1000
        processor.xref_cache[2] = b'y' * 2000
        processor.hash_cache['hash1'] = 1
        processor.hash_cache['hash2'] = 2
        processor.position_cache[1] = (0, (0, 0, 100, 100))

        stats = processor.get_cache_statistics()

        assert stats['xref_cache_size'] == 2
        assert stats['hash_cache_size'] == 2
        assert stats['position_cache_size'] == 1
        assert stats['total_cached_bytes'] == 3000
        assert stats['total_cached_mb'] == pytest.approx(3000 / (1024 * 1024))

        print("✓ Cache statistics computed correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
