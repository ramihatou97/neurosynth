"""
Database Module

SQLite database with vector search for storing and retrieving content.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from src.config import settings
from src.models import (
    Chunk,
    ChunkType,
    DocumentType,
    ExtractedImage,
    ImageType,
    SourceMetadata,
    Specialty,
)


class Database:
    """
    SQLite database for storing processed documents, chunks, and images.

    Uses sqlite-vec for vector similarity search when available,
    falls back to brute-force cosine similarity otherwise.
    """

    SCHEMA = """
    -- Sources (your library documents)
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        authors TEXT,
        year INTEGER,
        specialty TEXT DEFAULT 'general',
        total_pages INTEGER DEFAULT 0,
        processed_at TIMESTAMP
    );

    -- Chunks (searchable content units)
    CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id),
        source_title TEXT NOT NULL,
        section_title TEXT,
        content TEXT NOT NULL,
        chunk_type TEXT DEFAULT 'narrative',
        page_start INTEGER,
        page_end INTEGER,
        embedding BLOB,
        image_ids TEXT,  -- JSON list of IDs
        also_in_sources TEXT,  -- JSON list of source IDs
        metadata TEXT,    -- JSON dictionary
        evidence_level TEXT DEFAULT 'unknown',
        FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS chunk_search USING fts5(
        content,
        section_title,
        source_title
    );

    -- Images (with context)
    CREATE TABLE IF NOT EXISTS images (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id),
        chunk_id TEXT REFERENCES chunks(id),
        file_path TEXT NOT NULL,
        caption TEXT,
        surrounding_text TEXT,
        image_type TEXT DEFAULT 'illustration',
        page INTEGER,
        width INTEGER,
        height INTEGER,
        embedding BLOB
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
    CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);
    CREATE INDEX IF NOT EXISTS idx_images_source ON images(source_id);
    CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type);
    CREATE INDEX IF NOT EXISTS idx_sources_specialty ON sources(specialty);
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            self.db_path = settings.database_path
        else:
            self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database and create tables"""
        conn = self._get_conn()
        conn.executescript(self.SCHEMA)

        # Check if evidence_level column exists (migration for existing DBs)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(chunks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "evidence_level" not in columns:
            cursor.execute(
                "ALTER TABLE chunks ADD COLUMN evidence_level TEXT DEFAULT 'unknown'"
            )

        # Check for other new columns for migration
        if "image_ids" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN image_ids TEXT")
        if "also_in_sources" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN also_in_sources TEXT")
        if "metadata" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN metadata TEXT")

        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ========================================================================
    # Sources
    # ========================================================================

    def insert_source(self, metadata: SourceMetadata) -> None:
        """Insert or update a source document"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO sources
            (id, title, doc_type, file_path, authors, year, specialty, total_pages, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.id,
                metadata.title,
                metadata.doc_type.value,
                str(metadata.file_path),
                metadata.authors,
                metadata.year,
                metadata.specialty.value,
                metadata.total_pages,
                (metadata.processed_at.isoformat() if metadata.processed_at else None),
            ),
        )
        conn.commit()
        conn.close()

    def get_source(self, source_id: str) -> SourceMetadata | None:
        """Get a source by ID"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        conn.close()

        if row:
            return SourceMetadata(
                id=row["id"],
                title=row["title"],
                doc_type=DocumentType(row["doc_type"]),
                file_path=Path(row["file_path"]),
                authors=row["authors"],
                year=row["year"],
                specialty=(
                    Specialty(row["specialty"])
                    if row["specialty"]
                    else Specialty.GENERAL
                ),
                total_pages=row["total_pages"],
                processed_at=(
                    datetime.fromisoformat(row["processed_at"])
                    if row["processed_at"]
                    else None
                ),
            )
        return None

    def get_all_sources(self) -> list[SourceMetadata]:
        """Get all sources"""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM sources ORDER BY title").fetchall()
        conn.close()
        return [
            SourceMetadata(
                id=row["id"],
                title=row["title"],
                doc_type=DocumentType(row["doc_type"]),
                file_path=Path(row["file_path"]),
                authors=row["authors"],
                year=row["year"],
                specialty=(
                    Specialty(row["specialty"])
                    if row["specialty"]
                    else Specialty.GENERAL
                ),
                total_pages=row["total_pages"],
                processed_at=(
                    datetime.fromisoformat(row["processed_at"])
                    if row["processed_at"]
                    else None
                ),
            )
            for row in rows
        ]

    def source_exists(self, source_id: str) -> bool:
        """Check if a source exists"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        conn.close()
        return row is not None

    def update_source_specialty(self, source_id: str, specialty: "Specialty") -> None:
        """Update the specialty classification for a source"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sources SET specialty = ? WHERE id = ?",
            (specialty.value, source_id),
        )
        conn.commit()
        conn.close()

    def update_source_doctype(self, source_id: str, doc_type: "DocumentType") -> None:
        """Update the document type for a source"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sources SET doc_type = ? WHERE id = ?", (doc_type.value, source_id)
        )
        conn.commit()
        conn.close()

    def delete_source(self, source_id: str) -> None:
        """Delete a source and all associated chunks and images"""
        conn = self._get_conn()
        # Delete images first (foreign key constraint)
        conn.execute("DELETE FROM images WHERE source_id = ?", (source_id,))
        # Delete chunks
        conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        # Delete source
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()
        conn.close()

    # ========================================================================
    # Chunks
    # ========================================================================

    def insert_chunk(self, chunk: Chunk) -> None:
        """Insert a chunk"""
        conn = self._get_conn()
        cursor = conn.cursor()

        embedding_blob = None
        if chunk.embedding:
            embedding_blob = self._serialize_embedding(chunk.embedding)

        cursor.execute(
            """
            INSERT OR REPLACE INTO chunks
            (id, source_id, source_title, section_title, content, chunk_type,
             page_start, page_end, embedding, image_ids, also_in_sources, metadata, evidence_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.id,
                chunk.source_id,
                chunk.source_title,
                chunk.section_title,
                chunk.content,
                chunk.chunk_type.value,
                chunk.page_start,
                chunk.page_end,
                embedding_blob,
                json.dumps(chunk.image_ids),
                json.dumps(chunk.also_in_sources),
                json.dumps(chunk.metadata),
                chunk.evidence_level,
            ),
        )
        conn.commit()
        conn.close()

    def insert_chunks(self, chunks: list[Chunk]) -> None:
        """Insert multiple chunks efficiently"""
        if not chunks:
            return

        conn = self._get_conn()
        cursor = conn.cursor()

        data = []
        for chunk in chunks:
            embedding_blob = None
            if chunk.embedding:
                embedding_blob = self._serialize_embedding(chunk.embedding)

            data.append(
                (
                    chunk.id,
                    chunk.source_id,
                    chunk.source_title,
                    chunk.section_title,
                    chunk.content,
                    chunk.chunk_type.value,
                    chunk.page_start,
                    chunk.page_end,
                    embedding_blob,
                    json.dumps(chunk.image_ids),
                    json.dumps(chunk.also_in_sources),
                    json.dumps(chunk.metadata),
                    chunk.evidence_level,
                )
            )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO chunks
            (id, source_id, source_title, section_title, content, chunk_type,
             page_start, page_end, embedding, image_ids, also_in_sources, metadata, evidence_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )
        conn.commit()
        conn.close()

    def get_chunks_by_source(self, source_id: str) -> list[Chunk]:
        """Get all chunks for a source"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM chunks WHERE source_id = ?", (source_id,)
        ).fetchall()
        conn.close()
        return [self._row_to_chunk(row) for row in rows]

    def get_all_chunks(self) -> list[Chunk]:
        """Get all chunks (without embeddings if possible to save memory, but _row_to_chunk deserializes)"""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM chunks").fetchall()
        conn.close()
        return [self._row_to_chunk(row) for row in rows]

    def get_all_chunks_with_embeddings(self) -> list[tuple[Chunk, list[float]]]:
        """Get all chunks with their embeddings for vector search"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM chunks WHERE embedding IS NOT NULL"
        ).fetchall()
        conn.close()

        results = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            embedding = self._deserialize_embedding(row["embedding"])
            results.append((chunk, embedding))

        return results

    def count_chunks(self) -> int:
        """Count total chunks"""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as count FROM chunks").fetchone()
        conn.close()
        return row["count"]

    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        """Convert database row to Chunk object"""
        # Helper to safely get column if it exists (for migration support)
        evidence = "unknown"
        if "evidence_level" in row.keys():
            evidence = row["evidence_level"]

        image_ids = []
        if "image_ids" in row.keys() and row["image_ids"]:
            image_ids = json.loads(row["image_ids"])

        also_in_sources = []
        if "also_in_sources" in row.keys() and row["also_in_sources"]:
            also_in_sources = json.loads(row["also_in_sources"])

        metadata = {}
        if "metadata" in row.keys() and row["metadata"]:
            metadata = json.loads(row["metadata"])

        return Chunk(
            id=row["id"],
            source_id=row["source_id"],
            source_title=row["source_title"],
            section_title=row["section_title"] or "",
            content=row["content"],
            chunk_type=(
                ChunkType(row["chunk_type"])
                if row["chunk_type"]
                else ChunkType.NARRATIVE
            ),
            page_start=row["page_start"] or 0,
            page_end=row["page_end"] or 0,
            embedding=(
                self._deserialize_embedding(row["embedding"])
                if row["embedding"]
                else None
            ),
            image_ids=image_ids,
            also_in_sources=also_in_sources,
            metadata=metadata,
            evidence_level=evidence,
        )

    # ========================================================================
    # Images
    # ========================================================================

    def insert_image(self, image: ExtractedImage) -> None:
        """Insert an image"""
        with self._get_conn() as conn:
            embedding_blob = None
            if image.embedding:
                embedding_blob = self._serialize_embedding(image.embedding)

            conn.execute(
                """
                INSERT OR REPLACE INTO images
                (id, source_id, file_path, caption, surrounding_text, image_type,
                 page, width, height, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    image.id,
                    image.source_id,
                    str(image.file_path),
                    image.caption,
                    image.surrounding_text,
                    image.image_type.value,
                    image.page,
                    image.width,
                    image.height,
                    embedding_blob,
                ),
            )
            conn.commit()

    def insert_images(self, images: list[ExtractedImage]) -> None:
        """Insert multiple images"""
        with self._get_conn() as conn:
            for image in images:
                embedding_blob = None
                if image.embedding:
                    embedding_blob = self._serialize_embedding(image.embedding)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO images
                    (id, source_id, file_path, caption, surrounding_text, image_type,
                     page, width, height, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        image.id,
                        image.source_id,
                        str(image.file_path),
                        image.caption,
                        image.surrounding_text,
                        image.image_type.value,
                        image.page,
                        image.width,
                        image.height,
                        embedding_blob,
                    ),
                )
            conn.commit()

    def get_all_images(self) -> list[ExtractedImage]:
        """Get all images"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM images").fetchall()
            return [self._row_to_image(row) for row in rows]

    def get_images_without_embeddings(self) -> list[ExtractedImage]:
        """Get images that need embeddings (backfill)"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE embedding IS NULL"
            ).fetchall()
            return [self._row_to_image(row) for row in rows]

    def get_image_by_id(self, image_id: str) -> ExtractedImage | None:
        """Get a single image by ID"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM images WHERE id = ?", (image_id,)
            ).fetchone()
            return self._row_to_image(row) if row else None

    def update_image_embedding(self, image_id: str, embedding: list[float]) -> None:
        """Update an image's embedding"""
        blob = self._serialize_embedding(embedding)
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE images SET embedding = ? WHERE id = ?
                """,
                (blob, image_id),
            )
            conn.commit()

    def get_images_by_source(self, source_id: str) -> list[ExtractedImage]:
        """Get all images for a source"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE source_id = ?", (source_id,)
            ).fetchall()
            return [self._row_to_image(row) for row in rows]

    def get_images_by_ids(self, image_ids: list[str]) -> list[ExtractedImage]:
        """Get images by IDs"""
        if not image_ids:
            return []

        with self._get_conn() as conn:
            placeholders = ",".join("?" * len(image_ids))
            rows = conn.execute(
                f"SELECT * FROM images WHERE id IN ({placeholders})", image_ids
            ).fetchall()
            return [self._row_to_image(row) for row in rows]

    def get_all_images_with_embeddings(
        self,
    ) -> list[tuple[ExtractedImage, list[float]]]:
        """Get all images with embeddings for vector search"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE embedding IS NOT NULL"
            ).fetchall()

            results = []
            for row in rows:
                image = self._row_to_image(row)
                embedding = self._deserialize_embedding(row["embedding"])
                results.append((image, embedding))

            return results

    def count_images(self) -> int:
        """Count total images"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM images").fetchone()
            return row["count"]

    def _row_to_image(self, row: sqlite3.Row) -> ExtractedImage:
        """Convert database row to ExtractedImage object"""
        return ExtractedImage(
            id=row["id"],
            source_id=row["source_id"],
            page=row["page"] or 0,
            file_path=Path(row["file_path"]),
            caption=row["caption"] or "",
            surrounding_text=row["surrounding_text"] or "",
            image_type=(
                ImageType(row["image_type"])
                if row["image_type"]
                else ImageType.ILLUSTRATION
            ),
            width=row["width"] or 0,
            height=row["height"] or 0,
            embedding=(
                self._deserialize_embedding(row["embedding"])
                if row["embedding"]
                else None
            ),
        )

    # ========================================================================
    # Embedding serialization
    # ========================================================================

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        """Serialize embedding to bytes for storage"""
        import struct

        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, blob: bytes) -> list[float]:
        """Deserialize embedding from bytes"""
        import struct

        n_floats = len(blob) // 4
        return list(struct.unpack(f"{n_floats}f", blob))

    # ========================================================================
    # Statistics & Helpers
    # ========================================================================

    def get_image_counts_per_source(self) -> dict[str, int]:
        """Get mapping of source_id to number of extracted images"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT source_id, COUNT(*) as c FROM images GROUP BY source_id"
            ).fetchall()
            return {row["source_id"]: row["c"] for row in rows}

    def get_stats(self) -> dict:
        """Get database statistics"""
        with self._get_conn() as conn:
            sources = conn.execute("SELECT COUNT(*) as c FROM sources").fetchone()["c"]
            chunks = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
            images = conn.execute("SELECT COUNT(*) as c FROM images").fetchone()["c"]

            specialties = conn.execute(
                """
                SELECT specialty, COUNT(*) as c FROM sources
                GROUP BY specialty ORDER BY c DESC
            """
            ).fetchall()

            return {
                "sources": sources,
                "chunks": chunks,
                "images": images,
                "by_specialty": {row["specialty"]: row["c"] for row in specialties},
            }

    def reset_all_data(self) -> dict:
        """
        Clear all indexed data from the database.
        Returns counts of deleted records.
        """
        with self._get_conn() as conn:
            # Get counts before deletion
            sources_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            chunks_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            images_count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]

            # Delete in order (respect foreign keys)
            conn.execute("DELETE FROM chunk_search")
            conn.execute("DELETE FROM images")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM sources")
            conn.commit()

            return {
                "sources_deleted": sources_count,
                "chunks_deleted": chunks_count,
                "images_deleted": images_count,
            }
