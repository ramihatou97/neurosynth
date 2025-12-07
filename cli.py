#!/usr/bin/env python3
"""
Neurosurgical Chapter Synthesis Engine - CLI

Commands:
    ingest    - Process PDF documents into searchable index
    synthesize - Generate a chapter on a topic
    search    - Search your indexed library
    stats     - Show library statistics
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings, ensure_directories
from src.models import ChunkType


console = Console()


@click.group()
@click.version_option(version="1.0.0")
def main():
    """
    Neurosurgical Chapter Synthesis Engine
    
    Transform your PDF library into unified, comprehensive chapters.
    """
    ensure_directories()


# ============================================================================
# INGEST Command
# ============================================================================

@main.command()
@click.argument('library_path', type=click.Path(exists=True), required=False)
@click.option('--force', '-f', is_flag=True, help='Reprocess already indexed documents')
def ingest(library_path: Optional[str], force: bool):
    """
    Process PDF documents and build searchable index.
    
    LIBRARY_PATH: Path to your PDF library (default: data/library)
    """
    from src.ingest import DocumentProcessor
    from src.index import Database, SemanticChunker
    from src.ai import AIClient
    
    path = Path(library_path) if library_path else settings.library_path
    
    if not path.exists():
        console.print(f"[red]Library path not found: {path}[/red]")
        console.print(f"Create the directory and add your PDFs, or specify a different path.")
        return
    
    # Find PDFs
    pdf_files = list(path.rglob("*.pdf"))
    
    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {path}[/yellow]")
        return
    
    console.print(Panel(f"[bold]Processing {len(pdf_files)} PDF documents[/bold]"))
    
    # Initialize components
    processor = DocumentProcessor()
    db = Database()
    chunker = SemanticChunker()
    
    # Check for API key
    try:
        ai = AIClient()
    except ValueError as e:
        console.print(f"[red]API key error: {e}[/red]")
        console.print("Set VOYAGE_API_KEY and ANTHROPIC_API_KEY environment variables.")
        return
    
    processed_count = 0
    chunk_count = 0
    image_count = 0
    errors = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        task = progress.add_task("Processing documents...", total=len(pdf_files))
        
        for pdf_path in pdf_files:
            try:
                # Check if already processed
                doc_id = processor._generate_id(pdf_path)
                if not force and db.source_exists(doc_id):
                    progress.update(task, advance=1, description=f"Skipping {pdf_path.name} (already indexed)")
                    continue
                
                progress.update(task, description=f"Processing {pdf_path.name}...")
                
                # Process document
                document = processor.process(pdf_path)
                
                # Store source metadata
                db.insert_source(document.metadata)
                
                # Create chunks
                chunks = chunker.chunk_document(document)
                
                # Generate embeddings for chunks
                progress.update(task, description=f"Embedding {len(chunks)} chunks...")
                chunk_texts = [c.content[:2000] for c in chunks]  # Truncate for embedding
                embeddings = ai.get_embeddings(chunk_texts)
                
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding
                
                db.insert_chunks(chunks)
                chunk_count += len(chunks)
                
                # Store images with embeddings
                if document.images:
                    progress.update(task, description=f"Embedding {len(document.images)} images...")
                    img_contexts = [f"{img.caption} {img.surrounding_text}"[:1000] for img in document.images]
                    img_embeddings = ai.get_embeddings(img_contexts)
                    
                    for img, embedding in zip(document.images, img_embeddings):
                        img.embedding = embedding
                    
                    db.insert_images(document.images)
                    image_count += len(document.images)
                
                processed_count += 1
                progress.update(task, advance=1)
                
            except Exception as e:
                errors.append((pdf_path.name, str(e)))
                progress.update(task, advance=1)
                continue
    
    # Summary
    console.print()
    table = Table(title="Ingestion Complete")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")
    
    table.add_row("Documents processed", str(processed_count))
    table.add_row("Chunks created", str(chunk_count))
    table.add_row("Images extracted", str(image_count))
    if errors:
        table.add_row("Errors", str(len(errors)))
    
    console.print(table)
    
    if errors:
        console.print("\n[yellow]Errors:[/yellow]")
        for name, error in errors[:5]:  # Show first 5
            console.print(f"  • {name}: {error}")
        if len(errors) > 5:
            console.print(f"  ... and {len(errors) - 5} more")


# ============================================================================
# SYNTHESIZE Command
# ============================================================================

@main.command()
@click.argument('topic')
@click.option('--template', '-t', 
              type=click.Choice(['surgical_procedure', 'anatomy', 'clinical_topic']),
              default='surgical_procedure',
              help='Chapter template to use')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--format', '-f', 
              type=click.Choice(['pdf', 'docx', 'md', 'all']),
              default='all',
              help='Output format')
def synthesize(topic: str, template: str, output: Optional[str], format: str):
    """
    Generate a comprehensive chapter on a topic.
    
    TOPIC: The topic to synthesize (e.g., "translabyrinthine approach")
    """
    from src.index import Database, SearchEngine
    from src.synthesize import SynthesisEngine
    from src.output import ChapterRenderer
    from src.ai import AIClient
    
    console.print(Panel(f"[bold]Synthesizing Chapter: {topic}[/bold]"))
    
    # Initialize components
    db = Database()
    
    # Check if we have data
    stats = db.get_stats()
    if stats['chunks'] == 0:
        console.print("[red]No documents indexed. Run 'ingest' first.[/red]")
        return
    
    try:
        ai = AIClient()
    except ValueError as e:
        console.print(f"[red]API key error: {e}[/red]")
        return
    
    search = SearchEngine(db)
    engine = SynthesisEngine(db, search, ai)
    
    output_dir = Path(output) if output else settings.output_path
    renderer = ChapterRenderer(output_dir)
    
    formats = ['pdf', 'docx', 'md'] if format == 'all' else [format]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Retrieve
        task = progress.add_task("Retrieving relevant content...", total=None)
        
        # Synthesize
        progress.update(task, description="Synthesizing chapter sections...")
        chapter = engine.synthesize_chapter(topic, template)
        
        # Render
        progress.update(task, description="Rendering output files...")
        outputs = renderer.render(chapter, formats)
    
    # Summary
    console.print()
    console.print(f"[green]✓ Chapter synthesized successfully![/green]")
    console.print()
    
    table = Table(title="Chapter Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Topic", chapter.topic)
    table.add_row("Sections", str(len(chapter.sections)))
    table.add_row("Sources used", str(len(chapter.sources)))
    table.add_row("Chunks processed", str(chapter.total_chunks_used))
    table.add_row("Images included", str(chapter.total_images))
    
    console.print(table)
    
    console.print()
    console.print("[bold]Output files:[/bold]")
    for fmt, path in outputs.items():
        console.print(f"  • {fmt.upper()}: {path}")


# ============================================================================
# SEARCH Command
# ============================================================================

@main.command()
@click.argument('query')
@click.option('--limit', '-n', default=10, help='Number of results')
@click.option('--type', '-t', 
              type=click.Choice(['all', 'anatomy', 'procedure', 'complications']),
              default='all',
              help='Filter by content type')
def search(query: str, limit: int, type: str):
    """
    Search your indexed library.
    
    QUERY: Search query (e.g., "facial nerve preservation")
    """
    from src.index import Database, SearchEngine
    from src.ai import AIClient
    
    db = Database()
    
    # Check if we have data
    stats = db.get_stats()
    if stats['chunks'] == 0:
        console.print("[red]No documents indexed. Run 'ingest' first.[/red]")
        return
    
    try:
        ai = AIClient()
    except ValueError as e:
        console.print(f"[red]API key error: {e}[/red]")
        return
    
    search_engine = SearchEngine(db)
    
    # Get query embedding
    console.print(f"Searching for: [cyan]{query}[/cyan]")
    query_embedding = ai.get_embedding(query)
    
    # Filter by type
    chunk_types = None
    if type == 'anatomy':
        chunk_types = [ChunkType.ANATOMY]
    elif type == 'procedure':
        chunk_types = [ChunkType.PROCEDURE_STEP, ChunkType.POSITIONING]
    elif type == 'complications':
        chunk_types = [ChunkType.COMPLICATIONS]
    
    # Search
    results = search_engine.search_chunks(
        query_embedding=query_embedding,
        top_k=limit,
        chunk_types=chunk_types
    )
    
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    
    console.print()
    
    for i, result in enumerate(results, 1):
        score_pct = int(result.score * 100)
        
        panel_content = result.chunk.content[:500]
        if len(result.chunk.content) > 500:
            panel_content += "..."
        
        console.print(Panel(
            panel_content,
            title=f"[cyan]{i}. {result.chunk.source_title}[/cyan] | [dim]p.{result.chunk.page_start}[/dim] | [green]{score_pct}% match[/green]",
            subtitle=f"[dim]{result.chunk.section_title} | {result.chunk.chunk_type.value}[/dim]"
        ))
        console.print()


# ============================================================================
# STATS Command
# ============================================================================

@main.command()
def stats():
    """Show library statistics."""
    from src.index import Database
    
    db = Database()
    stats = db.get_stats()
    
    table = Table(title="Library Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")
    
    table.add_row("Documents", str(stats['sources']))
    table.add_row("Chunks", str(stats['chunks']))
    table.add_row("Images", str(stats['images']))
    
    console.print(table)
    
    if stats['by_specialty']:
        console.print()
        specialty_table = Table(title="By Specialty")
        specialty_table.add_column("Specialty", style="cyan")
        specialty_table.add_column("Documents", style="white")
        
        for specialty, count in stats['by_specialty'].items():
            specialty_table.add_row(specialty, str(count))
        
        console.print(specialty_table)


# ============================================================================
# TOPICS Command
# ============================================================================

@main.command()
@click.option('--specialty', '-s', help='Filter by specialty')
def topics(specialty: Optional[str]):
    """List available topics based on indexed content."""
    from src.index import Database
    
    db = Database()
    sources = db.get_all_sources()
    
    if specialty:
        sources = [s for s in sources if s.specialty.value == specialty]
    
    if not sources:
        console.print("[yellow]No sources found.[/yellow]")
        return
    
    # Group by specialty
    by_specialty = {}
    for source in sources:
        spec = source.specialty.value
        if spec not in by_specialty:
            by_specialty[spec] = []
        by_specialty[spec].append(source)
    
    for spec, spec_sources in sorted(by_specialty.items()):
        console.print(f"\n[bold cyan]{spec.upper()}[/bold cyan]")
        for source in spec_sources[:10]:  # Show first 10
            pages = f" ({source.total_pages} pages)" if source.total_pages else ""
            console.print(f"  • {source.title}{pages}")
        if len(spec_sources) > 10:
            console.print(f"  [dim]... and {len(spec_sources) - 10} more[/dim]")


# ============================================================================
# CONSULT Command (Quick Precision Lookup)
# ============================================================================

@main.command()
@click.argument('question')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed retrieval info')
def consult(question: str, verbose: bool):
    """
    Quick precision lookup with ColBERT reranking.
    
    QUESTION: Clinical question (e.g., "What is anterior to the facial nerve?")
    
    This uses the Deep-Dx precision retrieval engine with:
    - Query classification (spatial, procedural, contraindication, etc.)
    - ColBERT token-level precision reranking
    - Confidence scoring
    """
    from src.index import Database, PrecisionSearchEngine
    from src.ai import AIClient
    
    db = Database()
    
    # Check if we have data
    stats = db.get_stats()
    if stats['chunks'] == 0:
        console.print("[red]No documents indexed. Run 'ingest' first.[/red]")
        return
    
    try:
        ai = AIClient()
    except ValueError as e:
        console.print(f"[red]API key error: {e}[/red]")
        return
    
    # Initialize precision search
    precision_search = PrecisionSearchEngine(db, colbert_enabled=True)
    
    console.print(f"\n🔍 [bold]Query:[/bold] {question}")
    
    # Get query embedding
    query_embedding = ai.get_embedding(question)
    
    # Execute precision search
    result = precision_search.search(
        query=question,
        query_embedding=query_embedding,
        top_k=10,
        include_images=False
    )
    
    # Show query classification
    console.print(f"📊 [dim]Type: {result.query_type.value} | Systems: {', '.join(result.systems_used)} | {result.retrieval_time_ms:.0f}ms[/dim]")
    
    # Confidence indicator
    conf_color = {
        'high': 'green',
        'medium': 'yellow', 
        'low': 'red',
        'insufficient': 'red'
    }[result.confidence_level.value]
    
    console.print(f"🎯 [bold {conf_color}]Confidence: {result.confidence:.0%} ({result.confidence_level.value})[/bold {conf_color}]")
    
    if result.warnings:
        for w in result.warnings:
            console.print(f"⚠️  [yellow]{w}[/yellow]")
    
    console.print()
    
    if not result.results:
        console.print("[yellow]No results found.[/yellow]")
        return
    
    # Show top results
    for i, r in enumerate(result.results[:5], 1):
        score_display = f"ColBERT: {r.colbert_score:.1f}" if r.colbert_score else f"Dense: {r.dense_score:.2f}"
        safety_badge = " 🚨" if r.has_safety_content else ""
        
        panel_content = r.chunk.content[:400]
        if len(r.chunk.content) > 400:
            panel_content += "..."
        
        console.print(Panel(
            panel_content,
            title=f"[cyan]{i}. {r.chunk.source_title}[/cyan] | [dim]p.{r.chunk.page_start}[/dim] | [green]{score_display}[/green]{safety_badge}",
            subtitle=f"[dim]{r.chunk.section_title}[/dim]"
        ))
        console.print()
    
    if verbose and len(result.results) > 5:
        console.print(f"[dim]... and {len(result.results) - 5} more results[/dim]")


if __name__ == "__main__":
    main()
