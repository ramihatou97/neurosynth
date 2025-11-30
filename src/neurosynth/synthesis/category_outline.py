"""Category-aware outline generation for structured neurosurgical content.

This module implements dynamic outline templates that respect the separation
between Surgical/Anatomical and Theoretical content, enforcing strict category
boundaries to prevent the "Two-Brain" mixing problem.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from rich.console import Console

console = Console()


class OutlineTemplate(Enum):
    """Available outline templates based on source composition."""
    COMPREHENSIVE_CHAPTER = "comprehensive"  # Balanced Surgical/Theoretical
    PROCEDURAL = "procedural"               # Surgical/Anatomical dominant (User Architecture)
    THEORETICAL = "theoretical"             # Theoretical dominant


@dataclass
class SectionBlueprint:
    """Blueprint for a section with category restrictions."""
    title: str
    description: str
    allowed_groups: Optional[list[str]]  # None = allow all, ["Surgical/Anatomical"] = restrict
    keywords: list[str]
    tone_instruction: str  # "descriptive" or "imperative"
    required: bool = False
    word_target: int = 1000


@dataclass
class OutlineNode:
    """A node in the generated outline with assigned sources."""
    title: str
    level: int
    description: str
    allowed_groups: Optional[list[str]]
    tone: str
    word_target: int
    assigned_sources: list[dict] = field(default_factory=list)
    has_content: bool = False


class CategoryAwareOutlineGenerator:
    """Generate outlines that respect category boundaries.

    This generator:
    1. Analyzes source density (ratio of Surgical to Theoretical content)
    2. Selects an appropriate template based on the ratio
    3. Assigns sources to sections respecting allowed_groups restrictions
    4. Removes empty sections to prevent hallucination
    """

    def __init__(self):
        self.templates = self._build_templates()

    def generate(self, manifest: dict) -> list[OutlineNode]:
        """
        Generate a category-aware outline from a Reference Library manifest.

        Args:
            manifest: The manifest.json from Reference Library containing:
                - topic: Chapter topic
                - search_query: Original search query
                - category_summary: {"Surgical/Anatomical": N, "Theoretical": M}
                - sources: List of source dicts with category_group

        Returns:
            List of OutlineNode objects with sources assigned
        """
        sources = manifest.get("sources", [])
        topic = manifest.get("topic", "Chapter")

        # Step 1: Analyze density
        density = self._analyze_density(sources)
        console.print(f"[blue]Source density: {density:.0%} Surgical/Anatomical[/blue]")

        # Step 2: Select template
        requested_type = manifest.get("template_type")
        template_name = self._select_template(density, requested_type)
        console.print(f"[blue]Selected template: {template_name.value}[/blue]")
        blueprint = self.templates[template_name]

        # Step 3: Assign sources to blueprint sections
        outline = self._assign_content_to_blueprint(sources, blueprint)

        # Step 4: Filter empty sections (except required ones)
        outline = self._filter_empty_sections(outline)

        # Log results
        with_content = sum(1 for n in outline if n.has_content)
        console.print(
            f"[green]Generated outline: {len(outline)} sections "
            f"({with_content} with content)[/green]"
        )

        return outline

    def _analyze_density(self, sources: list[dict]) -> float:
        """Calculate the ratio of Surgical/Anatomical to total categorized sources."""
        surgical = 0
        theoretical = 0

        for source in sources:
            group = source.get("category_group", "")
            if group == "Surgical/Anatomical":
                surgical += 1
            elif group == "Theoretical":
                theoretical += 1

        total = surgical + theoretical
        if total == 0:
            return 0.5  # Default to balanced if no categorized sources

        return surgical / total

    def _select_template(self, density: float, template_type: str = None) -> OutlineTemplate:
        """Select the appropriate template based on type or density."""
        if template_type == "procedural":
            return OutlineTemplate.PROCEDURAL
        elif template_type == "theoretical":
            return OutlineTemplate.THEORETICAL
        
        # Fallback to density-based selection
        if density >= 0.7:
            return OutlineTemplate.PROCEDURAL
        elif density <= 0.3:
            return OutlineTemplate.THEORETICAL
        else:
            return OutlineTemplate.COMPREHENSIVE_CHAPTER

    def _assign_content_to_blueprint(
        self,
        sources: list[dict],
        blueprint: list[SectionBlueprint]
    ) -> list[OutlineNode]:
        """Assign sources to sections respecting category restrictions."""
        # Create outline nodes from blueprint
        nodes = []
        for bp in blueprint:
            node = OutlineNode(
                title=bp.title,
                level=1,  # All top-level for now
                description=bp.description,
                allowed_groups=bp.allowed_groups,
                tone=bp.tone_instruction,
                word_target=bp.word_target,
                assigned_sources=[],
                has_content=False
            )
            nodes.append(node)

        # Track unassigned sources for fallback pass
        unassigned = []

        # Pass 1: Assign by keywords and category restriction
        for source in sources:
            assigned = False
            source_group = source.get("category_group")  # Keep None, don't default to ""
            source_excerpts = " ".join(source.get("context_excerpts", [])).lower()
            source_category = (source.get("category") or "").lower()

            for node in nodes:
                # Check category restriction (only if source HAS a category)
                if node.allowed_groups is not None and source_group is not None:
                    if source_group not in node.allowed_groups:
                        continue  # Categorized source not allowed in this section

                # Check keyword match
                for bp in blueprint:
                    if bp.title == node.title:
                        if self._matches_keywords(source_excerpts, source_category, bp.keywords):
                            node.assigned_sources.append(source)
                            node.has_content = True
                            assigned = True
                            break

                if assigned:
                    break

            if not assigned:
                unassigned.append(source)

        # Pass 2: Knowledge safety net - assign unassigned to most appropriate section
        for source in unassigned:
            source_group = source.get("category_group")  # Keep None, don't default to ""

            # Find best matching section by category
            for node in nodes:
                if node.allowed_groups is None:
                    # Unrestricted section - accepts anything
                    node.assigned_sources.append(source)
                    node.has_content = True
                    break
                elif source_group is None:
                    # Uncategorized source (from search) - can go to ANY section
                    node.assigned_sources.append(source)
                    node.has_content = True
                    break
                elif source_group in node.allowed_groups:
                    # Categorized source matching restricted section
                    node.assigned_sources.append(source)
                    node.has_content = True
                    break

        return nodes

    def _matches_keywords(
        self,
        source_text: str,
        source_category: str,
        keywords: list[str]
    ) -> bool:
        """Check if source matches section keywords."""
        for keyword in keywords:
            if keyword.lower() in source_text or keyword.lower() in source_category:
                return True
        return False

    def _filter_empty_sections(self, outline: list[OutlineNode]) -> list[OutlineNode]:
        """Remove sections with no content (except required ones)."""
        # Find required sections from templates
        required_titles = set()
        for template in self.templates.values():
            for bp in template:
                if bp.required:
                    required_titles.add(bp.title)

        filtered = []
        for node in outline:
            if node.has_content or node.title in required_titles:
                filtered.append(node)
            else:
                console.print(
                    f"[yellow]Removing empty section: {node.title}[/yellow]"
                )

        return filtered

    def _build_templates(self) -> dict[OutlineTemplate, list[SectionBlueprint]]:
        """Build the three outline templates."""
        templates = {}

        # COMPREHENSIVE_CHAPTER: Balanced approach with clear separation
        templates[OutlineTemplate.COMPREHENSIVE_CHAPTER] = [
            SectionBlueprint(
                title="Introduction",
                description="Overview of the topic, clinical importance, and scope",
                allowed_groups=None,  # Both allowed
                keywords=["introduction", "overview", "background", "importance"],
                tone_instruction="descriptive",
                required=True,
                word_target=500
            ),
            SectionBlueprint(
                title="Epidemiology and Natural History",
                description="Incidence, prevalence, demographics, and disease progression",
                allowed_groups=["Theoretical"],
                keywords=["epidemiology", "incidence", "prevalence", "demographics", "natural history"],
                tone_instruction="descriptive",
                word_target=800
            ),
            SectionBlueprint(
                title="Pathophysiology",
                description="Disease mechanisms and underlying biology",
                allowed_groups=["Theoretical"],
                keywords=["pathophysiology", "mechanism", "pathology", "etiology", "biology"],
                tone_instruction="descriptive",
                word_target=1000
            ),
            SectionBlueprint(
                title="Surgical Anatomy",
                description="Anatomical structures relevant to surgical approach",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["anatomy", "anatomical", "neuroanatomy", "structure", "surgical anatomy"],
                tone_instruction="descriptive",
                word_target=1200
            ),
            SectionBlueprint(
                title="Clinical Presentation and Diagnosis",
                description="Signs, symptoms, examination findings, and diagnostic workup",
                allowed_groups=None,  # Both allowed
                keywords=["clinical", "presentation", "symptoms", "diagnosis", "imaging"],
                tone_instruction="descriptive",
                word_target=1000
            ),
            SectionBlueprint(
                title="Surgical Technique",
                description="Step-by-step operative approach",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["technique", "surgical", "operative", "approach", "procedure", "step"],
                tone_instruction="imperative",  # "Position the patient...", "Make the incision..."
                required=True,
                word_target=2500
            ),
            SectionBlueprint(
                title="Complications and Management",
                description="Potential complications and how to prevent/manage them",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["complication", "risk", "adverse", "management", "prevention"],
                tone_instruction="imperative",
                word_target=1000
            ),
            SectionBlueprint(
                title="Outcomes and Prognosis",
                description="Expected results and long-term outlook",
                allowed_groups=["Theoretical"],
                keywords=["outcome", "prognosis", "result", "survival", "follow-up"],
                tone_instruction="descriptive",
                word_target=800
            ),
            SectionBlueprint(
                title="Conclusions",
                description="Summary and key takeaways",
                allowed_groups=None,
                keywords=["conclusion", "summary", "key points"],
                tone_instruction="descriptive",
                required=True,
                word_target=300
            ),
        ]

        # PROCEDURAL: Detailed User Architecture
        templates[OutlineTemplate.PROCEDURAL] = [
            # I. PRE-OPERATIVE MODULE
            SectionBlueprint(
                title="Clinical Context",
                description="Indication hierarchy, patient selection, alternatives, and expected outcomes",
                allowed_groups=["Surgical/Anatomical", "Theoretical"],
                keywords=["indication", "selection", "criteria", "alternative", "outcome"],
                tone_instruction="descriptive",
                required=True,
                word_target=800
            ),
            SectionBlueprint(
                title="Strategic Planning",
                description="Imaging interpretation, 3D trajectory planning, risk stratification, and equipment",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["imaging", "planning", "trajectory", "risk", "equipment"],
                tone_instruction="imperative",
                required=True,
                word_target=1000
            ),
            # II. OPERATIVE EXECUTION
            SectionBlueprint(
                title="Positioning and Exposure",
                description="Patient positioning, biomechanical rationale, and pre-draping checks",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["positioning", "fixation", "setup", "check"],
                tone_instruction="imperative",
                required=True,
                word_target=800
            ),
            SectionBlueprint(
                title="Surface Anatomy and Incision",
                description="Landmark identification, incision design, and danger zones",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["landmark", "incision", "surface", "anatomy", "danger"],
                tone_instruction="imperative",
                required=True,
                word_target=800
            ),
            SectionBlueprint(
                title="Dissection and Approach",
                description="Layered dissection, tissue characteristics, instrument choice, and planes",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["dissection", "approach", "layer", "plane", "instrument"],
                tone_instruction="imperative",
                required=True,
                word_target=1500
            ),
            # III. CRITICAL PROCEDURE PHASE
            SectionBlueprint(
                title="The Definitive Action",
                description="Target identification, instrument prep, execution, and real-time checks",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["action", "resection", "placement", "execution", "target"],
                tone_instruction="imperative",
                required=True,
                word_target=2000
            ),
            # IV. CLOSURE & POST-OP
            SectionBlueprint(
                title="Closure and Post-op",
                description="Layer-specific closure, drains, dressings, and immediate care",
                allowed_groups=["Surgical/Anatomical"],
                keywords=["closure", "suture", "drain", "dressing", "post-op"],
                tone_instruction="imperative",
                required=True,
                word_target=800
            ),
        ]

        # THEORETICAL: Comprehensive Review
        templates[OutlineTemplate.THEORETICAL] = [
            SectionBlueprint(
                title="Introduction",
                description="Overview of the topic and its clinical significance",
                allowed_groups=None,
                keywords=["introduction", "overview", "history", "significance"],
                tone_instruction="descriptive",
                required=True,
                word_target=600
            ),
            SectionBlueprint(
                title="Historical Perspective",
                description="Evolution of understanding and treatment",
                allowed_groups=["Theoretical"],
                keywords=["history", "historical", "evolution", "discovery"],
                tone_instruction="descriptive",
                required=True,
                word_target=600
            ),
            SectionBlueprint(
                title="Epidemiology and Natural History",
                description="Incidence, demographics, and disease progression",
                allowed_groups=["Theoretical"],
                keywords=["epidemiology", "incidence", "demographics", "natural history"],
                tone_instruction="descriptive",
                required=True,
                word_target=800
            ),
            SectionBlueprint(
                title="Pathophysiology and Molecular Biology",
                description="Disease mechanisms, cellular biology, and genetics",
                allowed_groups=["Theoretical"],
                keywords=["pathophysiology", "mechanism", "molecular", "genetics"],
                tone_instruction="descriptive",
                required=True,
                word_target=1200
            ),
            SectionBlueprint(
                title="Clinical Presentation and Diagnosis",
                description="Symptoms, signs, imaging, and diagnostic criteria",
                allowed_groups=None,
                keywords=["clinical", "presentation", "diagnosis", "imaging", "symptoms"],
                tone_instruction="descriptive",
                required=True,
                word_target=1000
            ),
            SectionBlueprint(
                title="Management Strategies",
                description="Medical management, surgical indications, and treatment paradigms",
                allowed_groups=["Theoretical"],
                keywords=["management", "treatment", "indication", "strategy"],
                tone_instruction="descriptive",
                required=True,
                word_target=1200
            ),
            SectionBlueprint(
                title="Outcomes and Evidence",
                description="Clinical trial results, prognosis, and evidence-based outcomes",
                allowed_groups=["Theoretical"],
                keywords=["outcome", "evidence", "trial", "prognosis", "result"],
                tone_instruction="descriptive",
                required=True,
                word_target=1000
            ),
            SectionBlueprint(
                title="Future Directions",
                description="Emerging therapies and research",
                allowed_groups=["Theoretical"],
                keywords=["future", "emerging", "research", "novel"],
                tone_instruction="descriptive",
                required=True,
                word_target=600
            ),
            SectionBlueprint(
                title="Conclusions",
                description="Summary of key theoretical and clinical points",
                allowed_groups=None,
                keywords=["conclusion", "summary"],
                tone_instruction="descriptive",
                required=True,
                word_target=400
            ),
        ]

        return templates

    def get_tone_prompt(self, tone: str) -> str:
        """Get the appropriate writing style prompt for a tone."""
        if tone == "imperative":
            return (
                "Write in an imperative, active voice suitable for surgical instruction. "
                "Use direct commands: 'Position the patient...', 'Make the incision...', "
                "'Identify the landmark...'. Be specific and actionable. "
                "This section should read like a surgical manual."
            )
        else:  # descriptive
            return (
                "Write in a descriptive, academic voice suitable for medical literature. "
                "Use third person and passive voice where appropriate: 'The incidence is...', "
                "'Studies have shown...'. Maintain scholarly tone with proper citations."
            )
