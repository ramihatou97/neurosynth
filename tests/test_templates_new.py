"""
Tests for TemplateManager
"""

from pathlib import Path

import pytest

from src.templates import TemplateManager

# Mock template content
MOCK_TEMPLATE = """
---SYSTEM---
You are a system.
---USER---
You are a user with {{ ctx.variable }}.
"""

MOCK_USER_ONLY = """
Just a user prompt with {{ ctx.variable }}.
"""


@pytest.fixture
def template_manager(tmp_path):
    # Create a temporary template directory
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # Write mock templates
    (templates_dir / "mock.j2").write_text(MOCK_TEMPLATE)
    (templates_dir / "user_only.j2").write_text(MOCK_USER_ONLY)

    with open(templates_dir / "mock.j2", "w") as f:
        f.write(MOCK_TEMPLATE)
    with open(templates_dir / "user_only.j2", "w") as f:
        f.write(MOCK_USER_ONLY)

    return TemplateManager(templates_dir=templates_dir)


def test_render_split_prompts(template_manager):
    context = {"ctx": {"variable": "value"}}
    system, user = template_manager.render_prompt("mock.j2", context)

    assert "You are a system" in system
    assert "You are a user with value" in user


def test_render_user_only(template_manager):
    context = {"ctx": {"variable": "value"}}
    system, user = template_manager.render_prompt("user_only.j2", context)

    assert "neurosurgical knowledge synthesizer" in system  # Default
    assert "Just a user prompt with value" in user
