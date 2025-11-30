"""Test FigurePlate attribute fix.

Verifies that Section.total_figures property correctly accesses
FigurePlate.figures (not .elements) to avoid AttributeError.

Bug fixed: output.py:75 - changed .elements to .figures
"""
import pytest
from pathlib import Path
from neurosynth.models.output import Section
from neurosynth.models.visual import VisualElement, FigurePlate, ImageType


def test_figure_plate_has_figures_attribute():
    """Verify FigurePlate uses 'figures' attribute, not 'elements'."""
    plate = FigurePlate(section_title="Test Plate")

    # Verify 'figures' exists
    assert hasattr(plate, 'figures'), "FigurePlate should have 'figures' attribute"
    assert isinstance(plate.figures, list), "FigurePlate.figures should be a list"

    # Verify 'elements' does NOT exist
    assert not hasattr(plate, 'elements'), "FigurePlate should NOT have 'elements' attribute"

    print("✓ FigurePlate correctly uses 'figures' attribute")


def test_total_figures_with_plate():
    """Test Section.total_figures with figure plate (main bug scenario)."""
    section = Section(
        title="Craniotomy Approaches",
        level=2,
        content="This section discusses various craniotomy approaches.",
    )

    # Add inline figures
    section.inline_figures = [
        VisualElement(
            id="fig1",
            image_type=ImageType.SURGICAL_STEP,
            caption="Figure 1: Pterional craniotomy",
            type_confidence=0.9,
        ),
        VisualElement(
            id="fig2",
            image_type=ImageType.ANATOMICAL,
            caption="Figure 2: Anatomical landmarks",
            type_confidence=0.85,
        ),
    ]

    # Add figure plate with 3 additional figures
    section.figure_plate = FigurePlate(
        section_title="Craniotomy Visual References",
        figures=[
            VisualElement(
                id="fig3",
                image_type=ImageType.IMAGING,
                caption="Figure 3: Preoperative MRI",
                type_confidence=0.8,
            ),
            VisualElement(
                id="fig4",
                image_type=ImageType.IMAGING,
                caption="Figure 4: Postoperative CT",
                type_confidence=0.75,
            ),
            VisualElement(
                id="fig5",
                image_type=ImageType.TABLE,
                caption="Table 1: Outcome comparison",
                type_confidence=0.7,
            ),
        ],
    )

    # THIS IS THE CRITICAL TEST - should NOT raise AttributeError
    try:
        total = section.total_figures
    except AttributeError as e:
        pytest.fail(f"AttributeError raised: {e}. Bug not fixed!")

    # Verify count is correct
    expected_total = 2 + 3  # 2 inline + 3 in plate
    assert total == expected_total, \
        f"Expected {expected_total} total figures (2 inline + 3 plate), got {total}"

    print(f"✓ total_figures = {total} (2 inline + 3 plate)")
    print("✓ No AttributeError - bug is fixed!")


def test_total_figures_without_plate():
    """Test Section.total_figures when figure_plate is None."""
    section = Section(
        title="Introduction",
        level=1,
        content="Introductory content.",
    )

    section.inline_figures = [
        VisualElement(id="fig1", caption="Figure 1"),
        VisualElement(id="fig2", caption="Figure 2"),
    ]
    section.figure_plate = None

    total = section.total_figures
    assert total == 2, f"Expected 2 figures, got {total}"
    print(f"✓ total_figures without plate = {total}")


def test_total_figures_empty():
    """Test Section.total_figures with no figures."""
    section = Section(
        title="Bibliography",
        level=1,
        content="References.",
    )

    section.inline_figures = []
    section.figure_plate = None

    total = section.total_figures
    assert total == 0, f"Expected 0 figures, got {total}"
    print(f"✓ total_figures with no figures = {total}")


def test_total_figures_empty_plate():
    """Test Section.total_figures with empty plate."""
    section = Section(
        title="Discussion",
        level=1,
        content="Discussion content.",
    )

    section.inline_figures = [VisualElement(id="fig1", caption="Figure 1")]
    section.figure_plate = FigurePlate(
        section_title="Empty Plate",
        figures=[],  # Empty list
    )

    total = section.total_figures
    assert total == 1, f"Expected 1 figure (1 inline + 0 plate), got {total}"
    print(f"✓ total_figures with empty plate = {total}")


def test_figure_plate_count_property():
    """Test FigurePlate.count property uses .figures correctly."""
    plate = FigurePlate(
        section_title="Test",
        figures=[
            VisualElement(id="f1", caption="Fig 1"),
            VisualElement(id="f2", caption="Fig 2"),
            VisualElement(id="f3", caption="Fig 3"),
        ],
    )

    # FigurePlate.count should use .figures
    count = plate.count
    assert count == 3, f"Expected count=3, got {count}"
    print(f"✓ FigurePlate.count = {count}")


def test_figure_plate_methods_use_figures():
    """Verify all FigurePlate methods correctly use .figures attribute."""
    plate = FigurePlate(section_title="Methods Test")

    # Test add_figure
    plate.add_figure(VisualElement(
        id="surgical1",
        image_type=ImageType.SURGICAL_STEP,
        caption="Surgical view",
    ))
    assert len(plate.figures) == 1, "add_figure should append to .figures"

    # Test get_figures_by_type
    plate.add_figure(VisualElement(
        id="anatomy1",
        image_type=ImageType.ANATOMICAL,
        caption="Anatomical diagram",
    ))
    plate.add_figure(VisualElement(
        id="surgical2",
        image_type=ImageType.SURGICAL_STEP,
        caption="Another surgical view",
    ))

    surgical_figs = plate.get_figures_by_type(ImageType.SURGICAL_STEP)
    assert len(surgical_figs) == 2, "Should find 2 surgical figures"

    # Test is_empty
    assert not plate.is_empty, "Plate with figures should not be empty"

    empty_plate = FigurePlate(section_title="Empty")
    assert empty_plate.is_empty, "Plate with no figures should be empty"

    print("✓ All FigurePlate methods use .figures correctly")


if __name__ == "__main__":
    print("="*60)
    print("TESTING FIX 1.1: FigurePlate.elements → .figures")
    print("="*60)
    print()

    test_figure_plate_has_figures_attribute()
    print()
    test_total_figures_with_plate()
    print()
    test_total_figures_without_plate()
    print()
    test_total_figures_empty()
    print()
    test_total_figures_empty_plate()
    print()
    test_figure_plate_count_property()
    print()
    test_figure_plate_methods_use_figures()

    print()
    print("="*60)
    print("✅ ALL TESTS PASSED - FIX 1.1 VERIFIED")
    print("="*60)
