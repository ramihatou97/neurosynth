import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from datetime import datetime

from src.ai.client import AIClient
from src.index.database import Database
from src.models import Chunk, ChunkType, DocumentType, SourceMetadata, Specialty


def seed_db():
    print("🌱 Seeding Database with sample content...")
    db = Database(db_path=Path("neurosynth.db"))

    # Check if already seeded
    if db.count_chunks() > 0:
        print("Database already has content. Skipping seed.")
        return

    # Use AI Client for embeddings if possible
    ai_client = AIClient()

    # Create Source
    source = SourceMetadata(
        id="sample_doc_1",
        title="Surgical Management of Acoustic Neuroma",
        doc_type=DocumentType.CHAPTER,
        file_path=Path("sample.pdf"),
        authors="Smith et al.",
        year=2024,
        specialty=Specialty.SKULL_BASE,
        total_pages=10,
        processed_at=datetime.now(),
    )
    db.insert_source(source)

    # Create Chunks (Content that matches our test topic)
    texts = [
        "The translabyrinthine approach is the preferred method for removing acoustic neuromas when hearing preservation is not a goal.",
        "Key landmarks for the translabyrinthine approach include the sigmoid sinus, facial nerve, and jugular bulb.",
        "A mastoidectomy is performed, identifying the antrum and unroofing the sigmoid sinus.",
        "The facial nerve is skeletonized but left covered by a thin layer of bone to prevent injury.",
        "Complications can include CSF leak, facial nerve palsy, and hearing loss (expected).",
    ]

    chunks = []
    print("Generating embeddings...")
    embeddings = ai_client.get_embeddings(texts)

    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        chunk = Chunk(
            id=f"chunk_{i}",
            source_id=source.id,
            source_title=source.title,
            section_title="Operative Technique",
            content=text,
            chunk_type=ChunkType.NARRATIVE,
            page_start=1,
            page_end=1,
            embedding=emb,
        )
        chunks.append(chunk)

    db.insert_chunks(chunks)
    print(f"✅ Inserted {len(chunks)} chunks.")


if __name__ == "__main__":
    seed_db()
