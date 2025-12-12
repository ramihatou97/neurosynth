import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.index.database import Database
from src.models import Chunk
from src.neurosynth.llm.embeddings import EmbeddingClient


async def backfill_embeddings(limit: int = 20):
    print(f"🚀 Starting embedding backfill (Sample Limit: {limit})...")

    try:
        db = Database()
        print(f"Connected to DB at: {db.db_path}")

        # 1. Fetch chunks without embeddings
        # We need to manually query because get_images_without_embeddings exists but get_chunks_without_embeddings might not?
        # Let's check Database class or just query directly.
        # Database class in memory didn't show explicit get_chunks_without_embeddings.
        # But we can query safely.

        with db._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM chunks WHERE embedding IS NULL LIMIT {limit}"
            ).fetchall()

        chunks = [db._row_to_chunk(row) for row in rows]

        if not chunks:
            print("✅ No chunks found needing embeddings!")
            return

        print(f"Found {len(chunks)} chunks to process.")

        # 2. Initialize Client
        client = EmbeddingClient()

        # 3. Process in batches
        BATCH_SIZE = 10
        total_embedded = 0

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c.content for c in batch]

            print(f"  Processing batch {i//BATCH_SIZE + 1} ({len(batch)} chunks)...")

            try:
                embeddings = await client.embed_async(texts)

                # Update DB
                with db._get_conn() as conn:
                    for chunk, vec in zip(batch, embeddings):
                        # Serialize
                        blob = db._serialize_embedding(vec)
                        conn.execute(
                            "UPDATE chunks SET embedding = ? WHERE id = ?",
                            (blob, chunk.id),
                        )
                    conn.commit()

                total_embedded += len(batch)
                print(f"  ✅ Saved {len(batch)} embeddings.")

            except Exception as e:
                print(f"  ❌ Batch failed: {e}")

        print(f"\n🎉 Backfill complete! Processed {total_embedded} chunks.")

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(backfill_embeddings(limit=6000))
