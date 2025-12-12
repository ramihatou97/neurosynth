"""
Async Ingestor Service
======================

Consumer service that pulls images from the AsyncIngestionQueue and processes
them using the ModelManager (ColPali/BiomedCLIP) and persisting to Qdrant/SQLite.
"""

import asyncio
import logging
from typing import List, Optional

from src.index.database import Database
from src.ingest.smart_extractor import ExtractedFigure
from src.neurosynth.config import get_settings
from src.services.ingestion_queue import QueueItem, get_queue
from src.services.model_manager import get_model_manager

logger = logging.getLogger("AsyncIngestor")


class AsyncIngestor:
    def __init__(self):
        self.queue = get_queue()
        self.model_manager = get_model_manager()
        self.db = Database()
        self.settings = get_settings()
        self._running = False
        self._consumer_task: asyncio.Task | None = None

        # Initialize sync ingestor (for Qdrant logic reuse)
        try:
            from src.neurosynth.ai.ingestor import BiomedIngestor

            self.biomed_ingestor = BiomedIngestor()
        except ImportError:
            logger.warning("BiomedIngestor unavailable (Qdrant client missing?)")
            self.biomed_ingestor = None

    async def start(self):
        """Start the background consumer task."""
        if self._running:
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("AsyncIngestor consumer started")

    async def stop(self):
        """Stop the consumer task gracefully."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncIngestor consumer stopped")

    async def _consume_loop(self):
        """Main consumer loop."""
        batch_size = self.settings.colpali_batch_size  # Use configured batch size (2-4)

        while self._running:
            try:
                # 1. Dequeue Batch
                items = await self.queue.dequeue_batch(batch_size=batch_size)
                if not items:
                    continue

                logger.info(f"Processing batch of {len(items)} items")

                # 2. Process Batch
                await self._process_image_batch(items)

                # 3. Mark Done
                self.queue.task_done(len(items))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer loop error: {e}")
                await asyncio.sleep(1)  # Backoff on error

    async def _process_image_batch(self, items: list[QueueItem]):
        """
        Embed and persist a batch of images.
        """
        # Filter valid image items
        image_items = [item for item in items if item.type == "image" and item.img_path]
        if not image_items:
            return

        # Prepare for embedding
        paths = [item.img_path for item in image_items]

        try:
            # 1. Embed (Async via ColPali wrapper)
            colpali = self.model_manager.get_colpali()
            if not colpali:
                logger.warning("ColPali model not available, skipping embedding")
                return

            # Note: embed_images is async-friendly in our wrapper
            embeddings = await colpali.embed_images(paths)

            # 2. Update Objects & DB
            figures_for_qdrant = []

            for item, embedding in zip(image_items, embeddings):
                # Update item payload (which holds the extracted image object)
                # item.payload is likely an ExtractedFigure or ExtractedImage

                # Update SQLite
                # We assume the ID in QueueItem matches the DB ID
                try:
                    # Async update of embedding in SQLite?
                    # Database class is sync. We should run in executor or just call it
                    # since SQLite writes are fast enough for now compared to embedding.
                    self.db.update_image_embedding(item.id, embedding.tolist())
                except Exception as db_err:
                    logger.error(f"Failed to update DB for {item.id}: {db_err}")

                # Prepare for Qdrant
                # We need to construct/update the object expected by BiomedIngestor
                # If payload is ExtractedFigure, we can use it.
                if isinstance(item.payload, ExtractedFigure):
                    fig = item.payload
                    # Manually attach embedding since ExtractedFigure prevents it?
                    # Actually BiomedIngestor expects to generate embeddings itself usually.
                    # We should modify BiomedIngestor to accept pre-embedded figures OR
                    # just use the Qdrant client directly here for efficiency.
                    # reusing logic is better.
                    figures_for_qdrant.append(fig)

            # 3. Upsert to Qdrant
            # Since we already computed embeddings, we shouldn't re-compute them in BiomedIngestor.
            # But BiomedIngestor.ingest_figures does both.
            # Optimization: Let's just do the upsert here directly to avoid double-work.
            # OR refactor BiomedIngestor.
            # For now, let's implement the upsert logic here to be safe and efficient.
            if self.biomed_ingestor and figures_for_qdrant:
                self._upsert_to_qdrant(figures_for_qdrant, embeddings)

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

    def _upsert_to_qdrant(self, figures: list[ExtractedFigure], embeddings: list):
        """Helper to upsert already-embedded figures to Qdrant."""
        try:
            from uuid import uuid4

            from qdrant_client.models import PointStruct

            points = []
            for fig, vector in zip(figures, embeddings):
                payload = {
                    "filename": fig.image_filename,
                    "source_pdf": fig.source_pdf,
                    "caption": fig.caption,
                    "context": fig.context,
                    "modality": "unknown",  # Classifier not run here yet
                    "path": str(fig.local_path),
                    "page_num": fig.page_num,
                }

                points.append(
                    PointStruct(
                        id=str(uuid4()),
                        vector={"biomed": vector.tolist()},
                        payload=payload,
                    )
                )

            if points:
                client = self.biomed_ingestor.client
                client.upsert(
                    collection_name=self.biomed_ingestor.COLLECTION_NAME, points=points
                )
                logger.info(f"Upserted {len(points)} points to Qdrant")

        except Exception as e:
            logger.error(f"Qdrant upsert failed: {e}")
