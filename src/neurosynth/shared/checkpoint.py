import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages state persistence for long-running processes (Bridge Sync, Image Extraction).
    Allows pausing and resuming by saving progress to a JSON file.
    """

    def __init__(self, task_id: str, checkpoint_dir: str = ".checkpoints"):
        self.task_id = task_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_file = self.checkpoint_dir / f"{task_id}.json"

        # Create dir if not exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.state = {
            "last_processed_id": None,
            "processed_count": 0,
            "timestamp": None,
            "metadata": {},
        }
        self._load()

    def _load(self):
        """Load state from checkpoint file if it exists."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file) as f:
                    data = json.load(f)
                    self.state.update(data)
                logger.info(f"Loaded checkpoint for '{self.task_id}': {self.state}")
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

    def save(self, last_id: Any, count: int, metadata: dict = None):
        """Save current progress."""
        self.state["last_processed_id"] = last_id
        self.state["processed_count"] = count
        self.state["timestamp"] = time.time()
        if metadata:
            self.state["metadata"].update(metadata)

        try:
            # Atomic write
            temp_file = self.checkpoint_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=2)
            temp_file.replace(self.checkpoint_file)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def get_last_processed(self):
        """Get ID of last successfully processed item."""
        return self.state.get("last_processed_id")

    def get_count(self):
        return self.state.get("processed_count", 0)

    def clear(self):
        """Clear checkpoint (e.g., after successful completion)."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            self.state = {"last_processed_id": None, "processed_count": 0}
            logger.info(f"Checkpoint cleared for '{self.task_id}'")
