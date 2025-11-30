"""NeuroSynth Worker - Main entry point.

Consumes jobs from Redis queue and executes synthesis pipeline.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from neurosynth.worker.queue import JobQueue
from neurosynth.worker.executor import JobExecutor

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class Worker:
    """NeuroSynth job worker."""

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize worker.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.queue = JobQueue(self.redis_url)
        self.executor = JobExecutor(self.queue)
        self.running = False
        self._current_job: Optional[str] = None

    def start(self) -> None:
        """Start the worker."""
        logger.info("Starting NeuroSynth worker...")
        logger.info(f"Redis URL: {self.redis_url}")

        # Test Redis connection
        try:
            self.queue.client.ping()
            logger.info("Redis connection successful")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            sys.exit(1)

        # Requeue any jobs left in processing state from crashes
        requeued = self.queue.requeue_processing()
        if requeued:
            logger.info(f"Requeued {requeued} jobs from previous session")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        self.running = True
        logger.info("Worker ready, waiting for jobs...")

        # Run the main loop
        asyncio.run(self._run())

    async def _run(self) -> None:
        """Main worker loop."""
        while self.running:
            try:
                # Wait for a job (blocking with 5s timeout for shutdown checks)
                job_id = self.queue.dequeue(timeout=5)

                if job_id is None:
                    # Timeout - check if we should continue
                    continue

                self._current_job = job_id
                logger.info(f"Processing job: {job_id}")

                # Get job data
                job_data = self.queue.get_job_data(job_id)
                if not job_data:
                    logger.warning(f"Job {job_id} not found in Redis")
                    continue

                # Check if cancelled
                if self.queue.is_cancelled(job_id):
                    logger.info(f"Job {job_id} was cancelled, skipping")
                    continue

                # Mark as processing
                self.queue.mark_started(job_id)

                try:
                    # Execute the job
                    output_path = await self.executor.execute(job_id, job_data)

                    # Mark completed
                    self.queue.mark_completed(job_id, output_path)
                    logger.info(f"Job {job_id} completed successfully: {output_path}")

                except Exception as e:
                    # Mark failed
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    self.queue.mark_failed(job_id, error_msg)
                    logger.error(f"Job {job_id} failed: {error_msg}")

                finally:
                    self._current_job = None

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying

        logger.info("Worker stopped")

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")

        if self._current_job:
            logger.info(f"Waiting for current job {self._current_job} to complete...")

        self.running = False

    def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        self.queue.close()


def main():
    """Entry point for the worker."""
    worker = Worker()
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        worker.stop()


if __name__ == "__main__":
    main()
