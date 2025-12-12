"""
Template Configuration Registry
================================
Defines all 7 specialized synthesis templates and their configurable parameters.
Used by Synthesis Studio for template selection and dynamic UI generation.
"""

from dataclasses import dataclass, field
from typing import Any

# Template Registry - Maps template key to configuration
TEMPLATE_REGISTRY = {
    "section": {
        "name": "Generic Section",
        "description": "Standard textbook section synthesis with balanced content",
        "template_path": "synthesis/section.md.j2",
        "icon": "📝",
        "parameters": {
            "word_target": {
                "type": "slider",
                "min": 500,
                "max": 3000,
                "default": 1000,
                "step": 100,
                "label": "Word Target",
            },
            "section_type": {
                "type": "select",
                "options": ["DESCRIPTIVE", "IMPERATIVE"],
                "default": "DESCRIPTIVE",
                "label": "Section Style",
            },
            "dedup_threshold": {
                "type": "slider",
                "min": 0.5,
                "max": 1.0,
                "default": 0.85,
                "step": 0.05,
                "label": "Deduplication Threshold",
            },
        },
    },
    "anatomy": {
        "name": "Rhoton Anatomy",
        "description": "Microsurgical anatomy with layer-by-layer progression, 100-150 figures per region",
        "template_path": "synthesis/anatomy.md.j2",
        "icon": "🧠",
        "parameters": {
            "word_target": {
                "type": "slider",
                "min": 2000,
                "max": 10000,
                "default": 8000,
                "step": 500,
                "label": "Word Target",
            },
            "region_type": {
                "type": "select",
                "options": ["CRANIAL", "SPINAL", "CRANIOCERVICAL"],
                "default": "CRANIAL",
                "label": "Region Type",
            },
        },
    },
    "procedure": {
        "name": "Schmidek Procedure",
        "description": "Operative technique with step-by-step instructions, 80-120 figures per chapter",
        "template_path": "synthesis/procedure.md.j2",
        "icon": "🔬",
        "parameters": {
            "word_target": {
                "type": "slider",
                "min": 3000,
                "max": 15000,
                "default": 12000,
                "step": 500,
                "label": "Word Target",
            },
            "anatomy_depth": {
                "type": "select",
                "options": ["MINIMAL", "STANDARD", "COMPREHENSIVE"],
                "default": "STANDARD",
                "label": "Anatomy Detail Level",
            },
        },
    },
    "disorder": {
        "name": "Clinical Disorder",
        "description": "Disease-focused chapter with 4-part structure (Epi/Path, Presentation, Workup, Treatment)",
        "template_path": "synthesis/disorder.md.j2",
        "icon": "🩺",
        "parameters": {
            "word_target": {
                "type": "slider",
                "min": 2000,
                "max": 12000,
                "default": 8000,
                "step": 500,
                "label": "Word Target",
            },
            "focus_area": {
                "type": "select",
                "options": ["DIAGNOSIS", "TREATMENT", "BALANCED"],
                "default": "BALANCED",
                "label": "Content Focus",
            },
        },
    },
    "encyclopedia": {
        "name": "Encyclopedia Entry",
        "description": "Comprehensive reference entry integrating all aspects of a neurosurgical topic",
        "template_path": "synthesis/encyclopedia.md.j2",
        "icon": "📚",
        "parameters": {
            "word_target": {
                "type": "slider",
                "min": 5000,
                "max": 20000,
                "default": 15000,
                "step": 1000,
                "label": "Word Target",
            },
            "anatomy_depth": {
                "type": "select",
                "options": ["MINIMAL", "STANDARD", "COMPREHENSIVE"],
                "default": "STANDARD",
                "label": "Anatomy Depth",
            },
            "content_emphasis": {
                "type": "select",
                "options": ["DISORDER", "SURGICAL", "BALANCED"],
                "default": "BALANCED",
                "label": "Content Emphasis",
            },
        },
    },
    "imaging": {
        "name": "Neuroradiology",
        "description": "Imaging-focused synthesis with protocol details, pattern recognition, and surgical correlation",
        "template_path": "synthesis/imaging.md.j2",
        "icon": "📷",
        "parameters": {
            "modality_focus": {
                "type": "select",
                "options": ["MRI", "CT", "ANGIOGRAPHY", "MULTIMODAL"],
                "default": "MULTIMODAL",
                "label": "Primary Modality",
            },
            "imaging_purpose": {
                "type": "select",
                "options": [
                    "DIAGNOSTIC",
                    "PREOPERATIVE",
                    "INTRAOPERATIVE",
                    "SURVEILLANCE",
                ],
                "default": "DIAGNOSTIC",
                "label": "Clinical Purpose",
            },
            "target_audience": {
                "type": "select",
                "options": ["NEUROSURGEON", "NEURORADIOLOGIST", "TRAINEE"],
                "default": "NEUROSURGEON",
                "label": "Target Audience",
            },
        },
    },
    "outline": {
        "name": "Chapter Outline",
        "description": "Adaptive outline generation for chapter planning before full synthesis",
        "template_path": "synthesis/outline.md.j2",
        "icon": "📋",
        "parameters": {
            "template_type": {
                "type": "select",
                "options": ["COMPREHENSIVE", "PROCEDURAL", "THEORETICAL", "ADAPTIVE"],
                "default": "ADAPTIVE",
                "label": "Outline Style",
            },
            "word_budget": {
                "type": "slider",
                "min": 5000,
                "max": 30000,
                "default": 15000,
                "step": 1000,
                "label": "Total Word Budget",
            },
            "max_concurrent": {
                "type": "slider",
                "min": 1,
                "max": 10,
                "default": 3,
                "step": 1,
                "label": "Max Concurrent Generators",
            },
        },
    },
}


def get_template_config(template_key: str) -> dict:
    """Get configuration for a specific template."""
    return TEMPLATE_REGISTRY.get(template_key, TEMPLATE_REGISTRY["section"])


def get_template_choices() -> list[tuple[str, str, str]]:
    """Get list of (key, display_name, icon) for template selection dropdown."""
    return [(k, v["name"], v["icon"]) for k, v in TEMPLATE_REGISTRY.items()]


def get_default_params(template_key: str) -> dict[str, Any]:
    """Get default parameter values for a template."""
    config = get_template_config(template_key)
    params = {}
    for param_key, param_config in config.get("parameters", {}).items():
        params[param_key] = param_config.get("default")
    return params
