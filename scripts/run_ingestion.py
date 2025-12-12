import logging
import sys
import uuid
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import settings
from src.index.chunker import SemanticChunker
from src.index.database import Database
from src.ingest.processor import DocumentProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IngestionScript")

NAMESPACE_NEUROSYNTH = uuid.uuid5(uuid.NAMESPACE_DNS, "neurosynth.org")


def get_uuid(text_id: str) -> str:
    """Hash string ID to a valid UUID string for Qdrant validation."""
    return str(uuid.uuid5(NAMESPACE_NEUROSYNTH, str(text_id)))


def main():
    logger.info("🚀 Starting Ingestion Pipeline...")

    # Initialize Database
    db = Database()

    # Initialize Processor
    logger.info("Initializing DocumentProcessor...")
    processor = DocumentProcessor(
        chunk_size=1500,
        chunk_overlap=200,
        entropy_threshold=4.5,
        text_embedding_model="voyage-3-lite",
        # Use centralized config
        image_embedding_model=settings.image_embedding_model,
        enable_vector_graphics=True,  # Phase 4 Enabled
        enable_cross_references=True,  # Phase 4 Enabled
    )

    # Initialize Qdrant Client (Docker Service)
    qdrant = None
    collection_name = "neurosurgical_figures_hybrid"

    try:
        # Use centralized config URL (handles Docker service name via env var or default)
        qdrant = QdrantClient(url=settings.qdrant_url)

        # Ensure collection exists
        if not qdrant.collection_exists(collection_name):
            logger.info(f"Creating Qdrant collection: {collection_name}")
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )
        logger.info(f"✓ Connected to Qdrant at {settings.qdrant_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        qdrant = None

    # Initialize Chunker
    chunker = SemanticChunker(chunk_size=1500, chunk_overlap=200)

    # Locate Library
    library_path = settings.library_path
    if not library_path.exists():
        logger.error(f"Library path not found: {library_path}")
        return

    pdf_files = list(library_path.rglob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDFs in {library_path}")

    if not pdf_files:
        logger.warning("No PDFs to process.")
        return

    # Get already indexed sources to skip duplicates
    existing_paths = set()
    try:
        for src in db.get_all_sources():
            if hasattr(src, "file_path") and src.file_path:
                existing_paths.add(Path(src.file_path).resolve())
    except Exception as e:
        logger.warning(f"Could not get existing sources: {e}")

    # Filter to only unindexed PDFs
    files_to_process = [p for p in pdf_files if p.resolve() not in existing_paths]

    logger.info(
        f"Found {len(files_to_process)} unindexed PDFs (skipping {len(existing_paths)} already indexed)"
    )

    if not files_to_process:
        logger.info("All PDFs already indexed!")
        return

    processed = 0
    failed = 0

    for pdf_path in files_to_process:
        try:
            logger.info(f"📄 Processing {pdf_path.name}...")

            # 1. Process
            result = processor.process(pdf_path)

            # 2. Chunk
            chunks = chunker.chunk_document(result)

            # 3. Store
            db.insert_source(result.metadata)
            db.insert_chunks(chunks)
            for img in result.images:
                db.insert_image(img)

            # 4. Store Vectors in Qdrant
            if qdrant and result.images:
                try:
                    points = []
                    for img in result.images:
                        if img.embedding:
                            points.append(
                                PointStruct(
                                    id=get_uuid(img.id),  # Hashed to valid UUID
                                    vector=img.embedding,  # List[float]
                                    payload={
                                        "source_pdf": img.source_id,
                                        "page_num": img.page,
                                        "path": str(img.file_path),
                                        "caption": img.caption,
                                        "context": (
                                            img.surrounding_text[:1000]
                                            if img.surrounding_text
                                            else ""
                                        ),
                                        # "modality": "unknown", # Optional: can add if needed
                                        "image_type": img.image_type.value,
                                        # "detected_regions": img.detected_regions # Lists in payload can be tricky, check schema
                                    },
                                )
                            )

                    if points:
                        qdrant.upsert(collection_name=collection_name, points=points)
                        logger.info(f"Inserted {len(points)} vectors to Qdrant")

                except Exception as q_err:
                    logger.error(f"Failed to upsert vectors to Qdrant: {q_err}")

            logger.info(
                f"✅ [{processed+1}/{len(files_to_process)}] {pdf_path.name}: {len(chunks)} chunks, {len(result.images)} images"
            )
            processed += 1

        except Exception as e:
            logger.error(f"❌ Failed to process {pdf_path.name}: {e}")
            failed += 1

    logger.info(f"✨ Ingestion Complete: {processed} indexed, {failed} failed")


if __name__ == "__main__":
    main()
