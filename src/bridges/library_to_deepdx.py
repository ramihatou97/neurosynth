#!/usr/bin/env python3
"""
Reference Library → Deep-DX Bridge
===================================
Syncs data from the Reference Library (library.db) to the Deep Search engine
(neurosynth.db + Qdrant vector store).

ETL Pipeline:
1. EXTRACT: Read tracked_files + pdf_text_cache from library.db
2. TRANSFORM: Aggregate pages into chunks, classify specialty, generate embeddings
3. LOAD: Write to neurosynth.db (sources, chunks) and push vectors to Qdrant

Usage:
    python library_to_deepdx_bridge.py [--sample N] [--force] [--skip-qdrant]
"""

import argparse
import asyncio
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams

# Import local modules
try:
    from neurosynth.llm.voyage import VoyageClient
    from models import ChunkType, DocumentType, Specialty, SourceMetadata, Chunk
    from index.database import Database
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the neurosynth root directory.")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Source: Reference Library database
SOURCE_DB_PATH = Path("reference-library/data/library.db")

# Target: Deep-DX database
TARGET_DB_PATH = Path("neurosynth.db")

# Vector store
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "deep_dx_collection"
VECTOR_SIZE = 1024  # Voyage AI embedding dimension

# Chunking parameters
CHUNK_SIZE = 1500  # Characters per chunk (~300-400 tokens)
CHUNK_OVERLAP = 200  # Overlap between chunks

# Batch sizes
EMBEDDING_BATCH_SIZE = 50  # Voyage API batch size
QDRANT_BATCH_SIZE = 100


# =============================================================================
# SPECIALTY CLASSIFICATION
# =============================================================================

SPECIALTY_KEYWORDS = {
    Specialty.SPINE: ["spine", "spinal", "vertebr", "lumbar", "cervical", "thoracic", "disc", "scoliosis"],
    Specialty.TUMOR: ["tumor", "tumour", "glioma", "meningioma", "schwannoma", "oncol", "neoplasm"],
    Specialty.VASCULAR: ["vascular", "aneurysm", "avm", "stroke", "hemorrhage", "carotid", "angiography"],
    Specialty.SKULL_BASE: ["skull base", "acoustic", "pituitary", "sellar", "petrosal", "craniopharyngioma"],
    Specialty.FUNCTIONAL: ["dbs", "deep brain", "parkinson", "tremor", "epilepsy", "functional"],
    Specialty.PEDIATRIC: ["pediatric", "paediatric", "child", "infant", "congenital"],
    Specialty.TRAUMA: ["trauma", "injury", "fracture", "tbi", "concussion"],
    Specialty.ANATOMY: ["anatomy", "neuroanatomy", "atlas", "dissection"],
}

def classify_specialty(title: str, path: str) -> Specialty:
    """Classify document specialty based on title and path."""
    text = f"{title} {path}".lower()
    
    scores = {spec: 0 for spec in Specialty}
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[specialty] += 1
    
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else Specialty.GENERAL


# =============================================================================
# TIER CLASSIFICATION (for search ranking)
# =============================================================================

def classify_tier(title: str, path: str) -> str:
    """Classify document tier for search ranking."""
    text = f"{title} {path}".lower()
    
    # Tier 1: Gold standard references
    tier1_keywords = ["rhoton", "atlas", "7.0 tesla", "7t", "greenberg handbook"]
    if any(kw in text for kw in tier1_keywords):
        return "1"
    
    # Tier 2: Major textbooks
    tier2_keywords = ["youmans", "greenberg", "principles", "schmidek", "winn"]
    if any(kw in text for kw in tier2_keywords):
        return "2"
    
    # Tier 3: Everything else
    return "3"


# =============================================================================
# TEXT CHUNKING
# =============================================================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[tuple[str, int, int]]:
    """Split text into overlapping chunks.
    
    Returns list of (chunk_text, char_start, char_end) tuples.
    """
    if not text or len(text.strip()) < 50:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        # Try to break at sentence boundary
        if end < text_len:
            # Look for sentence end in last 20% of chunk
            search_start = start + int(chunk_size * 0.8)
            best_break = -1
            for punct in [". ", ".\n", "? ", "! "]:
                idx = text.rfind(punct, search_start, end)
                if idx > best_break:
                    best_break = idx + 1
            
            if best_break > search_start:
                end = best_break
        
        chunk_text = text[start:end].strip()
        if len(chunk_text) > 50:  # Minimum viable chunk
            chunks.append((chunk_text, start, end))

        start = end - overlap if end < text_len else text_len

    return chunks


# =============================================================================
# MAIN BRIDGE CLASS
# =============================================================================

class LibraryToDeepDxBridge:
    """Orchestrates the ETL pipeline from Reference Library to Deep-DX."""

    def __init__(
        self,
        source_db: Path = SOURCE_DB_PATH,
        target_db: Path = TARGET_DB_PATH,
        qdrant_url: str = QDRANT_URL,
        skip_qdrant: bool = False
    ):
        self.source_db_path = source_db
        self.target_db_path = target_db
        self.qdrant_url = qdrant_url
        self.skip_qdrant = skip_qdrant

        # Connections (lazy init)
        self._source_conn: Optional[sqlite3.Connection] = None
        self._target_db: Optional[Database] = None
        self._qdrant: Optional[QdrantClient] = None
        self._voyage: Optional[VoyageClient] = None

        # Stats
        self.stats = {
            "sources_processed": 0,
            "chunks_created": 0,
            "chunks_embedded": 0,
            "qdrant_points": 0,
            "errors": [],
        }

    def connect(self) -> bool:
        """Establish all database connections."""
        print("=" * 60)
        print("🔌 CONNECTING TO DATABASES")
        print("=" * 60)

        # Source database
        if not self.source_db_path.exists():
            print(f"❌ Source database not found: {self.source_db_path}")
            return False

        self._source_conn = sqlite3.connect(self.source_db_path)
        self._source_conn.row_factory = sqlite3.Row
        print(f"✅ Source: {self.source_db_path}")

        # Count source data
        cursor = self._source_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tracked_files")
        file_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM pdf_text_cache")
        page_count = cursor.fetchone()[0]
        print(f"   → {file_count:,} files, {page_count:,} cached pages")

        # Target database
        self._target_db = Database(db_path=self.target_db_path)
        print(f"✅ Target: {self.target_db_path}")

        # Qdrant
        if not self.skip_qdrant:
            try:
                self._qdrant = QdrantClient(url=self.qdrant_url)
                self._qdrant.get_collections()
                print(f"✅ Qdrant: {self.qdrant_url}")

                # Ensure collection exists
                collections = [c.name for c in self._qdrant.get_collections().collections]
                if COLLECTION_NAME not in collections:
                    print(f"   → Creating collection '{COLLECTION_NAME}'...")
                    self._qdrant.create_collection(
                        collection_name=COLLECTION_NAME,
                        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
                    )
                else:
                    # Get current count
                    info = self._qdrant.get_collection(COLLECTION_NAME)
                    print(f"   → Collection exists with {info.points_count:,} points")
            except Exception as e:
                print(f"⚠️  Qdrant connection failed: {e}")
                print("   → Continuing without Qdrant sync")
                self.skip_qdrant = True
        else:
            print("⏭️  Qdrant: SKIPPED (--skip-qdrant flag)")

        # Voyage AI client
        self._voyage = VoyageClient()
        print("✅ Voyage AI: Ready")

        return True

    def get_source_files(self, limit: int = 0) -> list[dict]:
        """Get list of source files with aggregated text."""
        cursor = self._source_conn.cursor()

        query = """
            SELECT
                t.pdf_path,
                t.book_series,
                t.chapter_title,
                t.page_count as tracked_page_count,
                COUNT(c.page_number) as cached_pages,
                GROUP_CONCAT(c.page_number) as page_numbers
            FROM tracked_files t
            LEFT JOIN pdf_text_cache c ON t.pdf_path = c.pdf_path
            GROUP BY t.pdf_path
            HAVING cached_pages > 0
            ORDER BY t.pdf_path
        """

        if limit > 0:
            query += f" LIMIT {limit}"

        cursor.execute(query)

        files = []
        for row in cursor:
            files.append({
                "pdf_path": row["pdf_path"],
                "book_series": row["book_series"],
                "chapter_title": row["chapter_title"],
                "cached_pages": row["cached_pages"],
            })

        return files

    def get_page_text(self, pdf_path: str) -> dict[int, str]:
        """Get all page text for a PDF, ordered by page number."""
        cursor = self._source_conn.cursor()
        cursor.execute(
            "SELECT page_number, text_content FROM pdf_text_cache WHERE pdf_path = ? ORDER BY page_number",
            (pdf_path,)
        )
        return {row["page_number"]: row["text_content"] for row in cursor}

    def generate_source_id(self, pdf_path: str) -> str:
        """Generate a stable unique ID for a source."""
        return hashlib.md5(pdf_path.encode()).hexdigest()[:12]

    def generate_chunk_id(self, source_id: str, page: int, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        hash_input = f"{source_id}_{page}_{chunk_index}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    async def process_file(self, file_info: dict) -> tuple[SourceMetadata, list[Chunk]]:
        """Process a single file: create source metadata and chunks."""
        pdf_path = file_info["pdf_path"]
        title = file_info["chapter_title"] or Path(pdf_path).stem.replace("-", " ").replace("_", " ")

        # Generate IDs
        source_id = self.generate_source_id(pdf_path)

        # Classify
        specialty = classify_specialty(title, pdf_path)
        tier = classify_tier(title, pdf_path)

        # Get page text
        pages = self.get_page_text(pdf_path)
        total_pages = max(pages.keys()) + 1 if pages else 0

        # Create source metadata
        source = SourceMetadata(
            id=source_id,
            title=title,
            doc_type=DocumentType.CHAPTER,
            file_path=Path(pdf_path),
            authors=None,
            year=None,
            specialty=specialty,
            total_pages=total_pages,
            processed_at=datetime.now(),
        )

        # Create chunks
        chunks = []
        for page_num, text in sorted(pages.items()):
            if not text or len(text.strip()) < 50:
                continue

            page_chunks = chunk_text(text)
            for i, (chunk_text_content, char_start, char_end) in enumerate(page_chunks):
                chunk_id = self.generate_chunk_id(source_id, page_num, i)

                chunk = Chunk(
                    id=chunk_id,
                    source_id=source_id,
                    source_title=title,
                    section_title=None,  # Could extract from PDF structure
                    content=chunk_text_content,
                    chunk_type=ChunkType.NARRATIVE,
                    page_start=page_num,
                    page_end=page_num,
                    embedding=None,  # Will be filled later
                )
                # Store tier as metadata (not in Chunk dataclass, but we'll use it for Qdrant)
                chunk._tier = tier
                chunks.append(chunk)

        return source, chunks

    async def embed_chunks(self, chunks: list[Chunk]) -> int:
        """Generate embeddings for chunks using Voyage AI."""
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        embedded = 0

        # Process in batches
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch_texts = texts[i:i + EMBEDDING_BATCH_SIZE]
            batch_chunks = chunks[i:i + EMBEDDING_BATCH_SIZE]

            try:
                vectors = await self._voyage.embed_texts(batch_texts, batch_size=len(batch_texts))

                for chunk, vector in zip(batch_chunks, vectors):
                    if vector is not None:
                        if hasattr(vector, 'tolist'):
                            vector = vector.tolist()
                        chunk.embedding = vector
                        embedded += 1

            except Exception as e:
                self.stats["errors"].append(f"Embedding error: {e}")
                print(f"  ⚠️  Embedding batch failed: {e}")

        return embedded

    async def push_to_qdrant(self, chunks: list[Chunk], source: SourceMetadata) -> int:
        """Push embedded chunks to Qdrant vector store."""
        if self.skip_qdrant or not self._qdrant:
            return 0

        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue

            # Generate point ID from chunk ID
            point_id = hashlib.md5(chunk.id.encode()).hexdigest()

            payload = {
                "text": chunk.content,
                "source_doc_id": chunk.source_id,
                "title": chunk.source_title,
                "file_path": str(source.file_path),
                "tier": getattr(chunk, '_tier', '3'),
                "page": chunk.page_start,
                "specialty": source.specialty.value,
                "original_chunk_id": chunk.id,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=chunk.embedding,
                    payload=payload
                )
            )

        if not points:
            return 0

        # Upsert in batches
        pushed = 0
        for i in range(0, len(points), QDRANT_BATCH_SIZE):
            batch = points[i:i + QDRANT_BATCH_SIZE]
            try:
                self._qdrant.upsert(collection_name=COLLECTION_NAME, points=batch)
                pushed += len(batch)
            except Exception as e:
                self.stats["errors"].append(f"Qdrant upsert error: {e}")
                print(f"  ⚠️  Qdrant batch failed: {e}")

        return pushed

    async def run(self, limit: int = 0, force: bool = False):
        """Run the full ETL pipeline."""
        print("\n" + "=" * 60)
        print("🚀 REFERENCE LIBRARY → DEEP-DX BRIDGE")
        print("=" * 60)

        if not self.connect():
            return

        # Get files to process
        files = self.get_source_files(limit=limit)
        total_files = len(files)

        if total_files == 0:
            print("❌ No files with cached text found!")
            return

        print(f"\n📚 Processing {total_files:,} files...")

        # Check existing sources if not forcing
        existing_sources = set()
        if not force:
            with self._target_db._get_conn() as conn:
                cursor = conn.execute("SELECT id FROM sources")
                existing_sources = {row[0] for row in cursor}
            print(f"   → {len(existing_sources):,} sources already in target (use --force to re-process)")

        # Process each file
        for idx, file_info in enumerate(files, 1):
            pdf_path = file_info["pdf_path"]
            title = file_info["chapter_title"] or Path(pdf_path).stem[:40]

            # Check if already processed
            source_id = self.generate_source_id(pdf_path)
            if source_id in existing_sources and not force:
                continue

            print(f"\n[{idx}/{total_files}] {title[:50]}...")

            try:
                # Process file
                source, chunks = await self.process_file(file_info)

                if not chunks:
                    print(f"  ⏭️  No chunks generated (empty text)")
                    continue

                print(f"  📄 {len(chunks)} chunks from {file_info['cached_pages']} pages")

                # Generate embeddings
                embedded = await self.embed_chunks(chunks)
                print(f"  🧠 {embedded} embeddings generated")

                # Save to target database
                self._target_db.insert_source(source)
                self._target_db.insert_chunks(chunks)
                self.stats["sources_processed"] += 1
                self.stats["chunks_created"] += len(chunks)
                self.stats["chunks_embedded"] += embedded

                # Push to Qdrant
                if not self.skip_qdrant:
                    pushed = await self.push_to_qdrant(chunks, source)
                    self.stats["qdrant_points"] += pushed
                    print(f"  📤 {pushed} vectors pushed to Qdrant")

            except Exception as e:
                self.stats["errors"].append(f"{pdf_path}: {e}")
                print(f"  ❌ Error: {e}")

        # Final summary
        self._print_summary()

    def _print_summary(self):
        """Print final statistics."""
        print("\n" + "=" * 60)
        print("📊 SYNC COMPLETE")
        print("=" * 60)
        print(f"  Sources processed: {self.stats['sources_processed']:,}")
        print(f"  Chunks created:    {self.stats['chunks_created']:,}")
        print(f"  Embeddings:        {self.stats['chunks_embedded']:,}")
        print(f"  Qdrant points:     {self.stats['qdrant_points']:,}")

        if self.stats["errors"]:
            print(f"\n⚠️  {len(self.stats['errors'])} errors occurred:")
            for err in self.stats["errors"][:5]:
                print(f"    - {err[:80]}")
            if len(self.stats["errors"]) > 5:
                print(f"    ... and {len(self.stats['errors']) - 5} more")

        # Verify counts
        print("\n📈 Database Verification:")
        with self._target_db._get_conn() as conn:
            sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            print(f"  neurosynth.db: {sources:,} sources, {chunks:,} chunks")

        if not self.skip_qdrant and self._qdrant:
            info = self._qdrant.get_collection(COLLECTION_NAME)
            print(f"  Qdrant:        {info.points_count:,} vectors")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sync Reference Library to Deep-DX")
    parser.add_argument("--sample", type=int, default=0, help="Process only N files (for testing)")
    parser.add_argument("--force", action="store_true", help="Re-process existing sources")
    parser.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant sync (DB only)")
    args = parser.parse_args()

    bridge = LibraryToDeepDxBridge(skip_qdrant=args.skip_qdrant)
    asyncio.run(bridge.run(limit=args.sample, force=args.force))


if __name__ == "__main__":
    main()

