"""Chapter outline generation."""

from dataclasses import dataclass, field

from rich.console import Console

from neurosynth.llm.claude import ClaudeClient
from neurosynth.models.knowledge import KnowledgeCluster
from neurosynth.models.output import Section

console = Console()


@dataclass
class OutlineEntry:
    """An entry in the chapter outline."""

    title: str
    level: int
    description: str = ""
    expected_content: list[str] = field(default_factory=list)
    assigned_clusters: list[KnowledgeCluster] = field(default_factory=list)
    word_target: int = 1000


class OutlineGenerator:
    """Generate neurosurgical chapter outlines."""

    # Standard neurosurgical chapter structure
    STANDARD_SECTIONS = [
        ("Introduction", 1, "Overview, importance, and scope", 500),
        ("Historical Background", 1, "History and evolution of understanding", 400),
        ("Epidemiology", 1, "Incidence, prevalence, demographics", 600),
        ("Anatomy and Neuroanatomy", 1, "Relevant anatomical structures", 1200),
        ("Pathophysiology", 1, "Disease mechanisms and processes", 1000),
        ("Clinical Presentation", 1, "Signs, symptoms, and findings", 800),
        ("Diagnostic Workup", 1, "Imaging, labs, and evaluation", 1000),
        ("Classification", 1, "Grading and staging systems", 600),
        ("Treatment Options", 1, "Overview of management approaches", 800),
        ("Surgical Indications", 1, "When surgery is indicated", 600),
        ("Surgical Technique", 1, "Operative approach and steps", 2000),
        ("Complications and Management", 1, "Risks and their management", 1000),
        ("Outcomes and Prognosis", 1, "Results and long-term outlook", 800),
        ("Controversies and Emerging Trends", 1, "Current debates and future", 600),
        ("Conclusions", 1, "Summary and key points", 300),
    ]

    def __init__(self):
        self.claude = ClaudeClient()

    async def generate_outline(
        self,
        topic: str,
        clusters: list[KnowledgeCluster],
        use_llm: bool = True,
    ) -> list[OutlineEntry]:
        """Generate a chapter outline based on available content."""
        if use_llm and clusters:
            # Use LLM to create adaptive outline
            return await self._generate_adaptive_outline(topic, clusters)
        else:
            # Use standard outline
            return self._generate_standard_outline()

    async def _generate_adaptive_outline(
        self,
        topic: str,
        clusters: list[KnowledgeCluster],
    ) -> list[OutlineEntry]:
        """Generate outline adapted to available content."""
        # Prepare cluster summaries
        cluster_summaries = [
            c.merged_content[:200] if c.merged_content else c.chunks[0].content[:200]
            for c in clusters[:50]  # Limit for API
        ]

        # Get outline from LLM
        raw_outline = await self.claude.generate_outline(topic, cluster_summaries)

        # Convert to OutlineEntry objects
        entries = []
        for item in raw_outline:
            entry = OutlineEntry(
                title=item.get("title", "Section"),
                level=item.get("level", 1),
                description=item.get("description", ""),
                expected_content=item.get("expected_clusters", []),
            )
            entries.append(entry)

        # Ensure we have minimum required sections
        entries = self._ensure_required_sections(entries)

        return entries

    def _generate_standard_outline(self) -> list[OutlineEntry]:
        """Generate standard neurosurgical outline."""
        entries = []
        for title, level, description, word_target in self.STANDARD_SECTIONS:
            entry = OutlineEntry(
                title=title,
                level=level,
                description=description,
                word_target=word_target,
            )
            entries.append(entry)
        return entries

    def _ensure_required_sections(
        self,
        entries: list[OutlineEntry],
    ) -> list[OutlineEntry]:
        """Ensure minimum required sections exist."""
        required = ["Introduction", "Surgical Technique", "Conclusions"]
        existing_titles = {e.title.lower() for e in entries}

        for req in required:
            if req.lower() not in existing_titles:
                # Find appropriate position and insert
                if req == "Introduction":
                    entries.insert(0, OutlineEntry(title=req, level=1))
                elif req == "Conclusions":
                    entries.append(OutlineEntry(title=req, level=1))
                else:
                    # Insert near the end
                    entries.insert(-1, OutlineEntry(title=req, level=1))

        return entries

    async def assign_clusters_to_sections(
        self,
        outline: list[OutlineEntry],
        clusters: list[KnowledgeCluster],
    ) -> list[OutlineEntry]:
        """Assign knowledge clusters to appropriate outline sections."""
        # Build section keyword mapping
        section_keywords = self._build_section_keywords(outline)

        # Score each cluster for each section
        for cluster in clusters:
            best_section = self._find_best_section(cluster, outline, section_keywords)
            if best_section:
                best_section.assigned_clusters.append(cluster)
                cluster.target_section = best_section.title

        # Log assignment statistics
        assigned = sum(len(e.assigned_clusters) for e in outline)
        unassigned = len(clusters) - assigned
        console.print(
            f"[green]Assigned {assigned} clusters to sections "
            f"({unassigned} unassigned)[/green]"
        )

        return outline

    def _build_section_keywords(
        self,
        outline: list[OutlineEntry],
    ) -> dict[str, set[str]]:
        """Build keyword sets for each section."""
        keyword_map = {
            "introduction": {"introduction", "overview", "background", "scope"},
            "history": {"history", "historical", "evolution", "discovery"},
            "epidemiology": {"epidemiology", "incidence", "prevalence", "demographics"},
            "anatomy": {"anatomy", "anatomical", "neuroanatomy", "structure", "region"},
            "pathophysiology": {
                "pathophysiology",
                "mechanism",
                "pathology",
                "etiology",
            },
            "clinical": {
                "clinical",
                "presentation",
                "symptoms",
                "signs",
                "examination",
            },
            "diagnostic": {
                "diagnostic",
                "imaging",
                "mri",
                "ct",
                "workup",
                "evaluation",
            },
            "classification": {"classification", "grading", "staging", "type"},
            "treatment": {"treatment", "therapy", "management", "conservative"},
            "surgical indications": {
                "indication",
                "criteria",
                "selection",
                "candidate",
            },
            "surgical technique": {
                "technique",
                "surgical",
                "operative",
                "approach",
                "procedure",
            },
            "complications": {"complication", "risk", "adverse", "morbidity"},
            "outcomes": {"outcome", "prognosis", "result", "survival", "follow-up"},
            "controversies": {"controversy", "debate", "emerging", "future", "novel"},
            "conclusions": {"conclusion", "summary", "key points"},
        }

        section_keywords = {}
        for entry in outline:
            title_lower = entry.title.lower()

            # Find matching keyword set
            for key, keywords in keyword_map.items():
                if key in title_lower or any(k in title_lower for k in keywords):
                    section_keywords[entry.title] = keywords
                    break

            # Default keywords from title
            if entry.title not in section_keywords:
                section_keywords[entry.title] = set(title_lower.split())

        return section_keywords

    def _find_best_section(
        self,
        cluster: KnowledgeCluster,
        outline: list[OutlineEntry],
        section_keywords: dict[str, set[str]],
    ) -> OutlineEntry | None:
        """Find the best section for a cluster."""
        # Get cluster content
        content = (
            cluster.merged_content
            if cluster.merged_content
            else cluster.chunks[0].content if cluster.chunks else ""
        ).lower()

        # Score each section
        best_score = 0
        best_section = None

        for entry in outline:
            keywords = section_keywords.get(entry.title, set())
            score = sum(1 for k in keywords if k in content)

            if score > best_score:
                best_score = score
                best_section = entry

        # Use topic hint if available
        if cluster.topic:
            for entry in outline:
                if cluster.topic.lower() in entry.title.lower():
                    return entry

        return best_section if best_score > 0 else outline[0]

    def to_sections(self, outline: list[OutlineEntry]) -> list[Section]:
        """Convert outline entries to Section objects."""
        sections = []
        for entry in outline:
            section = Section(
                title=entry.title,
                level=entry.level,
                clusters=entry.assigned_clusters,
            )
            sections.append(section)
        return sections
