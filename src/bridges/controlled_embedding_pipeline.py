#!/usr/bin/env python3
"""
Controlled Embedding Pipeline
=============================
A user-controlled, resumable pipeline for embedding library documents.

Features:
- Checkpoint-based progress tracking (pause/resume)
- Sample mode for testing before full deployment
- Configurable batch sizes and rate limiting
- Progress monitoring and ETA estimation
- NO automatic execution - requires explicit user action

Usage:
    # Test on 10 documents first
    pipeline = ControlledEmbeddingPipeline()
    pipeline.run_sample(sample_size=10)

    # Full run with checkpoints
    pipeline.run_full(batch_size=50)

    # Resume after interruption
    pipeline.resume()
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.models import Distance, VectorParams

# Checkpoint file location
CHECKPOINT_DIR = Path.home() / ".neurosynth" / "embedding_pipeline"
CHECKPOINT_FILE = CHECKPOINT_DIR / "checkpoint.json"


@dataclass
class PipelineCheckpoint:
    """Checkpoint state for resumable pipeline."""

    started_at: str = ""
    last_updated_at: str = ""
    status: str = "not_started"  # not_started, in_progress, paused, completed, failed
    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    total_chunks: int = 0
    total_vectors: int = 0
    total_images_extracted: int = 0  # Track extracted images
    processed_file_hashes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    avg_time_per_doc_ms: float = 0.0

    def save(self):
        """Save checkpoint to disk."""
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self.last_updated_at = datetime.now().isoformat()
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "PipelineCheckpoint":
        """Load checkpoint from disk or create new."""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE) as f:
                data = json.load(f)
                return cls(**data)
        return cls()

    @classmethod
    def clear(cls):
        """Clear existing checkpoint."""
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()


@dataclass
class PipelineConfig:
    """Configuration for the embedding pipeline."""

    # Source database
    source_db_path: Path = Path("data/library.db")
    target_db_path: Path = Path("data/neurosynth.db")

    # Qdrant settings
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "deep_dx_collection"
    vector_size: int = 512  # voyage-3-lite dimension

    # Processing settings
    batch_size: int = 50  # Documents per batch
    embedding_batch_size: int = 50  # Chunks per embedding API call
    qdrant_batch_size: int = 100  # Points per Qdrant upsert

    # Chunking settings
    chunk_size: int = 1500
    chunk_overlap: int = 200

    # Image extraction (toggleable)
    enable_image_extraction: bool = False
    enable_image_embedding: bool = False

    # Enhanced image extraction options
    enable_caption_parsing: bool = True  # Extract structured figure refs (Fig. 1, etc.)
    enable_deduplication: bool = True  # Perceptual hash-based deduplication
    dedup_hash_threshold: int = 5  # Hamming distance for duplicates
    dedup_consecutive_threshold: int = 3  # Pages to classify as header/footer

    # Anatomical region detection
    enable_region_detection: bool = True  # Auto-tag anatomical regions
    region_min_confidence: float = 0.3  # Minimum confidence for region tags

    # OCR caption extraction
    enable_ocr: bool = False  # Extract captions via OCR (slower, optional)
    ocr_timeout_seconds: int = 5  # Timeout per image for OCR

    # Rate limiting
    delay_between_batches_ms: int = 100


class ControlledEmbeddingPipeline:
    """
    A controlled, resumable pipeline for embedding library documents.

    This pipeline is designed for user control:
    - Never runs automatically
    - Supports pause/resume with checkpoints
    - Provides progress monitoring
    - Allows sample testing before full runs
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.checkpoint = PipelineCheckpoint.load()
        self._qdrant: QdrantClient | None = None
        self._voyage = None
        self._paused = False

    def get_status(self) -> dict:
        """Get current pipeline status."""
        cp = self.checkpoint
        progress = (
            cp.processed_documents / cp.total_documents * 100
            if cp.total_documents > 0
            else 0
        )

        remaining = cp.total_documents - cp.processed_documents
        eta_ms = remaining * cp.avg_time_per_doc_ms if cp.avg_time_per_doc_ms > 0 else 0
        eta_minutes = eta_ms / 1000 / 60

        return {
            "status": cp.status,
            "progress_percent": round(progress, 1),
            "processed": cp.processed_documents,
            "total": cp.total_documents,
            "remaining": remaining,
            "eta_minutes": round(eta_minutes, 1),
            "chunks_created": cp.total_chunks,
            "vectors_stored": cp.total_vectors,
            "errors": len(cp.errors),
            "started_at": cp.started_at,
            "last_updated_at": cp.last_updated_at,
        }

    def can_resume(self) -> bool:
        """Check if pipeline can be resumed."""
        return self.checkpoint.status in ("in_progress", "paused")

    def pause(self):
        """Pause the pipeline (will stop after current batch)."""
        self._paused = True
        self.checkpoint.status = "paused"
        self.checkpoint.save()

    def reset(self):
        """Reset pipeline state (clears checkpoint)."""
        PipelineCheckpoint.clear()
        self.checkpoint = PipelineCheckpoint()

    def _ensure_qdrant_collection(self):
        """Ensure Qdrant collection exists with correct dimensions."""
        if not self._qdrant:
            self._qdrant = QdrantClient(url=self.config.qdrant_url)

        try:
            info = self._qdrant.get_collection(self.config.collection_name)
            if info.config.params.vectors.size != self.config.vector_size:
                raise ValueError(
                    f"Collection exists with wrong dimensions: "
                    f"expected {self.config.vector_size}, got {info.config.params.vectors.size}"
                )
        except Exception:
            # Create collection
            self._qdrant.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=self.config.vector_size, distance=Distance.COSINE
                ),
            )

    def _get_source_files(self, limit: int = 0) -> list[dict]:
        """Get list of source files from library.db."""
        if not self.config.source_db_path.exists():
            raise FileNotFoundError(
                f"Source database not found: {self.config.source_db_path}"
            )

        conn = sqlite3.connect(self.config.source_db_path)
        conn.row_factory = sqlite3.Row

        # Get files with cached text (using correct column names)
        query = """
            SELECT
                tf.id, tf.pdf_path, tf.chapter_title as title,
                COUNT(ptc.page_number) as cached_pages,
                GROUP_CONCAT(ptc.text_content, '\\n\\n') as full_text
            FROM tracked_files tf
            LEFT JOIN pdf_text_cache ptc ON tf.pdf_path = ptc.pdf_path
            WHERE ptc.text_content IS NOT NULL
            GROUP BY tf.id
            HAVING cached_pages > 0
            ORDER BY tf.id
        """

        if limit > 0:
            query += f" LIMIT {limit}"

        rows = conn.execute(query).fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def run_sample(self, sample_size: int = 10, callback=None) -> dict:
        """
        Run pipeline on a sample of documents for testing.

        Args:
            sample_size: Number of documents to process
            callback: Optional function(status_dict) called after each document

        Returns:
            Status dictionary with results
        """
        return self._run_pipeline(limit=sample_size, callback=callback)

    def run_full(self, callback=None) -> dict:
        """
        Run full pipeline on all documents.

        Args:
            callback: Optional function(status_dict) called after each batch

        Returns:
            Status dictionary with results
        """
        return self._run_pipeline(limit=0, callback=callback)

    def resume(self, callback=None) -> dict:
        """
        Resume pipeline from last checkpoint.

        Args:
            callback: Optional function(status_dict) called after each batch

        Returns:
            Status dictionary with results
        """
        if not self.can_resume():
            raise RuntimeError("No pipeline in progress to resume")

        self._paused = False
        return self._run_pipeline(limit=0, callback=callback, resume=True)

    def _run_pipeline(
        self, limit: int = 0, callback=None, resume: bool = False
    ) -> dict:
        """
        Core pipeline execution.

        Args:
            limit: Max documents to process (0 = all)
            callback: Optional progress callback
            resume: Whether resuming from checkpoint
        """
        import asyncio
        import hashlib

        from neurosynth.llm.voyage import VoyageClient

        # Initialize
        self._ensure_qdrant_collection()
        self._voyage = VoyageClient()
        self._paused = False

        # Get source files
        files = self._get_source_files(limit)

        if not resume:
            self.checkpoint = PipelineCheckpoint(
                started_at=datetime.now().isoformat(),
                status="in_progress",
                total_documents=len(files),
            )
            self.checkpoint.save()

        # Filter out already processed files
        processed_hashes = set(self.checkpoint.processed_file_hashes)
        files_to_process = []
        for f in files:
            file_hash = hashlib.md5(f["pdf_path"].encode()).hexdigest()[:16]
            if file_hash not in processed_hashes:
                f["_hash"] = file_hash
                files_to_process.append(f)

        print(f"Processing {len(files_to_process)} documents...")

        # Process files
        for i, file_info in enumerate(files_to_process):
            if self._paused:
                print("Pipeline paused by user")
                break

            start_time = time.time()

            try:
                chunks_created, vectors_stored = self._process_document(file_info)

                # Update checkpoint
                self.checkpoint.processed_documents += 1
                self.checkpoint.total_chunks += chunks_created
                self.checkpoint.total_vectors += vectors_stored
                self.checkpoint.processed_file_hashes.append(file_info["_hash"])

                # Update timing
                elapsed_ms = (time.time() - start_time) * 1000
                n = self.checkpoint.processed_documents
                old_avg = self.checkpoint.avg_time_per_doc_ms
                self.checkpoint.avg_time_per_doc_ms = (
                    old_avg * (n - 1) + elapsed_ms
                ) / n

            except Exception as e:
                self.checkpoint.failed_documents += 1
                self.checkpoint.errors.append(f"{file_info['title']}: {str(e)[:100]}")

            # Save checkpoint periodically
            if i % 10 == 0:
                self.checkpoint.save()

            # Callback for progress updates
            if callback:
                callback(self.get_status())

            # Rate limiting
            if self.config.delay_between_batches_ms > 0:
                time.sleep(self.config.delay_between_batches_ms / 1000)

        # Final save
        if not self._paused:
            self.checkpoint.status = "completed"
        self.checkpoint.save()

        return self.get_status()

    def _process_document(self, file_info: dict) -> tuple[int, int]:
        """Process a single document. Returns (chunks_created, vectors_stored)."""
        import asyncio
        import hashlib
        import uuid

        chunks_created = 0
        vectors_stored = 0

        # 1. Process text chunks
        text = file_info.get("full_text", "")
        if text:
            c, v = self._process_text_chunks(file_info, text)
            chunks_created += c
            vectors_stored += v

        # 2. Process images if enabled
        if self.config.enable_image_extraction:
            img_count = self._process_images(file_info)
            self.checkpoint.total_images_extracted += img_count

        return chunks_created, vectors_stored

    def _process_text_chunks(self, file_info: dict, text: str) -> tuple[int, int]:
        """Process text into chunks and embed them."""
        import asyncio
        import hashlib
        import uuid

        # Chunk text
        chunks = []
        for i in range(
            0, len(text), self.config.chunk_size - self.config.chunk_overlap
        ):
            chunk_text = text[i : i + self.config.chunk_size]
            if len(chunk_text.strip()) > 50:  # Skip tiny chunks
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "source_id": str(file_info["id"]),
                        "title": file_info["title"],
                    }
                )

        if not chunks:
            return 0, 0

        # Generate embeddings
        texts = [c["content"] for c in chunks]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        embeddings = loop.run_until_complete(
            self._voyage.embed_texts(texts, use_cache=True)
        )

        # Upload to Qdrant
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = hashlib.md5(chunk["id"].encode()).hexdigest()
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=(
                        embedding.tolist()
                        if hasattr(embedding, "tolist")
                        else embedding
                    ),
                    payload={
                        "text": chunk["content"][:2000],
                        "source_doc_id": chunk["source_id"],
                        "title": chunk["title"],
                    },
                )
            )

        # Batch upsert
        for i in range(0, len(points), self.config.qdrant_batch_size):
            batch = points[i : i + self.config.qdrant_batch_size]
            self._qdrant.upsert(
                collection_name=self.config.collection_name, points=batch
            )

        return len(chunks), len(points)

    def _process_images(self, file_info: dict) -> int:
        """
        Extract and optionally embed images from a PDF.

        Returns:
            Number of images extracted
        """
        from pathlib import Path

        pdf_path = Path(file_info.get("pdf_path", ""))
        if not pdf_path.exists():
            return 0

        try:
            from src.ingest.smart_extractor import SmartImageExtractor

            # Output directory for extracted images
            output_dir = (
                Path.home() / ".neurosynth" / "extracted_images" / str(file_info["id"])
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            extractor = SmartImageExtractor(str(output_dir), min_entropy=4.5)

            # Use enhanced extraction options from config
            figures = extractor.process_pdf(
                str(pdf_path),
                enable_caption_parsing=self.config.enable_caption_parsing,
                enable_deduplication=self.config.enable_deduplication,
                dedup_hash_threshold=self.config.dedup_hash_threshold,
                dedup_consecutive_threshold=self.config.dedup_consecutive_threshold,
                enable_region_detection=self.config.enable_region_detection,
                region_min_confidence=self.config.region_min_confidence,
                enable_ocr=self.config.enable_ocr,
                ocr_timeout_seconds=self.config.ocr_timeout_seconds,
            )

            # Store metadata for reporting
            if not hasattr(self, "_image_extraction_results"):
                self._image_extraction_results = []

            # Track deduplication stats
            total_before_dedup = len(figures)
            unique_figures = [f for f in figures if not f.is_duplicate]
            header_footer_count = sum(
                1 for f in figures if f.image_type == "header_footer"
            )
            figures_with_caption = sum(1 for f in figures if f.figure_number)

            for fig in figures:
                # ExtractedFigure enhanced attributes
                img_path = fig.local_path if hasattr(fig, "local_path") else None

                # Get image dimensions if file exists
                width, height = 0, 0
                if img_path and img_path.exists():
                    try:
                        from PIL import Image

                        with Image.open(img_path) as img:
                            width, height = img.size
                    except Exception:
                        pass

                self._image_extraction_results.append(
                    {
                        "source_id": file_info["id"],
                        "source_title": file_info["title"],
                        "pdf_path": str(pdf_path),
                        "image_path": str(img_path) if img_path else "",
                        "image_filename": getattr(fig, "image_filename", ""),
                        "page_number": getattr(fig, "page_num", 0),
                        # Enhanced caption fields
                        "caption": getattr(fig, "caption", ""),
                        "figure_prefix": getattr(fig, "figure_prefix", ""),
                        "figure_number": getattr(fig, "figure_number", ""),
                        "parsed_caption": getattr(fig, "parsed_caption", ""),
                        "context": getattr(fig, "context", "")[:200],
                        "image_type": getattr(fig, "image_type", "unknown"),
                        # Deduplication fields
                        "perceptual_hash": getattr(fig, "perceptual_hash", ""),
                        "is_duplicate": getattr(fig, "is_duplicate", False),
                        "duplicate_of": getattr(fig, "duplicate_of", ""),
                        "consecutive_occurrences": getattr(
                            fig, "consecutive_occurrences", 1
                        ),
                        # Dimensions
                        "width": width,
                        "height": height,
                    }
                )

            # Log extraction stats
            if total_before_dedup > 0:
                dup_count = total_before_dedup - len(unique_figures)
                print(
                    f"  {pdf_path.name}: {len(unique_figures)} unique images "
                    f"({dup_count} duplicates, {header_footer_count} headers/footers, "
                    f"{figures_with_caption} with figure numbers)"
                )

            return len(unique_figures)  # Return unique count

        except Exception as e:
            print(f"Image extraction failed for {pdf_path.name}: {e}")
            return 0

    def get_image_extraction_results(self, unique_only: bool = True) -> list[dict]:
        """
        Get image extraction results for reporting.

        Args:
            unique_only: If True, exclude duplicates and headers/footers
        """
        results = getattr(self, "_image_extraction_results", [])
        if unique_only:
            return [
                r
                for r in results
                if not r.get("is_duplicate") and r.get("image_type") != "header_footer"
            ]
        return results

    def get_extraction_stats(self) -> dict:
        """Get summary statistics for image extraction."""
        results = getattr(self, "_image_extraction_results", [])
        if not results:
            return {}

        total = len(results)
        unique = sum(1 for r in results if not r.get("is_duplicate"))
        duplicates = sum(1 for r in results if r.get("is_duplicate"))
        headers = sum(1 for r in results if r.get("image_type") == "header_footer")
        with_figure_num = sum(1 for r in results if r.get("figure_number"))

        return {
            "total_extracted": total,
            "unique_images": unique,
            "duplicates_removed": duplicates,
            "headers_footers": headers,
            "with_figure_number": with_figure_num,
            "caption_detection_rate": with_figure_num / total * 100 if total else 0,
            "dedup_reduction_rate": duplicates / total * 100 if total else 0,
        }
