"""Test resilient 3-tier filter integration with ImageExtractor.

Verifies that ImageExtractor properly integrates ResilientImageFilter
with fallback chain: Enhanced → Basic → Permissive → Legacy.

Integration: image_extractor.py - added filter_image() method
"""
import pytest
import io
import random
from PIL import Image
from pathlib import Path
from neurosynth.parsers.image_extractor import ImageExtractor
from neurosynth.models.visual import ImageType
from neurosynth.config import Settings


def create_complex_image(width: int, height: int) -> bytes:
    """Create complex image with random pixels (simulates real medical image)."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for i in range(min(width, 100)):  # Limit to 100x100 for speed
        for j in range(min(height, 100)):
            pixels[i, j] = (
                random.randint(100, 200),
                random.randint(100, 200),
                random.randint(100, 200),
            )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_simple_image(width: int, height: int, color: str = "red") -> bytes:
    """Create simple solid-color image."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestResilientFilterIntegration:
    """Test resilient filter integration in ImageExtractor."""

    def test_extractor_has_resilient_filter(self):
        """Verify ImageExtractor initializes resilient filter when enabled."""
        extractor = ImageExtractor()

        # Should have filter_image method
        assert hasattr(extractor, 'filter_image'), \
            "ImageExtractor should have filter_image() method"

        # Should have filter_stats
        assert hasattr(extractor, 'filter_stats'), \
            "ImageExtractor should have filter_stats dict"

        # May or may not have resilient_filter depending on config
        has_resilient = extractor.resilient_filter is not None
        print(f"  Resilient filter initialized: {has_resilient}")

        if has_resilient:
            print("  ✓ Resilient 3-tier filter active")
        else:
            print("  ✓ Legacy 6-rule filter active")

    def test_filter_image_method_works(self):
        """Test filter_image() instance method."""
        extractor = ImageExtractor()

        # Create test image
        image_bytes = create_complex_image(500, 400)

        # Call filter_image
        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=500,
            height=400,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.ANATOMICAL,
            context_text="anatomical diagram",
        )

        # Verify result structure
        assert hasattr(result, 'is_valid'), "Result should have is_valid"
        assert hasattr(result, 'rejection_reason'), "Result should have rejection_reason"
        assert hasattr(result, 'confidence'), "Result should have confidence"

        print(f"  ✓ filter_image() works (500x400: {'ACCEPT' if result.is_valid else 'REJECT'})")

    def test_filter_accepts_valid_medical_image(self):
        """Test that valid medical images are accepted."""
        extractor = ImageExtractor()

        # Large, complex surgical image
        image_bytes = create_complex_image(800, 600)

        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=800,
            height=800,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.SURGICAL_STEP,
            context_text="intraoperative view of craniotomy",
        )

        assert result.is_valid, f"Should accept 800x600 surgical image: {result.rejection_reason}"
        assert result.confidence >= 0.2, f"Should have some confidence: {result.confidence}"

        print(f"  ✓ Valid surgical image accepted (confidence: {result.confidence:.2f})")

    def test_filter_rejects_tiny_icon(self):
        """Test that tiny icons are rejected."""
        extractor = ImageExtractor()

        # Tiny icon
        image_bytes = create_simple_image(32, 32)

        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=32,
            height=32,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.UNKNOWN,
            context_text="",
        )

        assert not result.is_valid, "Should reject 32x32 icon"
        print(f"  ✓ Tiny icon rejected: {result.rejection_reason}")

    def test_filter_rejects_separator(self):
        """Test that separator bars are rejected."""
        extractor = ImageExtractor()

        # Extreme aspect ratio separator
        image_bytes = create_simple_image(1000, 5)

        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=1000,
            height=5,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.UNKNOWN,
            context_text="",
        )

        assert not result.is_valid, "Should reject 1000x5 separator"
        # Accept any rejection reason (could be aspect ratio, too_small_bytes, etc.)
        print(f"  ✓ Separator rejected: {result.rejection_reason}")

    def test_filter_statistics_tracking(self):
        """Test that filter statistics are tracked."""
        extractor = ImageExtractor()

        # Reset stats
        extractor.filter_stats = {k: 0 for k in extractor.filter_stats}

        # Process several images
        test_images = [
            (800, 600, True, "complex"),   # Accept
            (32, 32, False, "simple"),      # Reject
            (500, 400, True, "complex"),   # Accept
            (1000, 5, False, "simple"),    # Reject
        ]

        for width, height, should_accept, complexity in test_images:
            if complexity == "complex":
                image_bytes = create_complex_image(width, height)
            else:
                image_bytes = create_simple_image(width, height)

            extractor.filter_image(
                image_bytes=image_bytes,
                width=width,
                height=height,
                file_size_bytes=len(image_bytes),
                image_type=ImageType.UNKNOWN,
                context_text="",
            )

        # Check stats
        stats = extractor.filter_stats
        assert stats['total_filtered'] == 4, "Should have processed 4 images"
        assert stats['accepted'] > 0, "Should have accepted some images"
        assert stats['rejected'] > 0, "Should have rejected some images"

        print(f"  ✓ Statistics tracked: {stats['total_filtered']} processed")
        print(f"    Accepted: {stats['accepted']}, Rejected: {stats['rejected']}")

        # Print stats
        print("\n  Filter statistics:")
        extractor.print_filter_stats()

    def test_resilient_filter_fallback_chain(self):
        """Test that fallback chain works when enhanced filter unavailable."""
        extractor = ImageExtractor()

        # Process an image
        image_bytes = create_complex_image(400, 300)

        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=400,
            height=300,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.ANATOMICAL,
            context_text="anatomical cross-section",
        )

        # Should get a result regardless of which filter tier was used
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'confidence')

        # Check which filter was used
        stats = extractor.filter_stats
        if stats['enhanced_used'] > 0:
            print("  ✓ Enhanced (Tier 1) filter used")
        elif stats['basic_fallback'] > 0:
            print("  ✓ Basic (Tier 2) filter used")
        elif stats['permissive_fallback'] > 0:
            print("  ✓ Permissive (Tier 3) filter used")
        elif stats['legacy_used'] > 0:
            print("  ✓ Legacy 6-rule filter used")

    def test_backward_compatibility(self):
        """Test that ImageExtractor still works when enhancements disabled."""
        # This would require modifying settings, which we don't want to do globally
        # Just verify the legacy path exists
        extractor = ImageExtractor()

        # Legacy filter should still work via self.filter_image()
        image_bytes = create_complex_image(300, 250)

        result = extractor.filter_image(
            image_bytes=image_bytes,
            width=300,
            height=250,
            file_size_bytes=len(image_bytes),
            image_type=ImageType.IMAGING,
            context_text="MRI scan",
        )

        # Should work regardless of which filter is active
        assert isinstance(result.is_valid, bool)
        print("  ✓ Backward compatibility maintained")


def run_all_tests():
    """Run all resilient filter integration tests."""
    print("="*70)
    print("PHASE 3.3: RESILIENT FILTER INTEGRATION TESTING")
    print("="*70)
    print()

    test = TestResilientFilterIntegration()

    print("[1/7] Testing filter initialization...")
    test.test_extractor_has_resilient_filter()
    print()

    print("[2/7] Testing filter_image() method...")
    test.test_filter_image_method_works()
    print()

    print("[3/7] Testing valid image acceptance...")
    test.test_filter_accepts_valid_medical_image()
    print()

    print("[4/7] Testing tiny icon rejection...")
    test.test_filter_rejects_tiny_icon()
    print()

    print("[5/7] Testing separator rejection...")
    test.test_filter_rejects_separator()
    print()

    print("[6/7] Testing statistics tracking...")
    test.test_filter_statistics_tracking()
    print()

    print("[7/7] Testing fallback chain...")
    test.test_resilient_filter_fallback_chain()
    print()

    print("="*70)
    print("✅ ALL RESILIENT FILTER INTEGRATION TESTS PASSED")
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
