"""
Database Module

SQLite database with vector search for storing and retrieving content.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from models import (
    SourceMetadata,
    Chunk,
    ExtractedImage,
    DocumentType,
    Specialty,
    ChunkType,
    ImageType,
)
from config import settings


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
        FOREIGN KEY (source_id) REFERENCES sources(id)
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
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
    
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
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sources 
                (id, title, doc_type, file_path, authors, year, specialty, total_pages, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.id,
                metadata.title,
                metadata.doc_type.value,
                str(metadata.file_path),
                metadata.authors,
                metadata.year,
                metadata.specialty.value,
                metadata.total_pages,
                metadata.processed_at.isoformat() if metadata.processed_at else None
            ))
            conn.commit()
    
    def get_source(self, source_id: str) -> Optional[SourceMetadata]:
        """Get a source by ID"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
            
            if row:
                return SourceMetadata(
                    id=row['id'],
                    title=row['title'],
                    doc_type=DocumentType(row['doc_type']),
                    file_path=Path(row['file_path']),
                    authors=row['authors'],
                    year=row['year'],
                    specialty=Specialty(row['specialty']) if row['specialty'] else Specialty.GENERAL,
                    total_pages=row['total_pages'],
                    processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None
                )
            return None
    
    def get_all_sources(self) -> List[SourceMetadata]:
        """Get all sources"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY title").fetchall()
            return [
                SourceMetadata(
                    id=row['id'],
                    title=row['title'],
                    doc_type=DocumentType(row['doc_type']),
                    file_path=Path(row['file_path']),
                    authors=row['authors'],
                    year=row['year'],
                    specialty=Specialty(row['specialty']) if row['specialty'] else Specialty.GENERAL,
                    total_pages=row['total_pages'],
                    processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None
                )
                for row in rows
            ]
    
    def source_exists(self, source_id: str) -> bool:
        """Check if a source exists"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
            return row is not None
    
    # ========================================================================
    # Chunks
    # ========================================================================
    
    def insert_chunk(self, chunk: Chunk) -> None:
        """Insert a chunk"""
        with self._get_conn() as conn:
            embedding_blob = None
            if chunk.embedding:
                embedding_blob = self._serialize_embedding(chunk.embedding)
            
            conn.execute("""
                INSERT OR REPLACE INTO chunks
                (id, source_id, source_title, section_title, content, chunk_type, 
                 page_start, page_end, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.id,
                chunk.source_id,
                chunk.source_title,
                chunk.section_title,
                chunk.content,
                chunk.chunk_type.value,
                chunk.page_start,
                chunk.page_end,
                embedding_blob
            ))
            conn.commit()
    
    def insert_chunks(self, chunks: List[Chunk]) -> None:
        """Insert multiple chunks efficiently"""
        with self._get_conn() as conn:
            for chunk in chunks:
                embedding_blob = None
                if chunk.embedding:
                    embedding_blob = self._serialize_embedding(chunk.embedding)
                
                conn.execute("""
                    INSERT OR REPLACE INTO chunks
                    (id, source_id, source_title, section_title, content, chunk_type, 
                     page_start, page_end, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk.id,
                    chunk.source_id,
                    chunk.source_title,
                    chunk.section_title,
                    chunk.content,
                    chunk.chunk_type.value,
                    chunk.page_start,
                    chunk.page_end,
                    embedding_blob
                ))
            conn.commit()
    
    def get_chunks_by_source(self, source_id: str) -> List[Chunk]:
        """Get all chunks for a source"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE source_id = ?", (source_id,)
            ).fetchall()
            return [self._row_to_chunk(row) for row in rows]
    
    def get_all_chunks(self) -> List[Chunk]:
        """Get all chunks (without embeddings if possible to save memory, but _row_to_chunk deserializes)"""
        with self._get_conn() as conn:
            # We don't strictly need embeddings for BM25, but row_to_chunk reads them.
            # Optimized query could skip embedding blob
            rows = conn.execute("SELECT * FROM chunks").fetchall()
            return [self._row_to_chunk(row) for row in rows]

    def get_all_chunks_with_embeddings(self) -> List[Tuple[Chunk, List[float]]]:
        """Get all chunks with their embeddings for vector search"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE embedding IS NOT NULL"
            ).fetchall()
            
            results = []
            for row in rows:
                chunk = self._row_to_chunk(row)
                embedding = self._deserialize_embedding(row['embedding'])
                results.append((chunk, embedding))
            
            return results
    
    def count_chunks(self) -> int:
        """Count total chunks"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM chunks").fetchone()
            return row['count']
    
    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        """Convert database row to Chunk object"""
        return Chunk(
            id=row['id'],
            source_id=row['source_id'],
            source_title=row['source_title'],
            section_title=row['section_title'] or "",
            content=row['content'],
            chunk_type=ChunkType(row['chunk_type']) if row['chunk_type'] else ChunkType.NARRATIVE,
            page_start=row['page_start'] or 0,
            page_end=row['page_end'] or 0,
            embedding=self._deserialize_embedding(row['embedding']) if row['embedding'] else None
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
            
            conn.execute("""
                INSERT OR REPLACE INTO images
                (id, source_id, file_path, caption, surrounding_text, image_type,
                 page, width, height, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                image.id,
                image.source_id,
                str(image.file_path),
                image.caption,
                image.surrounding_text,
                image.image_type.value,
                image.page,
                image.width,
                image.height,
                embedding_blob
            ))
            conn.commit()
    
    def insert_images(self, images: List[ExtractedImage]) -> None:
        """Insert multiple images"""
        with self._get_conn() as conn:
            for image in images:
                embedding_blob = None
                if image.embedding:
                    embedding_blob = self._serialize_embedding(image.embedding)
                
                conn.execute("""
                    INSERT OR REPLACE INTO images
                    (id, source_id, file_path, caption, surrounding_text, image_type,
                     page, width, height, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    image.id,
                    image.source_id,
                    str(image.file_path),
                    image.caption,
                    image.surrounding_text,
                    image.image_type.value,
                    image.page,
                    image.width,
                    image.height,
                    embedding_blob
                ))
            conn.commit()
    
    def get_images_by_source(self, source_id: str) -> List[ExtractedImage]:
        """Get all images for a source"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE source_id = ?", (source_id,)
            ).fetchall()
            return [self._row_to_image(row) for row in rows]
    
    def get_images_by_ids(self, image_ids: List[str]) -> List[ExtractedImage]:
        """Get images by IDs"""
        if not image_ids:
            return []
        
        with self._get_conn() as conn:
            placeholders = ','.join('?' * len(image_ids))
            rows = conn.execute(
                f"SELECT * FROM images WHERE id IN ({placeholders})", image_ids
            ).fetchall()
            return [self._row_to_image(row) for row in rows]
    
    def get_all_images_with_embeddings(self) -> List[Tuple[ExtractedImage, List[float]]]:
        """Get all images with embeddings for vector search"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE embedding IS NOT NULL"
            ).fetchall()
            
            results = []
            for row in rows:
                image = self._row_to_image(row)
                embedding = self._deserialize_embedding(row['embedding'])
                results.append((image, embedding))
            
            return results
    
    def count_images(self) -> int:
        """Count total images"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM images").fetchone()
            return row['count']
    
    def _row_to_image(self, row: sqlite3.Row) -> ExtractedImage:
        """Convert database row to ExtractedImage object"""
        return ExtractedImage(
            id=row['id'],
            source_id=row['source_id'],
            page=row['page'] or 0,
            file_path=Path(row['file_path']),
            caption=row['caption'] or "",
            surrounding_text=row['surrounding_text'] or "",
            image_type=ImageType(row['image_type']) if row['image_type'] else ImageType.ILLUSTRATION,
            width=row['width'] or 0,
            height=row['height'] or 0,
            embedding=self._deserialize_embedding(row['embedding']) if row['embedding'] else None
        )
    
    # ========================================================================
    # Embedding serialization
    # ========================================================================
    
    def _serialize_embedding(self, embedding: List[float]) -> bytes:
        """Serialize embedding to bytes for storage"""
        import struct
        return struct.pack(f'{len(embedding)}f', *embedding)
    
    def _deserialize_embedding(self, blob: bytes) -> List[float]:
        """Deserialize embedding from bytes"""
        import struct
        n_floats = len(blob) // 4
        return list(struct.unpack(f'{n_floats}f', blob))
    
    # ========================================================================
    # Statistics
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        with self._get_conn() as conn:
            sources = conn.execute("SELECT COUNT(*) as c FROM sources").fetchone()['c']
            chunks = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()['c']
            images = conn.execute("SELECT COUNT(*) as c FROM images").fetchone()['c']
            
            specialties = conn.execute("""
                SELECT specialty, COUNT(*) as c FROM sources 
                GROUP BY specialty ORDER BY c DESC
            """).fetchall()
            
            return {
                "sources": sources,
                "chunks": chunks,
                "images": images,
                "by_specialty": {row['specialty']: row['c'] for row in specialties}
            }
