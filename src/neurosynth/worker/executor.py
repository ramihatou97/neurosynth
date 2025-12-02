"""Job executor - runs the NeuroSynth pipeline for a job."""

import json
import logging
from pathlib import Path

from neurosynth.worker.queue import JobQueue

logger = logging.getLogger(__name__)


class JobExecutor:
    """Executes NeuroSynth synthesis jobs."""

    def __init__(self, queue: JobQueue):
        """Initialize executor.

        Args:
            queue: Job queue for status updates
        """
        self.queue = queue

    async def execute(self, job_id: str, job_data: dict) -> str:
        """Execute a synthesis job.

        Args:
            job_id: Job identifier
            job_data: Job data from Redis

        Returns:
            Path to output file

        Raises:
            Exception: If job fails
        """
        # Parse config
        config = json.loads(job_data.get("config", "{}"))
        topic = config.get("topic", job_data.get("topic", "Untitled"))
        output_format = config.get("output_format", "latex")
        config.get("chunk_size", 1000)
        similarity_threshold = config.get("similarity_threshold", 0.92)
        use_cache = config.get("use_cache", True)

        sources_dir = Path(job_data.get("sources_dir", ""))
        output_dir = Path(job_data.get("output_dir", ""))

        if not sources_dir.exists():
            raise ValueError(f"Sources directory not found: {sources_dir}")

        # Create progress callback
        def progress_callback(stage: str, message: str, percent: float | None = None):
            self.queue.update_progress(job_id, stage, message, percent)
            logger.info(f"[{job_id}] {stage}: {message}")

        # Check for cancellation
        if self.queue.is_cancelled(job_id):
            raise ValueError("Job was cancelled")

        progress_callback("starting", "Initializing synthesis pipeline")

        # Import pipeline components
        from neurosynth.chunking import SemanticChunker
        from neurosynth.dedup import (
            ClusterMerger,
            EmbeddingGenerator,
            SemanticClusterer,
        )
        from neurosynth.dedup.embeddings import ExactDeduplicator
        from neurosynth.latex import LaTeXGenerator
        from neurosynth.parsers import ParserFactory
        from neurosynth.synthesis import OutlineGenerator, SectionSynthesizer
        from neurosynth.synthesis.checkpoint import SynthesisCheckpoint

        # Initialize checkpoint for recovery
        checkpoint = SynthesisCheckpoint(topic)

        try:
            # Step 1: Parse documents
            progress_callback("parsing", "Parsing source documents", 10)

            source_files = list(sources_dir.glob("*.*"))
            supported = {".pdf", ".epub", ".docx", ".doc", ".txt", ".md"}
            source_files = [f for f in source_files if f.suffix.lower() in supported]

            if not source_files:
                raise ValueError("No supported source files found")

            all_chunks = []
            for i, file_path in enumerate(source_files, 1):
                if self.queue.is_cancelled(job_id):
                    raise ValueError("Job was cancelled")

                progress_callback(
                    "parsing",
                    f"Parsing document {i}/{len(source_files)}: {file_path.name}",
                    10 + (20 * i / len(source_files)),
                )

                parser = ParserFactory.get_parser(file_path)
                doc = await parser.parse(file_path)

                chunker = SemanticChunker()
                chunks = await chunker.chunk_document(doc)
                all_chunks.extend(chunks)

            progress_callback("parsing", f"Extracted {len(all_chunks)} chunks", 30)

            # Step 2: Deduplicate
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback("deduplication", "Deduplicating chunks", 35)
            all_chunks = ExactDeduplicator.deduplicate(all_chunks)
            progress_callback(
                "deduplication", f"After deduplication: {len(all_chunks)} chunks", 40
            )

            # Step 3: Generate embeddings
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback(
                "embeddings", "Generating embeddings (this may take a while)", 45
            )
            generator = EmbeddingGenerator(use_cache=use_cache)
            await generator.generate_embeddings(all_chunks)
            progress_callback("embeddings", "Embeddings complete", 55)

            # Step 4: Cluster
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback("clustering", "Clustering chunks", 60)
            clusterer = SemanticClusterer(similarity_threshold=similarity_threshold)
            result = await clusterer.cluster_chunks(all_chunks)
            progress_callback(
                "clustering", f"Created {result.num_clusters} clusters", 65
            )

            # Step 5: Merge clusters
            progress_callback("merging", "Merging clusters", 70)
            merger = ClusterMerger()
            await merger.merge_all_clusters(result.clusters)
            progress_callback("merging", "Cluster merging complete", 75)

            # Save clusters to checkpoint (filter out any None clusters)
            valid_clusters = [c for c in (result.clusters or []) if c is not None]
            clusters_data = [
                c.to_dict()
                for c in valid_clusters
                if c is not None and hasattr(c, "to_dict")
            ]
            checkpoint.save_stage("clusters", clusters_data)

            # Step 6: Generate outline
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback("outline", "Generating chapter outline", 78)
            outline_gen = OutlineGenerator()
            outline = await outline_gen.generate_outline(topic, valid_clusters)
            outline = await outline_gen.assign_clusters_to_sections(
                outline, valid_clusters
            )
            progress_callback(
                "outline", f"Outline created with {len(outline)} sections", 80
            )

            # Step 7: Synthesize
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback(
                "synthesis", "Synthesizing chapter (this may take 5-20 minutes)", 82
            )
            synthesizer = SectionSynthesizer()
            chapter = await synthesizer.synthesize_chapter(
                topic, outline, checkpoint=checkpoint
            )
            progress_callback("synthesis", "Chapter synthesis complete", 90)

            # Step 8: Generate output
            if self.queue.is_cancelled(job_id):
                raise ValueError("Job was cancelled")

            progress_callback("output", "Generating output document", 92)

            if output_format == "latex":
                latex_gen = LaTeXGenerator()
                safe_topic = topic.lower().replace(" ", "_")
                tex_path = latex_gen.generate_to_file(
                    chapter,
                    output_dir / f"{safe_topic}.tex",
                )

                # Save LaTeX to checkpoint
                checkpoint.save_latex(tex_path.read_text())

                # Compile to PDF (REQUIRED - don't silently fall back)
                progress_callback("output", "Compiling LaTeX to PDF", 95)
                try:
                    from neurosynth.latex.exceptions import (
                        ImagePreparationError,
                        LaTeXCompilationError,
                        PDFValidationError,
                    )

                    pdf_path = latex_gen.compile_to_pdf(
                        tex_path, output_dir, validate=True
                    )
                    checkpoint.copy_pdf(pdf_path)
                    output_path = str(pdf_path)
                    progress_callback("output", "PDF compiled successfully", 98)

                except LaTeXCompilationError as e:
                    logger.error(f"LaTeX compilation failed: {e}")
                    checkpoint.log_error(f"LaTeX compilation error: {e}")

                    # Build detailed error message
                    error_msg = f"PDF compilation failed: {e}"
                    if hasattr(e, "log_path") and e.log_path:
                        error_msg += f". Check log file: {e.log_path}"
                    if hasattr(e, "errors") and e.errors:
                        error_msg += f". Errors: {e.errors[:500]}"

                    raise RuntimeError(error_msg) from e

                except PDFValidationError as e:
                    logger.error(f"PDF validation failed: {e}")
                    checkpoint.log_error(f"PDF validation error: {e}")
                    raise RuntimeError(
                        f"PDF validation failed: {e}. File was generated but appears corrupted."
                    ) from e

                except ImagePreparationError as e:
                    logger.error(f"Image preparation failed: {e}")
                    checkpoint.log_error(f"Image preparation error: {e}")
                    raise RuntimeError(
                        f"Image preparation failed: {e}. Check that all source images are accessible."
                    ) from e
            else:
                # Markdown output
                safe_topic = topic.lower().replace(" ", "_")
                md_path = output_dir / f"{safe_topic}.md"
                md_content = self._chapter_to_markdown(chapter)
                md_path.write_text(md_content)
                output_path = str(md_path)

            progress_callback("complete", "Synthesis complete", 100)
            checkpoint.mark_complete()

            return output_path

        except Exception as e:
            checkpoint.log_error(str(e))
            raise

    def _chapter_to_markdown(self, chapter) -> str:
        """Convert chapter to markdown format."""
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
