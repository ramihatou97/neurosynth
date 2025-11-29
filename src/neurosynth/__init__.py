"""
NeuroSynth - Neurosurgical Knowledge Synthesis System

Transform multiple neurosurgical reference sources into comprehensive,
deduplicated chapters with zero information loss.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

__version__ = "0.1.0"

# Configure logging
_log_dir = Path.home() / ".neurosynth" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)

_log_file = _log_dir / "neurosynth.log"

# Create logger
logger = logging.getLogger("neurosynth")
logger.setLevel(logging.DEBUG)

# File handler with rotation (10MB, 5 backups)
_file_handler = RotatingFileHandler(
    _log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
)

# Console handler (errors only, to not interfere with Rich output)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.ERROR)
_console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

# Add handlers if not already added
if not logger.handlers:
    logger.addHandler(_file_handler)
    logger.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a module."""
    return logging.getLogger(f"neurosynth.{name}")
