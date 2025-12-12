"""
Tests for section.md.j2 template logic
"""

from pathlib import Path

import pytest

from src.templates import TemplateManager


@pytest.fixture
def template_manager():
    # Helper to get the real template manager pointing to src/neurosynth/templates
    # This assumes the test file is run from the root directory or has proper pythonpath

    return TemplateManager()


def test_render_differential_diagnosis(template_manager):
    context = {
        "ctx": {
            "section_title": "Differential Diagnosis",
            "section_type": "DESCRIPTIVE",
            "chapter_context": "Vestibular Schwannoma",
            "sources": [],
            "figures": [],
        }
    }
    system, user = template_manager.render_prompt("synthesis/section.md.j2", context)

    assert "Differential Diagnosis Requirements" in user
    assert "Comparison Matrix" in user
    assert "Distinguishing Features" in user


def test_render_complications(template_manager):
    context = {
        "ctx": {
            "section_title": "Complications and Avoidance",
            "section_type": "DESCRIPTIVE",
            "chapter_context": "Vestibular Schwannoma",
            "sources": [],
            "figures": [],
        }
    }
    system, user = template_manager.render_prompt("synthesis/section.md.j2", context)

    assert "Outcomes/Complications Section Requirements" in user
    assert "Critical Complication Callout" in user
    assert "⚠️ CRITICAL COMPLICATION" in user


def test_render_standard_section(template_manager):
    context = {
        "ctx": {
            "section_title": "History",
            "section_type": "DESCRIPTIVE",
            "chapter_context": "Vestibular Schwannoma",
            "sources": [],
            "figures": [],
        }
    }
    system, user = template_manager.render_prompt("synthesis/section.md.j2", context)

    assert "Comparison Matrix" not in user
    assert "Critical Complication Callout" not in user
