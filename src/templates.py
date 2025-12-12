"""
Template Manager for Neurosurgical Synthesis

Handles loading and rendering of Jinja2 templates for the synthesis engine.
Supports splitting templates into System and User prompts.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger(__name__)


import re


class TemplateManager:
    """
    Manages Jinja2 templates for prompt generation.
    """

    def __init__(self, templates_dir: Path | None = None):
        if templates_dir is None:
            # Default to src/neurosynth/templates
            current_file = Path(__file__)
            # src/templates.py -> src/neurosynth/templates
            templates_dir = current_file.parent / "neurosynth" / "templates"

        if not templates_dir.exists():
            logger.warning("templates_dir_not_found", path=str(templates_dir))

        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.env.filters["regex_search"] = self._regex_search

        logger.info("template_manager_initialized", path=str(templates_dir))

    @staticmethod
    def _regex_search(value: str, pattern: str) -> bool:
        """Custom Jinja2 filter for regex searching"""
        if not value:
            return False
        return bool(re.search(pattern, value, re.IGNORECASE))

    def render_prompt(
        self, template_name: str, context: dict[str, Any]
    ) -> tuple[str, str]:
        """
        Render a template and split it into System and User prompts.

        Templates should use ---SYSTEM--- and ---USER--- markers.
        If no markers are found, the entire content is returned as the User prompt,
        and a default System prompt is returned.

        Args:
            template_name: Name of template (e.g., 'synthesis/anatomy.md.j2')
            context: Dictionary of context variables

        Returns:
            Tuple[str, str]: (system_prompt, user_prompt)
        """
        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**context)
        except Exception as e:
            logger.error("template_render_failed", template=template_name, error=str(e))
            raise

        return self._parse_prompts(rendered)

    def _parse_prompts(self, rendered_text: str) -> tuple[str, str]:
        """Parse the rendered text into system and user info"""

        # Default system prompt if none specified
        default_system = "You are an expert neurosurgical knowledge synthesizer."

        if "---SYSTEM---" in rendered_text and "---USER---" in rendered_text:
            parts = rendered_text.split("---USER---")
            system_part = parts[0].replace("---SYSTEM---", "").strip()
            user_part = parts[1].strip()
            return system_part, user_part

        elif "---USER---" in rendered_text:
            # Only User marker found
            parts = rendered_text.split("---USER---")
            user_part = parts[1].strip()
            return default_system, user_part

        else:
            # No markers, treat all as User prompt
            return default_system, rendered_text.strip()
