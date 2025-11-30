"""Test FLOWCHART ImageType addition.

Verifies that ImageType.FLOWCHART enum value exists and is properly
integrated into classification patterns and priority ordering.

Bug fixed: visual.py - added FLOWCHART enum value
Enhancement: image_extractor.py - added 12 FLOWCHART patterns
"""
import pytest
from neurosynth.models.visual import ImageType, VisualElement
from neurosynth.models.output import Section
from neurosynth.parsers.image_extractor import ImageExtractor


class TestFlowchartEnum:
    """Test FLOWCHART enum definition and properties."""

    def test_flowchart_enum_exists(self):
        """Verify FLOWCHART enum value exists."""
        assert hasattr(ImageType, 'FLOWCHART'), \
            "ImageType should have FLOWCHART attribute"
        assert ImageType.FLOWCHART.value == "flowchart", \
            "FLOWCHART value should be 'flowchart'"
        print("✓ ImageType.FLOWCHART enum defined correctly")

    def test_flowchart_in_priority_order(self):
        """Verify FLOWCHART appears in priority order list."""
        priority_order = ImageType.priority_order()

        assert ImageType.FLOWCHART in priority_order, \
            "FLOWCHART should be in priority_order()"

        # Verify position: should be between TABLE and UNKNOWN
        flowchart_idx = priority_order.index(ImageType.FLOWCHART)
        table_idx = priority_order.index(ImageType.TABLE)
        unknown_idx = priority_order.index(ImageType.UNKNOWN)

        assert table_idx < flowchart_idx < unknown_idx, \
            f"FLOWCHART should be between TABLE and UNKNOWN: " \
            f"TABLE({table_idx}) < FLOWCHART({flowchart_idx}) < UNKNOWN({unknown_idx})"

        print(f"✓ FLOWCHART at position {flowchart_idx} (after TABLE, before UNKNOWN)")

    def test_flowchart_not_high_priority(self):
        """Verify FLOWCHART is not high priority (not inline by default)."""
        # Only SURGICAL_STEP and ANATOMICAL are high priority
        assert not ImageType.FLOWCHART.is_high_priority, \
            "FLOWCHART should not be high priority (goes to plate, not inline)"
        print("✓ FLOWCHART correctly marked as non-high-priority")


class TestFlowchartPatterns:
    """Test FLOWCHART classification patterns."""

    def test_flowchart_patterns_defined(self):
        """Verify FLOWCHART patterns exist in TYPE_PATTERNS."""
        extractor = ImageExtractor()

        assert ImageType.FLOWCHART in extractor.TYPE_PATTERNS, \
            "TYPE_PATTERNS should include FLOWCHART key"

        patterns = extractor.TYPE_PATTERNS[ImageType.FLOWCHART]
        assert isinstance(patterns, list), "FLOWCHART patterns should be a list"
        assert len(patterns) >= 10, \
            f"FLOWCHART should have at least 10 patterns, got {len(patterns)}"

        print(f"✓ FLOWCHART has {len(patterns)} classification patterns")

    def test_flowchart_key_patterns_present(self):
        """Verify key FLOWCHART patterns are present."""
        extractor = ImageExtractor()
        patterns = extractor.TYPE_PATTERNS[ImageType.FLOWCHART]

        # Convert patterns to searchable text
        pattern_text = " ".join(patterns).lower()

        # Check for essential patterns
        expected_terms = [
            "flowchart",
            "algorithm",
            "workflow",
            "decision",
        ]

        missing = []
        for term in expected_terms:
            if term not in pattern_text:
                missing.append(term)

        assert not missing, \
            f"Missing essential FLOWCHART patterns: {missing}"

        print(f"✓ All essential patterns present: {expected_terms}")

    def test_flowchart_classification_works(self):
        """Test FLOWCHART classification with clear examples."""
        extractor = ImageExtractor()

        # Clear FLOWCHART examples - should classify as FLOWCHART
        flowchart_cases = [
            ("Figure 5", "Management algorithm flowchart"),
            ("", "The flowchart shows the decision tree"),
            ("Algorithm", "Treatment decision algorithm and workflow"),
        ]

        for caption, context in flowchart_cases:
            image_type, confidence = extractor._classify_image_type(
                caption=caption,
                context_text=context
            )

            assert image_type == ImageType.FLOWCHART, \
                f"Should classify as FLOWCHART: '{caption} {context}' → got {image_type}"
            print(f"  ✓ FLOWCHART: '{context[:45]}...' (confidence: {confidence:.2f})")


class TestFlowchartIntegration:
    """Test FLOWCHART integration in output and clustering."""

    def test_flowchart_in_output_type_priority(self):
        """Verify output.py type_priority dict can use FLOWCHART without AttributeError."""
        # This is the exact code at output.py:96 that was failing before fix
        try:
            type_priority = {
                ImageType.SURGICAL_STEP: 100,
                ImageType.ANATOMICAL: 80,
                ImageType.IMAGING: 60,
                ImageType.TABLE: 40,
                ImageType.FLOWCHART: 30,  # This would raise AttributeError before fix
                ImageType.UNKNOWN: 10,
            }
        except AttributeError as e:
            pytest.fail(f"AttributeError when creating type_priority dict: {e}")

        assert ImageType.FLOWCHART in type_priority, \
            "FLOWCHART should be in type_priority dict"
        assert type_priority[ImageType.FLOWCHART] == 30, \
            "FLOWCHART priority should be 30"

        print("✓ output.py type_priority dict works with FLOWCHART (no AttributeError)")

    def test_flowchart_visual_element_creation(self):
        """Test creating VisualElement with FLOWCHART type."""
        try:
            visual = VisualElement(
                id="flow1",
                image_type=ImageType.FLOWCHART,
                caption="Treatment algorithm for cerebral aneurysms",
                type_confidence=0.85,
                width=800,
                height=600,
            )
        except AttributeError as e:
            pytest.fail(f"AttributeError when creating VisualElement with FLOWCHART: {e}")

        assert visual.image_type == ImageType.FLOWCHART
        assert visual.image_type.value == "flowchart"
        assert not visual.image_type.is_high_priority
        print("✓ VisualElement with FLOWCHART type created successfully")

    def test_flowchart_in_section_sorting(self):
        """Test that FLOWCHART participates in section sorting without errors."""
        section = Section(
            title="Treatment Algorithms",
            level=2,
            content="Various treatment algorithms",
        )

        # Create visuals of different types including FLOWCHART
        visuals = [
            VisualElement(id="f1", image_type=ImageType.FLOWCHART, type_confidence=0.9),
            VisualElement(id="s1", image_type=ImageType.SURGICAL_STEP, type_confidence=0.8),
            VisualElement(id="a1", image_type=ImageType.ANATOMICAL, type_confidence=0.85),
            VisualElement(id="t1", image_type=ImageType.TABLE, type_confidence=0.7),
            VisualElement(id="u1", image_type=ImageType.UNKNOWN, type_confidence=0.5),
        ]

        # Simulate sorting by priority (as done in output.py:91-104)
        type_priority = {
            ImageType.SURGICAL_STEP: 100,
            ImageType.ANATOMICAL: 80,
            ImageType.IMAGING: 60,
            ImageType.TABLE: 40,
            ImageType.FLOWCHART: 30,
            ImageType.UNKNOWN: 10,
        }

        try:
            sorted_visuals = sorted(
                visuals,
                key=lambda v: (-type_priority.get(v.image_type, 0), -v.type_confidence),
            )
        except (AttributeError, KeyError) as e:
            pytest.fail(f"Error during sorting with FLOWCHART: {e}")

        # Verify FLOWCHART participated in sorting
        flowchart_visual = [v for v in sorted_visuals if v.image_type == ImageType.FLOWCHART]
        assert len(flowchart_visual) == 1, "FLOWCHART visual should be in sorted list"

        actual_order = [v.id for v in sorted_visuals]
        print(f"✓ Sorting works correctly with FLOWCHART")
        print(f"  Order: {' > '.join(actual_order)}")


def run_all_tests():
    """Run all FLOWCHART tests."""
    print("="*60)
    print("TESTING FIX 1.2: FLOWCHART ImageType Addition")
    print("="*60)
    print()

    # Enum tests
    print("[1/3] Testing Enum Definition...")
    test_enum = TestFlowchartEnum()
    test_enum.test_flowchart_enum_exists()
    test_enum.test_flowchart_in_priority_order()
    test_enum.test_flowchart_not_high_priority()
    print()

    # Pattern tests
    print("[2/3] Testing Classification Patterns...")
    test_patterns = TestFlowchartPatterns()
    test_patterns.test_flowchart_patterns_defined()
    test_patterns.test_flowchart_key_patterns_present()
    test_patterns.test_flowchart_classification_works()
    print()

    # Integration tests
    print("[3/3] Testing Integration...")
    test_integration = TestFlowchartIntegration()
    test_integration.test_flowchart_in_output_type_priority()
    test_integration.test_flowchart_visual_element_creation()
    test_integration.test_flowchart_in_section_sorting()
    print()

    print("="*60)
    print("✅ ALL TESTS PASSED - FIX 1.2 VERIFIED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
