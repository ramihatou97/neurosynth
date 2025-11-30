"""Redis queue interface for job management."""

import json
import logging
from datetime import datetime
from typing import Optional

import redis

logger = logging.getLogger(__name__)


class JobQueue:
    """Redis-based job queue for NeuroSynth workers."""

    QUEUE_KEY = "jobs:queue"
    PROCESSING_KEY = "jobs:processing"

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize the job queue.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
            )
        return self._client

    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None

    def _job_key(self, job_id: str) -> str:
        return f"jobs:{job_id}"

    def dequeue(self, timeout: int = 0) -> Optional[str]:
        """Dequeue a job from the queue.

        Args:
            timeout: Blocking timeout in seconds (0 = block forever)

        Returns:
            Job ID or None if timeout
        """
        result = self.client.blpop(self.QUEUE_KEY, timeout=timeout)
        if result:
            _, job_id = result
            # Move to processing set
            self.client.sadd(self.PROCESSING_KEY, job_id)
            return job_id
        return None

    def get_job_data(self, job_id: str) -> Optional[dict]:
        """Get job data from Redis.

        Args:
            job_id: Job identifier

        Returns:
            Job data dictionary or None
        """
        data = self.client.hgetall(self._job_key(job_id))
        return data if data else None

    def update_status(
        self,
        job_id: str,
        status: str,
        **extra_fields,
    ) -> None:
        """Update job status.

        Args:
            job_id: Job identifier
            status: New status value
            **extra_fields: Additional fields to update
        """
        updates = {"status": status, **extra_fields}
        self.client.hset(self._job_key(job_id), mapping=updates)

    def update_progress(
        self,
        job_id: str,
        stage: str,
        message: str,
        percent: Optional[float] = None,
    ) -> None:
        """Update job progress.

        Args:
            job_id: Job identifier
            stage: Current processing stage
            message: Progress message
            percent: Optional progress percentage
        """
        progress = {
            "stage": stage,
            "message": message,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if percent is not None:
            progress["percent"] = percent

        self.client.hset(
            self._job_key(job_id),
            "progress",
            json.dumps(progress),
        )

    def mark_started(self, job_id: str) -> None:
        """Mark job as started processing.

        Args:
            job_id: Job identifier
        """
        self.update_status(
            job_id,
            status="processing",
            started_at=datetime.utcnow().isoformat(),
        )

    def mark_completed(self, job_id: str, output_path: str) -> None:
        """Mark job as completed.

        Args:
            job_id: Job identifier
            output_path: Path to output file
        """
        self.update_status(
            job_id,
            status="completed",
            completed_at=datetime.utcnow().isoformat(),
            output_path=output_path,
        )
        # Remove from processing set
        self.client.srem(self.PROCESSING_KEY, job_id)

    def mark_failed(self, job_id: str, error: str) -> None:
        """Mark job as failed.

        Args:
            job_id: Job identifier
            error: Error message
        """
        self.update_status(
            job_id,
            status="failed",
            completed_at=datetime.utcnow().isoformat(),
            error=error,
        )
        # Remove from processing set
        self.client.srem(self.PROCESSING_KEY, job_id)

    def is_cancelled(self, job_id: str) -> bool:
        """Check if job has been cancelled.

        Args:
            job_id: Job identifier

        Returns:
            True if job is cancelled
        """
        status = self.client.hget(self._job_key(job_id), "status")
        return status == "cancelled"

    def requeue_processing(self) -> int:
        """Requeue jobs that were left in processing state.

        Called on worker startup to recover from crashes.

        Returns:
            Number of jobs requeued
        """
        processing = self.client.smembers(self.PROCESSING_KEY)
        count = 0
        for job_id in processing:
            # Check if job still exists and is in processing state
            status = self.client.hget(self._job_key(job_id), "status")
            if status == "processing":
                # Requeue the job
                self.client.lpush(self.QUEUE_KEY, job_id)
                self.update_status(job_id, "queued")
                count += 1
            # Remove from processing set either way
            self.client.srem(self.PROCESSING_KEY, job_id)

        if count > 0:
            logger.info(f"Requeued {count} jobs from previous crash")

        return count

    def get_queue_length(self) -> int:
        """Get number of jobs in queue.

        Returns:
            Queue length
        """
        return self.client.llen(self.QUEUE_KEY)

    def get_processing_count(self) -> int:
        """Get number of jobs being processed.

        Returns:
            Number of jobs in processing
        """
        return self.client.scard(self.PROCESSING_KEY)
