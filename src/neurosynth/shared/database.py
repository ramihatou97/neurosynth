"""Shared SQLite configuration for Reference Library and NeuroSynth CLI.

This module provides consistent database configuration across both applications
to ensure concurrent access works correctly with WAL mode.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class SharedDatabase:
    """
    Unified SQLite connection manager with WAL mode enforcement.

    Used by both Reference Library GUI and NeuroSynth CLI to ensure
    concurrent access works correctly. WAL mode allows readers and
    writers to operate simultaneously without blocking.

    Attributes:
        db_path: Path to the SQLite database file
    """

    # Consistent settings across both apps for optimal performance and reliability
    PRAGMAS = [
        "PRAGMA journal_mode=WAL",      # Write-ahead logging for concurrency
        "PRAGMA busy_timeout=5000",     # Wait up to 5 seconds for locks
        "PRAGMA synchronous=NORMAL",    # Balance safety and speed
        "PRAGMA temp_store=MEMORY",     # Store temp tables in memory
        "PRAGMA foreign_keys=ON",       # Enforce foreign key constraints
        "PRAGMA cache_size=-64000",     # 64MB cache for better performance
    ]

    def __init__(self, db_path: Path):
        """
        Initialize the shared database manager.

        Args:
            db_path: Path to the SQLite database file.
                     Parent directories will be created if they don't exist.
        """
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """
        Get a properly configured database connection.

        This context manager ensures consistent PRAGMA settings and
        proper cleanup of connections.

        Yields:
            sqlite3.Connection: Configured database connection with Row factory

        Example:
            >>> db = SharedDatabase(Path("~/.neurosynth/cache.db"))
            >>> with db.get_connection() as conn:
            ...     cursor = conn.execute("SELECT * FROM embeddings")
            ...     rows = cursor.fetchall()
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=5.0,
            check_same_thread=False,
        )
        try:
            # Apply all PRAGMAs for consistent configuration
            for pragma in self.PRAGMAS:
                conn.execute(pragma)
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            conn.close()

    def execute_script(self, script: str) -> None:
        """
        Execute a SQL script (e.g., for schema initialization).

        Args:
            script: SQL script to execute (can contain multiple statements)
        """
        with self.get_connection() as conn:
            conn.executescript(script)
            conn.commit()

    @classmethod
    def get_reference_library_db(cls) -> "SharedDatabase":
        """
        Get the Reference Library database instance.

        Returns:
            SharedDatabase configured for the Reference Library cache

        Note:
            Default location: ~/.reference-library/cache.db
        """
        return cls(Path.home() / ".reference-library" / "cache.db")

    @classmethod
    def get_embedding_cache_db(cls) -> "SharedDatabase":
        """
        Get the embedding cache database instance.

        Returns:
            SharedDatabase configured for the NeuroSynth embedding cache

        Note:
            Default location: ~/.neurosynth/embedding_cache/embeddings.db
        """
        return cls(Path.home() / ".neurosynth" / "embedding_cache" / "embeddings.db")

    @classmethod
    def get_neurosynth_project_db(cls, project_path: Path) -> "SharedDatabase":
        """
        Get a project-specific database instance.

        Args:
            project_path: Path to the NeuroSynth project directory

        Returns:
            SharedDatabase configured for the project's data directory
        """
        return cls(project_path / "data" / "cache.db")

    def check_wal_mode(self) -> bool:
        """
        Verify that WAL mode is properly enabled.

        Returns:
            True if WAL mode is active, False otherwise

        This can be used for diagnostics to ensure the database
        is configured correctly for concurrent access.
        """
        with self.get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            return result[0].lower() == "wal" if result else False

    def get_stats(self) -> dict:
        """
        Get database statistics for diagnostics.

        Returns:
            Dictionary with database statistics including:
            - page_count: Total number of pages in the database
            - page_size: Size of each page in bytes
            - wal_mode: Current journal mode
            - foreign_keys: Whether foreign keys are enabled
        """
        with self.get_connection() as conn:
            stats = {}

            cursor = conn.execute("PRAGMA page_count")
            stats["page_count"] = cursor.fetchone()[0]

            cursor = conn.execute("PRAGMA page_size")
            stats["page_size"] = cursor.fetchone()[0]

            cursor = conn.execute("PRAGMA journal_mode")
            stats["wal_mode"] = cursor.fetchone()[0]

            cursor = conn.execute("PRAGMA foreign_keys")
            stats["foreign_keys"] = bool(cursor.fetchone()[0])

            stats["db_size_mb"] = (stats["page_count"] * stats["page_size"]) / (1024 * 1024)

            return stats
