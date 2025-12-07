import asyncio
import hashlib
import sqlite3
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams

try:
    from neurosynth.llm.voyage import VoyageClient
except ImportError:
    print(
        "Error: Could not import VoyageClient. Make sure you are running from the project root."
    )
    sys.exit(1)

# --- CONFIGURATION ---
# Using the main 18MB database which contains sources and chunks
REF_DB_PATH = "data/neurosynth.db"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "deep_dx_collection"

# Initialize Voyage Client
voyage_client = VoyageClient()


async def get_embedding_function(text: str):
    """Generate embedding for text using Voyage AI."""
    try:
        # voyage_client.embed_text returns a numpy array
        vector = await voyage_client.embed_text(text)
        return vector.tolist()
    except Exception as e:
        print(f"Embedding error: {e}")
        return None


from neurosynth.shared.checkpoint import CheckpointManager


async def sync_library_to_qdrant():
    print(f"Connecting to Reference Library at {REF_DB_PATH}...")

    # Checkpoint Initialization
    checkpoint = CheckpointManager("bridge_sync_chunks")
    start_offset = checkpoint.get_count()
    if start_offset > 0:
        print(
            f"🔄 Found checkpoint! Resuming from chunk ID: {checkpoint.get_last_processed()} ({start_offset} processed)"
        )

    # 1. Connect to Databases
    if not Path(REF_DB_PATH).exists():
        print(f"Error: Database not found at {REF_DB_PATH}")
        return

    conn = sqlite3.connect(REF_DB_PATH)
    # Use Row factory for convenience
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        client = QdrantClient(url=QDRANT_URL)
        # Test connection
        client.get_collections()
        print(f"Connected to Qdrant at {QDRANT_URL}")
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")
        return

    # 2. Fetch Data
    print("Fetching documents from database...")

    # Check counts
    try:
        cursor.execute("SELECT count(*) FROM sources")
        source_count = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        print(f"Found {source_count} sources and {chunk_count} chunks in database.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return

    # Select chunks
    # We order by ID to ensure stable resumption order
    query = """
        SELECT
            s.id as source_id,
            s.title,
            s.file_path,
            c.id as chunk_id,
            c.content,
            c.page_start
        FROM sources s
        JOIN chunks c ON s.id = c.source_id
        ORDER BY c.id
    """

    cursor.execute(query)
    records = cursor.fetchall()

    if not records:
        print("No records found to sync.")
        return

    # Skip already processed records if resuming
    # Note: Fetching all then slicing is memory inefficient for HUGE datasets but fine for 36k items (metadata only)
    if start_offset > 0:
        if start_offset >= len(records):
            print("All records already processed according to checkpoint.")
            return
        records_to_process = records[start_offset:]
        print(
            f"Resuming: Skipping first {start_offset} records. Processing remaining {len(records_to_process)}."
        )
    else:
        records_to_process = records
        print(f"Starting fresh sync for {len(records)} chunks...")

    # Ensure Collection Exists
    VECTOR_SIZE = 1024

    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if not exists:
        print(f"Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        print(f"Collection '{COLLECTION_NAME}' exists.")

    # Batch Processing
    BATCH_SIZE = 100
    current_batch = []

    total_processed = start_offset

    async def process_batch(batch_items):
        texts = [item["text"] for item in batch_items]
        try:
            # Batch embedding generation
            vectors = await voyage_client.embed_texts(
                texts, batch_size=len(batch_items)
            )
        except Exception as e:
            print(f"Error generating embeddings for batch: {e}")
            return False

        points = []
        last_chunk_id = None

        for i, item in enumerate(batch_items):
            vector = vectors[i]
            if vector is None:
                continue

            if hasattr(vector, "tolist"):
                vector = vector.tolist()

            # ID Generation
            point_id = hashlib.md5(f"{item['chunk_id']}".encode()).hexdigest()
            last_chunk_id = item["chunk_id"]

            payload = {
                "text": item["text"],
                "source_doc_id": item["source_id"],
                "title": item["title"],
                "file_path": item["path"],
                "tier": item["tier"],
                "page": item["page_start"],
                "original_chunk_id": item["chunk_id"],
            }

            points.append(
                models.PointStruct(id=point_id, vector=vector, payload=payload)
            )

        if points:
            try:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                # Checkpoint here
                return True, last_chunk_id
            except Exception as e:
                print(f"Error upserting batch to Qdrant: {e}")
                return False, None
        return False, None

    for row in records_to_process:
        source_id = row["source_id"]
        title = row["title"] or "Unknown"
        path = row["file_path"]
        chunk_id_db = row["chunk_id"]
        text = row["content"]
        page_start = row["page_start"]

        if not text:
            # Still count empty text to keep offsets aligned with cursor?
            # Ideally we shouldn't skip tracking valid rows even if we don't index specific ones
            # For simplicity, we assume robust data and just process valid ones
            continue

        # Determine Tier
        tier = "3"
        title_lower = title.lower()
        if "atlas" in title_lower or "rhoton" in title_lower:
            tier = "1"
        elif "greenberg" in title_lower:
            tier = "2"

        current_batch.append(
            {
                "source_id": source_id,
                "title": title,
                "path": path,
                "chunk_id": chunk_id_db,
                "text": text,
                "page_start": page_start,
                "tier": tier,
            }
        )

        if len(current_batch) >= BATCH_SIZE:
            success, last_id = await process_batch(current_batch)
            if success:
                total_processed += len(current_batch)
                checkpoint.save(last_id, total_processed)  # Save Checkpoint
                print(
                    f"--> Pushed {total_processed} chunks. Encoded {len(current_batch)} items."
                )
            else:
                print("Skipping batch due to error.")

            current_batch = []

    # Final Batch
    if current_batch:
        success, last_id = await process_batch(current_batch)
        if success:
            total_processed += len(current_batch)
            checkpoint.save(last_id, total_processed)
            print(f"--> Pushed remaining chunks. Total: {total_processed}")

    print("Sync Complete.")
    checkpoint.clear()  # Reset on success
    conn.close()


if __name__ == "__main__":
    asyncio.run(sync_library_to_qdrant())
