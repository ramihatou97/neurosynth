"""Main pipeline coordinator for NeuroSynth."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.models.document import ContentChunk, Document
from neurosynth.models.knowledge import KnowledgeBase, KnowledgeCluster
from neurosynth.models.output import Chapter

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement

console = Console()


@dataclass
class PipelineConfig:
    """Configuration for the synthesis pipeline."""

    # Input
    source_dir: Path = field(default_factory=lambda: Path("sources"))
    supported_formats: list[str] = field(default_factory=lambda: [".pdf", ".epub", ".docx", ".txt"])

    # Processing
    chunk_size: int = 1000
    chunk_overlap: int = 100
    similarity_threshold: float = 0.92
    use_cache: bool = True

    # Concurrency
    parallel_parse_concurrency: int = 4  # Max concurrent document parsing tasks

    # Output
    output_dir: Path = field(default_factory=lambda: Path("output"))
    output_format: str = "latex"  # "latex" or "markdown"

    # Features
    detect_conflicts: bool = True
    use_llm_chunking: bool = False
    generate_subsections: bool = False

    # Visual Processing
    enable_visual_extraction: bool = True
    enable_visual_embeddings: bool = True
    max_inline_figures: int = 3
    visual_relevance_threshold: float = 0.3

    # Clustering
    use_faiss_clustering: bool = True  # Use FAISS for large-scale clustering (if available)


@dataclass
class PipelineState:
    """Current state of the pipeline."""

    documents: list[Document] = field(default_factory=list)
    all_chunks: list[ContentChunk] = field(default_factory=list)
    clusters: list[KnowledgeCluster] = field(default_factory=list)
    knowledge_base: KnowledgeBase | None = None
    chapter: Chapter | None = None

    # Visual content
    all_visuals: list["VisualElement"] = field(default_factory=list)
    visuals_embedded: bool = False

    # Progress tracking
    current_stage: str = "initialized"
    stages_completed: list[str] = field(default_factory=list)

    # Metrics
    metrics: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Main orchestrator for the knowledge synthesis pipeline."""

    STAGES = [
        "parse",
        "chunk",
        "deduplicate",
        "embed_visuals",  # New: Generate visual embeddings
        "cluster",
        "associate_visuals",  # New: Associate visuals to clusters
        "merge",
        "outline",
        "synthesize",
        "output",
    ]

    def __init__(
        self,
        topic: str,
        config: PipelineConfig | None = None,
    ):
        self.topic = topic
        self.config = config or PipelineConfig()
        self.state = PipelineState()

        # Check if visual processing is available
        from neurosynth.llm import VISUAL_AVAILABLE
        if self.config.enable_visual_extraction and not VISUAL_AVAILABLE:
            console.print(
                "[yellow]Visual extraction disabled: optional dependencies not installed.\n"
                "Install with: pip install neurosynth[visual][/yellow]"
            )
            self.config.enable_visual_extraction = False
            self.config.enable_visual_embeddings = False

        # Callbacks for progress reporting
        self._callbacks: dict[str, list[Callable]] = {
            "stage_start": [],
            "stage_complete": [],
            "error": [],
        }

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for pipeline events."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, **kwargs) -> None:
        """Emit an event to callbacks."""
        for callback in self._callbacks.get(event, []):
            callback(**kwargs)

    async def run(self) -> Chapter:
        """Run the complete synthesis pipeline."""
        console.print(f"\n[bold blue]NeuroSynth Pipeline: {self.topic}[/bold blue]\n")

        try:
            # Stage 1: Parse documents (includes image extraction if enabled)
            await self._run_stage("parse", self._parse_documents)

            # Stage 2: Chunk content
            await self._run_stage("chunk", self._chunk_documents)

            # Stage 3: Exact deduplication
            await self._run_stage("deduplicate", self._deduplicate_exact)

            # Stage 4: Generate visual embeddings (if enabled)
            if self.config.enable_visual_embeddings and self.state.all_visuals:
                await self._run_stage("embed_visuals", self._embed_visuals)

            # Stage 5: Semantic clustering
            await self._run_stage("cluster", self._cluster_chunks)

            # Stage 6: Associate visuals to clusters
            if self.config.enable_visual_extraction and self.state.all_visuals:
                await self._run_stage("associate_visuals", self._associate_visuals)

            # Stage 7: Merge clusters
            await self._run_stage("merge", self._merge_clusters)

            # Stage 8: Generate outline
            await self._run_stage("outline", self._generate_outline)

            # Stage 9: Synthesize content
            await self._run_stage("synthesize", self._synthesize_chapter)

            # Stage 10: Generate output
            await self._run_stage("output", self._generate_output)

            console.print("\n[bold green]Pipeline complete![/bold green]")
            self._print_summary()

            return self.state.chapter

        except Exception as e:
            self._emit("error", error=e, stage=self.state.current_stage)
            console.print(
                f"\n[bold red]Pipeline failed at {self.state.current_stage}: {e}[/bold red]"
            )
            raise

    async def _run_stage(self, stage: str, func: Callable) -> None:
        """Run a pipeline stage with progress tracking."""
        self.state.current_stage = stage
        self._emit("stage_start", stage=stage)
        console.print(f"[blue]▶ Stage: {stage.upper()}[/blue]")

        await func()

        self.state.stages_completed.append(stage)
        self._emit("stage_complete", stage=stage)
        console.print(f"[green]✓ {stage.upper()} complete[/green]\n")

    async def _parse_documents(self) -> None:
        """Parse all source documents in parallel with concurrency control."""
        from neurosynth.parsers import ParserFactory

        source_files = []
        for ext in self.config.supported_formats:
            source_files.extend(self.config.source_dir.glob(f"*{ext}"))

        if not source_files:
            raise ValueError(f"No source files found in {self.config.source_dir}")

        console.print(f"  Found {len(source_files)} source files")

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.parallel_parse_concurrency)
        parse_errors: list[tuple[Path, Exception]] = []

        async def parse_single_file(file_path: Path) -> Document | None:
            """Parse a single file with semaphore-controlled concurrency."""
            async with semaphore:
                try:
                    parser = ParserFactory.get_parser(file_path)
                    doc = await parser.parse(file_path)
                    console.print(f"  ✓ Parsed: {file_path.name}", style="dim")
                    return doc
                except Exception as e:
                    parse_errors.append((file_path, e))
                    console.print(f"  [red]✗ Error parsing {file_path.name}: {e}[/red]")
                    return None

        # Parse all documents in parallel (bounded by semaphore)
        console.print(
            f"  Parsing with {self.config.parallel_parse_concurrency} concurrent workers...",
            style="dim",
        )
        results = await asyncio.gather(
            *[parse_single_file(fp) for fp in source_files],
            return_exceptions=False,  # Exceptions handled inside parse_single_file
        )

        # Collect successful results
        for doc in results:
            if doc is not None:
                self.state.documents.append(doc)

                # Collect visual elements from parsed documents
                if self.config.enable_visual_extraction and doc.visual_elements:
                    self.state.all_visuals.extend(doc.visual_elements)

        # Report results
        if parse_errors:
            console.print(
                f"  [yellow]Warning: {len(parse_errors)} files failed to parse[/yellow]"
            )

        self.state.metrics["documents_parsed"] = len(self.state.documents)
        self.state.metrics["documents_failed"] = len(parse_errors)
        self.state.metrics["visuals_extracted"] = len(self.state.all_visuals)

    async def _chunk_documents(self) -> None:
        """Chunk all parsed documents."""
        from neurosynth.chunking import ChunkingStrategy, SemanticChunker

        strategy = (
            ChunkingStrategy.SEMANTIC if self.config.use_llm_chunking else ChunkingStrategy.HYBRID
        )

        chunker = SemanticChunker(
            target_size=self.config.chunk_size,
            overlap=self.config.chunk_overlap,
            strategy=strategy,
        )

        for doc in self.state.documents:
            chunks = await chunker.chunk_document(doc)
            self.state.all_chunks.extend(chunks)

        self.state.metrics["total_chunks"] = len(self.state.all_chunks)
        console.print(f"  Created {len(self.state.all_chunks)} chunks")

    async def _deduplicate_exact(self) -> None:
        """Remove exact duplicate chunks."""
        from neurosynth.dedup.embeddings import ExactDeduplicator

        original_count = len(self.state.all_chunks)
        self.state.all_chunks = ExactDeduplicator.deduplicate(self.state.all_chunks)

        removed = original_count - len(self.state.all_chunks)
        self.state.metrics["exact_duplicates_removed"] = removed

    async def _embed_visuals(self) -> None:
        """Generate visual embeddings using ColPali."""
        if not self.state.all_visuals:
            console.print("  [dim]No visuals to embed[/dim]")
            return

        try:
            from neurosynth.llm.colpali import get_colpali_client
            from neurosynth.dedup.qdrant_store import get_qdrant_store

            console.print(f"  Generating embeddings for {len(self.state.all_visuals)} images...")

            # Get ColPali client and generate embeddings
            colpali = get_colpali_client()
            self.state.all_visuals = await colpali.embed_visual_elements(
                self.state.all_visuals
            )

            # Count embedded visuals
            embedded_count = sum(
                1 for v in self.state.all_visuals if v.visual_embedding is not None
            )
            self.state.visuals_embedded = True
            self.state.metrics["visuals_embedded"] = embedded_count

            # Store in Qdrant for persistent search
            qdrant = get_qdrant_store()
            stored_count = await qdrant.store_visual_elements(self.state.all_visuals)
            self.state.metrics["visuals_stored"] = stored_count

            console.print(f"  Generated {embedded_count} visual embeddings")
            console.print(f"  Stored {stored_count} embeddings in Qdrant")

        except ImportError as e:
            console.print(
                f"  [yellow]Visual embedding skipped (dependencies not installed): {e}[/yellow]"
            )
            self.state.metrics["visuals_embedded"] = 0
        except Exception as e:
            console.print(f"  [yellow]Visual embedding failed: {e}[/yellow]")
            self.state.metrics["visuals_embedded"] = 0

    async def _associate_visuals(self) -> None:
        """Associate visual elements with text clusters."""
        if not self.state.all_visuals or not self.state.clusters:
            return

        from neurosynth.dedup import VisualAssociator

        console.print(
            f"  Associating {len(self.state.all_visuals)} visuals "
            f"with {len(self.state.clusters)} clusters..."
        )

        # Create associator
        associator = VisualAssociator(
            visual_relevance_threshold=self.config.visual_relevance_threshold,
        )

        # Associate visuals to existing clusters
        self.state.clusters = await associator.associate_visuals_to_existing_clusters(
            self.state.clusters,
            self.state.all_visuals,
        )

        # Count associations
        total_associations = sum(len(c.visual_elements) for c in self.state.clusters)
        self.state.metrics["visual_associations"] = total_associations

        console.print(f"  Created {total_associations} visual-cluster associations")

    async def _cluster_chunks(self) -> None:
        """Cluster chunks semantically using FAISS (if available) or sklearn."""
        from neurosynth.dedup import (
            EmbeddingGenerator,
            FAISS_AVAILABLE,
            FAISSClusterer,
            SemanticClusterer,
        )

        # Choose clustering backend
        use_faiss = self.config.use_faiss_clustering and FAISS_AVAILABLE

        if use_faiss:
            console.print("  Using FAISS IndexFlatIP for clustering", style="dim")
            clusterer = FAISSClusterer(
                similarity_threshold=self.config.similarity_threshold,
            )
            # FAISS clusterer handles embedding generation internally
            result = await clusterer.cluster_chunks(self.state.all_chunks)
            self.state.metrics["clustering_backend"] = "faiss"
        else:
            if self.config.use_faiss_clustering and not FAISS_AVAILABLE:
                console.print(
                    "  [yellow]FAISS not available, using sklearn clustering[/yellow]"
                )
            # Generate embeddings first (sklearn path)
            generator = EmbeddingGenerator(use_cache=self.config.use_cache)
            await generator.generate_embeddings(self.state.all_chunks)

            clusterer = SemanticClusterer(
                similarity_threshold=self.config.similarity_threshold,
            )
            result = await clusterer.cluster_chunks(self.state.all_chunks)
            self.state.metrics["clustering_backend"] = "sklearn"

        self.state.clusters = result.clusters
        self.state.metrics["clusters_created"] = result.num_clusters
        self.state.metrics["dedup_ratio"] = result.dedup_ratio

    async def _merge_clusters(self) -> None:
        """Merge content within clusters."""
        from neurosynth.dedup import ClusterMerger

        merger = ClusterMerger()
        results = await merger.merge_all_clusters(
            self.state.clusters,
            detect_conflicts=self.config.detect_conflicts,
        )

        total_conflicts = sum(len(r.conflicts) for r in results)
        self.state.metrics["conflicts_detected"] = total_conflicts

        # Create knowledge base
        self.state.knowledge_base = KnowledgeBase(
            topic=self.topic,
            clusters=self.state.clusters,
            total_chunks_processed=len(self.state.all_chunks),
            total_sources=len(self.state.documents),
            dedup_ratio=self.state.metrics.get("dedup_ratio", 1.0),
        )

    async def _generate_outline(self) -> None:
        """Generate chapter outline."""
        from neurosynth.synthesis import OutlineGenerator

        generator = OutlineGenerator()
        self.state.outline = await generator.generate_outline(
            self.topic,
            self.state.clusters,
        )

        # Assign clusters to sections
        self.state.outline = await generator.assign_clusters_to_sections(
            self.state.outline,
            self.state.clusters,
        )

        self.state.metrics["sections_planned"] = len(self.state.outline)

    async def _synthesize_chapter(self) -> None:
        """Synthesize the full chapter."""
        from neurosynth.synthesis import SectionSynthesizer

        synthesizer = SectionSynthesizer()
        self.state.chapter = await synthesizer.synthesize_chapter(
            self.topic,
            self.state.outline,
        )

        self.state.metrics["total_words"] = self.state.chapter.total_words
        self.state.metrics["total_sources"] = self.state.chapter.total_sources

    async def _generate_output(self) -> None:
        """Generate final output files."""
        from neurosynth.latex import LaTeXGenerator

        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.output_format == "latex":
            generator = LaTeXGenerator()
            output_name = self.topic.lower().replace(" ", "_")

            tex_path = generator.generate_to_file(
                self.state.chapter,
                self.config.output_dir / f"{output_name}.tex",
            )

            # Try PDF compilation
            pdf_path = generator.compile_to_pdf(tex_path, self.config.output_dir)
            if pdf_path:
                self.state.metrics["output_pdf"] = str(pdf_path)

            self.state.metrics["output_tex"] = str(tex_path)

    def _print_summary(self) -> None:
        """Print pipeline summary."""
        from rich.table import Table

        table = Table(title="Pipeline Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for key, value in self.state.metrics.items():
            display_key = key.replace("_", " ").title()
            if isinstance(value, float):
                display_value = f"{value:.2f}"
            else:
                display_value = str(value)
            table.add_row(display_key, display_value)

        console.print(table)


async def run_pipeline(
    topic: str,
    source_dir: Path,
    output_dir: Path,
    **kwargs,
) -> Chapter:
    """Convenience function to run the full pipeline."""
    config = PipelineConfig(
        source_dir=source_dir,
        output_dir=output_dir,
        **kwargs,
    )

    pipeline = Pipeline(topic, config)
    return await pipeline.run()
