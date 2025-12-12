import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path to ensure imports work
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

import logging

from src.config import settings
from src.index.chunker import SemanticChunker
from src.index.database import Database
from src.ingest.async_ingestor import AsyncIngestor
from src.ingest.processor import DocumentProcessor
from src.services.ingestion_queue import QueueItem, get_queue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RescanLibrary")


async def rescan_async():
    lib_path = settings.library_path
    print(f"Scanning library at: {lib_path}")

    if not lib_path.exists():
        print(f"Library path does not exist: {lib_path}")
        return

    # Recursive glob for PDFs
    files = list(lib_path.rglob("*.pdf"))
    if not files:
        print("No PDF files found in the library directory.")
        return

    print(f"Found {len(files)} PDFs. Starting ingestion...")

    try:
        db = Database()
        print(f"Connected to database at {settings.database_path}")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    # Initialize processor
    try:
        # Disable sync embedding
        processor = DocumentProcessor(image_embedding_model="none")
        chunker = SemanticChunker()

        # Start Async Ingestor (Consumer)
        ingestor = AsyncIngestor()
        await ingestor.start()

    except Exception as e:
        print(f"Failed to initialize processors: {e}")
        return

    success_count = 0
    SAMPLE_LIMIT = 10

    print(
        f"\n🧪 Running BALANCED SAMPLE MODE via ASYNC PIPELINE: Processing diverse set of {SAMPLE_LIMIT} files...\n"
    )

    # Selection Logic (Same as before)
    categories = {
        "SPINE": ["spine", "back", "vertebra"],
        "ONCOLOGY": ["tumor", "onco", "glioma", "meningioma", "cancer"],
        "TRAUMA": ["trauma", "injury", "fracture", "concussion"],
        "ANATOMY": ["anatomy", "atlas", "rhoton"],
        "VASCULAR": ["aneurysm", "vascular", "stroke"],
    }

    selected_files = []
    seen_files = set()

    # 1. Select one file for each category
    for category, keywords in categories.items():
        for pdf_path in files:
            if pdf_path in seen_files:
                continue
            name_lower = pdf_path.name.lower()
            if any(kw in name_lower for kw in keywords):
                selected_files.append(pdf_path)
                seen_files.add(pdf_path)
                break

    # 2. Fill the rest
    for pdf_path in files:
        if len(selected_files) >= SAMPLE_LIMIT:
            break
        if pdf_path not in seen_files:
            selected_files.append(pdf_path)
            seen_files.add(pdf_path)

    files_to_process = selected_files
    print(f"\nStarting processing of {len(files_to_process)} selected files...\n")

    from rich.console import Console
    from rich.live import Live
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    console = Console()
    queue = get_queue()
    quality_report = []

    console.print(
        "\n[bold green]🧪 Running BALANCED SAMPLE MODE via ASYNC PIPELINE[/bold green]"
    )
    console.print(f"Target: {len(files_to_process)} files selected.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:

        parse_task = progress.add_task(
            "[cyan]Parsing PDFs[/cyan]", total=len(files_to_process)
        )
        # Embedding total is dynamic, we'll update it as we find images. Start with 1 to show activity.
        embed_task = progress.add_task("[magenta]Embedding Images[/magenta]", total=100)

        # PRODUCER LOOP
        for i, pdf_path in enumerate(files_to_process):
            progress.update(
                parse_task, description=f"[cyan]Parsing: {pdf_path.name}[/cyan]"
            )

            try:
                # CPU-bound processing (Sync)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, processor.process, pdf_path)

                # Chunking
                chunks = chunker.chunk_document(result)

                # DB Operations
                db.insert_source(result.metadata)
                db.insert_chunks(chunks)

                # Enqueue Images
                image_count = 0
                if result.images:
                    # Update embed total
                    current_total = progress.tasks[embed_task].total
                    if current_total == 100:  # Initial adjustment
                        progress.update(embed_task, total=len(result.images))
                    else:
                        progress.update(
                            embed_task, total=current_total + len(result.images)
                        )

                    for img in result.images:
                        try:
                            # 1. Insert Metadata
                            db.insert_image(img)
                            # 2. Queue
                            await queue.enqueue(
                                QueueItem(
                                    id=img.id,
                                    type="image",
                                    payload=img,
                                    img_path=img.file_path,
                                )
                            )
                            image_count += 1
                        except Exception as ie:
                            console.print(
                                f"[red]Warning: Failed to insert image metadata {img.id}: {ie}[/red]"
                            )

                quality_report.append(
                    {
                        "file": pdf_path.name,
                        "chunks": len(chunks),
                        "images_queued": image_count,
                    }
                )
                success_count += 1
                progress.advance(parse_task)

            except Exception as e:
                console.print(f"[red]Failed: {pdf_path.name}: {e}[/red]")
                quality_report.append({"file": pdf_path.name, "error": str(e)})

        progress.update(parse_task, description="[green]Parsing Complete[/green]")

        # MONITORING LOOP (Wait for Consumer)
        while not queue.is_empty:
            q_size = queue.qsize()
            pending = queue.total_queued - queue.total_processed
            # embedding task completed = total - pending
            completed = progress.tasks[embed_task].total - pending
            # Ideally we track processed count in queue

            # Better way: Queue tracks 'total_processed'.
            progress.update(
                embed_task,
                completed=queue.total_processed,
                description=f"[magenta]Embedding (Queue: {q_size})[/magenta]",
            )
            await asyncio.sleep(0.5)

        # Final update
        progress.update(
            embed_task,
            completed=queue.total_queued,
            description="[green]Embedding Complete[/green]",
        )

    await ingestor.stop()

    console.print("\n" + "=" * 60)
    console.print("📊 ASYNC PIPELINE REPORT")
    console.print("=" * 60)
    for report in quality_report:
        console.print(f"\n📄 File: {report['file']}")
        if "error" in report:
            console.print(f"   ❌ Error: {report['error']}")
        else:
            console.print(f"   • Text Chunks: {report['chunks']}")
            console.print(f"   • Images Queued: {report['images_queued']}")
    console.print("=" * 60 + "\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(rescan_async())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
