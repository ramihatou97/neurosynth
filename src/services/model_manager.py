"""
Model Manager Service
=====================

Centralized singleton service for managing heavyweight AI models
(BiomedCLIP, ColPali, etc.) to prevent redundant reloading and
manage memory usage efficiently.
"""

import logging
from threading import Lock
from typing import Any, Optional

from src.config import settings

logger = logging.getLogger("ModelManager")


class ModelManager:
    """
    Singleton manager for AI models.
    Ensures models are loaded once and reused across the application.
    """

    _instance: Optional["ModelManager"] = None
    _lock: Lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._biomed_clip = None
        self._colpali_client = None
        self._lock = Lock()
        self._initialized = True
        logger.info("ModelManager initialized (Singleton)")

    def get_biomed_clip(self) -> Any:
        """
        Get or load the BiomedCLIP searcher instance.
        """
        if self._biomed_clip is None:
            with self._lock:
                if self._biomed_clip is None:
                    try:
                        logger.info("Loading Shared BiomedCLIP Model...")
                        from src.neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

                        self._biomed_clip = BiomedCLIPSearcher()
                        logger.info("Shared BiomedCLIP Model Loaded Successfully")
                    except Exception as e:
                        logger.error(f"Failed to load BiomedCLIP: {e}")
                        raise
        return self._biomed_clip

    def get_colpali(self) -> Any:
        """
        Get or load the ColPali client instance.
        """
        if self._colpali_client is None:
            with self._lock:
                if self._colpali_client is None:
                    try:
                        logger.info("Loading Shared ColPali Model...")
                        from src.neurosynth.llm.colpali import get_colpali_client

                        # ColPaliClient is already a singleton, but wrapping it here for consistency
                        self._colpali_client = get_colpali_client()
                        logger.info("Shared ColPali Model Loaded Successfully")
                    except Exception as e:
                        logger.error(f"Failed to load ColPali: {e}")
                        raise
        return self._colpali_client

    def unload_all(self):
        """
        Unload all models to free memory (e.g., when pausing ingestion).
        """
        with self._lock:
            if self._colpali_client:
                # ColPali has its own unload method
                try:
                    self._colpali_client.unload_model()
                except AttributeError:
                    pass
                self._colpali_client = None

            if self._biomed_clip:
                # BiomedCLIP relies on GC, just remove reference
                self._biomed_clip = None

            import gc

            gc.collect()
            logger.info("All AI models unloaded from memory")


def get_model_manager() -> ModelManager:
    """Accessor for the ModelManager singleton."""
    return ModelManager()
