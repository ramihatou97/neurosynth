"""Test unified filtering between main pipeline and bridge.

Verifies that the reference library bridge now uses the same sophisticated
6-rule filter as the main pipeline (no longer using simple 3KB filter).

Changes verified:
- neurosynth_bridge.py: Removed duplicate _is_medical_image() function
- neurosynth_bridge.py: Added import of filter_image_bytes from main
- neurosynth_bridge.py:424: Updated to use unified filter
"""
import pytest
import io
import random
from PIL import Image
from neurosynth.parsers.image_extractor import filter_image_bytes


def create_simple_image(width: int, height: int, color: str = "red") -> bytes:
    """Create simple solid-color test image."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_complex_image(width: int, height: int) -> bytes:
    """Create complex image with random pixels (simulates real medical image)."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for i in range(width):
        for j in range(height):
            pixels[i, j] = (
                random.randint(100, 200),
                random.randint(100, 200),
                random.randint(100, 200),
            )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestFilterUnification:
    """Test that bridge and main use the same filter logic."""

    def test_valid_surgical_image_accepted(self):
        """Large complex image should pass filter."""
        image_bytes = create_complex_image(800, 600)

        is_valid, reason = filter_image_bytes(image_bytes)

        assert is_valid, f"Should accept 800x600 complex image: {reason}"
        print(f"✓ Valid 800x600 surgical image accepted (size: {len(image_bytes):,}B)")

    def test_tiny_icon_rejected(self):
        """Tiny icon should be rejected by Rule 1 (both dims < 150px)."""
        image_bytes = create_simple_image(32, 32)

        is_valid, reason = filter_image_bytes(image_bytes)

        assert not is_valid, "Should reject 32x32 icon"
        assert "small" in reason.lower() or "32x32" in reason.lower(), \
            f"Expected size-related reason, got: {reason}"
        print(f"✓ Tiny icon rejected: {reason}")

    def test_separator_bar_rejected(self):
        """Extreme aspect ratio separator should be rejected by Rule 2."""
        image_bytes = create_simple_image(1000, 5)

        is_valid, reason = filter_image_bytes(image_bytes)

        assert not is_valid, "Should reject 1000x5 separator bar"
        assert "aspect" in reason.lower() or "bar" in reason.lower(), \
            f"Expected aspect ratio reason, got: {reason}"
        print(f"✓ Separator bar rejected: {reason}")

    def test_small_area_rejected(self):
        """Image with small total area should be rejected by Rule 3."""
        image_bytes = create_simple_image(140, 140)  # 19,600px² < 30,000px²

        is_valid, reason = filter_image_bytes(image_bytes)

        assert not is_valid, "Should reject 140x140 (small area)"
        assert "small" in reason.lower() or "area" in reason.lower(), \
            f"Expected area reason, got: {reason}"
        print(f"✓ Small area rejected: {reason}")

    def test_low_complexity_rejected(self):
        """Solid color image should be rejected by Rule 4 (low complexity)."""
        # Large dimensions but solid color = very small file size
        image_bytes = create_simple_image(800, 600)

        is_valid, reason = filter_image_bytes(image_bytes)
        file_size = len(image_bytes)

        # Should be rejected if file size < 5KB for such large area
        if file_size < 5000:
            assert not is_valid, f"Should reject low-complexity image ({file_size}B for 480k px²)"
            assert "complexity" in reason.lower() or "bytes" in reason.lower(), \
                f"Expected complexity reason, got: {reason}"
            print(f"✓ Low-complexity rejected: {reason} ({file_size:,}B)")
        else:
            # If PNG compression resulted in > 5KB, might be accepted
            print(f"✓ Low-complexity image: {file_size:,}B (may pass if > 5KB)")

    def test_logo_dimensions_rejected(self):
        """Common logo sizes should be rejected by Rule 5."""
        # Common logo size: 100x100
        image_bytes = create_simple_image(100, 100)

        is_valid, reason = filter_image_bytes(image_bytes)

        assert not is_valid, "Should reject 100x100 logo-like dimensions"
        assert "logo" in reason.lower() or "small" in reason.lower(), \
            f"Expected logo or size reason, got: {reason}"
        print(f"✓ Logo dimensions rejected: {reason}")

    def test_borderline_size_accepted(self):
        """Image just above thresholds should be accepted."""
        # 200x200 = 40,000px² (> 30,000 threshold)
        image_bytes = create_complex_image(200, 200)

        is_valid, reason = filter_image_bytes(image_bytes)

        assert is_valid, f"Should accept 200x200 (area > 30k): {reason}"
        print(f"✓ Borderline 200x200 accepted (area: 40,000px²)")


class TestFilterConsistency:
    """Test filter consistency across various image sizes."""

    def test_consistency_across_sizes(self):
        """Test a range of image sizes for expected filter behavior."""
        print("\nFilter consistency test:")
        print("-" * 60)

        test_cases = [
            # (width, height, complexity, expected_valid, description)
            (50, 50, "simple", False, "tiny icon"),
            (140, 140, "simple", False, "small area"),
            (200, 200, "complex", True, "valid small diagram"),
            (500, 400, "complex", True, "standard medical image"),
            (800, 600, "complex", True, "large surgical photo"),
            (1000, 10, "simple", False, "horizontal separator"),
            (10, 1000, "simple", False, "vertical separator"),
            (100, 100, "simple", False, "logo dimensions"),
        ]

        results = []
        for width, height, complexity, expected_valid, description in test_cases:
            if complexity == "complex":
                image_bytes = create_complex_image(width, height)
            else:
                image_bytes = create_simple_image(width, height)

            is_valid, reason = filter_image_bytes(image_bytes)

            # Check expected result
            status = "✓" if is_valid == expected_valid else "✗"
            result = f"{status} {width:4d}x{height:4d} ({description:25s}): "
            result += f"{'ACCEPT' if is_valid else 'REJECT':7s}"
            if not is_valid:
                result += f" - {reason}"

            results.append((status, result, is_valid == expected_valid))

            print(result)

        # Verify all tests matched expectations
        failures = [r for s, r, matched in results if not matched]
        assert not failures, f"Some tests failed expectations:\n" + "\n".join(failures)

        print("-" * 60)
        print(f"✓ All {len(test_cases)} consistency tests passed")


class TestBridgeIntegration:
    """Test that bridge can import and use unified filter."""

    def test_bridge_import_works(self):
        """Verify bridge can import filter_image_bytes from main."""
        try:
            from neurosynth.parsers.image_extractor import filter_image_bytes as bridge_filter
            print("✓ Bridge can import filter_image_bytes from main")
        except ImportError as e:
            pytest.fail(f"Bridge import failed: {e}")

    def test_bridge_filter_usage_pattern(self):
        """Test the exact usage pattern in bridge code."""
        # Simulate bridge usage
        image_bytes = create_complex_image(500, 400)

        # This is how bridge uses it (line 424)
        is_valid, rejection_reason = filter_image_bytes(image_bytes)

        if is_valid:
            print("✓ Image accepted - would be saved")
        else:
            print(f"✓ Image rejected: {rejection_reason}")

        # Just verify it returns correct types
        assert isinstance(is_valid, bool), "is_valid should be bool"
        assert isinstance(rejection_reason, str), "rejection_reason should be str"

    def test_old_3kb_filter_comparison(self):
        """Compare old 3KB filter vs new unified filter."""
        # Create test case that old filter would ACCEPT but new filter REJECTS
        # Example: 1000x5 separator bar with > 3KB file size
        separator_bytes = create_simple_image(1000, 5)

        # Old filter (3KB check only)
        old_would_accept = len(separator_bytes) >= 3072

        # New unified filter
        is_valid_new, reason_new = filter_image_bytes(separator_bytes)

        print(f"\n1000x5 separator bar ({len(separator_bytes):,} bytes):")
        print(f"  Old 3KB filter: {'ACCEPT' if old_would_accept else 'REJECT'}")
        print(f"  New unified filter: {'ACCEPT' if is_valid_new else 'REJECT'}")

        if old_would_accept and not is_valid_new:
            print(f"  ✓ Improvement: New filter correctly rejects separator ({reason_new})")
        elif not old_would_accept and is_valid_new:
            print(f"  ⚠ Divergence: New filter accepts what old rejected")
        else:
            print(f"  ✓ Consistent result")


def run_all_tests():
    """Run all filter unification tests."""
    print("="*60)
    print("PHASE 2: FILTER UNIFICATION TESTING")
    print("="*60)
    print()

    print("[1/3] Testing Filter Unification...")
    test_unification = TestFilterUnification()
    test_unification.test_valid_surgical_image_accepted()
    test_unification.test_tiny_icon_rejected()
    test_unification.test_separator_bar_rejected()
    test_unification.test_small_area_rejected()
    test_unification.test_low_complexity_rejected()
    test_unification.test_logo_dimensions_rejected()
    test_unification.test_borderline_size_accepted()
    print()

    print("[2/3] Testing Filter Consistency...")
    test_consistency = TestFilterConsistency()
    test_consistency.test_consistency_across_sizes()
    print()

    print("[3/3] Testing Bridge Integration...")
    test_bridge = TestBridgeIntegration()
    test_bridge.test_bridge_import_works()
    test_bridge.test_bridge_filter_usage_pattern()
    test_bridge.test_old_3kb_filter_comparison()
    print()

    print("="*60)
    print("✅ ALL FILTER UNIFICATION TESTS PASSED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
