"""
Async Ingestion Manager
=======================
Manages background tasks for "Heavy" RAG operations (RAPTOR summarization, GraphRAG extraction).
Decouples the main ingestion loop (Extract -> Chunk -> Embed) from advanced reasoning layers.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, List

logger = logging.getLogger(__name__)


@dataclass
class BackgroundTask:
    task_type: str  # "RAPTOR" or "GRAPH"
    source: Any  # SourceMetadata object
    chunks: list[Any]  # List[Chunk]
    status: str = "PENDING"


class AsyncIngestionManager:
    """
    Orchestrator for background RAG tasks.
    """

    def __init__(self, bridge_instance):
        self.bridge = bridge_instance
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: list[asyncio.Task] = []
        self._running = False

    async def start_worker(self):
        """Start the background worker."""
        if self._running:
            return

        self._running = True
        logger.info("🚀 Async Ingestion Worker Started")

        while self._running:
            try:
                task: BackgroundTask = await self.queue.get()
                await self._process_task(task)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker Loop Error: {e}")

    async def submit_job(self, task_type: str, source: Any, chunks: list[Any]):
        """Submit a job to the background queue."""
        task = BackgroundTask(task_type, source, chunks)
        await self.queue.put(task)
        logger.info(
            f"Queued {task_type} job for Source {source.id} ({self.queue.qsize()} pending)"
        )

    async def _process_task(self, task: BackgroundTask):
        """Execute the actual logic."""
        logger.info(f"Processing {task.task_type} for Source {task.source.title}...")

        try:
            if task.task_type == "RAPTOR":
                if self.bridge.raptor:
                    summaries = await self.bridge.raptor.generate_tree(task.chunks)
                    if summaries:
                        await self.bridge.embed_chunks(summaries)
                        self.bridge._target_db.insert_chunks(summaries)
                        if not self.bridge.skip_qdrant:
                            await self.bridge.push_to_qdrant(summaries, task.source)
                        logger.info(
                            f"✅ RAPTOR complete for {task.source.title}: {len(summaries)} summaries"
                        )

            elif task.task_type == "GRAPH":
                if self.bridge.graph_builder:
                    await self.bridge.graph_builder.process_chunks(task.chunks)
                    logger.info(f"✅ Graph update complete for {task.source.title}")

        except Exception as e:
            logger.error(f"❌ Task {task.task_type} Failed: {e}")

    async def shutdown(self):
        """Stop worker and wait for queue to empty (optional)."""
        self._running = False
        # In a real app we might wait join(), but for now we just stop accepting.
