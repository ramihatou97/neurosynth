"""Tests for system assessment template rendering."""

from src.templates import TemplateManager


def test_system_assessment_template_renders():
    """Template should render structured assessment instructions."""
    manager = TemplateManager()
    context = {"ctx": {"system_description": "Example system description"}}

    system, user = manager.render_prompt(
        "analysis/system_assessment.md.j2", context
    )

    assert "expert technical evaluator" in system
    assert "<scratchpad>" in user
    assert "<assessment>" in user
    assert "Example system description" in user
    assert "**1. COMPONENT-BY-COMPONENT ANALYSIS**" in user
    assert "**5. RECOMMENDATIONS FOR IMPROVEMENT**" in user
