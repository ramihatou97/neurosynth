# Jinja2 Prompt Migration: Definitive Implementation Plan

## Executive Summary

**Problem:** NeuroSynth's prompts are fragmented across 3 files with inconsistent figure handling:
- `prompts.py` ✅ Has figure integration instructions (`[FIGURE: ID]`)
- `claude.py` ❌ Lines 323-369: Inline prompts, **NO figure instructions**
- `gemini.py` ❌ Lines 252-298: Inline prompts, **NO figure instructions**

**Solution:** A 2-move approach (not phased):
1. **Move 1:** Lobotomize LLM clients (make them "dumb pipes")
2. **Move 2:** Full Jinja2 switch with ViewModel layer

**Timeline:** 7 days | **Risk:** Low (fail-loud design)

---

## Current Architecture Analysis

### Call Flow (What Actually Happens Today)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNTHESIS ENTRY POINTS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. synthesize_section()         2. synthesize_category_section()            │
│     └─ Uses claude.synthesize_section()  └─ Uses prompts.py templates       │
│        └─ INLINE PROMPTS (no figures!)      └─ claude.generate() with prompt│
│                                                 └─ HAS FIGURE INSTRUCTIONS! │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Core Problem

| Path | Prompt Location | Figure Instructions |
|------|-----------------|---------------------|
| `SectionSynthesizer.synthesize_section()` → `claude.synthesize_section()` | `claude.py:323-369` | ❌ **Missing** |
| `SectionSynthesizer.synthesize_category_section()` → `claude.generate()` | `prompts.py` | ✅ Present |
| Gemini fallback → `gemini.synthesize_section()` | `gemini.py:252-298` | ❌ **Missing** |

**Result:** Figure integration works in category-aware path but fails in the default path.

### Methods to Lobotomize

**In `claude.py`:**
| Method | Lines | Hardcoded Prompts | Action |
|--------|-------|-------------------|--------|
| `generate()` | 71-116 | Default system prompt (line 90) | Remove default |
| `merge_chunks()` | 117-181 | Inline system + user | Keep (utility) |
| `detect_conflicts()` | 183-222 | Inline system + user | Keep (utility) |
| `generate_outline()` | 224-291 | Inline system + user | Keep (utility) |
| `synthesize_section()` | 293-373 | **Full prompts, no figures** | **DELETE** |
| `synthesize_section_with_conflict_preservation()` | 375-458 | Full prompts | **DELETE** |
| `generate_abstract()` | 460-483 | Inline prompts | Keep (utility) |
| `extract_keywords()` | 485-513 | Inline prompts | Keep (utility) |

**In `gemini.py`:**
| Method | Lines | Hardcoded Prompts | Action |
|--------|-------|-------------------|--------|
| `generate()` | 51-85 | None (clean) | ✅ Keep |
| `extract_structure()` | 87-113 | Inline | Keep (utility) |
| `identify_chunk_topic()` | 115-152 | Inline | Keep (utility) |
| `segment_into_chunks()` | 154-197 | Inline | Keep (utility) |
| `extract_metadata()` | 199-230 | Inline | Keep (utility) |
| `synthesize_section()` | 232-302 | **Full prompts, no figures** | **DELETE** |

---

## Guiding Principles

| Principle | Rationale |
|-----------|-----------|
| **No Frankenstein architecture** | Mixing Python strings + Jinja2 concatenation = two mental models |
| **Lobotomize first, template second** | Creates the vacuum that demands templating |
| **ViewModel layer inside engine** | Decouples templates from model changes |
| **StrictUndefined mandatory** | Silent failures unacceptable for prompts |
| **Full switch, not partial** | Eliminates transition tax |

---

## Move 1: Lobotomize LLM Clients (Days 1-2)

### Step 1.1: Audit Current State

```bash
# Run these to identify all hardcoded prompts
grep -n "You are" src/neurosynth/llm/claude.py
grep -n "You are" src/neurosynth/llm/gemini.py
grep -n "system.*=" src/neurosynth/llm/claude.py
grep -n "FIGURE" src/neurosynth/llm/claude.py
grep -n "source_id" src/neurosynth/llm/gemini.py
```

### Step 1.2: Remove Default System Prompt from `claude.generate()`

**File:** `src/neurosynth/llm/claude.py`  
**Line 90 - Current:**
```python
system=system or "You are an expert neurosurgeon and medical writer.",
```

**After:**
```python
system=system,  # Caller MUST provide system prompt
```

**Add validation at line 78:**
```python
if system is None:
    raise ValueError("system prompt required - clients must not use defaults")
```

### Step 1.3: Delete `synthesize_section()` Methods

**Delete from `claude.py`:** Lines 293-458 (both methods)
**Delete from `gemini.py`:** Lines 232-302

### Step 1.4: Add `system_prompt` Parameter to `gemini.generate()`

**Current signature (line 51):**
```python
async def generate(
    self,
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 8192,
) -> str:
```

**New signature:**
```python
async def generate(
    self,
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 8192,
) -> str:
    """Generate text completion.

    Args:
        prompt: User prompt
        system_prompt: System instruction (prepended to prompt for Gemini)
        ...
    """
    # Gemini handles system prompt differently
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    # ... rest of method
```

### Step 1.5: Validation Checkpoint

```bash
# Must return NOTHING after lobotomy
grep -rn "You are a" src/neurosynth/llm/
grep -rn "synthesize_section" src/neurosynth/llm/
```

---

## Move 2: Full Jinja2 Switch (Days 3-7)

### Step 2.1: Directory Structure

```
src/neurosynth/
├── templates/                          # NEW
│   ├── macros/
│   │   └── common.j2                   # Reusable macros
│   └── synthesis/
│       ├── base.md.j2                  # Base with {% block %} sections
│       ├── section_descriptive.md.j2   # Extends base (encyclopedia style)
│       ├── section_imperative.md.j2    # Extends base (surgical technique)
│       └── section_category.md.j2      # Category-restricted variant
└── synthesis/
    ├── prompt_engine.py                # NEW: Central rendering engine
    ├── view_models.py                  # NEW: Template-safe models
    └── prompts.py                      # DEPRECATED after migration
```

### Step 2.2: ViewModel Layer

**File:** `src/neurosynth/synthesis/view_models.py`

```python
"""ViewModels for Jinja2 templates - stable interface between models and templates."""

from pydantic import BaseModel
from typing import Optional
from pathlib import Path


class TemplateFigure(BaseModel):
    """Template-safe representation of a figure.

    Maps from internal VisualElement but provides stable interface.
    """
    id: str
    image_type: str  # From ImageType enum value
    caption: str
    page: int
    source_pdf: str = ""
    sequence_id: Optional[str] = None
    is_procedural: bool = False

    @classmethod
    def from_visual_element(cls, ve: "VisualElement") -> "TemplateFigure":
        """Create from internal VisualElement model."""
        from neurosynth.models.visual import VisualElement
        return cls(
            id=ve.id,
            image_type=ve.image_type.value if hasattr(ve.image_type, 'value') else str(ve.image_type),
            caption=ve.caption or "",
            page=ve.page_number,
            source_pdf=str(ve.source_pdf.stem) if ve.source_pdf else "",
            sequence_id=ve.sequence_id,
            is_procedural=ve.is_procedural,
        )

    @classmethod
    def from_dict(cls, data: dict, index: int = 0) -> "TemplateFigure":
        """Create from figure dictionary (used in category synthesis)."""
        return cls(
            id=data.get("id", f"fig_{index}"),
            image_type=data.get("image_type", "unknown"),
            caption=data.get("caption", ""),
            page=data.get("page_number", 0),
            source_pdf=data.get("source_pdf", ""),
            sequence_id=data.get("sequence_id"),
            is_procedural=data.get("is_procedural", False),
        )


class TemplateSource(BaseModel):
    """Template-safe representation of a source/cluster."""
    source_id: str
    source_name: str
    content: str
    page_range: str = ""
    has_conflicts: bool = False

    @classmethod
    def from_cluster(cls, cluster: dict, index: int) -> "TemplateSource":
        """Create from cluster dictionary."""
        return cls(
            source_id=cluster.get("source_id", f"cluster_{index+1}"),
            source_name=cluster.get("source", cluster.get("sources", "Unknown")),
            content=cluster.get("content", ""),
            has_conflicts=cluster.get("has_conflicts", False),
        )


class TemplateSequence(BaseModel):
    """Grouped procedural sequence for templates."""
    id: str
    figures: list[TemplateFigure]


class SynthesisContext(BaseModel):
    """Complete context for synthesis templates."""
    # Core fields
    section_title: str
    section_description: str = ""
    word_target: int = 1500
    tone: str = "descriptive"  # "descriptive" | "imperative"

    # Content
    sources: list[TemplateSource]
    figures: list[TemplateFigure] = []
    grouped_sequences: dict[str, list[TemplateFigure]] = {}

    # Category restrictions (optional)
    allowed_categories: Optional[str] = None
    source_category: Optional[str] = None
    restriction_note: str = ""

    # Feature flags
    use_xml_citations: bool = True

    class Config:
        arbitrary_types_allowed = True
```

### Step 2.3: PromptEngine Core

**File:** `src/neurosynth/synthesis/prompt_engine.py`

```python
"""Centralized prompt rendering engine using Jinja2 templates."""

from pathlib import Path
from typing import Optional, Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from neurosynth import get_logger
from neurosynth.synthesis.view_models import (
    SynthesisContext,
    TemplateFigure,
    TemplateSource,
)

logger = get_logger("synthesis.prompt_engine")

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class PromptEngine:
    """Renders prompts from Jinja2 templates with strict undefined checking."""

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the prompt engine.

        Args:
            template_dir: Custom template directory. Defaults to package templates.
        """
        self.template_dir = template_dir or TEMPLATE_DIR

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            undefined=StrictUndefined,  # CRITICAL: Fail loud on typos
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # Prompts, not HTML
        )

        self._register_filters()
        logger.info(f"Initialized PromptEngine with templates from: {self.template_dir}")

    def _register_filters(self):
        """Register custom Jinja2 filters for prompt formatting."""
        # Guaranteed correct placeholder format matching figure_resolver.py
        self.env.filters['figure_placeholder'] = lambda id: f"[FIGURE: {id}]"
        self.env.filters['truncate'] = lambda s, n=100: (s[:n] + "...") if len(s) > n else s
        self.env.filters['safe_caption'] = lambda s: s.replace("\n", " ").strip() if s else ""
        self.env.filters['source_id_tag'] = lambda id: f"[SOURCE_ID: {id}]"

    def render(
        self,
        template_name: str,
        context: SynthesisContext,
    ) -> tuple[str, str]:
        """Render a synthesis template.

        Args:
            template_name: Template name (e.g., "section_descriptive")
            context: Complete synthesis context

        Returns:
            Tuple of (user_prompt, system_prompt)
        """
        # Pre-render validation
        self._validate_context(context, template_name)

        try:
            template = self.env.get_template(f"synthesis/{template_name}.md.j2")
        except TemplateNotFound:
            logger.error(f"Template not found: synthesis/{template_name}.md.j2")
            raise ValueError(f"Unknown template: {template_name}")

        # Render with context
        rendered = template.render(ctx=context)

        # Split system and user prompts (templates use ---SYSTEM--- marker)
        if "---SYSTEM---" in rendered:
            parts = rendered.split("---SYSTEM---", 1)
            user_prompt = parts[0].strip()
            system_prompt = parts[1].strip() if len(parts) > 1 else ""
        else:
            user_prompt = rendered.strip()
            system_prompt = "You are an expert neurosurgeon and medical writer."

        return user_prompt, system_prompt

    def render_synthesis(
        self,
        section_title: str,
        clusters: list[dict],
        word_target: int = 1500,
        tone: str = "descriptive",
        figures: list[Any] | None = None,
        use_xml_citations: bool = True,
        **kwargs,
    ) -> tuple[str, str]:
        """Convenience method for section synthesis.

        This is the main entry point called from SectionSynthesizer.

        Args:
            section_title: Title of section being synthesized
            clusters: List of cluster dicts with 'content', 'source', etc.
            word_target: Target word count
            tone: "descriptive" or "imperative"
            figures: Optional list of figure dicts or VisualElement objects
            use_xml_citations: Whether to use XML citation anchoring

        Returns:
            Tuple of (user_prompt, system_prompt)
        """
        # Transform to ViewModels
        sources = [TemplateSource.from_cluster(c, i) for i, c in enumerate(clusters)]

        # Handle figures (could be VisualElement, dict, or TemplateFigure)
        template_figures = []
        if figures:
            for i, fig in enumerate(figures):
                if isinstance(fig, TemplateFigure):
                    template_figures.append(fig)
                elif isinstance(fig, dict):
                    template_figures.append(TemplateFigure.from_dict(fig, i))
                else:
                    # Assume VisualElement
                    template_figures.append(TemplateFigure.from_visual_element(fig))

        # Group procedural sequences
        grouped_sequences = {}
        for fig in template_figures:
            if fig.sequence_id:
                grouped_sequences.setdefault(fig.sequence_id, []).append(fig)

        context = SynthesisContext(
            section_title=section_title,
            word_target=word_target,
            tone=tone,
            sources=sources,
            figures=template_figures,
            grouped_sequences=grouped_sequences,
            use_xml_citations=use_xml_citations,
            **kwargs,
        )

        template_name = f"section_{tone}"
        return self.render(template_name, context)

    def _validate_context(self, context: SynthesisContext, template_name: str) -> None:
        """Pre-render validation."""
        errors = []

        if not context.sources:
            errors.append("No source documents provided")

        if context.word_target < 100:
            errors.append(f"Word target too low: {context.word_target}")

        if errors:
            raise ValueError(f"Context validation failed for {template_name}: {errors}")

    def validate_all_templates(self) -> list[str]:
        """Validate all templates for syntax errors (for CI)."""
        errors = []
        synthesis_dir = self.template_dir / "synthesis"

        if not synthesis_dir.exists():
            return [f"Template directory not found: {synthesis_dir}"]

        for template_path in synthesis_dir.glob("*.md.j2"):
            try:
                self.env.get_template(f"synthesis/{template_path.name}")
            except Exception as e:
                errors.append(f"{template_path.name}: {e}")

        return errors


# Module-level singleton
_engine: Optional[PromptEngine] = None


def get_prompt_engine() -> PromptEngine:
    """Get or create the global PromptEngine instance."""
    global _engine
    if _engine is None:
        _engine = PromptEngine()
    return _engine
```

### Step 2.4: Base Template

**File:** `src/neurosynth/templates/synthesis/base.md.j2`

```jinja2
{# Base template for section synthesis - all variants extend this #}

{% block system_prompt %}
---SYSTEM---
You are writing a section of a neurosurgical textbook chapter.
Write in formal academic medical prose. Be comprehensive but not redundant.
{% endblock %}

{% block header %}
Section: {{ ctx.section_title }}
{% if ctx.section_description %}Description: {{ ctx.section_description }}{% endif %}
Word Target: approximately {{ ctx.word_target }} words
{% endblock %}

{% block source_material %}
Source Material:
{% for source in ctx.sources %}
---
[SOURCE_ID: {{ source.source_id }}] From: {{ source.source_name }}
{{ source.content }}
{% endfor %}
{% endblock %}

{% block figure_instructions %}
{% if ctx.figures %}
FIGURE INTEGRATION:
The source material includes available figures with IDs.
You MUST integrate these figures into your text where relevant by inserting the tag [FIGURE: <id>].
- Place the tag at the end of the sentence referencing the figure.
- Use at least 1 figure for every 300 words if available.
- Do not invent figure IDs. Only use those provided below.

AVAILABLE FIGURES:
{% for fig in ctx.figures %}
- [FIGURE_ID: {{ fig.id }}] Type: {{ fig.image_type }}, Caption: {{ fig.caption|safe_caption|truncate(100) }}
{% endfor %}
{% endif %}
{% endblock %}

{% block citation_instructions %}
{% if ctx.use_xml_citations %}
CITATION FORMAT:
Wrap claims with source attribution using XML tags:
<claim source_id="SOURCE_ID">The specific claim from that source.</claim>
{% endif %}
{% endblock %}

{% block requirements %}
Requirements:
- Synthesize the source material into coherent prose
- Integrate citations naturally
- Ensure medical accuracy
- Do not fabricate information not present in sources
{% endblock %}

{% block closing %}
Write the section:
{% endblock %}
```

### Step 2.5: Descriptive Template (Encyclopedia Style)

**File:** `src/neurosynth/templates/synthesis/section_descriptive.md.j2`

```jinja2
{% extends "synthesis/base.md.j2" %}

{% block system_prompt %}
---SYSTEM---
You are writing a section for a neurosurgical textbook chapter.
Write in a descriptive, academic voice suitable for medical literature.
- Use third person and passive voice where appropriate
- Example: "The incidence of this condition is approximately..."
- Example: "Studies have demonstrated that..."
- Maintain scholarly tone with proper citation integration
- Be thorough but avoid redundancy
{% endblock %}

{% block requirements %}
Requirements:
- Synthesize the source material into coherent prose
- Integrate citations naturally (use the format provided in sources)
- Present evidence objectively
- Acknowledge conflicting evidence where present
- Ensure medical accuracy
- Do not fabricate information not present in sources
{% endblock %}
```

### Step 2.6: Imperative Template (Surgical Technique)

**File:** `src/neurosynth/templates/synthesis/section_imperative.md.j2`

```jinja2
{% extends "synthesis/base.md.j2" %}

{% block system_prompt %}
---SYSTEM---
You are writing a surgical technique section for a neurosurgical operative atlas.
Write in an imperative, active voice suitable for surgical instruction.
- Use direct commands: "Position the patient...", "Make the incision..."
- Example: "Identify the superficial temporal artery and protect it during dissection."
- Example: "Elevate the bone flap carefully, avoiding dural tearing."
- Be specific and actionable
- This section should read like a surgical manual
{% endblock %}

{% block requirements %}
Requirements:
- Present steps in logical operative sequence
- Include specific measurements, angles, and landmarks where provided
- Emphasize key decision points and safety considerations
- Include tips for avoiding complications
- Use sources to support technique recommendations
- Do not fabricate steps not supported by source material
{% endblock %}

{% block why_integration %}
"WHY" INTEGRATION:
For each major step, include the rationale at three levels if supported by the source material:
1. Anatomical Why (e.g., "We angle 15° medially because the pedicle axis deviates...")
2. Safety Why (e.g., "This keeps us 3mm from the vertebral artery...")
3. Outcome Why (e.g., "Medial angulation increases pullout strength by 40%...")
{% endblock %}

{% block procedural_sequences %}
{% if ctx.grouped_sequences %}
PROCEDURAL SEQUENCES:
The following figures are part of step-by-step sequences:
{% for seq_id, figs in ctx.grouped_sequences.items() %}
Sequence {{ seq_id }}:
{% for fig in figs %}
  - Step {{ loop.index }}: {{ fig.id|figure_placeholder }} - {{ fig.caption|safe_caption|truncate(80) }}
{% endfor %}
{% endfor %}
Reference these in order when describing the procedure.
{% endif %}
{% endblock %}
```

### Step 2.7: Category-Restricted Template

**File:** `src/neurosynth/templates/synthesis/section_category.md.j2`

```jinja2
{% extends "synthesis/base.md.j2" %}

{% block header %}
Section: {{ ctx.section_title }}
{% if ctx.section_description %}Description: {{ ctx.section_description }}{% endif %}
Word Target: approximately {{ ctx.word_target }} words

CONTENT RESTRICTIONS:
This section should ONLY use content from the {{ ctx.allowed_categories }} category.
{% if ctx.restriction_note %}{{ ctx.restriction_note }}{% endif %}
{% endblock %}

{% block source_material %}
Source Material (from {{ ctx.source_category or ctx.allowed_categories }} sources only):
{% for source in ctx.sources %}
---
[SOURCE_ID: {{ source.source_id }}] From: {{ source.source_name }}
{{ source.content }}
{% endfor %}
{% endblock %}

{% block requirements %}
Requirements:
- Synthesize the source material into coherent prose
- Stay within the topical bounds of this section
- Integrate citations naturally
- Ensure medical accuracy
- Do not include content from other categories
- Do not fabricate information not present in sources
{% endblock %}
```

---

## Step 3: Integration Layer (Day 5-6)

### Step 3.1: Update SectionSynthesizer

**File:** `src/neurosynth/synthesis/section.py`

**Replace the synthesis call in `synthesize_section()` (around line 86):**

```python
# BEFORE (line 86):
content = await self.claude.synthesize_section(
    section_title=entry.title,
    clusters=cluster_data,
    images=images,
)

# AFTER:
from neurosynth.synthesis.prompt_engine import get_prompt_engine

engine = get_prompt_engine()
user_prompt, system_prompt = engine.render_synthesis(
    section_title=entry.title,
    clusters=cluster_data,
    figures=images,
    word_target=self.config.word_target if hasattr(self.config, 'word_target') else 1500,
    tone=self.config.tone if hasattr(self.config, 'tone') else "descriptive",
)

try:
    content = await self.claude.generate(
        prompt=user_prompt,
        system=system_prompt,
    )
except Exception as e:
    logger.warning(f"Claude failed, falling back to Gemini: {e}")
    content = await self.gemini.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
    )
```

**Replace the synthesis call in `synthesize_category_section()` (around line 442):**

```python
# BEFORE (line 442):
content = await self.claude.generate(
    prompt=prompt,
    system=system_prompt,
)

# AFTER:
from neurosynth.synthesis.prompt_engine import get_prompt_engine

engine = get_prompt_engine()
user_prompt, system_prompt = engine.render_synthesis(
    section_title=node.title,
    section_description=node.description or "",
    clusters=source_data,  # Transform node.assigned_sources to cluster format
    figures=figures,
    word_target=node.word_target or 1500,
    tone=node.tone or "descriptive",
    allowed_categories=node.allowed_groups,
    source_category=node.allowed_groups,
)

content = await self.claude.generate(
    prompt=user_prompt,
    system=system_prompt,
)
```

---

## Step 4: Testing Strategy (Day 6-7)

### Test 1: Template Syntax Validation

```python
# tests/test_templates.py
import pytest
from neurosynth.synthesis.prompt_engine import PromptEngine

def test_all_templates_parse():
    """Ensure all templates have valid Jinja2 syntax."""
    engine = PromptEngine()
    errors = engine.validate_all_templates()
    assert errors == [], f"Template errors: {errors}"
```

### Test 2: Figure Placeholder Format

```python
import re

def test_figure_placeholder_format():
    """Ensure figure placeholders match the resolver regex."""
    from neurosynth.synthesis.prompt_engine import PromptEngine
    from neurosynth.synthesis.view_models import SynthesisContext, TemplateSource, TemplateFigure

    engine = PromptEngine()

    context = SynthesisContext(
        section_title="Test Section",
        word_target=500,
        tone="descriptive",
        sources=[TemplateSource(source_id="s1", source_name="Test", content="Content")],
        figures=[TemplateFigure(id="abc123", image_type="anatomical", caption="Test", page=1)],
    )

    user_prompt, _ = engine.render("section_descriptive", context)

    # Must match the regex in figure_resolver.py
    FIGURE_REGEX = r'\[FIGURE:\s*([a-zA-Z0-9_-]+)\]'
    matches = re.findall(FIGURE_REGEX, user_prompt)

    # Should find the figure ID in the available figures section
    assert "abc123" in user_prompt
```

### Test 3: StrictUndefined Catches Typos

```python
def test_strict_undefined_catches_typos():
    """Ensure typos in templates raise errors, not silent failures."""
    from jinja2 import Environment, StrictUndefined

    env = Environment(undefined=StrictUndefined)
    template = env.from_string("Hello {{ naem }}")  # Typo: naem vs name

    with pytest.raises(Exception):  # UndefinedError
        template.render(name="World")
```

### Test 4: End-to-End Render

```python
@pytest.mark.asyncio
async def test_synthesis_render_e2e():
    """Full render with realistic data."""
    from neurosynth.synthesis.prompt_engine import get_prompt_engine

    engine = get_prompt_engine()

    clusters = [
        {"content": "The pterional approach...", "source": "Yasargil 1984", "source_id": "yas84"},
        {"content": "Craniotomy technique...", "source": "Rhoton 2002", "source_id": "rho02"},
    ]

    figures = [
        {"id": "fig1", "image_type": "surgical_step", "caption": "Skin incision", "page_number": 12},
    ]

    user_prompt, system_prompt = engine.render_synthesis(
        section_title="Pterional Craniotomy",
        clusters=clusters,
        figures=figures,
        tone="imperative",
    )

    # Verify structure
    assert "Pterional Craniotomy" in user_prompt
    assert "[FIGURE_ID: fig1]" in user_prompt
    assert "surgical instruction" in system_prompt.lower()
```

---

## Validation Checklist

| Check | Command | Expected |
|-------|---------|----------|
| No prompts in LLM clients | `grep -rn "You are" src/neurosynth/llm/` | Empty |
| All templates parse | `pytest tests/test_templates.py` | Green |
| Figure placeholder format | Regex test | Matches `[FIGURE: ID]` |
| StrictUndefined active | Typo test | Raises error |
| End-to-end synthesis | Manual test | Works |

---

## Migration Sequence

```
Day 1-2: Move 1 (Lobotomize)
├── Remove default system prompt from claude.generate()
├── Add system_prompt param to gemini.generate()
├── Delete synthesize_section() from both clients
├── Update SectionSynthesizer to pass prompts explicitly
└── Run validation greps

Day 3-4: Move 2 (Templates)
├── Create templates/ directory structure
├── Implement view_models.py
├── Implement prompt_engine.py
├── Create base.md.j2 and variants
└── Write template tests

Day 5-6: Integration
├── Wire PromptEngine into SectionSynthesizer
├── Update synthesize_section() call path
├── Update synthesize_category_section() call path
└── Run integration tests

Day 7: Cleanup
├── Delete prompts.py (or mark deprecated)
├── Final validation
├── Documentation update
└── PR review
```

---

## Architecture After Migration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AFTER: CLEAN ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SectionSynthesizer                                                          │
│       │                                                                      │
│       ▼                                                                      │
│  PromptEngine.render_synthesis()                                             │
│       │                                                                      │
│       ├── ViewModels (TemplateFigure, TemplateSource, SynthesisContext)     │
│       │                                                                      │
│       ├── Templates (section_descriptive.md.j2, section_imperative.md.j2)   │
│       │                                                                      │
│       └── Returns (user_prompt, system_prompt)                               │
│                │                                                             │
│                ▼                                                             │
│  claude.generate(prompt=user_prompt, system=system_prompt)                   │
│       │                                                                      │
│       └── Fallback: gemini.generate(prompt, system_prompt)                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Properties:**
- ✅ Single source of truth for prompts (templates)
- ✅ Figure instructions in ALL synthesis paths
- ✅ LLM clients are "dumb pipes"
- ✅ StrictUndefined catches typos
- ✅ ViewModels decouple templates from internal models
- ✅ No hybrid/fallback paths

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Prompts in LLM clients | 0 |
| Template syntax errors | 0 |
| Figure integration in all paths | 100% |
| Test coverage for templates | >90% |
| Migration time | ≤7 days |

**This is the plan. One week. No half-measures.**
