"""Logging infrastructure for Reference Library App."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: Path | None = None,
    log_level: int = logging.INFO,
    console_output: bool = True,
) -> logging.Logger:
    """
    Set up logging infrastructure with file rotation.

    Args:
        log_dir: Directory for log files. Defaults to ~/.neurosynth/logs/
        log_level: Logging level (default: INFO)
        console_output: Whether to also log to console

    Returns:
        Configured root logger
    """
    # Default log directory
    if log_dir is None:
        log_dir = Path.home() / ".neurosynth" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger
    logger = logging.getLogger("reference_library")
    logger.setLevel(log_level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_dir / "reference_library.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.

    Args:
        name: Module name (e.g., 'search.pdf_searcher')

    Returns:
        Logger instance for the module
    """
    return logging.getLogger(f"reference_library.{name}")


# Initialize logging on import
_root_logger = setup_logging()
