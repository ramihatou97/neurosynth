"""
Batch PDF Indexing Service

Provides batch processing of PDFs with real-time progress tracking.
Supports: Proposition Chunking, RAPTOR Summaries, GraphRAG

Async-first design with concurrent PDF processing.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


class IndexingStage(Enum):
    """Stages of PDF indexing pipeline"""

    PENDING = "pending"
    TEXT_EXTRACTION = "text_extraction"
    CHUNKING = "chunking"
    TEXT_EMBEDDING = "text_embedding"
    IMAGE_EXTRACTION = "image_extraction"
    IMAGE_EMBEDDING = "image_embedding"
    RAPTOR = "raptor"  # Recursive summaries
    GRAPH_RAG = "graph_rag"  # Knowledge graph extraction
    STORAGE = "storage"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class FileProgress:
    """Progress tracking for a single file"""

    file_path: Path
    file_name: str
    stage: IndexingStage = IndexingStage.PENDING
    stage_progress: float = 0.0  # 0-100 within current stage
    error_message: str | None = None
    chunks_created: int = 0
    images_extracted: int = 0
    # Embedding counts
    chunks_embedded: int = 0
    images_embedded: int = 0
    # Qdrant push counts
    chunks_pushed_qdrant: int = 0
    images_pushed_qdrant: int = 0
    # RAPTOR summary counts
    raptor_chunks_created: int = 0
    start_time: float | None = None
    end_time: float | None = None

    @property
    def duration(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_complete(self) -> bool:
        return self.stage in (IndexingStage.COMPLETE, IndexingStage.FAILED)

    @property
    def is_success(self) -> bool:
        return self.stage == IndexingStage.COMPLETE


@dataclass
class BatchProgress:
    """Progress tracking for entire batch"""

    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    current_file_index: int = 0
    current_file: FileProgress | None = None
    file_results: list[FileProgress] = field(default_factory=list)
    batch_start_time: float | None = None
    # Concurrent processing tracking
    active_files: list[FileProgress] = field(default_factory=list)
    concurrent_mode: bool = False

    @property
    def percent_complete(self) -> float:
        if self.total_files == 0:
            return 100.0
        return (self.completed_files / self.total_files) * 100

    @property
    def elapsed_time(self) -> float:
        if self.batch_start_time is None:
            return 0.0
        return time.time() - self.batch_start_time

    @property
    def estimated_remaining(self) -> float:
        if self.completed_files == 0:
            return 0.0
        avg_time = self.elapsed_time / self.completed_files
        remaining = self.total_files - self.completed_files
        return avg_time * remaining

    @property
    def success_count(self) -> int:
        return sum(1 for f in self.file_results if f.is_success)

    @property
    def active_count(self) -> int:
        return len(self.active_files)


ProgressCallback = Callable[[BatchProgress], None]


class BatchIndexer:
    """
    Batch PDF indexing with progress tracking.

    Supports advanced RAG features based on config:
    - Proposition Chunker (Small-to-Big)
    - RAPTOR (Recursive Summaries)
    - GraphRAG (Knowledge Graph)
    - Phase 4: Vector Graphics Extraction
    - Phase 4: Cross-Reference Tracking

    Usage:
        indexer = BatchIndexer(db)
        for progress in indexer.index_batch(pdf_files):
            update_ui(progress)
    """

    def __init__(
        self,
        db,
        processor=None,
        chunker=None,
        enable_vector_graphics: bool = False,
        enable_cross_references: bool = False,
    ):
        """
        Initialize batch indexer.

        Args:
            db: Database instance for storage
            processor: DocumentProcessor for PDF processing (lazy loaded if None)
            chunker: Chunker for text chunking (lazy loaded based on config)
            enable_vector_graphics: Enable Phase 4 vector graphics extraction
                                   (flowcharts, diagrams). Default False.
            enable_cross_references: Enable Phase 4 cross-reference tracking
                                    between figures. Default False.
        """
        self.db = db
        self._processor = processor
        self._chunker = chunker
        self._raptor = None
        self._graph_builder = None
        self._ai_client = None
        self._embedder = None
        self._image_embedder = None
        self._qdrant = None

        # Phase 4 feature flags
        self.enable_vector_graphics = enable_vector_graphics
        self.enable_cross_references = enable_cross_references

        # Log active features
        logger.info("BatchIndexer initialized with:")
        logger.info(f"  - Proposition Chunker: {settings.enable_proposition_chunker}")
        logger.info(f"  - RAPTOR: {settings.enable_raptor}")
        logger.info(f"  - GraphRAG: {settings.enable_graph_rag}")
        logger.info(f"  - Qdrant Push (text): {settings.enable_qdrant_push}")
        logger.info(f"  - Qdrant Push (images): {settings.enable_image_qdrant_push}")
        if enable_vector_graphics:
            logger.info("  - Phase 4: Vector Graphics ENABLED 🎨")
        if enable_cross_references:
            logger.info("  - Phase 4: Cross-References ENABLED 🔗")

    @property
    def processor(self):
        if self._processor is None:
            from src.ingest.processor import DocumentProcessor

            self._processor = DocumentProcessor(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                entropy_threshold=2.0,  # Lowered to 2.0 to allow simpler diagrams
                enable_vector_graphics=self.enable_vector_graphics,
                enable_cross_references=self.enable_cross_references,
            )
        return self._processor

    @property
    def chunker(self):
        if self._chunker is None:
            if settings.enable_proposition_chunker:
                from src.index.proposition_chunker import PropositionChunker

                self._chunker = PropositionChunker(target_chunk_size=800)
                logger.info("Using PropositionChunker (Small-to-Big)")
            else:
                from src.index.chunker import SemanticChunker

                self._chunker = SemanticChunker(
                    chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
                )
                logger.info("Using SemanticChunker")
        return self._chunker

    @property
    def ai_client(self):
        """Lazy-load AI client for RAPTOR/GraphRAG"""
        if self._ai_client is None and (
            settings.enable_raptor or settings.enable_graph_rag
        ):
            from src.ai.client import AIClient

            self._ai_client = AIClient()
        return self._ai_client

    @property
    def raptor(self):
        """Lazy-load RAPTOR summarizer with embedder for summary embedding"""
        if self._raptor is None and settings.enable_raptor:
            from src.index.raptor import RecursiveSummarizer

            self._raptor = RecursiveSummarizer(
                self.ai_client, self.db, embedder=self.embedder
            )
        return self._raptor

    @property
    def graph_builder(self):
        """Lazy-load GraphRAG builder"""
        if self._graph_builder is None and settings.enable_graph_rag:
            from src.index.graph import KnowledgeGraphBuilder

            self._graph_builder = KnowledgeGraphBuilder(self.ai_client)
        return self._graph_builder

    @property
    def embedder(self):
        """Lazy-load AsyncEmbedder for text embedding"""
        if self._embedder is None:
            from src.services.embedder import AsyncEmbedder

            self._embedder = AsyncEmbedder()
        return self._embedder

    @property
    def image_embedder(self):
        """Lazy-load AsyncImageEmbedder for image embedding"""
        if self._image_embedder is None:
            from src.services.image_embedder import AsyncImageEmbedder

            self._image_embedder = AsyncImageEmbedder()
        return self._image_embedder

    @property
    def qdrant(self):
        """Lazy-load QdrantService if enabled (handles both text and images)"""
        if not settings.enable_qdrant_push and not settings.enable_image_qdrant_push:
            return None
        if self._qdrant is None:
            from src.services.qdrant_service import QdrantService

            self._qdrant = QdrantService()
        return self._qdrant

    async def _embed_chunks_async(self, chunks: list) -> list:
        """
        Generate embeddings for chunks using VoyageAI (async).
        """
        if not chunks:
            return chunks
        return await self.embedder.embed_chunks(chunks)

    async def _embed_images_async(self, images: list) -> list:
        """
        Generate embeddings for images using BiomedCLIP (async).
        """
        if not images:
            return images
        return await self.image_embedder.embed_images(images)

    async def _push_images_async(self, images: list, source) -> int:
        """
        Push images with embeddings to Qdrant (async).

        Args:
            images: List of ExtractedImage objects
            source: SourceMetadata for the document

        Returns:
            Number of images pushed to Qdrant
        """
        if not settings.enable_image_qdrant_push:
            return 0

        if not images or not self.qdrant:
            return 0

        # Count images with embeddings
        embedded_images = [img for img in images if img.embedding is not None]
        if not embedded_images:
            logger.debug("no_embedded_images_for_qdrant", source=source.title)
            return 0

        loop = asyncio.get_event_loop()
        try:
            pushed = await loop.run_in_executor(
                None,
                self.qdrant.push_images,
                embedded_images,
                source,
            )
            return pushed
        except Exception as e:
            logger.warning(f"Image Qdrant push failed: {e}")
            return 0

    def _embed_chunks(self, chunks: list) -> list:
        """
        Generate embeddings for chunks using VoyageAI (sync wrapper).

        For backward compatibility with sync callers.
        """
        if not chunks:
            return chunks

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - can't use run_until_complete
                import nest_asyncio

                nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._embed_chunks_async(chunks))

    def _create_chunks(self, result):
        """
        Create chunks from document using the configured chunker.

        Handles both SemanticChunker (chunk_document) and
        PropositionChunker (chunk_section per section).
        """
        if settings.enable_proposition_chunker:
            # PropositionChunker: process each section separately
            all_chunks = []
            # SourceMetadata is a dataclass, access attributes directly
            source_id = (
                result.metadata.id
                if hasattr(result.metadata, "id")
                else str(result.path)
            )
            source_title = (
                result.metadata.title
                if hasattr(result.metadata, "title")
                else (result.path.name if hasattr(result, "path") else "Unknown")
            )

            for section in result.sections:
                section_chunks = self.chunker.chunk_section(
                    section=section,
                    source_id=source_id,
                    source_title=source_title,
                )
                all_chunks.extend(section_chunks)
            return all_chunks
        else:
            # SemanticChunker: process entire document
            return self.chunker.chunk_document(result)

    async def _process_single_pdf_async(
        self,
        pdf_path: Path,
        file_progress: FileProgress,
        progress: BatchProgress,
        callback: ProgressCallback | None = None,
    ) -> tuple[FileProgress, list, list]:
        """
        Process a single PDF asynchronously.

        Returns:
            Tuple of (file_progress, chunks, raptor_chunks)
        """
        try:
            # Stage 1: Text Extraction (CPU-bound, run in executor)
            file_progress.stage = IndexingStage.TEXT_EXTRACTION
            if callback:
                callback(progress)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.processor.process, pdf_path)
            file_progress.stage_progress = 100.0

            # Stage 2: Chunking (CPU-bound, run in executor)
            file_progress.stage = IndexingStage.CHUNKING
            file_progress.stage_progress = 0.0
            if callback:
                callback(progress)

            chunks = await loop.run_in_executor(None, self._create_chunks, result)
            file_progress.chunks_created = len(chunks)
            file_progress.stage_progress = 100.0

            # Stage 3+4+5: Parallel Text & Image Embedding
            # Run text embedding (VoyageAI) and image embedding (BiomedCLIP) concurrently
            file_progress.stage = IndexingStage.TEXT_EMBEDDING
            file_progress.stage_progress = 0.0
            file_progress.images_extracted = len(result.images)
            logger.info(f"  📷 Images extracted: {len(result.images)}")
            if callback:
                callback(progress)

            # Create embedding tasks
            text_embed_task = asyncio.create_task(self._embed_chunks_async(chunks))
            image_embed_task = asyncio.create_task(
                self._embed_images_async(result.images)
            )

            # Wait for both to complete (parallel execution)
            try:
                chunks, result.images = await asyncio.gather(
                    text_embed_task,
                    image_embed_task,
                    return_exceptions=False,
                )

                # Log results and update counts
                text_embedded = sum(1 for c in chunks if c.embedding)
                image_embedded = sum(1 for img in result.images if img.embedding)
                file_progress.chunks_embedded = text_embedded
                file_progress.images_embedded = image_embedded
                logger.info(
                    f"  📊 Parallel embedding complete for {pdf_path.name}: "
                    f"{text_embedded}/{len(chunks)} chunks, {image_embedded}/{len(result.images)} images"
                )
            except Exception as e:
                logger.warning(
                    f"  ⚠️ Parallel embedding had errors for {pdf_path.name}: {e}"
                )
                # Try to get partial results
                if not text_embed_task.done():
                    text_embed_task.cancel()
                if not image_embed_task.done():
                    image_embed_task.cancel()

            # Update stage to IMAGE_EMBEDDING to show completion
            file_progress.stage = IndexingStage.IMAGE_EMBEDDING
            file_progress.stage_progress = 100.0
            if callback:
                callback(progress)

            # Stage 6: RAPTOR (if enabled, async)
            raptor_chunks = []
            if settings.enable_raptor and self.raptor:
                file_progress.stage = IndexingStage.RAPTOR
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)
                try:
                    raptor_chunks = await self.raptor.generate_tree(chunks)
                    file_progress.raptor_chunks_created = len(raptor_chunks)
                    logger.info(
                        f"  🦖 RAPTOR: {len(raptor_chunks)} summary chunks for {pdf_path.name}"
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ RAPTOR failed for {pdf_path.name}: {e}")
                file_progress.stage_progress = 100.0

            # Stage 7: GraphRAG (if enabled, async)
            if settings.enable_graph_rag and self.graph_builder:
                file_progress.stage = IndexingStage.GRAPH_RAG
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)
                try:
                    await self.graph_builder.process_chunks(chunks)
                    logger.info(f"  🕸️ GraphRAG: entities extracted for {pdf_path.name}")
                except Exception as e:
                    logger.warning(f"  ⚠️ GraphRAG failed for {pdf_path.name}: {e}")
                file_progress.stage_progress = 100.0

            # Stage 8: Storage (run DB ops in executor)
            file_progress.stage = IndexingStage.STORAGE
            file_progress.stage_progress = 0.0
            if callback:
                callback(progress)

            # Store in SQLite
            await loop.run_in_executor(None, self.db.insert_source, result.metadata)
            await loop.run_in_executor(None, self.db.insert_chunks, chunks)
            if raptor_chunks:
                await loop.run_in_executor(None, self.db.insert_chunks, raptor_chunks)
            images_saved = 0
            for img in result.images:
                await loop.run_in_executor(None, self.db.insert_image, img)
                images_saved += 1
            if images_saved > 0:
                logger.info(f"  💾 Images saved to SQLite: {images_saved}")

            # Push to Qdrant (if enabled)
            qdrant_pushed = 0
            qdrant_images_pushed = 0
            if self.qdrant:
                # Push text chunks
                if settings.enable_qdrant_push:
                    try:
                        # Log embedding dimensions for debugging
                        if chunks and chunks[0].embedding:
                            logger.info(
                                f"  🔢 Embedding dimension: {len(chunks[0].embedding)}"
                            )
                        qdrant_pushed = await loop.run_in_executor(
                            None, self.qdrant.push_chunks, chunks, result.metadata
                        )
                        if raptor_chunks:
                            qdrant_pushed += await loop.run_in_executor(
                                None,
                                self.qdrant.push_chunks,
                                raptor_chunks,
                                result.metadata,
                            )
                    except Exception as e:
                        logger.warning(
                            f"  ⚠️ Qdrant text push failed for {pdf_path.name}: {e}"
                        )

                # Push images
                if settings.enable_image_qdrant_push:
                    try:
                        qdrant_images_pushed = await self._push_images_async(
                            result.images, result.metadata
                        )
                    except Exception as e:
                        logger.warning(
                            f"  ⚠️ Qdrant image push failed for {pdf_path.name}: {e}"
                        )

                # Update file progress with Qdrant counts
                file_progress.chunks_pushed_qdrant = qdrant_pushed
                file_progress.images_pushed_qdrant = qdrant_images_pushed

                if qdrant_pushed or qdrant_images_pushed:
                    logger.info(
                        f"  🔍 Qdrant: {qdrant_pushed} chunks, {qdrant_images_pushed} images for {pdf_path.name}"
                    )

            file_progress.stage_progress = 100.0
            file_progress.stage = IndexingStage.COMPLETE
            file_progress.end_time = time.time()

            logger.info(
                f"✅ {pdf_path.name}: {len(chunks)} chunks, {len(result.images)} images"
                + (
                    f", Qdrant: {qdrant_pushed} chunks + {qdrant_images_pushed} images"
                    if qdrant_pushed or qdrant_images_pushed
                    else ""
                )
            )

            return file_progress, chunks, raptor_chunks

        except Exception as e:
            file_progress.stage = IndexingStage.FAILED
            file_progress.error_message = str(e)
            file_progress.end_time = time.time()
            logger.error(f"❌ Failed to index {pdf_path.name}: {e}")
            return file_progress, [], []

    async def index_batch_async(
        self,
        pdf_files: list[Path],
        callback: ProgressCallback | None = None,
        max_concurrent: int | None = None,
    ) -> AsyncIterator[BatchProgress]:
        """
        Index a batch of PDF files asynchronously with concurrent processing.

        Args:
            pdf_files: List of PDF paths to index
            callback: Optional callback for progress updates
            max_concurrent: Max concurrent PDFs (default: settings.max_concurrent_pdfs)

        Yields:
            BatchProgress after each file completes
        """
        max_concurrent = max_concurrent or settings.max_concurrent_pdfs
        semaphore = asyncio.Semaphore(max_concurrent)

        progress = BatchProgress(
            total_files=len(pdf_files),
            concurrent_mode=max_concurrent > 1,
        )
        progress.batch_start_time = time.time()

        async def process_with_semaphore(pdf_path: Path) -> FileProgress:
            """Process a single PDF with semaphore limiting."""
            async with semaphore:
                file_progress = FileProgress(
                    file_path=pdf_path,
                    file_name=pdf_path.name,
                )
                file_progress.start_time = time.time()

                # Track active file
                progress.active_files.append(file_progress)
                if callback:
                    callback(progress)

                try:
                    result, _, _ = await self._process_single_pdf_async(
                        pdf_path, file_progress, progress, callback
                    )
                    return result
                finally:
                    # Remove from active files
                    if file_progress in progress.active_files:
                        progress.active_files.remove(file_progress)

        # Process all PDFs concurrently with semaphore limiting
        tasks = [
            asyncio.create_task(process_with_semaphore(pdf_path))
            for pdf_path in pdf_files
        ]

        # Yield progress as each task completes
        for coro in asyncio.as_completed(tasks):
            file_progress = await coro

            progress.file_results.append(file_progress)
            if file_progress.is_success:
                progress.completed_files += 1
            else:
                progress.failed_files += 1

            progress.current_file = file_progress
            progress.current_file_index = len(progress.file_results)

            if callback:
                callback(progress)

            yield progress

        logger.info(
            f"✨ Batch complete: {progress.success_count}/{progress.total_files} succeeded, "
            f"{progress.failed_files} failed"
        )

    def index_batch(
        self,
        pdf_files: list[Path],
        callback: ProgressCallback | None = None,
    ):
        """
        Index a batch of PDF files with progress tracking.

        Args:
            pdf_files: List of PDF paths to index
            callback: Optional callback for progress updates

        Yields:
            BatchProgress after each file completes
        """
        progress = BatchProgress(total_files=len(pdf_files))
        progress.batch_start_time = time.time()

        for idx, pdf_path in enumerate(pdf_files):
            file_progress = FileProgress(
                file_path=pdf_path,
                file_name=pdf_path.name,
            )
            file_progress.start_time = time.time()
            progress.current_file_index = idx + 1
            progress.current_file = file_progress

            try:
                # Stage 1: Text Extraction
                file_progress.stage = IndexingStage.TEXT_EXTRACTION
                if callback:
                    callback(progress)

                result = self.processor.process(pdf_path)
                file_progress.stage_progress = 100.0

                # Stage 2: Chunking
                file_progress.stage = IndexingStage.CHUNKING
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)

                chunks = self._create_chunks(result)
                file_progress.chunks_created = len(chunks)
                file_progress.stage_progress = 100.0

                # Stage 3: Text Embedding (VoyageAI)
                file_progress.stage = IndexingStage.TEXT_EMBEDDING
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)

                # Actually embed chunks using VoyageAI
                try:
                    chunks = self._embed_chunks(chunks)
                    embedded_count = sum(1 for c in chunks if c.embedding)
                    file_progress.chunks_embedded = embedded_count
                    logger.info(f"  📊 Embedded {embedded_count}/{len(chunks)} chunks")
                except Exception as e:
                    logger.warning(f"  ⚠️ Embedding failed: {e}")
                    # Continue without embeddings - chunks can still be stored

                file_progress.stage_progress = 100.0

                # Stage 4: Image Extraction (already done in processor)
                file_progress.stage = IndexingStage.IMAGE_EXTRACTION
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)
                file_progress.images_extracted = len(result.images)
                file_progress.stage_progress = 100.0

                # Stage 5: Image Embedding (BiomedCLIP)
                file_progress.stage = IndexingStage.IMAGE_EMBEDDING
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)

                try:
                    # Run async image embedding in sync context
                    result.images = asyncio.run(
                        self.image_embedder.embed_images(result.images)
                    )
                    image_embedded = sum(1 for img in result.images if img.embedding)
                    file_progress.images_embedded = image_embedded
                    logger.info(
                        f"  🖼️ Embedded {image_embedded}/{len(result.images)} images"
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ Image embedding failed: {e}")

                file_progress.stage_progress = 100.0

                # Stage 6: RAPTOR (if enabled)
                raptor_chunks = []
                if settings.enable_raptor and self.raptor:
                    file_progress.stage = IndexingStage.RAPTOR
                    file_progress.stage_progress = 0.0
                    if callback:
                        callback(progress)
                    try:
                        raptor_chunks = asyncio.run(self.raptor.generate_tree(chunks))
                        file_progress.raptor_chunks_created = len(raptor_chunks)
                        logger.info(f"  🦖 RAPTOR: {len(raptor_chunks)} summary chunks")
                    except Exception as e:
                        logger.warning(f"  ⚠️ RAPTOR failed: {e}")
                    file_progress.stage_progress = 100.0

                # Stage 7: GraphRAG (if enabled)
                if settings.enable_graph_rag and self.graph_builder:
                    file_progress.stage = IndexingStage.GRAPH_RAG
                    file_progress.stage_progress = 0.0
                    if callback:
                        callback(progress)
                    try:
                        asyncio.run(self.graph_builder.process_chunks(chunks))
                        logger.info("  🕸️ GraphRAG: entities extracted")
                    except Exception as e:
                        logger.warning(f"  ⚠️ GraphRAG failed: {e}")
                    file_progress.stage_progress = 100.0

                # Stage 8: Storage
                file_progress.stage = IndexingStage.STORAGE
                file_progress.stage_progress = 0.0
                if callback:
                    callback(progress)

                # Store in SQLite
                self.db.insert_source(result.metadata)
                self.db.insert_chunks(chunks)
                if raptor_chunks:
                    self.db.insert_chunks(raptor_chunks)
                for img in result.images:
                    self.db.insert_image(img)

                # Push to Qdrant (if enabled)
                qdrant_pushed = 0
                qdrant_images_pushed = 0
                if self.qdrant:
                    # Push text chunks
                    if settings.enable_qdrant_push:
                        try:
                            # Log embedding dimensions for debugging
                            if chunks and chunks[0].embedding:
                                logger.info(
                                    f"  🔢 Embedding dimension: {len(chunks[0].embedding)}"
                                )
                            qdrant_pushed = self.qdrant.push_chunks(
                                chunks, result.metadata
                            )
                            if raptor_chunks:
                                qdrant_pushed += self.qdrant.push_chunks(
                                    raptor_chunks, result.metadata
                                )
                        except Exception as e:
                            logger.warning(f"  ⚠️ Qdrant text push failed: {e}")

                    # Push images
                    if settings.enable_image_qdrant_push:
                        try:
                            embedded_images = [
                                img for img in result.images if img.embedding
                            ]
                            if embedded_images:
                                qdrant_images_pushed = self.qdrant.push_images(
                                    embedded_images, result.metadata
                                )
                        except Exception as e:
                            logger.warning(f"  ⚠️ Qdrant image push failed: {e}")

                    # Update file progress with Qdrant counts
                    file_progress.chunks_pushed_qdrant = qdrant_pushed
                    file_progress.images_pushed_qdrant = qdrant_images_pushed

                    if qdrant_pushed or qdrant_images_pushed:
                        logger.info(
                            f"  🔍 Qdrant: {qdrant_pushed} chunks, {qdrant_images_pushed} images"
                        )

                file_progress.stage_progress = 100.0
                file_progress.stage = IndexingStage.COMPLETE
                file_progress.end_time = time.time()

                progress.completed_files += 1
                logger.info(
                    f"✅ [{progress.completed_files}/{progress.total_files}] "
                    f"{pdf_path.name}: {len(chunks)} chunks, {len(result.images)} images"
                    + (
                        f", Qdrant: {qdrant_pushed} chunks + {qdrant_images_pushed} images"
                        if qdrant_pushed or qdrant_images_pushed
                        else ""
                    )
                )

            except Exception as e:
                file_progress.stage = IndexingStage.FAILED
                file_progress.error_message = str(e)
                file_progress.end_time = time.time()
                progress.failed_files += 1
                logger.error(f"❌ Failed to index {pdf_path.name}: {e}")

            progress.file_results.append(file_progress)

            if callback:
                callback(progress)

            yield progress

        logger.info(
            f"✨ Batch complete: {progress.success_count}/{progress.total_files} succeeded, "
            f"{progress.failed_files} failed"
        )
