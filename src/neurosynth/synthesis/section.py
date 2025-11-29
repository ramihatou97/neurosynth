"""Section-by-section synthesis."""

import asyncio
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.llm.claude import ClaudeClient
from neurosynth.models.output import Chapter, Section
from neurosynth.models.document import Source, DocumentFormat
from neurosynth.models.visual import VisualElement, ImageType, FigurePlate
from neurosynth.synthesis.conflicts import ConflictHandler
from neurosynth.synthesis.outline import OutlineEntry
from neurosynth.synthesis.prompts import (
    SECTION_ENHANCEMENT_PROMPT,
    SUBSECTION_GENERATION_PROMPT,
    SECTION_SYNTHESIS_DESCRIPTIVE,
    SECTION_SYNTHESIS_IMPERATIVE,
    CATEGORY_AWARE_SECTION_PROMPT,
)

if TYPE_CHECKING:
    from neurosynth.synthesis.checkpoint import SynthesisCheckpoint

console = Console()


@dataclass
class SynthesisConfig:
    """Configuration for synthesis."""

    min_words_per_section: int = 300
    max_words_per_section: int = 3000
    include_citations: bool = True
    present_conflicts: bool = True
    academic_style: bool = True


class SectionSynthesizer:
    """Synthesize chapter sections from knowledge clusters."""

    def __init__(self, config: SynthesisConfig | None = None):
        self.config = config or SynthesisConfig()
        self.claude = ClaudeClient()
        self.conflict_handler = ConflictHandler()

    async def synthesize_section(
        self,
        entry: OutlineEntry,
    ) -> Section:
        """Synthesize a single section from its assigned clusters."""
        section = Section(
            title=entry.title,
            level=entry.level,
            clusters=entry.assigned_clusters,
        )

        if not entry.assigned_clusters:
            console.print(f"[yellow]Warning: No content for section '{entry.title}'[/yellow]")
            section.content = f"[Content pending for {entry.title}]"
            return section

        # Prepare cluster content for synthesis
        cluster_data = []
        for cluster in entry.assigned_clusters:
            content = cluster.merged_content or (
                cluster.chunks[0].content if cluster.chunks else ""
            )
            cluster_data.append(
                {
                    "content": content,
                    "sources": cluster.get_citations(),
                    "has_conflicts": cluster.has_conflicts,
                }
            )

        # Calculate word target
        word_target = entry.word_target or self._estimate_word_target(entry)

        # Synthesize content using Claude
        console.print(f"  Synthesizing: {entry.title}", style="dim")
        content = await self.claude.synthesize_section(
            section_title=entry.title,
            clusters=cluster_data,
            word_target=word_target,
        )

        # Add conflict presentations if any
        if self.config.present_conflicts:
            conflict_text = self.conflict_handler.generate_conflict_text(entry.assigned_clusters)
            if conflict_text:
                content += f"\n\n{conflict_text}"

        section.content = content
        section.word_count = len(content.split())
        section.has_conflicts = any(c.has_conflicts for c in entry.assigned_clusters)

        return section

    async def synthesize_chapter(
        self,
        topic: str,
        outline: list[OutlineEntry],
        max_concurrent: int | None = None,
        checkpoint: Optional["SynthesisCheckpoint"] = None,
    ) -> Chapter:
        """Synthesize complete chapter from outline with parallel section synthesis.

        Args:
            topic: Chapter topic/title
            outline: List of outline entries to synthesize
            max_concurrent: Maximum concurrent Claude API calls (default from config)
            checkpoint: Optional checkpoint for immediate section saving
        """
        settings = get_settings()
        max_concurrent = max_concurrent or settings.synthesis_concurrency
        console.print(f"[blue]Synthesizing chapter: {topic} (parallel, max {max_concurrent} concurrent)[/blue]")

        # Create chapter
        chapter = Chapter(
            title=topic,
            topic=topic,
        )

        # Semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(max_concurrent)

        # Track progress
        completed = 0
        total = len(outline)
        failed_sections = []

        async def synthesize_with_limit(entry: OutlineEntry, index: int) -> tuple[int, Section, bool]:
            """Synthesize section with immediate checkpoint save.

            Returns:
                Tuple of (index, section, success_flag)
            """
            nonlocal completed
            async with semaphore:
                try:
                    section = await self.synthesize_section(entry)
                    completed += 1
                    console.print(f"  [dim]Completed {completed}/{total} sections[/dim]")

                    # IMMEDIATE SAVE to checkpoint after each section
                    if checkpoint:
                        checkpoint.save_section(index, section.content, title=entry.title)

                    return index, section, True

                except Exception as e:
                    completed += 1
                    console.print(f"  [red]Section {index} ({entry.title}) failed: {e}[/red]")

                    # Log error and create placeholder section
                    if checkpoint:
                        checkpoint.log_error(f"Section {index} ({entry.title}) failed: {e}")
                        # Save placeholder so user knows which section failed
                        checkpoint.save_section(
                            index,
                            f"[SYNTHESIS FAILED]\n\nError: {e}\n\nSection: {entry.title}",
                            title=f"[FAILED] {entry.title}"
                        )

                    # Create placeholder section instead of losing everything
                    placeholder = Section(
                        title=entry.title,
                        level=entry.level,
                        clusters=entry.assigned_clusters,
                    )
                    placeholder.content = f"[Section synthesis failed: {e}]"
                    placeholder.word_count = 0

                    return index, placeholder, False

        # Create tasks for all sections
        tasks = [
            synthesize_with_limit(entry, i)
            for i, entry in enumerate(outline)
        ]

        # Execute all in parallel with semaphore limiting concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sort by original index to maintain order, handle errors
        sections_with_index = []
        for result in results:
            if isinstance(result, Exception):
                # This shouldn't happen anymore since we catch inside synthesize_with_limit
                console.print(f"[red]Unexpected error in synthesis task: {result}[/red]")
                if checkpoint:
                    checkpoint.log_error(f"Unexpected synthesis task error: {result}")
                continue

            index, section, success = result
            sections_with_index.append((index, section))
            if not success:
                failed_sections.append(index)

        # Sort by index and extract sections
        sections_with_index.sort(key=lambda x: x[0])
        for _, section in sections_with_index:
            chapter.sections.append(section)

        # Report failures
        if failed_sections:
            console.print(f"[yellow]Warning: {len(failed_sections)} section(s) failed synthesis[/yellow]")
            if checkpoint:
                checkpoint._update_stage_status("sections", f"partial ({len(failed_sections)} failed)")

        # Generate abstract (must wait for all sections)
        all_content = "\n\n".join(s.content for s in chapter.sections if not s.content.startswith("[Section"))

        try:
            chapter.abstract = await self.claude.generate_abstract(all_content, topic)
        except Exception as e:
            console.print(f"[yellow]Abstract generation failed: {e}[/yellow]")
            if checkpoint:
                checkpoint.log_error(f"Abstract generation failed: {e}")
            chapter.abstract = "[Abstract generation failed]"

        # Extract keywords
        try:
            chapter.keywords = await self.claude.extract_keywords(all_content)
        except Exception as e:
            console.print(f"[yellow]Keyword extraction failed: {e}[/yellow]")
            if checkpoint:
                checkpoint.log_error(f"Keyword extraction failed: {e}")
            chapter.keywords = []

        # Collect bibliography
        chapter.bibliography = self._collect_sources(outline)

        # Calculate statistics
        chapter._calculate_stats()

        console.print(
            f"[green]Chapter complete: {chapter.total_words} words, "
            f"{len(chapter.bibliography)} sources[/green]"
        )

        return chapter

    async def enhance_section(
        self,
        section: Section,
        additional_context: str = "",
    ) -> Section:
        """Enhance an existing section with additional detail."""
        prompt = SECTION_ENHANCEMENT_PROMPT.format(
            content=section.content, context=additional_context
        )

        enhanced = await self.claude.generate(prompt, temperature=0.3)
        section.content = enhanced
        section.word_count = len(enhanced.split())

        return section

    # ==================== Category-Aware Synthesis ====================

    async def synthesize_category_section(
        self,
        node,  # OutlineNode from category_outline
    ) -> Section:
        """
        Synthesize a section from a CategoryAwareOutlineGenerator node.

        This method respects:
        - allowed_groups restrictions (only uses assigned sources)
        - tone instructions (imperative vs descriptive)
        """
        from neurosynth.synthesis.category_outline import OutlineNode
        import uuid

        section = Section(
            title=node.title,
            level=node.level,
            clusters=[],  # No clusters in this path
        )

        if not node.assigned_sources:
            console.print(f"[yellow]Warning: No content for section '{node.title}'[/yellow]")
            section.content = f"[Content pending for {node.title}]"
            return section

        # Prepare source content
        source_content = self._prepare_source_content(node.assigned_sources)

        # Select prompt based on tone
        if node.tone == "imperative":
            prompt = SECTION_SYNTHESIS_IMPERATIVE.format(
                section_title=node.title,
                section_description=node.description,
                word_target=node.word_target,
                source_content=source_content,
            )
        else:
            prompt = SECTION_SYNTHESIS_DESCRIPTIVE.format(
                section_title=node.title,
                section_description=node.description,
                word_target=node.word_target,
                source_content=source_content,
            )

        # Synthesize content using Claude
        console.print(f"  Synthesizing [{node.tone}]: {node.title}", style="dim")
        content = await self.claude.generate(prompt, temperature=0.3)

        # Collect visuals from assigned sources
        visuals = []
        for source in node.assigned_sources:
            for fig in source.get("figures", []):
                if fig.get("image_path"):
                    try:
                        visual = VisualElement(
                            id=fig.get("id") or str(uuid.uuid4())[:8],
                            image_path=fig.get("image_path"),
                            image_type=fig.get("image_type", "unknown"),
                            caption=fig.get("caption", ""),
                            page_number=fig.get("page_number", 0),
                        )
                        visuals.append(visual)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not load visual: {e}[/yellow]")

        # Assign visuals to section
        if visuals:
            # Simple heuristic: first 2 high-priority inline, rest in plate
            high_priority = [v for v in visuals if v.image_type in ("surgical_step", "anatomical")]
            other = [v for v in visuals if v not in high_priority]
            
            # Sort high priority by page number
            high_priority.sort(key=lambda v: v.page_number)
            
            section.inline_figures = high_priority[:2]
            plate_figures = high_priority[2:] + other
            
            if plate_figures:
                section.figure_plate = FigurePlate(
                    section_title=f"{node.title} - Visuals",
                    figures=plate_figures
                )

        section.content = content
        section.word_count = len(content.split())

        return section

    async def synthesize_chapter_from_category_outline(
        self,
        topic: str,
        outline,  # list[OutlineNode]
        manifest: Optional[dict] = None,
        max_concurrent: int | None = None,
        checkpoint: Optional["SynthesisCheckpoint"] = None,
    ) -> Chapter:
        """
        Synthesize complete chapter from category-aware outline with parallel synthesis.

        Args:
            topic: Chapter topic
            outline: List of OutlineNode objects with assigned sources
            manifest: Optional manifest dict for metadata
            max_concurrent: Maximum concurrent Claude API calls (default from config)
            checkpoint: Optional checkpoint for immediate section saving
        """
        settings = get_settings()
        max_concurrent = max_concurrent or settings.synthesis_concurrency
        console.print(f"[blue]Synthesizing category-aware chapter: {topic} (parallel, max {max_concurrent} concurrent)[/blue]")

        # Create chapter
        chapter = Chapter(
            title=topic,
            topic=topic,
        )

        # Semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(max_concurrent)

        # Track progress
        completed = 0
        total = len(outline)
        failed_sections = []

        async def synthesize_with_limit(node, index: int) -> tuple[int, Section, bool]:
            """Synthesize section with immediate checkpoint save."""
            nonlocal completed
            async with semaphore:
                try:
                    section = await self.synthesize_category_section(node)
                    completed += 1
                    console.print(f"  [dim]Completed {completed}/{total} sections[/dim]")

                    # IMMEDIATE SAVE to checkpoint
                    if checkpoint:
                        checkpoint.save_section(index, section.content, title=node.title)

                    return index, section, True

                except Exception as e:
                    completed += 1
                    console.print(f"  [red]Section {index} ({node.title}) failed: {e}[/red]")

                    if checkpoint:
                        checkpoint.log_error(f"Section {index} ({node.title}) failed: {e}")
                        checkpoint.save_section(
                            index,
                            f"[SYNTHESIS FAILED]\n\nError: {e}\n\nSection: {node.title}",
                            title=f"[FAILED] {node.title}"
                        )

                    # Create placeholder section
                    placeholder = Section(
                        title=node.title,
                        level=node.level,
                        clusters=[],
                    )
                    placeholder.content = f"[Section synthesis failed: {e}]"
                    placeholder.word_count = 0

                    return index, placeholder, False

        # Create tasks for all sections
        tasks = [
            synthesize_with_limit(node, i)
            for i, node in enumerate(outline)
        ]

        # Execute all in parallel with semaphore limiting concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sort by original index to maintain order, handle errors
        sections_with_index = []
        for result in results:
            if isinstance(result, Exception):
                console.print(f"[red]Unexpected error in synthesis task: {result}[/red]")
                if checkpoint:
                    checkpoint.log_error(f"Unexpected synthesis task error: {result}")
                continue

            index, section, success = result
            sections_with_index.append((index, section))
            if not success:
                failed_sections.append(index)

        # Sort by index and extract sections
        sections_with_index.sort(key=lambda x: x[0])
        for _, section in sections_with_index:
            chapter.sections.append(section)

        # Report failures
        if failed_sections:
            console.print(f"[yellow]Warning: {len(failed_sections)} section(s) failed synthesis[/yellow]")
            if checkpoint:
                checkpoint._update_stage_status("sections", f"partial ({len(failed_sections)} failed)")

        # Generate abstract (must wait for all sections)
        all_content = "\n\n".join(s.content for s in chapter.sections if not s.content.startswith("[Section"))

        try:
            chapter.abstract = await self.claude.generate_abstract(all_content, topic)
        except Exception as e:
            console.print(f"[yellow]Abstract generation failed: {e}[/yellow]")
            if checkpoint:
                checkpoint.log_error(f"Abstract generation failed: {e}")
            chapter.abstract = "[Abstract generation failed]"

        # Extract keywords
        try:
            chapter.keywords = await self.claude.extract_keywords(all_content)
        except Exception as e:
            console.print(f"[yellow]Keyword extraction failed: {e}[/yellow]")
            if checkpoint:
                checkpoint.log_error(f"Keyword extraction failed: {e}")
            chapter.keywords = []

        # Collect bibliography from manifest sources
        if manifest:
            chapter.bibliography = self._collect_manifest_sources(manifest)

        # Calculate statistics
        chapter._calculate_stats()

        console.print(
            f"[green]Chapter complete: {chapter.total_words} words, "
            f"{len(chapter.bibliography)} sources[/green]"
        )

        return chapter

    def _prepare_source_content(self, sources: list[dict]) -> str:
        """Prepare source content for synthesis prompt."""
        content_parts = []

        for i, source in enumerate(sources, 1):
            original_source = source.get("original_source", "Unknown")
            category = source.get("category", "")
            excerpts = source.get("context_excerpts", [])
            full_text = source.get("full_text", "")
            pages = source.get("pages", [])

            part = f"--- Source {i}: {original_source}"
            if category:
                part += f" [{category}]"
            if pages:
                part += f" (pages {pages[0]}-{pages[-1]})"
            part += " ---\n"

            if full_text:
                part += full_text
            elif excerpts:
                part += "\n".join(excerpts)
            else:
                part += "[No excerpt available]"

            content_parts.append(part)

        return "\n\n".join(content_parts)

    def _collect_manifest_sources(self, manifest: dict) -> list:
        """Collect unique sources from manifest for bibliography."""
        sources = []
        seen = set()

        from pathlib import Path

        for source in manifest.get("sources", []):
            original = source.get("original_source", "")
            if original and original not in seen:
                seen.add(original)
                
                # Create Source object
                path_str = source.get("original_path", original)
                path = Path(path_str)
                
                # Determine format or default to PDF
                try:
                    fmt = DocumentFormat.from_path(path)
                except ValueError:
                    fmt = DocumentFormat.PDF

                src_obj = Source(
                    path=path,
                    format=fmt,
                    title=original,
                    authors=source.get("authors", ["Unknown"]),
                    year=source.get("year"),
                    publisher=source.get("publisher"),
                )
                sources.append(src_obj)

        return sources

    def _estimate_word_target(self, entry: OutlineEntry) -> int:
        """Estimate word target based on section type and content."""
        # Base targets by section type
        targets = {
            "introduction": 500,
            "anatomy": 1200,
            "surgical technique": 2000,
            "pathophysiology": 1000,
            "complications": 1000,
            "outcomes": 800,
            "conclusions": 300,
        }

        title_lower = entry.title.lower()
        for key, target in targets.items():
            if key in title_lower:
                return target

        # Scale by number of clusters
        cluster_count = len(entry.assigned_clusters)
        return max(300, min(500 * cluster_count, 2000))

    def _collect_sources(
        self,
        outline: list[OutlineEntry],
    ) -> list:
        """Collect all unique sources from outline."""

        sources = []
        seen_ids = set()

        for entry in outline:
            for cluster in entry.assigned_clusters:
                for source in cluster.sources:
                    if source.id not in seen_ids:
                        seen_ids.add(source.id)
                        sources.append(source)

        return sorted(sources, key=lambda s: s.citation_key)


class SubsectionGenerator:
    """Generate subsections for detailed sections."""

    def __init__(self):
        self.claude = ClaudeClient()

    async def generate_subsections(
        self,
        section: Section,
        max_subsections: int = 5,
    ) -> list[Section]:
        """Break a section into logical subsections."""
        if section.word_count < 800:
            return []  # Too short to subdivide

        prompt = SUBSECTION_GENERATION_PROMPT.format(
            title=section.title, content=section.content, max_subsections=max_subsections
        )

        response = await self.claude.generate(prompt, temperature=0.1)

        import json

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                titles = json.loads(response[start:end])

                subsections = []
                for title in titles[:max_subsections]:
                    subsection = Section(
                        title=title,
                        level=section.level + 1,
                    )
                    subsections.append(subsection)
                return subsections
        except json.JSONDecodeError:
            pass

        return []
