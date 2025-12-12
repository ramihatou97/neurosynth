"""
Async Ingestion Queue Service
=============================

Manages the queue of items (images/chunks) waiting for heavyweight processing
(embedding, Qdrant upsert). Decouples the fast CPU-bound parsing/extraction
from the slower GPU-bound embedding.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("IngestionQueue")


@dataclass
class QueueItem:
    """A generic item in the processing queue."""

    id: str
    type: str  # "image", "chunk"
    payload: Any
    priority: int = 1  # 0=High, 1=Normal, 2=Low
    img_path: Path | None = None  # For image items


class AsyncIngestionQueue:
    """
    Singleton queue manager for ingestion tasks.
    """

    _instance: Optional["AsyncIngestionQueue"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AsyncIngestionQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Unbounded queue for producers, but we can limit if memory signals needed
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self.active_workers: int = 0
        self.total_processed: int = 0
        self.total_queued: int = 0
        self._initialized = True
        logger.info("AsyncIngestionQueue initialized")

    async def enqueue(self, item: QueueItem):
        """Add an item to the processing queue."""
        await self.queue.put(item)
        self.total_queued += 1
        # Debug log every 100 items to avoid spam
        if self.total_queued % 100 == 0:
            logger.debug(
                f"Queue Status: {self.qsize()} pending, {self.total_queued} total submitted"
            )

    async def dequeue_batch(self, batch_size: int = 4) -> list[QueueItem]:
        """
        Get a batch of items from the queue.
        Waits for at least one item, then greedily grabs up to batch_size.
        """
        items = []
        try:
            # Wait for first item
            item = await self.queue.get()
            items.append(item)

            # Try to get more immediately without waiting
            for _ in range(batch_size - 1):
                try:
                    next_item = self.queue.get_nowait()
                    items.append(next_item)
                except asyncio.QueueEmpty:
                    break
        except asyncio.CancelledError:
            raise

        return items

    def task_done(self, count: int = 1):
        """Mark items as processed."""
        for _ in range(count):
            self.queue.task_done()
        self.total_processed += count

    def qsize(self) -> int:
        return self.queue.qsize()

    @property
    def is_empty(self) -> bool:
        return self.queue.empty()


def get_queue() -> AsyncIngestionQueue:
    return AsyncIngestionQueue()
