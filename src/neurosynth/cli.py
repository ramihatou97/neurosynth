"""Command-line interface for NeuroSynth."""

import asyncio
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from neurosynth import __version__
from neurosynth.synthesis.checkpoint import SynthesisCheckpoint

app = typer.Typer(
    name="neurosynth",
    help="Neurosurgical Knowledge Synthesis System",
    add_completion=False,
)
console = Console()


def safe_copy(src: Path, dst: Path, checkpoint: Optional[SynthesisCheckpoint] = None) -> bool:
    """Copy file with error handling and logging.

    Args:
        src: Source file path
        dst: Destination file path
        checkpoint: Optional checkpoint for error logging

    Returns:
        True if copy succeeded, False otherwise
    """
    try:
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        error_msg = f"Copy failed {src} -> {dst}: {e}"
        if checkpoint:
            checkpoint.log_error(error_msg)
        console.print(f"[yellow]Warning: {error_msg}[/yellow]")
        return False


def run_async_safe(coro, checkpoint: Optional[SynthesisCheckpoint] = None):
    """Run async coroutine with exception handling to preserve checkpoints.

    Args:
        coro: Coroutine to run
        checkpoint: Optional checkpoint for error logging

    Returns:
        Result of the coroutine

    Raises:
        typer.Exit: On failure, after logging to checkpoint
    """
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        if checkpoint:
            checkpoint.log_error("Synthesis interrupted by user (Ctrl+C)")
            _print_recovery_info(checkpoint)
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if checkpoint:
            checkpoint.log_error(f"Fatal error: {type(e).__name__}: {e}")
            _print_recovery_info(checkpoint)
        raise typer.Exit(1)


def _print_recovery_info(checkpoint: SynthesisCheckpoint):
    """Print recovery information to user."""
    summary = checkpoint.get_recovery_summary()
    console.print("\n[yellow]═══ RECOVERY INFORMATION ═══[/yellow]")
    console.print(f"[yellow]Recovery directory: {summary['recovery_dir']}[/yellow]")
    console.print(f"[yellow]Sections saved: {summary['section_count']}[/yellow]")
    console.print(f"[yellow]Figures saved: {summary['figure_count']}[/yellow]")
    if summary['has_latex']:
        console.print("[green]✓ LaTeX source preserved[/green]")
    if summary['has_pdf']:
        console.print("[green]✓ PDF preserved[/green]")
    console.print("[yellow]═══════════════════════════[/yellow]\n")


@app.callback()
def callback():
    """NeuroSynth - Synthesize neurosurgical knowledge from multiple sources."""
    pass


@app.command()
def version():
    """Show version information."""
    console.print(f"NeuroSynth v{__version__}")


@app.command()
def init(
    topic: str = typer.Argument(..., help="Topic name for the chapter"),
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        "-o",
        help="Output directory",
    ),
):
    """Initialize a new synthesis project."""
    project_dir = output_dir / topic.lower().replace(" ", "_")
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (project_dir / "sources").mkdir(exist_ok=True)
    (project_dir / "processed").mkdir(exist_ok=True)
    (project_dir / "output").mkdir(exist_ok=True)

    # Create config file
    config_content = f"""# NeuroSynth Project Configuration
topic: "{topic}"
created: "{__import__('datetime').datetime.now().isoformat()}"

# Processing options
chunk_size: 1000
similarity_threshold: 0.92

# Output options
output_format: latex
"""
    (project_dir / "neurosynth.yaml").write_text(config_content)

    console.print(
        Panel(
            f"[green]Project initialized![/green]\n\n"
            f"Directory: {project_dir}\n"
            f"Topic: {topic}\n\n"
            f"Next steps:\n"
            f"1. Add source documents to: {project_dir}/sources/\n"
            f"2. Run: neurosynth process --project {project_dir}",
            title="NeuroSynth",
        )
    )


@app.command()
def add(
    files: list[Path] = typer.Argument(..., help="Files to add"),
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project directory",
    ),
):
    """Add source documents to the project."""
    sources_dir = project / "sources"
    if not sources_dir.exists():
        console.print("[red]Error: Not a valid NeuroSynth project[/red]")
        raise typer.Exit(1)

    added = 0
    for file_path in files:
        if file_path.exists():
            dest = sources_dir / file_path.name
            if safe_copy(file_path, dest):
                console.print(f"[green]Added:[/green] {file_path.name}")
                added += 1
        else:
            console.print(f"[yellow]Not found:[/yellow] {file_path}")

    console.print(f"\n[green]Added {added} files to project[/green]")


@app.command()
def process(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project directory",
    ),
    use_cache: bool = typer.Option(
        True,
        "--cache/--no-cache",
        help="Use embedding cache",
    ),
):
    """Process source documents (parse, chunk, deduplicate)."""
    run_async_safe(_process_async(project, use_cache))


async def _process_async(project: Path, use_cache: bool):
    """Async processing implementation."""
    from neurosynth.chunking import SemanticChunker
    from neurosynth.dedup import ClusterMerger, EmbeddingGenerator, SemanticClusterer
    from neurosynth.dedup.embeddings import ExactDeduplicator
    from neurosynth.parsers import ParserFactory
    from neurosynth.config import load_project_config, get_settings

    sources_dir = project / "sources"
    processed_dir = project / "processed"

    # Load project config from neurosynth.yaml
    # This ensures chunk_size, chunk_overlap, similarity_threshold are applied
    load_project_config(project)
    settings = get_settings()

    console.print(f"[dim]Config: chunk_size={settings.chunk_size}, "
                  f"chunk_overlap={settings.chunk_overlap}, "
                  f"similarity_threshold={settings.similarity_threshold}[/dim]")

    if not sources_dir.exists():
        console.print("[red]Error: sources/ directory not found[/red]")
        return

    # Find all source files
    source_files = list(sources_dir.glob("*.*"))
    supported = [".pdf", ".epub", ".docx", ".doc", ".txt", ".md"]
    source_files = [f for f in source_files if f.suffix.lower() in supported]

    if not source_files:
        console.print("[yellow]No source files found[/yellow]")
        return

    console.print(f"[blue]Processing {len(source_files)} source files...[/blue]")
    progress_log(f"Processing {len(source_files)} source files")

    # Parse documents
    all_chunks = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing documents...", total=len(source_files))

        for i, file_path in enumerate(source_files, 1):
            progress_log(f"Parsing document {i}/{len(source_files)}: {file_path.name}")
            try:
                parser = ParserFactory.get_parser(file_path)
                doc = await parser.parse(file_path)

                # Chunk document
                chunker = SemanticChunker()
                chunks = await chunker.chunk_document(doc)
                all_chunks.extend(chunks)

                progress.update(task, advance=1, description=f"Parsed: {file_path.name}")
            except Exception as e:
                console.print(f"[red]Error parsing {file_path.name}: {e}[/red]")

    progress_log(f"Extracted {len(all_chunks)} chunks")
    console.print(f"[green]Extracted {len(all_chunks)} chunks[/green]")

    # Exact deduplication
    progress_log("Deduplicating chunks...")
    all_chunks = ExactDeduplicator.deduplicate(all_chunks)
    progress_log(f"After deduplication: {len(all_chunks)} unique chunks")

    # Generate embeddings
    progress_log("Generating embeddings (may take several minutes)...")
    generator = EmbeddingGenerator(use_cache=use_cache)
    await generator.generate_embeddings(all_chunks)
    progress_log("Embeddings complete")

    # Semantic clustering
    progress_log("Clustering chunks...")
    clusterer = SemanticClusterer()
    result = await clusterer.cluster_chunks(all_chunks)
    progress_log(f"Created {result.num_clusters} clusters")

    # Merge clusters
    progress_log("Merging clusters...")
    merger = ClusterMerger()
    await merger.merge_all_clusters(result.clusters)
    progress_log("Cluster merging complete")

    # Save processed data as JSON (portable, debuggable)
    import json
    from neurosynth.utils.serialization import NumpyEncoder

    # Filter out any None clusters before serialization
    valid_clusters = [c for c in result.clusters if c is not None]
    clusters_data = [c.to_dict() for c in valid_clusters]
    with open(processed_dir / "clusters.json", "w", encoding="utf-8") as f:
        json.dump(clusters_data, f, cls=NumpyEncoder, indent=2)

    # Summary
    table = Table(title="Processing Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Source Files", str(len(source_files)))
    table.add_row("Total Chunks", str(result.total_chunks))
    table.add_row("Clusters", str(result.num_clusters))
    table.add_row("Dedup Ratio", f"{result.dedup_ratio:.1f}:1")

    console.print(table)
    console.print(f"\n[green]Processing complete. Data saved to {processed_dir}[/green]")


@app.command()
def synthesize(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project directory",
    ),
    topic: Optional[str] = typer.Option(
        None,
        "--topic",
        "-t",
        help="Override topic name",
    ),
    output_format: str = typer.Option(
        "latex",
        "--format",
        "-f",
        help="Output format (latex, markdown)",
    ),
):
    """Synthesize chapter from processed data."""
    run_async_safe(_synthesize_async(project, topic, output_format))


async def _synthesize_async(
    project: Path,
    topic: Optional[str],
    output_format: str,
    checkpoint: Optional[SynthesisCheckpoint] = None,
    manifest: Optional[dict] = None,
):
    """Async synthesis implementation with checkpoint support.

    Args:
        project: Project directory
        topic: Chapter topic
        output_format: Output format (latex, markdown)
        checkpoint: Optional checkpoint for recovery
        manifest: Optional manifest dictionary
    """
    import pickle

    import yaml

    from neurosynth.latex import LaTeXGenerator
    from neurosynth.synthesis import (
        OutlineGenerator,
        SectionSynthesizer,
        CategoryAwareOutlineGenerator,
    )
    from neurosynth.config import load_project_config, get_settings

    processed_dir = project / "processed"
    output_dir = project / "output"

    # Load project config from neurosynth.yaml
    # This merges YAML settings with environment defaults
    config = load_project_config(project)

    # Get the topic from config or default
    topic = topic or config.get("topic", "Neurosurgical Chapter")

    # Log loaded config values for transparency
    settings = get_settings()
    console.print(f"[dim]Config: chunk_size={settings.chunk_size}, "
                  f"chunk_overlap={settings.chunk_overlap}, "
                  f"similarity_threshold={settings.similarity_threshold}[/dim]")

    # Load clusters (auto-detect format: .json preferred, .pkl for legacy)
    from neurosynth.models.knowledge import KnowledgeCluster

    clusters_json = processed_dir / "clusters.json"
    clusters_pkl = processed_dir / "clusters.pkl"

    if clusters_json.exists():
        # New JSON format
        import json
        with open(clusters_json, "r", encoding="utf-8") as f:
            clusters_data = json.load(f)
        clusters = [KnowledgeCluster.from_dict(c) for c in clusters_data]
    elif clusters_pkl.exists():
        # Legacy pickle format (backward compatibility)
        console.print("[yellow]Note: Loading legacy .pkl format. Consider re-running 'neurosynth process'.[/yellow]")
        with open(clusters_pkl, "rb") as f:
            clusters = pickle.load(f)
    else:
        console.print("[red]Error: Run 'neurosynth process' first[/red]")
        return

    console.print(f"[blue]Synthesizing chapter: {topic}[/blue]")
    progress_log(f"Synthesizing chapter: {topic}")

    # Check for manifest-driven synthesis (Category Aware)
    if manifest and (manifest.get("template_type") or manifest.get("category_summary")):
        progress_log("Using Category-Aware Synthesis...")
        
        # Generate category-aware outline
        cat_outline_gen = CategoryAwareOutlineGenerator()
        outline = cat_outline_gen.generate(manifest)
        
        # Save outline to checkpoint
        if checkpoint:
            outline_data = [{"title": n.title, "level": n.level} for n in outline]
            checkpoint.save_stage("outline", outline_data)

        # Synthesize using category-aware pipeline
        progress_log("Synthesizing sections (this may take 5-20 minutes)...")
        synthesizer = SectionSynthesizer()
        chapter = await synthesizer.synthesize_chapter_from_category_outline(
            topic, 
            outline, 
            manifest=manifest,
            checkpoint=checkpoint
        )
        
    else:
        # Standard Cluster-based Synthesis
        progress_log("Generating chapter outline...")
        outline_gen = OutlineGenerator()
        outline = await outline_gen.generate_outline(topic, clusters)
        progress_log(f"Outline created with {len(outline)} sections")

        # Save outline to checkpoint
        if checkpoint:
            outline_data = [{"title": e.title, "level": e.level} for e in outline]
            checkpoint.save_stage("outline", outline_data)

        outline = await outline_gen.assign_clusters_to_sections(outline, clusters)

        # Synthesize chapter with checkpoint support
        progress_log("Synthesizing sections (this may take 5-20 minutes)...")
        synthesizer = SectionSynthesizer()
        chapter = await synthesizer.synthesize_chapter(topic, outline, checkpoint=checkpoint)
    
    progress_log("Chapter synthesis complete")

    # Generate output
    progress_log("Generating output document...")
    if output_format == "latex":
        generator = LaTeXGenerator()
        tex_path = generator.generate_to_file(
            chapter,
            output_dir / f"{topic.lower().replace(' ', '_')}.tex",
        )

        # Save LaTeX to checkpoint BEFORE attempting PDF compilation
        if checkpoint:
            latex_content = tex_path.read_text(encoding='utf-8')
            checkpoint.save_latex(latex_content)

            # Copy figures to checkpoint
            figures_dir = output_dir / "figures"
            if figures_dir.exists():
                figure_files = list(figures_dir.glob("*"))
                checkpoint.copy_figures(figure_files)

        # Try to compile PDF
        progress_log("Compiling LaTeX to PDF...")
        try:
            pdf_path = generator.compile_to_pdf(tex_path, output_dir)
            if pdf_path and checkpoint:
                checkpoint.copy_pdf(pdf_path)
            progress_log("PDF compilation complete")
        except Exception as e:
            if checkpoint:
                checkpoint.log_error(f"PDF compilation failed: {e}")
            console.print(f"[yellow]PDF compilation failed: {e}[/yellow]")
            console.print("[yellow]LaTeX source has been preserved[/yellow]")
    else:
        # Markdown output
        md_path = output_dir / f"{topic.lower().replace(' ', '_')}.md"
        md_content = _chapter_to_markdown(chapter)
        md_path.write_text(md_content)
        progress_log(f"Markdown saved: {md_path.name}")
        console.print(f"[green]Markdown saved to: {md_path}[/green]")

    # Quality report
    report = chapter.get_quality_report()
    table = Table(title="Chapter Quality Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in report.items():
        if key != "title":
            table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


@app.command()
def run(
    topic: str = typer.Argument(..., help="Topic for the chapter"),
    sources: Path = typer.Option(
        ...,
        "--sources",
        "-s",
        help="Directory containing source documents",
    ),
    output: Path = typer.Option(
        Path("output.pdf"),
        "--output",
        "-o",
        help="Output file path",
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to manifest.json",
    ),
):
    """Full pipeline: process sources and generate chapter."""
    # Create checkpoint BEFORE starting async work
    checkpoint = SynthesisCheckpoint(topic)
    console.print(f"[dim]Recovery directory: {checkpoint.recovery_dir}[/dim]")

    # Load manifest if provided
    manifest_data = None
    if manifest and manifest.exists():
        import json
        with open(manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            # Save manifest to checkpoint
            checkpoint.save_manifest(manifest_data)

    run_async_safe(_run_full_pipeline(topic, sources, output, checkpoint, manifest_data), checkpoint)


def progress_log(message: str):
    """Print a progress message with immediate flush for real-time streaming."""
    print(f"[PROGRESS] {message}", flush=True)


async def _run_full_pipeline(
    topic: str,
    sources: Path,
    output: Path,
    checkpoint: Optional[SynthesisCheckpoint] = None,
    manifest: Optional[dict] = None,
):
    """Run complete pipeline with checkpoint support.

    Args:
        topic: Chapter topic
        sources: Directory containing source documents
        output: Output file path
        checkpoint: Checkpoint manager for recovery
        manifest: Optional manifest dictionary
    """
    import tempfile
    from pathlib import Path as PathLib

    # Create checkpoint if not provided (for backwards compatibility)
    if checkpoint is None:
        checkpoint = SynthesisCheckpoint(topic)

    progress_log(f"Starting synthesis for: {topic}")

    # Create temporary project
    with tempfile.TemporaryDirectory() as tmpdir:
        project = PathLib(tmpdir)

        # Set up project structure
        (project / "sources").mkdir()
        (project / "processed").mkdir()
        (project / "output").mkdir()

        # Copy sources with safe copy
        source_files = list(sources.glob("*.*"))
        progress_log(f"Copying {len(source_files)} source files...")
        copy_failed = 0
        for f in source_files:
            if not safe_copy(f, project / "sources" / f.name, checkpoint):
                copy_failed += 1

        if copy_failed > 0:
            console.print(f"[yellow]Warning: {copy_failed} files failed to copy[/yellow]")

        # Create config
        config = f'topic: "{topic}"\n'
        (project / "neurosynth.yaml").write_text(config)

        # Process
        console.print("[bold blue]Step 1: Processing documents...[/bold blue]")
        progress_log("Step 1/3: Processing documents")
        checkpoint._update_stage_status("processing", "in_progress")
        await _process_async(project, use_cache=True)
        checkpoint._update_stage_status("processing", "completed")

        # Save clusters to checkpoint (prefer JSON, fall back to pickle)
        clusters_json = project / "processed" / "clusters.json"
        clusters_pkl = project / "processed" / "clusters.pkl"

        if clusters_json.exists():
            import json
            with open(clusters_json, "r", encoding="utf-8") as f:
                clusters_data = json.load(f)
            checkpoint.save_stage("clusters", clusters_data)
        elif clusters_pkl.exists():
            import pickle
            with open(clusters_pkl, "rb") as f:
                clusters_data = pickle.load(f)
            checkpoint.save_stage("clusters", clusters_data)

        # Synthesize
        console.print("\n[bold blue]Step 2: Synthesizing chapter...[/bold blue]")
        progress_log("Step 2/3: Synthesizing chapter")
        checkpoint._update_stage_status("synthesis", "in_progress")
        await _synthesize_async(project, topic, "latex", checkpoint, manifest)
        checkpoint._update_stage_status("synthesis", "completed")

        # Copy output
        progress_log("Step 3/3: Generating output file")
        output_files = list((project / "output").glob("*.pdf"))
        if output_files:
            if safe_copy(output_files[0], output, checkpoint):
                checkpoint.copy_pdf(output)
                progress_log(f"Complete! Saved to: {output.name}")
                console.print(f"\n[bold green]Complete! Output saved to: {output}[/bold green]")
                checkpoint.mark_complete()
            else:
                console.print("[red]Failed to copy final PDF[/red]")
        else:
            tex_files = list((project / "output").glob("*.tex"))
            if tex_files:
                tex_output = output.with_suffix(".tex")
                if safe_copy(tex_files[0], tex_output, checkpoint):
                    console.print(
                        f"\n[yellow]PDF compilation failed. "
                        f"LaTeX saved to: {tex_output}[/yellow]"
                    )
                else:
                    console.print("[red]Failed to copy LaTeX file[/red]")

                # Copy figures to output directory
                figures_dir = project / "output" / "figures"
                if figures_dir.exists():
                    output_figures = output.parent / "figures"
                    output_figures.mkdir(exist_ok=True)
                    for fig in figures_dir.glob("*"):
                        safe_copy(fig, output_figures / fig.name, checkpoint)


@app.command(name="import")
def import_manifest(
    manifest: Path = typer.Argument(..., help="Path to manifest.json from Reference Library"),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: based on topic)",
    ),
    auto_run: bool = typer.Option(
        True,
        "--auto-run/--no-auto-run",
        help="Automatically run synthesis after import",
    ),
):
    """Import sources from Reference Library App manifest."""
    # Read manifest first to get topic for checkpoint
    import json
    if manifest.exists():
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
        topic = data.get("topic", "Imported Chapter")
        checkpoint = SynthesisCheckpoint(topic)
        checkpoint.save_manifest(data)
        console.print(f"[dim]Recovery directory: {checkpoint.recovery_dir}[/dim]")
        run_async_safe(_import_manifest_async(manifest, output, auto_run, checkpoint), checkpoint)
    else:
        run_async_safe(_import_manifest_async(manifest, output, auto_run))


async def _import_manifest_async(
    manifest: Path,
    output: Optional[Path],
    auto_run: bool,
    checkpoint: Optional[SynthesisCheckpoint] = None
):
    """Import from manifest file with checkpoint support.

    Args:
        manifest: Path to manifest.json
        output: Output file path
        auto_run: Whether to run synthesis automatically
        checkpoint: Optional checkpoint for recovery
    """
    import json

    if not manifest.exists():
        console.print(f"[red]Error: Manifest not found: {manifest}[/red]")
        return

    # Load manifest
    with open(manifest, "r", encoding="utf-8") as f:
        data = json.load(f)

    topic = data.get("topic", "Imported Chapter")
    sources = data.get("sources", [])

    if not sources:
        console.print("[yellow]No sources in manifest[/yellow]")
        return

    console.print(
        Panel(
            f"[blue]Importing from Reference Library[/blue]\n\n"
            f"Topic: {topic}\n"
            f"Sources: {len(sources)} documents",
            title="NeuroSynth Import",
        )
    )

    # Determine sources directory (relative to manifest)
    sources_dir = manifest.parent

    # Verify source files exist
    valid_sources = []
    for source in sources:
        pdf_path = sources_dir / source["pdf_path"]
        if pdf_path.exists():
            valid_sources.append(pdf_path)
            console.print(
                f"[green]Found:[/green] {source['pdf_path']} ({source['original_source']})"
            )
        else:
            console.print(f"[yellow]Missing:[/yellow] {source['pdf_path']}")

    if not valid_sources:
        console.print("[red]No valid source files found[/red]")
        return

    # Determine output path
    if output is None:
        safe_topic = topic.lower().replace(" ", "_")
        output = Path.home() / "Documents" / "NeuroSynth" / f"{safe_topic}.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)

    if auto_run:
        console.print("\n[blue]Running synthesis...[/blue]")
        await _run_full_pipeline(topic, sources_dir, output, checkpoint, data)
    else:
        console.print("\n[green]Import complete. Run synthesis with:[/green]")
        console.print(f'neurosynth run "{topic}" --sources {sources_dir} --output {output}')


@app.command()
def status(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project directory",
    ),
):
    """Show project status."""
    sources_dir = project / "sources"
    processed_dir = project / "processed"
    output_dir = project / "output"

    table = Table(title="Project Status")
    table.add_column("Item", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    # Check sources
    if sources_dir.exists():
        source_count = len(list(sources_dir.glob("*.*")))
        table.add_row("Sources", "✓" if source_count > 0 else "○", f"{source_count} files")
    else:
        table.add_row("Sources", "✗", "Directory not found")

    # Check processed
    clusters_path = processed_dir / "clusters.pkl"
    if clusters_path.exists():
        import pickle

        with open(clusters_path, "rb") as f:
            clusters = pickle.load(f)
        table.add_row("Processed", "✓", f"{len(clusters)} clusters")
    else:
        table.add_row("Processed", "○", "Not yet processed")

    # Check output
    if output_dir.exists():
        outputs = list(output_dir.glob("*.*"))
        if outputs:
            table.add_row("Output", "✓", ", ".join(f.name for f in outputs[:3]))
        else:
            table.add_row("Output", "○", "Not yet generated")
    else:
        table.add_row("Output", "○", "Directory not found")

    console.print(table)


@app.command()
def cache(
    action: str = typer.Argument(
        ...,
        help="Action: stats, clear, or prune",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Target specific model (for clear action)",
    ),
    target_percent: float = typer.Option(
        0.8,
        "--target",
        "-t",
        help="Target percentage for prune (0.0-1.0)",
    ),
):
    """Manage embedding cache.

    Actions:
      stats - Show cache statistics
      clear - Clear all cached embeddings (or specific model with --model)
      prune - Force eviction to target percentage of max size
    """
    from neurosynth.llm.voyage import get_persistent_cache

    if action == "stats":
        # Show cache statistics
        cache = get_persistent_cache()
        stats = cache.get_stats()

        if "error" in stats:
            console.print(f"[red]Error getting cache stats: {stats['error']}[/red]")
            return

        table = Table(title="Embedding Cache Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Database Path", str(cache.db_path))
        table.add_row("Total Entries", str(stats.get("total_entries", 0)))
        table.add_row("Current Model Entries", str(stats.get("current_model_entries", 0)))
        table.add_row("Memory Cache Size", str(stats.get("memory_cache_size", 0)))
        table.add_row(
            "Size",
            f"{stats.get('size_mb', 0):.2f} MB / {stats.get('max_size_mb', 'unlimited')} MB"
        )
        table.add_row("Current Model", stats.get("model_name", "N/A"))
        table.add_row("Chunk Config", stats.get("chunk_config", "N/A"))

        models = stats.get("models", [])
        table.add_row("Models in Cache", ", ".join(models) if models else "None")

        oldest = stats.get("oldest_entry")
        newest = stats.get("newest_entry")
        table.add_row("Oldest Entry", str(oldest) if oldest else "N/A")
        table.add_row("Newest Entry", str(newest) if newest else "N/A")

        console.print(table)

        # Capacity warning
        size_mb = stats.get("size_mb", 0)
        max_size_mb = stats.get("max_size_mb", 0)
        if max_size_mb > 0 and size_mb > max_size_mb * 0.9:
            console.print(
                f"\n[yellow]⚠ Cache is at {size_mb/max_size_mb*100:.0f}% capacity. "
                f"Consider running 'neurosynth cache prune'[/yellow]"
            )

    elif action == "clear":
        cache = get_persistent_cache()

        if model:
            # Clear specific model
            deleted = cache.invalidate_model(model)
            console.print(f"[green]Cleared {deleted} entries for model: {model}[/green]")
        else:
            # Clear all
            confirm = typer.confirm(
                "This will clear ALL cached embeddings. Continue?",
                default=False,
            )
            if confirm:
                cache.clear()
                console.print("[green]Cleared all cached embeddings[/green]")
            else:
                console.print("[yellow]Aborted[/yellow]")

    elif action == "prune":
        cache = get_persistent_cache()
        stats = cache.get_stats()

        max_size_mb = stats.get("max_size_mb", 0)
        if max_size_mb <= 0:
            console.print(
                "[yellow]Cannot prune: max_size_mb is set to unlimited (0). "
                "Set EMBEDDING_CACHE_MAX_SIZE_MB in config.[/yellow]"
            )
            return

        current_size = stats.get("size_mb", 0)
        target_size = max_size_mb * target_percent

        console.print(
            f"[blue]Pruning cache from {current_size:.1f}MB to {target_size:.1f}MB "
            f"({target_percent*100:.0f}% of max)...[/blue]"
        )

        evicted = cache.prune_to_size(target_percent)

        if evicted > 0:
            new_stats = cache.get_stats()
            console.print(
                f"[green]Pruned {evicted} entries. "
                f"New size: {new_stats.get('size_mb', 0):.2f}MB[/green]"
            )
        else:
            console.print("[green]No pruning needed - cache is within target size[/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Valid actions: stats, clear, prune")
        raise typer.Exit(1)


def _chapter_to_markdown(chapter) -> str:
    """Convert chapter to markdown."""
    lines = [
        f"# {chapter.title}",
        "",
        "*Generated by NeuroSynth*",
        "",
    ]

    if chapter.abstract:
        lines.extend(["## Abstract", "", chapter.abstract, ""])

    if chapter.keywords:
        lines.extend([f"**Keywords:** {', '.join(chapter.keywords)}", ""])

    for section in chapter.sections:
        prefix = "#" * (section.level + 1)
        lines.extend([f"{prefix} {section.title}", "", section.content, ""])

    if chapter.bibliography:
        lines.extend(["## References", ""])
        for i, source in enumerate(chapter.bibliography, 1):
            lines.append(f"{i}. {source.to_citation()}")

    return "\n".join(lines)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
